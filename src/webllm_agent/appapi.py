"""The app's server side: the page itself and its API, served by the bridge (127.0.0.1:20130).

    /app/                  the compiled app (src/webllm_agent/static/app/), token injected
    GET  /api/estado       every piece and every AI with a traffic-light state
    POST /api/preguntar    ask one or several AIs; live progress as server-sent events
    GET  /api/historial    past runs (asks and chains) with their lock (journal check)
    GET  /api/historial/<id>, /api/historial/<id>/exportar
    POST /api/reanudar     lift an AI's protective pause
    POST /api/comprobar    open a chat page and report whether there is a session (sends nothing)
    POST /api/conectar     same, and bring the webllm window forward so Iván can log in
    POST /api/encender-omniroute, /api/encender-local (LM Studio / Ollama)
    POST /api/anadir       add a chat site by its address (the extension asks permission and tests it)
    GET  /api/anadir/<id>  how that test is going, step by step
    POST /api/quitar       remove a site added that way; GET /api/icono/<key> its icon

Only answers on this PC (the bridge's local-only middleware) and only with the bridge token,
which the app receives inside its HTML. Answers are untrusted text: the app renders them as
markdown without raw HTML, and this module never executes anything they contain.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlsplit

from aiohttp import web

from . import flows
from .broadcaster import GatewayError, verify_run
from .config import (
    PROJECT_ROOT, AppConfig, ProviderConfig, custom_provider, is_blocked_model, remove_custom_ai, save_custom_ai,
)
from .guard import Guard
from .local import LocalModels, label_for
from .omniroute import load_api_key

if TYPE_CHECKING:
    from .bridge import Bridge

APP_DIR = Path(__file__).with_name("static") / "app"
SITE_URLS = {
    "qwen": "https://chat.qwen.ai/",
    "deepseek": "https://chat.deepseek.com/",
    "zai": "https://chat.z.ai/",
    "meta": "https://www.meta.ai/",
}
RUN_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
RECENT_S = 15 * 60
MAX_PROMPT = 100_000
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
# Codes (flows.error_code) that say something about the AI right now, for the traffic light.
RECENT_STATE = {
    "login_required": "sin_sesion",
    "site_busy": "saturada", "overloaded": "saturada", "rate_limited": "saturada",
}


def start_omniroute() -> None:
    """Start OmniRoute with its own launcher, in a minimized window (Windows)."""
    script = PROJECT_ROOT / "herramientas" / "start-omniroute.cmd"
    subprocess.Popen(["cmd", "/c", "start", "OmniRoute", "/min", str(script), "/nopause"],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def site_of(p: ProviderConfig) -> str | None:
    """The Chrome chat site of a browser provider (``browser/zai`` -> ``zai``)."""
    return p.model.split("/", 1)[1] if p.gateway == "bridge" and "/" in p.model else None


class AppApi:
    def __init__(self, bridge: "Bridge", *, omniroute_launcher: Callable[[], None] | None = start_omniroute,
                 app_dir: Path = APP_DIR) -> None:
        self.bridge = bridge
        self.omniroute_launcher = omniroute_launcher
        self.app_dir = app_dir
        self.recent: dict[str, tuple[str, str, float]] = {}  # AI name -> (state, detail, when)
        self.show_wait_s = 8.0  # an extension older than 0.4.0 never answers "show"
        self.local = LocalModels()
        self.adding: dict[str, dict[str, Any]] = {}  # add_id -> progress of "+ Añadir otra IA"
        self._tasks: set[asyncio.Task] = set()  # test messages in flight (kept so they are not collected)
        self._last_omni_start = -1e9

    @property
    def cfg(self):
        return self.bridge.cfg

    def register(self, app: web.Application) -> None:
        app.router.add_get("/app", self.to_app)
        app.router.add_get("/app/{path:.*}", self.static)
        app.router.add_get("/api/estado", self.estado)
        app.router.add_post("/api/preguntar", self.preguntar)
        app.router.add_get("/api/historial", self.historial)
        app.router.add_get("/api/historial/{run_id}", self.detalle)
        app.router.add_get("/api/historial/{run_id}/exportar", self.exportar)
        app.router.add_post("/api/reanudar", self.reanudar)
        app.router.add_post("/api/comprobar", self.comprobar)
        app.router.add_post("/api/conectar", self.conectar)
        app.router.add_post("/api/encender-omniroute", self.encender_omniroute)
        app.router.add_post("/api/encender-local", self.encender_local)
        app.router.add_post("/api/anadir", self.anadir)
        app.router.add_get("/api/anadir/{add_id}", self.anadir_estado)
        app.router.add_post("/api/quitar", self.quitar)
        app.router.add_get("/api/icono/{key}", self.icono)

    # ---------------------------------------------------------------- helpers

    def _authorized(self, request: web.Request) -> bool:
        token = self.bridge.token
        return (request.headers.get("Authorization", "") == f"Bearer {token}"
                or request.query.get("token") == token)

    @staticmethod
    def _fail(status: int, message: str, code: str) -> web.Response:
        return web.json_response({"error": message, "code": code}, status=status)

    def _unauthorized(self) -> web.Response:
        return self._fail(401, "Esta ventana está caducada: ciérrala y vuelve a abrir webllm.", "unauthorized")

    async def _cfg(self, force: bool = False) -> AppConfig:
        """The configured AIs plus the models found in the programs on this PC."""
        await self.local.refresh(self.cfg, force)
        return self.local.with_providers(self.cfg)

    def _guard_for(self, p: ProviderConfig) -> tuple[Guard, str]:
        site = site_of(p)
        if site:
            return self.bridge.guard, site
        return Guard(self.cfg.paths.state_dir / "guard.json", self.cfg.guard), p.name

    async def _omniroute_up(self) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(self.cfg.base_url.rsplit("/v1", 1)[0] + "/api/health", timeout=3)
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _remember(self, answer: dict[str, Any]) -> None:
        name = answer["target"]
        if answer["ok"]:
            self.recent.pop(name, None)
        elif answer.get("code") in RECENT_STATE:
            self.recent[name] = (RECENT_STATE[answer["code"]], answer.get("error", ""), time.time())

    # ------------------------------------------------------------------ page

    async def to_app(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/app/")

    async def static(self, request: web.Request) -> web.StreamResponse:
        rel = request.match_info["path"]
        if rel in ("", "index.html"):
            index = self.app_dir / "index.html"
            if not index.exists():
                return web.Response(status=503, content_type="text/html", text=(
                    "<h1>La app de webllm no está instalada</h1><p>Haz doble clic en ACTUALIZAR.</p>"))
            html = index.read_text(encoding="utf-8").replace("__WEBLLM_TOKEN__", self.bridge.token)
            return web.Response(text=html, content_type="text/html", headers={
                "Cache-Control": "no-store", "X-Frame-Options": "DENY", "Content-Security-Policy": CSP,
                "Referrer-Policy": "no-referrer"})
        root = self.app_dir.resolve()
        path = (root / rel).resolve()
        if root not in path.parents or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"
                                               if "assets" in path.parts else "no-cache",
                                               "X-Content-Type-Options": "nosniff"})

    # ------------------------------------------------------------------ status

    async def estado(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        chrome = self.bridge.connected.is_set()
        omni, cfg = await asyncio.gather(self._omniroute_up(), self._cfg())
        now = time.time()
        ais = []
        for p in cfg.enabled_providers:
            guard, key = self._guard_for(p)
            st = guard.status().get(key, {})
            site = site_of(p)
            server = self.local.status_of(p.model.split("/", 1)[0]) if p.gateway == "local" else None
            state, detail, until = "lista", "", None
            recent = self.recent.get(p.name)
            if recent and now - recent[2] > RECENT_S:
                recent = None
            if (st.get("cooldown_until") or 0) > now:
                state, detail, until = "en_pausa", st.get("cooldown_reason", ""), st["cooldown_until"]
            elif site and not chrome:
                state = "sin_chrome"
            elif p.gateway == "omniroute" and not omni:
                state = "apagada"
            elif server is not None and not server.up:
                state = "apagada"
            elif recent:
                state, detail = recent[0], recent[1]
            today = time.strftime("%Y-%m-%d")
            ais.append({
                "name": p.name, "label": p.display, "kind": "chat" if site else "local" if server else "api",
                "state": state, "detail": detail, "until": until,
                "url": p.url or SITE_URLS.get(site or ""), "today": st.get("count_today", 0) if st.get("day") == today else 0,
                "cap": cfg.guard.daily_cap if (site or p.guarded) else None,
                "server": server.server.key if server else None,
                "server_name": server.server.name if server else None,
                "custom": p.custom,
                "icon": bool(site and self._icon_path(site)),
                # "challenge" / "popup": its chat is waiting for Iván right now (the question goes on after)
                "waiting": self.bridge.waiting.get(site) if site else None,
            })
        local = [{"key": st.server.key, "name": st.server.name, "up": st.up, "installed": st.installed,
                  "models": len(st.models)}
                 for st in self.local._statuses if st.up or st.installed or st.models]
        return web.json_response({"chrome": chrome, "omniroute": omni, "extension_path": str(PROJECT_ROOT / "extension"),
                                  "ais": ais, "local_servers": local})

    # ------------------------------------------------------------------- ask

    async def preguntar(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return self._unauthorized()
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._fail(400, "La petición no es válida.", "bad_request")
        prompt = str(body.get("prompt") or "").strip()
        names = [str(n) for n in (body.get("to") or [])]
        title = str(body.get("title") or "Pregunta")[:120]
        if not prompt:
            return self._fail(400, "Escribe una pregunta.", "empty")
        if len(prompt) > MAX_PROMPT:
            return self._fail(400, "La pregunta es demasiado larga.", "too_long")
        if not names:
            return self._fail(400, "Elige al menos una IA.", "no_target")
        cfg = await self._cfg()
        unknown = [n for n in names if n not in cfg.providers or not cfg.providers[n].enabled]
        if unknown:
            return self._fail(400, f"No conozco esta IA: {', '.join(unknown)}.", "unknown_target")
        skipped = []
        if any(cfg.providers[n].gateway == "omniroute" for n in names) and not await self._omniroute_up():
            skipped = [n for n in names if cfg.providers[n].gateway == "omniroute"]
            names = [n for n in names if n not in skipped]
            if not names:
                return self._fail(503, "El servicio de las IAs por API (OmniRoute) está apagado.", "unreachable")
        flow = flows.Flow(name=title, template="pregunta", inputs={"pregunta": prompt}, steps=(
            flows.Step(id="respuestas", title="Respuestas", to=tuple(dict.fromkeys(names)), message="{{pregunta}}"),))
        try:
            flows.validate(cfg, flow)
        except flows.FlowError as exc:
            return self._fail(400, str(exc), "invalid")

        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                           "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        closed = False

        async def send(event: dict[str, Any]) -> None:
            nonlocal closed
            if event.get("type") == "target_done":
                self._remember(event)
            if closed:
                return
            try:
                await resp.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
            except (ConnectionResetError, RuntimeError):
                closed = True  # the window closed: keep going so the run is complete and journaled

        async def heartbeat() -> None:
            while not closed:
                await asyncio.sleep(15)
                try:
                    await resp.write(b": ping\n\n")
                except (ConnectionResetError, RuntimeError):
                    return

        beat = asyncio.create_task(heartbeat())
        try:
            for n in skipped:
                await send({"type": "target_done", "step": "respuestas", "target": n, "provider": n,
                            "label": cfg.providers[n].display, "provider_label": cfg.providers[n].display,
                            "ok": False, "text": "", "seconds": 0, "code": "unreachable", "notices": [],
                            "error": "El servicio de las IAs por API (OmniRoute) está apagado."})
            try:
                api_key = load_api_key()
            except Exception:
                api_key = ""
            guard = Guard(self.cfg.paths.state_dir / "guard.json", self.cfg.guard)
            try:
                await flows.run_flow(cfg, flow, api_key=api_key, guard=guard, bridge_key=self.bridge.token,
                                     emit=send)
            except GatewayError as exc:
                await send({"type": "error", "code": "unreachable", "error": str(exc)})
        finally:
            beat.cancel()
        if not closed:
            try:
                await resp.write_eof()
            except (ConnectionResetError, RuntimeError):
                pass
        return resp

    # --------------------------------------------------------------- history

    def _run_dir(self, run_id: str) -> Path | None:
        if not RUN_ID.match(run_id):
            return None
        d = self.cfg.paths.runs_dir / run_id
        return d if (d / "journal.jsonl").exists() else None

    def _read_run(self, run_dir: Path) -> dict[str, Any]:
        """One run (a `webllm ask`, an app question or a chain) in one shape."""
        lines = []
        for raw in (run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        known = {p.name: p.display for p in self.local.with_providers(self.cfg).providers.values()}
        label = _Labels(known)

        def read(rel: str | None) -> str:
            if not rel:
                return ""
            f = (run_dir / rel).resolve()
            if run_dir.resolve() not in f.parents or not f.is_file():
                return ""
            return f.read_text(encoding="utf-8")

        def answer(line: dict[str, Any], target: str) -> dict[str, Any]:
            ok = line.get("status") == "ok"
            return {"target": target, "label": label.get(target, target), "provider": line.get("provider", target),
                    "provider_label": label.get(line.get("provider", target), line.get("provider", target)),
                    "ok": ok, "text": read(line.get("response_file")) if ok else "",
                    "seconds": round(float(line.get("latency_s") or 0), 1),
                    "error": "" if ok else (line.get("error") or line.get("status") or ""),
                    "code": "" if ok else line.get("code", "")}

        flow_file = run_dir / "flow.json"
        if flow_file.exists():
            spec = json.loads(flow_file.read_text(encoding="utf-8"))
            steps = []
            for s in spec.get("steps", []):
                calls = [x for x in lines if x.get("kind") == "flow" and x.get("step") == s["id"]]
                answers = []
                for t in s.get("to", []):
                    mine = [x for x in calls if x.get("target") == t]
                    if mine:
                        best = next((x for x in reversed(mine) if x.get("status") == "ok"), mine[-1])
                        answers.append(answer(best, t))
                message = read(calls[0].get("message_file")) if calls else ""
                steps.append({"id": s["id"], "title": s.get("title") or s["id"], "message": message,
                              "answers": answers, "ran": bool(calls)})
            end = next((x for x in reversed(lines) if x.get("kind") == "flow_end"), None)
            inputs = spec.get("inputs") or {}
            kind = "pregunta" if spec.get("template") == "pregunta" else "cadena"
            text = inputs.get("pregunta") or inputs.get("objetivo") or inputs.get("entrada") or (
                steps[0]["message"] if steps else "")
            return {"kind": kind, "title": spec.get("name") or "Cadena", "template": spec.get("template", ""),
                    "text": text, "steps": steps, "status": end.get("status") if end else "unfinished",
                    "ts": lines[0].get("ts") if lines else None}
        prompt = read("prompt.txt")
        answers = [answer(x, x.get("provider", "?")) for x in lines if "provider" in x]
        good = sum(a["ok"] for a in answers)
        return {"kind": "pregunta", "title": "Pregunta", "template": "ask", "text": prompt,
                "steps": [{"id": "respuestas", "title": "Respuestas", "message": prompt, "answers": answers,
                           "ran": True}],
                "status": "ok" if answers and good == len(answers) else "partial" if good else "stopped",
                "ts": lines[0].get("ts") if lines else None}

    async def historial(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        q = request.query.get("q", "").strip().lower()
        try:
            limit = max(1, min(int(request.query.get("limite", "200")), 500))
        except ValueError:
            limit = 200
        runs_dir = self.cfg.paths.runs_dir
        dirs = sorted((d for d in runs_dir.iterdir() if RUN_ID.match(d.name) and (d / "journal.jsonl").exists()),
                      reverse=True) if runs_dir.exists() else []
        items = []
        for d in dirs[:1000]:
            try:
                run = self._read_run(d)
            except (OSError, ValueError, KeyError):
                continue
            if q:
                hay = " ".join([run["title"], run["text"], *(a["text"] for s in run["steps"] for a in s["answers"])])
                if q not in hay.lower():
                    continue
            ais: dict[str, dict[str, Any]] = {}
            for s in run["steps"]:
                for a in s["answers"]:
                    prev = ais.get(a["target"])
                    ais[a["target"]] = {"name": a["target"], "label": a["label"],
                                        "ok": a["ok"] and (prev is None or prev["ok"])}
            items.append({"id": d.name, "ts": run["ts"], "kind": run["kind"], "title": run["title"],
                          "text": run["text"][:280], "status": run["status"], "ais": list(ais.values()),
                          "lock": verify_run(d).ok})
            if len(items) >= limit:
                break
        return web.json_response({"runs": items})

    async def detalle(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        d = self._run_dir(request.match_info["run_id"])
        if d is None:
            return self._fail(404, "No encuentro ese registro.", "not_found")
        run = self._read_run(d)
        check = verify_run(d)
        return web.json_response({"id": d.name, **run, "lock": check.ok, "lock_reason": check.reason,
                                  "folder": str(d)})

    async def exportar(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        d = self._run_dir(request.match_info["run_id"])
        if d is None:
            return self._fail(404, "No encuentro ese registro.", "not_found")
        run = self._read_run(d)
        lock = verify_run(d).ok
        out = [f"# {run['title']}", "",
               f"Registro `{d.name}` · {run['ts'] or ''} · Candado: {'verde (nadie lo ha tocado)' if lock else 'ROJO (no cuadra)'}",
               ""]
        for s in run["steps"]:
            out += [f"## {s['title']}", "", "**Mensaje enviado:**", "", s["message"].rstrip(), ""]
            for a in s["answers"]:
                who = a["provider_label"] + (f" (en lugar de {a['label']})" if a["provider"] != a["target"] else "")
                out += [f"### {who} · {a['seconds']} s", ""]
                out += [a["text"].rstrip() if a["ok"] else f"_No respondió: {a['error']}_", ""]
        return web.Response(text="\n".join(out), content_type="text/markdown", charset="utf-8", headers={
            "Content-Disposition": f'attachment; filename="webllm-{d.name}.md"', "Cache-Control": "no-store"})

    # ----------------------------------------------------------------- fixes

    async def reanudar(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        name = str((await request.json()).get("ia", ""))
        p = self.cfg.providers.get(name)
        if p is None:
            return self._fail(404, f"No conozco esta IA: {name}.", "unknown_target")
        guard, key = self._guard_for(p)
        cleared = guard.clear(key)
        self.recent.pop(name, None)
        return web.json_response({"ok": True, "cleared": cleared})

    async def _chat_site(self, request: web.Request) -> tuple[str, str | None]:
        name = str((await request.json()).get("ia", ""))
        p = self.cfg.providers.get(name)
        return name, site_of(p) if p else None

    async def _session(self, name: str, site: str) -> str:
        """Open the chat in the webllm window (an open tab is reused, never reloaded) and read its state."""
        if not await self.bridge._ensure_extension():
            return "sin_chrome"
        res = await self.bridge._send_to_extension({"type": "diagnose", **self.bridge.site_payload(site)}, 90)
        try:
            state = json.loads(res.get("text") or "{}").get("state") or {}
        except (ValueError, AttributeError):
            state = {}
        if not res.get("ok") or not state:
            session = "desconocido"
        elif state.get("challenge"):
            session = "verificacion"
        elif state.get("loginWall") or not state.get("input"):
            session = "sin_sesion"
        else:
            session = "lista"
        if session == "lista":
            self.recent.pop(name, None)
        elif session == "sin_sesion":
            self.recent[name] = ("sin_sesion", "", time.time())
        return session

    async def comprobar(self, request: web.Request) -> web.Response:
        """Read whether a chat has a session (sends nothing). The app polls this while Iván logs in."""
        if not self._authorized(request):
            return self._unauthorized()
        name, site = await self._chat_site(request)
        if site is None:
            return self._fail(404, f"«{name}» no es un chat de Chrome.", "unknown_target")
        return web.json_response({"session": await self._session(name, site)})

    async def conectar(self, request: web.Request) -> web.Response:
        """Open the chat in the webllm window; if there is no session, bring that window to the front.

        Bringing a window forward is allowed here because Iván has to type his login in it
        (same rule as a verification). ``shown`` is False when the extension could not do it
        (for example an extension older than 0.4.0).
        """
        if not self._authorized(request):
            return self._unauthorized()
        name, site = await self._chat_site(request)
        if site is None:
            return self._fail(404, f"«{name}» no es un chat de Chrome.", "unknown_target")
        session = await self._session(name, site)
        shown = False
        if session in ("sin_sesion", "verificacion", "desconocido"):
            res = await self.bridge._send_to_extension({"type": "show", **self.bridge.site_payload(site)}, self.show_wait_s)
            shown = bool(res.get("ok"))
        return web.json_response({"session": session, "shown": shown})

    async def encender_omniroute(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        if await self._omniroute_up():
            return web.json_response({"ok": True, "already": True})
        if self.omniroute_launcher is None:
            return self._fail(501, "No sé encender OmniRoute en este ordenador.", "unsupported")
        if time.monotonic() - self._last_omni_start > 60:
            self._last_omni_start = time.monotonic()
            try:
                await asyncio.get_running_loop().run_in_executor(None, self.omniroute_launcher)
            except OSError as exc:
                return self._fail(500, f"No pude encender OmniRoute: {exc}", "launch_failed")
        return web.json_response({"ok": True, "already": False})


    # ------------------------------------------------------------- add a site

    def _icon_path(self, key: str) -> Path | None:
        folder = self.cfg.paths.state_dir / "icons"
        for ext in ("png", "ico", "svg", "jpg", "webp", "gif"):
            f = folder / f"{key}.{ext}"
            if f.is_file():
                return f
        return None

    async def anadir(self, request: web.Request) -> web.Response:
        """Start adding a chat site: check the address, then the extension asks permission and tests it."""
        if not self._authorized(request):
            return self._unauthorized()
        try:
            url, host = parse_chat_url(str((await request.json()).get("url", "")))
        except ValueError as exc:
            code = str(exc)
            return self._fail(400, ADD_ERRORS.get(code, ADD_ERRORS["bad_url"]), code)
        names = self.bridge.site_names()
        for key, known in SITE_URLS.items():  # the built-in chats, configured or not
            if urlsplit(known).hostname == host:
                return self._fail(409, f"{names.get(key, key)} ya viene con webllm: no hace falta añadirla.", "duplicate")
        for p in self.cfg.providers.values():
            if p.url and (urlsplit(p.url).hostname or "").lower() == host:
                return self._fail(409, f"Ya tienes esta IA: {p.display}.", "duplicate")
        taken = {site_of(p) or p.name for p in self.cfg.providers.values()} | set(self.bridge.site_names())
        key = site_key(host, taken)
        if is_blocked_model(self.cfg, f"browser/{key}"):
            return self._fail(400, ADD_ERRORS["blocked"], "blocked")
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm y vuelve a probar.", "sin_chrome")
        add_id = secrets.token_hex(6)
        name = site_name(key)
        self.adding[add_id] = {"add_id": add_id, "key": key, "name": name, "url": url, "status": "running",
                               "steps": [{"step": "permission", "ok": None,
                                          "text": "Esperando tu permiso en Chrome…"}],
                               "error": "", "message": "", "detail": ""}
        res = await self.bridge._send_to_extension(
            {"type": "add_site", "add_id": add_id, "key": key, "name": name, "url": url}, 15)
        if not res.get("ok"):
            old_extension = res.get("error") == "timeout"
            self._add_failed(add_id, "old_extension" if old_extension else str(res.get("error") or "extension_error"),
                             str(res.get("detail") or ""))
        return web.json_response(self.adding[add_id])

    def _add_failed(self, add_id: str, code: str, detail: str = "", fallback: str = "") -> None:
        st = self.adding[add_id]
        messages = {
            "permission_denied": "No diste permiso en Chrome, así que webllm no puede usar esta web.",
            "cancelled": "Cancelado. No se ha añadido nada.",
            "login_required": f"{st['name']} te pide entrar con tu cuenta. Entra en la ventanita de webllm que se ha abierto y pulsa «Probar otra vez».",
            "challenge": f"{st['name']} pide una verificación. Resuélvela tú en la ventanita de webllm y pulsa «Probar otra vez».",
            "no_input": "No encontré la caja de texto de esta web, así que todavía no se deja manejar.",
            "insert_failed": "Encontré la caja de texto, pero no pude escribir en ella.",
            "not_sent": "Escribí la prueba, pero el mensaje no salió (quizá una ventana emergente lo tapó).",
            "timeout": "La web no terminó de contestar a la prueba en 2 minutos.",
            "empty_answer": "La web contestó, pero no supe leer la respuesta.",
            "unexpected_answer": "La web contestó, pero no lo que le pedí, así que no me fío de cómo la leo.",
            "site_busy": f"{st['name']} está saturada ahora mismo. Prueba en un rato.",
            "rate_limited": f"{st['name']} dice que has llegado a su límite de mensajes.",
            "old_extension": "La extensión de Chrome es antigua: en chrome://extensions pulsa la flecha ↻ de «webllm puente» y vuelve a probar.",
        }
        st.update(status="failed", error=code, detail=detail[:6000],
                  message=messages.get(code) or fallback or "Algo falló al probar la web.")

    @staticmethod
    def _set_step(st: dict[str, Any], step: str, ok: bool | None, text: str) -> None:
        st["steps"] = [*(x for x in st["steps"] if x["step"] != step), {"step": step, "ok": ok, "text": text}]

    def on_add_event(self, data: dict[str, Any]) -> None:
        """Progress from the extension while it checks a site: permission, page, text box.
        Then ("add_ready") the test message goes like any other one, through the account guard."""
        st = self.adding.get(str(data.get("add_id")))
        if st is None or st["status"] != "running":
            return
        if data.get("type") == "add_progress":
            self._set_step(st, str(data.get("step")), data.get("ok"), str(data.get("text") or ""))
        elif data.get("type") == "add_ready":
            task = asyncio.create_task(self._send_test(st, data.get("icon")))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif not data.get("ok"):  # add_done: the extension stopped before the test message
            self._add_failed(st["add_id"], str(data.get("error") or "extension_error"), str(data.get("detail") or ""))

    async def _send_test(self, st: dict[str, Any], icon: Any) -> None:
        """Send "pong" once, guarded like every message to a chat, and save the site if it answers."""
        self._set_step(st, "send", None, "Enviando una prueba…")
        res = await self.bridge.send_job(st["key"], st["name"], ADD_TEST_PROMPT, timeout_s=120,
                                         site_config={"name": st["name"], "url": st["url"]})
        if st["status"] != "running":
            return
        if not res.get("ok"):
            self._add_failed(st["add_id"], res["error"], res.get("detail", ""), res.get("message", ""))
            return
        text = str(res.get("text") or "")
        self._set_step(st, "send", True, "Prueba enviada y contestada")
        self._set_step(st, "read", True, "Respuesta leída con el botón «copiar» de la web" if res.get("via") == "copy-button"
                       else "Respuesta leída del texto de la página (esta web no tiene botón «copiar»)")
        if not re.search(r"pong", text, re.IGNORECASE):
            self._add_failed(st["add_id"], "unexpected_answer", text[:300])
            return
        save_custom_ai(self.cfg.paths, st["key"], st["name"], st["url"])
        self._save_icon(st["key"], icon)
        self.bridge.cfg = dataclasses.replace(
            self.cfg, providers={**self.cfg.providers, st["key"]: custom_provider(st["key"], st["name"], st["url"])})
        st.update(status="ok", via=str(res.get("via") or ""),
                  message=f"¡Listo! {st['name']} ya está entre tus IAs. Puedes preguntarle desde Preguntar.")

    def _save_icon(self, key: str, data_url: Any) -> None:
        m = re.match(r"^data:image/(png|x-icon|vnd\.microsoft\.icon|svg\+xml|jpeg|webp|gif);base64,([A-Za-z0-9+/=]+)$",
                     str(data_url or ""))
        if not m:
            return
        ext = {"x-icon": "ico", "vnd.microsoft.icon": "ico", "svg+xml": "svg", "jpeg": "jpg"}.get(m.group(1), m.group(1))
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except ValueError:
            return
        if len(raw) > 60000:
            return
        folder = self.cfg.paths.state_dir / "icons"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{key}.{ext}").write_bytes(raw)

    async def anadir_estado(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        st = self.adding.get(request.match_info["add_id"])
        if st is None:
            return self._fail(404, "No encuentro esa prueba.", "not_found")
        return web.json_response(st)

    async def quitar(self, request: web.Request) -> web.Response:
        """Remove a chat site added from the app (the built-in ones stay)."""
        if not self._authorized(request):
            return self._unauthorized()
        name = str((await request.json()).get("ia", ""))
        p = self.cfg.providers.get(name)
        if p is None or not p.custom:
            return self._fail(400, "Solo se pueden quitar las IAs que añadiste tú.", "not_custom")
        remove_custom_ai(self.cfg.paths, name)
        icon = self._icon_path(name)
        if icon:
            icon.unlink(missing_ok=True)
        self.bridge.cfg = dataclasses.replace(
            self.cfg, providers={k: v for k, v in self.cfg.providers.items() if k != name})
        self.recent.pop(name, None)
        return web.json_response({"ok": True})

    async def icono(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return self._unauthorized()
        key = request.match_info["key"]
        f = self._icon_path(key) if re.fullmatch(r"[a-z0-9-]{1,40}", key) else None
        if f is None:
            raise web.HTTPNotFound()
        types = {".svg": "image/svg+xml", ".ico": "image/x-icon", ".jpg": "image/jpeg"}
        return web.FileResponse(f, headers={"Content-Type": types.get(f.suffix, f"image/{f.suffix[1:]}"),
                                            "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff",
                                            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

    async def encender_local(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        key = str((await request.json()).get("server", ""))
        await self.local.refresh(self.cfg, force=True)
        st = self.local.status_of(key)
        if st is not None and st.up:
            return web.json_response({"ok": True, "already": True})
        result = self.local.start(self.cfg, key)
        if result == "not_installed":
            name = st.server.name if st else key
            return self._fail(404, f"No encuentro {name} instalado en este PC.", "not_installed")
        return web.json_response({"ok": True, "already": False})


# ------------------------------------------------------------------ add a chat site

BLOCKED_HOSTS = ("claude.ai", "anthropic.com", "chatgpt.com", "chat.openai.com", "openai.com")  # = extension/common.js
ADD_TEST_PROMPT = "Responde solo con la palabra: pong"
ADD_ERRORS = {
    "bad_url": "Eso no parece una dirección de internet. Cópiala de la barra de Chrome, por ejemplo https://chat.mistral.ai",
    "not_https": "La dirección tiene que empezar por https://",
    "blocked": "Claude y ChatGPT no se usan con webllm, así que esta dirección no se puede añadir.",
}


def parse_chat_url(text: str) -> tuple[str, str]:
    """(normalised url, host) or ValueError with a code of ADD_ERRORS. Same rules as extension/common.js."""
    try:
        u = urlsplit(str(text or "").strip())
    except ValueError as exc:
        raise ValueError("bad_url") from exc
    if not u.scheme or not u.hostname:
        raise ValueError("bad_url")
    if u.scheme.lower() != "https":
        raise ValueError("not_https")
    host = u.hostname.lower()
    if any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS):
        raise ValueError("blocked")
    path = re.sub(r"/+$", "/", u.path or "/")
    origin = f"https://{host}" + (f":{u.port}" if u.port else "")
    return origin + path, host


def site_key(host: str, taken: set[str]) -> str:
    """chat.mistral.ai -> "mistral" (same as extension/common.js)."""
    parts = re.sub(r"^(chat|www|app|web)\.", "", host).split(".")
    base = re.sub(r"[^a-z0-9]", "", parts[-2] if len(parts) > 1 else parts[0]) or "web"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def site_name(key: str) -> str:
    base = re.sub(r"-\d+$", "", key)
    return base[:1].upper() + base[1:]


class _Labels(dict):
    """Provider name -> human name; local AIs no longer listed still read well."""

    def get(self, key, default=None):  # type: ignore[override]
        if key in self:
            return self[key]
        return label_for(key) if isinstance(key, str) and ":" in key else default


__all__ = ["AppApi", "APP_DIR", "SITE_URLS", "site_of"]

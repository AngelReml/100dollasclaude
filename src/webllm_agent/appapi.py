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
    GET  /api/catalogo     every web chat webllm knows (catalog.yaml) with what Iván did with it (PLAN-v5 F3)
    POST /api/conectar-varias   connect several: one Chrome permission, then one by one (log in, "pong")
    GET  /api/conectar-varias/<id>, POST /api/conectar-varias/<id>/parar
    GET  /api/ficha/<ai>   what a chat can do (PLAN-v5 F4): models (strongest first), modes, "+" menu, files
    POST /api/descubrir    read it on the chat's page (menus opened, read and closed; nothing pressed or sent)
    POST /api/ficha/<ai>/potente   Iván says which model is the strongest
    POST /api/ensename     "Enséñame dónde está": Iván clicks the thing in the chat's page
    POST /api/ficha/<ai>/olvidar   forget what he showed (back to the site's own and generic rules)

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

from . import catalog as catalog_mod
from . import fichas
from . import flows
from . import repair
from . import vault
from .broadcaster import GatewayError, verify_run
from .budget import budget_for
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
# What each part of a site's patch is, in Iván's words (PLAN-v5 F6).
PATCH_WHAT = {"input": "la caja de texto", "send": "el botón de enviar", "stop": "el botón de parar", "copy": "el botón de copiar",
              "answer": "la respuesta", "modelButton": "el selector de modelos", "plusButton": "el botón «+»",
              "fileInput": "la subida de archivos"}
RECENT_S = 15 * 60
MAX_PROMPT = 100_000
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
# Codes (flows.error_code) that say something about the AI right now, for the traffic light.
RECENT_STATE = {
    "login_required": "sin_sesion",
    "site_busy": "saturada", "overloaded": "saturada", "rate_limited": "saturada", "no_credit": "saturada",
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
        self.asking: dict[str, asyncio.Event] = {}  # run_id -> its "parar" (questions from this app in progress)
        self.catalog = catalog_mod.load()  # the web chats webllm knows (catalog.yaml, in git)
        self.batches: dict[str, dict[str, Any]] = {}  # batch_id -> "Conectar varias" in progress / done
        self.login_wait_s = 180.0  # how long a site waits for Iván to log in during "Conectar varias"
        self.ack_wait_s = 15.0  # an extension that never acknowledges a message is too old for it
        self._last_omni_start = -1e9
        self._memory_retry = -1e9  # when the app last asked the memory to write again what it missed
        self.observing: dict[int, dict[str, Any]] = {}  # Chrome tab -> the conversation Iván goes on with there
        self.tab_conversation: dict[tuple[int, str], str] = {}  # (tab, site) -> the run its hand-written turns follow
        self.checking: asyncio.Task | None = None  # the daily check in progress
        self._daily: asyncio.Task | None = None
        self.daily_every_s = 24 * 3600.0

    @property
    def cfg(self):
        return self.bridge.cfg

    def stop_all(self) -> tuple[int, set[str]]:
        """"Parar todo" for this app's questions: each one's calls end as "cancelled", nothing more is sent,
        and a chat's job in Chrome that belongs to it is told to stop. (questions stopped, chat sites stopped)"""
        sites: set[str] = set()
        for run_id, stop in list(self.asking.items()):
            stop.set()
            self.bridge.stop(run_id)
            sites.update(site for site in list(self.bridge.jobs) if self.bridge.cancel(site, tag=run_id))
        return len(self.asking), sites

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
        app.router.add_get("/api/catalogo", self.catalogo)
        app.router.add_post("/api/conectar-varias", self.conectar_varias)
        app.router.add_get("/api/conectar-varias/{batch_id}", self.conectar_varias_estado)
        app.router.add_post("/api/conectar-varias/{batch_id}/parar", self.conectar_varias_parar)
        app.router.add_get("/api/ficha/{ai}", self.ficha)
        app.router.add_post("/api/descubrir", self.descubrir)
        app.router.add_post("/api/ficha/{ai}/potente", self.ficha_potente)
        app.router.add_post("/api/ensename", self.ensename)
        app.router.add_post("/api/ficha/{ai}/olvidar", self.ficha_olvidar)
        app.router.add_get("/api/memoria", self.memoria)
        app.router.add_post("/api/memoria", self.guardar_memoria)
        app.router.add_post("/api/memoria/reescribir", self.reescribir_memoria)
        app.router.add_post("/api/memoria/anteriores", self.memoria_anteriores)
        # PLAN-v5 F6: webs that repair themselves, the daily check, and going on by hand in the web
        app.router.add_get("/api/revision", self.revision)
        app.router.add_post("/api/revisar", self.revisar)
        app.router.add_get("/api/reparar", self.reparar_estado)
        app.router.add_post("/api/reparar", self.reparar_guardar)
        app.router.add_get("/api/comite", self.comite_estado)
        app.router.add_post("/api/comite", self.comite_guardar)
        app.router.add_post("/api/ficha/{ai}/deshacer", self.ficha_deshacer)
        app.router.add_post("/api/continuar", self.continuar)
        app.router.add_post("/api/dejar-de-registrar", self.dejar_de_registrar)
        app.on_startup.append(self._start_daily)
        app.on_cleanup.append(self._stop_daily)

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

    def usage(self, cfg, p: ProviderConfig) -> tuple[int, int | None]:
        """(messages today, the day's cap): the account guard for a chat site, the API budget (budget.py) for
        the rest; one source for the app and for Open WebUI."""
        if site_of(p) or p.guarded:
            guard, key = self._guard_for(p)
            st = guard.status().get(key, {})
            cap = p.daily_cap if p.daily_cap is not None else cfg.guard.daily_cap
            return (st.get("count_today", 0) if st.get("day") == time.strftime("%Y-%m-%d") else 0), cap
        budget = budget_for(cfg)
        return budget.used(p.name), budget.cap(p)

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
            today, cap = self.usage(cfg, p)
            ais.append({
                "name": p.name, "label": p.display, "kind": "chat" if site else "local" if server else "api",
                "state": state, "detail": detail, "until": until,
                "url": p.url or SITE_URLS.get(site or ""), "today": today, "cap": cap, "catalog": p.catalog,
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
                                  "ais": ais, "local_servers": local,
                                  # PLAN-v5 F6: the chats Iván is going on with by hand, recorded
                                  "observing": list(self.observing.values())})

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
            run_id = flows.new_run_id()
            self.asking[run_id] = asyncio.Event()
            try:
                await flows.run_flow(cfg, flow, api_key=api_key, guard=guard, bridge_key=self.bridge.token,
                                     emit=send, run_id=run_id, stop=self.asking[run_id])
            except GatewayError as exc:
                await send({"type": "error", "code": "unreachable", "error": str(exc)})
            finally:
                self.asking.pop(run_id, None)
                self.bridge.stopped.discard(run_id)
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
                    "code": "" if ok else line.get("code", ""),
                    # PLAN-v5 F6: "Continuar en la web" needs its address; a turn Iván wrote himself says so
                    "url": line.get("url") or "", "by_ivan": line.get("by") == "ivan",
                    "role": str(line.get("role") or ""),  # PLAN-v5 F7: its role in a Committee
                    "repaired": bool(line.get("repaired"))}

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
                if spec.get("template") == "comite" and s["id"] == "rol" and calls:
                    message = ("Cada IA recibió su propio rol (lo pone encima de su respuesta) y contestó «CONFIRMO: <rol>». "
                               "El texto completo de cada rol está en el registro de su llamada.")
                steps.append({"id": s["id"], "title": s.get("title") or s["id"], "message": message,
                              "answers": answers, "ran": bool(calls)})
            end = next((x for x in reversed(lines) if x.get("kind") == "flow_end"), None)
            inputs = spec.get("inputs") or {}
            template = spec.get("template")
            kind = {"pregunta": "pregunta", "observado": "web", "comite": "comite"}.get(str(template), "cadena")
            text = inputs.get("pregunta") or inputs.get("objetivo") or inputs.get("entrada") or (
                steps[0]["message"] if steps else "")
            title = spec.get("name") or "Cadena"
            if kind == "web":  # a turn Iván wrote himself in a chat's page (PLAN-v5 F6)
                who = next((a["provider_label"] for s in steps for a in s["answers"]), "")
                title = f"En la web de {who}" if who else "En la web"
            return {"kind": kind, "title": title, "template": spec.get("template", ""),
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
        listed = self.catalog.by_host(host)  # an address from webllm's list: it is connected as that one
        for p in self.cfg.providers.values():
            if p.url and (urlsplit(p.url).hostname or "").lower() == host:
                return self._fail(409, f"Ya tienes esta IA: {p.display}.", "duplicate")
        taken = {site_of(p) or p.name for p in self.cfg.providers.values()} | set(self.bridge.site_names())
        key, name = (listed.key, listed.name) if listed else (site_key(host, taken), "")
        url = listed.url if listed else url
        if is_blocked_model(self.cfg, f"browser/{key}"):
            return self._fail(400, ADD_ERRORS["blocked"], "blocked")
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm y vuelve a probar.", "sin_chrome")
        add_id = secrets.token_hex(6)
        name = name or site_name(key)
        self.adding[add_id] = {"add_id": add_id, "key": key, "name": name, "url": url, "status": "running",
                               "catalog": listed is not None,
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
            "moved": (f"{st['name']} te lleva a otra dirección ({detail[:120]}), y webllm solo tiene permiso para la de "
                      "su lista. Si quieres usarla ya, añádela con «+ Añadir otra IA» pegando esa dirección."),
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
        from_catalog = bool(st.get("catalog"))
        save_custom_ai(self.cfg.paths, st["key"], st["name"], st["url"], catalog=from_catalog)
        self._save_icon(st["key"], icon)
        self.bridge.cfg = dataclasses.replace(self.cfg, providers={
            **self.cfg.providers, st["key"]: custom_provider(st["key"], st["name"], st["url"], catalog=from_catalog)})
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
        if p.catalog:
            catalog_mod.save_state(self.cfg.paths, name, "sin_conectar", reason="quitada",
                                   message="La quitaste de tus IAs. Puedes volver a conectarla cuando quieras.")
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

    # ------------------------------------------------------------------ catalog (PLAN-v5 F3)

    def _catalog_view(self) -> list[dict[str, Any]]:
        """Each web chat of the catalog with what Iván did with it. "conectada" is what really holds now:
        the built-in ones configured, a catalog one in his AIs, or the same address added by hand."""
        states = catalog_mod.load_state(self.cfg.paths)
        enabled = [p for p in self.cfg.providers.values() if p.enabled]
        by_site = {p.model.removeprefix("browser/"): p.name for p in enabled if p.model.startswith("browser/")}
        by_host = {(urlsplit(p.url).hostname or ""): p.name for p in enabled if p.url}
        out = []
        for ai in self.catalog.ais:
            row = ai.public()
            row["daily_cap"] = ai.daily_cap if ai.daily_cap is not None else self.cfg.guard.daily_cap
            # a built-in chat is configured by its site (z.ai's chat is "zai-chat"; "zai" is the API)
            provider = by_site.get(ai.key) if ai.builtin else by_host.get(urlsplit(ai.url).hostname or "")
            st = states.get(ai.key, {})
            state = "conectada" if provider else st.get("state", "sin_conectar")
            if state == "conectada" and not provider:  # its entry in custom_ais.json was removed by hand
                state = "sin_conectar"
            row.update(state=state, provider=provider, when=st.get("when", ""),
                       reason="" if provider else st.get("reason", ""),
                       message="" if provider else st.get("message", ""),
                       diagnosis_saved=bool(st.get("detail")) and not provider)
            out.append(row)
        return out

    async def catalogo(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        running = next((b for b in self.batches.values() if b["status"] in ("permission", "running")), None)
        return web.json_response({"checked": self.catalog.checked, "ais": self._catalog_view(),
                                  "batch": self._batch_view(running) if running else None})

    def _batch_view(self, b: dict[str, Any]) -> dict[str, Any]:
        results = []
        for key in b["keys"]:
            r = dict(b["results"][key])
            st = self.adding.get(r.get("add_id") or "")
            if st is not None:
                r["steps"] = st["steps"]
            results.append(r)
        return {k: v for k, v in b.items() if k not in ("results", "stop", "permission")} | {
            "results": results, "done": sum(r["status"] not in ("pending", "running") for r in results),
            "connected": sum(r["status"] == "ok" for r in results)}

    async def conectar_varias(self, request: web.Request) -> web.Response:
        """Connect several catalog chats: Chrome asks permission ONCE for all of them (Iván's click), then
        the webllm window opens them one by one; one that asks to log in is shown to Iván and waits up to
        3 minutes (he types his password himself); each one gets the "pong" test through the guard."""
        if not self._authorized(request):
            return self._unauthorized()
        try:
            body = await request.json()
            keys = list(dict.fromkeys(str(k) for k in body.get("keys") or []))
            skip = list(dict.fromkeys(str(k) for k in body.get("skip") or []))
        except (ValueError, TypeError, AttributeError):
            return self._fail(400, "La petición no es válida.", "bad_request")
        view = {r["key"]: r for r in self._catalog_view()}
        bad = [k for k in keys + skip if k not in view or view[k]["builtin"] or view[k]["state"] == "conectada"]
        if bad:
            return self._fail(400, f"Estas no se pueden conectar desde aquí: {', '.join(bad)}.", "bad_keys")
        if not keys:
            return self._fail(400, "Marca al menos una IA.", "empty")
        if any(b["status"] in ("permission", "running") for b in self.batches.values()):
            return self._fail(409, "Ya hay una conexión en marcha: espera a que termine o párala.", "busy")
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm y vuelve a probar.", "sin_chrome")
        for k in skip:
            catalog_mod.save_state(self.cfg.paths, k, "no_la_quiero", reason="desmarcada",
                                   message="La desmarcaste en «Conectar varias». Puedes conectarla cuando quieras.")
        batch_id = secrets.token_hex(6)
        b: dict[str, Any] = {
            "batch_id": batch_id, "status": "permission", "keys": keys, "current": None, "error": "",
            "message": "Chrome te pide permiso en la pestaña que se ha abierto: pulsa «Permitir y conectar».",
            "results": {k: {"key": k, "name": view[k]["name"], "status": "pending", "error": "", "message": ""}
                        for k in keys}}
        self.batches[batch_id] = b
        b["permission"] = asyncio.get_running_loop().create_future()
        res = await self.bridge._send_to_extension({"type": "add_many", "batch_id": batch_id, "sites": [
            {"key": k, "name": view[k]["name"], "url": view[k]["url"]} for k in keys]}, self.ack_wait_s)
        if not res.get("ok"):
            old = res.get("error") == "timeout"
            b.update(status="failed", error="old_extension" if old else str(res.get("error") or "extension_error"),
                     message=("La extensión de Chrome es antigua: en chrome://extensions pulsa la flecha ↻ de "
                              "«webllm puente» y vuelve a probar.") if old else "Chrome no pudo abrir la página del permiso.")
            b.pop("permission")
            return web.json_response(self._batch_view(b))
        task = asyncio.create_task(self._run_batch(b))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return web.json_response(self._batch_view(b))

    def on_batch_permission(self, data: dict[str, Any]) -> None:
        b = self.batches.get(str(data.get("batch_id")))
        fut = b.get("permission") if b else None
        if fut is not None and not fut.done():
            fut.set_result(bool(data.get("ok")))

    async def _run_batch(self, b: dict[str, Any]) -> None:
        try:
            granted = await asyncio.wait_for(b["permission"], 600)
        except asyncio.TimeoutError:
            granted = False
        finally:
            b.pop("permission", None)
        if not granted:
            for r in b["results"].values():
                r.update(status="skipped", message="No se probó: no hubo permiso de Chrome.")
            b.update(status="failed", error="permission_denied",
                     message="No diste permiso en Chrome, así que no se ha conectado ninguna. Puedes volver a intentarlo.")
            return
        b.update(status="running", message="")
        for key in b["keys"]:
            r = b["results"][key]
            if b.get("stop"):
                r.update(status="skipped", message="No se probó: paraste «Conectar varias».")
                continue
            entry = self.catalog.get(key)
            add_id = secrets.token_hex(6)
            st = {"add_id": add_id, "key": key, "name": entry.name, "url": entry.url, "status": "running",
                  "catalog": True, "steps": [{"step": "open", "ok": None, "text": "Abriendo la web…"}],
                  "error": "", "message": "", "detail": ""}
            self.adding[add_id] = st
            b["current"] = key
            r.update(status="running", add_id=add_id)
            res = await self.bridge._send_to_extension({"type": "add_check", "add_id": add_id, "key": key,
                                                        "name": entry.name, "url": entry.url,
                                                        "wait_login_s": self.login_wait_s}, self.ack_wait_s)
            if not res.get("ok"):
                self._add_failed(add_id, "old_extension" if res.get("error") == "timeout"
                                 else str(res.get("error") or "extension_error"), str(res.get("detail") or ""))
            limit = time.monotonic() + self.login_wait_s + 300  # log in + the "pong" test (2 min) + margin
            while st["status"] == "running" and time.monotonic() < limit:
                await asyncio.sleep(0.25)
            if st["status"] == "running":
                self._add_failed(add_id, "timeout")
            r.update(self._record_connect(entry, st))
        b["current"] = None
        n = sum(r["status"] == "ok" for r in b["results"].values())
        b.update(status="done", message=(
            f"Listo: {n} de {len(b['keys'])} conectadas. Ya salen en Open WebUI; para que allí reciban archivos y "
            "los interruptores, vuelve a hacer doble clic en herramientas\\poner-en-openwebui.cmd."
            if n else f"No se conectó ninguna de las {len(b['keys'])}. En cada una tienes el motivo."))

    def _record_connect(self, entry: "catalog_mod.CatalogAI", st: dict[str, Any]) -> dict[str, Any]:
        """What one connection attempt leaves in the catalog state, and the line Iván reads."""
        if st["status"] == "ok":
            catalog_mod.save_state(self.cfg.paths, entry.key, "conectada")
            return {"status": "ok", "error": "", "message": "Conectada: contestó a la prueba."}
        code = st["error"]
        if code in ("login_required", "challenge"):
            what = "entrar con tu cuenta" if code == "login_required" else "una verificación"
            mins = max(1, round(self.login_wait_s / 60))
            message = (f"Pedía {what} y no se hizo en {mins} minuto{'' if mins == 1 else 's'}. Queda sin conectar: "
                       "pulsa «Conectar» cuando quieras.")
            catalog_mod.save_state(self.cfg.paths, entry.key, "sin_conectar", reason=code, message=message)
            return {"status": "sin_conectar", "error": code, "message": message}
        if code in ("cancelled", "permission_denied", "old_extension"):
            catalog_mod.save_state(self.cfg.paths, entry.key, "sin_conectar", reason=code, message=st["message"])
            return {"status": "sin_conectar", "error": code, "message": st["message"]}
        catalog_mod.save_state(self.cfg.paths, entry.key, "no_funciona", reason=code, message=st["message"],
                               detail=st.get("detail", ""))  # the page's diagnosis, for self-repair (F6)
        return {"status": "no_funciona", "error": code, "message": st["message"]}

    async def conectar_varias_estado(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        b = self.batches.get(request.match_info["batch_id"])
        if b is None:
            return self._fail(404, "No encuentro esa conexión.", "not_found")
        return web.json_response(self._batch_view(b))

    async def conectar_varias_parar(self, request: web.Request) -> web.Response:
        """Stop "Conectar varias": the one being tried now is let go, the rest are not tried."""
        if not self._authorized(request):
            return self._unauthorized()
        b = self.batches.get(request.match_info["batch_id"])
        if b is None:
            return self._fail(404, "No encuentro esa conexión.", "not_found")
        b["stop"] = True
        fut = b.get("permission")
        if fut is not None and not fut.done():
            fut.set_result(False)
        current = b["results"].get(b.get("current") or "", {})
        st = self.adding.get(current.get("add_id") or "")
        if st is not None and st["status"] == "running":
            if self.bridge.ws is not None and not self.bridge.ws.closed:
                await self.bridge.ws.send_json({"type": "cancel", "id": st["add_id"]})  # the page check
            self.bridge.cancel(st["key"])  # or its "pong" test, if it had got that far
            self._add_failed(st["add_id"], "cancelled")
        return web.json_response(self._batch_view(b))

    # ------------------------------------------------------------------ each chat's card (PLAN-v5 F4)

    def _chat(self, name: str) -> tuple[ProviderConfig, str] | None:
        p = self.cfg.providers.get(name)
        site = site_of(p) if p is not None else None
        if p is None:  # a chat of the catalog that does not work yet: its card, "Enséñame" and repairs (PLAN-v5 F6)
            entry = self.catalog.get(name)
            if entry is not None:
                return custom_provider(entry.key, entry.name, entry.url, catalog=True), entry.key
        return (p, site) if p is not None and site else None

    def _site_msg(self, site: str) -> dict[str, Any]:
        """What the extension needs about a site; one of the catalog not connected yet travels with its address."""
        out = self.bridge.site_payload(site)
        entry = self.catalog.get(site)
        if "site_config" not in out and entry is not None and not any(site_of(p) == site for p in self.cfg.providers.values()):
            out["site_config"] = {"name": entry.name, "url": entry.url}
        return out

    def ficha_view(self, p: ProviderConfig, site: str) -> dict[str, Any]:
        entry = self.catalog.get(site)
        card = fichas.load(self.cfg.paths, site)
        return {
            "ai": p.name, "label": p.display, "site": site, "discovered": bool(card.get("when")), "when": card.get("when"),
            "current_model": card.get("current_model"), "models": fichas.rank(entry, card),
            "strongest": fichas.strongest(entry, card), "strongest_by_ivan": card.get("strongest_by_ivan"),
            "use_page_model": bool(card.get("use_page_model")),
            "modes": card.get("modes") or [], "plus": card.get("plus") or [], "files": card.get("files") or [],
            "found": {"model": bool(card.get("model_button")), "plus": bool(card.get("plus"))},
            "table": {"source": entry.models_source if entry else "", "checked": entry.models_checked if entry else "",
                      "known": [m["match"] for m in (entry.models if entry else ())]},
            "taught": sorted(fichas.load_patch(self.cfg.paths, site)),
            # PLAN-v5 F6: every change to where things are on this site (by Iván or by an AI), dated, undoable
            "arreglos": [{"index": i, "when": h.get("when"), "what": PATCH_WHAT.get(str(h.get("key")), str(h.get("key"))),
                          "by": "tú" if h.get("by") == "ivan" else self._ai_label(str(h.get("by") or "")), "why": h.get("why") or "",
                          "active": bool(h.get("active")), "undone": h.get("undone")}
                         for i, h in enumerate(fichas.patch_history(self.cfg.paths, site))][::-1],
            "revision": self._revision_of(site),
        }

    async def ficha(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        chat = self._chat(request.match_info["ai"])
        if chat is None:
            return self._fail(404, "Solo los chats web tienen ficha.", "not_a_chat")
        return web.json_response(self.ficha_view(*chat))

    async def descubrir(self, request: web.Request) -> web.Response:
        """Read a chat's card on its page. Its menus are opened, read and closed; no option is pressed and
        nothing is sent, so it spends no message (and does not go through the message guard)."""
        if not self._authorized(request):
            return self._unauthorized()
        chat = self._chat(str((await request.json()).get("ia", "")))
        if chat is None:
            return self._fail(404, "Solo los chats web tienen ficha.", "not_a_chat")
        p, site = chat
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm.", "sin_chrome")
        async with self.bridge.locks.setdefault(site, asyncio.Lock()):  # never while a question is being asked
            res = await self.bridge._send_to_extension({"type": "discover", **self._site_msg(site)}, 120)
        if not res.get("ok"):
            code = str(res.get("error") or "extension_error")
            text = {"login_required": f"{p.display} no tiene la sesión abierta: pulsa Conectar y entra.",
                    "challenge": f"{p.display} pide una verificación: resuélvela tú y vuelve a pulsar Descubrir.",
                    "no_input": f"No encontré la caja de texto de {p.display}.",
                    "timeout": "La extensión de Chrome no contestó: si es antigua, pulsa ↻ en «webllm puente»."}.get(
                        code, f"No pude leer la ficha de {p.display}.")
            return self._fail(502, text, code)
        try:
            card = json.loads(str(res.get("text") or "{}"))
        except ValueError:
            return self._fail(502, "La extensión devolvió una ficha rota.", "bad_card")
        fichas.save_discovery(self.cfg.paths, site, card)
        return web.json_response(self.ficha_view(p, site))

    async def ficha_potente(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        chat = self._chat(request.match_info["ai"])
        if chat is None:
            return self._fail(404, "Solo los chats web tienen ficha.", "not_a_chat")
        body = await request.json()
        model = body.get("model")
        try:
            fichas.set_strongest(self.cfg.paths, chat[1], str(model) if model else None, page=bool(body.get("page")))
        except ValueError:
            return self._fail(400, "Ese modelo no está en su ficha: pulsa Descubrir otra vez.", "unknown_model")
        return web.json_response(self.ficha_view(*chat))

    async def ficha_olvidar(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        chat = self._chat(request.match_info["ai"])
        if chat is None:
            return self._fail(404, "Solo los chats web tienen ficha.", "not_a_chat")
        fichas.forget_patch(self.cfg.paths, chat[1])
        return web.json_response(self.ficha_view(*chat))

    async def ensename(self, request: web.Request) -> web.Response:
        """"Enséñame dónde está": the chat comes to the front with a banner, and Iván's next click there
        (which does nothing on the page) tells webllm where that thing is, for good."""
        if not self._authorized(request):
            return self._unauthorized()
        body = await request.json()
        chat = self._chat(str(body.get("ia", "")))
        what = str(body.get("what", ""))
        if chat is None or what not in fichas.TEACHABLE:
            return self._fail(400, "No sé qué enseñar ahí.", "bad_request")
        p, site = chat
        text = {"model": "haz clic en el botón que elige el modelo",
                "plus": "haz clic en el botón «+» (el que abre las opciones y adjuntar)",
                "file": "haz clic en el botón para adjuntar archivos",
                "input": "haz clic en la caja donde se escribe el mensaje",
                "send": "haz clic en el botón de enviar (no se enviará nada)",
                "answer": "haz clic en la última respuesta de la IA"}[what]
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm.", "sin_chrome")
        async with self.bridge.locks.setdefault(site, asyncio.Lock()):
            res = await self.bridge._send_to_extension({"type": "teach", **self._site_msg(site), "what": what,
                                                        "text": text, "wait_ms": 180000}, 200)
        try:
            out = json.loads(str(res.get("text") or "{}"))
        except ValueError:
            out = {}
        if not res.get("ok") or not out.get("selector"):
            return self._fail(408, "No llegó tu clic (esperé 3 minutos). Vuelve a intentarlo.", "no_click")
        if what in ("input", "send", "answer"):  # PLAN-v5 F6: the lesson is tried on the page first, sending nothing
            async with self.bridge.locks.setdefault(site, asyncio.Lock()):
                tried = await self.bridge._send_to_extension({"type": "try_patch", **self._site_msg(site),
                                                              "patch": {fichas.TEACHABLE[what]: [str(out["selector"])]}, "sent": ""}, 60)
            try:
                checks = json.loads(str(tried.get("text") or "{}")) if tried.get("ok") else {}
            except ValueError:
                checks = {}
            if not checks.get("ok"):
                why = {"input": "la caja donde se escribe", "send": "el botón de enviar",
                       "answer": "una respuesta de la IA (si en la ventanita no hay ninguna, pregúntale algo antes)"}[what]
                return self._fail(422, f"Eso no parece {why}. Vuelve a pulsar Enséñame y haz clic justo encima.", "not_that")
        fichas.teach(self.cfg.paths, site, what, str(out["selector"]))
        return web.json_response({"ok": True, "what": what, "name": out.get("name"), **self.ficha_view(p, site)})

    # ---------------------------------------------------------------- memory in Obsidian (PLAN-v5 F5)

    def memoria_view(self) -> dict[str, Any]:
        s = vault.settings(self.cfg.paths)
        last = s.get("last")
        try:
            last = time.strftime("%d/%m/%Y a las %H:%M", time.strptime(str(last), "%Y-%m-%d %H:%M:%S")) if last else None
        except ValueError:
            last = None
        return {"dir": s["dir"], "enabled": s["enabled"], "error": s.get("error"), "last": last,
                "conversations": vault.conversations(self.cfg.paths), "answers": vault.answers(self.cfg.paths)}

    async def memoria(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        view = self.memoria_view()
        if view["enabled"] and view["error"] and time.monotonic() - self._memory_retry > 60:
            self._memory_retry = time.monotonic()  # the app asks every few seconds: try again once a minute
            vault.retry(self.cfg.paths)  # Drive may be back: write what it missed
        return web.json_response(view)

    async def guardar_memoria(self, request: web.Request) -> web.Response:
        """Turn the memory on (in this vault folder) or off. The folder check touches Drive: in a thread, so a
        slow Drive never holds the app up."""
        if not self._authorized(request):
            return self._unauthorized()
        try:
            body = await request.json()
        except ValueError:
            return self._fail(400, "La petición no es JSON.", "bad_request")
        try:
            await asyncio.to_thread(vault.configure, self.cfg.paths, str(body.get("dir") or ""),
                                    bool(body.get("enabled", True)))
        except ValueError as exc:
            return self._fail(400, str(exc), "bad_folder")
        return web.json_response(self.memoria_view())

    async def memoria_anteriores(self, request: web.Request) -> web.Response:
        """"Copiar también lo de antes": the questions webllm recorded before the memory was on."""
        if not self._authorized(request):
            return self._unauthorized()
        if not vault.settings(self.cfg.paths)["enabled"]:
            return self._fail(409, "La memoria está apagada: enciéndela primero.", "memory_off")
        cfg = await self._cfg()
        vault.import_history(self.cfg.paths, labels={p.name: p.display for p in cfg.providers.values()})
        return web.json_response(self.memoria_view())

    async def reescribir_memoria(self, request: web.Request) -> web.Response:
        """"Reescribir todo": everything written again from the journal (what Iván changed by hand in webllm's
        files is lost; the app asks him first)."""
        if not self._authorized(request):
            return self._unauthorized()
        if not vault.settings(self.cfg.paths)["enabled"]:
            return self._fail(409, "La memoria está apagada: enciéndela primero.", "memory_off")
        vault.rewrite_all(self.cfg.paths)
        return web.json_response(self.memoria_view())

    # ---------------------------------------------------------------- the Committee (PLAN-v5 F7)

    async def comite_view(self) -> dict[str, Any]:
        """Iván's settings, and who would take part if he launched it now (nothing is sent to find out)."""
        from . import committee, committee_face
        st = committee.settings(self.cfg.paths)
        cfg = await self._cfg()
        out: dict[str, Any] = {k: st[k] for k in ("number", "roles", "think", "parallel_web")}
        try:
            plan = await committee_face.plan_for(self.bridge, cfg, "vista previa")
        except committee.CommitteeError as exc:
            return {**out, "preview": None, "preview_error": str(exc)}
        seat = lambda s: {"provider": s.provider, "label": s.label, "kind": s.kind, "role": s.role, "model": s.model,  # noqa: E731
                          "modes": s.modes}
        return {**out, "preview": {"seats": [seat(s) for s in plan.seats], "reserves": [seat(s) for s in plan.reserves],
                                   "fusion": [seat(s) for s in plan.fusion], "missing": [list(m) for m in plan.missing]}}

    async def comite_estado(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        return web.json_response(await self.comite_view())

    async def comite_guardar(self, request: web.Request) -> web.Response:
        """How many (3 or 5), "pensar", two web chats at once, and the roles (templates); "reset_roles" = webllm's."""
        from . import committee
        if not self._authorized(request):
            return self._unauthorized()
        body = await request.json()
        changes = {k: body[k] for k in ("number", "think", "parallel_web", "roles", "reset_roles") if k in body}
        for k in ("think", "parallel_web", "reset_roles"):
            if k in changes:
                changes[k] = bool(changes[k])
        try:
            committee.configure(self.cfg.paths, **changes)
        except ValueError as exc:
            return self._fail(400, str(exc), "bad_request")
        return web.json_response(await self.comite_view())

    # ---------------------------------------------------------------- self-repair and daily check (PLAN-v5 F6)

    def _ai_label(self, by: str) -> str:
        name = by.split(":", 1)[1] if by.startswith("ia:") else by
        p = self.cfg.providers.get(name)
        return f"una IA ({p.display if p else name})"

    async def ficha_deshacer(self, request: web.Request) -> web.Response:
        """Undo one repair or lesson of a chat ("Deshacer"): the extension stops using it at once."""
        if not self._authorized(request):
            return self._unauthorized()
        chat = self._chat(request.match_info["ai"])
        if chat is None:
            return self._fail(404, "Solo los chats web tienen ficha.", "not_a_chat")
        try:
            fichas.undo_patch(self.cfg.paths, chat[1], int((await request.json()).get("index", -1)))
        except (ValueError, TypeError):
            return self._fail(400, "Ese arreglo ya estaba deshecho.", "bad_request")
        return web.json_response(self.ficha_view(*chat))

    def reparar_view(self) -> dict[str, Any]:
        st = repair.settings(self.cfg.paths)
        cfg = self.local.with_providers(self.cfg)
        options = repair.helpers(cfg)
        chosen = repair.helper(cfg)
        return {"enabled": st["enabled"], "ai": chosen.name if chosen else None, "ai_label": chosen.display if chosen else None,
                "options": [{"name": o.name, "label": o.display} for o in options],
                "last": [{"when": x.get("when"), "site": x.get("site"), "result": x.get("result"), "why": x.get("why")}
                         for x in repair.history(self.cfg.paths, limit=10)]}

    async def reparar_estado(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        await self._cfg()
        return web.json_response(self.reparar_view())

    async def reparar_guardar(self, request: web.Request) -> web.Response:
        """"Reparar solas con IA": on or off, and which AI looks at the pages' x-rays."""
        if not self._authorized(request):
            return self._unauthorized()
        body = await request.json()
        cfg = await self._cfg()
        ai = str(body.get("ai") or "")
        if ai and ai not in {o.name for o in repair.helpers(cfg)}:
            return self._fail(400, "Esa IA no puede ayudar a reparar (tiene que ser por API o de tu PC, y privada).", "bad_ai")
        repair.configure(self.cfg.paths, bool(body.get("enabled", True)), ai)
        return web.json_response(self.reparar_view())

    def _revision_of(self, site: str) -> dict[str, Any] | None:
        return (self._read_revision().get("sites") or {}).get(site)

    def _read_revision(self) -> dict[str, Any]:
        try:
            data = json.loads((self.cfg.paths.state_dir / "revision.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _check_sites(self) -> list[tuple[ProviderConfig, str]]:
        """The web chats to look at: the ones in use (built in or connected), each once."""
        seen, out = set(), []
        for p in self.cfg.providers.values():
            site = site_of(p)
            if site and site not in seen and (not p.catalog or catalog_mod.load_state(self.cfg.paths).get(site, {}).get("state") == "conectada"):
                seen.add(site)
                out.append((p, site))
        return out

    async def check_all(self) -> dict[str, Any]:
        """The daily check (and "Comprobar ahora"): each web chat opened and looked at, nothing sent. A chat whose
        text box is not found gets a repair (layer 3) on the spot, tried on its page without sending."""
        results: dict[str, Any] = {}
        for p, site in self._check_sites():
            if not self.bridge.connected.is_set():
                break
            async with self.bridge.locks.setdefault(site, asyncio.Lock()):  # never while a question is being asked
                res = await self.bridge._send_to_extension({"type": "check", **self.bridge.site_payload(site)}, 120)
                try:
                    out = json.loads(str(res.get("text") or "{}")) if res.get("ok") else {}
                except ValueError:
                    out = {}
                state = ("bien" if out.get("input") else "sin_sesion" if out.get("login") else "verificacion" if out.get("challenge")
                         else "saturada" if out.get("busy") else "limite" if out.get("limited") else "bloqueada" if out.get("banned")
                         else "no_encuentro_la_caja" if res.get("ok") else "no_se_pudo_abrir")
                fixed = None
                if state == "no_encuentro_la_caja" and out.get("xray"):
                    fixed = await self.bridge._repair(site, p.display, ["input"], out["xray"], "")
                    if fixed:
                        state = "reparada"
            results[site] = {"state": state, "label": p.display, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
                             **({"repaired_by": fixed["ai"]} if fixed else {})}
            self.bridge.log(f"Comprobación diaria: {p.display}: {state}")
        data = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "sites": {**(self._read_revision().get("sites") or {}), **results}}
        (self.cfg.paths.state_dir / "revision.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return data

    def revision_view(self) -> dict[str, Any]:
        data = self._read_revision()
        sites = [{"site": k, **v} for k, v in (data.get("sites") or {}).items()]
        return {"when": data.get("when"), "running": bool(self.checking and not self.checking.done()), "sites": sites,
                "ok": sum(1 for x in sites if x.get("state") in ("bien", "reparada")), "total": len(sites)}

    async def revision(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        return web.json_response(self.revision_view())

    async def revisar(self, request: web.Request) -> web.Response:
        """"Comprobar ahora": the same check as every day, now (in the background; the app polls /api/revision)."""
        if not self._authorized(request):
            return self._unauthorized()
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm.", "sin_chrome")
        if not (self.checking and not self.checking.done()):
            self.checking = asyncio.create_task(self.check_all())
        return web.json_response(self.revision_view())

    async def _start_daily(self, app: web.Application) -> None:
        self._daily = asyncio.create_task(self._daily_loop())

    async def _stop_daily(self, app: web.Application) -> None:
        for t in (self._daily, self.checking):
            if t and not t.done():
                t.cancel()

    async def _daily_loop(self) -> None:
        """Once a day, when Chrome is connected and nothing has been asked for 10 minutes."""
        while True:
            await asyncio.sleep(min(1800.0, self.daily_every_s / 4))
            last = self._read_revision().get("when")
            try:
                age = time.time() - time.mktime(time.strptime(str(last), "%Y-%m-%d %H:%M:%S")) if last else 1e12
            except ValueError:
                age = 1e12
            quiet = not self.bridge.jobs and time.monotonic() - self.bridge.last_job_at > 600
            if age >= self.daily_every_s and quiet and self.bridge.connected.is_set() and not (self.checking and not self.checking.done()):
                self.checking = asyncio.create_task(self.check_all())
                try:
                    await self.checking
                except Exception as exc:  # noqa: BLE001 - logged; tomorrow again
                    self.bridge.log(f"Comprobación diaria: falló ({exc})")

    # ---------------------------------------------------------------- going on by hand in the web (PLAN-v5 F6, D16)

    def _run_head(self, run_id: str) -> tuple[list[dict[str, Any]], Path] | None:
        if not RUN_ID.match(run_id):
            return None
        d = self.cfg.paths.runs_dir / run_id
        try:
            lines = [json.loads(x) for x in (d / "journal.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        except (OSError, ValueError):
            return None
        return lines, d

    async def continuar(self, request: web.Request) -> web.Response:
        """"Continuar en la web": that exact conversation, in a normal tab of Iván's Chrome, recorded as he goes on."""
        if not self._authorized(request):
            return self._unauthorized()
        body = await request.json()
        return await self.continue_run(str(body.get("run_id") or ""), str(body.get("ai") or ""))

    async def continue_run(self, run_id: str, ai: str = "") -> web.Response:
        head = self._run_head(run_id)
        if head is None:
            return self._fail(404, "No encuentro esa pregunta en el historial.", "not_found")
        lines, _ = head
        calls = [x for x in lines if x.get("kind") in ("flow", None) and x.get("url") and (not ai or x.get("provider") == ai)]
        if not calls:
            return self._fail(409, "Esa respuesta no vino de un chat web (o es de antes de F6): no hay conversación que abrir.", "no_url")
        call = calls[-1]
        p = self.cfg.providers.get(str(call.get("provider")))
        site = site_of(p) if p else None
        if not site:
            return self._fail(409, "Esa IA ya no está en webllm.", "no_site")
        if not await self.bridge._ensure_extension():
            return self._fail(503, "Chrome no está conectado: abre Chrome con la extensión webllm.", "sin_chrome")
        res = await self.bridge._send_to_extension({"type": "observe", **self.bridge.site_payload(site), "url": call["url"],
                                                    "follows": run_id}, 60)
        if not res.get("ok"):
            return self._fail(502, f"No pude abrir la conversación de {p.display} ({res.get('error')}).", "no_abre")
        return web.json_response({"ok": True, "label": p.display, "url": call["url"]})

    async def dejar_de_registrar(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._unauthorized()
        tab = (await request.json()).get("tab")
        if self.bridge.ws is not None and not self.bridge.ws.closed:
            await self.bridge.ws.send_json({"type": "observe_stop", **({"tab": int(tab)} if tab else {})})
        return web.json_response({"ok": True})

    def on_observe_state(self, data: dict[str, Any]) -> None:
        tab = int(data.get("tab") or 0)
        if data.get("on"):
            p = self._provider_of_site(str(data.get("site") or ""))
            self.observing[tab] = {"tab": tab, "site": data.get("site"), "label": p.display if p else data.get("site"),
                                   "follows": data.get("follows"), "since": time.strftime("%H:%M")}
        else:
            self.observing.pop(tab, None)

    def _provider_of_site(self, site: str) -> ProviderConfig | None:
        return next((p for p in self.cfg.providers.values() if site_of(p) == site), None)

    async def on_observed(self, data: dict[str, Any]) -> None:
        """A turn Iván wrote himself in the chat's page: recorded in the same conversation (history and vault)."""
        site = str(data.get("site") or "")
        p = self._provider_of_site(site)
        user = str(data.get("user") or "").strip()
        if p is None or not user:
            self.bridge.log(f"Observador: turno sin chat conocido ({site}) o sin mensaje: no se guarda.")
            return
        self.bridge.guard.note(ProviderConfig(name=site, model="browser/" + site, kind="browser"))  # counts, never blocks
        # the conversation this turn belongs to: the question it was continued from, or (a chat Iván opened himself
        # and registered from the extension's icon) the first turn recorded in that tab
        tab = int(data.get("tab") or 0)
        follows = str(data.get("follows") or "") or self.tab_conversation.get((tab, site)) or None
        run_dir = await asyncio.to_thread(flows.record_observed, self.cfg, p, follows=follows, user=user[:MAX_PROMPT],
                                          answer=str(data.get("answer") or ""), url=str(data.get("url") or "")[:500],
                                          via=data.get("via"), error=data.get("error"), seconds=_seconds(data.get("seconds")))
        if tab:  # the next turns in that tab follow the same conversation
            self.tab_conversation[(tab, site)] = follows or run_dir.name
            if tab in self.observing:
                self.observing[tab]["follows"] = self.tab_conversation[(tab, site)]
            if not data.get("follows") and self.bridge.ws is not None and not self.bridge.ws.closed:
                # the extension keeps it too, so a restart of webllm does not split the conversation
                await self.bridge.ws.send_json({"type": "observe_follows", "tab": tab, "follows": self.tab_conversation[(tab, site)]})
        self.bridge.log(f"Observador: {p.display}: turno escrito por Iván guardado ({run_dir.name}).")

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


def _seconds(value: Any) -> float | None:
    """How long a page took to answer a turn Iván wrote himself, as the extension measured it (or None)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if 0 < v < 24 * 3600 else None


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

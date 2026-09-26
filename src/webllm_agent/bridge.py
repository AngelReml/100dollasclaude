"""Local bridge: the AI chats open in your Chrome, served as an OpenAI-style API.

    webllm puente                 run the bridge (127.0.0.1:20130)

The Chrome extension in ``extension/`` connects here over a WebSocket (with a
token) and does the typing/reading in the real chat pages. Clients (aider,
``webllm ask``) call ``POST /v1/chat/completions`` with model ``browser/<site>``.

Account protection lives here, per site: one message at a time, a minimum
spacing, a daily cap, and a pause after a limit, a ban or an unsolved
verification. A missing login is not paused: nothing was sent, and the next
request works as soon as you log in (with the same or a new account).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from aiohttp import WSMsgType, web

from . import vault
from .appapi import AppApi
from .gateway import Gateway, RequestError, decode_files
from .client import _content_text
from .config import JOB_HARD_CAP_S, PROJECT_ROOT, AppConfig, ProviderConfig
from .guard import Guard, GuardBlocked

MODEL_PREFIX = "browser/"
PANEL_HTML = Path(__file__).with_name("panel.html")
SITES = {"qwen": "Qwen", "deepseek": "DeepSeek", "zai": "z.ai", "meta": "Meta AI"}
EXTENSION_DIR = PROJECT_ROOT / "extension"

# extension error code -> (HTTP status, pause hours or None, Spanish message)
# The extension says "still on it" every 10 s; without that for this long, the job is lost.
JOB_ALIVE_GRACE_S = 45.0

ERRORS: dict[str, tuple[int, float | None, str]] = {
    "login_required": (401, None, "no hay sesión abierta en Chrome. Entra en {site} con tu cuenta (o una nueva) y vuelve a pedirlo"),
    "banned": (403, 24 * 30, "la cuenta parece bloqueada. Crea otra, entra con ella en Chrome y haz doble clic en REANUDAR"),
    "rate_limited": (403, -1, "límite de mensajes del chat alcanzado"),
    "challenge": (403, -1, "pidió una verificación humana y nadie la resolvió"),
    "timeout": (504, None, "no terminó de responder a tiempo"),
    "extension_disconnected": (503, None, "Chrome se desconectó a mitad del envío"),
    "site_busy": (503, None, "está saturado ahora mismo (no es un límite de tu cuenta). Prueba en un rato o elige otro modelo en su web"),
    "not_sent": (502, None, "el mensaje se quedó sin enviar (una ventana emergente lo tapó). Vuelve a pedirlo"),
    "cancelled": (409, None, "lo has parado tú"),
    # PLAN-v5 F4 (D21): what Iván chose was not confirmed on the page, so nothing was sent (no pause)
    "not_confirmed": (409, None, "la página no confirmó lo que pediste (modelo o modo), así que no envié nada"),
    "model_not_in_page": (409, None, "ese modelo no está en su selector, así que no envié nada"),
    "mode_not_in_page": (409, None, "ese modo no está en su web, así que no envié nada"),
    "file_not_attached": (409, None, "el archivo no quedó adjunto en su web, así que no envié nada"),
    "forbidden": (409, None, "iba a pulsar un botón prohibido (publicar, compartir, borrar…) y no lo hice; no envié nada"),
    "expensive_cap": (429, None, "ya se han usado hoy los modos caros de este chat (se cuentan aparte)"),
}
# The extension's file errors, all "the file did not get attached" for Iván (the detail says which).
FILE_ERRORS = {"file_not_shown", "no_file_input", "file_type_refused", "file_changed", "file_incomplete"}
EXPENSIVE_MODES = frozenset({"investigar", "constructor"})  # few uses a day on the sites
FILE_PART_BYTES = 512 * 1024


def load_token(state_dir: Path) -> str:
    """Bridge token (created once, stored in data/state/bridge_token)."""
    path = state_dir / "bridge_token"
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    state_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    path.write_text(token, encoding="utf-8")
    return token


def write_extension_config(token: str, port: int, ext_dir: Path = EXTENSION_DIR) -> Path:
    """extension/config.json tells the extension where the bridge is (git-ignored)."""
    path = ext_dir / "config.json"
    data = {"bridge": f"ws://127.0.0.1:{port}/ext", "token": token}
    if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != data:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def flatten_messages(messages: list[dict[str, Any]]) -> str:
    """Turn an OpenAI message list into one prompt a chat box can take."""
    parts = []
    for m in messages or []:
        text = _content_text(m.get("content")) or ""
        if text.strip():
            parts.append((m.get("role", "user"), text))
    if not any(role == "user" for role, _ in parts):
        return ""  # nothing to ask: never send just the closing instruction to a chat
    if len(parts) == 1 and parts[0][0] == "user":
        return parts[0][1]
    labels = {"system": "SYSTEM INSTRUCTIONS", "user": "USER", "assistant": "ASSISTANT (your earlier reply)"}
    out = [f"=== {labels.get(role, role.upper())} ===\n{text}" for role, text in parts]
    out.append("=== END ===\nReply to the last USER message, following the SYSTEM INSTRUCTIONS.")
    return "\n\n".join(out)


def launch_chrome() -> None:
    """Open Chrome normally (your profile, no debugging flags)."""
    subprocess.Popen(["cmd", "/c", "start", "", "chrome"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class Bridge:
    def __init__(
        self,
        cfg: AppConfig,
        token: str,
        *,
        guard: Guard | None = None,
        timeout_s: float = 300.0,
        human_wait_s: float = 240.0,
        connect_wait_s: float = 25.0,
        launcher: Callable[[], None] | None = launch_chrome,
        log: Callable[[str], None] = print,
    ) -> None:
        self.cfg = cfg
        self.token = token
        self.guard = guard or Guard(cfg.paths.state_dir / "bridge_guard.json", cfg.guard)
        self.timeout_s = timeout_s
        self.human_wait_s = human_wait_s
        self.connect_wait_s = connect_wait_s
        self.launcher = launcher
        self.log = log
        self.ws: web.WebSocketResponse | None = None
        self.connected = asyncio.Event()
        self.pending: dict[str, asyncio.Future] = {}
        self.locks: dict[str, asyncio.Lock] = {}  # one message at a time per site
        self.alive: dict[str, float] = {}  # job id -> last time the extension said it is still on it
        self.waiting: dict[str, str] = {}  # site -> "challenge" | "popup" while the chat waits for Iván
        self.jobs: dict[str, tuple[str, str]] = {}  # site -> (job id, question tag) the extension is doing there
        self.stopped: set[str] = set()  # question tags Iván stopped: never sent, even if still waiting their turn
        self._last_launch = -1e9
        self._panel_running = False
        self.app_api = AppApi(self)
        self.gateway = Gateway(self)

    # ------------------------------------------------------------------ app

    @web.middleware
    async def _local_only(self, request: web.Request, handler):
        # Only answer requests addressed to this PC (blocks DNS-rebinding tricks).
        host = request.host.split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            return web.Response(status=403, text="local only")
        return await handler(request)

    def app(self) -> web.Application:
        # Files travel as base64 inside the JSON body (gateway.py): 100 MB of files is ~134 MB of body.
        app = web.Application(client_max_size=160 * 1024 * 1024, middlewares=[self._local_only])
        app.router.add_get("/", self.panel)
        app.router.add_get("/panel/state", self.panel_state)
        app.router.add_get("/panel/run", self.panel_run)
        app.router.add_post("/panel/ask", self.panel_ask)
        app.router.add_get("/health", self.health)
        app.router.add_get("/ext", self.ext_socket)
        app.router.add_get("/v1/models", self.models)
        app.router.add_post("/v1/chat/completions", self.chat_completions)
        app.router.add_get("/status", self.status)
        app.router.add_post("/admin/resume", self.resume)
        app.router.add_post("/admin/diagnose", self.diagnose)
        self.app_api.register(app)
        self.gateway.register(app)
        app.on_shutdown.append(self._flush_vault)
        return app

    @staticmethod
    async def _flush_vault(app: web.Application) -> None:
        """Whatever the memory still has to write reaches the vault before the bridge closes (PLAN-v5 F5)."""
        await asyncio.to_thread(vault.flush, 10)

    def site_names(self) -> dict[str, str]:
        """Chat sites the bridge serves: the built-in ones plus the ones added from the app."""
        out = dict(SITES)
        for p in self.cfg.providers.values():
            if p.custom and p.model.startswith(MODEL_PREFIX):
                out[p.model[len(MODEL_PREFIX):]] = p.display
        return out

    def site_cap(self, site: str) -> int | None:
        """A chat site's own daily cap (its provider, else webllm's catalog: sites with few free messages);
        None = the guard's default."""
        for p in self.cfg.providers.values():
            if p.model == MODEL_PREFIX + site and p.daily_cap is not None:
                return p.daily_cap
        entry = self.app_api.catalog.get(site)
        return entry.daily_cap if entry else None

    def site_payload(self, site: str) -> dict[str, Any]:
        """What the extension needs about a site; an added one travels with its name and address, and
        what Iván showed with "Enséñame dónde está" travels with every site (PLAN-v5 F4)."""
        out: dict[str, Any] = {"site": site}
        for p in self.cfg.providers.values():
            if p.custom and p.model == MODEL_PREFIX + site:
                out["site_config"] = {"name": p.display, "url": p.url}
                break
        patch = self.site_patch(site)
        if patch:
            out["site_patch"] = patch
        return out

    def site_patch(self, site: str) -> dict[str, list[str]]:
        try:
            data = json.loads((self.cfg.paths.state_dir / "patches" / f"{site}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: [str(x) for x in v][:5] for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}

    def _authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization", "") == f"Bearer {self.token}"

    @staticmethod
    def _error(status: int, message: str, code: str) -> web.Response:
        return web.json_response({"error": {"message": message, "type": code, "code": code}}, status=status)

    # ------------------------------------------------------------ extension

    async def ext_socket(self, request: web.Request) -> web.StreamResponse:
        if request.query.get("token") != self.token:
            return web.Response(status=401, text="bad token")
        ws = web.WebSocketResponse(heartbeat=25, max_msg_size=64 * 1024 * 1024)  # files a chat produced come back here
        await ws.prepare(request)
        old, self.ws = self.ws, ws
        if old is not None and not old.closed:
            await old.close()
        self.connected.set()
        self.log("Chrome conectado (extensión webllm).")
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                if data.get("type") == "result":
                    fut = self.pending.pop(data.get("id"), None)
                    if fut is not None and not fut.done():
                        fut.set_result(data)
                elif data.get("type") == "job_alive":
                    if data.get("id") in self.pending:
                        self.alive[data["id"]] = time.monotonic()
                        site = str(data.get("site") or "")
                        if data.get("waiting"):
                            self.waiting[site] = str(data["waiting"])
                        else:
                            self.waiting.pop(site, None)
                elif data.get("type") in ("add_progress", "add_ready", "add_done"):
                    self.app_api.on_add_event(data)
                elif data.get("type") == "add_many_permission":
                    self.app_api.on_batch_permission(data)
                elif data.get("type") == "notice":
                    self.log(f"AVISO {data.get('site')}: {data.get('message')}")
        finally:
            if self.ws is ws:
                self.ws = None
                self.connected.clear()
                self.log("Chrome desconectado.")
                for fut in list(self.pending.values()):
                    if not fut.done():
                        fut.set_result({"ok": False, "error": "extension_disconnected"})
                self.pending.clear()
                self.waiting.clear()
        return ws

    async def _ensure_extension(self) -> bool:
        if self.connected.is_set():
            return True
        # Open Chrome and wait for the extension at most once every 5 minutes;
        # otherwise answer at once instead of making every request wait.
        if time.monotonic() - self._last_launch < 300:
            return False
        self._last_launch = time.monotonic()
        if self.launcher:
            self.log("Chrome no está conectado: lo abro.")
            try:
                self.launcher()
            except OSError as exc:
                self.log(f"No pude abrir Chrome: {exc}")
        try:
            await asyncio.wait_for(self.connected.wait(), self.connect_wait_s)
            return True
        except asyncio.TimeoutError:
            return False

    async def _send_to_extension(self, payload: dict[str, Any], wait_s: float, tag: str = "",
                                 files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Send one message to the extension and wait for its result: at least ``wait_s``, and
        longer while the extension keeps saying it is still on the job (extension 0.5.0+ says so
        every 10 s, e.g. while Iván solves a verification; it enforces the real time limits).
        ``files`` ({name, mime, sha256, bytes}) travel first, in parts, however big."""
        job_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[job_id] = fut
        if payload.get("type") == "job":
            self.jobs[str(payload.get("site"))] = (job_id, tag)
        start = time.monotonic()
        try:
            metas = []
            for i, f in enumerate(files or []):
                key = f"f{i}"
                data = f["bytes"]
                n = max(1, -(-len(data) // FILE_PART_BYTES))
                for k in range(n):
                    part = base64.b64encode(data[k * FILE_PART_BYTES:(k + 1) * FILE_PART_BYTES]).decode("ascii")
                    await self.ws.send_json({"type": "file_part", "job": job_id, "key": key, "n": k, "data": part})
                metas.append({"key": key, "name": f["name"], "type": f["mime"], "sha256": f["sha256"], "parts": n})
            await self.ws.send_json({**payload, "id": job_id, **({"files": metas} if metas else {})})
            while True:
                now = time.monotonic()
                until = start + wait_s
                if job_id in self.alive:
                    until = max(until, self.alive[job_id] + JOB_ALIVE_GRACE_S)
                until = min(until, start + JOB_HARD_CAP_S)
                if now >= until:
                    return {"ok": False, "error": "timeout"}
                try:
                    return await asyncio.wait_for(asyncio.shield(fut), min(until - now, 5.0))
                except asyncio.TimeoutError:
                    continue
        finally:
            self.pending.pop(job_id, None)
            self.alive.pop(job_id, None)
            if payload.get("type") == "job":
                self.waiting.pop(str(payload.get("site")), None)
                if self.jobs.get(str(payload.get("site")), ("",))[0] == job_id:
                    self.jobs.pop(str(payload.get("site")), None)

    def stop(self, tag: str) -> None:
        """Iván stopped this question: if it is still waiting its turn at a chat site, it is never sent."""
        if tag:
            self.stopped.add(tag)

    def cancel(self, site: str, tag: str | None = None) -> bool:
        """Stop the job a chat site is doing ("parar"): it ends as "cancelled" at once, and the extension
        (0.5.2+) stops driving the page; an older one finishes on its own, but nobody waits for it.
        With ``tag``, only if that job belongs to that question (never another conversation's)."""
        job_id, job_tag = self.jobs.get(site, ("", ""))
        fut = self.pending.get(job_id)
        if not job_id or fut is None or fut.done() or (tag is not None and tag != job_tag):
            return False
        if self.ws is not None and not self.ws.closed:
            asyncio.ensure_future(self.ws.send_json({"type": "cancel", "id": job_id, "site": site}))
        if not fut.done():
            fut.set_result({"ok": False, "error": "cancelled"})
        return True

    def cancel_all(self) -> list[str]:
        """"Parar todo": every chat site with a job in progress."""
        return [site for site in list(self.jobs) if self.cancel(site)]

    async def send_job(self, site: str, name: str, prompt: str, *, site_config: dict[str, str] | None = None,
                       timeout_s: float | None = None, tag: str = "",
                       wanted: Callable[[], bool] | None = None, files: list[dict[str, Any]] | None = None,
                       want: dict[str, Any] | None = None) -> dict[str, Any]:
        """One message to a chat site, always through the account guard (one at a time per site,
        spacing, daily cap, pause on account limits). ``site_config`` is for a site being added
        that is not saved yet. On failure: {"ok": False, "status", "error", "message", "detail"}."""
        provider = ProviderConfig(name=site, model=MODEL_PREFIX + site, kind="browser", daily_cap=self.site_cap(site))
        timeout_s = timeout_s or self.timeout_s
        payload = {"site": site, "site_config": site_config} if site_config else self.site_payload(site)
        async with self.locks.setdefault(site, asyncio.Lock()):  # one message at a time per site
            try:
                permit = await self.guard.acquire(provider, notify=self.log)
            except GuardBlocked as blocked:
                return {"ok": False, "status": 403, "error": "paused", "message": blocked.message_es, "detail": ""}
            extra_permits = []
            try:
                # Expensive modes (deep research, builder) have few uses a day: counted apart, per chat.
                for mode in sorted(set((want or {}).get("modes") or []) & EXPENSIVE_MODES):
                    try:
                        extra_permits.append(await self.guard.acquire(ProviderConfig(
                            name=f"{site}:{mode}", model=MODEL_PREFIX + site, kind="browser",
                            daily_cap=self.cfg.guard.expensive_daily_cap), notify=self.log))
                    except GuardBlocked:
                        return {"ok": False, "status": 429, "error": "expensive_cap", "detail": "",
                                "message": f"{name}: ya has usado hoy las {self.cfg.guard.expensive_daily_cap} veces "
                                           f"de «{mode}» (los modos caros se cuentan aparte). Mañana vuelve."}
                if (tag and tag in self.stopped) or (wanted is not None and not wanted()):
                    # stopped while it waited its turn: nothing is sent
                    return {"ok": False, "status": 409, "error": "cancelled", "detail": "",
                            "message": f"{name}: {ERRORS['cancelled'][2]}"}
                if not await self._ensure_extension():
                    return {"ok": False, "status": 503, "error": "bridge_unavailable", "detail": "",
                            "message": "Chrome no está conectado: abre Chrome con la extensión webllm cargada"}
                t0 = time.perf_counter()
                res = await self._send_to_extension(
                    {"type": "job", **payload, "prompt": prompt, "timeout_ms": int(timeout_s * 1000),
                     **({"want": want} if want else {})},
                    timeout_s + self.human_wait_s,  # room for a human to solve a verification
                    tag=tag, files=files,
                )
                res["latency"] = time.perf_counter() - t0
            finally:
                self.guard.release(permit)
                for extra in extra_permits:
                    self.guard.release(extra)
        if res.get("ok"):
            return res
        code = res.get("error", "extension_error")
        if code in FILE_ERRORS:
            res["detail"] = f"{code}: {res.get('detail') or ''}"
            code = "file_not_attached"
        status, hours, text = ERRORS.get(code, (502, None, "falló en la página del chat"))
        message = f"{name}: {text.format(site=name)}"
        if hours is not None:
            message = self.guard.trip(provider, text.format(site=name), None if hours < 0 else hours)
        detail = res.get("detail")
        self.log(f"{message}" + (f" [{detail}]" if detail else ""))
        return {"ok": False, "status": status, "error": code, "message": message, "detail": str(detail or "")}

    # --------------------------------------------------------------- panel

    async def panel(self, request: web.Request) -> web.Response:
        html = PANEL_HTML.read_text(encoding="utf-8").replace("__WEBLLM_TOKEN__", self.token)
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})

    async def panel_state(self, request: web.Request) -> web.Response:
        if request.query.get("token") != self.token:
            return self._error(401, "token del puente incorrecto", "unauthorized")
        import httpx
        omni = False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(self.cfg.base_url.rsplit("/v1", 1)[0] + "/api/health", timeout=3)
                omni = r.status_code == 200
        except httpx.HTTPError:
            omni = False
        return web.json_response({
            "omniroute": omni,
            "extension": self.connected.is_set(),
            "extension_path": str(EXTENSION_DIR),
            "providers": [{"name": p.name, "kind": p.kind} for p in self.cfg.enabled_providers],
            "paused": {k: v.get("cooldown_reason") for k, v in self.guard.status().items()
                       if (v.get("cooldown_until") or 0) > time.time()},
        })

    async def panel_run(self, request: web.Request) -> web.StreamResponse:
        if request.query.get("token") != self.token:
            return self._error(401, "token del puente incorrecto", "unauthorized")
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(request)

        async def send(obj: dict) -> None:
            await resp.write(f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8"))

        if self._panel_running:
            await send({"kind": "busy"})
            return resp
        self._panel_running = True
        from .selftest import run_checks  # late import: selftest imports this module

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(15)
                await resp.write(b": ping\n\n")

        beat = asyncio.create_task(heartbeat())
        program_with = request.query.get("program", "api")
        try:
            final = await run_checks(self.cfg, send, program_with=program_with)
            good = sum(ev["state"] == "ok" for ev in final)
            await send({"kind": "done", "good": good, "total": len(final)})
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            beat.cancel()
            self._panel_running = False
        return resp

    async def panel_ask(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return web.json_response({"error": "token del puente incorrecto"}, status=401)
        from .broadcaster import TargetError, GatewayError, broadcast, new_run_id, resolve_targets, write_run
        from .omniroute import load_api_key
        body = await request.json()
        prompt = str(body.get("prompt", "")).strip()
        if not prompt:
            return web.json_response({"error": "Escribe una pregunta."}, status=400)
        try:
            targets = resolve_targets(self.cfg, str(body.get("to") or "todas"))
        except TargetError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        skipped = []
        if not self.connected.is_set():
            skipped = [t.name for t in targets if t.gateway == "bridge"]
            targets = [t for t in targets if t.gateway != "bridge"]
            if not targets:
                return web.json_response({"error": "Esa IA es un chat de Chrome y la extensión no está instalada: "
                                                   "haz los 3 pasos del recuadro rojo de arriba."}, status=400)
        try:
            api_key = load_api_key()
        except Exception:
            api_key = ""
        guard = Guard(self.cfg.paths.state_dir / "guard.json", self.cfg.guard)
        try:
            outcomes = await broadcast(self.cfg, prompt, targets, api_key=api_key, guard=guard,
                                       notify=self.log, bridge_key=self.token)
        except GatewayError as exc:
            return web.json_response({"error": str(exc)}, status=503)
        run_id = new_run_id()
        write_run(self.cfg.paths.runs_dir, run_id, prompt, outcomes)
        return web.json_response({"run_id": run_id, "skipped": skipped, "outcomes": [{
            "name": o.target.name, "model": o.result.model or o.target.model, "ok": o.result.ok,
            "text": o.result.text, "seconds": round(o.result.latency_s, 1),
            "error": (o.result.error or "") + (f" {o.result.body_excerpt[:300]}" if o.result.body_excerpt else ""),
            "notices": o.notices} for o in outcomes]})

    # -------------------------------------------------------------- routes

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "extension": self.connected.is_set()})

    async def models(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        return web.json_response({"object": "list", "data": [
            {"id": MODEL_PREFIX + s, "object": "model", "owned_by": "webllm-bridge"} for s in self.site_names()]})

    async def status(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        return web.json_response({"extension": self.connected.is_set(), "guard": self.guard.status()})

    async def resume(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        body = await request.json() if request.can_read_body else {}
        sites = [body["site"]] if body.get("site") else list(self.site_names())
        cleared = [s for s in sites if self.guard.clear(s)]
        return web.json_response({"cleared": cleared})

    async def diagnose(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        site = (await request.json()).get("site", "")
        if site not in self.site_names():
            return self._error(404, f"sitio desconocido: {site}", "unknown_site")
        if not await self._ensure_extension():
            return self._error(503, "Chrome no está conectado", "bridge_unavailable")
        res = await self._send_to_extension({"type": "diagnose", **self.site_payload(site)}, 90)
        return web.json_response(res)

    async def chat_completions(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        body = await request.json()
        model = str(body.get("model", ""))
        site = model[len(MODEL_PREFIX):] if model.startswith(MODEL_PREFIX) else model
        names = self.site_names()
        if site not in names:
            return self._error(404, f"modelo desconocido: {model} (usa {', '.join(MODEL_PREFIX + s for s in names)})", "model_not_found")
        prompt = flatten_messages(body.get("messages") or [])
        if not prompt.strip():
            return self._error(400, "el prompt está vacío", "empty_prompt")
        # PLAN-v5 F4: what Iván chose for this chat (model, modes) and the files that go with the question
        extra = body.get("webllm") if isinstance(body.get("webllm"), dict) else {}
        try:
            files = decode_files(extra.get("files") or [])
        except RequestError as exc:
            return self._error(exc.status, exc.message, exc.code)
        want = {k: v for k, v in {"model": str(extra.get("model") or "")[:120] or None,
                                  "modes": [str(m) for m in extra.get("modes") or []][:6]}.items() if v}
        transport = request.transport
        tag = request.headers.get("x-webllm-run", "")
        res = await self.send_job(site, names[site], prompt, tag=tag, files=files or None, want=want or None,
                                  wanted=lambda: transport is not None and not transport.is_closing())
        if not res.get("ok"):
            detail = res.get("detail")
            message = res["message"] + (f" ({detail})" if detail and res["status"] == 502 else "")
            return self._error(res["status"], message, res["error"])

        latency = res["latency"]
        text = res.get("text", "")
        webllm = {"used": res.get("used") or {}, "downloads": self._save_downloads(tag, res.get("downloads") or [])}
        label = str(res.get("model_label") or "")
        if label:
            model = f"{model} · {label}"
        headers = {"x-webllm-site": site, "x-webllm-capture": str(res.get("via", "")),
                   "x-webllm-model-label": label.encode("ascii", "replace").decode(),
                   "x-webllm-latency-ms": str(int(latency * 1000))}
        cid = "chatcmpl-" + uuid.uuid4().hex
        created = int(time.time())
        if body.get("stream"):
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", **headers})
            await resp.prepare(request)
            for chunk in (
                {"choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "webllm": webllm},
            ):
                data = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model, **chunk}
                await resp.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
            await resp.write(b"data: [DONE]\n\n")
            await resp.write_eof()
            return resp
        return web.json_response({
            "id": cid, "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(text) // 4,
                      "total_tokens": (len(prompt) + len(text)) // 4},
            "webllm": webllm,
        }, headers=headers)

    def _save_downloads(self, tag: str, items: list[Any]) -> list[dict[str, Any]]:
        """Files a chat produced (made in its page) go to data/descargas/<question>/; links stay links."""
        folder = self.cfg.paths.data_dir / "descargas" / (tag if re.fullmatch(r"[\w-]{1,64}", tag or "") else
                                                          time.strftime("%Y%m%d-%H%M%S"))
        out: list[dict[str, Any]] = []
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            name = re.sub(r"[^\w.\- ]+", "_", str(item.get("name") or "archivo"))[:100].strip(" .") or "archivo"
            if item.get("b64"):
                try:
                    data = base64.b64decode(str(item["b64"]), validate=True)
                except ValueError:
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / name
                for n in range(2, 100):
                    if not path.exists():
                        break
                    path = folder / f"{Path(name).stem}-{n}{Path(name).suffix}"
                path.write_bytes(data)
                out.append({"name": name, "path": str(path), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            elif str(item.get("url") or "").startswith("https://"):
                out.append({"name": name, "url": str(item["url"])[:500]})
        return out


def serve(cfg: AppConfig, port: int, timeout_s: float) -> None:
    token = load_token(cfg.paths.state_dir)
    cfg_path = write_extension_config(token, port)
    log_file = cfg.paths.logs_dir / "bridge.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line, flush=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    bridge = Bridge(cfg, token, timeout_s=timeout_s, log=log)
    print(f"Puente webllm en http://127.0.0.1:{port}/v1  (extensión: {cfg_path.parent})")
    print(f"Panel de pruebas: http://127.0.0.1:{port}/   App: http://127.0.0.1:{port}/app/")
    print("Esperando a Chrome... Deja esta ventana abierta.")
    web.run_app(bridge.app(), host="127.0.0.1", port=port, print=None, access_log=None)


async def call_admin(port: int, token: str, path: str, payload: dict | None = None) -> tuple[int, Any]:
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.post(f"http://127.0.0.1:{port}{path}", json=payload or {},
                              headers={"Authorization": f"Bearer {token}"}, timeout=120)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text


__all__ = ["Bridge", "flatten_messages", "load_token", "write_extension_config", "serve", "SITES", "MODEL_PREFIX"]

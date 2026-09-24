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
import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from aiohttp import WSMsgType, web

from .client import _content_text
from .config import PROJECT_ROOT, AppConfig, ProviderConfig
from .guard import Guard, GuardBlocked

MODEL_PREFIX = "browser/"
PANEL_HTML = Path(__file__).with_name("panel.html")
SITES = {"qwen": "Qwen", "deepseek": "DeepSeek", "zai": "z.ai", "meta": "Meta AI"}
EXTENSION_DIR = PROJECT_ROOT / "extension"

# extension error code -> (HTTP status, pause hours or None, Spanish message)
ERRORS: dict[str, tuple[int, float | None, str]] = {
    "login_required": (401, None, "no hay sesión abierta en Chrome. Entra en {site} con tu cuenta (o una nueva) y vuelve a pedirlo"),
    "banned": (403, 24 * 30, "la cuenta parece bloqueada. Crea otra, entra con ella en Chrome y haz doble clic en REANUDAR"),
    "rate_limited": (403, -1, "límite de mensajes del chat alcanzado"),
    "challenge": (403, -1, "pidió una verificación humana y nadie la resolvió"),
    "timeout": (504, None, "no terminó de responder a tiempo"),
    "extension_disconnected": (503, None, "Chrome se desconectó a mitad del envío"),
}


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
        self.locks: dict[str, asyncio.Lock] = {s: asyncio.Lock() for s in SITES}
        self._last_launch = -1e9
        self._panel_running = False

    # ------------------------------------------------------------------ app

    @web.middleware
    async def _local_only(self, request: web.Request, handler):
        # Only answer requests addressed to this PC (blocks DNS-rebinding tricks).
        host = request.host.split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            return web.Response(status=403, text="local only")
        return await handler(request)

    def app(self) -> web.Application:
        app = web.Application(client_max_size=64 * 1024 * 1024, middlewares=[self._local_only])
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
        return app

    def _authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization", "") == f"Bearer {self.token}"

    @staticmethod
    def _error(status: int, message: str, code: str) -> web.Response:
        return web.json_response({"error": {"message": message, "type": code, "code": code}}, status=status)

    # ------------------------------------------------------------ extension

    async def ext_socket(self, request: web.Request) -> web.StreamResponse:
        if request.query.get("token") != self.token:
            return web.Response(status=401, text="bad token")
        ws = web.WebSocketResponse(heartbeat=25)
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

    async def _send_to_extension(self, payload: dict[str, Any], wait_s: float) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[job_id] = fut
        try:
            await self.ws.send_json({**payload, "id": job_id})
            return await asyncio.wait_for(fut, wait_s)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout"}
        finally:
            self.pending.pop(job_id, None)

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
        try:
            final = await run_checks(self.cfg, send)
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
            {"id": MODEL_PREFIX + s, "object": "model", "owned_by": "webllm-bridge"} for s in SITES]})

    async def status(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        return web.json_response({"extension": self.connected.is_set(), "guard": self.guard.status()})

    async def resume(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        body = await request.json() if request.can_read_body else {}
        sites = [body["site"]] if body.get("site") else list(SITES)
        cleared = [s for s in sites if self.guard.clear(s)]
        return web.json_response({"cleared": cleared})

    async def diagnose(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        site = (await request.json()).get("site", "")
        if site not in SITES:
            return self._error(404, f"sitio desconocido: {site}", "unknown_site")
        if not await self._ensure_extension():
            return self._error(503, "Chrome no está conectado", "bridge_unavailable")
        res = await self._send_to_extension({"type": "diagnose", "site": site}, 90)
        return web.json_response(res)

    async def chat_completions(self, request: web.Request) -> web.StreamResponse:
        if not self._authorized(request):
            return self._error(401, "token del puente incorrecto", "unauthorized")
        body = await request.json()
        model = str(body.get("model", ""))
        site = model[len(MODEL_PREFIX):] if model.startswith(MODEL_PREFIX) else model
        if site not in SITES:
            return self._error(404, f"modelo desconocido: {model} (usa {', '.join(MODEL_PREFIX + s for s in SITES)})", "model_not_found")
        prompt = flatten_messages(body.get("messages") or [])
        if not prompt.strip():
            return self._error(400, "el prompt está vacío", "empty_prompt")
        provider = ProviderConfig(name=site, model=model, kind="browser")
        name = SITES[site]

        async with self.locks[site]:  # one message at a time per site
            try:
                permit = await self.guard.acquire(provider, notify=self.log)
            except GuardBlocked as blocked:
                return self._error(403, blocked.message_es, "paused")
            try:
                if not await self._ensure_extension():
                    return self._error(503, "Chrome no está conectado: abre Chrome con la extensión webllm cargada", "bridge_unavailable")
                t0 = time.perf_counter()
                res = await self._send_to_extension(
                    {"type": "job", "site": site, "prompt": prompt, "timeout_ms": int(self.timeout_s * 1000)},
                    self.timeout_s + self.human_wait_s,  # room for a human to solve a verification
                )
                latency = time.perf_counter() - t0
            finally:
                self.guard.release(permit)

        if not res.get("ok"):
            code = res.get("error", "extension_error")
            status, hours, text = ERRORS.get(code, (502, None, "falló en la página del chat"))
            message = f"{name}: {text.format(site=name)}"
            if hours is not None:
                message = self.guard.trip(provider, text.format(site=name), None if hours < 0 else hours)
            detail = res.get("detail")
            self.log(f"{message}" + (f" [{detail}]" if detail else ""))
            return self._error(status, message + (f" ({detail})" if detail and status == 502 else ""), code)

        text = res.get("text", "")
        headers = {"x-webllm-site": site, "x-webllm-capture": str(res.get("via", "")),
                   "x-webllm-latency-ms": str(int(latency * 1000))}
        cid = "chatcmpl-" + uuid.uuid4().hex
        created = int(time.time())
        if body.get("stream"):
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", **headers})
            await resp.prepare(request)
            for chunk in (
                {"choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
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
        }, headers=headers)


def serve(cfg: AppConfig, port: int, timeout_s: float) -> None:
    token = load_token(cfg.paths.state_dir)
    cfg_path = write_extension_config(token, port)
    bridge = Bridge(cfg, token, timeout_s=timeout_s)
    print(f"Puente webllm en http://127.0.0.1:{port}/v1  (extensión: {cfg_path.parent})")
    print(f"Panel de pruebas: http://127.0.0.1:{port}/")
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

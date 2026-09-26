"""webllm as the one connection of the face (PLAN-v5 D2): an OpenAI-compatible API under /gw/v1.

Every AI webllm knows is a "model" here: the chat sites in Chrome, the API models (OmniRoute) and
the models on this PC.
- A chat site: the question goes through the same engine as the app (flows.run_flow: the account
  guard, the journal with its green padlock, the history, the error codes). While it runs, the
  answer's thinking block (OpenAI ``reasoning_content``) says what is happening, "te espera" included.
- An AI by API or on this PC: the request goes as it came (tools included) and the answer streams back
  as it is written; the daily cap (budget.py) and the stand-ins configured for it apply, and the call is
  journaled in the same shape as a one-step flow.
Either way: SSE comments keep long waits alive; the last chunk carries ``webllm.avisos``, what Iván must
still see (D21: what you see is what was used); if the face goes away (its stop button) or "Parar todo"
is pressed, the work stops, the Chrome job included, and the journal says so.

Webllm's own fields travel in the request body under ``webllm``:
    {"chat_id", "message_id", "task", "files": [{"name", "mime", "data" (base64), "sha256"?}], "modes": [...]}
Files are checked (size, sha256) and recorded in the journal; handing them to the web chats is phase F4.
A ``task`` (a title, tags... that Open WebUI generates in the background) never reaches a web chat.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from aiohttp import web

from . import flows, journal
from .appapi import MAX_PROMPT, site_of
from .broadcaster import SKIPPED as _SKIPPED, GatewayError, Outcome, new_run_id, upstream_key
from .budget import budget_for
from .client import (CANCELLED, CONNECTION_ERROR, HTTP_ERROR, MALFORMED, OK, TIMEOUT, TRANSPARENT_HEADERS, ChatResult,
                     _content_text, auth_headers)
from .config import AppConfig, ProviderConfig
from .guard import Guard
from .local import server_lock
from .omniroute import load_api_key
from .problems import WAITING_SHORT, problem_text

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES_BYTES = 100 * 1024 * 1024
HEARTBEAT_S = 10.0
KIND_LABEL = {"bridge": "web", "omniroute": "API", "local": "tu PC"}
DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,(.*)$", re.S)
# What an OpenAI-style request may carry besides model/messages/stream, passed on as it came.
DIRECT_KEYS = ("tools", "tool_choice", "parallel_tool_calls", "temperature", "top_p", "max_tokens",
               "max_completion_tokens", "stop", "seed", "response_format")


class RequestError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if m.get("role") == "user":
            return (_content_text(m.get("content")) or "").strip()
    return ""


def _inline_images(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Images the face put inside the last user message as data URLs (OpenAI image_url parts)."""
    out = []
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        for n, part in enumerate(m.get("content") if isinstance(m.get("content"), list) else []):
            url = ((part or {}).get("image_url") or {}).get("url", "") if isinstance(part, dict) else ""
            hit = DATA_URL.match(url or "")
            if hit:
                out.append({"name": f"imagen-{n + 1}.{hit.group(1).split('/')[-1]}", "mime": hit.group(1),
                            "data": hit.group(2), "inline": True})
        break
    return out


def decode_files(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check the files sent with a question: base64, size limits, and the sha256 when one is given.
    Returns [{"name", "mime", "size", "sha256", "bytes", "inline"}] without duplicates (same content)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for item in items or []:
        if not isinstance(item, dict):
            raise RequestError(400, "bad_file", "Un archivo llegó mal formado.")
        name = str(item.get("name") or "archivo")[:200]
        if "data" not in item:
            raise RequestError(400, "bad_file", f"El archivo «{name}» llegó sin contenido.")
        try:
            data = base64.b64decode(str(item.get("data") or ""), validate=True)
        except (binascii.Error, ValueError):
            raise RequestError(400, "bad_file", f"El archivo «{name}» llegó dañado.") from None
        digest = hashlib.sha256(data).hexdigest()
        if item.get("sha256") and str(item["sha256"]).lower() != digest:
            raise RequestError(400, "bad_file", f"El archivo «{name}» cambió por el camino (su huella no coincide).")
        if len(data) > MAX_FILE_BYTES:
            raise RequestError(413, "file_too_big", f"El archivo «{name}» pasa de 50 MB.")
        total += len(data)
        if total > MAX_FILES_BYTES:
            raise RequestError(413, "file_too_big", "Los archivos de un mensaje no pueden pasar de 100 MB en total.")
        if digest in seen:
            continue
        seen.add(digest)
        out.append({"name": name, "mime": str(item.get("mime") or "application/octet-stream")[:100],
                    "size": len(data), "sha256": digest, "bytes": data, "inline": bool(item.get("inline"))})
    return out


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",") if n >= 1024 * 1024 else f"{max(1, round(n / 1024))} KB"


def card(p: ProviderConfig, cap: int | None) -> str:
    """One line about an AI for the face (its description under the name): what it costs, how it goes."""
    if p.gateway == "bridge":
        return (f"Chat de tu Chrome: gasta mensajes de tu cuenta (webllm la protege: como mucho {cap} al día). "
                "Va despacio; puede pedirte una verificación."
                + ("" if p.private else " No privada: lo que escribes puede publicarse o usarse; webllm nunca "
                   "la elige por su cuenta."))
    if p.gateway == "local":
        return "En tu PC: gratis y privada; va a la velocidad de tu ordenador."
    return (f"Por API: gratis dentro del límite del servicio (y como mucho {cap} preguntas al día). "
            "Rápida; puede usar herramientas.")


class Reply:
    """One answer to the face: a stream of OpenAI chunks (notes as reasoning, the answer, the last chunk
    with what Iván must still see), or without stream one JSON at the end."""

    def __init__(self, request: web.Request, stream: bool, run_id: str, model: str) -> None:
        self.request, self.stream, self.run_id, self.model = request, stream, run_id, model
        self.cid, self.created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
        self.resp: web.StreamResponse | None = None
        self.closed = False
        self.notes: list[str] = []
        self.avisos: list[str] = []

    async def open(self) -> None:
        if not self.stream:
            return
        self.resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                                "X-Accel-Buffering": "no", "x-webllm-run": self.run_id})
        await self.resp.prepare(self.request)
        await self.chunk({"role": "assistant"})

    def gone(self) -> bool:
        """The face went away (its stop button closes the connection)."""
        transport = self.request.transport
        return self.closed or transport is None or transport.is_closing()

    async def write(self, data: bytes) -> None:
        if self.closed or self.resp is None:
            return
        try:
            await self.resp.write(data)
        except (ConnectionResetError, RuntimeError):
            self.closed = True

    async def chunk(self, delta: dict[str, Any], finish: str | None = None, **extra: Any) -> None:
        data = {"id": self.cid, "object": "chat.completion.chunk", "created": self.created, "model": self.model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}], **extra}
        await self.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))

    async def say(self, text: str) -> None:
        self.notes.append(text)
        if self.stream:
            await self.chunk({"reasoning_content": text + "\n\n"})

    async def heartbeat(self) -> None:
        while self.stream:
            await asyncio.sleep(HEARTBEAT_S)
            await self.write(b": webllm sigue\n\n")

    async def end(self) -> web.StreamResponse:
        await self.write(b"data: [DONE]\n\n")
        if not self.closed and self.resp is not None:
            with contextlib.suppress(ConnectionResetError, RuntimeError):
                await self.resp.write_eof()
        return self.resp  # type: ignore[return-value]

    async def error(self, code: str, message: str, status: int = 502) -> web.StreamResponse:
        if not self.stream:
            return web.json_response({"error": {"message": message, "type": code, "code": code, "run_id": self.run_id},
                                      "webllm": {"avisos": self.avisos}}, status=status, headers={"x-webllm-run": self.run_id})
        await self.write(f"data: {json.dumps({'error': {'message': message, 'code': code}, 'webllm': {'avisos': self.avisos}}, ensure_ascii=False)}\n\n".encode("utf-8"))
        return await self.end()


class Gateway:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge
        self.running: dict[str, tuple[asyncio.Task, ProviderConfig]] = {}  # run id -> (work, AI), for "Parar todo"

    def register(self, app: web.Application) -> None:
        app.router.add_get("/gw/v1/models", self.models)
        app.router.add_post("/gw/v1/chat/completions", self.chat)
        app.router.add_post("/gw/v1/parar", self.stop_all)

    @staticmethod
    def _error(status: int, code: str, message: str) -> web.Response:
        return web.json_response({"error": {"message": message, "type": code, "code": code}}, status=status)

    # ---------------------------------------------------------------- models

    async def models(self, request: web.Request) -> web.Response:
        if not self.bridge._authorized(request):
            return self._error(401, "unauthorized", "token del puente incorrecto")
        cfg = await self.bridge.app_api._cfg()
        order = {"bridge": 0, "omniroute": 1, "local": 2}
        providers = sorted((p for p in cfg.enabled_providers if p.gateway in order), key=lambda p: order[p.gateway])
        data = []
        for p in providers:
            today, cap = self.bridge.app_api.usage(cfg, p)  # the same numbers the app shows
            kind = {"bridge": "chat", "omniroute": "api", "local": "local"}[p.gateway]
            tail = f" ({KIND_LABEL[p.gateway]}" + ("" if p.private else ", no privada") + ")"  # its name warns (F3)
            view = self.bridge.app_api.ficha_view(p, site_of(p)) if site_of(p) else None
            default = (f" Sin elegir modelo usa el más potente: «{view['strongest']}»." if view and view["strongest"]
                       else " Sin elegir modelo usa el que tenga puesto su web." if view else "")
            data.append({
                "id": p.name, "object": "model", "owned_by": "webllm",
                "name": f"{p.display.removesuffix(' (chat)')}{tail}",
                "webllm": {"kind": kind, "label": p.display, "card": card(p, cap) + default,
                           "daily_cap": cap, "used_today": today}})
            # each model of its selector (PLAN-v5 D18/D22), strongest first and saying so
            for m in (view or {}).get("models") or []:
                note = " — el más potente" if m["strongest"] else "" if m["known"] else " (nuevo, sin datos)"
                data.append({
                    "id": f"{p.name}@{m['slug']}", "object": "model", "owned_by": "webllm",
                    "name": f"{p.display.removesuffix(' (chat)')} · {m['name']}{tail}{note}",
                    "webllm": {"kind": kind, "label": p.display, "model": m["name"], "strongest": m["strongest"],
                               "card": card(p, cap) + f" Modelo «{m['name']}» de su selector.",
                               "daily_cap": cap, "used_today": today}})
        return web.json_response({"object": "list", "data": data})

    # ----------------------------------------------------------------- stop

    async def stop_all(self, request: web.Request) -> web.Response:
        """"Parar todo": every question in progress through here, and every job in Chrome."""
        if not self.bridge._authorized(request):
            return self._error(401, "unauthorized", "token del puente incorrecto")
        stopped, sites = len(self.running), set()
        for run_id, (work, p) in list(self.running.items()):
            if self._stop(p, work, run_id):
                sites.add(site_of(p))
        app_stopped, app_sites = self.bridge.app_api.stop_all()  # the app's own questions
        stopped, sites = stopped + app_stopped, sites | app_sites
        sites.update(self.bridge.cancel_all())  # and any other job in Chrome (e.g. `webllm cadena`)
        return web.json_response({"parados": stopped, "chats": sorted(sites)})

    def _stop(self, p: ProviderConfig, work: asyncio.Task, run_id: str) -> bool:
        """Stop one question. A chat site: its job in Chrome ends as "cancelled" (the flow then finishes and
        journals it) and, if it is still waiting its turn, it is never sent. Anything else: cancelled outright."""
        self.bridge.stop(run_id)
        site = site_of(p)
        if site and self.bridge.cancel(site, tag=run_id):
            return True  # a job in Chrome was stopped
        work.cancel()
        return False

    # ------------------------------------------------------------------ chat

    async def _prepare(self, body: dict[str, Any]) -> tuple[Any, ProviderConfig, dict[str, Any]]:
        if not isinstance(body, dict):
            raise RequestError(400, "bad_request", "La petición no es un objeto JSON.")
        ext = body.get("webllm") if isinstance(body.get("webllm"), dict) else {}
        cfg = await self.bridge.app_api._cfg()
        name = str(body.get("model") or "")
        base, _, slug = name.partition("@")  # "qwen@qwen3.8max": that chat, that model of its selector
        p = cfg.providers.get(base)
        if p is None or not p.enabled or (slug and not site_of(p)):
            raise RequestError(404, "model_not_found", f"No conozco esta IA: {name}.")
        want_model, strongest, use_page = None, False, False
        if site_of(p):
            view = self.bridge.app_api.ficha_view(p, site_of(p))
            if slug:
                hit = next((m for m in view["models"] if m["slug"] == slug), None)
                if hit is None:
                    raise RequestError(404, "model_not_found", f"Ese modelo ya no está en la ficha de {p.display}: "
                                                               "pulsa Descubrir en webllm → Conectores.")
                want_model, strongest = hit["name"], hit["strongest"]
            elif view["strongest"]:  # by default, the strongest (D21.3)
                want_model, strongest = view["strongest"], True
            use_page = bool(view.get("use_page_model")) and not slug
        if ext.get("task") and p.gateway == "bridge":
            raise RequestError(400, "task_for_web_chat", problem_text("task_for_web_chat", p.display))
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        conversation = self.bridge_flatten(messages)
        question = _last_user_text(messages) or conversation
        if not conversation.strip():
            raise RequestError(400, "empty_prompt", "El mensaje está vacío.")
        if len(conversation) > MAX_PROMPT:
            raise RequestError(413, "too_long", "La conversación es demasiado larga para mandarla de una vez.")
        files = decode_files([*(ext.get("files") or []), *_inline_images(messages)])
        modes = [str(m)[:40] for m in (ext.get("modes") or []) if isinstance(m, str)][:10]
        return cfg, p, {"question": question, "conversation": conversation, "files": files, "modes": modes,
                        "want_model": want_model, "strongest": strongest, "use_page_model": use_page,
                        "chat_id": str(ext.get("chat_id") or "")[:100], "message_id": str(ext.get("message_id") or "")[:100],
                        "task": str(ext.get("task") or "")[:60], "tools": bool(body.get("tools")),
                        # where Open WebUI keeps the conversation (its folder = the project in Obsidian)
                        "project": str(ext.get("project") or "")[:80] or None, "title": str(ext.get("title") or "")[:120] or None}

    @staticmethod
    def bridge_flatten(messages: list[dict[str, Any]]) -> str:
        from .bridge import flatten_messages  # late: bridge imports this module
        return flatten_messages(messages)

    def _record(self, cfg: AppConfig, run_dir: Any, run_id: str, p: ProviderConfig, req: dict[str, Any],
                flow: flows.Flow) -> None:
        """The first journal line of a question from the face: where it came from, and the files
        (saved next to it, hashed) and modes it brought."""
        entries = []
        if req["files"]:
            (run_dir / "files").mkdir(parents=True, exist_ok=True)
        for n, f in enumerate(req["files"], start=1):
            rel = f"files/{n:02d}-{flows._safe(f['name'])}"
            (run_dir / rel).write_bytes(f["bytes"])
            entries.append({"name": f["name"], "mime": f["mime"], "size": f["size"], "sha256": f["sha256"], "file": rel})
        run_dir.mkdir(parents=True, exist_ok=True)
        journal.append(run_dir / journal.JOURNAL_NAME, {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": run_id, "kind": "gateway",
            "origin": "open-webui",
            "provider": p.name, "chat_id": req["chat_id"], "message_id": req["message_id"], "task": req["task"],
            "files": entries, "modes": req["modes"],
            **({"project": req["project"]} if req["project"] else {}), **({"title": req["title"]} if req["title"] else {}),
        })
        # PLAN-v5 F5: the question is in Obsidian while the answer is on its way, in the project (Open WebUI's
        # folder) and under the title Open WebUI shows
        flows.write_flow(run_dir, flow)
        flows.to_vault(cfg, run_dir, project=req["project"], title=req["title"])

    @staticmethod
    def _flow(p: ProviderConfig, req: dict[str, Any]) -> flows.Flow:
        return flows.Flow(
            name="Desde Open WebUI", template="pregunta",
            inputs={"pregunta": req["question"], "conversacion": req["conversation"], "origen": "Open WebUI",
                    "chat_id": req["chat_id"], "message_id": req["message_id"]},
            steps=(flows.Step(id="respuestas", title="Respuesta", to=(p.name,), message="{{conversacion}}"),))

    async def _before(self, reply: Reply, p: ProviderConfig, req: dict[str, Any]) -> None:
        """Say what came with the question and what the AI will get of it."""
        direct = p.gateway != "bridge"
        if not direct:  # a chat site (PLAN-v5 F4): the files go up with its own button, checked on its page
            for f in req["files"]:
                await reply.say(f"Recibido «{f['name']}» ({_size(f['size'])}, huella {f['sha256'][:12]}). "
                                f"Se sube a {p.display} con su propio botón y se comprueba que queda adjunto.")
            if req["want_model"]:
                await reply.say(f"Modelo: «{req['want_model']}»" + (" (el más potente)." if req["strongest"] else "."))
            elif req["use_page_model"]:
                await reply.say(f"Modelo: el que tenga puesto {p.display} (lo elegiste tú en su Ficha).")
            else:
                await reply.say(f"Modelo: el que tenga puesto {p.display} (aún no sé cuál es su más potente: "
                                "márcalo en su Ficha, en webllm).")
            if req["modes"]:
                await reply.say(f"Pediste: {', '.join(req['modes'])}. Se pone en {p.display} y se comprueba en su "
                                "web antes de enviar; si no se puede, no se envía.")
        else:
            for f in req["files"]:
                await reply.say(f"Recibido «{f['name']}» ({_size(f['size'])}, huella {f['sha256'][:12]}). " +
                                ("Va dentro del mensaje, tal cual." if f["inline"] else
                                 f"{p.display} no lo recibe: por API solo van imágenes dentro del mensaje."))
            unseen = [f for f in req["files"] if not f["inline"]]
            if unseen:
                names = ", ".join(f"«{f['name']}»" for f in unseen)
                reply.avisos.append(f"{p.display} no ha visto {names}: por API solo van imágenes. Para un PDF u "
                                    "otro archivo, pregúntaselo a un chat web.")
            if req["modes"]:
                reply.avisos.append(f"{', '.join(req['modes']).capitalize()}: son modos de los chats web; "
                                    f"{p.display} (por API) no los tiene.")
        if req["tools"] and not direct:
            reply.avisos.append(f"{p.display} todavía no puede usar herramientas: llega en la fase F9.")

    async def chat(self, request: web.Request) -> web.StreamResponse:
        if not self.bridge._authorized(request):
            return self._error(401, "unauthorized", "token del puente incorrecto")
        try:
            body = await request.json()
            cfg, p, req = await self._prepare(body)
        except RequestError as exc:
            return self._error(exc.status, exc.code, exc.message)
        except (ValueError, UnicodeDecodeError):
            return self._error(400, "bad_request", "La petición no es JSON.")
        if p.gateway == "omniroute" and not await self.bridge.app_api._omniroute_up():
            return self._error(503, "unreachable", problem_text("unreachable", p.display))
        flow = self._flow(p, req)
        try:
            flows.validate(cfg, flow)
        except flows.FlowError as exc:
            return self._error(400, "invalid", str(exc))

        run_id = new_run_id()
        run_dir = cfg.paths.runs_dir / run_id
        self._record(cfg, run_dir, run_id, p, req, flow)
        reply = Reply(request, bool(body.get("stream")), run_id, p.name)
        await reply.open()
        await self._before(reply, p, req)
        beat = asyncio.create_task(reply.heartbeat())
        try:
            if p.gateway == "bridge":
                return await self._through_flow(reply, cfg, p, flow, run_dir, req)
            return await self._direct(reply, cfg, p, flow, run_dir, req, body)
        finally:
            beat.cancel()

    async def _watch(self, reply: Reply, work: asyncio.Task, p: ProviderConfig) -> None:
        """While the work runs: "te espera" for a chat waiting for Iván, and stop it all if the face goes."""
        site, last = site_of(p), None
        while not work.done():
            if reply.gone():
                self._stop(p, work, reply.run_id)
                return
            kind = self.bridge.waiting.get(site) if site else None
            if kind != last:
                if kind in WAITING_SHORT:
                    await reply.say(WAITING_SHORT[kind].format(ai=p.display))
                elif last:
                    await reply.say("Sigo.")
                last = kind
            await asyncio.sleep(0.5)

    # A chat site: the same engine as the app.
    async def _through_flow(self, reply: Reply, cfg: Any, p: ProviderConfig, flow: flows.Flow, run_dir: Any,
                            req: dict[str, Any]):
        done: dict[str, Any] = {}

        async def emit(ev: dict[str, Any]) -> None:
            t = ev.get("type")
            if t == "target_start":
                await reply.say(f"Preguntando a {ev.get('label')}…")
            elif t == "target_wait":
                await reply.say(f"{ev.get('label')} falló ({ev.get('error')}). Lo intento otra vez en {ev.get('seconds')} s.")
            elif t == "target_fallback":
                await reply.say(f"{ev.get('label')} falló ({ev.get('error')}). Pruebo con {ev.get('provider_label')}, "
                                "la reserva que tienes configurada.")
            elif t == "target_done":
                self.bridge.app_api._remember(ev)
                done.update(ev)

        try:
            api_key = load_api_key()
        except Exception:
            api_key = ""
        guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
        extra = {"model": req["want_model"], "modes": req["modes"],
                 "files": [{"name": f["name"], "mime": f["mime"], "sha256": f["sha256"],
                            "data": base64.b64encode(f["bytes"]).decode("ascii")} for f in req["files"]]}
        work = asyncio.create_task(flows.run_flow(cfg, flow, api_key=api_key, guard=guard, bridge_key=self.bridge.token,
                                                  emit=emit, run_id=reply.run_id,
                                                  bridge_extra={k: v for k, v in extra.items() if v}))
        self.running[reply.run_id] = (work, p)
        watch = asyncio.create_task(self._watch(reply, work, p))
        try:
            # shield: cancelling this request must not kill the work on the spot (asyncio would cancel the
            # awaited task too) before its job in Chrome is told to stop; _stop decides how it ends.
            await asyncio.shield(work)
        except asyncio.CancelledError:
            if not work.done():  # the face's request itself was cancelled: stop the work, let it journal it
                self._stop(p, work, reply.run_id)
                raise
            self._journal_stop(run_dir, reply.run_id, p)  # stopped before anything was sent
            done = {"ok": False, "code": "cancelled", "error": ""}
        except GatewayError:
            shutil.rmtree(run_dir, ignore_errors=True)  # nothing was sent
            done = {"ok": False, "code": "unreachable", "error": ""}
        finally:
            watch.cancel()
            self.running.pop(reply.run_id, None)
            self.bridge.stopped.discard(reply.run_id)

        for notice in done.get("notices") or []:
            await reply.say(str(notice))
        if not done.get("ok"):
            code = str(done.get("code") or "error")
            return await reply.error(code, problem_text(code, p.display, str(done.get("error") or "")))
        if done.get("provider") and done.get("provider") != p.name:
            reply.avisos.append(f"Respondió {done.get('provider_label')} en lugar de {p.display} (tu reserva).")
        reply.avisos.extend(self._used_avisos(p, done))
        return await self._finish_text(reply, str(done.get("text") or ""))

    def _used_avisos(self, p: ProviderConfig, done: dict[str, Any]) -> list[str]:
        """What the chat's page really used (read back from it) and what it produced (PLAN-v5 D21/D22)."""
        used = done.get("used") or {}
        out = []
        label = str(done.get("model") or "").partition(" · ")[2]
        model = used.get("model") or label
        modes = [str(m.get("name") or m.get("mode")) for m in used.get("modes") or [] if isinstance(m, dict)]
        what = (f"con el modelo «{model}»" if model else "con el modelo que tenía puesto su web") + (
            f" y {'el modo' if len(modes) == 1 else 'los modos'} {', '.join(f'«{m}»' for m in modes)}" if modes else "")
        out.append(f"Respondió {p.display} {what}" + (" (comprobado en su web)." if used.get("model") or modes else "."))
        extra_on = [m for m in used.get("modes_on") or [] if m not in modes]
        if extra_on:
            out.append(f"En su web también estaba puesto: {', '.join(f'«{m}»' for m in extra_on)} (no lo pediste; "
                       "webllm no lo quita).")
        files = [f for f in used.get("files") or [] if isinstance(f, dict)]
        if files:
            entry = self.bridge.app_api.catalog.get(site_of(p) or "")
            who = f"{p.display} ({entry.by})" if entry and entry.by and entry.by != p.display else p.display
            names = ", ".join("«" + str(f.get("name")) + "»" for f in files)
            out.append(f"{names} se {'subió' if len(files) == 1 else 'subieron'} a {who}, con la misma huella.")
        fixed = done.get("repaired") or {}
        if fixed:
            what = {"input": "su caja de texto", "answer": "su respuesta"}
            parts = " y ".join(what.get(r, r) for r in fixed.get("roles") or [])
            out.append(f"La web de {p.display} había cambiado y webllm no encontraba {parts}: {fixed.get('ai')} señaló "
                       "dónde está, se comprobó en la página sin enviar nada y queda guardado (lo puedes deshacer en su "
                       "Ficha, en webllm).")
        for d in done.get("downloads") or []:
            if d.get("path"):
                out.append(f"{p.display} generó «{d.get('name')}»: guardado en {d['path']}.")
            elif d.get("url"):
                out.append(f"{p.display} dejó «{d.get('name')}» en su web: {d['url']}")
        return out

    def _journal_stop(self, run_dir: Any, run_id: str, p: ProviderConfig) -> None:
        journal.append(run_dir / journal.JOURNAL_NAME, {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "run_id": run_id,
            "kind": "stopped", "provider": p.name, "by": "Iván (parar)"})

    async def _finish_text(self, reply: Reply, text: str) -> web.StreamResponse:
        if not reply.stream:
            return web.json_response({
                "id": reply.cid, "object": "chat.completion", "created": reply.created, "model": reply.model,
                "webllm": {"avisos": reply.avisos},
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text,
                                         **({"reasoning_content": "\n\n".join(reply.notes)} if reply.notes else {})}}],
            }, headers={"x-webllm-run": reply.run_id})
        await reply.chunk({"content": text})
        await reply.chunk({}, "stop", webllm={"avisos": reply.avisos})
        return await reply.end()

    # An AI by API or on this PC: the request as it came, the answer as it is written.
    async def _direct(self, reply: Reply, cfg: Any, p: ProviderConfig, flow: flows.Flow, run_dir: Any,
                      req: dict[str, Any], body: dict[str, Any]) -> web.StreamResponse:
        step = flow.steps[0]
        message_file, message_sha = flows.start_run(run_dir, flow, step, req["conversation"])
        if p.gateway == "local":
            base, key = p.base_url, ""
        else:
            try:
                key = load_api_key()
            except Exception:
                key = ""
            base = cfg.base_url
        budget = budget_for(cfg)
        outcome = Outcome(p, ChatResult(_SKIPPED, model=p.model))
        result: dict[str, Any] = {}
        work = asyncio.current_task()
        self.running[reply.run_id] = (work, p)  # type: ignore[assignment]
        watch = asyncio.create_task(self._watch(reply, work, p))  # type: ignore[arg-type]
        try:
            for n, model in enumerate((p.model, *p.fallback_models)):
                if not budget.take(p):
                    outcome.result = ChatResult(_SKIPPED, model=model, error="daily_cap")
                    outcome.notices.append(budget.notice(p))
                    break
                outcome.tried_models.append(model)
                payload = {"model": (p.remote_model or model) if p.gateway == "local" else model,
                           "messages": body.get("messages") or [], "stream": reply.stream,
                           **{k: body[k] for k in DIRECT_KEYS if k in body}}
                lock = server_lock(upstream_key(p.model)) if p.gateway == "local" else contextlib.nullcontext()
                async with lock:
                    outcome.result, result = await self._upstream(reply, base, key, payload, p)
                if outcome.result.ok or result.get("started") or n == len(p.fallback_models):
                    break
                nxt = p.fallback_models[n]
                await reply.say(f"{p.display} ({model}) falló: {outcome.result.error}. Pruebo con {nxt}, "
                                "la reserva que tienes configurada.")
        except asyncio.CancelledError:
            outcome.result = ChatResult(CANCELLED, model=p.model, error="parado por Iván")
            result = {"cancelled": True}
        finally:
            watch.cancel()
            self.running.pop(reply.run_id, None)
        if len(outcome.tried_models) > 1 and outcome.result.ok:
            outcome.notices.append(f"{p.name}: respondió el respaldo {outcome.tried_models[-1]}")
            reply.avisos.append(f"Respondió el respaldo {outcome.tried_models[-1]} en lugar de {p.model} "
                                "(tu reserva configurada).")
        extra = {"tool_calls": result.get("tool_calls")} if result.get("tool_calls") else None
        answer = flows.journal_call(run_dir, reply.run_id, 1, step.id, message_file, message_sha, outcome, "first",
                                    p.name, extra=extra)
        status = flows.OK if answer.ok else flows.FAILED
        flows.close_run(run_dir, reply.run_id, flow.name, status, {step.id: status})
        flows.to_vault(cfg, run_dir)
        self.bridge.app_api._remember({"target": p.name, "code": answer.code, "error": answer.error, "ok": answer.ok})
        for notice in outcome.notices:
            await reply.say(notice)
        if outcome.result.ok and outcome.result.model:  # which model really answered (D21)
            used = outcome.result.model
            reply.avisos.append(f"Respondió {p.display}." if used.rsplit("/", 1)[-1] in p.display
                                else f"Respondió {p.display} con {used}.")
        if not answer.ok:
            if result.get("started"):  # part of the answer was already shown: close it with the reason
                await reply.chunk({"content": f"\n\n({problem_text(answer.code, p.display, answer.error)})"}, "stop",
                                  webllm={"avisos": reply.avisos})
                return await reply.end()
            return await reply.error(answer.code, problem_text(answer.code, p.display, answer.error))
        if not reply.stream:
            return web.json_response({**result.get("body", {}), "webllm": {"avisos": reply.avisos}},
                                     headers={"x-webllm-run": reply.run_id})
        await reply.chunk({}, None, webllm={"avisos": reply.avisos})
        return await reply.end()

    async def _upstream(self, reply: Reply, base: str, key: str, payload: dict[str, Any], p: ProviderConfig
                        ) -> tuple[ChatResult, dict[str, Any]]:
        """One call to the API (or this PC's server); a stream is passed on as it comes."""
        headers = {**auth_headers(key), **(TRANSPARENT_HEADERS if p.gateway == "omniroute" else {})}
        timeout = httpx.Timeout(connect=10.0, read=p.timeout_s, write=30.0, pool=10.0)
        t0 = time.perf_counter()
        info: dict[str, Any] = {"started": False}
        text, calls, served = [], {}, None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{base.rstrip('/')}/chat/completions", json=payload, headers=headers) as r:
                    upstream = r.headers.get("x-omniroute-provider")
                    if r.status_code != 200:
                        excerpt = (await r.aread())[:500].decode("utf-8", "replace")
                        return ChatResult(HTTP_ERROR, http_status=r.status_code, error=f"HTTP {r.status_code}",
                                          body_excerpt=excerpt, latency_s=time.perf_counter() - t0,
                                          upstream_provider=upstream), info
                    if payload["stream"] and "text/event-stream" not in r.headers.get("content-type", ""):
                        # asked to stream, answered with one JSON: pass it on as chunks all the same
                        data = json.loads(await r.aread())
                        message = data["choices"][0]["message"]
                        delta = {k: v for k, v in (("content", message.get("content")),
                                                   ("tool_calls", [{"index": i, **c} for i, c in enumerate(message.get("tool_calls") or [])]))
                                 if v}
                        await reply.chunk(delta)
                        await reply.chunk({}, data["choices"][0].get("finish_reason") or "stop")
                        info["started"] = True
                        if message.get("tool_calls"):
                            info["tool_calls"] = [{"name": c["function"]["name"]} for c in message["tool_calls"]]
                        return ChatResult(OK, text=_content_text(message.get("content")) or "", model=data.get("model"),
                                          latency_s=time.perf_counter() - t0, http_status=200,
                                          upstream_provider=upstream), info
                    if not payload["stream"]:
                        data = json.loads(await r.aread())
                        message = data["choices"][0]["message"]
                        info["body"] = data
                        if message.get("tool_calls"):
                            info["tool_calls"] = [{"name": c["function"]["name"]} for c in message["tool_calls"]]
                        return ChatResult(OK, text=_content_text(message.get("content")) or "", model=data.get("model"),
                                          latency_s=time.perf_counter() - t0, http_status=200,
                                          upstream_provider=upstream), info
                    async for line in r.aiter_lines():
                        if reply.gone():
                            raise asyncio.CancelledError
                        if not line.startswith("data:"):
                            continue
                        if line.strip() == "data: [DONE]":
                            break
                        try:
                            chunk = json.loads(line[5:])
                        except ValueError:
                            continue
                        if chunk.get("error"):
                            err = chunk["error"]
                            return ChatResult(HTTP_ERROR, http_status=int(err.get("code") or 0) if str(err.get("code") or "").isdigit() else None,
                                              error="error a mitad de la respuesta", body_excerpt=json.dumps({"error": err})[:500],
                                              latency_s=time.perf_counter() - t0), info
                        served = served or chunk.get("model")
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if delta.get("content"):
                                text.append(delta["content"])
                            for c in delta.get("tool_calls") or []:
                                slot = calls.setdefault(c.get("index", 0), {"name": "", "arguments": ""})
                                fn = c.get("function") or {}
                                slot["name"] += fn.get("name") or ""
                                slot["arguments"] += fn.get("arguments") or ""
                        info["started"] = True
                        await reply.write(f"{line.strip()}\n\n".encode("utf-8"))
        except httpx.TimeoutException as exc:
            return ChatResult(TIMEOUT, latency_s=time.perf_counter() - t0, error=f"timeout ({type(exc).__name__})"), info
        except httpx.HTTPError as exc:
            return ChatResult(CONNECTION_ERROR, latency_s=time.perf_counter() - t0, error=f"{type(exc).__name__}: {exc}"), info
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return ChatResult(MALFORMED, latency_s=time.perf_counter() - t0, error=f"respuesta mal formada: {exc}"), info
        if calls:
            info["tool_calls"] = [{"name": c["name"]} for c in calls.values()]
        return ChatResult(OK, text="".join(text), model=served or payload["model"], latency_s=time.perf_counter() - t0,
                          http_status=200), info


__all__ = ["Gateway", "decode_files", "RequestError", "MAX_FILE_BYTES", "MAX_FILES_BYTES", "card"]

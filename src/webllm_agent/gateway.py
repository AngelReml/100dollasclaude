"""webllm as the one connection of the face (PLAN-v5 D2): an OpenAI-compatible API under /gw/v1.

Every AI webllm knows is a "model" here: the chat sites in Chrome, the API models (OmniRoute) and
the models on this PC. A question goes through the same engine as the app (flows.run_flow): the
account guard, the journal with its green padlock, the history, the error codes. While it runs,
the answer's thinking block (OpenAI ``reasoning_content``) says what is happening in plain Spanish,
including "te espera" while a chat waits for Iván; SSE comments keep long waits alive.

Webllm's own fields travel in the request body under ``webllm``:
    {"chat_id", "message_id", "task", "files": [{"name", "mime", "data" (base64), "sha256"?}], "modes": [...]}
Files are checked (size, sha256) and recorded in the journal; handing them to the web chats is
phase F4, and until then the answer says so (nothing is silently dropped: D21).
A ``task`` (a title, tags... that Open WebUI generates in the background) never reaches a web chat:
it would spend messages of Iván's accounts.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from . import flows, journal
from .appapi import MAX_PROMPT, site_of
from .broadcaster import GatewayError, new_run_id
from .client import _content_text
from .config import ProviderConfig
from .guard import Guard
from .omniroute import load_api_key
from .problems import WAITING_SHORT, problem_text

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_FILES_BYTES = 100 * 1024 * 1024
HEARTBEAT_S = 10.0
KIND_LABEL = {"bridge": "web", "omniroute": "API", "local": "tu PC"}
DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,(.*)$", re.S)


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
                            "data": hit.group(2)})
        break
    return out


def decode_files(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check the files sent with a question: base64, size limits, and the sha256 when one is given.
    Returns [{"name", "mime", "size", "sha256", "bytes"}] without duplicates (same content)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 0
    for item in items or []:
        if not isinstance(item, dict):
            raise RequestError(400, "bad_file", "Un archivo llegó mal formado.")
        name = str(item.get("name") or "archivo")[:200]
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
                    "size": len(data), "sha256": digest, "bytes": data})
    return out


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB".replace(".", ",") if n >= 1024 * 1024 else f"{max(1, round(n / 1024))} KB"


class Gateway:
    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge

    def register(self, app: web.Application) -> None:
        app.router.add_get("/gw/v1/models", self.models)
        app.router.add_post("/gw/v1/chat/completions", self.chat)

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
        return web.json_response({"object": "list", "data": [{
            "id": p.name, "object": "model", "owned_by": "webllm",
            "name": f"{p.display.removesuffix(' (chat)')} ({KIND_LABEL[p.gateway]})",
            "webllm": {"kind": {"bridge": "chat", "omniroute": "api", "local": "local"}[p.gateway], "label": p.display},
        } for p in providers]})

    # ------------------------------------------------------------------ chat

    async def _prepare(self, body: dict[str, Any]) -> tuple[Any, ProviderConfig, dict[str, Any]]:
        if not isinstance(body, dict):
            raise RequestError(400, "bad_request", "La petición no es un objeto JSON.")
        ext = body.get("webllm") if isinstance(body.get("webllm"), dict) else {}
        cfg = await self.bridge.app_api._cfg()
        name = str(body.get("model") or "")
        p = cfg.providers.get(name)
        if p is None or not p.enabled:
            raise RequestError(404, "model_not_found", f"No conozco esta IA: {name}.")
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
                        "chat_id": str(ext.get("chat_id") or "")[:100], "message_id": str(ext.get("message_id") or "")[:100],
                        "task": str(ext.get("task") or "")[:60]}

    @staticmethod
    def bridge_flatten(messages: list[dict[str, Any]]) -> str:
        from .bridge import flatten_messages  # late: bridge imports this module
        return flatten_messages(messages)

    def _record(self, run_dir: Any, run_id: str, p: ProviderConfig, req: dict[str, Any]) -> None:
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
        })

    def _notes_before(self, p: ProviderConfig, req: dict[str, Any]) -> list[str]:
        notes = []
        for f in req["files"]:
            notes.append(f"Recibido «{f['name']}» ({_size(f['size'])}, huella {f['sha256'][:12]}). "
                         f"Todavía no se lo paso a {p.display}: subir archivos a las IAs llega en la fase F4.")
        if req["modes"]:
            notes.append(f"Pediste: {', '.join(req['modes'])}. Todavía no se activa en {p.display}: llega en la fase F4.")
        return notes

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

        run_id = new_run_id()
        run_dir = cfg.paths.runs_dir / run_id
        flow = flows.Flow(
            name="Desde Open WebUI", template="pregunta",
            inputs={"pregunta": req["question"], "conversacion": req["conversation"], "origen": "Open WebUI",
                    "chat_id": req["chat_id"], "message_id": req["message_id"]},
            steps=(flows.Step(id="respuestas", title="Respuesta", to=(p.name,), message="{{conversacion}}"),))
        try:
            flows.validate(cfg, flow)
        except flows.FlowError as exc:
            return self._error(400, "invalid", str(exc))
        self._record(run_dir, run_id, p, req)

        stream = bool(body.get("stream"))
        cid, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
        resp: web.StreamResponse | None = None
        closed = False
        notes: list[str] = []
        # What Iván must still see when the answer is done (D21: what you see is what was used):
        # files or modes not used yet, a stand-in that answered instead. It travels in the last chunk
        # ("webllm": {"avisos": [...]}); the pipe keeps it on the status line above the answer.
        avisos: list[str] = []

        async def write(data: bytes) -> None:
            nonlocal closed
            if closed or resp is None:
                return
            try:
                await resp.write(data)
            except (ConnectionResetError, RuntimeError):
                closed = True  # the face went away: keep going so the run is complete and journaled

        async def chunk(delta: dict[str, Any], finish: str | None = None) -> None:
            data = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": p.name,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            await write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))

        async def say(text: str) -> None:
            notes.append(text)
            if stream:
                await chunk({"reasoning_content": text + "\n\n"})

        if stream:
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                               "X-Accel-Buffering": "no", "x-webllm-run": run_id})
            await resp.prepare(request)
            await chunk({"role": "assistant"})

        done: dict[str, Any] = {}

        async def emit(ev: dict[str, Any]) -> None:
            t = ev.get("type")
            if t == "target_start":
                await say(f"Preguntando a {ev.get('label')}…")
            elif t == "target_wait":
                await say(f"{ev.get('label')} falló ({ev.get('error')}). Lo intento otra vez en {ev.get('seconds')} s.")
            elif t == "target_fallback":
                await say(f"{ev.get('label')} falló ({ev.get('error')}). Pruebo con {ev.get('provider_label')}, "
                          "la reserva que tienes configurada.")
            elif t == "target_done":
                self.bridge.app_api._remember(ev)
                done.update(ev)

        async def watch_waiting() -> None:
            site, last = site_of(p), None
            while site:
                kind = self.bridge.waiting.get(site)
                if kind != last:
                    if kind in WAITING_SHORT:
                        await say(WAITING_SHORT[kind].format(ai=p.display))
                    elif last:
                        await say("Sigo.")
                    last = kind
                await asyncio.sleep(1.0)

        async def heartbeat() -> None:
            while stream:
                await asyncio.sleep(HEARTBEAT_S)
                await write(b": webllm sigue\n\n")

        for note in self._notes_before(p, req):
            await say(note)
        if req["files"]:
            avisos.append(f"{p.display} no ha visto {'el archivo' if len(req['files']) == 1 else 'los archivos'}: "
                          "pasarlos a las IAs llega en la fase F4.")
        if req["modes"]:
            avisos.append(f"{', '.join(req['modes']).capitalize()}: aún no se activa en {p.display} (fase F4).")
        tasks = [asyncio.create_task(watch_waiting()), asyncio.create_task(heartbeat())]
        try:
            try:
                api_key = load_api_key()
            except Exception:
                api_key = ""
            guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
            await flows.run_flow(cfg, flow, api_key=api_key, guard=guard, bridge_key=self.bridge.token,
                                 emit=emit, run_id=run_id)
        except GatewayError:
            shutil.rmtree(run_dir, ignore_errors=True)  # nothing was sent
            done = {"ok": False, "code": "unreachable", "error": ""}
        finally:
            for t in tasks:
                t.cancel()

        ok = bool(done.get("ok"))
        text = str(done.get("text") or "")
        if ok and done.get("provider") and done.get("provider") != p.name:
            avisos.append(f"Respondió {done.get('provider_label')} en lugar de {p.display} (tu reserva).")
        for notice in done.get("notices") or []:
            await say(str(notice))
        if not ok:
            message = problem_text(str(done.get("code") or "error"), p.display, str(done.get("error") or ""))
        if not stream:
            if not ok:
                return web.json_response({"error": {"message": message, "type": done.get("code") or "error",
                                                    "code": done.get("code") or "error", "run_id": run_id}},
                                         status=502, headers={"x-webllm-run": run_id})
            return web.json_response({
                "id": cid, "object": "chat.completion", "created": created, "model": p.name, "webllm": {"avisos": avisos},
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text,
                                         **({"reasoning_content": "\n\n".join(notes)} if notes else {})}}],
            }, headers={"x-webllm-run": run_id})
        if ok:
            await chunk({"content": text})
            final = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": p.name,
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "webllm": {"avisos": avisos}}
            await write(f"data: {json.dumps(final, ensure_ascii=False)}\n\n".encode("utf-8"))
        else:
            await write(f"data: {json.dumps({'error': {'message': message, 'code': done.get('code') or 'error'}, 'webllm': {'avisos': avisos}}, ensure_ascii=False)}\n\n".encode("utf-8"))
        await write(b"data: [DONE]\n\n")
        if not closed and resp is not None:
            try:
                await resp.write_eof()
            except (ConnectionResetError, RuntimeError):
                pass
        return resp  # type: ignore[return-value]


__all__ = ["Gateway", "decode_files", "RequestError", "MAX_FILE_BYTES", "MAX_FILES_BYTES"]

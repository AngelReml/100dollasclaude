"""
title: webllm
author: webllm (github.com/angelreml/100dollasclaude)
version: 0.1.0
required_open_webui_version: 0.11.0
description: Todas tus IAs de webllm como modelos: los chats de tu Chrome, las IAs por API y las de tu PC. Con el guardián de tus cuentas y el registro de webllm.
"""

# Open WebUI "pipe" function (PLAN-v5 D2): the one connection between Open WebUI and webllm.
# Open WebUI runs this file itself; webllm's installer (scripts/openwebui_setup.py) puts it there.
# - pipes(): every AI webllm knows, from webllm's /gw/v1/models.
# - pipe(): the conversation, the files of THIS message (whole, with their sha256) and the modes
#   switched on in the "+" of the text box go to webllm's /gw/v1/chat/completions; its stream comes
#   back as it is (the thinking block says what webllm is doing, "te espera" included). The same
#   notes also go to Open WebUI's status line, visible without opening the (folded) thinking block,
#   and what Iván must still see at the end (a file not used yet, a stand-in AI) stays there.
# - Open WebUI's own background jobs (a title, tags, follow-up suggestions...) are answered here:
#   they never reach an AI of Iván's accounts.

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, AsyncGenerator

import aiohttp
from pydantic import BaseModel, Field

LOCAL_TASKS = {
    "title_generation", "tags_generation", "follow_up_generation", "emoji_generation",
    "autocomplete_generation", "query_generation", "image_prompt_generation",
}


def last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, list):
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
        return str(c or "").strip()
    return ""


def local_task_answer(task: str, messages: list[dict[str, Any]]) -> str:
    """What Open WebUI expects back from each background job, made here without asking anyone.
    The conversation's own first question is inside the job's prompt; the title uses its first words."""
    text = last_user_text(messages)
    question = text
    if "<chat_history>" in text:  # the job's prompt holds the conversation as "USER: ..." / "ASSISTANT: ..." lines
        history = text.split("<chat_history>", 1)[1].split("</chat_history>", 1)[0]
        asked = [part.split("\nASSISTANT:", 1)[0].strip() for part in history.split("USER: ")[1:]]
        question = asked[0] if asked else ""
    words = question.split()
    if task == "title_generation":
        title = " ".join(words[:6]).strip(" .,:;¿?¡!") or "Conversación"
        return json.dumps({"title": title[:60]}, ensure_ascii=False)
    if task == "tags_generation":
        return json.dumps({"tags": []})
    if task == "follow_up_generation":
        return json.dumps({"follow_ups": []})
    if task == "emoji_generation":
        return "💬"
    if task == "query_generation":
        return json.dumps({"queries": []})
    if task == "autocomplete_generation":
        return json.dumps({"text": ""})
    return ""


class Pipe:
    class Valves(BaseModel):
        WEBLLM_URL: str = Field(default="http://127.0.0.1:20130", description="Dónde está webllm en tu PC.")
        WEBLLM_TOKEN: str = Field(default="", description="La llave de webllm (la pone el instalador).")

    def __init__(self) -> None:
        self.valves = self.Valves()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.valves.WEBLLM_TOKEN}"}

    async def pipes(self) -> list[dict[str, str]]:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(f"{self.valves.WEBLLM_URL}/gw/v1/models", headers=self._headers()) as r:
                    if r.status == 401:
                        return [{"id": "sin-llave", "name": "webllm: falta la llave (vuelve a ejecutar el instalador)"}]
                    data = (await r.json()).get("data", [])
                    return [{"id": m["id"], "name": m.get("name") or m["id"]} for m in data]
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return [{"id": "apagado", "name": "webllm está apagado: ábrelo con su icono"}]

    async def _files(self, metadata: dict[str, Any] | None, files: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """The files of the message being sent (Open WebUI passes every file of the conversation in
        __files__; the message itself is in metadata["user_message"]), read whole from its storage."""
        items = ((metadata or {}).get("user_message") or {}).get("files")
        if items is None:
            items = files or []
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            url = str(it.get("url") or "")
            if url.startswith("data:") and ";base64," in url:
                mime, data = url[5:].split(";base64,", 1)
                raw = base64.b64decode(data)
                out.append({"name": str(it.get("name") or "imagen"), "mime": mime, "data": data,
                            "sha256": hashlib.sha256(raw).hexdigest()})
                continue
            fid = it.get("id") or (it.get("file") or {}).get("id")
            if not fid or it.get("type") not in (None, "file", "image"):
                continue  # a knowledge collection or a web page: not a file of this message
            from open_webui.models.files import Files  # only inside Open WebUI
            from open_webui.storage.provider import Storage
            f = await Files.get_file_by_id(fid)
            if f is None or not f.path:
                continue
            with open(Storage.get_file(f.path), "rb") as fh:
                raw = fh.read()
            meta = f.meta or {}
            out.append({"name": f.filename, "mime": meta.get("content_type") or "application/octet-stream",
                        "data": base64.b64encode(raw).decode(), "sha256": hashlib.sha256(raw).hexdigest()})
        return out

    async def pipe(
        self,
        body: dict[str, Any],
        __metadata__: dict[str, Any] | None = None,
        __files__: list[dict[str, Any]] | None = None,
        __task__: str | None = None,
        __chat_id__: str | None = None,
        __message_id__: str | None = None,
        __event_emitter__: Any = None,
    ) -> Any:
        model = str(body.get("model", "")).split(".", 1)[-1]
        messages = body.get("messages") or []
        if __task__ and str(__task__) in LOCAL_TASKS:
            return local_task_answer(str(__task__), messages)
        if model in ("apagado", "sin-llave"):
            return "webllm no está listo: ábrelo con su icono (o vuelve a ejecutar el instalador) y pregunta otra vez."
        payload = {
            "model": model, "stream": True, "messages": messages,
            "webllm": {"chat_id": __chat_id__ or "", "message_id": __message_id__ or "",
                       "task": str(__task__ or ""), "files": await self._files(__metadata__, __files__),
                       "modes": list(body.get("webllm_modes") or [])},
        }
        if body.get("tools"):
            payload["tools"] = body["tools"]
        if body.get("stream") is False:  # someone asked for the whole answer at once (Open WebUI's API)
            return await self._complete(payload)
        return self._stream(payload, __event_emitter__)

    async def _complete(self, payload: dict[str, Any]) -> Any:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(f"{self.valves.WEBLLM_URL}/gw/v1/chat/completions", json={**payload, "stream": False},
                                  headers=self._headers()) as r:
                    body = await r.json()
        except (aiohttp.ClientError, ValueError):
            return {"error": {"message": "webllm no responde: ábrelo con su icono y pregunta otra vez."}}
        if body.get("error"):
            return {"error": {"message": body["error"].get("message") or "webllm no pudo responder."}}
        return body["choices"][0]["message"].get("content") or ""

    async def _status(self, emitter: Any, text: str, done: bool = False) -> None:
        if emitter is not None:
            await emitter({"type": "status", "data": {"description": text, "done": done, "hidden": done and not text}})

    async def _stream(self, payload: dict[str, Any], emitter: Any = None) -> AsyncGenerator[Any, None]:
        # No time limit here: webllm keeps the line alive and decides when a chat has taken too long
        # (a verification can make Iván take minutes).
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None)
        avisos: list[str] = []
        try:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(f"{self.valves.WEBLLM_URL}/gw/v1/chat/completions", json=payload,
                                  headers=self._headers()) as r:
                    if r.content_type == "application/json":
                        err = (await r.json()).get("error") or {}
                        yield {"error": {"message": err.get("message") or f"webllm respondió {r.status}"}}
                        return
                    buffer = b""
                    async for piece in r.content.iter_any():  # answers can be long: no line-size limit
                        buffer += piece
                        while b"\n" in buffer:
                            raw, buffer = buffer.split(b"\n", 1)
                            line = raw.decode("utf-8").strip()
                            if not line.startswith("data:") or line == "data: [DONE]":
                                continue  # keep-alive comments; Open WebUI adds its own end
                            data, choice = {}, {}
                            try:
                                data = json.loads(line[5:])
                                avisos += [str(x) for x in (data.get("webllm") or {}).get("avisos") or []]
                                choice = data["choices"][0]
                            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                                pass
                            if not isinstance(data, dict):
                                continue  # a broken line: nothing for Open WebUI
                            if data.get("error"):
                                yield line  # Open WebUI shows it and keeps it in the conversation
                                continue
                            if not isinstance(choice, dict) or not choice:
                                continue  # not an answer chunk
                            delta = choice.get("delta") or {}
                            if delta.get("reasoning_content"):
                                await self._status(emitter, delta["reasoning_content"].strip())
                            elif delta.get("content"):
                                await self._status(emitter, "", done=True)
                            if data.get("webllm") and not delta and not choice.get("finish_reason"):
                                continue  # webllm's own last word (what to keep on view), nothing for the answer
                            yield line
        except aiohttp.ClientError:
            yield {"error": {"message": "webllm no responde: ábrelo con su icono y pregunta otra vez."}}
        finally:
            await self._status(emitter, " ".join(avisos), done=True)

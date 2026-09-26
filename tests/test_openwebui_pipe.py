"""openwebui/webllm_pipe.py (the function Open WebUI runs) against a fake webllm: what it sends, what it
answers by itself, and what it shows. Reading files from Open WebUI's storage is checked on the real
screen (tests/openwebui/f1_checks.mjs, check 12)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

pytest.importorskip("pydantic")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "openwebui"))
import webllm_pipe  # noqa: E402

TITLE_JOB = [{"role": "user", "content": "### Task:\nGenera un título.\n<chat_history>\nUSER: ¿Qué es la inflación y "
              "por qué sube tanto?\nASSISTANT: La inflación es la subida de los precios.\n</chat_history>"}]


class FakeWebllm:
    def __init__(self, token="llave", down=False):
        self.token, self.requests = token, []
        self.app = web.Application()
        self.app.router.add_get("/gw/v1/models", self.models)
        self.app.router.add_post("/gw/v1/chat/completions", self.chat)

    async def models(self, request):
        if request.headers.get("Authorization") != f"Bearer {self.token}":
            return web.json_response({"error": {}}, status=401)
        return web.json_response({"data": [{"id": "qwen", "name": "Qwen (web)"}, {"id": "zai", "name": "z.ai (API)"}]})

    async def chat(self, request):
        self.requests.append(await request.json())
        if self.requests[-1].get("stream") is False:
            return web.json_response({"choices": [{"message": {"role": "assistant", "content": "respuesta entera"}}]})
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await resp.prepare(request)
        chunk = lambda delta, **extra: f"data: {json.dumps({'choices': [{'delta': delta}], **extra})}\n\n".encode()
        await resp.write(chunk({"reasoning_content": "Preguntando a Qwen…\n\n"}))
        await resp.write(b": webllm sigue\n\n")
        await resp.write(chunk({"content": "x" * 200_000}))  # a long answer in one line
        await resp.write(b"data: esto no es json\n\n")  # a broken line must not break the answer
        await resp.write(chunk({}, webllm={"avisos": ["Qwen no ha visto el archivo."]}))
        await resp.write(b"data: [DONE]\n\n")
        return resp


async def with_webllm(fake, fn):
    server = TestServer(fake.app)
    await server.start_server()
    try:
        pipe = webllm_pipe.Pipe()
        pipe.valves.WEBLLM_URL = str(server.make_url("")).rstrip("/")
        pipe.valves.WEBLLM_TOKEN = "llave"
        return await fn(pipe)
    finally:
        await server.close()


def run(coro):
    return asyncio.run(coro)


def test_open_webui_background_jobs_are_answered_here_without_asking_anyone():
    fake = FakeWebllm()

    async def go(pipe):
        title = await pipe.pipe({"model": "webllm.qwen", "messages": TITLE_JOB}, __task__="title_generation")
        follow = await pipe.pipe({"model": "webllm.qwen", "messages": TITLE_JOB}, __task__="follow_up_generation")
        return title, follow

    title, follow = run(with_webllm(fake, go))
    assert json.loads(title) == {"title": "Qué es la inflación y por"} and json.loads(follow) == {"follow_ups": []}
    assert fake.requests == []


def test_a_question_carries_the_conversation_files_modes_and_ids_and_streams_back():
    fake = FakeWebllm()
    png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 50
    statuses = []

    async def emitter(event):
        statuses.append(event["data"])

    async def go(pipe):
        body = {"model": "webllm.qwen", "messages": [{"role": "user", "content": "¿Qué ves?"}], "webllm_modes": ["pensar"]}
        meta = {"user_message": {"files": [{"type": "image", "name": "foto.png",
                                            "url": "data:image/png;base64," + base64.b64encode(png).decode()}]}}
        gen = await pipe.pipe(body, __metadata__=meta, __files__=[{"id": "otro-de-antes"}], __chat_id__="c-1",
                              __message_id__="m-1", __event_emitter__=emitter)
        return [line async for line in gen]

    lines = run(with_webllm(fake, go))
    sent = fake.requests[0]
    assert sent["model"] == "qwen" and sent["messages"][0]["content"] == "¿Qué ves?"
    assert sent["webllm"]["chat_id"] == "c-1" and sent["webllm"]["modes"] == ["pensar"]
    assert [(f["name"], f["sha256"]) for f in sent["webllm"]["files"]] == [("foto.png", hashlib.sha256(png).hexdigest())]
    assert all(line.startswith("data:") and "[DONE]" not in line for line in lines)  # no keep-alives, no double end
    # webllm's last word (its avisos) is not part of the answer: it goes to the status line only; a broken
    # line is dropped
    assert len(lines) == 2 and len(json.loads(lines[1][5:])["choices"][0]["delta"]["content"]) == 200_000
    assert not any("avisos" in line or "no es json" in line for line in lines)
    assert statuses[0] == {"description": "Preguntando a Qwen…", "done": False, "hidden": False}
    assert statuses[-1] == {"description": "Qwen no ha visto el archivo.", "done": True, "hidden": False}


def test_an_error_in_the_middle_of_the_answer_reaches_open_webui():
    """webllm streams a failure as `data: {"error": ...}` (no choices); Open WebUI shows that and keeps it in
    the conversation, so the pipe must pass it on, and the avisos still stay on view."""
    class Failing(FakeWebllm):
        async def chat(self, request):
            self.requests.append(await request.json())
            resp = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
            await resp.prepare(request)
            await resp.write(b'data: {"choices": [{"delta": {"reasoning_content": "Preguntando a Qwen\u2026"}}]}\n\n')
            await resp.write(('data: ' + json.dumps({"error": {"message": "Lo has parado tú.", "code": "cancelled"},
                                                      "webllm": {"avisos": ["Qwen no ha visto el archivo."]}}) + "\n\n").encode())
            await resp.write(b"data: [DONE]\n\n")
            return resp

    statuses = []

    async def emitter(event):
        statuses.append(event["data"])

    async def go(pipe):
        gen = await pipe.pipe({"model": "webllm.qwen", "messages": [{"role": "user", "content": "hola"}]},
                              __event_emitter__=emitter)
        return [line async for line in gen]

    lines = run(with_webllm(Failing(), go))
    assert len(lines) == 2 and json.loads(lines[1][5:])["error"]["message"] == "Lo has parado tú."
    assert statuses[-1] == {"description": "Qwen no ha visto el archivo.", "done": True, "hidden": False}


def test_the_model_list_says_when_webllm_is_off_or_the_key_is_wrong():
    async def listed(token):
        fake = FakeWebllm(token=token)
        return await with_webllm(fake, lambda pipe: pipe.pipes())

    assert [m["name"] for m in run(listed("llave"))] == ["Qwen (web)", "z.ai (API)"]
    assert run(listed("otra"))[0]["id"] == "sin-llave"
    pipe = webllm_pipe.Pipe()
    pipe.valves.WEBLLM_URL = "http://127.0.0.1:9"
    assert run(pipe.pipes())[0]["id"] == "apagado"


def test_asked_for_the_whole_answer_at_once_it_returns_the_text_not_the_stream():
    fake = FakeWebllm()

    async def go(pipe):
        return await pipe.pipe({"model": "webllm.zai", "stream": False, "messages": [{"role": "user", "content": "hola"}]})

    assert run(with_webllm(fake, go)) == "respuesta entera"
    assert fake.requests[0]["stream"] is False


def test_the_conversation_title_and_its_open_webui_folder_travel_with_the_question(monkeypatch):
    """PLAN-v5 F5: Open WebUI's folder is the project in Obsidian; read with Open WebUI's own functions."""
    import types

    class Chats:
        @staticmethod
        async def get_chat_title_by_id(chat_id):
            return {"c-1": "Precios y dinero", "c-2": "New Chat"}.get(chat_id)

        @staticmethod
        async def get_chat_folder_id(chat_id, user_id):
            return "f-1" if (chat_id, user_id) == ("c-1", "u-1") else None

    class Folders:
        @staticmethod
        async def get_folder_by_id_and_user_id(folder_id, user_id):
            return types.SimpleNamespace(name="Clientes 2026") if (folder_id, user_id) == ("f-1", "u-1") else None

    for name, attrs in (("open_webui", {}), ("open_webui.models", {}), ("open_webui.models.chats", {"Chats": Chats}),
                        ("open_webui.models.folders", {"Folders": Folders})):
        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(**attrs))
    fake = FakeWebllm()

    async def go(pipe):
        body = {"model": "webllm.qwen", "messages": [{"role": "user", "content": "hola"}]}
        for chat_id in ("c-1", "c-2", "local:x"):
            gen = await pipe.pipe(dict(body), __chat_id__=chat_id, __user__={"id": "u-1"})
            [line async for line in gen]

    run(with_webllm(fake, go))
    got = [{k: r["webllm"].get(k) for k in ("title", "project")} for r in fake.requests]
    assert got == [{"title": "Precios y dinero", "project": "Clientes 2026"}, {"title": "New Chat", "project": None},
                   {"title": None, "project": None}]

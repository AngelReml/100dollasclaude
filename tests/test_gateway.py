"""The gateway (PLAN-v5 F1/F2): webllm as the one OpenAI-compatible connection of Open WebUI.
The real bridge in-process, a fake Chrome extension over a real WebSocket and the mock OmniRoute."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from pathlib import Path

from test_appapi import AUTH, App, run
from test_bridge import WaitingExtension
from webllm_agent import problems
from webllm_agent.broadcaster import verify_run

ROOT = Path(__file__).resolve().parents[1]


async def gw(app: App, body: dict, headers=AUTH) -> tuple[int, list, dict]:
    """POST /gw/v1/chat/completions; for a stream, every data line (the JSON ones parsed)."""
    async with app.http.post(app.url("/gw/v1/chat/completions"), json=body, headers=headers) as r:
        if r.content_type == "application/json":
            return r.status, [await r.json()], dict(r.headers)
        lines = []
        async for raw in r.content:
            line = raw.decode("utf-8").strip()
            if line.startswith("data: "):
                lines.append(line[6:] if line[6:] == "[DONE]" else json.loads(line[6:]))
        return r.status, lines, dict(r.headers)


def reasoning(lines: list) -> str:
    return "".join(x["choices"][0]["delta"].get("reasoning_content", "") for x in lines
                   if isinstance(x, dict) and x.get("choices"))


def content(lines: list) -> str:
    return "".join(x["choices"][0]["delta"].get("content", "") or "" for x in lines
                   if isinstance(x, dict) and x.get("choices"))


def journal_lines(app: App, run_id: str) -> list[dict]:
    path = app.cfg.paths.runs_dir / run_id / "journal.jsonl"
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def ask(model: str, text: str = "¿Qué es la inflación?", **webllm) -> dict:
    return {"model": model, "stream": True, "messages": [{"role": "user", "content": text}],
            **({"webllm": webllm} if webllm else {})}


# ------------------------------------------------------------------ models

def test_models_are_every_ai_with_a_spanish_name(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            status, _, _ = await app.get("/gw/v1/models", headers={})
            assert status == 401
            status, body, _ = await app.get("/gw/v1/models")
            assert status == 200
            got = {m["id"]: (m["name"], m["webllm"]["kind"]) for m in body["data"]}
            assert got["qwen"] == ("Qwen (web)", "chat") and got["zai"][1] == "api" and got["zai"][0].endswith("(API)")
            kinds = [m["webllm"]["kind"] for m in body["data"]]
            assert kinds == sorted(kinds, key=["chat", "api", "local"].index)  # chats, then APIs, then this PC
    run(go())


# -------------------------------------------------------------------- chat

def test_a_question_to_a_web_chat_streams_notes_then_the_answer_and_is_journaled(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            body = {"model": "qwen", "stream": True, "webllm": {"chat_id": "chat-1", "message_id": "m-1"},
                    "messages": [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola, ¿qué tal?"},
                                 {"role": "user", "content": "¿Qué es la inflación?"}]}
            status, lines, headers = await gw(app, body)
            assert status == 200 and lines[-1] == "[DONE]"
            assert "Preguntando a Qwen" in reasoning(lines) and content(lines) == "answer from qwen"
            assert lines[-2]["choices"][0]["finish_reason"] == "stop"
            # the web chat got the whole conversation, the history shows the last question
            assert "=== ASSISTANT" in app.ext.jobs[0]["prompt"] and app.ext.jobs[0]["prompt"].rstrip().endswith("SYSTEM INSTRUCTIONS.")
            run_id = headers["x-webllm-run"]
            first = journal_lines(app, run_id)[0]
            assert first["kind"] == "gateway" and first["chat_id"] == "chat-1" and first["origin"] == "open-webui"
            assert verify_run(app.cfg.paths.runs_dir / run_id).ok
            status, hist, _ = await app.get(f"/api/historial/{run_id}")
            assert status == 200 and hist["title"] == "Desde Open WebUI" and hist["text"] == "¿Qué es la inflación?"
    run(go())


def test_a_question_to_an_api_model_without_stream(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            status, [body], _ = await gw(app, {**ask("zai"), "stream": False})
            assert status == 200 and body["choices"][0]["message"]["content"]
            assert "Preguntando a" in body["choices"][0]["message"]["reasoning_content"]
    run(go())


def test_open_webui_background_tasks_never_spend_web_chat_messages(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            status, [body], _ = await gw(app, ask("qwen", "Genera un título", task="title_generation"))
            assert status == 400 and body["error"]["code"] == "task_for_web_chat"
            assert app.ext.jobs == [] and not any(app.cfg.paths.runs_dir.glob("*"))
            status, _, _ = await gw(app, {**ask("zai", task="title_generation"), "stream": False})
            assert status == 200  # an API model may do it (no account spent)
    run(go())


def test_an_error_explains_itself_in_spanish_with_what_the_service_said(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            app.cfg.providers["zai"] = type(app.cfg.providers["zai"])(name="zai", model="z/r429")
            status, lines, _ = await gw(app, ask("zai"))
            err = next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]
            assert err["code"] == "rate_limited" and "ha llegado a su límite" in err["message"]
            assert "Lo que respondió" in err["message"] and lines[-1] == "[DONE]"
    run(go())


def test_unknown_model_and_empty_message(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            assert (await gw(app, ask("nadie")))[0] == 404
            assert (await gw(app, ask("qwen", "   ")))[0] == 400
            assert (await gw(app, ask("qwen"), headers={}))[0] == 401
            assert app.ext.jobs == []
    run(go())


# ----------------------------------------------------------------- waiting

class SlowAfterWaiting(WaitingExtension):
    """Iván solves the verification, then the chat still takes 1.5 s to write the answer."""

    async def _answer(self, job):
        for _ in range(self.beats):
            await self.ws.send_json({"type": "job_alive", "id": job["id"], "site": job["site"], "waiting": "challenge"})
            await asyncio.sleep(0.2)
        await self.ws.send_json({"type": "job_alive", "id": job["id"], "site": job["site"], "waiting": None})
        await asyncio.sleep(1.5)
        await self.ws.send_json({"type": "result", "id": job["id"], **self.answer})


def test_while_a_chat_waits_for_ivan_the_thinking_block_says_so(tmp_path, mock_server):
    class WaitingApp(App):
        async def __aenter__(self):
            await super().__aenter__()
            await self.ext.close()
            self.ext = SlowAfterWaiting(beats=8, answer={"ok": True, "text": "después de la verificación", "via": "copy-button"})
            await self.ext.connect(self.server)
            await asyncio.sleep(0.2)
            return self

    async def go():
        async with WaitingApp(tmp_path, mock_server.base_url) as app:
            status, lines, _ = await gw(app, ask("qwen"))
            text = reasoning(lines)
            assert problems.WAITING_SHORT["challenge"].format(ai="Qwen") in text and "Sigo." in text
            assert text.index("te espera") < text.index("Sigo.")
            assert all(len(v.format(ai="DeepSeek")) <= 95 for v in problems.WAITING_SHORT.values())  # one line
            assert content(lines) == "después de la verificación"
    run(go())


# ------------------------------------------------------------------- files

def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_files_arrive_whole_are_hashed_and_the_answer_says_they_are_not_used_yet(tmp_path, mock_server):
    pdf = b"%PDF-1.4\n" + bytes(range(256)) * 300
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000

    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            body = ask("qwen", files=[{"name": "informe.pdf", "mime": "application/pdf", "data": b64(pdf),
                                       "sha256": hashlib.sha256(pdf).hexdigest()}], modes=["pensar"])
            body["messages"] = [{"role": "user", "content": [
                {"type": "text", "text": "¿Qué dice?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(png)}}]}]
            status, lines, headers = await gw(app, body)
            assert status == 200 and content(lines) == "answer from qwen"
            notes = reasoning(lines)
            assert "Recibido «informe.pdf»" in notes and "Todavía no se lo paso a Qwen" in notes and "pensar" in notes
            avisos = next(x for x in lines if isinstance(x, dict) and x.get("webllm"))["webllm"]["avisos"]
            assert avisos == ["Qwen no ha visto los archivos: pasarlos a las IAs llega en la fase F4.",
                              "Pensar: aún no se activa en Qwen (fase F4)."]
            assert "data:image" not in app.ext.jobs[0]["prompt"]  # the picture is a file, not text
            run_dir = app.cfg.paths.runs_dir / headers["x-webllm-run"]
            files = journal_lines(app, headers["x-webllm-run"])[0]["files"]
            assert [(f["name"], f["sha256"]) for f in files] == [
                ("informe.pdf", hashlib.sha256(pdf).hexdigest()), ("imagen-2.png", hashlib.sha256(png).hexdigest())]
            assert (run_dir / files[0]["file"]).read_bytes() == pdf
            assert verify_run(run_dir).ok
            (run_dir / files[0]["file"]).write_bytes(pdf + b"x")  # someone changes the saved file
            assert not verify_run(run_dir).ok
    run(go())


def test_a_file_changed_on_the_way_is_refused_and_nothing_is_sent(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            body = ask("qwen", files=[{"name": "a.txt", "data": b64(b"hola"), "sha256": "0" * 64}])
            status, [err], _ = await gw(app, body)
            assert status == 400 and err["error"]["code"] == "bad_file"
            status, [err], _ = await gw(app, ask("qwen", files=[{"name": "b.txt", "data": "no es base64!"}]))
            assert status == 400 and app.ext.jobs == []
    run(go())


# --------------------------------------------------------- texts in Spanish

def test_every_code_the_app_explains_is_explained_through_the_gateway_too():
    fix = (ROOT / "app" / "src" / "fix.ts").read_text("utf-8")
    codes = set(re.findall(r'case "([a-z_]+)":', fix))
    assert codes and codes <= set(problems.PROBLEMS), sorted(codes - set(problems.PROBLEMS))

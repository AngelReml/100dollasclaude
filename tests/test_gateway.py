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


def test_open_webui_and_the_app_show_the_same_daily_numbers(tmp_path, mock_server):
    """A chat site: its account guard's cap and count; an AI by API: its budget. Same numbers in both faces."""
    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            await gw(app, ask("qwen"))
            await gw(app, ask("zai"))
            _, models, _ = await app.get("/gw/v1/models")
            _, estado, _ = await app.get("/api/estado")
            face = {m["id"]: (m["webllm"]["used_today"], m["webllm"]["daily_cap"]) for m in models["data"]}
            panel = {a["name"]: (a["today"], a["cap"]) for a in estado["ais"]}
            assert face["qwen"] == panel["qwen"] == (1, app.cfg.guard.daily_cap)
            assert face["zai"] == panel["zai"] == (1, app.cfg.guard.api_daily_cap)
            card = {m["id"]: m["webllm"]["card"] for m in models["data"]}
            assert f"como mucho {app.cfg.guard.daily_cap} al día" in card["qwen"]
            assert f"como mucho {app.cfg.guard.api_daily_cap} preguntas al día" in card["zai"]
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
            assert status == 200 and body["choices"][0]["message"]["content"] == "answer from z/ok"
            assert body["webllm"]["avisos"] == ["Respondió z.ai con z/ok."]  # which model really answered (D21)
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


def test_a_long_answer_keeps_the_line_alive(tmp_path, mock_server, monkeypatch):
    """A chat that takes long: webllm sends keep-alive comments so nothing on the way hangs up, and they are
    not part of the answer (SSE comments)."""
    from webllm_agent import gateway
    monkeypatch.setattr(gateway, "HEARTBEAT_S", 0.2)

    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            raw = b""
            async with app.http.post(app.url("/gw/v1/chat/completions"), json=ask("qwen"), headers=AUTH) as r:
                async def read():
                    nonlocal raw
                    async for piece in r.content.iter_any():
                        raw += piece
                reading = asyncio.create_task(read())
                await asyncio.sleep(1.0)  # the chat says nothing for a while
                app.bridge.cancel("qwen")  # then it ends
                await asyncio.wait_for(reading, 10)
            text = raw.decode("utf-8")
            assert text.count(": webllm sigue\n\n") >= 3
            assert not [x for x in text.split("\n\n") if x.startswith("data:") and "webllm sigue" in x]
    run(go())


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
            assert avisos == ["Qwen no ha visto «informe.pdf», «imagen-2.png»: pasar archivos a las IAs llega en la fase F4.",
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
    gateway_only = {"task_for_web_chat"}  # only Open WebUI asks for internal tasks
    assert set(problems.PROBLEMS) - gateway_only <= codes, sorted(set(problems.PROBLEMS) - gateway_only - codes)



# ------------------------------------------------------- APIs, directly (F2)

def api_app(tmp_path, mock_server, *providers):
    """The App fixture with other API providers (the mock picks its behaviour from the model id)."""
    class A(App):
        async def __aenter__(self):
            await super().__aenter__()
            for p in providers:
                self.cfg.providers[p.name] = p
            return self
    return A(tmp_path, mock_server.base_url)


def P(name, model, **kw):
    from webllm_agent.config import ProviderConfig
    return ProviderConfig(name=name, model=model, **kw)


def test_an_api_answer_streams_as_it_is_written_and_is_journaled(tmp_path, mock_server):
    async def go():
        async with api_app(tmp_path, mock_server, P("rapida", "x/ok")) as app:
            status, lines, headers = await gw(app, ask("rapida", "hola"))
            pieces = [x["choices"][0]["delta"]["content"] for x in lines
                      if isinstance(x, dict) and x.get("choices") and x["choices"][0]["delta"].get("content")]
            assert status == 200 and len(pieces) >= 3 and "".join(pieces) == "answer from x/ok"
            assert lines[-1] == "[DONE]" and not reasoning(lines)  # a fast API: no notes, just the answer
            last = [x for x in lines if isinstance(x, dict) and x.get("webllm")][-1]
            assert last["webllm"]["avisos"] == ["Respondió rapida con x/ok."]
            run_dir = app.cfg.paths.runs_dir / headers["x-webllm-run"]
            assert verify_run(run_dir).ok
            status, hist, _ = await app.get(f"/api/historial/{headers['x-webllm-run']}")
            assert hist["steps"][0]["answers"][0]["text"] == "answer from x/ok"
            sent = mock_server.requests[-1]["body"]
            assert sent["stream"] is True and sent["messages"] == [{"role": "user", "content": "hola"}]
    run(go())


def test_tools_go_to_the_api_as_they_came_and_its_tool_calls_come_back(tmp_path, mock_server):
    tool = {"type": "function", "function": {"name": "hora", "description": "La hora", "parameters": {"type": "object"}}}

    async def go():
        async with api_app(tmp_path, mock_server, P("conherramientas", "x/tools")) as app:
            status, lines, headers = await gw(app, {**ask("conherramientas", "¿qué hora es?"), "tools": [tool]})
            calls = [c for x in lines if isinstance(x, dict) and x.get("choices")
                     for c in x["choices"][0]["delta"].get("tool_calls") or []]
            assert calls[0]["function"]["name"] == "hora" and mock_server.requests[-1]["body"]["tools"] == [tool]
            assert journal_lines(app, headers["x-webllm-run"])[1]["tool_calls"] == [{"name": "hora"}]
            # the face runs the tool (after Iván allows it) and asks again with its result
            follow = {**ask("conherramientas"), "tools": [tool], "messages": [
                {"role": "user", "content": "¿qué hora es?"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function",
                                                                        "function": {"name": "hora", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": "son las 10:30"}]}
            status, lines, _ = await gw(app, follow)
            assert content(lines) == "La herramienta dijo: son las 10:30"
    run(go())


def test_a_configured_stand_in_answers_and_the_answer_says_so(tmp_path, mock_server):
    async def go():
        async with api_app(tmp_path, mock_server, P("conreserva", "x/r503", fallback_models=("x/ok2",))) as app:
            status, lines, _ = await gw(app, ask("conreserva"))
            assert content(lines) == "answer from x/ok2"
            assert "Pruebo con x/ok2" in reasoning(lines)
            avisos = [x for x in lines if isinstance(x, dict) and x.get("webllm")][-1]["webllm"]["avisos"]
            assert "Respondió el respaldo x/ok2 en lugar de x/r503 (tu reserva configurada)." in avisos
    run(go())


def test_a_failing_ai_is_never_swapped_for_another_on_its_own(tmp_path, mock_server):
    """D21: with no stand-in configured by Iván, a failure is said, and no other AI or model is asked."""
    async def go():
        async with api_app(tmp_path, mock_server, P("caida", "x/r503")) as app:
            app.ext.behaviour["qwen"] = {"ok": False, "error": "site_busy"}
            status, lines, _ = await gw(app, ask("caida"))
            assert next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]["code"] == "overloaded"
            status, lines, _ = await gw(app, ask("qwen"))
            assert next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]["code"] == "site_busy"
            assert [r["model"] for r in mock_server.requests] == ["x/r503"]  # that one, once, nothing else
            assert [j["site"] for j in app.ext.jobs] == ["qwen"]
    run(go())


def test_over_its_daily_cap_an_api_is_not_called_and_the_reason_is_in_spanish(tmp_path, mock_server):
    async def go():
        async with api_app(tmp_path, mock_server, P("tope", "x/ok", daily_cap=1)) as app:
            assert content((await gw(app, ask("tope")))[1]) == "answer from x/ok"
            status, lines, _ = await gw(app, ask("tope"))
            err = next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]
            assert err["code"] == "daily_cap" and "ya ha gastado" in err["message"]
            assert mock_server.calls("x/ok") == 1
            _, models, _ = await app.get("/gw/v1/models")
            tope = next(m for m in models["data"] if m["id"] == "tope")["webllm"]
            assert tope["daily_cap"] == 1 and tope["used_today"] == 1 and "como mucho 1 preguntas" in tope["card"]
    run(go())


# ------------------------------------------------------------------ stop

def test_parar_todo_stops_a_web_chat_and_its_job_in_chrome(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            asking = asyncio.create_task(gw(app, ask("qwen")))
            for _ in range(50):
                await asyncio.sleep(0.1)
                if app.bridge.jobs.get("qwen"):
                    break
            job_id = app.bridge.jobs["qwen"][0]
            status, stopped = await app.post("/gw/v1/parar", {})
            assert status == 200 and stopped["parados"] == 1 and stopped["chats"] == ["qwen"]
            status, lines, headers = await asyncio.wait_for(asking, 10)
            err = next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]
            assert err["code"] == "cancelled" and "Lo has parado tú" in err["message"]
            await asyncio.sleep(0.3)
            assert [m for m in app.ext.seen if m["type"] == "cancel"] == [{"type": "cancel", "id": job_id, "site": "qwen"}]
            lines = journal_lines(app, headers["x-webllm-run"])
            assert [x["kind"] for x in lines] == ["gateway", "flow", "flow_end"] and lines[1]["code"] == "cancelled"
            assert verify_run(app.cfg.paths.runs_dir / headers["x-webllm-run"]).ok
    run(go())


def test_parar_todo_also_stops_the_apps_own_questions(tmp_path, mock_server, monkeypatch):
    """A question from webllm's app (not Open WebUI) to a chat site and to a slow API AI: "Parar todo" ends
    both at once, tells Chrome to stop, and the question's record still closes and verifies."""
    import test_appapi
    from webllm_agent.config import ProviderConfig
    monkeypatch.setattr(test_appapi, "providers", lambda: [
        ProviderConfig(name="qwen", model="browser/qwen", kind="browser", gateway="bridge"),
        ProviderConfig(name="lenta", model="z/slow")])

    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            asking = asyncio.create_task(app.ask("¿Qué es la inflación?", ["qwen", "lenta"]))
            for _ in range(50):
                await asyncio.sleep(0.1)
                if app.bridge.jobs.get("qwen") and any(r["model"] == "z/slow" for r in mock_server.requests):
                    break
            job_id = app.bridge.jobs["qwen"][0]
            status, stopped = await app.post("/gw/v1/parar", {})
            assert status == 200 and stopped == {"parados": 1, "chats": ["qwen"]}
            status, events = await asyncio.wait_for(asking, 1.5)  # the slow AI takes 2 s: not waited for
            done = {e["target"]: e["code"] for e in events if e["type"] == "target_done"}
            assert done == {"qwen": "cancelled", "lenta": "cancelled"}
            flow_done = next(e for e in events if e["type"] == "flow_done")
            assert flow_done["verified"] and verify_run(app.cfg.paths.runs_dir / flow_done["run_id"]).ok
            await asyncio.sleep(0.3)
            assert [m for m in app.ext.seen if m["type"] == "cancel"] == [{"type": "cancel", "id": job_id, "site": "qwen"}]
            assert not app.bridge.app_api.asking and not app.bridge.stopped
            status, again = await app.post("/gw/v1/parar", {})
            assert again == {"parados": 0, "chats": []}  # nothing left in progress
    run(go())


def test_closing_the_answer_in_the_face_stops_the_work(tmp_path, mock_server):
    """Open WebUI's stop button closes the connection: the chat job in Chrome must stop too."""
    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            async with app.http.post(app.url("/gw/v1/chat/completions"), json=ask("qwen"), headers=AUTH) as r:
                await r.content.readline()  # the answer has started
                for _ in range(50):
                    await asyncio.sleep(0.1)
                    if app.bridge.jobs.get("qwen"):
                        break
                job_id = app.bridge.jobs["qwen"][0]
            # leaving the block closed the connection, as the stop button does
            for _ in range(50):
                await asyncio.sleep(0.1)
                if any(m.get("type") == "cancel" for m in app.ext.seen):
                    break
            assert {"type": "cancel", "id": job_id, "site": "qwen"} in app.ext.seen
            assert not app.bridge.jobs and not app.bridge.app_api.bridge.gateway.running
    run(go())



def test_a_question_stopped_while_waiting_its_turn_is_never_sent(tmp_path, mock_server):
    """Two conversations ask Qwen; the second waits its turn. Stopping it must not send it later, and must not
    touch the first one's job."""
    async def go():
        async with App(tmp_path, mock_server.base_url, behaviour={"qwen": "silent"}) as app:
            first = asyncio.create_task(gw(app, ask("qwen", "primera")))
            for _ in range(50):
                await asyncio.sleep(0.1)
                if app.bridge.jobs.get("qwen"):
                    break
            first_job = app.bridge.jobs["qwen"]
            async with app.http.post(app.url("/gw/v1/chat/completions"), json=ask("qwen", "segunda"), headers=AUTH) as r:
                await r.content.readline()
                await asyncio.sleep(0.5)  # queued behind the first
            await asyncio.sleep(0.5)
            assert app.bridge.jobs.get("qwen") == first_job  # the first one's job untouched
            assert not any(m.get("type") == "cancel" for m in app.ext.seen)
            app.bridge.cancel("qwen")  # the first one ends (as if it answered)
            await asyncio.wait_for(first, 10)
            await asyncio.sleep(1.0)
            assert [m["prompt"] for m in app.ext.seen if m["type"] == "job"] == ["primera"]  # the second never went out
    run(go())

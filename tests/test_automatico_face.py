"""PLAN-v5 F8: "webllm · Automático" through the real gateway (the Committee's test world: the real bridge, a fake
Chrome extension that keeps each web conversation, a fake OpenAI-style API that records what it gets)."""

from __future__ import annotations

import base64
import hashlib
import json

from aiohttp import web

from test_appapi import run
from test_committee import Committee, FakeAPI, jobs_of
from test_gateway import content, gw, journal_lines
from webllm_agent import automatico, committee

GROQ = "groq/openai/gpt-oss-120b"


def body(*turns: str, stream: bool = True, files=None, chat_id: str = "c-1") -> dict:
    """Open WebUI's request: Iván's turns, and in between what was answered (as given)."""
    messages = []
    for t in turns:
        if isinstance(t, tuple):
            messages.append({"role": "assistant", "content": t[0]})
        else:
            messages.append({"role": "user", "content": t})
    return {"model": automatico.MODEL_ID, "stream": stream, "messages": messages,
            "webllm": {"chat_id": chat_id, "message_id": f"m-{len(messages)}", **({"files": files} if files else {})}}


def a_file(name: str, mime: str, data: bytes) -> dict:
    return {"name": name, "mime": mime, "data": base64.b64encode(data).decode(), "sha256": hashlib.sha256(data).hexdigest()}


def run_id_of(headers: dict) -> str:
    return headers.get("x-webllm-run") or headers.get("X-Webllm-Run") or ""


def test_automatico_is_a_model_after_the_web_chats_and_never_the_first(tmp_path):
    async def go():
        async with Committee(tmp_path) as app:
            status, got, _ = await app.get("/gw/v1/models")
            data = got["data"]
            ids = [m["id"] for m in data]
            assert ids.index("automatico") == ids.index("comite") + 1 and ids[0] not in ("comite", "automatico")
            entry = data[ids.index("automatico")]
            assert entry["name"] == "webllm · Automático" and "primera línea" in entry["webllm"]["card"]
    run(go())


def test_a_question_goes_to_the_first_available_ai_and_the_first_line_says_which_and_why(tmp_path):
    async def go():
        async with Committee(tmp_path, api_scripts={GROQ: lambda t: "Aquí tienes el script."}) as app:
            status, lines, headers = await gw(app, body("Hazme un script en Python que ordene una lista"))
            text = content(lines)
            assert status == 200
            first, _, rest = text.partition("\n\n")
            # GLM-5.2, Qwen3.8-27B and Codestral are not configured here and Kimi is not connected: groq is next
            assert first.startswith("**Automático** eligió **groq** para «Código» (dice «script», dice «python»).")
            assert "Antes en su lista: GLM-5.2 (API), sin configurar; Qwen3.8-27B (Groq), sin configurar;" in first
            assert "Kimi, sin conectar" in first and rest == "Aquí tienes el script."
            assert len(app.api.calls(GROQ)) == 1 and not app.ext.jobs  # one AI, nothing else sent
            head = journal_lines(app, run_id_of(headers))[0]
            assert head["provider"] == "groq" and head["automatico"]["tipo"] == "codigo"
            assert head["automatico"]["eligio"] == "groq" and ["Kimi", "sin conectar"] in head["automatico"]["saltadas"]
            # the answer in the record is the AI's own words (the first line is webllm's note, not the AI's)
            run_dir = app.cfg.paths.runs_dir / run_id_of(headers)
            responses = [p.read_text("utf-8") for p in (run_dir / "responses").glob("*.md")]
            assert responses and all("Automático" not in r for r in responses) and "Aquí tienes el script." in responses[0]
    run(go())


def test_without_stream_the_first_line_is_in_the_answer_too(tmp_path):
    async def go():
        async with Committee(tmp_path, api_scripts={GROQ: lambda t: "Hecho."}) as app:
            status, lines, _ = await gw(app, body("Hazme un script en Python", stream=False))
            message = lines[0]["choices"][0]["message"]["content"]
            assert status == 200 and message.startswith("**Automático** eligió **groq** para «Código»") and message.endswith("Hecho.")
    run(go())


def test_the_next_question_goes_on_with_the_conversation_and_the_ai_never_sees_the_first_line(tmp_path):
    async def go():
        async with Committee(tmp_path, api_scripts={GROQ: lambda t: "Vale."}) as app:
            _, lines, _ = await gw(app, body("Hazme un script en Python"))
            first_answer = content(lines)
            _, lines, _ = await gw(app, body("Hazme un script en Python", (first_answer,), "¿y cómo lo pruebo?"))
            assert content(lines).startswith("**Automático** eligió **groq** para «Código» (sigue la conversación).")
            sent = app.api.calls(GROQ)[-1]["messages"]
            assert [m["content"] for m in sent] == ["Hazme un script en Python", "Vale.", "¿y cómo lo pruebo?"]
    run(go())


def test_an_idea_gets_the_committees_plan_with_the_first_line_and_its_replies_go_to_the_committee(tmp_path):
    async def go():
        async with Committee(tmp_path) as app:
            _, lines, _ = await gw(app, body("¿Merece la pena montar una tienda online de cerámica?"))
            text = content(lines)
            assert text.startswith("**Automático** eligió **webllm · Comité** para «Evaluar una idea» (dice «merece la pena»).")
            assert "Plan del Comité" in text and not app.ext.jobs and not app.api.requests  # nothing sent: the plan first
            assert committee.load_pending(app.cfg.paths, "c-1") is not None
            _, lines, _ = await gw(app, body("¿Merece la pena…?", (text,), "cancela"))
            assert "Cancelado: no se ha enviado nada" in content(lines)
            assert committee.load_pending(app.cfg.paths, "c-1") is None
    run(go())


def test_a_new_question_lets_the_waiting_plan_go_and_says_so(tmp_path):
    async def go():
        async with Committee(tmp_path, api_scripts={GROQ: lambda t: "Listo."}) as app:
            _, lines, _ = await gw(app, body("¿Merece la pena montar una tienda online?"))
            _, lines, _ = await gw(app, body("¿Merece la pena…?", (content(lines),), "Hazme un script en Python que sume dos números"))
            assert "El plan del Comité que esperaba tu «adelante» se ha descartado." in content(lines).split("\n\n")[0]
            assert committee.load_pending(app.cfg.paths, "c-1") is None
            _, lines, _ = await gw(app, body("…", ("…",), "adelante"))  # nothing is waiting any more: never launched
            assert not app.ext.jobs
    run(go())


def test_nobody_available_sends_nothing_and_says_what_to_do(tmp_path):
    async def go():
        async with Committee(tmp_path) as app:
            status, lines, _ = await gw(app, body("Busca en internet las últimas noticias sobre la ley de IA, con fuentes"))
            text = content(lines)
            assert status == 200 and text.startswith("**Automático** no ha enviado nada: para «Investigar con fuentes»")
            assert "- Felo: sin conectar." in text and "Qué puedes hacer" in text
            assert not app.ext.jobs and not app.api.requests
    run(go())


class FailingAPI(FakeAPI):
    async def chat(self, request):
        self.requests.append(await request.json())
        return web.json_response({"error": {"message": "overloaded", "code": 503}}, status=503)


class FailingWorld(Committee):
    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        self.api = FailingAPI({})


def test_if_the_chosen_ai_fails_the_error_says_what_automatico_chose_and_nothing_goes_to_another(tmp_path):
    async def go():
        async with FailingWorld(tmp_path) as app:
            _, lines, _ = await gw(app, body("Hazme un script en Python"))
            err = next(x["error"] for x in lines if isinstance(x, dict) and "error" in x)
            assert err["message"].startswith("**Automático** eligió **groq** para «Código»")
            assert len(app.api.requests) == 1 and not app.ext.jobs  # D21: no second AI without Iván's gesture
    run(go())


def test_an_image_goes_to_a_web_chat_when_no_api_of_the_list_sees_images(tmp_path):
    async def go():
        async with Committee(tmp_path, web_scripts={"qwen": lambda p: "Una foto bonita."}) as app:
            png = b"\x89PNG prueba"
            _, lines, headers = await gw(app, body("¿Qué opinas de esta foto?", files=[a_file("foto.png", "image/png", png)]))
            text = content(lines)
            first, _, rest = text.partition("\n\n")
            assert first.startswith("**Automático** eligió **Qwen** para «Pregunta rápida»")
            assert "z.ai, no ve imágenes" in first and "groq, no ve imágenes" in first and rest == "Una foto bonita."
            (job,) = jobs_of(app, "qwen")
            assert [f["name"] for f in job["files"]] == ["foto.png"] and "Automático" not in job["prompt"]
            assert not app.api.requests  # the image went to one AI only
            head = journal_lines(app, run_id_of(headers))[0]
            assert head["automatico"]["eligio"] == "qwen" and json.dumps(head["files"])
    run(go())


def test_an_api_that_streams_gets_the_first_line_before_its_first_words(tmp_path, mock_server):
    """The API's own lines are passed on as they come (F2): the first line must go before the first of them."""
    from test_appapi import App

    from webllm_agent.config import ProviderConfig

    async def go():
        async with App(tmp_path, mock_server.base_url) as app:
            app.cfg.providers["groq"] = ProviderConfig(name="groq", model="groq/ok")  # the mock server streams "ok"
            status, lines, _ = await gw(app, body("Hazme un script en Python"))
            pieces = [x["choices"][0]["delta"]["content"] for x in lines
                      if isinstance(x, dict) and x.get("choices") and x["choices"][0]["delta"].get("content")]
            assert status == 200 and len(pieces) >= 3  # the line, then the API's own pieces
            assert pieces[0].startswith("**Automático** eligió **groq** para «Código»") and pieces[0].endswith("\n\n")
            assert "".join(pieces[1:]) == "answer from groq/ok"
    run(go())

"""PLAN-v5 F6: webs that repair themselves, and going on by hand in the web.

Units (what an AI may answer, patches with their history, a cut-short error) and the real bridge + gateway + app
API with a fake extension that also answers "try_patch", "reread", "check" and "observe". The same flows with the
real extension in Chromium: tests/extension/repair_flow.mjs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from test_appapi import AUTH, App, DiagnosingExtension, run
from test_gateway import ask, content, gw, journal_lines
from test_guard import QWEN, acquire, make_guard
from webllm_agent import fichas, flows, repair, vault
from webllm_agent.broadcaster import verify_run
from webllm_agent.client import ChatResult
from webllm_agent.config import ProviderConfig

ROOT = Path(__file__).resolve().parents[1]
# A page's x-ray as driver.js makes it: numbered candidates, the page's own selectors (never shown to the AI).
XRAY = {"url": "https://chat.qwen.ai/c/1", "candidates": [
    {"n": 0, "kind": "box", "tag": "textarea", "cls": "nuevo", "w": 700, "h": 60, "sel": "textarea.nuevo", "general": "textarea.nuevo"},
    {"n": 1, "kind": "button", "tag": "button", "label": "Send", "sel": "button#enviar", "general": "button#enviar"},
    {"n": 2, "kind": "block", "tag": "div", "cls": "x1 y2", "len": 120, "after_your_message": True,
     "sel": "main > div:nth-of-type(7)", "general": "div.x1.y2"},
    {"n": 3, "kind": "block", "tag": "div", "cls": "u", "len": 11, "is_your_message": True, "sel": "div.u", "general": "div.u"},
]}


# ------------------------------------------------------------------ what an AI may answer

def test_the_ai_only_names_candidates_by_number():
    assert repair.parse('{"input": 0}', XRAY, ["input"]) == {"input": XRAY["candidates"][0]}
    assert repair.parse('```json\n{"answer": 2}\n```', XRAY, ["answer"])["answer"]["n"] == 2
    assert repair.parse('{"answer": null}', XRAY, ["answer"]) == {}  # "none of them" is an answer too
    assert repair.to_patch(repair.parse('{"input": 0, "answer": 2}', XRAY, ["input", "answer"])) == {
        "input": ["textarea.nuevo"], "answer": ["div.x1.y2"]}  # an answer's selector finds the next answers too


@pytest.mark.parametrize("answer,why", [
    ("document.querySelector('textarea').value = 'x'", "not JSON"),
    ('{"input": "textarea.nuevo"}', "not a candidate number"),
    ('{"input": "0"}', "not a candidate number"),
    ('{"input": true}', "not a candidate number"),
    ('{"input": 0.0}', "not a candidate number"),
    ('{"input": 9}', "no candidate 9"),
    ('{"input": -1}', "no candidate -1"),
    ('{"input": 1}', "is a button, not a box"),
    ('{"answer": 3}', "the user's own message"),
    ('{"input": 0, "run": 1}', "roles not asked"),
    ('[0]', "not a JSON object"),
    ('Here it is: {"input": 0}', "not JSON"),
    ('{"input":' + " " * 2001 + '0}', "too long"),
], ids=lambda x: x[:30] if isinstance(x, str) else None)
def test_anything_else_an_ai_writes_is_rejected(answer, why):
    with pytest.raises(repair.Rejected, match=why.replace("(", r"\(").replace(")", r"\)")):
        repair.parse(answer, XRAY, ["input"] if '"answer"' not in answer else ["answer"])


def test_the_ai_never_sees_selectors():
    text = repair.prompt(XRAY, ["input"])
    for c in XRAY["candidates"]:
        assert c["sel"] not in text and f'"general"' not in text
    assert "textarea" in text and '"n": 0' in text and "Send" in text


def test_which_ai_helps_only_private_apis_or_this_pc_never_a_web_chat_or_a_blocked_one(tmp_path):
    from conftest import make_config
    cfg = make_config(tmp_path, "http://unused/v1", [
        ProviderConfig(name="qwen", model="browser/qwen", kind="browser", gateway="bridge"),
        ProviderConfig(name="otra", model="x/ok"),
        ProviderConfig(name="groq", model="groq/ok"),
        ProviderConfig(name="zai", model="z/ok"),
        ProviderConfig(name="publica", model="p/ok", private=False),
        ProviderConfig(name="prohibida", model="cc/claude-x"),
        ProviderConfig(name="lmstudio:qwen", model="lmstudio/qwen", kind="local", gateway="local", base_url="http://127.0.0.1:1234/v1"),
    ])
    assert [p.name for p in repair.helpers(cfg)] == ["zai", "groq", "otra", "lmstudio:qwen"]
    assert repair.helper(cfg).name == "zai"
    assert repair.settings(cfg.paths) == {"enabled": True, "ai": ""}  # on unless Iván turns it off
    repair.configure(cfg.paths, True, "lmstudio:qwen")
    assert repair.helper(cfg).name == "lmstudio:qwen"
    repair.configure(cfg.paths, False, "groq")
    assert repair.settings(cfg.paths) == {"enabled": False, "ai": "groq"}


# ------------------------------------------------------------------ patches: dated, by whom, undone one by one

def test_each_fix_is_dated_with_who_made_it_and_undone_on_its_own(tmp_path):
    from conftest import make_config
    paths = make_config(tmp_path, "http://unused/v1", []).paths
    fichas.add_patch(paths, "rara", "answer", "div.x1.y2", by="ia:zai", why="no podía leer la respuesta")
    fichas.teach(paths, "rara", "input", "textarea#nueva")
    fichas.add_patch(paths, "rara", "answer", "div.z9", by="ivan", why="Enséñame")
    assert fichas.load_patch(paths, "rara") == {"answer": ["div.z9", "div.x1.y2"], "input": ["textarea#nueva"]}
    hist = fichas.patch_history(paths, "rara")
    assert [(h["key"], h["by"], h["active"]) for h in hist] == [("answer", "ia:zai", True), ("input", "ivan", True),
                                                               ("answer", "ivan", True)]
    assert all(len(h["when"]) == 19 for h in hist)
    assert fichas.undo_patch(paths, "rara", 0) == {"answer": ["div.z9"], "input": ["textarea#nueva"]}
    with pytest.raises(ValueError):
        fichas.undo_patch(paths, "rara", 0)  # already undone
    with pytest.raises(ValueError):
        fichas.add_patch(paths, "rara", "cookies", "x", by="ia:zai")  # only the things a page is driven by
    assert fichas.forget_patch(paths, "rara") and fichas.load_patch(paths, "rara") == {}
    assert [h["active"] for h in fichas.patch_history(paths, "rara")] == [False, False, False]  # the history stays


# ------------------------------------------------------------------ a cut-short error still says what happened

def test_an_error_body_cut_short_keeps_webllms_code_and_the_start_of_its_message():
    whole = json.dumps({"error": {"code": "empty_answer", "type": "empty_answer",
                                  "message": "Rara: contestó, pero no pude leer su \"respuesta\" " + "x" * 900}})
    r = ChatResult("http_error", http_status=502, body_excerpt=whole[:500], error="HTTP 502")
    assert flows.error_code(r) == "empty_answer"  # not "overloaded" (Iván read "Rara está saturada")
    assert flows._error_text(r).startswith('Rara: contestó, pero no pude leer su "respuesta" x')
    other = ChatResult("http_error", http_status=502, body_excerpt='{"error": {"code": "1302", "message": "x"', error="HTTP 502")
    assert flows.error_code(other) == "overloaded"  # a provider's own code is still read like the HTTP status


def test_a_message_ivan_wrote_himself_counts_but_never_waits(tmp_path):
    g, ft = make_guard(tmp_path)
    g.note(QWEN)
    g.note(QWEN)
    assert g._load()["providers"]["qwen"]["count_today"] == 2 and ft.slept == []
    acquire(g, QWEN)  # webllm's next message keeps the spacing after his
    assert ft.slept and ft.slept[0] == pytest.approx(20, abs=0.5)


# ------------------------------------------------------------------ the bridge, with a fake extension

class RepairingExtension(DiagnosingExtension):
    """Also answers the F6 messages: try_patch (the page tries a patch, sending nothing), reread, check, observe."""

    def __init__(self, behaviour, tries_ok=True, reread=None, page=None):
        super().__init__(behaviour)
        self.tries_ok, self.reread, self.page = tries_ok, reread, page or {}

    async def _loop(self):
        async for msg in self.ws:
            m = json.loads(msg.data)
            self.seen.append(m)
            kind, reply = m.get("type"), None
            if kind == "try_patch":
                reply = {"ok": True, "text": json.dumps({"ok": self.tries_ok, "checks": {k: self.tries_ok for k in m["patch"]}})}
            elif kind == "reread":
                reply = {"ok": True, "text": self.reread, "via": "dom"} if self.reread else {"ok": False, "error": "empty_answer"}
            elif kind == "check":
                reply = {"ok": True, "text": json.dumps(self.page.get(m["site"], {"input": True}))}
            elif kind == "observe":
                reply = {"ok": True, "text": json.dumps({"tab": 7}), "via": "observe"}
            elif kind == "job":
                self.jobs.append(m)
                asyncio.create_task(self._answer(m))
            if reply is not None:
                await self.ws.send_json({"type": "result", "id": m["id"], **reply})


async def with_ext(app: App, ext: RepairingExtension) -> RepairingExtension:
    app.ext = ext
    await ext.connect(app.server)
    await asyncio.wait_for(app.bridge.connected.wait(), 2)
    return ext


def first_then(fail: dict, ok_text: str):
    """The page fails the first job this way; the next ones answer."""
    n = {"jobs": 0}

    def answer(job):
        n["jobs"] += 1
        return fail if n["jobs"] == 1 else {"ok": True, "text": ok_text, "via": "copy-button"}
    return answer


def helper_says(app: App, text: str) -> list[str]:
    asked: list[str] = []

    async def fake(cfg, p, prompt):
        asked.append(prompt)
        return text
    app.bridge._ask_helper = fake
    return asked


def avisos(lines) -> list[str]:
    return [x for x in lines if isinstance(x, dict) and x.get("webllm")][-1]["webllm"]["avisos"]


def test_a_page_whose_text_box_moved_is_repaired_and_the_question_sent_once(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension(
                {"qwen": first_then({"ok": False, "error": "no_input", "detail": "no box", "xray": XRAY}, "Hola, Iván")}))
            asked = helper_says(app, '{"input": 0}')
            status, lines, h = await gw(app, ask("qwen", "¿Hola?"))
            assert status == 200 and content(lines) == "Hola, Iván"
            # the AI saw the page's structure, not the question; the page tried it sending nothing; then it was sent
            assert len(asked) == 1 and "¿Hola?" not in asked[0] and "textarea.nuevo" not in asked[0]
            tried = [m for m in ext.seen if m["type"] == "try_patch"]
            assert tried == [{**tried[0], "patch": {"input": ["textarea.nuevo"]}, "sent": ""}]
            assert len(ext.jobs) == 2 and ext.jobs[1]["site_patch"]["input"] == ["textarea.nuevo"]
            assert any("no encontraba su caja" in a and "z.ai" in a for a in avisos(lines))
            (call,) = [x for x in journal_lines(app, h["x-webllm-run"]) if x["kind"] == "flow"]
            assert call["repaired"] == {"ai": "z.ai", "roles": ["input"]}
            assert [(x["by"], x["key"]) for x in fichas.patch_history(app.cfg.paths, "qwen")] == [("ia:zai", "input")]
            assert repair.history(app.cfg.paths)[0]["result"] == "guardada"
            assert app.bridge.app_api.usage(app.cfg, app.cfg.providers["zai"])[0] == 1  # the helper's call counts
            # the next question uses the fix with no AI asked
            status, lines, _ = await gw(app, ask("qwen", "¿Otra?"))
            assert content(lines) == "Hola, Iván" and len(asked) == 1 and ext.jobs[2]["site_patch"]["input"] == ["textarea.nuevo"]
    run(go())


def test_an_answer_that_cannot_be_read_is_read_again_and_never_sent_again(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension(
                {"qwen": {"ok": False, "error": "empty_answer", "detail": "no answer element", "xray": XRAY}},
                reread="La respuesta, leída de nuevo"))
            helper_says(app, '{"answer": 2}')
            status, lines, _ = await gw(app, ask("qwen", "¿Qué hora es?"))
            assert status == 200 and content(lines) == "La respuesta, leída de nuevo"
            assert len(ext.jobs) == 1  # sent once
            (tried,) = [m for m in ext.seen if m["type"] == "try_patch"]
            assert tried["patch"] == {"answer": ["div.x1.y2"]} and tried["sent"] == "¿Qué hora es?"  # checked against it
            assert [m["type"] for m in ext.seen if m["type"] in ("job", "try_patch", "reread")] == ["job", "try_patch", "reread"]
    run(go())


def test_a_fix_the_page_does_not_confirm_is_not_kept_and_the_error_says_what_happened(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            # the real extension sends the page's whole diagnosis as the detail (thousands of characters)
            ext = await with_ext(app, RepairingExtension(
                {"qwen": {"ok": False, "error": "empty_answer", "detail": json.dumps({"diagnose": "d" * 6000}), "xray": XRAY}},
                tries_ok=False))
            helper_says(app, '{"answer": 2}')
            _, lines, _ = await gw(app, ask("qwen"))
            err = next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]
            assert err["code"] == "empty_answer" and "no pude leer su respuesta" in err["message"] and "d" * 200 not in err["message"]
            assert fichas.load_patch(app.cfg.paths, "qwen") == {} and fichas.patch_history(app.cfg.paths, "qwen") == []
            assert repair.history(app.cfg.paths)[0]["result"] == "no pasó la prueba en la página"
            assert len(ext.jobs) == 1 and not [m for m in ext.seen if m["type"] == "reread"]
    run(go())


def test_an_ai_answer_that_is_not_numbers_changes_nothing(tmp_path, mock_server):
    """The helper really asked (the mock API answers prose): rejected, nothing tried, nothing sent again."""
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({"qwen": {"ok": False, "error": "no_input", "detail": "", "xray": XRAY}}))
            _, lines, _ = await gw(app, ask("qwen"))
            assert next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]["code"] == "no_input"
            assert mock_server.calls("z/ok") == 1
            last = repair.history(app.cfg.paths)[0]
            assert last["result"] == "rechazada" and last["why"] == "not JSON" and last["answer"] == "answer from z/ok"
            assert not [m for m in ext.seen if m["type"] == "try_patch"] and len(ext.jobs) == 1
            assert fichas.load_patch(app.cfg.paths, "qwen") == {}
    run(go())


def test_with_repair_off_no_ai_is_asked(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            await with_ext(app, RepairingExtension({"qwen": {"ok": False, "error": "no_input", "detail": "", "xray": XRAY}}))
            status, body = await app.post("/api/reparar", {"enabled": False})
            assert status == 200 and body["enabled"] is False and body["options"][0]["name"] == "zai"
            asked = helper_says(app, '{"input": 0}')
            _, lines, _ = await gw(app, ask("qwen"))
            assert next(x for x in lines if isinstance(x, dict) and "error" in x)["error"]["code"] == "no_input"
            assert asked == [] and mock_server.requests == [] and repair.history(app.cfg.paths)[0]["result"] == "apagada"
            status, body = await app.post("/api/reparar", {"enabled": True, "ai": "qwen"})
            assert status == 400 and "no puede ayudar" in body["error"]  # a web chat never helps
    run(go())


def test_undo_in_the_ficha_takes_effect_on_the_next_question(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({}))
            fichas.add_patch(app.cfg.paths, "qwen", "answer", "div.x1.y2", by="ia:zai", why="no podía leer la respuesta")
            _, ficha, _ = await app.get("/api/ficha/qwen")
            (fix,) = ficha["arreglos"]
            assert fix["by"] == "una IA (z.ai)" and fix["what"] == "la respuesta" and fix["active"]
            await gw(app, ask("qwen"))
            assert ext.jobs[-1]["site_patch"] == {"answer": ["div.x1.y2"]}
            status, ficha = await app.post("/api/ficha/qwen/deshacer", {"index": 0})
            assert status == 200 and ficha["arreglos"][0]["active"] is False and ficha["arreglos"][0]["undone"]
            await gw(app, ask("qwen"))
            assert "site_patch" not in ext.jobs[-1]
            status, body = await app.post("/api/ficha/qwen/deshacer", {"index": 0})
            assert status == 400 and "ya estaba deshecho" in body["error"]
    run(go())


def test_the_daily_check_opens_each_chat_sends_nothing_and_repairs_a_lost_box(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({}, page={"zai": {"input": False, "xray": XRAY}}))
            helper_says(app, '{"input": 0}')
            status, _ = await app.post("/api/revisar", {})
            assert status == 200
            for _ in range(50):
                _, rev, _ = await app.get("/api/revision")
                if not rev["running"]:
                    break
                await asyncio.sleep(0.1)
            states = {x["site"]: x["state"] for x in rev["sites"]}
            assert states == {"qwen": "bien", "zai": "reparada"} and rev["ok"] == rev["total"] == 2
            assert ext.jobs == []  # nothing was sent to any chat
            assert [m["site"] for m in ext.seen if m["type"] == "check"] == ["qwen", "zai"]
            assert fichas.load_patch(app.cfg.paths, "zai") == {"input": ["textarea.nuevo"]}
    run(go())


# ------------------------------------------------------------------ going on by hand in the web

def test_turns_written_by_hand_in_the_web_join_the_same_conversation(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({"qwen": {"ok": True, "text": "Primera respuesta", "via": "copy-button",
                                                                   "url": "https://chat.qwen.ai/c/abc"}}))
            folder = tmp_path / "vault"
            folder.mkdir()
            vault.configure(app.cfg.paths, str(folder))
            _, _, h = await gw(app, ask("qwen", "Empiezo en webllm", chat_id="c-9"))
            first = h["x-webllm-run"]
            # "Continuar en la web": that exact conversation, in a normal tab
            status, body = await app.post("/api/continuar", {"run_id": first})
            (obs,) = [m for m in ext.seen if m["type"] == "observe"]
            assert status == 200 and obs["url"] == "https://chat.qwen.ai/c/abc" and obs["follows"] == first
            ext_turn = {"type": "observed", "tab": 7, "site": "qwen", "url": "https://chat.qwen.ai/c/abc", "via": "dom", "seconds": 12.3}
            await ext.ws.send_json({**ext_turn, "state": "on"} | {"type": "observe_state", "on": True, "follows": first})
            for n in (1, 2):
                await ext.ws.send_json({**ext_turn, "follows": first, "user": f"Turno {n} a mano", "answer": f"Respuesta {n}"})
                await asyncio.sleep(0.3)
            await asyncio.sleep(0.5)
            runs = sorted(d for d in app.cfg.paths.runs_dir.iterdir() if d.name != first)
            heads = [journal_lines(app, d.name)[0] for d in runs]
            assert [x["kind"] for x in heads] == ["observed", "observed"] and {x["follows"] for x in heads} == {first}
            calls = [next(x for x in journal_lines(app, d.name) if x["kind"] == "flow") for d in runs]
            assert [c["by"] for c in calls] == ["ivan", "ivan"] and all(verify_run(d).ok for d in runs)
            # the history says what it is: written by him in the web, and how long the page took (measured there)
            _, seen, _ = await app.get(f"/api/historial/{runs[0].name}")
            (said,) = seen["steps"][0]["answers"]
            assert seen["kind"] == "web" and seen["title"] == "En la web de Qwen" and said["by_ivan"] and said["seconds"] == 12.3
            assert app.bridge.guard._load()["providers"]["qwen"]["count_today"] == 3  # his 2 count, nothing waited
            assert vault.flush(10)
            (note,) = [p for p in (folder / "webllm").rglob("*.md") if p.name != "Índice.md" and "Respuestas" not in p.parts]
            text = note.read_text("utf-8")
            assert text.count("Tú, en la web de Qwen") == 2 and "Empiezo en webllm" in text and "Respuesta 2" in text
            _, est, _ = await app.get("/api/estado")
            assert est["observing"][0]["follows"] == first
    run(go())


def test_a_chat_ivan_opened_himself_and_registered_is_one_conversation(tmp_path, mock_server):
    """ "Registrar esta conversación" from the extension's icon: no earlier question; the first turn starts the
    conversation and the next ones in that tab follow it."""
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({}))
            await ext.ws.send_json({"type": "observe_state", "site": "qwen", "tab": 11, "on": True, "follows": None})
            for n in (1, 2, 3):
                await ext.ws.send_json({"type": "observed", "tab": 11, "site": "qwen", "follows": None,
                                        "url": "https://chat.qwen.ai/c/z", "user": f"Mío {n}", "answer": f"R{n}"})
                await asyncio.sleep(0.4)
            await ext.ws.send_json({"type": "observe_state", "site": "qwen", "tab": 11, "on": False})
            await asyncio.sleep(0.3)
            heads = sorted((journal_lines(app, d.name)[0] for d in app.cfg.paths.runs_dir.iterdir()), key=lambda x: x["ts"])
            root = heads[0]["run_id"]
            assert heads[0]["follows"] is None and [x["follows"] for x in heads[1:]] == [root, root]
            # the extension is told too (so a restart of webllm does not split the conversation)
            assert {(m["tab"], m["follows"]) for m in ext.seen if m["type"] == "observe_follows"} == {(11, root)}
            _, est, _ = await app.get("/api/estado")
            assert est["observing"] == []  # stopped, and it stays stopped
            # a turn with nothing typed is not recorded
            await ext.ws.send_json({"type": "observed", "tab": 11, "site": "qwen", "user": "  ", "answer": "x"})
            await asyncio.sleep(0.3)
            assert len(list(app.cfg.paths.runs_dir.iterdir())) == 3
    run(go())


def test_continuing_an_answer_that_did_not_come_from_a_web_chat_says_why(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            await with_ext(app, RepairingExtension({}))
            _, _, h = await gw(app, ask("zai"))
            status, body = await app.post("/api/continuar", {"run_id": h["x-webllm-run"]})
            assert status == 409 and "no vino de un chat web" in body["error"]
            status, body = await app.post("/api/continuar", {"run_id": "../../etc"})
            assert status == 404
    run(go())


def test_continuar_under_an_open_webui_answer_finds_it_by_open_webuis_own_ids(tmp_path, mock_server):
    """The button's own code (openwebui/webllm_continuar.py) against the real bridge: the answer is found by the
    chat and message ids the pipe sent with the question; nothing else is guessed."""
    import importlib.util
    from test_bridge import TOKEN
    spec = importlib.util.spec_from_file_location("webllm_continuar", ROOT / "openwebui" / "webllm_continuar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({"qwen": {"ok": True, "text": "Hola", "via": "copy-button",
                                                                   "url": "https://chat.qwen.ai/c/xyz"}}))
            _, _, h = await gw(app, ask("qwen", "Hola", chat_id="owui-1", message_id="m-2"))
            await gw(app, ask("zai", "Hola", chat_id="owui-1", message_id="m-4"))
            button = mod.Action()
            button.valves.WEBLLM_URL, button.valves.WEBLLM_TOKEN = str(app.url("/")).rstrip("/"), TOKEN
            events: list[dict] = []

            async def emit(e):
                events.append(e)
            await button.action({"chat_id": "owui-1", "id": "m-2"}, __event_emitter__=emit)
            (obs,) = [m for m in ext.seen if m["type"] == "observe"]
            assert obs["follows"] == h["x-webllm-run"] and obs["url"] == "https://chat.qwen.ai/c/xyz"
            assert [e["type"] for e in events] == ["notification"]  # the answer's own status line is left alone
            assert events[0]["data"]["type"] == "success" and "Abierta en tu Chrome la conversación de Qwen" in events[0]["data"]["content"]
            ok, text = await button.ask("owui-1", "m-4")  # an answer by API: no web conversation
            assert not ok and "no vino de un chat web" in text
            ok, text = await button.ask("owui-1", "otro")
            assert not ok and "No encuentro esta respuesta" in text
            button.valves.WEBLLM_TOKEN = "mala"
            assert (await button.ask("owui-1", "m-2"))[0] is False
            button.valves.WEBLLM_URL = "http://127.0.0.1:9"
            assert await button.ask("owui-1", "m-2") == (False, "webllm está apagado: ábrelo con su icono y vuelve a pulsar «Continuar en la web».")
    run(go())


def test_coming_back_to_the_conversation_the_turns_written_in_the_web_go_with_the_next_question(tmp_path, mock_server):
    """PLAN-v5 section 3: "después puedes volver a webllm y seguir desde donde lo dejaste". Open WebUI does not
    have what Iván wrote in the web; webllm puts it where it happened, to whichever AI answers, and says so."""
    async def go():
        async with App(tmp_path, mock_server.base_url, connect=False) as app:
            ext = await with_ext(app, RepairingExtension({"qwen": {"ok": True, "text": "A1 de Qwen", "via": "copy-button",
                                                                   "url": "https://chat.qwen.ai/c/abc"}}))
            _, _, h = await gw(app, ask("qwen", "Q1 en webllm", chat_id="c-5", message_id="m-1"))
            first = h["x-webllm-run"]
            for n in (1, 2):
                await ext.ws.send_json({"type": "observed", "tab": 3, "site": "qwen", "follows": first, "url": "https://chat.qwen.ai/c/abc",
                                        "user": f"H{n} escrito a mano", "answer": f"R{n} de la web", "via": "dom"})
                await asyncio.sleep(0.4)
            history = [{"role": "user", "content": "Q1 en webllm"}, {"role": "assistant", "content": "A1 de Qwen"}]
            # back in Open WebUI, the next question to an AI by API
            body = {**ask("zai", chat_id="c-5", message_id="m-3"),
                    "messages": [*history, {"role": "user", "content": "Q2 de vuelta"}]}
            _, lines, _ = await gw(app, body)
            sent = mock_server.requests[-1]["body"]["messages"]
            assert [m["content"].split("\n")[-1] for m in sent] == [
                "Q1 en webllm", "A1 de Qwen", "H1 escrito a mano", "R1 de la web", "H2 escrito a mano", "R2 de la web", "Q2 de vuelta"]
            assert "directly in Qwen's own web page" in sent[2]["content"]
            assert "Con tu pregunta van también los 2 mensajes que escribiste directamente en la web de Qwen, con sus respuestas." in avisos(lines)
            # and to the web chat, in the one text it gets
            await gw(app, {**body, "model": "qwen", "messages": [*history, {"role": "user", "content": "Q3 a Qwen"}]})
            prompt = ext.jobs[-1]["prompt"]
            assert prompt.index("A1 de Qwen") < prompt.index("H1 escrito a mano") < prompt.index("R2 de la web") < prompt.index("Q3 a Qwen")
            # another conversation of Open WebUI gets nothing of it
            await gw(app, ask("zai", "Otra cosa", chat_id="c-6"))
            assert [m["content"] for m in mock_server.requests[-1]["body"]["messages"]] == ["Otra cosa"]
    run(go())


def test_hand_turns_go_after_the_answer_they_followed_even_with_later_questions():
    from webllm_agent.gateway import with_hand_turns
    msgs = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"}, {"role": "assistant", "content": "A2"}, {"role": "user", "content": "Q3"}]
    turns = [{"after": "Q1", "label": "Qwen", "user": "H", "answer": "R"}]
    out = [m["content"].split("\n")[-1] for m in with_hand_turns(msgs, turns)]
    assert out == ["Q1", "A1", "H", "R", "Q2", "A2", "Q3"]
    # the question it followed is no longer in Open WebUI (edited): just before the new one
    out = [m["content"].split("\n")[-1] for m in with_hand_turns(msgs, [{**turns[0], "after": "Q1 cambiada", "answer": ""}])]
    assert out == ["Q1", "A1", "Q2", "A2", "H", "(the answer could not be read from the page)", "Q3"]

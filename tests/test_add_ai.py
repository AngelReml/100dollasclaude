"""'+ Añadir otra IA': address checks, the extension's permission + test flow (faked), saving, removing."""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess

import pytest

from test_appapi import AUTH, App, DiagnosingExtension, run
from webllm_agent.appapi import parse_chat_url, site_key, site_name
from webllm_agent.config import Paths, load_config, load_custom_ais

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()


class AddingExtension(DiagnosingExtension):
    """Answers "add_site" like extension 0.5.0 would after Iván clicks "Permitir y probar"."""

    def __init__(self, outcome="ok", **kw):
        answer = {"ok": True, "text": "**pong**", "via": "copy-button"}
        if outcome == "other_answer":
            answer = {"ok": True, "text": "I can't help with that.", "via": "dom"}
        elif outcome == "rate_limited":
            answer = {"ok": False, "error": "rate_limited"}
        super().__init__({site: answer for site in ("mistral", "example")}, **kw)
        self.outcome = outcome
        self.adds: list[dict] = []

    async def _loop(self):
        async for msg in self.ws:
            job = json.loads(msg.data)
            if job.get("type") == "add_site":
                self.adds.append(job)
                await self.ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "add"})
                asyncio.create_task(self._test(job))
            elif job.get("type") == "job":
                self.jobs.append(job)
                asyncio.create_task(self._answer(job))

    async def _test(self, job):
        async def progress(step, ok, text):
            await asyncio.sleep(0.05)
            await self.ws.send_json({"type": "add_progress", "add_id": job["add_id"], "step": step, "ok": ok, "text": text})

        await progress("permission", True, "Permiso concedido")
        await progress("open", True, "Web abierta")
        if self.outcome == "no_input":
            await self.ws.send_json({"type": "add_done", "add_id": job["add_id"], "ok": False, "error": "no_input",
                                     "detail": "{\"inputs\": []}"})
            return
        await progress("input", True, "Caja de texto: encontrada")
        # the bridge then sends the test message as a normal (guarded) job
        await self.ws.send_json({"type": "add_ready", "add_id": job["add_id"], "icon": f"data:image/png;base64,{PNG}"})


class AddApp(App):
    def __init__(self, tmp_path, base_url, outcome="ok", **kw):
        super().__init__(tmp_path, base_url, **kw)
        self.outcome = outcome

    async def __aenter__(self):
        await super().__aenter__()
        await self.ext.close()
        self.ext = AddingExtension(self.outcome)
        await self.ext.connect(self.server)
        await asyncio.wait_for(self.bridge.connected.wait(), 2)
        return self

    async def wait_done(self, add_id):
        for _ in range(100):
            _, st, _ = await self.get(f"/api/anadir/{add_id}")
            if st["status"] != "running":
                return st
            await asyncio.sleep(0.05)
        raise AssertionError("the add test never finished")


# ------------------------------------------------------------------ address rules

@pytest.mark.parametrize("url, code", [
    ("claude.ai", "bad_url"), ("https://claude.ai/new", "blocked"), ("https://x.chatgpt.com", "blocked"),
    ("https://chat.openai.com", "blocked"), ("https://platform.openai.com", "blocked"),
    ("http://chat.mistral.ai", "not_https"), ("ftp://x.org", "not_https"), ("", "bad_url"),
])
def test_bad_or_excluded_addresses(url, code):
    with pytest.raises(ValueError, match=code):
        parse_chat_url(url)


def test_address_key_and_name():
    assert parse_chat_url("  https://Chat.Mistral.ai/chat///  ") == ("https://chat.mistral.ai/chat/", "chat.mistral.ai")
    assert site_key("chat.mistral.ai", set()) == "mistral"
    assert site_key("www.perplexity.ai", {"perplexity"}) == "perplexity-2"
    assert site_name("perplexity-2") == "Perplexity"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_extension_and_server_apply_the_same_rules():
    urls = ["https://chat.mistral.ai/chat///", "https://claude.ai", "http://x.org", "nope", "https://www.perplexity.ai"]
    js = ("const c=require('./extension/common.js');console.log(JSON.stringify(" + json.dumps(urls) +
          ".map(u=>{const p=c.parseChatUrl(u);return p.ok?[p.url,c.siteKey(p.host,[])]:p.error})))")
    out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    py = []
    for u in urls:
        try:
            url, host = parse_chat_url(u)
            py.append([url, site_key(host, set())])
        except ValueError as exc:
            py.append(str(exc))
    assert out == py


# ------------------------------------------------------------------ the flow

def test_add_a_site_end_to_end(tmp_path, mock_server):
    async def go():
        async with AddApp(tmp_path, mock_server.base_url) as a:
            status, st = await a.post("/api/anadir", {"url": "https://chat.mistral.ai/chat"})
            assert status == 200 and st["key"] == "mistral" and st["name"] == "Mistral"
            assert a.ext.adds[0]["url"] == "https://chat.mistral.ai/chat" and a.ext.adds[0]["add_id"] == st["add_id"]
            st = await a.wait_done(st["add_id"])
            assert st["status"] == "ok" and "Mistral ya está entre tus IAs" in st["message"]
            assert [x["step"] for x in st["steps"]] == ["permission", "open", "input", "send", "read"]
            assert all(x["ok"] for x in st["steps"])
            # the test message went like any other: through the bridge, guarded and counted
            (test,) = a.ext.jobs
            assert test["prompt"] == "Responde solo con la palabra: pong" and test["site_config"] == {
                "name": "Mistral", "url": "https://chat.mistral.ai/chat"}
            assert a.bridge.guard.status()["mistral"]["count_today"] == 1

            _, body, _ = await a.get("/api/estado")
            (m,) = [x for x in body["ais"] if x["name"] == "mistral"]
            assert (m["kind"], m["label"], m["custom"], m["icon"], m["url"]) == (
                "chat", "Mistral", True, True, "https://chat.mistral.ai/chat")
            async with a.http.get(a.url(f"/api/icono/mistral?token={AUTH['Authorization'][7:]}")) as r:
                assert r.status == 200 and r.headers["Content-Type"] == "image/png"
                assert (await r.read()).startswith(b"\x89PNG")

            # it works like any other chat: guarded, and the job carries its address
            _, events = await a.ask("hola", ["mistral"])
            assert [e["ok"] for e in events if e["type"] == "target_done"] == [True]
            job = a.ext.jobs[-1]
            assert job["site"] == "mistral" and job["site_config"] == {"name": "Mistral",
                                                                       "url": "https://chat.mistral.ai/chat"}
            assert a.bridge.guard.status()["mistral"]["count_today"] == 2  # the test + this question

            # it survives a restart: kept in data/state (not in data/config.yaml, which is in git)
            saved = load_custom_ais(Paths.from_data_dir(tmp_path / "data"))
            assert list(saved) == ["mistral"] and saved["mistral"].url == "https://chat.mistral.ai/chat"
            (tmp_path / "data" / "config.yaml").write_text("{}", encoding="utf-8")
            assert "mistral" in load_config(tmp_path / "data").providers

            status, body = await a.post("/api/anadir", {"url": "https://chat.mistral.ai/"})
            assert status == 409 and "Ya tienes esta IA" in body["error"]

            assert (await a.post("/api/quitar", {"ia": "mistral"}))[1] == {"ok": True}
            _, body, _ = await a.get("/api/estado")
            assert "mistral" not in [x["name"] for x in body["ais"]]
            assert load_custom_ais(Paths.from_data_dir(tmp_path / "data")) == {}
            assert (await a.post("/api/quitar", {"ia": "qwen"}))[0] == 400  # built-in ones stay
    run(go())


def test_a_site_that_cannot_be_driven_says_why(tmp_path, mock_server):
    async def go():
        async with AddApp(tmp_path, mock_server.base_url, outcome="no_input") as a:
            _, st = await a.post("/api/anadir", {"url": "https://example.org/chat"})
            st = await a.wait_done(st["add_id"])
            assert st["status"] == "failed" and st["error"] == "no_input"
            assert "caja de texto" in st["message"] and st["detail"] == '{"inputs": []}'
            _, body, _ = await a.get("/api/estado")
            assert "example" not in [x["name"] for x in body["ais"]]
    run(go())


def test_a_wrong_answer_or_an_account_limit_is_not_saved(tmp_path, mock_server):
    async def go():
        async with AddApp(tmp_path, mock_server.base_url, outcome="other_answer") as a:
            _, st = await a.post("/api/anadir", {"url": "https://example.org/chat"})
            st = await a.wait_done(st["add_id"])
            assert st["status"] == "failed" and st["error"] == "unexpected_answer" and "no me fío" in st["message"]
        async with AddApp(tmp_path, mock_server.base_url, outcome="rate_limited") as a:
            _, st = await a.post("/api/anadir", {"url": "https://example.org/chat"})
            st = await a.wait_done(st["add_id"])
            assert st["status"] == "failed" and st["error"] == "rate_limited"
            # an account limit pauses that site in the guard, as for any chat
            assert a.bridge.guard.status()["example"]["cooldown_reason"]
            _, st = await a.post("/api/anadir", {"url": "https://example.org/chat"})
            st = await a.wait_done(st["add_id"])  # trying again right away: the guard says no
            assert st["status"] == "failed" and st["error"] == "paused" and st["message"]
            assert len(a.ext.jobs) == 1
            _, body, _ = await a.get("/api/estado")
            assert "example" not in [x["name"] for x in body["ais"]]
    run(go())


def test_excluded_site_never_reaches_the_extension(tmp_path, mock_server):
    async def go():
        async with AddApp(tmp_path, mock_server.base_url) as a:
            status, body = await a.post("/api/anadir", {"url": "https://claude.ai/new"})
            assert status == 400 and body["code"] == "blocked" and "no se puede añadir" in body["error"]
            status, body = await a.post("/api/anadir", {"url": "https://chat.deepseek.com/"})
            assert status == 409 and "ya viene con webllm" in body["error"]  # built in, even if not configured
            assert a.ext.adds == []
    run(go())


def test_old_extension_is_told_to_reload(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:  # 0.4.0 fake: ignores add_site
            a.bridge.app_api.bridge._send_to_extension = _timeout
            _, st = await a.post("/api/anadir", {"url": "https://chat.mistral.ai"})
            assert st["status"] == "failed" and st["error"] == "old_extension" and "↻" in st["message"]
    run(go())


async def _timeout(payload, wait_s):
    return {"ok": False, "error": "timeout"}

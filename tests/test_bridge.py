"""Bridge tests: a fake Chrome extension over a real WebSocket (no network, no Chrome)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import aiohttp
from aiohttp.test_utils import TestServer

from conftest import make_config
from webllm_agent.bridge import Bridge, flatten_messages
from webllm_agent.broadcaster import broadcast, resolve_targets
from webllm_agent.config import GuardConfig, ProviderConfig
from webllm_agent.guard import Guard

TOKEN = "bridge-test-token"


class FakeExtension:
    """Answers bridge jobs with a scripted behaviour per site."""

    def __init__(self, behaviour):
        self.behaviour = behaviour  # site -> dict result | "silent" | callable
        self.jobs: list[dict] = []
        self.inflight: dict[str, int] = {}
        self.max_inflight: dict[str, int] = {}
        self.ws = None
        self.session = None

    async def connect(self, server: TestServer, token: str = TOKEN):
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(str(server.make_url("/ext")) + f"?token={token}")
        self.task = asyncio.create_task(self._loop())

    async def _loop(self):
        async for msg in self.ws:
            job = json.loads(msg.data)
            if job.get("type") != "job":
                continue
            self.jobs.append(job)
            asyncio.create_task(self._answer(job))

    async def _answer(self, job):
        site = job["site"]
        self.inflight[site] = self.inflight.get(site, 0) + 1
        self.max_inflight[site] = max(self.max_inflight.get(site, 0), self.inflight[site])
        try:
            b = self.behaviour.get(site, {"ok": True, "text": f"answer from {site}", "via": "copy-button"})
            if b == "silent":
                return
            await asyncio.sleep(0.2)
            if callable(b):
                b = b(job)
            await self.ws.send_json({"type": "result", "id": job["id"], **b})
        finally:
            self.inflight[site] -= 1

    async def close(self):
        if self.ws is not None:
            await self.ws.close()
        if self.session is not None:
            await self.session.close()


async def start(tmp_path, behaviour=None, connect=True, **bridge_kw):
    cfg = make_config(tmp_path, "http://unused/v1", [], guard=GuardConfig(min_spacing_s=0))
    logs: list[str] = []
    launched: list[bool] = []
    bridge = Bridge(cfg, TOKEN, timeout_s=bridge_kw.pop("timeout_s", 5), human_wait_s=0,
                    connect_wait_s=bridge_kw.pop("connect_wait_s", 1), launcher=lambda: launched.append(True),
                    log=logs.append, **bridge_kw)
    server = TestServer(bridge.app())
    await server.start_server()
    ext = FakeExtension(behaviour or {})
    if connect:
        await ext.connect(server)
        await asyncio.wait_for(bridge.connected.wait(), 2)
    return cfg, bridge, server, ext, logs, launched


async def post(server, model, content="hola", token=TOKEN, stream=False):
    async with aiohttp.ClientSession() as s:
        async with s.post(server.make_url("/v1/chat/completions"),
                          json={"model": model, "messages": [{"role": "user", "content": content}], "stream": stream},
                          headers={"Authorization": f"Bearer {token}"}) as r:
            return r.status, (await r.text()), dict(r.headers)


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ unit

def test_flatten_single_user_message_is_verbatim():
    assert flatten_messages([{"role": "user", "content": "hola\n\tmundo"}]) == "hola\n\tmundo"


def test_flatten_conversation_keeps_roles_and_order():
    text = flatten_messages([
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": [{"type": "text", "text": "q2"}]},
    ])
    assert text.index("SYSTEM INSTRUCTIONS") < text.index("q1") < text.index("a1") < text.index("q2")
    assert text.rstrip().endswith("following the SYSTEM INSTRUCTIONS.")


# ------------------------------------------------------------------ routes

def test_models_needs_token_and_lists_sites(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(server.make_url("/v1/models")) as r:
                    assert r.status == 401
                async with s.get(server.make_url("/v1/models"), headers={"Authorization": f"Bearer {TOKEN}"}) as r:
                    ids = [m["id"] for m in (await r.json())["data"]]
            assert ids == ["browser/qwen", "browser/deepseek", "browser/zai", "browser/meta"]
        finally:
            await ext.close(); await server.close()
    run(go())


def test_extension_with_bad_token_is_rejected(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, connect=False)
        try:
            async with aiohttp.ClientSession() as s:
                try:
                    await s.ws_connect(str(server.make_url("/ext")) + "?token=wrong")
                    assert False, "should have been rejected"
                except aiohttp.WSServerHandshakeError as exc:
                    assert exc.status == 401
            assert not bridge.connected.is_set()
        finally:
            await server.close()
    run(go())


def test_round_trip_json(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            status, body, headers = await post(server, "browser/qwen", "di hola")
            data = json.loads(body)
            assert status == 200
            assert data["choices"][0]["message"]["content"] == "answer from qwen"
            assert headers["x-webllm-site"] == "qwen" and headers["x-webllm-capture"] == "copy-button"
            assert ext.jobs[0]["prompt"] == "di hola" and ext.jobs[0]["site"] == "qwen"
        finally:
            await ext.close(); await server.close()
    run(go())


def test_round_trip_stream_sse(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            status, body, headers = await post(server, "browser/zai", stream=True)
            assert status == 200 and headers["Content-Type"].startswith("text/event-stream")
            events = [line[6:] for line in body.splitlines() if line.startswith("data: ")]
            assert events[-1] == "[DONE]"
            chunks = [json.loads(e) for e in events[:-1]]
            text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
            assert text == "answer from zai" and chunks[-1]["choices"][0]["finish_reason"] == "stop"
        finally:
            await ext.close(); await server.close()
    run(go())


def test_unknown_model_404(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            status, body, _ = await post(server, "browser/claude")
            assert status == 404 and ext.jobs == []
        finally:
            await ext.close(); await server.close()
    run(go())


# ------------------------------------------------------------------ failures and guard

def test_login_required_is_401_and_not_paused(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"deepseek": {"ok": False, "error": "login_required"}})
        try:
            s1, b1, _ = await post(server, "browser/deepseek")
            s2, _, _ = await post(server, "browser/deepseek")
            assert s1 == 401 and "Entra en DeepSeek" in json.loads(b1)["error"]["message"]
            assert s2 == 401 and len(ext.jobs) == 2  # next request goes through again
        finally:
            await ext.close(); await server.close()
    run(go())


def test_rate_limit_pauses_site_and_stops_sending(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"qwen": {"ok": False, "error": "rate_limited"}})
        try:
            s1, b1, _ = await post(server, "browser/qwen")
            s2, b2, _ = await post(server, "browser/qwen")
            s3, _, _ = await post(server, "browser/zai")
            assert s1 == 403 and "límite" in json.loads(b1)["error"]["message"]
            assert s2 == 403 and json.loads(b2)["error"]["code"] == "paused"
            assert [j["site"] for j in ext.jobs] == ["qwen", "zai"]  # qwen not contacted again
            assert s3 == 200
        finally:
            await ext.close(); await server.close()
    run(go())


def test_ban_pauses_long_and_tells_to_create_account(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"meta": {"ok": False, "error": "banned"}})
        try:
            s1, b1, _ = await post(server, "browser/meta")
            msg = json.loads(b1)["error"]["message"]
            assert s1 == 403 and "Crea otra" in msg
            until = bridge.guard.status()["meta"]["cooldown_until"]
            assert until - time.time() > 29 * 24 * 3600
        finally:
            await ext.close(); await server.close()
    run(go())


def test_unsolved_challenge_pauses(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"qwen": {"ok": False, "error": "challenge"}})
        try:
            s1, _, _ = await post(server, "browser/qwen")
            assert s1 == 403 and bridge.guard.status()["qwen"]["cooldown_until"] > time.time()
        finally:
            await ext.close(); await server.close()
    run(go())


def test_resume_lifts_pause(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"qwen": {"ok": False, "error": "rate_limited"}})
        try:
            await post(server, "browser/qwen")
            async with aiohttp.ClientSession() as s:
                async with s.post(server.make_url("/admin/resume"), json={},
                                  headers={"Authorization": f"Bearer {TOKEN}"}) as r:
                    assert (await r.json())["cleared"] == ["qwen"]
            ext.behaviour["qwen"] = {"ok": True, "text": "back", "via": "dom"}
            status, body, _ = await post(server, "browser/qwen")
            assert status == 200 and json.loads(body)["choices"][0]["message"]["content"] == "back"
        finally:
            await ext.close(); await server.close()
    run(go())


def test_timeout_is_504(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"zai": "silent"}, timeout_s=0.5)
        try:
            status, body, _ = await post(server, "browser/zai")
            assert status == 504
        finally:
            await ext.close(); await server.close()
    run(go())


def test_no_chrome_opens_it_and_returns_503(tmp_path):
    async def go():
        cfg, bridge, server, ext, logs, launched = await start(tmp_path, connect=False, connect_wait_s=0.3)
        try:
            status, body, _ = await post(server, "browser/qwen")
            assert status == 503 and launched == [True]
            assert "Chrome" in json.loads(body)["error"]["message"]
        finally:
            await server.close()
    run(go())


def test_disconnect_mid_job_returns_503(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path, {"qwen": "silent"}, timeout_s=5)
        try:
            task = asyncio.create_task(post(server, "browser/qwen"))
            await asyncio.sleep(0.3)
            await ext.close()
            status, _, _ = await asyncio.wait_for(task, 5)
            assert status == 503
        finally:
            await server.close()
    run(go())


def test_one_job_per_site_at_a_time_but_sites_in_parallel(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            t0 = time.perf_counter()
            results = await asyncio.gather(post(server, "browser/qwen"), post(server, "browser/qwen"),
                                           post(server, "browser/zai"), post(server, "browser/deepseek"))
            assert all(r[0] == 200 for r in results)
            assert ext.max_inflight["qwen"] == 1
            assert time.perf_counter() - t0 < 4 * 0.2 + 0.5  # the other sites overlapped
        finally:
            await ext.close(); await server.close()
    run(go())


# ------------------------------------------------------------------ through webllm ask

def test_webllm_ask_reaches_browser_sites_via_bridge(tmp_path, mock_server):
    async def go():
        _, bridge, server, ext, *_ = await start(tmp_path)
        try:
            cfg = make_config(tmp_path, mock_server.base_url, [
                ProviderConfig(name="qwen", model="browser/qwen", kind="browser", gateway="bridge"),
                ProviderConfig(name="groq", model="api/ok"),
            ])
            object.__setattr__(cfg, "bridge_port", server.port)
            guard = Guard(cfg.paths.state_dir / "guard.json", cfg.guard)
            outcomes = await broadcast(cfg, "hola", resolve_targets(cfg, "todas"), api_key="sk-test-key",
                                       guard=guard, notify=lambda m: None, bridge_key=TOKEN)
            by = {o.target.name: o.result for o in outcomes}
            assert by["qwen"].ok and by["qwen"].text == "answer from qwen"
            assert by["groq"].ok
            assert guard.status() == {}  # browser sites are guarded by the bridge, not twice
        finally:
            await ext.close(); await server.close()
    run(go())


# ------------------------------------------------------------------ panel page

def test_panel_page_served_locally_with_token_and_refuses_other_hosts(tmp_path):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(server.make_url("/")) as r:
                    html = await r.text()
                    assert r.status == 200 and TOKEN in html and "Probar todo" in html
                async with s.get(server.make_url("/"), headers={"Host": "evil.example"}) as r:
                    assert r.status == 403
                async with s.get(server.make_url("/panel/state")) as r:
                    assert r.status == 401
                async with s.get(server.make_url(f"/panel/state?token={TOKEN}")) as r:
                    st = await r.json()
            assert st["extension"] is True and st["extension_path"].endswith("extension")
        finally:
            await ext.close(); await server.close()
    run(go())


def test_panel_run_streams_real_checks_with_evidence(tmp_path, monkeypatch):
    import webllm_agent.selftest as selftest

    monkeypatch.setattr(selftest, "API_MODELS", [])
    monkeypatch.setattr(selftest, "_programming_run", lambda base, key, model: {
        "ok": True, "folder": "x", "task": "t", "test_code": "tc", "code_before": "a", "code_after": "b",
        "pytest_before": "1 failed", "pytest_after": "1 passed", "git_log": "abc fix"})

    async def go():
        behaviour = {s: {"ok": True, "text": "pong", "via": "copy-button"} for s in ("zai", "qwen", "deepseek")}
        behaviour["meta"] = {"ok": False, "error": "login_required"}
        cfg, bridge, server, ext, *_ = await start(tmp_path, behaviour)
        object.__setattr__(cfg, "bridge_port", server.port)
        load = selftest.load_token
        monkeypatch.setattr(selftest, "load_token", lambda d: TOKEN)
        monkeypatch.setattr(selftest, "AIDER", Path(__file__))  # "installed"
        try:
            events = []
            async with aiohttp.ClientSession() as s:
                async with s.get(server.make_url(f"/panel/run?token={TOKEN}"), timeout=aiohttp.ClientTimeout(total=60)) as r:
                    async for raw in r.content:
                        line = raw.decode().strip()
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))
            final = {e["id"]: e for e in events if e.get("state") in ("ok", "fail")}
            assert final["bridge"]["state"] == "ok" and final["chrome"]["state"] == "ok"
            assert final["chat:zai"]["state"] == "ok" and final["chat:zai"]["detail"]["answer"] == "pong"
            assert final["chat:meta"]["state"] == "fail" and "meta.ai" in final["chat:meta"]["message"]
            assert final["programar"]["state"] == "ok" and final["programar"]["detail"]["code_after"] == "b"
            assert "chat z.ai" in final["programar"]["title"].lower()
            assert events[-1]["kind"] == "done"
        finally:
            await ext.close(); await server.close()
    run(go())


def test_panel_ask_mixes_chrome_chats_and_api(tmp_path, mock_server):
    async def go():
        cfg, bridge, server, ext, *_ = await start(tmp_path)
        cfg2 = make_config(tmp_path, mock_server.base_url, [
            ProviderConfig(name="qwen", model="browser/qwen", kind="browser", gateway="bridge"),
            ProviderConfig(name="groq", model="api/ok"),
        ])
        object.__setattr__(cfg2, "bridge_port", server.port)
        bridge.cfg = cfg2
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(server.make_url("/panel/ask"), json={"prompt": "hola", "to": "todas"},
                                  headers={"Authorization": f"Bearer {TOKEN}"}) as r:
                    data = await r.json()
            by = {o["name"]: o for o in data["outcomes"]}
            assert by["qwen"]["ok"] and by["qwen"]["text"] == "answer from qwen"
            assert by["groq"]["ok"] and data["run_id"]
        finally:
            await ext.close(); await server.close()
    run(go())

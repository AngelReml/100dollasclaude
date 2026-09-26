"""Models on this PC (LM Studio / Ollama) as AIs "En tu PC": a fake LM Studio server, no network."""

from __future__ import annotations

import asyncio
import dataclasses
import json

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

from conftest import make_config
from test_appapi import AUTH, App, run
from webllm_agent.config import LocalServer, ProviderConfig, _coerce_local_servers
from webllm_agent.local import LocalModels


class FakeLMStudio:
    """GET /v1/models + POST /v1/chat/completions, recording what it receives."""

    def __init__(self, models=("qwen2.5-1.5b-instruct", "text-embedding-nomic-embed-text-v1.5", "claude-local")):
        self.models = list(models)
        self.requests: list[dict] = []
        self.inflight = 0
        self.max_inflight = 0

    def app(self) -> web.Application:
        async def models(request):
            return web.json_response({"object": "list", "data": [{"id": m, "object": "model"} for m in self.models]})

        async def chat(request):
            body = await request.json()
            self.requests.append({"model": body["model"], "auth": request.headers.get("Authorization")})
            self.inflight += 1
            self.max_inflight = max(self.max_inflight, self.inflight)
            try:
                await asyncio.sleep(0.3)
            finally:
                self.inflight -= 1
            return web.json_response({"id": "x", "object": "chat.completion", "model": body["model"],
                                      "choices": [{"index": 0, "message": {"role": "assistant",
                                                                           "content": f"local answer from {body['model']}"}}]})

        app = web.Application()
        app.router.add_get("/v1/models", models)
        app.router.add_post("/v1/chat/completions", chat)
        return app


async def start_fake(fake: FakeLMStudio) -> TestServer:
    server = TestServer(fake.app())
    await server.start_server()
    return server


def servers_at(url: str):
    return (LocalServer("lmstudio", "LM Studio", url, start=("lms", "server", "start")),)


# ------------------------------------------------------------------ discovery

def test_discovery_keeps_chat_models_and_remembers_them(tmp_path, mock_server):
    async def go():
        fake = FakeLMStudio()
        server = await start_fake(fake)
        cfg = dataclasses.replace(make_config(tmp_path, mock_server.base_url, []),
                                  local_servers=servers_at(str(server.make_url("/v1"))))
        local = LocalModels(ttl=0, launcher=None)
        (st,) = await local.refresh(cfg)
        assert st.up and st.models == ["qwen2.5-1.5b-instruct"]  # no embeddings, no "claude"
        p = local.providers()["lmstudio:qwen2.5-1.5b-instruct"]
        assert (p.kind, p.gateway, p.model, p.remote_model, p.display) == (
            "local", "local", "lmstudio/qwen2.5-1.5b-instruct", "qwen2.5-1.5b-instruct",
            "LM Studio · qwen2.5-1.5b-instruct")
        assert json.loads((cfg.paths.state_dir / "local_models.json").read_text()) == {
            "lmstudio": ["qwen2.5-1.5b-instruct"]}
        await server.close()
        (st,) = await local.refresh(cfg)  # LM Studio closed: the model is still known
        assert not st.up and st.models == ["qwen2.5-1.5b-instruct"] and st.installed
        assert "lmstudio:qwen2.5-1.5b-instruct" in local.providers()
    run(go())


def test_config_adds_lmstudio_and_ollama_and_lets_you_change_them():
    keys = [s.key for s in _coerce_local_servers(None)]
    assert keys == ["lmstudio", "ollama"]
    servers = _coerce_local_servers([{"key": "ollama", "enabled": False},
                                     {"key": "casa", "name": "Mi servidor", "url": "http://127.0.0.1:8080/v1/"}])
    assert [(s.key, s.url) for s in servers] == [("lmstudio", "http://127.0.0.1:1234/v1"),
                                                 ("casa", "http://127.0.0.1:8080/v1")]


def test_start_runs_the_program_once_and_says_when_it_is_missing(tmp_path, mock_server):
    started: list[list[str]] = []
    cfg = dataclasses.replace(make_config(tmp_path, mock_server.base_url, []),
                              local_servers=servers_at("http://127.0.0.1:9/v1") + (
                                  LocalServer("nada", "Nada", "http://127.0.0.1:9/v1"),))
    local = LocalModels(launcher=started.append)
    assert local.start(cfg, "lmstudio") == "started" and started == [["lms", "server", "start"]]
    assert local.start(cfg, "lmstudio") == "recent" and len(started) == 1
    assert local.start(cfg, "nada") == "not_installed"


# ------------------------------------------------------------------ in the app

class LocalApp(App):
    """The app with a fake LM Studio as the only program on this PC."""

    def __init__(self, tmp_path, base_url, fake=None, **kw):
        super().__init__(tmp_path, base_url, **kw)
        self.fake = fake or FakeLMStudio()
        self.started: list[list[str]] = []

    async def __aenter__(self):
        self.fake_server = await start_fake(self.fake)
        await super().__aenter__()
        self.bridge.cfg = dataclasses.replace(self.cfg, local_servers=servers_at(str(self.fake_server.make_url("/v1"))))
        self.cfg = self.bridge.cfg
        self.bridge.app_api.local = LocalModels(ttl=0, launcher=self.started.append)
        return self

    async def __aexit__(self, *exc):
        await super().__aexit__(*exc)
        await self.fake_server.close()


def test_local_models_show_in_status_and_answer(tmp_path, mock_server):
    async def go():
        async with LocalApp(tmp_path, mock_server.base_url) as a:
            _, body, _ = await a.get("/api/estado")
            local = [x for x in body["ais"] if x["kind"] == "local"]
            assert local == [{
                "name": "lmstudio:qwen2.5-1.5b-instruct", "label": "LM Studio · qwen2.5-1.5b-instruct", "kind": "local",
                "state": "lista", "detail": "", "until": None, "url": None, "today": 0, "cap": None,
                "server": "lmstudio", "server_name": "LM Studio", "custom": False, "icon": False, "waiting": None,
                "catalog": False}]
            assert body["local_servers"] == [{"key": "lmstudio", "name": "LM Studio", "up": True, "installed": True,
                                              "models": 1}]
            status, events = await a.ask("hola", ["lmstudio:qwen2.5-1.5b-instruct", "zai"])
            done = {e["target"]: e for e in events if e["type"] == "target_done"}
            assert done["lmstudio:qwen2.5-1.5b-instruct"]["text"] == "local answer from qwen2.5-1.5b-instruct"
            assert done["zai"]["ok"] and events[-1]["verified"]
            assert a.fake.requests == [{"model": "qwen2.5-1.5b-instruct", "auth": None}]  # its own id, no key
            _, hist, _ = await a.get("/api/historial")
            assert "LM Studio · qwen2.5-1.5b-instruct" in [x["label"] for x in hist["runs"][0]["ais"]]
    run(go())


def test_one_question_at_a_time_per_program(tmp_path, mock_server):
    async def go():
        async with LocalApp(tmp_path, mock_server.base_url) as a:
            await a.get("/api/estado")
            await asyncio.gather(a.ask("uno", ["lmstudio:qwen2.5-1.5b-instruct"]),
                                 a.ask("dos", ["lmstudio:qwen2.5-1.5b-instruct"]))
            assert len(a.fake.requests) == 2 and a.fake.max_inflight == 1
    run(go())


def test_program_off_shows_apagada_and_the_start_button_works(tmp_path, mock_server):
    async def go():
        async with LocalApp(tmp_path, mock_server.base_url) as a:
            await a.get("/api/estado")  # seen once: remembered
            await a.fake_server.close()
            _, body, _ = await a.get("/api/estado")
            (ai,) = [x for x in body["ais"] if x["kind"] == "local"]
            assert ai["state"] == "apagada" and body["local_servers"][0]["up"] is False
            _, events = await a.ask("hola", ["lmstudio:qwen2.5-1.5b-instruct"])
            done = [e for e in events if e["type"] == "target_done"][0]
            assert not done["ok"] and done["code"] == "unreachable"
            status, res = await a.post("/api/encender-local", {"server": "lmstudio"})
            assert status == 200 and res == {"ok": True, "already": False}
            assert a.started == [["lms", "server", "start"]]
            status, res = await a.post("/api/encender-local", {"server": "no-existe"})
            assert status == 404 and res["code"] == "not_installed"
    run(go())


def test_start_when_already_running_does_nothing(tmp_path, mock_server):
    async def go():
        async with LocalApp(tmp_path, mock_server.base_url) as a:
            assert (await a.post("/api/encender-local", {"server": "lmstudio"}))[1] == {"ok": True, "already": True}
            assert a.started == []
    run(go())


def test_without_programs_nothing_local_shows(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:  # make_config: no local servers
            _, body, _ = await a.get("/api/estado")
            assert body["local_servers"] == [] and all(x["kind"] != "local" for x in body["ais"])
    run(go())


def test_local_ai_is_not_skipped_when_omniroute_is_off(tmp_path):
    async def go():
        async with LocalApp(tmp_path, "http://127.0.0.1:9/v1") as a:
            await a.get("/api/estado")
            _, events = await a.ask("hola", ["lmstudio:qwen2.5-1.5b-instruct"])
            assert [e["ok"] for e in events if e["type"] == "target_done"] == [True]
    run(go())


def test_a_model_on_this_pc_answers_through_the_gateway(tmp_path, mock_server):
    """PLAN-v5 F2: Open WebUI asks a model on this PC through webllm's gateway. It answers (even though the
    program answers the stream request with one JSON), with its own id and no key, one question at a time,
    uncapped, said and journaled like any other."""
    from test_gateway import content, gw, journal_lines
    from webllm_agent.broadcaster import verify_run

    name = "lmstudio:qwen2.5-1.5b-instruct"
    ask = {"model": name, "stream": True, "messages": [{"role": "user", "content": "hola"}]}

    async def go():
        async with LocalApp(tmp_path, mock_server.base_url) as a:
            status, models, _ = await a.get("/gw/v1/models")
            assert [m["name"] for m in models["data"] if m["webllm"]["kind"] == "local"] == ["LM Studio · qwen2.5-1.5b-instruct (tu PC)"]
            first, second = await asyncio.gather(gw(a, ask), gw(a, ask))
            (s1, lines, headers), s2 = first, second[0]
            assert s1 == s2 == 200 and content(lines) == "local answer from qwen2.5-1.5b-instruct"
            avisos = [x for x in lines if isinstance(x, dict) and x.get("webllm")][-1]["webllm"]["avisos"]
            assert avisos == ["Respondió LM Studio · qwen2.5-1.5b-instruct."]  # its name already says the model
            assert a.fake.requests == [{"model": "qwen2.5-1.5b-instruct", "auth": None}] * 2 and a.fake.max_inflight == 1
            call = next(x for x in journal_lines(a, headers["x-webllm-run"]) if x["kind"] == "flow")
            assert call["status"] == "ok" and call["provider"] == name
            assert verify_run(a.cfg.paths.runs_dir / headers["x-webllm-run"]).ok
            _, models, _ = await a.get("/gw/v1/models")
            local = next(m for m in models["data"] if m["id"] == name)["webllm"]
            assert local["daily_cap"] is None  # no quota to protect on this PC
    run(go())

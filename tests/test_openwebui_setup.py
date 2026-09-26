"""scripts/openwebui_setup.py against a fake Open WebUI admin API (the real one is checked on screen by
tests/openwebui/f1_checks.mjs): what it installs, how it sets each webllm model, and that running it
twice changes nothing twice."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import openwebui_setup as setup  # noqa: E402


class FakeOpenWebUI:
    def __init__(self, models=("webllm.qwen", "webllm.zai")):
        self.functions: dict[str, dict] = {}
        self.models: dict[str, dict] = {}
        self.pipe_models = list(models)
        self.valves: dict = {}
        self.tasks = {"ENABLE_TITLE_GENERATION": True, "ENABLE_TAGS_GENERATION": True, "ENABLE_FOLLOW_UP_GENERATION": True,
                      "ENABLE_AUTOCOMPLETE_GENERATION": True, "ENABLE_SEARCH_QUERY_GENERATION": True,
                      "ENABLE_RETRIEVAL_QUERY_GENERATION": True, "TASK_MODEL": ""}
        self.chat = {"ENABLE_TOOL_PERMISSIONS": False, "ENABLE_CONTEXT_COMPACTION": True}
        self.config: dict = {}
        self.settings = {"ui": {"theme": "dark", "params": {"temperature": 0.5}}}  # Iván's own choices
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append(f"{method} {path}")
        body = json.loads(request.content) if request.content else None
        if request.headers.get("Authorization") != "Bearer clave":
            return httpx.Response(401)
        if path == "/api/v1/functions/":
            return httpx.Response(200, json=list(self.functions.values()))
        if path == "/api/v1/functions/create":
            self.functions[body["id"]] = {**body, "is_active": False}
            return httpx.Response(200, json=body)
        if path.startswith("/api/v1/functions/id/"):
            fid, *rest = path[len("/api/v1/functions/id/"):].split("/")
            if rest == ["update"]:
                self.functions[fid].update(body)
            elif rest == ["toggle"]:
                self.functions[fid]["is_active"] = not self.functions[fid]["is_active"]
            elif rest == ["valves", "update"]:
                self.valves[fid] = body
            return httpx.Response(200, json=self.functions[fid])
        if path == "/api/models":
            return httpx.Response(200, json={"data": [{"id": m, "name": m} for m in self.pipe_models]})
        if path == "/api/v1/models/model":
            got = self.models.get(request.url.params["id"])
            return httpx.Response(200, json=got) if got else httpx.Response(404, json={"detail": "not found"})
        if path in ("/api/v1/models/create", "/api/v1/models/model/update"):
            self.models[body["id"]] = body
            return httpx.Response(200, json=body)
        if path == "/api/v1/tasks/config":
            return httpx.Response(200, json=dict(self.tasks))
        if path == "/api/v1/tasks/config/update":
            self.tasks = body
            return httpx.Response(200, json=body)
        if path == "/api/v1/chats/config":
            if method == "POST":
                self.chat = body
            return httpx.Response(200, json=dict(self.chat))
        if path == "/api/v1/users/user/settings":
            return httpx.Response(200, json=self.settings)
        if path == "/api/v1/users/user/settings/update":
            self.settings = body
            return httpx.Response(200, json=body)
        if path in ("/api/v1/retrieval/config/update", "/api/v1/configs/suggestions", "/api/v1/evaluations/config"):
            self.config[path] = body
            return httpx.Response(200, json=body)
        return httpx.Response(404)


MODES = ["webllm_buscar", "webllm_constructor", "webllm_imagen", "webllm_investigar", "webllm_pensar"]

def run_install(fake: FakeOpenWebUI):
    ow = setup.OpenWebUI("http://ow.test", "clave", transport=httpx.MockTransport(fake.handler))
    known = {m: {"name": f"Nombre de {m}", "card": f"Ficha de {m}"} for m in fake.pipe_models}
    return setup.install(ow, "http://127.0.0.1:20130", "llave-webllm", say=lambda _m: None, known=known)


def test_installs_the_pipe_and_the_switches_active_with_webllms_key():
    fake = FakeOpenWebUI()
    run_install(fake)
    assert set(fake.functions) == {"webllm", *MODES}
    assert all(f["is_active"] for f in fake.functions.values())
    assert fake.valves["webllm"] == {"WEBLLM_URL": "http://127.0.0.1:20130", "WEBLLM_TOKEN": "llave-webllm"}
    assert fake.functions["webllm"]["content"] == (ROOT / "openwebui" / "webllm_pipe.py").read_text("utf-8")


def test_every_webllm_model_gets_whole_files_and_its_switches():
    fake = FakeOpenWebUI()
    run_install(fake)
    assert set(fake.models) == {"webllm.qwen", "webllm.zai"}
    for m in fake.models.values():
        assert m["name"] == f"Nombre de {m['id']}" and m["meta"]["description"] == f"Ficha de {m['id']}"
        caps = m["meta"]["capabilities"]
        assert caps["file_context"] is False and caps["vision"] is True and caps["file_upload"] is True
        assert caps["builtin_tools"] is False  # only the tools Iván switches on
        assert m["meta"]["filterIds"] == sorted(MODES)  # every switch of the "+" (PLAN-v5 F4)
    assert fake.config["/api/v1/retrieval/config/update"] == {"BYPASS_EMBEDDING_AND_RETRIEVAL": True}
    assert fake.config["/api/v1/evaluations/config"] == {"ENABLE_EVALUATION_ARENA_MODELS": False}


def test_background_jobs_that_would_spend_messages_are_off():
    fake = FakeOpenWebUI()
    run_install(fake)
    assert fake.tasks["ENABLE_TITLE_GENERATION"] is True  # titles stay: the pipe makes them itself
    assert not any(fake.tasks[k] for k in setup.TASKS_OFF)
    assert fake.chat == {"ENABLE_TOOL_PERMISSIONS": True, "ENABLE_CONTEXT_COMPACTION": False}


def test_running_it_again_updates_and_duplicates_nothing():
    fake = FakeOpenWebUI()
    run_install(fake)
    first = sorted(fake.calls)
    fake.calls.clear()
    run_install(fake)
    assert "POST /api/v1/functions/create" not in fake.calls and "POST /api/v1/models/create" not in fake.calls
    assert fake.calls.count("POST /api/v1/functions/id/webllm/toggle") == 0  # still active: not switched off
    assert len(fake.functions) == 1 + len(MODES) and len(fake.models) == 2 and first


def test_it_refuses_when_webllm_is_not_answering():
    fake = FakeOpenWebUI(models=("webllm.apagado",))
    try:
        run_install(fake)
    except SystemExit as exc:
        assert "webllm no contesta" in str(exc)
    else:
        raise AssertionError("it configured a model that says webllm is off")
    assert fake.models == {}


def test_frontmatter_reads_the_header_of_each_function():
    meta = setup.frontmatter((ROOT / "openwebui" / "webllm_modo_pensar.py").read_text("utf-8"))
    assert meta["title"] == "Pensar más" and meta["required_open_webui_version"] == "0.11.0"



def test_every_conversation_asks_before_using_a_tool_and_ivans_settings_stay():
    fake = FakeOpenWebUI()
    run_install(fake)
    assert fake.settings["ui"]["params"] == {"temperature": 0.5, "tool_approval_mode": "ask"}
    assert fake.settings["ui"]["theme"] == "dark"

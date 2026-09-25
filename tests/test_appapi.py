"""App API tests: the real bridge in-process, a fake Chrome extension and the mock OmniRoute."""

from __future__ import annotations

import asyncio
import json

import aiohttp
from aiohttp.test_utils import TestServer

from conftest import make_config
from test_bridge import TOKEN, FakeExtension
from webllm_agent.bridge import Bridge
from webllm_agent.broadcaster import write_run
from webllm_agent.client import ChatResult
from webllm_agent.broadcaster import Outcome
from webllm_agent.config import GuardConfig, ProviderConfig

AUTH = {"Authorization": f"Bearer {TOKEN}"}


class DiagnosingExtension(FakeExtension):
    """Also answers "diagnose" jobs with a page state."""

    def __init__(self, behaviour, page_state=None, knows_show=True):
        super().__init__(behaviour)
        self.page_state = page_state or {"input": True, "loginWall": False, "challenge": None}
        self.knows_show = knows_show  # False = an extension older than 0.4.0
        self.shown: list[str] = []

    async def _loop(self):
        async for msg in self.ws:
            job = json.loads(msg.data)
            if job.get("type") == "show" and self.knows_show:
                self.shown.append(job["site"])
                await self.ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "show"})
            elif job.get("type") == "diagnose":
                await self.ws.send_json({"type": "result", "id": job["id"], "ok": True,
                                         "text": json.dumps({"state": self.page_state})})
            elif job.get("type") == "job":
                self.jobs.append(job)
                asyncio.create_task(self._answer(job))


def providers():
    return [
        ProviderConfig(name="qwen", model="browser/qwen", kind="browser", gateway="bridge"),
        ProviderConfig(name="zai-chat", model="browser/zai", kind="browser", gateway="bridge"),
        ProviderConfig(name="zai", model="z/ok"),
    ]


class App:
    """Bridge + fake extension on a real port; base_url of the mock OmniRoute (or a dead one)."""

    def __init__(self, tmp_path, base_url, behaviour=None, page_state=None, app_dir=None, connect=True,
                 knows_show=True):
        self.tmp_path, self.base_url, self.connect = tmp_path, base_url, connect
        self.behaviour, self.page_state, self.app_dir = behaviour or {}, page_state, app_dir
        self.knows_show = knows_show
        self.launched: list[bool] = []

    async def __aenter__(self):
        cfg = make_config(self.tmp_path, self.base_url, providers(), guard=GuardConfig(min_spacing_s=0))
        self.bridge = Bridge(cfg, TOKEN, timeout_s=5, human_wait_s=0, connect_wait_s=0.5, launcher=None,
                             log=lambda m: None)
        self.bridge.app_api.omniroute_launcher = lambda: self.launched.append(True)
        self.bridge.app_api.show_wait_s = 0.5
        if self.app_dir is not None:
            self.bridge.app_api.app_dir = self.app_dir
        self.server = TestServer(self.bridge.app())
        await self.server.start_server()
        object.__setattr__(cfg, "bridge_port", self.server.port)
        self.cfg = cfg
        self.ext = DiagnosingExtension(self.behaviour, self.page_state, self.knows_show)
        if self.connect:
            await self.ext.connect(self.server)
            await asyncio.wait_for(self.bridge.connected.wait(), 2)
        self.http = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *exc):
        await self.http.close()
        await self.ext.close()
        await self.server.close()

    def url(self, path):
        return self.server.make_url(path)

    async def get(self, path, headers=AUTH):
        async with self.http.get(self.url(path), headers=headers) as r:
            return r.status, (await r.json() if r.content_type == "application/json" else await r.text()), r.headers

    async def post(self, path, body, headers=AUTH):
        async with self.http.post(self.url(path), json=body, headers=headers) as r:
            return r.status, await r.json()

    async def ask(self, prompt, to, **extra):
        events = []
        async with self.http.post(self.url("/api/preguntar"), json={"prompt": prompt, "to": to, **extra},
                                  headers=AUTH) as r:
            if r.content_type == "application/json":
                return r.status, await r.json()
            async for raw in r.content:
                line = raw.decode("utf-8").strip()
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        return r.status, events


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ page

def test_app_page_gets_the_token_and_a_strict_policy(tmp_path, mock_server):
    app_dir = tmp_path / "app"
    (app_dir / "assets").mkdir(parents=True)
    (app_dir / "index.html").write_text('<meta name="webllm-token" content="__WEBLLM_TOKEN__">', encoding="utf-8")
    (app_dir / "assets" / "main.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")

    async def go():
        async with App(tmp_path, mock_server.base_url, app_dir=app_dir) as a:
            status, html, headers = await a.get("/app/", headers={})
            assert status == 200 and f'content="{TOKEN}"' in html
            assert "script-src 'self'" in headers["Content-Security-Policy"]
            assert headers["X-Frame-Options"] == "DENY" and headers["Cache-Control"] == "no-store"
            status, js, _ = await a.get("/app/assets/main.js", headers={})
            assert status == 200 and js == "console.log(1)"
            async with a.http.get(a.url("/app"), allow_redirects=False) as r:
                assert r.status == 302 and r.headers["Location"] == "/app/"
            for bad in ("/app/../secret.txt", "/app/%2e%2e/secret.txt", "/app/assets/nope.js"):
                async with a.http.get(str(a.url("/")) + bad.lstrip("/")) as r:
                    assert r.status == 404, bad
    run(go())


def test_missing_build_says_what_to_do(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, app_dir=tmp_path / "nothing") as a:
            status, html, _ = await a.get("/app/", headers={})
            assert status == 503 and "ACTUALIZAR" in html
    run(go())


# ------------------------------------------------------------------ status

def test_status_needs_the_token(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            status, body, _ = await a.get("/api/estado", headers={})
            assert status == 401 and body["code"] == "unauthorized"
    run(go())


def test_status_traffic_lights(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            status, body, _ = await a.get("/api/estado")
            assert status == 200 and body["chrome"] and body["omniroute"]
            states = {x["name"]: x for x in body["ais"]}
            assert [x["name"] for x in body["ais"]] == ["qwen", "zai-chat", "zai"]
            assert states["qwen"]["state"] == "lista" and states["qwen"]["kind"] == "chat"
            assert states["qwen"]["url"] == "https://chat.qwen.ai/" and states["zai"]["kind"] == "api"
            assert states["zai-chat"]["label"] == "z.ai (chat)"
            a.bridge.guard.trip(ProviderConfig(name="qwen", model="browser/qwen", kind="browser"), "límite", 1)
            _, body, _ = await a.get("/api/estado")
            qwen = body["ais"][0]
            assert qwen["state"] == "en_pausa" and qwen["detail"] == "límite" and qwen["until"]
            status, res = await a.post("/api/reanudar", {"ia": "qwen"})
            assert status == 200 and res["cleared"]
            _, body, _ = await a.get("/api/estado")
            assert body["ais"][0]["state"] == "lista"
    run(go())


def test_status_without_chrome_or_omniroute(tmp_path):
    async def go():
        async with App(tmp_path, "http://127.0.0.1:9/v1", connect=False) as a:
            _, body, _ = await a.get("/api/estado")
            states = {x["name"]: x["state"] for x in body["ais"]}
            assert states == {"qwen": "sin_chrome", "zai-chat": "sin_chrome", "zai": "apagada"}
            status, res = await a.post("/api/encender-omniroute", {})
            assert status == 200 and res == {"ok": True, "already": False} and a.launched == [True]
            await a.post("/api/encender-omniroute", {})
            assert a.launched == [True]  # at most once a minute
    run(go())


# ------------------------------------------------------------------ ask + history

def test_ask_streams_progress_and_lands_in_history(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            status, events = await a.ask("¿té o café?", ["qwen", "zai"])
            assert status == 200
            kinds = [e["type"] for e in events]
            assert kinds[0] == "flow_start" and kinds[-1] == "flow_done"
            assert kinds.count("target_start") == 2 and kinds.count("target_done") == 2
            done = {e["target"]: e for e in events if e["type"] == "target_done"}
            assert done["qwen"]["text"] == "answer from qwen" and done["zai"]["text"] == "answer from z/ok"
            assert events[-1]["status"] == "ok" and events[-1]["verified"] is True
            run_id = events[-1]["run_id"]

            _, hist, _ = await a.get("/api/historial")
            (item,) = hist["runs"]
            assert item["id"] == run_id and item["kind"] == "pregunta" and item["lock"] is True
            assert item["text"] == "¿té o café?" and [x["label"] for x in item["ais"]] == ["Qwen", "z.ai"]
            _, hist, _ = await a.get("/api/historial?q=CAFÉ")
            assert len(hist["runs"]) == 1
            _, hist, _ = await a.get("/api/historial?q=answer%20from%20qwen")
            assert len(hist["runs"]) == 1
            _, hist, _ = await a.get("/api/historial?q=nada-de-esto")
            assert hist["runs"] == []

            _, detail, _ = await a.get(f"/api/historial/{run_id}")
            assert detail["lock"] and detail["steps"][0]["message"] == "¿té o café?"
            assert [x["text"] for x in detail["steps"][0]["answers"]] == ["answer from qwen", "answer from z/ok"]

            async with a.http.get(a.url(f"/api/historial/{run_id}/exportar?token={TOKEN}")) as r:
                md = await r.text()
                assert r.status == 200 and "attachment" in r.headers["Content-Disposition"]
            assert md.startswith("# Pregunta") and "### Qwen" in md and "answer from z/ok" in md
            status, _, _ = await a.get("/api/historial/..%2f..%2fetc")
            assert status == 404
    run(go())


def test_pass_it_on_keeps_its_own_title(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            _, events = await a.ask("Mira lo que dijo Qwen: ...", ["zai"], title="Qwen → z.ai")
            _, hist, _ = await a.get("/api/historial")
            assert hist["runs"][0]["title"] == "Qwen → z.ai" and events[-1]["status"] == "ok"
    run(go())


def test_ask_with_omniroute_off_still_asks_the_chats(tmp_path):
    async def go():
        async with App(tmp_path, "http://127.0.0.1:9/v1") as a:
            status, events = await a.ask("hola", ["qwen", "zai"])
            done = {e["target"]: e for e in events if e["type"] == "target_done"}
            assert done["zai"]["code"] == "unreachable" and not done["zai"]["ok"]
            assert done["qwen"]["ok"]
            status, body = await a.ask("hola", ["zai"])
            assert status == 503 and body["code"] == "unreachable"
    run(go())


def test_ask_refuses_bad_requests(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            assert (await a.ask("  ", ["qwen"]))[1]["code"] == "empty"
            assert (await a.ask("hola", []))[1]["code"] == "no_target"
            assert (await a.ask("hola", ["claude"]))[1]["code"] == "unknown_target"
            async with a.http.post(a.url("/api/preguntar"), json={"prompt": "x", "to": ["qwen"]}) as r:
                assert r.status == 401
        assert mock_server.requests == []
    run(go())


def test_failed_chat_turns_its_light_red_until_it_answers(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url,
                       behaviour={"qwen": {"ok": False, "error": "login_required"}}) as a:
            _, events = await a.ask("hola", ["qwen"])
            done = [e for e in events if e["type"] == "target_done"][0]
            assert done["code"] == "login_required" and "sesión" in done["error"]
            _, body, _ = await a.get("/api/estado")
            assert body["ais"][0]["state"] == "sin_sesion"
            a.ext.behaviour.clear()
            await a.ask("hola", ["qwen"])
            _, body, _ = await a.get("/api/estado")
            assert body["ais"][0]["state"] == "lista"
    run(go())


def test_session_check_sends_nothing(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, page_state={"input": False, "loginWall": True}) as a:
            status, res = await a.post("/api/comprobar", {"ia": "qwen"})
            assert status == 200 and res == {"session": "sin_sesion"} and a.ext.jobs == []
            a.ext.page_state = {"input": True, "loginWall": False}
            assert (await a.post("/api/comprobar", {"ia": "qwen"}))[1] == {"session": "lista"}
            a.ext.page_state = {"input": True, "challenge": "slider"}
            assert (await a.post("/api/comprobar", {"ia": "qwen"}))[1] == {"session": "verificacion"}
            assert (await a.post("/api/comprobar", {"ia": "zai"}))[0] == 404
    run(go())


def test_connect_brings_the_login_forward_and_then_turns_green(tmp_path, mock_server):
    """The "Conectar" flow: no session -> window forward; the app polls until the session is there."""
    async def go():
        async with App(tmp_path, mock_server.base_url, page_state={"input": False, "loginWall": True}) as a:
            status, res = await a.post("/api/conectar", {"ia": "qwen"})
            assert status == 200 and res == {"session": "sin_sesion", "shown": True}
            assert a.ext.shown == ["qwen"] and a.ext.jobs == []  # nothing was sent to the chat
            _, body, _ = await a.get("/api/estado")
            assert body["ais"][0]["state"] == "sin_sesion"
            a.ext.page_state = {"input": True, "loginWall": False}  # Iván logs in
            assert (await a.post("/api/comprobar", {"ia": "qwen"}))[1] == {"session": "lista"}
            _, body, _ = await a.get("/api/estado")
            assert body["ais"][0]["state"] == "lista"
            assert a.ext.shown == ["qwen"]  # polling never pulls the window forward again
    run(go())


def test_connect_with_a_session_does_not_touch_the_window(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            assert (await a.post("/api/conectar", {"ia": "zai-chat"}))[1] == {"session": "lista", "shown": False}
            assert a.ext.shown == []
            assert (await a.post("/api/conectar", {"ia": "zai"}))[0] == 404  # an API AI has no page
    run(go())


def test_connect_with_an_old_extension_says_it_could_not_show(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url, page_state={"input": False, "loginWall": True},
                       knows_show=False) as a:
            assert (await a.post("/api/conectar", {"ia": "qwen"}))[1] == {"session": "sin_sesion", "shown": False}
    run(go())


def test_history_reads_old_ask_runs_and_flags_tampering(tmp_path, mock_server):
    async def go():
        async with App(tmp_path, mock_server.base_url) as a:
            outcome = Outcome(ProviderConfig(name="zai", model="z/ok"), ChatResult("ok", text="hola", model="z/ok"))
            write_run(a.cfg.paths.runs_dir, "20260924-101010-abcd", "pregunta vieja", [outcome])
            _, events = await a.ask("nueva", ["zai"])
            _, hist, _ = await a.get("/api/historial")
            assert [r["text"] for r in hist["runs"]] == ["nueva", "pregunta vieja"]
            assert all(r["lock"] for r in hist["runs"])
            resp = next((a.cfg.paths.runs_dir / events[-1]["run_id"] / "responses").iterdir())
            resp.write_text("cambiado", encoding="utf-8")
            _, hist, _ = await a.get("/api/historial")
            assert [r["lock"] for r in hist["runs"]] == [False, True]
    run(go())


def test_the_compiled_app_is_in_the_repo():
    """Iván's PC never runs npm: the built app must be committed (cd app && npm run build)."""
    from webllm_agent.appapi import APP_DIR
    index = (APP_DIR / "index.html").read_text(encoding="utf-8")
    assert "__WEBLLM_TOKEN__" in index
    scripts = [line for line in index.splitlines() if "<script" in line]
    assert scripts and all('src="/app/assets/' in line for line in scripts)  # no inline code (CSP)
    for name in [part.split('"')[0] for part in index.split("/app/assets/")[1:]]:
        assert (APP_DIR / "assets" / name).is_file(), name

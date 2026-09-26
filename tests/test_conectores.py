"""PLAN-v5 F3 "Conectar varias": the real bridge + app API, a fake extension over a real WebSocket that plays
the part of extension 0.6.0 (and of Iván: his permission click, his login)."""

from __future__ import annotations

import asyncio
import json
import time

from test_appapi import App, DiagnosingExtension, run
from webllm_agent import catalog


class ConnectingExtension(DiagnosingExtension):
    """add_many: acknowledges and (as Iván) answers Chrome's permission prompt once.
    add_check: plays each site by `sites[key]`: ok | login (logs in after a moment) | login_never | nobox |
    moved | hang (until cancelled). Its "pong" test answers pong."""

    def __init__(self, sites, grant=True, knows_many=True):
        super().__init__({k: {"ok": True, "text": "**pong**", "via": "copy-button"} for k in sites})
        self.sites, self.grant, self.knows_many = sites, grant, knows_many
        self.many: list[dict] = []
        self.checks: list[tuple[str, float, float]] = []  # (key, started, finished)
        self.cancels: list[str] = []

    async def _loop(self):
        async for msg in self.ws:
            job = json.loads(msg.data)
            self.seen.append(job)
            if job.get("type") == "add_many" and self.knows_many:
                self.many.append(job)
                await self.ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "add_many"})
                await asyncio.sleep(0.1)  # Iván reads the list and clicks
                await self.ws.send_json({"type": "add_many_permission", "batch_id": job["batch_id"], "ok": self.grant})
            elif job.get("type") == "add_check":
                await self.ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "add_check"})
                asyncio.create_task(self._check(job))
            elif job.get("type") == "cancel":
                self.cancels.append(job["id"])
            elif job.get("type") == "job":
                self.jobs.append(job)
                asyncio.create_task(self._answer(job))

    async def _check(self, job):
        key, add_id, t0 = job["key"], job["add_id"], time.monotonic()
        send = self.ws.send_json

        async def progress(step, ok, text):
            await send({"type": "add_progress", "add_id": add_id, "step": step, "ok": ok, "text": text})

        how = self.sites[key]
        await progress("open", True, "Web abierta")
        if how == "login":
            await progress("login", None, "Te espera: entra con tu cuenta en la ventanita de webllm (hasta 3 minutos)")
            await asyncio.sleep(0.3)  # Iván logs in
            await progress("login", True, "Has entrado")
        if how in ("ok", "login"):
            await progress("input", True, "Caja de texto: encontrada")
            await send({"type": "add_ready", "add_id": add_id, "icon": None})
        elif how == "login_never":
            await progress("login", None, "Te espera: entra con tu cuenta")
            await asyncio.sleep(job["wait_login_s"])
            await send({"type": "add_done", "add_id": add_id, "ok": False, "error": "login_required", "detail": "x"})
        elif how == "nobox":
            await send({"type": "add_done", "add_id": add_id, "ok": False, "error": "no_input",
                        "detail": json.dumps({"inputs": 0, "buttons": 3, "url": job["url"]})})
        elif how == "moved":
            await send({"type": "add_done", "add_id": add_id, "ok": False, "error": "moved",
                        "detail": "https://otra.example/chat"})
        elif how == "hang":
            while add_id not in self.cancels:
                await asyncio.sleep(0.05)
            await send({"type": "add_done", "add_id": add_id, "ok": False, "error": "cancelled"})
        self.checks.append((key, t0, time.monotonic()))


class ConnApp(App):
    def __init__(self, tmp_path, base_url, sites, **kw):
        super().__init__(tmp_path, base_url)
        self.sites, self.kw = sites, kw

    async def __aenter__(self):
        await super().__aenter__()
        await self.ext.close()
        self.ext = ConnectingExtension(self.sites, **self.kw)
        await self.ext.connect(self.server)
        await asyncio.wait_for(self.bridge.connected.wait(), 2)
        self.bridge.app_api.login_wait_s = 0.5
        self.bridge.app_api.ack_wait_s = 0.5
        return self

    async def until_done(self, batch_id):
        for _ in range(200):
            _, b, _ = await self.get(f"/api/conectar-varias/{batch_id}")
            if b["status"] not in ("permission", "running"):
                return b
            await asyncio.sleep(0.05)
        raise AssertionError(f"«Conectar varias» never finished: {b}")

    async def catalog_row(self, key):
        _, cat, _ = await self.get("/api/catalogo")
        return next(x for x in cat["ais"] if x["key"] == key)


def test_conectar_varias_one_permission_one_by_one_and_each_result(tmp_path, mock_server):
    sites = {"kimi": "ok", "grok": "login", "felo": "nobox", "dola": "moved"}

    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, sites) as a:
            _, cat, _ = await a.get("/api/catalogo")
            assert len(cat["ais"]) == 27 and cat["batch"] is None
            assert {x["state"] for x in cat["ais"] if not x["builtin"]} == {"sin_conectar"}
            # the built-in chats configured here: Qwen and z.ai's chat ("zai-chat"; "zai" is z.ai's API)
            assert {x["key"]: x["provider"] for x in cat["ais"] if x["builtin"]} == {
                "qwen": "qwen", "deepseek": None, "zai": "zai-chat", "meta": None}

            status, b = await a.post("/api/conectar-varias", {"keys": list(sites), "skip": ["pi"]})
            assert status == 200 and b["status"] == "permission"
            b = await a.until_done(b["batch_id"])
            assert b["status"] == "done" and b["connected"] == 2
            assert {r["key"]: r["status"] for r in b["results"]} == {
                "kimi": "ok", "grok": "ok", "felo": "no_funciona", "dola": "no_funciona"}

            # ONE permission request, for every marked site
            (many,) = a.ext.many
            assert [(s["key"], s["url"]) for s in many["sites"]] == [(k, catalog.load().get(k).url) for k in sites]
            # one by one: each check starts after the previous one ended
            order = sorted(a.ext.checks, key=lambda c: c[1])
            assert [c[0] for c in order] == list(sites)
            assert all(later[1] >= earlier[2] for earlier, later in zip(order, order[1:]))
            # the "pong" test went through the guard, once per site that got that far
            assert sorted(j["site"] for j in a.ext.jobs) == ["grok", "kimi"]
            assert a.bridge.guard.status()["kimi"]["count_today"] == 1

            assert (await a.catalog_row("kimi"))["state"] == "conectada"
            felo = await a.catalog_row("felo")
            assert felo["state"] == "no_funciona" and "caja de texto" in felo["message"] and felo["diagnosis_saved"]
            dola = await a.catalog_row("dola")
            assert "https://otra.example/chat" in dola["message"] and "Añadir otra IA" in dola["message"]
            pi = await a.catalog_row("pi")
            assert pi["state"] == "no_la_quiero"
            saved = catalog.load_state(a.cfg.paths)
            assert json.loads(saved["felo"]["detail"])["buttons"] == 3  # the page diagnosis, kept for F6

            # only the connected ones are AIs, in the app and in Open WebUI
            _, estado, _ = await a.get("/api/estado")
            names = {x["name"] for x in estado["ais"]}
            assert {"kimi", "grok"} <= names and not {"felo", "dola", "pi"} & names
            _, models, _ = await a.get("/gw/v1/models")
            ids = {m["id"] for m in models["data"]}
            assert {"kimi", "grok"} <= ids and not {"felo", "dola", "pi"} & ids
    run(go())


def test_without_permission_nothing_is_tried(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"kimi": "ok"}, grant=False) as a:
            _, b = await a.post("/api/conectar-varias", {"keys": ["kimi"]})
            b = await a.until_done(b["batch_id"])
            assert b["status"] == "failed" and "No diste permiso" in b["message"]
            assert a.ext.checks == [] and a.ext.jobs == [] and b["results"][0]["status"] == "skipped"
            assert (await a.catalog_row("kimi"))["state"] == "sin_conectar"
    run(go())


def test_not_logging_in_in_time_leaves_it_unconnected_and_goes_on(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"gemini": "login_never", "kimi": "ok"}) as a:
            _, b = await a.post("/api/conectar-varias", {"keys": ["gemini", "kimi"]})
            b = await a.until_done(b["batch_id"])
            assert [(r["key"], r["status"]) for r in b["results"]] == [("gemini", "sin_conectar"), ("kimi", "ok")]
            row = await a.catalog_row("gemini")
            assert row["state"] == "sin_conectar" and "Pedía entrar con tu cuenta" in row["message"]
    run(go())


def test_parar_lets_go_of_the_current_one_and_tries_no_more(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"grok": "hang", "kimi": "ok"}) as a:
            _, b = await a.post("/api/conectar-varias", {"keys": ["grok", "kimi"]})
            for _ in range(100):
                _, b, _ = await a.get(f"/api/conectar-varias/{b['batch_id']}")
                if b["current"] == "grok":
                    break
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.2)
            status, _ = await a.post(f"/api/conectar-varias/{b['batch_id']}/parar", {})
            b = await a.until_done(b["batch_id"])
            assert status == 200 and [(r["key"], r["status"]) for r in b["results"]] == [
                ("grok", "sin_conectar"), ("kimi", "skipped")]
            assert a.ext.cancels == [b["results"][0]["add_id"]] and [c[0] for c in a.ext.checks] == ["grok"]
            assert a.ext.jobs == []
    run(go())


def test_what_cannot_be_asked(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"kimi": "hang"}) as a:
            for body in ({"keys": ["qwen"]}, {"keys": ["nadie"]}, {"keys": []}, {"keys": ["kimi"], "skip": ["zai"]}):
                status, _ = await a.post("/api/conectar-varias", body)
                assert status == 400, body
            _, b = await a.post("/api/conectar-varias", {"keys": ["kimi"]})
            status, body = await a.post("/api/conectar-varias", {"keys": ["grok"]})
            assert status == 409 and "Ya hay una conexión en marcha" in body["error"]
            _, cat, _ = await a.get("/api/catalogo")
            assert cat["batch"]["batch_id"] == b["batch_id"]
            await a.post(f"/api/conectar-varias/{b['batch_id']}/parar", {})
            await a.until_done(b["batch_id"])
    run(go())


def test_an_old_extension_is_named(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"kimi": "ok"}, knows_many=False) as a:
            _, b = await a.post("/api/conectar-varias", {"keys": ["kimi"]})
            assert b["status"] == "failed" and b["error"] == "old_extension" and "↻" in b["message"]
    run(go())


def test_a_public_one_says_so_and_a_low_cap_shows(tmp_path, mock_server):
    async def go():
        async with ConnApp(tmp_path, mock_server.base_url, {"arena": "ok", "venice": "ok"}) as a:
            _, b = await a.post("/api/conectar-varias", {"keys": ["arena", "venice"]})
            await a.until_done(b["batch_id"])
            _, models, _ = await a.get("/gw/v1/models")
            by = {m["id"]: m for m in models["data"]}
            assert by["arena"]["name"] == "Arena (chat directo) (web, no privada)"
            assert "No privada" in by["arena"]["webllm"]["card"] and by["venice"]["webllm"]["daily_cap"] == 10
            assert not catalog.eligible_for_auto(a.bridge.cfg.providers["arena"])
            assert catalog.eligible_for_auto(a.bridge.cfg.providers["venice"])
            _, estado, _ = await a.get("/api/estado")
            assert next(x for x in estado["ais"] if x["name"] == "venice")["cap"] == 10

            # Quitar: back to "Sin conectar", and it no longer is an AI
            status, _ = await a.post("/api/quitar", {"ia": "venice"})
            row = await a.catalog_row("venice")
            assert status == 200 and row["state"] == "sin_conectar" and "La quitaste" in row["message"]
            assert "venice" not in a.bridge.cfg.providers
    run(go())

"""Run the real webllm server + app with stand-ins for Chrome and OmniRoute (development only).

    python scripts/app_demo.py [--port 20199] [--data DIR] [--sin-chrome] [--limite SEGUNDOS]

Everything the app talks to is real (bridge, app API, chain engine, journal, guard) except:
- a fake Chrome extension that answers each chat job with a canned Spanish answer
  (Meta AI starts without a session; after "Conectar" brings its window forward it
  "logs in" 6 s later, so the light turns green by itself);
- a fake OmniRoute that answers the API models;
- a fake LM Studio with one chat model and one embedding model (left out by the app);
- an "installed" Ollama that is off (nothing listens on its port);
- "Añadir otra IA": the fake extension "gets" the permission 2.5 s later and walks through
  the test steps; an address with "nochat" in it fails at "no text box" (to see the error);
- a question with "(demo: verificación)" in it makes Qwen "wait for Iván" 8 s (a verification),
  as extension 0.5.0 reports it, before answering.
Nothing leaves this machine. Used to look at the app and take its screenshots in the cloud,
where Iván's Chrome and OmniRoute are not reachable. Open http://127.0.0.1:<port>/app/
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import tempfile
import time
from pathlib import Path

import yaml
from aiohttp import ClientSession, web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from webllm_agent.bridge import Bridge  # noqa: E402
from webllm_agent.config import load_config  # noqa: E402

TOKEN = "demo-token"

ANSWERS = {
    "qwen": ("La **inflación** es cuando las cosas cuestan cada vez más dinero.\n\n"
             "- Si hoy un bocadillo cuesta 3 €, dentro de un año puede costar 3,20 €.\n"
             "- Con el mismo dinero compras **menos cosas**.\n"
             "- Pasa cuando hay mucho dinero circulando o cuando producir cuesta más.\n\n"
             "Un poco de inflación (2 % al año) es normal; mucha es un problema."),
    "deepseek": ("Imagina que tienes **10 €** de paga y cada semana compras chuches.\n\n"
                 "1. Hoy te dan 10 chuches.\n2. El año que viene, con los mismos 10 €, solo 9.\n\n"
                 "Eso es la inflación: **los precios suben y tu dinero vale menos**. "
                 "Los bancos centrales intentan que suba poco y despacio."),
    "zai": ("Piensa en la inflación como en un globo que se hincha: los precios suben poco a poco.\n\n"
            "| Año | Precio del pan |\n|---|---|\n| 2024 | 1,00 € |\n| 2025 | 1,03 € |\n| 2026 | 1,06 € |\n\n"
            "Por eso tus ahorros \"encogen\" si están quietos en una hucha."),
}
ANSWERS["mistral"] = ("La inflación es la **subida general de los precios**. Con el mismo dinero compras menos que antes.\n\n"
                      "Ejemplo: si una barra de pan pasa de 1 € a 1,05 €, la inflación del pan ha sido del 5 %.")
# The site's own icon, as the real extension sends it (a data URL).
DEMO_ICON = "data:image/svg+xml;base64," + base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#111"/>'
    b'<rect x="5" y="6" width="5" height="20" fill="#f7d046"/><rect x="22" y="6" width="5" height="20" fill="#f7d046"/>'
    b'<rect x="10" y="6" width="4" height="7" fill="#f2a73b"/><rect x="18" y="6" width="4" height="7" fill="#f2a73b"/>'
    b'<rect x="14" y="13" width="4" height="7" fill="#ee792f"/><rect x="10" y="13" width="12" height="4" fill="#eb5829"/></svg>'
).decode()

API_ANSWERS = {
    "zai": "**Respuesta corta:** la inflación es la subida general de los precios. Si sube un 3 %, "
           "lo que costaba 100 € pasa a costar 103 €.",
    "groq": "La inflación mide cuánto suben los precios de media en un país durante un año. "
            "Se calcula con una *cesta* de productos típicos (comida, luz, transporte…).",
    "nemotron": "Inflación = los precios suben ⇒ el dinero compra menos. Ejemplo: un helado de 2 € "
                "que al año siguiente cuesta 2,10 €.",
}


def fake_lmstudio() -> web.Application:
    async def models(request):
        return web.json_response({"object": "list", "data": [{"id": "qwen2.5-1.5b-instruct"},
                                                              {"id": "text-embedding-nomic-embed-text-v1.5"}]})

    async def chat(request):
        body = await request.json()
        await asyncio.sleep(3.5)
        return web.json_response({"id": "x", "object": "chat.completion", "model": body["model"], "choices": [{
            "index": 0, "message": {"role": "assistant", "content":
                "La inflación es cuando **los precios suben** con el tiempo y con el mismo dinero compras menos. "
                "(Respondido por un modelo pequeño que funciona en tu PC.)"}}]})

    app = web.Application()
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat)
    return app


def fake_omniroute() -> web.Application:
    async def health(request):
        return web.json_response({"ok": True})

    async def models(request):
        return web.json_response({"object": "list", "data": [{"id": m} for m in ("zai/glm-4.7-flash", "groq/x", "nr/x")]})

    async def chat(request):
        body = await request.json()
        model = body["model"]
        await asyncio.sleep(1.2 if model.startswith("groq") else 2.5)
        prompt = body["messages"][-1]["content"]
        key = "zai" if model.startswith("zai") else "groq" if model.startswith("groq") else "nemotron"
        text = API_ANSWERS[key]
        if "critica" in prompt.lower() or "Otra IA" in prompt or "ojo crítico" in prompt:
            text = ("**Mi opinión:** la respuesta es correcta y clara. Le añadiría que un poco de inflación "
                    "es normal (alrededor del 2 %) y que lo peligroso es cuando sube muy deprisa.")
        return web.json_response({"id": "x", "object": "chat.completion", "model": model,
                                  "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]})

    app = web.Application()
    app.router.add_get("/api/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat)
    return app


async def fake_extension(port: int) -> None:
    delays = {"qwen": 3.0, "deepseek": 5.0, "zai": 4.0, "meta": 1.0}
    logged_in = {"meta": False}
    async with ClientSession() as s:
        while True:
            try:
                ws = await s.ws_connect(f"http://127.0.0.1:{port}/ext?token={TOKEN}")
                break
            except OSError:
                await asyncio.sleep(0.3)

        async def log_in_later(site):
            await asyncio.sleep(6)
            logged_in[site] = True

        async def progress(add_id, step, ok, text):
            await ws.send_json({"type": "add_progress", "add_id": add_id, "step": step, "ok": ok, "text": text})

        async def add_site(job):
            await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "add"})
            add_id = job["add_id"]
            await asyncio.sleep(2.5)  # Iván clicks "Permitir y probar" and "Permitir"
            await progress(add_id, "permission", True, "Permiso concedido")
            await progress(add_id, "open", None, "Abriendo la web…")
            await asyncio.sleep(1.5)
            await progress(add_id, "open", True, "Web abierta")
            if "nochat" in job["url"]:
                await ws.send_json({"type": "add_done", "add_id": add_id, "ok": False, "error": "no_input",
                                    "detail": json.dumps({"url": job["url"], "inputs": 0, "buttons": 3})})
                return
            await progress(add_id, "input", True, "Caja de texto: encontrada")
            # the bridge then sends the test message ("pong") as a normal, guarded job
            await ws.send_json({"type": "add_ready", "add_id": add_id, "icon": DEMO_ICON})

        async def answer(job):
            if job.get("type") == "add_site":
                return await add_site(job)
            site = job["site"]
            if job.get("type") == "show":
                await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "", "via": "show"})
                if not logged_in.get(site, True):
                    asyncio.create_task(log_in_later(site))
                return
            if site == "qwen" and "(demo: verificación)" in job.get("prompt", ""):
                for waiting in ["challenge"] * 8 + [None]:
                    await ws.send_json({"type": "job_alive", "id": job["id"], "site": site, "waiting": waiting})
                    await asyncio.sleep(1)
            await asyncio.sleep(0.4 if job.get("type") == "diagnose" else delays.get(site, 2.0))
            ok = logged_in.get(site, True)
            if job.get("type") == "diagnose":
                state = {"input": ok, "loginWall": not ok, "challenge": None}
                await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": json.dumps({"state": state})})
            elif not ok:
                await ws.send_json({"type": "result", "id": job["id"], "ok": False, "error": "login_required"})
            elif "pong" in job["prompt"]:  # the test message of "Añadir otra IA"
                await asyncio.sleep(2.5)
                await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": "pong", "via": "copy-button"})
            else:
                text = ANSWERS.get(site, "Respuesta de prueba.")
                if "Otra IA" in job["prompt"] or "ojo crítico" in job["prompt"]:
                    text = ("Está bien explicada. Yo añadiría un ejemplo con **sueldos**: si los precios suben un 5 % "
                            "y tu sueldo solo un 2 %, en realidad eres un 3 % más pobre.")
                await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": text, "via": "copy-button"})

        async for msg in ws:
            job = json.loads(msg.data)
            if job.get("type") in ("job", "diagnose", "show", "add_site"):
                asyncio.create_task(answer(job))


async def main(port: int, data: Path, chrome: bool = True, limit_s: float = 30) -> None:
    omni = web.AppRunner(fake_omniroute())
    await omni.setup()
    site = web.TCPSite(omni, "127.0.0.1", 0)
    await site.start()
    omni_port = site._server.sockets[0].getsockname()[1]
    lms = web.AppRunner(fake_lmstudio())
    await lms.setup()
    lms_site = web.TCPSite(lms, "127.0.0.1", 0)
    await lms_site.start()
    lms_port = lms_site._server.sockets[0].getsockname()[1]
    data.mkdir(parents=True, exist_ok=True)
    (data / "config.yaml").write_text(yaml.safe_dump({
        "omniroute": {"base_url": f"http://127.0.0.1:{omni_port}/v1"},
        "bridge": {"port": port},
        "guard": {"min_spacing_s": 0, "daily_cap": 150, "cooldown_hours": 6},
        "local_servers": [{"key": "lmstudio", "name": "LM Studio", "url": f"http://127.0.0.1:{lms_port}/v1",
                           "start": ["lms", "server", "start"]},
                          # installed but off, never used: shows grey with an "Encender" button
                          {"key": "ollama", "name": "Ollama", "url": "http://127.0.0.1:9/v1", "start": ["ollama", "serve"]}],
    }), encoding="utf-8")
    cfg = load_config(data)
    bridge = Bridge(cfg, TOKEN, timeout_s=limit_s, human_wait_s=0, connect_wait_s=2, launcher=None,
                    log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
    bridge.app_api.omniroute_launcher = lambda: print("(demo) encender OmniRoute", flush=True)
    bridge.app_api.local.launcher = lambda cmd: print("(demo) encender", cmd, flush=True)
    runner = web.AppRunner(bridge.app())
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    if chrome:
        asyncio.create_task(fake_extension(port))
    print(f"App de demostración: http://127.0.0.1:{port}/app/   (datos en {data})", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=20199)
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--sin-chrome", action="store_true", help="no fake extension: Chrome shows as not connected")
    ap.add_argument("--limite", type=float, default=30, help="time limit for a chat's answer, in seconds")
    a = ap.parse_args()
    asyncio.run(main(a.port, a.data or Path(tempfile.mkdtemp(prefix="webllm-demo-")), chrome=not a.sin_chrome,
                     limit_s=a.limite))

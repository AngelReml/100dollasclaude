"""Real end-to-end checks, shared by `webllm probar` (console) and the panel page.

Each check reports events {id, title, state: running|ok|fail, message, detail};
detail carries the evidence the page shows (the AI's actual answer, the code
before/after the programming test, pytest output). Checks, in order:
OmniRoute, the bridge, the Chrome extension, each Chrome chat (one short real
message), the API models, and a programming test (aider fixes a tiny broken
project through a Chrome chat, or through the API combo if no chat works).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from .bridge import SITES, load_token
from .client import TRANSPARENT_HEADERS
from .config import PROJECT_ROOT, AppConfig
from .omniroute import load_api_key

TOOLS = PROJECT_ROOT / "herramientas"
AIDER = Path.home() / ".local" / "bin" / "aider.exe"
SANDBOX = PROJECT_ROOT / "tests" / "sandbox-repo"
SITE_URLS = {"qwen": "https://chat.qwen.ai", "deepseek": "https://chat.deepseek.com",
             "zai": "https://chat.z.ai", "meta": "https://www.meta.ai"}
TEST_ORDER = ["zai", "qwen", "deepseek", "meta"]
API_MODELS = [("zai-api", "z.ai (API)", "zai/glm-4.7-flash"),
              ("groq", "groq (API)", "groq/openai/gpt-oss-120b"),
              ("nemotron", "Nemotron (API)", "openrouter/nvidia/nemotron-3-super-120b-a12b:free")]
PING = "Responde solo con la palabra: pong"

Emit = Callable[[dict[str, Any]], Awaitable[None]]


def _event(id_: str, title: str, state: str, message: str = "", **detail: Any) -> dict[str, Any]:
    return {"id": id_, "title": title, "state": state, "message": message, "detail": detail}


async def _up(client: httpx.AsyncClient, url: str) -> bool:
    try:
        return (await client.get(url, timeout=3)).status_code == 200
    except httpx.HTTPError:
        return False


async def _extension_connected(client: httpx.AsyncClient, bridge: str) -> bool:
    try:
        return bool((await client.get(f"{bridge}/health", timeout=3)).json().get("extension"))
    except (httpx.HTTPError, ValueError):
        return False


def _chat_failure(site: str, status: int, message: str) -> str:
    name = SITES[site]
    if status == 401:
        return f"No hay sesión abierta. -> Entra en {SITE_URLS[site]} con tu cuenta en Chrome y vuelve a probar."
    if status == 403:
        return f"{message} -> Cuando lo arregles, doble clic en REANUDAR."
    if status == 504:
        return "Tardó demasiado en responder. -> Deja su ventana de Chrome a la vista y vuelve a probar."
    if status == 503:
        return f"{message} -> Vuelve a probar en un rato."
    return f"No supe escribir o leer en la web de {name} ({message[:160]}). -> Dímelo y lo ajusto."


async def _check_chat(client: httpx.AsyncClient, bridge: str, token: str, site: str, emit: Emit) -> bool:
    id_, title = f"chat:{site}", f"Chat {SITES[site]} (en tu Chrome)"
    await emit(_event(id_, title, "running", "Escribiendo en la web y esperando la respuesta..."))
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{bridge}/v1/chat/completions", timeout=480,
                              headers={"Authorization": f"Bearer {token}"},
                              json={"model": f"browser/{site}", "messages": [{"role": "user", "content": PING}]})
    except httpx.HTTPError as exc:
        await emit(_event(id_, title, "fail", f"El puente no respondió ({type(exc).__name__})."))
        return False
    secs = round(time.perf_counter() - t0)
    if r.status_code == 200:
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        ok = "pong" in text.lower()
        used = data.get("model", "").split(" · ", 1)
        model_note = f" (modelo: {used[1]})" if len(used) == 2 else ""
        await emit(_event(id_, title, "ok" if ok else "fail",
                          (f"Respondió en {secs} s{model_note}: «{text.strip()[:120]}»" if ok
                           else f"Respondió otra cosa: «{text.strip()[:120]}» -> Dímelo y lo ajusto."),
                          question=PING, answer=text, seconds=secs, capture=r.headers.get("x-webllm-capture", "")))
        return ok
    try:
        message = r.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = r.text[:200]
    await emit(_event(id_, title, "fail", _chat_failure(site, r.status_code, message), http_status=r.status_code))
    return False


async def _check_api(client: httpx.AsyncClient, base: str, key: str, id_: str, label: str, model: str, emit: Emit) -> None:
    await emit(_event(f"api:{id_}", label, "running", "Preguntando..."))
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{base}/chat/completions", timeout=180,
                              headers={"Authorization": f"Bearer {key}", **TRANSPARENT_HEADERS},
                              json={"model": model, "messages": [{"role": "user", "content": PING}]})
    except httpx.HTTPError as exc:
        await emit(_event(f"api:{id_}", label, "fail", f"No respondió ({type(exc).__name__})."))
        return
    secs = round(time.perf_counter() - t0, 1)
    if r.status_code == 200:
        text = r.json()["choices"][0]["message"]["content"] or ""
        ok = "pong" in text.lower()
        await emit(_event(f"api:{id_}", label, "ok" if ok else "fail",
                          (f"Respondió en {secs} s: «{text.strip()[:120]}»" if ok
                           else f"Respondió otra cosa: «{text.strip()[:120]}»"),
                          question=PING, answer=text, seconds=secs, model=model))
    elif r.status_code in (429, 503, 529):
        await emit(_event(f"api:{id_}", label, "fail",
                          f"Está saturado ahora mismo (HTTP {r.status_code}). -> No es tuyo: vuelve a probar en un rato."))
    else:
        await emit(_event(f"api:{id_}", label, "fail", f"Falló (HTTP {r.status_code}). -> Dímelo."))


def _programming_run(base: str, key: str, model: str) -> dict[str, Any]:
    """aider fixes tests/sandbox-repo (one failing test) in a throwaway copy."""
    def sh(cmd, cwd, env=None):
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
    work = PROJECT_ROOT / "data" / "sandbox-runs" / f"{datetime.now():%Y%m%d-%H%M%S}-probar"
    shutil.copytree(SANDBOX, work)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "sandbox"]):
        sh(cmd, work)
    code_before = (work / "textstats.py").read_text(encoding="utf-8")
    before = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    env = {**os.environ, "OPENAI_API_BASE": base, "OPENAI_API_KEY": key}
    sh([str(AIDER), "--model", f"openai/{model}", "--no-stream", "--timeout", "600", "--auto-commits",
        "--no-show-model-warnings", "--analytics-disable", "--no-check-update", "--no-pretty",
        "--map-tokens", "0", "--yes-always", "--read", "test_textstats.py", "textstats.py",
        "--message", "The test in test_textstats.py fails. Fix textstats.py so that "
                     "`python -m pytest -q` passes. Do not modify test_textstats.py."], work, env)
    after = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    tail = lambda cp: "\n".join((cp.stdout or "").strip().splitlines()[-6:])  # noqa: E731
    return {
        "ok": before.returncode != 0 and after.returncode == 0,
        "folder": str(work),
        "task": "El test de test_textstats.py falla. Arregla textstats.py para que pase.",
        "test_code": (work / "test_textstats.py").read_text(encoding="utf-8"),
        "code_before": code_before,
        "code_after": (work / "textstats.py").read_text(encoding="utf-8"),
        "pytest_before": tail(before),
        "pytest_after": tail(after),
        "git_log": sh(["git", "log", "--oneline"], work).stdout.strip(),
    }


async def run_checks(cfg: AppConfig, emit: Emit, *, start_services: bool = False,
                     program_with: str = "api") -> list[dict[str, Any]]:
    """Run the checks; emit events as they go; return the final event per check.

    program_with="api" (default): quick check of everything, and the programming
    test through the API models so it spends no chat messages.
    program_with=<site>: ONLY the programming test, through that Chrome chat.
    """
    if program_with in SITES:
        return await _program_only(cfg, emit, program_with)
    final: dict[str, dict] = {}

    async def out(ev: dict) -> None:
        if ev["state"] != "running":
            final[ev["id"]] = ev
        await emit(ev)

    bridge = f"http://127.0.0.1:{cfg.bridge_port}"
    omni_health = cfg.base_url.rsplit("/v1", 1)[0] + "/api/health"
    async with httpx.AsyncClient() as client:
        if start_services and not (await _up(client, omni_health) and await _up(client, f"{bridge}/health")):
            await asyncio.get_running_loop().run_in_executor(None, lambda: subprocess.run(
                ["cmd", "/c", str(TOOLS / "iniciar.cmd"), "/nopause"], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240))

        ok = await _up(client, omni_health)
        await out(_event("omniroute", "OmniRoute (IAs por API)", "ok" if ok else "fail",
                         "Encendido." if ok else "Apagado. -> Doble clic en PREGUNTAR o PROBAR TODO lo enciende."))
        bridge_ok = await _up(client, f"{bridge}/health")
        await out(_event("bridge", "Puente con tu Chrome", "ok" if bridge_ok else "fail",
                         "Encendido." if bridge_ok else "Apagado. -> Doble clic en 2 - PROBAR TODO."))

        chrome_ok = False
        if bridge_ok:
            await out(_event("chrome", "Extensión en tu Chrome", "running", "Comprobando..."))
            if not await _extension_connected(client, bridge):
                subprocess.Popen(["cmd", "/c", "start", "", "chrome"])
                for _ in range(20):
                    if await _extension_connected(client, bridge):
                        break
                    await asyncio.sleep(1)
            chrome_ok = await _extension_connected(client, bridge)
            await out(_event("chrome", "Extensión en tu Chrome", "ok" if chrome_ok else "fail",
                             "Conectada." if chrome_ok else
                             "NO conectada. -> Haz la instalación (doble clic en '1 - INSTALAR') y vuelve a probar."))

        good_chats: list[str] = []
        if chrome_ok:
            token = load_token(cfg.paths.state_dir)
            results = await asyncio.gather(*(_check_chat(client, bridge, token, s, out) for s in TEST_ORDER))
            good_chats = [s for s, ok in zip(TEST_ORDER, results) if ok]

        try:
            omni_key = load_api_key()
        except Exception:
            omni_key = ""
        await asyncio.gather(*(_check_api(client, cfg.base_url, omni_key, i, label, model, out)
                               for i, label, model in API_MODELS))

    await _program(out, "Programar (con las IAs por API; para probarlo con un chat usa el otro botón)",
                   cfg.base_url, omni_key, "combo/webllm-default")
    return list(final.values())


async def _program(out: Emit, title: str, base: str, key: str, model: str) -> None:
    if not AIDER.exists():
        await out(_event("programar", title, "fail", "aider no está instalado. -> Dímelo."))
        return
    await out(_event("programar", title, "running", "La IA está arreglando un código roto (hasta 5 minutos)..."))
    res = await asyncio.get_running_loop().run_in_executor(None, _programming_run, base, key, model)
    await out(_event("programar", title, "ok" if res["ok"] else "fail",
                     "Arregló el código: el test pasó de FALLAR a PASAR." if res["ok"]
                     else "No lo arregló. -> Dímelo.", model=model, **{k: v for k, v in res.items() if k != "ok"}))


async def _program_only(cfg: AppConfig, emit: Emit, site: str) -> list[dict[str, Any]]:
    final: dict[str, dict] = {}

    async def out(ev: dict) -> None:
        if ev["state"] != "running":
            final[ev["id"]] = ev
        await emit(ev)

    bridge = f"http://127.0.0.1:{cfg.bridge_port}"
    async with httpx.AsyncClient() as client:
        if not await _extension_connected(client, bridge):
            await out(_event("chrome", "Extensión en tu Chrome", "fail",
                             "NO conectada. -> Instálala (recuadro rojo de arriba) y vuelve a probar."))
            return list(final.values())
    await _program(out, f"Programar con el chat {SITES[site]} (gasta 2 mensajes de ese chat)",
                   f"{bridge}/v1", load_token(cfg.paths.state_dir), f"browser/{site}")
    return list(final.values())


def run(cfg: AppConfig) -> int:
    """Console version (`webllm probar`)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    print("\n=================== PROBAR TODO ===================")
    print("  Se abrirán ventanas de Chrome solas: es normal, no las cierres.")
    print("  Tarda unos minutos. No toques nada hasta que ponga RESULTADO.\n", flush=True)

    async def emit(ev: dict) -> None:
        if ev["state"] != "running":
            print(f"  [{'BIEN' if ev['state'] == 'ok' else 'MAL '}] {ev['title']}: {ev['message']}", flush=True)

    final = asyncio.run(run_checks(cfg, emit, start_services=True))
    good = sum(ev["state"] == "ok" for ev in final)
    print("\n===================== RESULTADO =====================")
    print(f"  {good} de {len(final)} bien.")
    for ev in final:
        if ev["state"] != "ok":
            print(f"   - {ev['title']}: {ev['message']}")
    print("=====================================================\n")
    return 0 if good == len(final) else 1

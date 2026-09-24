"""`webllm probar`: one plain-language check of everything, for real.

Starts what is off, then checks, in order: OmniRoute, the bridge, the Chrome
extension, each Chrome chat (one short real message each), the API models,
and finally a real programming test (aider fixes a tiny broken project using a
Chrome chat). Prints BIEN / MAL per item with what to do when something fails.
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

import httpx

from .bridge import SITES, load_token
from .client import TRANSPARENT_HEADERS
from .config import PROJECT_ROOT, AppConfig
from .omniroute import load_api_key

TOOLS = PROJECT_ROOT / "herramientas"
AIDER = Path.home() / ".local" / "bin" / "aider.exe"
SITE_URLS = {"qwen": "https://chat.qwen.ai", "deepseek": "https://chat.deepseek.com",
             "zai": "https://chat.z.ai", "meta": "https://www.meta.ai"}
TEST_ORDER = ["zai", "qwen", "deepseek", "meta"]
API_MODELS = [("z.ai (API)", "zai/glm-4.7-flash"), ("groq (API)", "groq/openai/gpt-oss-120b"),
              ("Nemotron (API)", "openrouter/nvidia/nemotron-3-super-120b-a12b:free")]
PING = "Responde solo con la palabra: pong"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str]] = []

    def add(self, ok: bool, text: str) -> None:
        self.rows.append((ok, text))
        print(f"  [{'BIEN' if ok else 'MAL '}] {text}", flush=True)


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def _start_everything() -> None:
    # No pipes: the bridge keeps running and would hold a captured pipe open forever.
    subprocess.run(["cmd", "/c", str(TOOLS / "iniciar.cmd"), "/nopause"],
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)


def _extension_connected(bridge: str) -> bool:
    try:
        return bool(httpx.get(f"{bridge}/health", timeout=3).json().get("extension"))
    except (httpx.HTTPError, ValueError):
        return False


def _explain_chat_failure(site: str, status: int, message: str) -> str:
    name = SITES[site]
    if status == 401:
        return f"Chat {name}: no hay sesión abierta. -> Entra en {SITE_URLS[site]} con tu cuenta en Chrome y vuelve a probar."
    if status == 403:
        return f"Chat {name}: {message} -> Cuando lo arregles, doble clic en REANUDAR."
    if status == 504:
        return f"Chat {name}: tardó demasiado en responder. -> Deja su ventana de Chrome a la vista y vuelve a probar."
    if status == 503:
        return f"Chat {name}: Chrome se desconectó. -> Deja Chrome abierto y vuelve a probar."
    return f"Chat {name}: no supe escribir o leer en su web ({message[:120]}). -> Dímelo y lo ajusto."


async def _ask_chat(client: httpx.AsyncClient, bridge: str, token: str, site: str) -> tuple[str, bool, str]:
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{bridge}/v1/chat/completions", timeout=480,
                              headers={"Authorization": f"Bearer {token}"},
                              json={"model": f"browser/{site}", "messages": [{"role": "user", "content": PING}]})
    except httpx.HTTPError as exc:
        return site, False, f"Chat {SITES[site]}: el puente no respondió ({type(exc).__name__})."
    secs = round(time.perf_counter() - t0)
    if r.status_code == 200:
        text = r.json()["choices"][0]["message"]["content"]
        if "pong" in text.lower():
            return site, True, f"Chat {SITES[site]} respondió bien ({secs} s)."
        return site, False, f"Chat {SITES[site]} respondió otra cosa: {text[:80]!r}. -> Dímelo y lo ajusto."
    try:
        message = r.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = r.text[:200]
    return site, False, _explain_chat_failure(site, r.status_code, message)


def _api_ping(base: str, key: str, model: str) -> tuple[bool, str]:
    try:
        r = httpx.post(f"{base}/chat/completions", timeout=180,
                       headers={"Authorization": f"Bearer {key}", **TRANSPARENT_HEADERS},
                       json={"model": model, "messages": [{"role": "user", "content": PING}]})
    except httpx.HTTPError as exc:
        return False, type(exc).__name__
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    text = r.json()["choices"][0]["message"]["content"] or ""
    return "pong" in text.lower(), text[:60]


def _programming_test(base: str, key: str, model: str) -> tuple[bool, str]:
    """aider fixes tests/sandbox-repo (one failing test) in a throwaway copy."""
    def sh(cmd, cwd, env=None):
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
    work = PROJECT_ROOT / "data" / "sandbox-runs" / f"{datetime.now():%Y%m%d-%H%M%S}-probar"
    shutil.copytree(PROJECT_ROOT / "tests" / "sandbox-repo", work)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "sandbox"]):
        sh(cmd, work)
    before = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work).returncode
    env = {**os.environ, "OPENAI_API_BASE": base, "OPENAI_API_KEY": key}
    sh([str(AIDER), "--model", f"openai/{model}", "--no-stream", "--timeout", "600", "--auto-commits",
        "--no-show-model-warnings", "--analytics-disable", "--no-check-update", "--no-pretty",
        "--map-tokens", "0", "--yes-always", "--read", "test_textstats.py", "textstats.py",
        "--message", "The test in test_textstats.py fails. Fix textstats.py so that "
                     "`python -m pytest -q` passes. Do not modify test_textstats.py."], work, env)
    after = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work).returncode
    return before != 0 and after == 0, str(work)


def run(cfg: AppConfig) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    rep = Report()
    omni_health = cfg.base_url.rsplit("/v1", 1)[0] + "/api/health"
    bridge = f"http://127.0.0.1:{cfg.bridge_port}"
    print("\n=================== PROBAR TODO ===================")
    print("  Se abrirán ventanas de Chrome solas: es normal, no las cierres.")
    print("  Tarda unos minutos. No toques nada hasta que ponga RESULTADO.\n", flush=True)

    if not (_up(omni_health) and _up(f"{bridge}/health")):
        print("  Encendiendo lo que estaba apagado...", flush=True)
        _start_everything()
    rep.add(_up(omni_health), "OmniRoute (las IAs por API) encendido.")
    bridge_up = _up(f"{bridge}/health")
    rep.add(bridge_up, "Puente con tu Chrome encendido.")

    chrome_ok = False
    if bridge_up:
        if not _extension_connected(bridge):
            subprocess.Popen(["cmd", "/c", "start", "", "chrome"])
            for _ in range(30):
                if _extension_connected(bridge):
                    break
                time.sleep(1)
        chrome_ok = _extension_connected(bridge)
    rep.add(chrome_ok, "Tu Chrome está conectado." if chrome_ok else
            "Tu Chrome NO está conectado. -> Haz el paso 1 (doble clic en '1 - INSTALAR') y vuelve a probar.")

    good_chats: list[str] = []
    if chrome_ok:
        token = load_token(cfg.paths.state_dir)
        print("\n  Probando cada chat con un mensaje corto (hasta 2-3 minutos)...", flush=True)

        async def all_chats():
            async with httpx.AsyncClient() as client:
                return await asyncio.gather(*(_ask_chat(client, bridge, token, s) for s in TEST_ORDER))

        for site, ok, text in asyncio.run(all_chats()):
            rep.add(ok, text)
            if ok:
                good_chats.append(site)

    print("\n  Probando las IAs por API...", flush=True)
    try:
        omni_key = load_api_key()
    except Exception:
        omni_key = ""
    for label, model in API_MODELS:
        ok, detail = _api_ping(cfg.base_url, omni_key, model) if omni_key else (False, "sin clave de OmniRoute")
        if ok:
            rep.add(True, f"{label} respondió bien.")
        elif detail in ("HTTP 429", "HTTP 503", "HTTP 529"):
            rep.add(False, f"{label} está saturado ahora mismo ({detail}). -> No es tuyo: vuelve a probar en un rato.")
        else:
            rep.add(False, f"{label} falló ({detail}). -> Dímelo.")

    if AIDER.exists():
        if good_chats:
            site = good_chats[0]
            print(f"\n  Probando PROGRAMAR con el chat {SITES[site]} (arreglar un código roto, hasta 5 min)...", flush=True)
            ok, where = _programming_test(f"{bridge}/v1", load_token(cfg.paths.state_dir), f"browser/{site}")
            rep.add(ok, f"Programar con el chat {SITES[site]}: " +
                    ("arregló el código de prueba." if ok else f"no lo arregló. -> Dímelo (carpeta {where})."))
        else:
            print("\n  Ningún chat funcionó; pruebo PROGRAMAR con las IAs por API...", flush=True)
            ok, where = _programming_test(cfg.base_url, omni_key, "combo/webllm-default")
            rep.add(ok, "Programar con las IAs por API: " +
                    ("arregló el código de prueba." if ok else f"no lo arregló. -> Dímelo (carpeta {where})."))
    else:
        rep.add(False, "aider no está instalado. -> Dímelo.")

    good = sum(ok for ok, _ in rep.rows)
    print("\n===================== RESULTADO =====================")
    print(f"  {good} de {len(rep.rows)} bien.")
    bad = [t for ok, t in rep.rows if not ok]
    if bad:
        print("  Lo que falta:")
        for t in bad:
            print(f"   - {t}")
    else:
        print("  Todo funciona. Ya puedes usar PREGUNTAR y PROGRAMAR.")
    print("=====================================================\n")
    return 0 if not bad else 1

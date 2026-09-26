"""PLAN-v5 F1 + F2 + F4 from scratch: a fresh Open WebUI, webllm installed in it by scripts/openwebui_setup.py, and
the checks on the real screen: tests/openwebui/f1_checks.mjs (10), then f2_checks.mjs (8: a harmless MCP
tool, tests/openwebui/mcp_hora.py, used by an AI through webllm only after "Allow"; Open WebUI's
"Detener" stops a web chat's long answer; a web chat, an API and a model on this PC all answer),
then f4_checks.mjs (6, with the real extension: the chat's models, a whole file, a switch that changes the mode). Skipped unless
WEBLLM_OPENWEBUI_PY points at a Python that has Open WebUI (it is 7 GB: `uv venv -p 3.11 .venv &&
uv pip install open-webui`; it brings the `mcp` package the tool server needs)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWPY = os.environ.get("WEBLLM_OPENWEBUI_PY", "")
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
pytestmark = pytest.mark.skipif(
    not OWPY or not Path(OWPY).is_file() or shutil.which("node") is None or not Path(CHROMIUM).is_file()
    or shutil.which("openssl") is None
    or not (ROOT / "app" / "node_modules" / "playwright-core").is_dir(),
    reason="needs WEBLLM_OPENWEBUI_PY (a Python with open-webui), node, app/node_modules and Chromium",
)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_up(url: str, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"{url} did not come up")


def wait_port(port: int, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"port {port} did not open")


def post(url: str, body: dict, token: str = "") -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def test_open_webui_is_webllms_face_on_the_real_screen(tmp_path):
    ow_port, demo_port, mcp_port = free_port(), free_port(), free_port()
    ow_url, demo_url = f"http://127.0.0.1:{ow_port}", f"http://127.0.0.1:{demo_port}"
    env = {**os.environ, "DATA_DIR": str(tmp_path / "ow"), "WEBUI_SECRET_KEY": "prueba", "OFFLINE_MODE": "true",
           "HF_HUB_OFFLINE": "1", "ENABLE_OLLAMA_API": "false", "ENABLE_OPENAI_API": "false", "DEFAULT_LOCALE": "es-ES",
           "ENABLE_VERSION_UPDATE_CHECK": "false", "RAG_EMBEDDING_MODEL_AUTO_UPDATE": "false"}
    (tmp_path / "ow").mkdir()
    procs = [subprocess.Popen([str(Path(OWPY).parent / "open-webui"), "serve", "--host", "127.0.0.1", "--port", str(ow_port)],
                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
             subprocess.Popen([sys.executable, str(ROOT / "scripts" / "app_demo.py"), "--port", str(demo_port),
                               "--data", str(tmp_path / "demo")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
             subprocess.Popen([OWPY, str(ROOT / "tests" / "openwebui" / "mcp_hora.py"), str(mcp_port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    try:
        wait_up(f"{ow_url}/health", 240)
        wait_up(f"{demo_url}/health", 30)
        email, password = "prueba@webllm.test", "prueba-webllm-123"  # this test instance's own administrator
        token = post(f"{ow_url}/api/v1/auths/signup", {"name": "Prueba", "email": email, "password": password})["token"]
        setup = subprocess.run([sys.executable, str(ROOT / "scripts" / "openwebui_setup.py"), "--openwebui", ow_url,
                                "--clave", token, "--webllm", demo_url, "--webllm-token", "demo-token"],
                               capture_output=True, text=True, timeout=120)
        assert setup.returncode == 0 and "Listo." in setup.stdout, setup.stdout + setup.stderr
        out = subprocess.run(["node", str(ROOT / "tests" / "openwebui" / "f1_checks.mjs")], capture_output=True, text=True,
                             timeout=600, env={**os.environ, "OW_URL": ow_url, "OW_EMAIL": email, "OW_PASSWORD": password,
                                               "WEBLLM_DATA": str(tmp_path / "demo"), "OUT": str(tmp_path / "capturas")})
        lines = [x for x in out.stdout.splitlines() if x.startswith(("BIEN", "FALLO"))]
        assert out.returncode == 0 and len(lines) == 10 and all(x.startswith("BIEN") for x in lines), out.stdout + out.stderr
        wait_port(mcp_port, 30)
        out = subprocess.run(["node", str(ROOT / "tests" / "openwebui" / "f2_checks.mjs")], capture_output=True, text=True,
                             timeout=300, env={**os.environ, "OW_URL": ow_url, "OW_EMAIL": email, "OW_PASSWORD": password,
                                               "WEBLLM_DATA": str(tmp_path / "demo"), "OUT": str(tmp_path / "capturas-f2"),
                                               "MCP_URL": f"http://127.0.0.1:{mcp_port}/mcp"})
        lines = [x for x in out.stdout.splitlines() if x.startswith(("BIEN", "FALLO"))]
        assert out.returncode == 0 and len(lines) == 8 and all(x.startswith("BIEN") for x in lines), out.stdout + out.stderr
        # F4 (6): the same Open WebUI, now pointed at a webllm with the REAL extension in Chromium and the
        # extended test chat page: the chat's models in the selector, a file whole, a switch that changes the mode.
        out = subprocess.run(["node", str(ROOT / "tests" / "openwebui" / "f4_checks.mjs")], capture_output=True, text=True,
                             timeout=600, env={**os.environ, "OW_URL": ow_url, "OW_EMAIL": email, "OW_PASSWORD": password,
                                               "WEBLLM_PYTHON": sys.executable, "WEBLLM_TEST_PORT": str(free_port()),
                                               "OUT": str(tmp_path / "capturas-f4")})
        lines = [x for x in out.stdout.splitlines() if x.startswith(("BIEN", "FALLO"))]
        assert out.returncode == 0 and len(lines) == 6 and all(x.startswith("BIEN") for x in lines), out.stdout + out.stderr
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()

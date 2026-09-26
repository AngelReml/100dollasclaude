"""Check API-key permissions against an isolated Open WebUI installation."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from openwebui_setup import OpenWebUI  # noqa: E402

OWPY = os.environ.get("WEBLLM_OPENWEBUI_PY", "")
pytestmark = pytest.mark.skipif(not OWPY or not Path(OWPY).is_file(),
                                reason="needs WEBLLM_OPENWEBUI_PY (a Python with open-webui)")


def test_api_key_403_reasons_and_recovery_on_real_open_webui(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    data_dir = tmp_path / "ow"
    data_dir.mkdir()
    env = {**os.environ, "DATA_DIR": str(data_dir), "WEBUI_SECRET_KEY": "isolated-api-key-test",
           "OFFLINE_MODE": "true", "HF_HUB_OFFLINE": "1", "ENABLE_OLLAMA_API": "false",
           "ENABLE_OPENAI_API": "false", "ENABLE_VERSION_UPDATE_CHECK": "false"}
    executable = Path(OWPY).parent / "Scripts" / ("open-webui.exe" if os.name == "nt" else "open-webui")
    process = subprocess.Popen([str(executable), "serve", "--host", "127.0.0.1", "--port", str(port)],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        with httpx.Client(base_url=url, timeout=30) as client:
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(f"Open WebUI exited with status {process.returncode}")
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                pytest.fail("Open WebUI did not start within 240 seconds")

            signup = client.post("/api/v1/auths/signup", json={"name": "Prueba", "email": "key@webllm.test",
                                                               "password": "prueba-webllm-123"})
            signup.raise_for_status()
            token = signup.json()["token"]
            client.headers["Authorization"] = f"Bearer {token}"
            config_response = client.get("/api/v1/auths/admin/config")
            config_response.raise_for_status()
            config = config_response.json()
            config.update(ENABLE_API_KEYS=True, ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS=False)
            client.post("/api/v1/auths/admin/config", json=config).raise_for_status()
            key_response = client.post("/api/v1/auths/api_key")
            key_response.raise_for_status()
            api_key = key_response.json()["api_key"]
            assert api_key.startswith("sk-")
            ow = OpenWebUI(url, api_key)
            assert isinstance(ow.call("GET", "/api/v1/functions/"), list)

            config["ENABLE_API_KEYS"] = False
            client.post("/api/v1/auths/admin/config", json=config).raise_for_status()
            disabled = client.get("/api/v1/functions/", headers={"Authorization": f"Bearer {api_key}"})
            assert disabled.status_code == 403
            assert disabled.json()["detail"] == "Use of API key is not enabled in the environment."
            with pytest.raises(SystemExit, match="claves de API sin activar"):
                ow.call("GET", "/api/v1/functions/")

            config.update(ENABLE_API_KEYS=True, ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS=True,
                          API_KEYS_ALLOWED_ENDPOINTS="")
            client.post("/api/v1/auths/admin/config", json=config).raise_for_status()
            restricted = client.get("/api/v1/functions/", headers={"Authorization": f"Bearer {api_key}"})
            assert restricted.status_code == 403
            assert "permission to access" in restricted.json()["detail"]
            with pytest.raises(SystemExit, match="restricciones de endpoints"):
                ow.call("GET", "/api/v1/functions/")

            config["ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS"] = False
            client.post("/api/v1/auths/admin/config", json=config).raise_for_status()
            assert isinstance(ow.call("GET", "/api/v1/functions/"), list)
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=20)

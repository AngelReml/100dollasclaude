"""The extension in real Chromium (skipped without node, app/node_modules and Chromium):
driver.js on chat pages it has no selectors for, and the whole "+ Añadir otra IA" flow."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
needs_chromium = pytest.mark.skipif(
    shutil.which("node") is None or not (ROOT / "app" / "node_modules" / "playwright-core").is_dir()
    or not Path(CHROMIUM).is_file(),
    reason="needs node, app/node_modules (npm ci) and Chromium",
)


@needs_chromium
def test_generic_detection_types_sends_and_reads_on_an_unknown_site():
    out = subprocess.run(["node", str(ROOT / "tests" / "extension" / "generic_driver.mjs")],
                         capture_output=True, text=True, timeout=180)
    lines = out.stdout.strip().splitlines()
    assert out.returncode == 0, out.stdout + out.stderr
    assert [line.split()[0] for line in lines] == ["?copy=1", "?copy=0", "?editable=1", "?login=1"]
    assert "leer=copy-button" in lines[0] and "leer=dom" in lines[1] and "enviar=enter" in lines[2]
    assert "login detectado" in lines[3]


@needs_chromium
@pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl (a throwaway https certificate)")
def test_add_a_site_with_the_real_extension_and_bridge():
    with socket.socket() as sock:  # a free port for the bridge
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "WEBLLM_PYTHON": sys.executable, "WEBLLM_TEST_PORT": str(port)}
    out = subprocess.run(["node", str(ROOT / "tests" / "extension" / "add_flow.mjs")],
                         capture_output=True, text=True, timeout=300, env=env)
    lines = [line for line in out.stdout.splitlines() if line.startswith(("BIEN", "FALLO"))]
    assert out.returncode == 0 and len(lines) == 9 and all(line.startswith("BIEN") for line in lines), (
        out.stdout + out.stderr)

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
    assert [line.split()[0] for line in lines] == ["?copy=1", "?copy=0", "?editable=1", "?login=1",
                                                   "?stopfuera=1", "?clasestop=1"]
    assert "leer=copy-button" in lines[0] and "leer=dom" in lines[1] and "enviar=enter" in lines[2]
    assert "login detectado" in lines[3]
    assert all("BIEN" in line and "sigue_escribiendo=false" in line for line in lines[4:])


def run_real(script: str, timeout: float = 300) -> list[str]:
    """Run a tests/extension/*.mjs script (real extension + real bridge); its BIEN/FALLO lines."""
    with socket.socket() as sock:  # a free port for the bridge
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "WEBLLM_PYTHON": sys.executable, "WEBLLM_TEST_PORT": str(port)}
    out = subprocess.run(["node", str(ROOT / "tests" / "extension" / script)],
                         capture_output=True, text=True, timeout=timeout, env=env)
    lines = [line for line in out.stdout.splitlines() if line.startswith(("BIEN", "FALLO"))]
    assert out.returncode == 0 and all(line.startswith("BIEN") for line in lines), out.stdout + out.stderr
    return lines


needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl (a throwaway https certificate)")


@needs_chromium
@needs_openssl
def test_add_a_site_with_the_real_extension_and_bridge():
    assert len(run_real("add_flow.mjs")) == 9


@needs_chromium
@needs_openssl
def test_time_solving_a_verification_does_not_lose_the_answer():
    """Iván's report: a verification made the app give up on chats and lose their late answers."""
    assert len(run_real("captcha_flow.mjs")) == 14


@needs_chromium
@needs_openssl
def test_a_misleading_stop_button_does_not_hide_a_finished_answer():
    """Iván's Meta (2026-09-25): the answer was written but webllm kept waiting for it."""
    assert len(run_real("stuck_stop.mjs")) == 9


@needs_chromium
@needs_openssl
def test_parar_stops_the_job_in_chrome_and_leaves_the_chat_ready():
    """PLAN-v5 "Parar": a slow chat stopped halfway; the extension lets go at once, the next question works."""
    assert len(run_real("parar_flow.mjs")) == 6


@needs_chromium
@needs_openssl
def test_conectar_varias_with_the_real_extension():
    """PLAN-v5 F3: one permission for five catalog sites; one connects, one waits for Iván's login and
    connects, one has no text box and keeps its diagnosis, one sends you to another address to log in and
    connects when you come back, one has moved and says where; webllm types nothing on the login page."""
    assert len(run_real("catalog_flow.mjs")) == 13


@needs_chromium
@needs_openssl
def test_each_chats_capabilities_with_the_real_extension():
    """PLAN-v5 F4: discovery presses no option and sends nothing; model and modes confirmed on the page, or
    nothing is sent; files whole (20 MB too); "Publicar" never pressed; a download saved; "Enséñame"."""
    assert len(run_real("capabilities_flow.mjs")) == 14


@needs_chromium
@needs_openssl
def test_webs_that_repair_themselves_and_the_observer_with_the_real_extension():
    """PLAN-v5 F6: a page in French with a modern box works with no help (layer 1); one whose answers cannot be read
    is repaired by an AI that sees only the page's structure and answers with numbers (layer 3), tried on the page
    sending nothing; an AI answering with code is refused; "Deshacer"; "Enséñame" with 3 clicks (layer 4); "Parar"
    also presses the site's own stop; the daily check sends nothing; "Continuar en la web" and "Registrar esta
    conversación" record 2 turns written by hand into the same conversation and the vault. The same script with
    extension 0.7.0 fails (docs/F6-reparacion.md)."""
    assert len(run_real("repair_flow.mjs", timeout=1200)) == 15

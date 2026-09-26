"""Iván's double-click files (CLAUDE.md, "Things learned the hard way"): Windows needs CRLF line ends, and plain
ASCII text keeps cmd.exe from misreading accents. Checked for every .cmd, the new connectors (PLAN-v5 F9) included."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CMDS = sorted([*ROOT.glob("*.cmd"), *(ROOT / "herramientas").glob("*.cmd")])


def test_there_are_double_click_files():
    names = {p.name for p in CMDS}
    assert {"ACTUALIZAR.cmd", "WEBLLM.cmd", "conectar-github.cmd", "conectar-terminal.cmd", "poner-en-openwebui.cmd"} <= names


@pytest.mark.parametrize("path", CMDS, ids=lambda p: p.name)
def test_every_cmd_is_ascii_with_crlf(path):
    raw = path.read_bytes()
    assert raw.isascii(), f"{path.name} lleva caracteres que no son ASCII"
    assert raw.count(b"\n") == raw.count(b"\r\n"), f"{path.name} tiene saltos de línea que no son CRLF"

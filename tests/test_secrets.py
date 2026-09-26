"""The repo is public (CLAUDE.md rule 4): no key, token or private file may be committed. Scans every file
git would commit (tracked + new, not ignored) for secret-looking strings and forbidden paths."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    "OpenAI-style key": r"\bsk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{20,}",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{20,}",
    "Google key": r"\bAIza[0-9A-Za-z_-]{35}\b",
    "Groq key": r"\bgsk_[A-Za-z0-9]{20,}",
    "NVIDIA key": r"\bnvapi-[A-Za-z0-9_-]{20,}",
    "Slack token": r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
    "z.ai / Zhipu key": r"\b[0-9a-f]{32}\.[A-Za-z0-9]{16}\b",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
SECRET = re.compile("|".join(f"(?:{p})" for p in PATTERNS.values()))
FORBIDDEN = re.compile(r"^(?:data/(?!config\.yaml$).+|extension/config\.json|.*\.env|.*\.pem|.*\.key)$")

pytestmark = pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs git")


def files_to_commit() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode("utf-8")
    return [f for f in out.split("\0") if f and (ROOT / f).is_file()]


def test_the_patterns_catch_real_shaped_keys():
    # built here so this file itself holds no key-shaped string
    samples = ["sk-" + "a1" * 12, "sk-or-v1-" + "0f" * 16, "ghp_" + "A" * 36, "AIza" + "B" * 35, "gsk_" + "c" * 30,
               "nvapi-" + "D" * 30, "0123456789abcdef" * 2 + "." + "Q" * 16, "-----BEGIN " + "PRIVATE KEY-----"]
    assert all(SECRET.search(s) for s in samples)
    assert not SECRET.search("demo-token sk-short task-list AIzaShort")


def test_no_secret_is_committed():
    found = []
    for name in files_to_commit():
        data = (ROOT / name).read_bytes()
        if b"\0" in data[:4096]:
            continue  # images, fonts
        for m in SECRET.finditer(data.decode("utf-8", "replace")):
            found.append(f"{name}: {m.group(0)[:12]}…")
    assert not found, found


def test_no_private_file_is_committed():
    assert not [f for f in files_to_commit() if FORBIDDEN.match(f)]
    # where webllm writes its private files, git ignores them before anyone can add them
    private = ["extension/config.json", "data/state/guard.json", "data/state/api_budget.json", "data/runs/x/journal.jsonl",
               "data/logs/bridge.log", "data/state/custom_ais.json", "data/state/icons/x.png",
               "data/descargas/x/informe.txt", "data/state/fichas/qwen.json", "data/state/patches/qwen.json"]
    out = subprocess.run(["git", "check-ignore", "--no-index", *private], cwd=ROOT, capture_output=True, text=True).stdout
    assert out.split() == private

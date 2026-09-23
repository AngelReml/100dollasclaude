"""End-to-end check: aider + OmniRoute fixes a failing test in a throwaway repo.

    python tests/aider_sandbox.py --model groq/openai/gpt-oss-120b

Copies tests/sandbox-repo into data/sandbox-runs/<timestamp>-<model>/, makes it a
git repo, shows pytest failing, lets aider (non-interactive) edit it, then shows
pytest again, the git log, and proves the test file itself was not touched.
aider's --yes-always auto-DECLINES shell commands (explicit_yes_required in
aider's source), so nothing but file edits can happen.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from webllm_agent.omniroute import base_url, load_api_key  # noqa: E402

TEMPLATE = ROOT / "tests" / "sandbox-repo"
AIDER = Path.home() / ".local" / "bin" / "aider.exe"
SETTINGS = ROOT / "aider" / "omniroute.model-settings.yml"
MESSAGE = (
    "The test in test_textstats.py fails. Fix textstats.py so that "
    "`python -m pytest -q` passes. Do not modify test_textstats.py."
)


def sh(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def show(title: str, cp: subprocess.CompletedProcess, tail: int = 12) -> None:
    lines = (cp.stdout.strip() or cp.stderr.strip()).splitlines()
    print(f"--- {title} (exit={cp.returncode})")
    print("\n".join(lines[-tail:]))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="OmniRoute model id, e.g. groq/openai/gpt-oss-120b")
    ap.add_argument("--edit-format", default=None)
    a = ap.parse_args()

    slug = re.sub(r"[^A-Za-z0-9.-]+", "_", a.model)[:60]
    work = ROOT / "data" / "sandbox-runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}"
    shutil.copytree(TEMPLATE, work)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                ["git", "commit", "-q", "-m", "sandbox: failing test"]):
        sh(cmd, work).check_returncode()
    test_hash = sha(work / "test_textstats.py")
    print(f"sandbox: {work}")

    before = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    show("pytest BEFORE", before, 6)

    env = dict(os.environ)
    env["OPENAI_API_BASE"] = base_url()
    env["OPENAI_API_KEY"] = load_api_key()  # child process only, never printed
    cmd = [str(AIDER), "--model", f"openai/{a.model}", "--model-settings-file", str(SETTINGS),
           "--message", MESSAGE, "--yes-always", "--auto-commits", "--no-show-model-warnings",
           "--analytics-disable", "--no-check-update", "--no-pretty", "--map-tokens", "0",
           "--read", "test_textstats.py", "textstats.py"]
    if a.edit_format:
        cmd[1:1] = ["--edit-format", a.edit_format]
    run = sh(cmd, work, env=env)
    show("aider", run, 25)

    after = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    show("pytest AFTER", after, 6)
    show("git log --oneline", sh(["git", "log", "--oneline"], work), 10)
    show("git diff HEAD~1 -- textstats.py", sh(["git", "diff", "HEAD~1", "--", "textstats.py"], work), 20)
    untouched = sha(work / "test_textstats.py") == test_hash
    print(f"test file untouched: {untouched}")

    ok = before.returncode != 0 and after.returncode == 0 and untouched
    print(f"SANDBOX RESULT {a.model}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

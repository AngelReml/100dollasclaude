"""Plumbing check: aider -> running bridge -> (fake) extension -> answer -> file edit.

    python tests/bridge_aider_check.py

Connects a stand-in extension to the RUNNING bridge (127.0.0.1:20130) that
answers every job with a whole-file fix for tests/sandbox-repo, then runs aider
against the bridge in a throwaway copy and shows pytest red -> green. Proves
the bridge speaks the API aider expects; the real extension replaces the
stand-in. Do not run it while the real extension is connected (the newest
connection takes over).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
TOKEN = (ROOT / "data" / "state" / "bridge_token").read_text(encoding="utf-8").strip()
AIDER = Path.home() / ".local" / "bin" / "aider.exe"
FIX = (
    "textstats.py\n```python\n"
    '"""Tiny module used as the aider sandbox target."""\n\n\n'
    "def word_count(text: str) -> int:\n"
    '    """Return the number of words in text; words are separated by any whitespace."""\n'
    "    return len(text.split())\n```\n"
)


async def stand_in_extension(seen: list[dict]) -> None:
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(f"ws://127.0.0.1:20130/ext?token={TOKEN}") as ws:
            async for msg in ws:
                job = json.loads(msg.data)
                if job.get("type") == "job":
                    seen.append(job)
                    await ws.send_json({"type": "result", "id": job["id"], "ok": True, "text": FIX, "via": "stand-in"})


def sh(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    work = ROOT / "data" / "sandbox-runs" / f"{datetime.now():%Y%m%d-%H%M%S}-bridge"
    shutil.copytree(ROOT / "tests" / "sandbox-repo", work)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "sandbox"]):
        sh(cmd, work).check_returncode()
    before = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    print("pytest BEFORE:", before.stdout.strip().splitlines()[-1])

    seen: list[dict] = []
    ext = asyncio.create_task(stand_in_extension(seen))
    await asyncio.sleep(1.0)
    env = {**__import__("os").environ, "OPENAI_API_BASE": "http://127.0.0.1:20130/v1", "OPENAI_API_KEY": TOKEN}
    proc = await asyncio.create_subprocess_exec(
        str(AIDER), "--model", "openai/browser/zai", "--no-stream", "--timeout", "120", "--auto-commits",
        "--no-show-model-warnings", "--analytics-disable", "--no-check-update", "--no-pretty", "--map-tokens", "0",
        "--yes-always", "--message", "Fix textstats.py so the test passes.", "--read", "test_textstats.py", "textstats.py",
        cwd=str(work), env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    ext.cancel()
    lines = out.decode("utf-8", "replace").splitlines()
    print("aider exit:", proc.returncode, "|", " | ".join(l for l in lines if l.startswith(("Model:", "Applied edit", "Commit "))))
    print("jobs received by the extension:", len(seen), "| prompt chars:", len(seen[0]["prompt"]) if seen else 0,
          "| prompt includes aider system instructions:", bool(seen) and "SYSTEM INSTRUCTIONS" in seen[0]["prompt"])
    after = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], work)
    print("pytest AFTER:", after.stdout.strip().splitlines()[-1])
    print("git log:", sh(["git", "log", "--oneline"], work).stdout.strip().replace("\n", " | "))
    ok = before.returncode != 0 and after.returncode == 0 and bool(seen)
    print("BRIDGE+AIDER:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

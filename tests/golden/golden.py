"""Golden round-trip test: can a model echo a tricky code block byte for byte?

Run against the live OmniRoute gateway:

    python tests/golden/golden.py --model groq/openai/gpt-oss-120b --runs 5

Web providers (see WEB_PREFIXES) are always run one at a time with at least
20 s between requests, to protect the account.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from webllm_agent.client import chat  # noqa: E402
from webllm_agent.omniroute import base_url, load_api_key  # noqa: E402

# The block is built from escapes so git/editor line-ending or encoding
# settings cannot alter it. It contains: backticks (inline and double), a tab,
# n-tilde and euro sign, a line starting with "#", nested quotes, and a line
# with two trailing spaces.
GOLDEN_BLOCK = (
    "```text\n"
    "# golden-v1: keep every byte\n"
    "name = \"Iv\u00e1n's \\\"a\u00f1o\\\" budget: 12,50 \u20ac\"\n"
    "\tindented_with_tab = `x` and ``y``\n"
    "quote_mix = 'she said \"hola\" twice'\n"
    "two trailing spaces here  \n"
    "END \u00f1\u20ac\n"
    "```"
)

GOLDEN_PROMPT = (
    "Reply with EXACTLY the fenced code block below and nothing else: no "
    "explanation, no text before or after it. Copy every character exactly, "
    "including the tab, the trailing spaces, quotes, backslashes, backticks and "
    "non-ASCII characters.\n\n" + GOLDEN_BLOCK
)

WEB_PREFIXES = ("qwen-web/", "deepseek-web/", "ds-web/", "muse-spark-web/", "ms-web/", "zai-web/", "zw/")
WEB_MIN_SPACING_S = 20.0


def compare(response_text: str, expected: str = GOLDEN_BLOCK) -> tuple[bool, str]:
    """Byte comparison after stripping outer whitespace. Returns (ok, detail)."""
    got = response_text.strip().encode("utf-8")
    want = expected.strip().encode("utf-8")
    if got == want:
        return True, "identical"
    n = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return False, (
        f"first difference at byte {n}: got {got[max(0, n - 12):n + 12]!r} "
        f"want {want[max(0, n - 12):n + 12]!r} (len got={len(got)} want={len(want)})"
    )


def is_web(model: str) -> bool:
    return model.startswith(WEB_PREFIXES)


async def run(model: str, runs: int, spacing_s: float, timeout_s: float, out: Path) -> int:
    if is_web(model):
        spacing_s = max(spacing_s, WEB_MIN_SPACING_S)
    key = load_api_key()
    passed = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        for i in range(1, runs + 1):
            if i > 1 and spacing_s:
                await asyncio.sleep(spacing_s)
            res = await chat(client, base_url=base_url(), api_key=key, model=model,
                             prompt=GOLDEN_PROMPT, timeout_s=timeout_s)
            if res.ok:
                ok, detail = compare(res.text)
            else:
                ok, detail = False, f"{res.status}: {res.error} {res.body_excerpt[:200]!r}"
            passed += ok
            rec = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "requested_model": model,
                "served_model": res.model,
                "run": i,
                "result": "PASS" if ok else "FAIL",
                "latency_s": round(res.latency_s, 2),
                "upstream_provider": res.upstream_provider,
                "omniroute_cache": res.cache,
                "detail": detail,
                "response_sha256": hashlib.sha256(res.text.encode("utf-8")).hexdigest() if res.ok else None,
            }
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{i}/{runs}] {rec['result']} {model} served={res.model} via={res.upstream_provider} cache={res.cache} latency={rec['latency_s']}s {detail if not ok else ''}", flush=True)
            if not ok and res.http_status in (401, 403, 429) and is_web(model):
                print("stopping: account-protection rule (401/403/429 on a web provider)", flush=True)
                break
    print(f"SUMMARY {model}: {passed}/{runs} PASS")
    return 0 if passed == runs else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--spacing", type=float, default=0.0, help="seconds between runs (web: min 20)")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "golden" / "results.jsonl")
    a = ap.parse_args(argv)
    return asyncio.run(run(a.model, a.runs, a.spacing, a.timeout, a.out))


if __name__ == "__main__":
    raise SystemExit(main())

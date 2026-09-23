"""Apply OmniRoute's native per-connection limits to the web (cookie) providers.

    python scripts/apply_web_limits.py            # dry run: show what would change
    python scripts/apply_web_limits.py --apply    # PATCH, then read back and verify

Native equivalents of the broadcaster's guard (OmniRoute v3.8.50,
PATCH /api/providers/{id}, field ``rateLimitOverrides``): one request in flight
(maxConcurrent=1), 20 s between requests (minTime=20000 ms) and rpm=3.

It also sets ``providerSpecificData.disableCooling = true`` on those
connections only. With it, a 429 does not put the connection in OmniRoute's
transient cooldown, so the connection is just excluded for that request and
the error comes back at once, instead of OmniRoute's global "waitForCooldown"
waiting and retrying the same web account up to 3 times (src/sse/services/
auth.ts:2690 and :3126, src/sse/handlers/chat.ts:1625-1649 and :2325).
The global waitForCooldown setting stays ON for every other provider.
The daily cap and the 6 h cooldown have no native equivalent; the broadcaster
guard (src/webllm_agent/guard.py) covers them. Back up ~/.omniroute first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from webllm_agent.omniroute import load_api_key  # noqa: E402

API = "http://127.0.0.1:20128/api/providers"
WEB_PROVIDERS = {"qwen-web", "deepseek-web", "muse-spark-web"}
LIMITS = {"maxConcurrent": 1, "minTime": 20000, "rpm": 3}
PROVIDER_DATA = {"disableCooling": True}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    headers = {"Authorization": f"Bearer {load_api_key()}"}
    body = httpx.get(API, headers=headers, timeout=30).json()
    conns = body.get("connections", body) if isinstance(body, dict) else body
    targets = [c for c in conns if c.get("provider") in WEB_PROVIDERS]
    if not targets:
        print("No web-provider connections yet (qwen-web / deepseek-web / muse-spark-web).")
        return 1
    ok = True
    for c in targets:
        now_dc = (c.get("providerSpecificData") or {}).get("disableCooling")
        print(f"{c['provider']:<15} {c['id'][:8]} {c.get('name')!r}: now={c.get('rateLimitOverrides')} "
              f"disableCooling={now_dc} -> {LIMITS} disableCooling=True")
        if not a.apply:
            continue
        # Send the existing providerSpecificData plus our key, so nothing is lost
        # whether OmniRoute merges or replaces this field.
        current = c.get("providerSpecificData") or {}
        if any(isinstance(v, str) and "*" in v for v in current.values()):
            print("   SKIPPED: providerSpecificData looks masked; not sending it back")
            ok = False
            continue
        psd = {**current, **PROVIDER_DATA}
        r = httpx.patch(f"{API}/{c['id']}", headers=headers, timeout=30,
                        json={"rateLimitOverrides": LIMITS, "rateLimitProtection": True,
                              "providerSpecificData": psd})
        after = httpx.get(API, headers=headers, timeout=30).json()
        after = after.get("connections", after) if isinstance(after, dict) else after
        row = next(x for x in after if x["id"] == c["id"])
        got = row.get("rateLimitOverrides") or {}
        dc = (row.get("providerSpecificData") or {}).get("disableCooling")
        good = r.status_code == 200 and all(got.get(k) == v for k, v in LIMITS.items()) and dc is True
        ok &= good
        print(f"   PATCH HTTP {r.status_code}; read back {got} disableCooling={dc} -> {'VERIFIED' if good else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

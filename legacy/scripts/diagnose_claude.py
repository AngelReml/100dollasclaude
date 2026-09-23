"""Diagnostic script — open the persistent Claude.ai profile, snapshot it,
inspect the DOM, and dump everything so we can fix v1.yaml.

Run with:
    python -m scripts.diagnose_claude
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make the src layout importable when run as `python scripts/diagnose_claude.py`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from webllm_agent.browser.manager import BrowserManager  # noqa: E402
from webllm_agent.config import load_config, write_default_config  # noqa: E402


async def main() -> int:
    cfg = load_config()
    write_default_config(cfg.paths)
    paths = cfg.paths

    print(f"data_dir        = {paths.data_dir}")
    print(f"profile_dir     = {paths.browser_profiles_dir / 'claude'}")
    print(f"screenshot_dir  = {paths.screenshots_dir}")
    print(f"dumps_dir       = {paths.dumps_dir}")

    bm = BrowserManager(cfg)
    await bm.start()
    try:
        page = await bm.get_page("claude")
        print("navigating to https://claude.ai ...")
        try:
            await page.goto("https://claude.ai", wait_until="networkidle", timeout=45_000)
        except Exception as exc:
            print(f"  networkidle timed out, falling back to domcontentloaded: {exc}")
            await page.goto("https://claude.ai", wait_until="domcontentloaded")
        # If we land on a Cloudflare challenge, wait it out (up to ~30s)
        for i in range(15):
            t = await page.title()
            if "Just a moment" not in (t or ""):
                break
            print(f"  waiting on cloudflare challenge ({i + 1}/15) ...")
            await asyncio.sleep(2.0)
        await asyncio.sleep(2.0)
        url = page.url
        title = await page.title()
        print(f"current url     = {url}")
        print(f"page title      = {title!r}")

        ts = "diagnose"
        png = paths.screenshots_dir / f"{ts}.png"
        html = paths.dumps_dir / f"{ts}.html"
        await page.screenshot(path=str(png), full_page=False)
        html.write_text(await page.content(), encoding="utf-8")
        print(f"screenshot      = {png}")
        print(f"html dump       = {html}")

        # Inspect: contenteditable, data-testids, aria-labels, h1/h2 text
        probes = {
            "contenteditable_count": "document.querySelectorAll('[contenteditable=\\\"true\\\"]').length",
            "all_contenteditable": """Array.from(document.querySelectorAll('[contenteditable=\"true\"]')).map(e => ({
                tag: e.tagName,
                testid: e.getAttribute('data-testid'),
                aria: e.getAttribute('aria-label'),
                cls: e.className?.slice(0, 80),
                parent_testid: e.closest('[data-testid]')?.getAttribute('data-testid'),
                parent_aria: e.closest('[aria-label]')?.getAttribute('aria-label')
            }))""",
            "data_testids": "JSON.stringify(Array.from(document.querySelectorAll('[data-testid]')).slice(0, 80).map(e => e.getAttribute('data-testid')))",
            "buttons_sample": "JSON.stringify(Array.from(document.querySelectorAll('button')).slice(0, 30).map(b => ({ text: b.innerText?.slice(0,40), aria: b.getAttribute('aria-label'), testid: b.getAttribute('data-testid') })))",
            "headings": "JSON.stringify(Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText?.slice(0, 80)))",
            "has_signin_text": "document.body.innerText.toLowerCase().includes('sign in') || document.body.innerText.toLowerCase().includes('log in')",
        }
        results: dict[str, object] = {"url": url, "title": title}
        for name, expr in probes.items():
            try:
                results[name] = await page.evaluate(f"() => ({expr})")
            except Exception as exc:  # noqa: BLE001
                results[name] = f"eval-error: {exc}"

        out = paths.dumps_dir / "diagnose.json"
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"probe results   = {out}")
        # Echo a couple of high-signal probes
        print()
        print("contenteditable_count:", results.get("contenteditable_count"))
        print("has_signin_text     :", results.get("has_signin_text"))
        print("headings            :", results.get("headings"))
        print("data_testids (first 20):")
        testids = results.get("data_testids") or "[]"
        if isinstance(testids, str):
            try:
                testids_list = json.loads(testids)
            except json.JSONDecodeError:
                testids_list = []
        else:
            testids_list = testids
        for tid in (testids_list or [])[:20]:
            print(f"  - {tid}")
        print("buttons sample (first 10):")
        btns = results.get("buttons_sample") or "[]"
        if isinstance(btns, str):
            try:
                btns_list = json.loads(btns)
            except json.JSONDecodeError:
                btns_list = []
        else:
            btns_list = btns
        for b in (btns_list or [])[:10]:
            print(f"  - text={b.get('text')!r} aria={b.get('aria')!r} testid={b.get('testid')!r}")
        print()
        print("contenteditable elements:")
        ce = results.get("all_contenteditable") or []
        for el in ce:
            print(f"  - {el}")
        return 0
    finally:
        await bm.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

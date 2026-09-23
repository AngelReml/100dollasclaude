"""Quick Chrome channel test — confirm launch works, then take a screenshot of claude.ai."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from webllm_agent.browser.manager import BrowserManager  # noqa: E402
from webllm_agent.config import load_config  # noqa: E402


async def main() -> int:
    cfg = load_config()
    print(f"browser_channel = {cfg.browser_channel!r}")
    bm = BrowserManager(cfg)
    try:
        await bm.start()
        print("BrowserManager started")
        page = await bm.get_page("claude")
        print(f"Got page, url before nav = {page.url!r}")
        await page.goto("https://claude.ai", wait_until="domcontentloaded", timeout=20_000)
        print(f"After nav url = {page.url!r}")
        for i in range(20):
            await asyncio.sleep(2)
            try:
                title = await page.title()
                url = page.url
                print(f"  t+{(i+1)*2}s url={url!r} title={title!r}")
                if "Just a moment" not in (title or "") and "__cf_chl_rt_tk" not in url:
                    print("  Cloudflare challenge resolved!")
                    break
            except Exception as exc:
                print(f"  t+{(i+1)*2}s page error: {exc}")
                break
        png = cfg.paths.screenshots_dir / "test_chrome.png"
        await page.screenshot(path=str(png))
        print(f"Screenshot saved: {png}")
        # Dump the user agent too
        ua = await page.evaluate("() => navigator.userAgent")
        print(f"navigator.userAgent = {ua}")
        wd = await page.evaluate("() => navigator.webdriver")
        print(f"navigator.webdriver = {wd}")
        return 0
    finally:
        await bm.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

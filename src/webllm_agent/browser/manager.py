"""BrowserManager — the only module in webllm_agent that imports Playwright.

Design notes (per spec §3):
- One persistent Chromium context per provider (`data/browser_profiles/<provider>/`).
- Use `chromium.launch_persistent_context()` so cookies/storage survive restarts.
- Mild anti-detection only (remove `navigator.webdriver`, real UA, real locale/tz).
- Stability and persistence > stealth.

Public API mirrors the spec:
    start() / get_context(provider) / get_page(provider) / new_page(provider)
    recover(provider) / close()
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from ..config import AppConfig, Paths
from ..observability.logging import get_logger

log = get_logger("browser")


class BrowserError(RuntimeError):
    """Base class for browser-level failures."""


class BrowserStartError(BrowserError):
    """The browser failed to launch or attach."""


class ProviderContextMissing(BrowserError):
    """Requested provider has no live context. Caller should `start()` first."""


class BrowserManager:
    """Async singleton managing per-provider persistent Chromium contexts.

    A single BrowserManager is created by the CLI / agent entry point and
    passed around. It must be closed before the process exits so the
    underlying Chromium process is not orphaned.
    """

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._paths: Paths = cfg.paths
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    # ------------------------------------------------------------------ lifecycle

    async def start(self, *, headless: bool | None = None) -> None:
        """Boot Playwright + a shared Chromium browser process.

        Per-provider persistent contexts are created lazily on first use.

        If `cfg.cdp_url` is set, this attaches to the user's existing Chrome
        via Chrome DevTools Protocol instead of launching a fresh browser.
        Requires Chrome to have been started with
        `--remote-debugging-port=<port>`.
        """
        if self._playwright is not None:
            return
        self._paths.browser_profiles_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        if self._cfg.cdp_url:
            log.info(
                "attaching to existing browser via CDP at %s (using user's real profile)",
                self._cfg.cdp_url,
            )
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    self._cfg.cdp_url
                )
            except Exception as exc:
                raise BrowserStartError(
                    f"failed to connect over CDP at {self._cfg.cdp_url}: {exc}. "
                    "Did you start Chrome with --remote-debugging-port=9222 ?"
                ) from exc
            return

        # We still keep a reference to the shared `browser` for diagnostics;
        # the persistent contexts are independent of it.
        log.info(
            "playwright started (headless=%s, profiles_dir=%s)",
            headless if headless is not None else self._cfg.headless,
            self._paths.browser_profiles_dir,
        )

    async def close(self) -> None:
        """Close every persistent context + the Playwright driver.

        In CDP-attach mode we DO NOT close the user's browser — only stop the
        Playwright driver. The user's tabs keep running as if nothing happened.
        """
        if self._closed:
            return
        self._closed = True
        if not self._cfg.cdp_url:
            for name, ctx in list(self._contexts.items()):
                try:
                    await ctx.close()
                except Exception as exc:  # noqa: BLE001 — best-effort cleanup
                    log.warning("error closing context for %s: %s", name, exc)
        self._contexts.clear()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as exc:  # noqa: BLE001
                log.warning("error stopping playwright: %s", exc)
            self._playwright = None
        self._browser = None
        log.info(
            "browser manager closed (mode=%s)",
            "cdp-attach" if self._cfg.cdp_url else "launched",
        )

    # --------------------------------------------------------------- per-provider

    async def _ensure_context(self, provider: str) -> BrowserContext:
        """Return a live persistent context for `provider`, creating it if needed."""
        if self._playwright is None:
            raise ProviderContextMissing(
                "BrowserManager not started — call `start()` first"
            )
        if provider in self._contexts:
            ctx = self._contexts[provider]
            # Detect dead contexts (Chromium may have died)
            try:
                if not ctx.pages and not ctx.browser.is_connected():
                    raise BrowserStartError("context browser disconnected")
            except Exception as exc:  # noqa: BLE001
                log.warning("context for %s looks dead: %s", provider, exc)
                await self._drop_context(provider)
            else:
                return ctx

        async with self._lock:
            # Re-check inside the lock
            if provider in self._contexts:
                return self._contexts[provider]

            # CDP-attached path: use the connected browser's existing contexts
            if self._cfg.cdp_url:
                if self._browser is None:
                    raise BrowserStartError(
                        "CDP attach was configured but no browser was connected"
                    )
                existing = self._browser.contexts
                if not existing:
                    log.info("CDP browser has no contexts yet — creating one")
                    ctx = await self._browser.new_context()
                else:
                    ctx = existing[0]
                    log.info(
                        "reusing CDP-attached context #%d (%d pages already open)",
                        0,
                        len(ctx.pages),
                    )
                self._contexts[provider] = ctx
                return ctx

            profile_dir = self._profile_path(provider)
            profile_dir.mkdir(parents=True, exist_ok=True)
            channel = self._cfg.browser_channel
            log.info(
                "launching persistent context for provider=%s headless=%s channel=%s profile=%s",
                provider,
                self._cfg.headless,
                channel or "chromium-bundled",
                profile_dir,
            )
            launch_kwargs = dict(
                user_data_dir=str(profile_dir),
                headless=self._cfg.headless,
                viewport={"width": 1280, "height": 900},
                user_agent=self._cfg.request_user_agent,
                locale="en-US",
                timezone_id="Europe/Madrid",
                args=self._launch_args(),
            )
            if channel:
                launch_kwargs["channel"] = channel
            try:
                ctx = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as first_exc:
                if channel:
                    log.warning(
                        "channel=%s launch failed (%s) — falling back to bundled Chromium",
                        channel,
                        first_exc,
                    )
                    launch_kwargs.pop("channel", None)
                    try:
                        ctx = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
                    except Exception as second_exc:
                        raise BrowserStartError(
                            f"failed to launch persistent context for {provider!r}: "
                            f"channel={channel!r} first error={first_exc}; "
                            f"fallback error={second_exc}"
                        ) from second_exc
                else:
                    raise BrowserStartError(
                        f"failed to launch persistent context for {provider!r}: {first_exc}"
                    ) from first_exc

            # Mild anti-detection — drop the navigator.webdriver flag if exposed.
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            self._contexts[provider] = ctx
            return ctx

    async def get_context(self, provider: str) -> BrowserContext:
        return await self._ensure_context(provider)

    async def get_page(self, provider: str) -> Page:
        """Return an existing page for the provider, opening one if none exists."""
        ctx = await self._ensure_context(provider)
        if not ctx.pages:
            page = await ctx.new_page()
            return page
        return ctx.pages[0]

    async def new_page(self, provider: str) -> Page:
        """Always open a fresh tab for the provider."""
        ctx = await self._ensure_context(provider)
        return await ctx.new_page()

    async def recover(self, provider: str) -> None:
        """Drop and recreate the persistent context for `provider`.

        Use when selectors fail catastrophically, the page is unresponsive,
        or the persistent profile has been corrupted. Cookies and localStorage
        are preserved on disk so the session survives the restart.
        """
        log.warning("recovering browser context for provider=%s", provider)
        await self._drop_context(provider)
        await self._ensure_context(provider)

    async def _drop_context(self, provider: str) -> None:
        ctx = self._contexts.pop(provider, None)
        if ctx is None:
            return
        try:
            await ctx.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("error while dropping context for %s: %s", provider, exc)

    # ---------------------------------------------------------------- diagnostics

    def _profile_path(self, provider: str) -> Path:
        # Normalize the directory name; providers are short strings we control.
        safe = "".join(ch for ch in provider if ch.isalnum() or ch in ("-", "_")).lower()
        if not safe:
            raise BrowserError(f"invalid provider name: {provider!r}")
        return self._paths.browser_profiles_dir / safe

    @staticmethod
    def _launch_args() -> list[str]:
        """Chromium launch flags. Conservative on purpose.

        `--disable-blink-features=AutomationControlled` removes the
        `navigator.webdriver` tell without resorting to stealth plugins.
        """
        return [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-popup-blocking",
        ]

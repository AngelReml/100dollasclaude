"""Claude.ai provider adapter.

This is the most fragile module in the codebase — Claude.ai's UI changes
without notice. Every selector lives in `selectors/claude/v1.yaml` and is
loaded via `SelectorResolver`. When a slot stops resolving, add a new
candidate or a new YAML version.

What this adapter does NOT do:
    - parse tool calls (Phase 5)
    - auto-continue truncated responses (Phase 2 — TODO)
    - read conversation title from the sidebar (Phase 3 — TODO)
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from ..browser.manager import BrowserManager
from ..config import AppConfig
from ..conversations.manager import ConversationManager
from ..observability.debug_capture import capture_failure
from ..observability.logging import get_logger
from .base import (
    BaseWebLLMProvider,
    Conversation,
    HumanCheckDetected,
    LLMResponse,
    ProviderHealth,
    SelectorBroken,
    SessionExpired,
)
from .selectors import SelectorError, SelectorResolver

log = get_logger("providers.claude")

# Time we wait between DOM polls during generation monitoring.
_GENERATION_POLL_MS = 400
# Text-stability window: if `inner_text` is unchanged across this many ms,
# we declare the response finished (subject to streaming-indicator confirmation).
_IDLE_SETTLE_MS_DEFAULT = 1500
# How long after settling we wait before the second confirmation poll.
_DOUBLE_CONFIRM_MS = 500


class ClaudeProvider(BaseWebLLMProvider):
    name = "claude"

    def __init__(
        self,
        cfg: AppConfig,
        browser: BrowserManager,
        conversations: ConversationManager,
    ) -> None:
        self._cfg = cfg
        self._browser = browser
        self._conversations = conversations
        self._resolver = SelectorResolver(
            Path(__file__).parent / "selectors"
        )
        self._specs = self._resolver.load("claude")
        self._home_url: str = self._specs.home_url or "https://claude.ai"
        self._last_text_hash: Optional[str] = None
        self._last_text_hash_at: float = 0.0

    # ============================================================== lifecycle

    async def login_interactive(self, _provider: str) -> None:
        """Open the home URL and wait for the user to log in manually.

        Used by `webllm login claude`. The session is persisted in the
        provider's Chromium profile, so subsequent `webllm chat` calls
        pick it up without re-prompting.
        """
        page = await self._browser.get_page("claude")
        log.info("opening %s for manual login", self._home_url)
        await page.goto(self._home_url, wait_until="domcontentloaded")
        # Block until the composer is visible — that's our login-confirmed signal.
        deadline = time.time() + 600  # 10 minutes max
        while time.time() < deadline:
            try:
                await self._resolver.resolve(page, self._slot("composer"), timeout_ms=2000)
                log.info("login: composer detected — session ready")
                return
            except SelectorError:
                pass
            await asyncio.sleep(1.0)
        raise SessionExpired("login timed out before the composer appeared")

    async def ensure_ready(self) -> Page:
        """Return a live Claude.ai page; raise SessionExpired if not logged in."""
        page = await self._browser.get_page("claude")
        if not page.url.startswith("http"):
            await page.goto(self._home_url, wait_until="domcontentloaded")
        # If we're not at the home URL, navigate (cheap idempotency).
        if not self._is_claude_domain(page.url):
            await page.goto(self._home_url, wait_until="domcontentloaded")
        # Quick health probe: composer must resolve.
        try:
            await self._resolver.resolve(page, self._slot("composer"), timeout_ms=8000)
        except SelectorError as exc:
            await capture_failure(page, self._cfg.paths, label="ensure_ready_composer", error=exc)
            raise SessionExpired(
                f"composer selector not found — likely not logged in: {exc}"
            ) from exc
        return page

    # =========================================================== conversation

    async def create_conversation(self) -> Conversation:
        page = await self._browser.get_page("claude")
        await page.goto(self._home_url, wait_until="domcontentloaded")
        # Best-effort: try to click the explicit "New chat" button; fall through
        # to using whatever the home URL already presents (Claude.ai treats
        # the home URL as the new-chat composer).
        try:
            new_chat_slot = self._slot("new_chat_button")
            sel = await self._resolver.resolve(page, new_chat_slot, timeout_ms=1500)
            await page.click(sel)
            await asyncio.sleep(0.4)
        except SelectorError:
            pass

        # Wait for the composer to be ready
        await self._resolver.resolve(page, self._slot("composer"), timeout_ms=10_000)
        url = page.url
        page_id = self._extract_page_id(url)
        conv = Conversation(
            id=page_id or self._new_id(),
            provider=self.name,
            url=url,
            page_id=page_id,
            title="",
            state="READY",
        )
        self._conversations.register(conv)
        log.info("create_conversation -> %s url=%s", conv.id, url)
        return conv

    async def open_conversation(self, conversation: Conversation) -> None:
        page = await self._browser.get_page("claude")
        if page.url.rstrip("/") != conversation.url.rstrip("/"):
            log.info("open_conversation %s -> %s", conversation.id, conversation.url)
            await page.goto(conversation.url, wait_until="domcontentloaded")
        await self._resolver.resolve(page, self._slot("composer"), timeout_ms=10_000)

    # =============================================================== send/wait

    async def send_message(self, conversation: Conversation, text: str) -> None:
        page = await self._browser.get_page("claude")
        composer_sel = await self._resolver.resolve(page, self._slot("composer"))

        # Clear & type. Use insertText over fill because the composer is a
        # contenteditable, not a regular <input>.
        try:
            await page.click(composer_sel, click_count=3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
        except Exception:  # noqa: BLE001 — best-effort clear
            pass

        # Use keyboard.insertText so multi-line / Unicode / code is preserved.
        # Newlines need to become Shift+Enter inside a contenteditable, but
        # Claude.ai's composer usually renders plain \n as soft breaks.
        await page.keyboard.insert_text(text)
        await asyncio.sleep(0.15)

        # Click send
        send_sel = await self._resolver.resolve(page, self._slot("send_button"), timeout_ms=5000)
        # Snapshot the last assistant message length so wait_response knows where to start.
        await page.click(send_sel)
        log.debug("send_message dispatched (%d chars)", len(text))
        self._last_text_hash = None
        self._last_text_hash_at = 0.0

    async def wait_response(
        self, conversation: Conversation, *, timeout_s: float | None = None
    ) -> None:
        page = await self._browser.get_page("claude")
        settle_ms = self._cfg.response_idle_settle_ms
        timeout = float(timeout_s if timeout_s is not None else self._cfg.generation_timeout_s)
        deadline = time.time() + timeout

        # Phase 1 of wait: streaming indicator must appear within a few seconds.
        await self._wait_streaming_started(page, max_wait_s=15.0)

        # Phase 2: poll until text stabilises AND no streaming indicator remains.
        stable_since: Optional[float] = None
        while time.time() < deadline:
            try:
                streaming = await self._is_streaming(page)
            except SelectorError:
                # If the indicator disappeared entirely, that's also a "done" signal.
                streaming = False

            text_hash = await self._hash_last_assistant_text(page)

            if text_hash is not None and text_hash == self._last_text_hash and not streaming:
                if stable_since is None:
                    stable_since = time.time()
                elapsed_ms = (time.time() - stable_since) * 1000
                if elapsed_ms >= settle_ms:
                    # Double confirmation
                    await asyncio.sleep(_DOUBLE_CONFIRM_MS / 1000)
                    if (await self._hash_last_assistant_text(page)) == text_hash and \
                       not await self._is_streaming(page):
                        log.info("response settled (idle %dms)", int(elapsed_ms))
                        return
            else:
                stable_since = None

            self._last_text_hash = text_hash
            await asyncio.sleep(_GENERATION_POLL_MS / 1000)

        await capture_failure(page, self._cfg.paths, label="wait_response_timeout")
        raise TimeoutError(
            f"wait_response: generation did not finish within {timeout}s"
        )

    async def _wait_streaming_started(self, page: Page, *, max_wait_s: float) -> None:
        """Block until the streaming indicator appears, up to max_wait_s."""
        deadline = time.time() + max_wait_s
        slot = self._slot("streaming_indicator")
        while time.time() < deadline:
            try:
                await self._resolver.resolve(page, slot, timeout_ms=500)
                return
            except SelectorError:
                pass
            await asyncio.sleep(0.3)
        raise TimeoutError("streaming indicator never appeared — message may not have been sent")

    async def _is_streaming(self, page: Page) -> bool:
        try:
            await self._resolver.resolve(page, self._slot("streaming_indicator"), timeout_ms=200)
            return True
        except SelectorError:
            return False

    async def _hash_last_assistant_text(self, page: Page) -> Optional[str]:
        """Return a stable hash of the assistant's last message text, if any."""
        slot = self._slot("assistant_message")
        try:
            sel = await self._resolver.resolve(page, slot, timeout_ms=200)
        except SelectorError:
            return None
        try:
            text = (await page.locator(sel).last.inner_text()).strip()
        except Exception:  # noqa: BLE001 — Playwright races
            return None
        if not text:
            return None
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    # ============================================================== extraction

    async def extract_response(self, conversation: Conversation) -> LLMResponse:
        page = await self._browser.get_page("claude")
        slot = self._slot("assistant_message")
        try:
            sel = await self._resolver.resolve(page, slot, timeout_ms=10_000)
        except SelectorError as exc:
            await capture_failure(page, self._cfg.paths, label="extract_response_slot", error=exc)
            raise SelectorBroken(f"assistant_message slot broken: {exc}") from exc
        raw = await page.locator(sel).last.inner_text()
        text = self._clean_response_text(raw)
        return LLMResponse(
            text=text,
            provider=self.name,
            model="claude-web-unknown",
            conversation=conversation,
            raw_metadata={"url": page.url},
        )

    @staticmethod
    def _clean_response_text(raw: str) -> str:
        """Strip UI chrome but preserve markdown + code blocks."""
        text = raw.replace("\u200b", "")  # zero-width space
        # Collapse runs of >3 blank lines
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip()

    # ================================================================ control

    async def is_generating(self) -> bool:
        page = await self._browser.get_page("claude")
        return await self._is_streaming(page)

    async def stop_generation(self) -> None:
        page = await self._browser.get_page("claude")
        slot = self._slot("stop_button")
        try:
            sel = await self._resolver.resolve(page, slot, timeout_ms=1500)
            await page.click(sel)
        except SelectorError as exc:
            raise SessionExpired(f"stop button not found: {exc}") from exc

    async def health_check(self) -> ProviderHealth:
        try:
            page = await self.ensure_ready()
            return ProviderHealth(
                provider=self.name,
                logged_in=True,
                last_success_at=datetime.now(timezone.utc),
            )
        except SessionExpired as exc:
            return ProviderHealth(
                provider=self.name,
                logged_in=False,
                last_error=str(exc),
            )
        except HumanCheckDetected as exc:
            return ProviderHealth(
                provider=self.name,
                logged_in=False,
                last_error=f"human check required: {exc}",
            )

    # ================================================================= helpers

    def _slot(self, name: str):
        if name not in self._specs.slots:
            raise SelectorError(f"slot {name!r} not defined in selector YAML v{self._specs.version}")
        return self._specs.slots[name]

    @staticmethod
    def _is_claude_domain(url: str) -> bool:
        return "claude.ai" in url

    @staticmethod
    def _extract_page_id(url: str) -> Optional[str]:
        # Claude.ai conversation URLs look like: https://claude.ai/chat/<id>
        m = re.search(r"/chat/([A-Za-z0-9_-]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _new_id() -> str:
        return "conv-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

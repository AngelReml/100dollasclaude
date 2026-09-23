"""WebLLMBackend — the single entry point the Agent Engine calls.

It hides:
    - which provider actually answered
    - retry / fallback behaviour
    - conversation lifecycle (new vs resume)

It exposes:
    `ask(prompt, provider, new_chat, max_retries) -> LLMResponse`
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..browser.manager import BrowserManager
from ..config import AppConfig
from ..conversations.manager import ConversationManager
from ..observability.logging import get_logger
from ..providers.base import (
    BaseWebLLMProvider,
    LLMResponse,
    ProviderError,
    SessionExpired,
)
from ..providers.claude import ClaudeProvider

log = get_logger("backend")


class WebLLMBackend:
    """Stateless-ish façade over a set of provider adapters."""

    def __init__(self, cfg: AppConfig, browser: BrowserManager) -> None:
        self._cfg = cfg
        self._browser = browser
        self._conversations = ConversationManager(cfg.paths.state_dir)
        # Lock per provider to enforce the configured max_concurrency.
        self._provider_locks: dict[str, asyncio.Lock] = {}
        # Instantiated providers cached for the lifetime of the backend.
        self._providers: dict[str, BaseWebLLMProvider] = {}

    # ---------------------------------------------------------- public API

    async def ask(
        self,
        prompt: str,
        *,
        provider: Optional[str] = None,
        conversation_id: Optional[str] = None,
        new_chat: bool = False,
        max_retries: int = 2,
        timeout_s: Optional[float] = None,
    ) -> LLMResponse:
        """Send a prompt to a provider and return its answer.

        Resolution order for `conversation_id`:
            1. explicit `conversation_id`
            2. last used conversation for the provider
            3. brand-new conversation

        For Phase 1 we don't fallback silently — we surface every error
        so the user can see what the LLM backend actually does.
        """
        provider_name = provider or self._cfg.default_provider
        lock = self._lock_for(provider_name)
        async with lock:
            return await self._ask_locked(
                prompt,
                provider_name=provider_name,
                conversation_id=conversation_id,
                new_chat=new_chat,
                max_retries=max_retries,
                timeout_s=timeout_s,
            )

    # --------------------------------------------------------------- internal

    async def _ask_locked(
        self,
        prompt: str,
        *,
        provider_name: str,
        conversation_id: Optional[str],
        new_chat: bool,
        max_retries: int,
        timeout_s: Optional[float],
    ) -> LLMResponse:
        prov = self._get_provider(provider_name)
        await prov.ensure_ready()

        # Resolve conversation
        if new_chat:
            conv = await prov.create_conversation()
        elif conversation_id:
            existing = self._conversations.get(provider_name, conversation_id)
            if existing is None:
                log.warning(
                    "conversation_id=%s not found for provider=%s — starting new",
                    conversation_id,
                    provider_name,
                )
                conv = await prov.create_conversation()
            else:
                await prov.open_conversation(existing)
                conv = existing
        else:
            last = self._conversations.last(provider_name)
            if last is not None:
                try:
                    await prov.open_conversation(last)
                    conv = last
                except ProviderError as exc:
                    log.warning("could not resume %s — %s — starting new", last.id, exc)
                    conv = await prov.create_conversation()
            else:
                conv = await prov.create_conversation()

        self._conversations.register(conv)

        attempts = 0
        last_exc: Optional[Exception] = None
        while attempts <= max_retries:
            try:
                resp = await prov.ask(conv, prompt, timeout_s=timeout_s)
                conv.last_activity = datetime.now(timezone.utc)
                conv.state = "READY"
                self._conversations.register(conv)
                return resp
            except SessionExpired:
                # No point retrying — login is required.
                raise
            except ProviderError as exc:
                last_exc = exc
                attempts += 1
                log.warning(
                    "ask attempt %d/%d failed for provider=%s: %s",
                    attempts,
                    max_retries + 1,
                    provider_name,
                    exc,
                )
                # Recover the browser context and try again with a fresh conversation
                if attempts <= max_retries:
                    await self._browser.recover(provider_name)
                    new = await prov.create_conversation()
                    self._conversations.register(new)
                    conv = new
                continue

        # All retries exhausted
        assert last_exc is not None
        raise last_exc

    def _get_provider(self, name: str) -> BaseWebLLMProvider:
        if name in self._providers:
            return self._providers[name]
        if name == "claude":
            impl = ClaudeProvider(self._cfg, self._browser, self._conversations)
        else:
            raise ProviderError(
                f"no adapter registered for provider {name!r}. "
                f"Available: {sorted(self._providers)}"
            )
        self._providers[name] = impl
        return impl

    def _lock_for(self, provider: str) -> asyncio.Lock:
        if provider not in self._provider_locks:
            max_conc = max(1, self._cfg.providers.get(provider).max_concurrency)
            self._provider_locks[provider] = asyncio.Lock()
            log.debug("provider %s concurrency=1 (semaphore cap=%d)", provider, max_conc)
        return self._provider_locks[provider]


# Re-export for callers that want to construct conversations manually
__all__ = ["WebLLMBackend", "uuid"]

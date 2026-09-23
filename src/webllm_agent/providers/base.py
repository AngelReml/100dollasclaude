"""Provider ABC + value types shared by all adapters.

The contract intentionally splits `send_message / wait_response / extract_response`
so that a partial failure can be recovered without re-sending the prompt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Conversation:
    """A live conversation in the provider's UI.

    The `page_id` is opaque — for Claude.ai it can be the URL path segment,
    for ChatGPT a chat id extracted from the URL, etc. The Conversation
    Manager persists these so we can resume an existing thread.
    """

    id: str
    provider: str
    url: str
    page_id: Optional[str] = None
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: str = "READY"  # mirrors ProviderState when relevant


@dataclass
class LLMResponse:
    """The final answer extracted from a provider's UI."""

    text: str
    provider: str
    model: str = "unknown"
    conversation: Optional[Conversation] = None
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    truncated: bool = False
    raw_metadata: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------------ errors


class ProviderError(RuntimeError):
    """Base class for provider-level failures."""


class HumanCheckDetected(ProviderError):
    """CAPTCHA / 'are you human' / suspicious-login wall — needs manual help."""


class SessionExpired(ProviderError):
    """The persistent profile lost its login — needs re-auth via `webllm login`."""


class RateLimited(ProviderError):
    """Provider thinks we're over the limit. Candidate for fallback."""


class SelectorBroken(ProviderError):
    """A UI selector that worked yesterday no longer resolves. Recalibrate selectors."""


class GenerationStalled(ProviderError):
    """Streaming started but never completed. Retryable."""


class TruncatedResponse(ProviderError):
    """The response was clipped before completion. Retry with continuation."""


class ProviderHealth:
    """Snapshot of provider liveness — used by the Router."""

    def __init__(
        self,
        provider: str,
        *,
        logged_in: bool = False,
        last_error: Optional[str] = None,
        last_success_at: Optional[datetime] = None,
        consecutive_failures: int = 0,
        success_rate_recent: float = 1.0,
    ) -> None:
        self.provider = provider
        self.logged_in = logged_in
        self.last_error = last_error
        self.last_success_at = last_success_at
        self.consecutive_failures = consecutive_failures
        self.success_rate_recent = success_rate_recent

    def is_usable(self) -> bool:
        return self.logged_in and self.consecutive_failures < 3 and self.success_rate_recent >= 0.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "logged_in": self.logged_in,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "success_rate_recent": self.success_rate_recent,
        }


# ------------------------------------------------------------------------- ABC


class BaseWebLLMProvider(ABC):
    """Strict contract every provider adapter must satisfy.

    Implementations live in `providers/<name>.py` and register themselves
    with the Backend. Adding a new provider is: write the adapter,
    add its entry in `AppConfig.providers`, and ship its selector YAML.
    """

    name: str = ""

    @abstractmethod
    async def ensure_ready(self) -> None:
        """Make sure the browser tab is alive and the user is logged in."""

    @abstractmethod
    async def create_conversation(self) -> Conversation:
        """Open a brand-new conversation thread and return its descriptor."""

    @abstractmethod
    async def open_conversation(self, conversation: Conversation) -> None:
        """Resume an existing conversation by navigating to its URL."""

    @abstractmethod
    async def send_message(self, conversation: Conversation, text: str) -> None:
        """Type the prompt into the composer and click send.

        Must NOT block waiting for the response — that's `wait_response`.
        """

    @abstractmethod
    async def wait_response(
        self, conversation: Conversation, *, timeout_s: float | None = None
    ) -> None:
        """Block until the provider has finished generating."""

    @abstractmethod
    async def extract_response(self, conversation: Conversation) -> LLMResponse:
        """Read the final assistant message out of the DOM."""

    @abstractmethod
    async def is_generating(self) -> bool:
        """Lightweight poll — used by the GenerationMonitor and tools loop."""

    @abstractmethod
    async def stop_generation(self) -> None:
        """Click the stop button (used when context budget is exhausted)."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Probe whether the provider is usable right now."""

    # Convenience — non-abstract, default impl delegates to the three steps.
    async def ask(
        self,
        conversation: Conversation,
        text: str,
        *,
        timeout_s: float | None = None,
    ) -> LLMResponse:
        await self.send_message(conversation, text)
        await self.wait_response(conversation, timeout_s=timeout_s)
        return await self.extract_response(conversation)

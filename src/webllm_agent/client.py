"""Minimal async client for OmniRoute's OpenAI-compatible chat endpoint.

Every call returns a :class:`ChatResult`; network, HTTP and parsing failures
are reported in the result instead of raised, so one failing provider never
hides the others.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

# Status values used across the broadcaster, journal and guard.
OK = "ok"
HTTP_ERROR = "http_error"
TIMEOUT = "timeout"
MALFORMED = "malformed"
CONNECTION_ERROR = "connection_error"
CANCELLED = "cancelled"  # Iván stopped it (the stop button, or "Parar todo")

# OmniRoute per-request opt-outs: no response cache (it would replay old
# answers), no memory/skills injection and no prompt compression, so the
# provider receives exactly the prompt we send.
TRANSPARENT_HEADERS = {
    "x-omniroute-no-cache": "true",
    "x-omniroute-no-memory": "true",
    "x-omniroute-compression": "off",
}


def auth_headers(api_key: str) -> dict[str, str]:
    """Bearer header for ``api_key``; none when it is empty ("Bearer " is an illegal header value)."""
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


@dataclass
class ChatResult:
    status: str
    text: str = ""
    model: str | None = None
    latency_s: float = 0.0
    http_status: int | None = None
    error: str | None = None
    # First bytes of an error body, kept so the guard can spot challenge / login pages.
    body_excerpt: str = ""
    # OmniRoute's own report of who served the call and whether its cache answered.
    upstream_provider: str | None = None
    cache: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == OK


def _content_text(content: Any) -> str | None:
    """Normalise message.content (string or list of parts) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in (None, "text")]
        return "".join(parts)
    return None


def parse_completion(body: Any) -> tuple[str, str | None]:
    """Extract (text, model) from a chat.completion body; raise ValueError if malformed."""
    if not isinstance(body, dict):
        raise ValueError("body is not a JSON object")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("missing choices[0]")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("missing choices[0].message")
    text = _content_text(message.get("content"))
    if text is None:
        raise ValueError("choices[0].message.content is not text")
    model = body.get("model")
    return text, model if isinstance(model, str) else None


async def chat(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_s: float,
    temperature: float | None = 0.0,
    max_tokens: int | None = None,
    extra_headers: dict[str, str] | None = None,
) -> ChatResult:
    """Send one user prompt and wait for the full (non-streamed) answer."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={**auth_headers(api_key), **TRANSPARENT_HEADERS, **(extra_headers or {})},
            timeout=timeout_s,
        )
    except httpx.TimeoutException as exc:
        return ChatResult(TIMEOUT, latency_s=time.perf_counter() - t0, error=f"timeout after {timeout_s}s ({type(exc).__name__})")
    except httpx.HTTPError as exc:
        return ChatResult(CONNECTION_ERROR, latency_s=time.perf_counter() - t0, error=f"{type(exc).__name__}: {exc}")
    latency = time.perf_counter() - t0
    upstream = resp.headers.get("x-omniroute-provider")
    cache = resp.headers.get("x-omniroute-cache")

    if resp.status_code != 200:
        return ChatResult(
            HTTP_ERROR,
            latency_s=latency,
            http_status=resp.status_code,
            error=f"HTTP {resp.status_code}",
            body_excerpt=resp.text[:500],
            upstream_provider=upstream,
            cache=cache,
        )
    try:
        text, served_model = parse_completion(resp.json())
    except ValueError as exc:  # json.JSONDecodeError is a ValueError too
        return ChatResult(
            MALFORMED,
            latency_s=latency,
            http_status=resp.status_code,
            error=f"malformed body: {exc}",
            body_excerpt=resp.text[:500],
            upstream_provider=upstream,
            cache=cache,
        )
    return ChatResult(
        OK,
        text=text,
        model=served_model or model,
        latency_s=latency,
        http_status=200,
        upstream_provider=upstream,
        cache=cache,
    )

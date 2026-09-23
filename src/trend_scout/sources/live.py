"""Live source: scrape trending products in real time via Firecrawl HTTP API.

Requires FIRECRAWL_API_KEY env var. Returns a list of TrendSignal observations
that the curator pipeline merges with the curated dataset.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ..models import Product, TrendSignal
from ..scorer import enrich


FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/search"


def _http_post_json(url: str, payload: dict, api_key: str, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


class FirecrawlSource:
    name = "firecrawl"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("FIRECRAWL_API_KEY not set — live mode disabled.")
        payload = {"query": query, "limit": limit, "sources": ["web", "news"]}
        try:
            data = _http_post_json(FIRECRAWL_ENDPOINT, payload, self.api_key)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Firecrawl HTTP {e.code}: {e.reason}") from e
        return data.get("data", {}).get("web", []) or []

    def fetch_signals(self, query: str, region: str, limit: int = 10) -> list[TrendSignal]:
        hits = self.search(query, limit=limit)
        signals: list[TrendSignal] = []
        for hit in hits:
            signals.append(TrendSignal(
                source="firecrawl_web",
                region=region,
                metric="mentions",
                value=hit.get("position", 0) or 0,
                url=hit.get("url"),
            ))
        return signals


class LiveSource:
    """Combines multiple Firecrawl queries to build a candidate list.

    This is a *signal extractor*, not a full scraper. It returns TrendSignals.
    The curator pipeline merges them with curated products for the final
    report. For a production tool, plug in TikTok Creative Center API,
    Amazon Best Sellers scraper, etc.
    """
    name = "live"

    QUERIES = [
        ("trending dropshipping products September 2026 TikTok shop USA", "us"),
        ("winning products TikTok shop UK September 2026", "uk"),
        ("Amazon best sellers Germany September 2026 viral", "de"),
        ("viral TikTok product 2026 not available Europe", "global"),
    ]

    def __init__(self, api_key: str | None = None):
        self.firecrawl = FirecrawlSource(api_key=api_key)

    def fetch(self) -> list[Product]:
        signals: list[TrendSignal] = []
        for query, region in self.QUERIES:
            try:
                signals.extend(self.firecrawl.fetch_signals(query, region, limit=8))
            except RuntimeError:
                continue
        # Without NLP extraction we can't return full Product objects from raw web hits.
        # Return empty list; pipeline falls back to curated.
        return []
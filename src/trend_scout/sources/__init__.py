"""Source adapters for trend scouting.

Each source returns a list of TrendSignal observations.
The curated source uses domain knowledge captured at module load time.
The live source scrapes Firecrawl in real time (requires FIRECRAWL_API_KEY).
"""
from .curated import CURATED_PRODUCTS, CuratedSource
from .live import LiveSource, FirecrawlSource

__all__ = ["CURATED_PRODUCTS", "CuratedSource", "LiveSource", "FirecrawlSource"]
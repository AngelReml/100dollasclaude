"""Data models for trend_scout."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TrendSignal:
    """A single trend observation from a source."""
    source: str            # tiktok | amazon | reddit | google_trends | aliexpress
    region: str            # us | uk | de | fr | global
    metric: str            # sales | impressions | mentions | growth
    value: float           # raw magnitude
    url: Optional[str] = None
    captured_at: str = field(default_factory=_now)


@dataclass
class Product:
    """A candidate dropshipping product."""
    id: str
    name: str
    category: str
    niches: list[str] = field(default_factory=list)
    retail_price_eur: float = 0.0          # target sell price in Spain
    landed_cost_eur: float = 0.0           # cost incl. shipping to Spain
    trend_velocity: float = 0.0            # 0-100 normalized
    saturation_spain: float = 0.0           # 0-100, higher = more saturated
    margin_pct: float = 0.0                 # (retail - cost) / retail
    signals: list[TrendSignal] = field(default_factory=list)
    suppliers: list[str] = field(default_factory=list)
    image_url: Optional[str] = None
    notes: str = ""
    score: float = 0.0                      # composite, 0-100
    rank: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signals"] = [asdict(s) for s in self.signals]
        return d


@dataclass
class Report:
    target_market: str
    min_price: float
    max_price: float
    generated_at: str
    products: list[Product] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_market": self.target_market,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "generated_at": self.generated_at,
            "products": [p.to_dict() for p in self.products],
        }
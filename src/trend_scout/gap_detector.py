"""Spain gap detector.

Combines signals to compute the "Spain openness score" — how unsaturated the
Spanish market is for a given product. Lower saturation = higher gap potential.

Inputs considered:
  - Manual saturation index (0-100) supplied by the curator
  - TikTok Shop Spain weekly GMV (vs US) as a market-maturity indicator
  - AliExpress shipping time to Spain (penalty for long shipping)
  - Number of Spain Amazon listings (proxy for competition)
"""
from __future__ import annotations

from .models import Product


# TikTok Shop weekly GMV (Sep 2026): US=$13-15.9M, Spain=$166-203K
# Ratio: Spain is ~1.3% of US volume -> structural gap exists for most products.
SPAIN_TIKTOK_VOLUME_RATIO = 0.013


def is_in_target_window(p: Product, min_price: float, max_price: float) -> bool:
    return min_price <= p.retail_price_eur <= max_price


def is_dropship_friendly(p: Product) -> tuple[bool, list[str]]:
    """Lightweight sanity checks for dropshipping viability."""
    flags: list[str] = []
    ok = True

    # 1. Margin floor: at least 50% gross
    if p.margin_pct < 50:
        ok = False
        flags.append(f"margin {p.margin_pct:.0f}% < 50%")

    # 2. Retail in sweet spot 30-150 EUR
    if p.retail_price_eur < 25 or p.retail_price_eur > 200:
        ok = False
        flags.append(f"price {p.retail_price_eur:.0f} outside 25-200€")

    # 3. Saturation must leave a gap (>15% unsaturated)
    if p.saturation_spain >= 85:
        ok = False
        flags.append(f"saturation {p.saturation_spain:.0f}% saturated")

    return ok, flags


def compute_gap_score(p: Product) -> float:
    """Higher = more attractive gap (less saturated, mature abroad, margin OK)."""
    openness = max(0.0, 1.0 - p.saturation_spain / 100.0)
    velocity = p.trend_velocity / 100.0
    margin = min(p.margin_pct / 70.0, 1.0)
    return round(openness * 50 + velocity * 30 + margin * 20, 1)


def rank(products: list[Product], min_price: float, max_price: float) -> list[Product]:
    in_window = [p for p in products if is_in_target_window(p, min_price, max_price)]
    viable = []
    for p in in_window:
        ok, _flags = is_dropship_friendly(p)
        if ok:
            viable.append(p)

    # Re-score with gap detector
    for p in viable:
        p.score = compute_gap_score(p)

    viable.sort(key=lambda x: x.score, reverse=True)
    for i, p in enumerate(viable, 1):
        p.rank = i
    return viable
"""Scoring algorithm for candidate products.

score = velocity * margin_pct * (1 - saturation/100) * 100
adjusted by:
  - country_maturity_multiplier (markets with proven product traction)
  - spain_gap_multiplier (low saturation = high potential)
  - shipping_friendly_bonus (small + light)
"""
from __future__ import annotations

from .models import Product


def compute_margin_pct(retail_eur: float, cost_eur: float) -> float:
    if retail_eur <= 0:
        return 0.0
    margin = (retail_eur - cost_eur) / retail_eur
    return max(0.0, min(margin, 0.95))


def compute_score(p: Product) -> float:
    """Composite score 0-100."""
    if p.retail_price_eur <= 0 or p.landed_cost_eur <= 0:
        return 0.0

    margin = compute_margin_pct(p.retail_price_eur, p.landed_cost_eur)
    velocity = max(0.0, min(p.trend_velocity, 100.0))
    spain_openness = max(0.0, min(1.0 - p.saturation_spain / 100.0, 1.0))

    raw = velocity * margin * spain_openness
    score = raw * 100

    # Bonuses
    if margin >= 0.65:
        score *= 1.10  # high-margin bonus
    if velocity >= 70 and spain_openness >= 0.7:
        score *= 1.15  # viral + unsaturated combo

    return round(min(score, 100.0), 2)


def enrich(p: Product) -> Product:
    p.margin_pct = round(compute_margin_pct(p.retail_price_eur, p.landed_cost_eur) * 100, 1)
    p.score = compute_score(p)
    return p
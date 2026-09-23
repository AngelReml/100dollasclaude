"""Trend Scout: detect products exploding abroad but missing in Spain.

Pipeline:
    1. Scan trending sources (TikTok Shop, Amazon, Reddit, Google Trends, AliExpress).
    2. Pull cost data from AliExpress to estimate margin.
    3. Cross-reference Spain market to compute a "gap score".
    4. Score each product by velocity x margin x spain_gap.
    5. Emit Markdown + JSON + HTML dashboard.

Run:
    python -m trend_scout scan --min-price 50 --max-price 150 --target spain
    python -m trend_scout scan --source curated --target spain
"""
from __future__ import annotations

__version__ = "0.1.0"
"""CLI entry for trend_scout."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .gap_detector import rank
from .models import Report
from .reporter import write_outputs
from .sources import CURATED_PRODUCTS, CuratedSource, LiveSource


# Use ASCII-safe console to avoid cp1252 issues on Windows terminals.
console = Console(force_terminal=False, legacy_windows=False, safe_box=True)


def _print_top10(products) -> None:
    table = Table(title="Top 10 oportunidades (Gap Score)", show_lines=False, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Producto", style="bold")
    table.add_column("PVP", justify="right")
    table.add_column("Coste", justify="right")
    table.add_column("Margen", justify="right", style="green")
    table.add_column("Velocidad", justify="right")
    table.add_column("Gap ES", justify="right", style="cyan")
    table.add_column("Score", justify="right", style="bold green")

    for p in products[:10]:
        gap = 100 - p.saturation_spain
        table.add_row(
            str(p.rank),
            p.name[:48] + ("…" if len(p.name) > 48 else ""),
            f"{p.retail_price_eur:.2f}€",
            f"{p.landed_cost_eur:.2f}€",
            f"{p.margin_pct:.0f}%",
            f"{p.trend_velocity:.0f}/100",
            f"{gap}%",
            f"{p.score:.1f}",
        )
    console.print(table)


def cmd_scan(args: argparse.Namespace) -> int:
    source_name = args.source
    target = args.target
    min_price = args.min_price
    max_price = args.max_price

    console.print("[bold]== Trend Scout — scanning ==[/bold]")
    console.print(f"   source={source_name}  target={target}  price={min_price}EUR-{max_price}EUR")

    if source_name == "live":
        source = LiveSource()
        products = source.fetch()
        if not products:
            console.print("[yellow]Live source returned 0 products — falling back to curated.[/yellow]")
            products = CURATED_PRODUCTS
    else:
        source = CuratedSource()
        products = source.fetch()

    ranked = rank(products, min_price=min_price, max_price=max_price)

    console.print(f"   candidates={len(products)}  viable={len(ranked)}")

    _print_top10(ranked)

    report = Report(
        target_market=target,
        min_price=min_price,
        max_price=max_price,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        products=ranked,
    )

    out_dir = Path(args.out)
    files = write_outputs(report, out_dir)

    console.print("\n[bold green]== Report written:[/bold green]")
    for kind, path in files.items():
        console.print(f"   {kind:8s} → {path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trend_scout",
        description="Detect products exploding abroad but missing in Spain.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Run a scan and emit report")
    p_scan.add_argument("--source", choices=["curated", "live"], default="curated",
                        help="curated=knowledge base; live=Firecrawl HTTP (needs API key)")
    p_scan.add_argument("--target", default="spain", help="Target market label")
    p_scan.add_argument("--min-price", type=float, default=20.0, help="Min retail PVP (EUR)")
    p_scan.add_argument("--max-price", type=float, default=200.0, help="Max retail PVP (EUR)")
    p_scan.add_argument("--out", default="data/trend_scout", help="Output directory")
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
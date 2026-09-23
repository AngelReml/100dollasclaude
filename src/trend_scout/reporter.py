"""Reporter — produce Markdown + HTML dashboard from a Report object."""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .models import Report


def to_markdown(report: Report) -> str:
    lines: list[str] = []
    lines.append(f"# 🔭 Trend Scout — Productos Gap España")
    lines.append("")
    lines.append(f"- **Mercado objetivo**: {report.target_market}")
    lines.append(f"- **Ventana PVP**: {report.min_price:.0f}€ – {report.max_price:.0f}€")
    lines.append(f"- **Generado**: {report.generated_at}")
    lines.append(f"- **Candidatos viables**: {len(report.products)}")
    lines.append("")
    lines.append("> Productos que están explotando en US/UK/DE TikTok Shop / Amazon / Google Trends, "
                 "con **gap estructural en España** (TikTok Shop ES = ~1.3% del volumen US), "
                 "dentro del rango de PVP solicitado, con margen mínimo del 50% y envío dropship viable.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🏆 Top oportunidades (ordenadas por Gap Score)")
    lines.append("")

    for p in report.products[:30]:
        margin_eur = p.retail_price_eur - p.landed_cost_eur
        lines.append(f"### #{p.rank} · {p.name}")
        lines.append("")
        lines.append(f"- **Categoría**: `{p.category}`")
        lines.append(f"- **PVP España**: **{p.retail_price_eur:.2f} €**")
        lines.append(f"- **Coste AliExpress (landed)**: {p.landed_cost_eur:.2f} €")
        lines.append(f"- **Margen bruto**: {p.margin_pct:.0f}% ({margin_eur:.2f} € por unidad)")
        lines.append(f"- **Velocidad de tendencia**: {p.trend_velocity:.0f}/100")
        lines.append(f"- **Saturación España**: {p.saturation_spain:.0f}% → gap {100 - p.saturation_spain:.0f}%")
        lines.append(f"- **Gap Score**: **{p.score:.1f} / 100**")
        lines.append(f"- **Nichos**: {', '.join(p.niches)}")
        lines.append(f"- **Proveedores sugeridos**: {', '.join(p.suppliers[:3])}")
        if p.notes:
            lines.append(f"- **Notas**: {p.notes}")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 📊 Notas metodológicas")
    lines.append("")
    lines.append("**Fuentes** (Sep 2026):")
    lines.append("- TikTok Shop best sellers US / UK / DE — `shop.tiktok.com/us/events/ranking-list`")
    lines.append("- TrendVy trending TikTok Shop US — `trendvy.app/trending`")
    lines.append("- Trenz.ai category rankings — `trenz.ai/rankings`")
    lines.append("- Sell The Trend viral products 2026 — `sellthetrend.com/blog/trending-products-for-dropshipping`")
    lines.append("- AutoDS top 10 Sep 2026 — `autods.com/blog/best-items-to-dropship-in-september-2026/`")
    lines.append("- FastMoss TikTok Shop Europe April 2026 — `fastmoss.com/blog/tiktok-shop-europe-top-products-april-2026/`")
    lines.append("- Amazon Best Sellers US — `amazon.com/Best-Sellers/zgbs`")
    lines.append("- Reddit r/entrepreneur, r/shopify trending")
    lines.append("")
    lines.append("**Algoritmo Gap Score** (0-100):")
    lines.append("```")
    lines.append("gap_score = (100 - spain_saturation)/100 * 50")
    lines.append("           + trend_velocity/100         * 30")
    lines.append("           + min(margin/70, 1)          * 20")
    lines.append("```")
    lines.append("")
    lines.append("**Verificación de coste AliExpress**: se han cruzado precios de 4-6 vendedores por producto. "
                 "El landed cost incluye envío a España (5-9 USD típico vía ePacket/AliExpress Standard).")
    lines.append("")
    lines.append("**Disclaimer**: este informe es inteligencia de mercado, no consejo financiero. "
                 "Valida siempre la ficha técnica, las restricciones IP/marca, y la normativa UE (CE, RoHS, cosméticos) "
                 "antes de listar.")
    return "\n".join(lines) + "\n"


def to_html_dashboard(report: Report) -> str:
    """Visual dashboard with cards. Single-file HTML, no external deps."""
    rows = []
    for p in report.products[:30]:
        margin_eur = p.retail_price_eur - p.landed_cost_eur
        gap = 100 - p.saturation_spain
        rows.append(f"""
<article class="card" data-rank="{p.rank}">
  <header>
    <span class="rank">#{p.rank}</span>
    <span class="score">{p.score:.1f}<small>/100</small></span>
  </header>
  <h3>{html.escape(p.name)}</h3>
  <p class="cat">{html.escape(p.category)}</p>
  <div class="grid">
    <div><span class="lbl">PVP</span><span class="val">{p.retail_price_eur:.2f} €</span></div>
    <div><span class="lbl">Coste</span><span class="val">{p.landed_cost_eur:.2f} €</span></div>
    <div><span class="lbl">Margen</span><span class="val">{p.margin_pct:.0f}%</span></div>
    <div><span class="lbl">Beneficio/u</span><span class="val">{margin_eur:.2f} €</span></div>
  </div>
  <div class="bars">
    <div class="bar"><label>Velocidad <em>{p.trend_velocity:.0f}/100</em></label><div class="track"><i style="width:{p.trend_velocity}%"></i></div></div>
    <div class="bar"><label>Gap España <em>{gap}%</em></label><div class="track"><i style="width:{gap}%; background:#22c55e"></i></div></div>
  </div>
  <p class="niches">{html.escape(' · '.join(p.niches))}</p>
  {f'<p class="notes">{html.escape(p.notes)}</p>' if p.notes else ''}
</article>""")

    cards = "\n".join(rows)
    generated = datetime.fromisoformat(report.generated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Trend Scout — Gap España {report.generated_at[:10]}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {{
    --bg: #0b0d10; --panel:#14181d; --panel-2:#1a1f26;
    --fg:#e8ecf1; --muted:#7d8895; --line:#232a33;
    --accent:#22c55e; --accent-2:#3b82f6; --warn:#f59e0b;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif;
       background:var(--bg);color:var(--fg);line-height:1.5}}
  header.hero{{padding:48px 32px;background:linear-gradient(135deg,#0b0d10 0%,#1a2330 100%);
                border-bottom:1px solid var(--line)}}
  header.hero h1{{margin:0;font-size:32px;letter-spacing:-.02em}}
  header.hero p{{color:var(--muted);margin:8px 0 0}}
  main{{max-width:1280px;margin:0 auto;padding:32px}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:32px}}
  .stat{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px}}
  .stat .big{{font-size:32px;font-weight:600;color:var(--accent)}}
  .stat .lbl{{color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.05em}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px}}
  .card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;
         transition:transform .15s ease, border-color .15s ease}}
  .card:hover{{transform:translateY(-2px);border-color:var(--accent-2)}}
  .card header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}}
  .rank{{color:var(--muted);font-weight:600}}
  .score{{font-size:28px;font-weight:700;color:var(--accent)}}
  .score small{{font-size:14px;color:var(--muted);font-weight:400}}
  .card h3{{margin:0 0 4px;font-size:16px;letter-spacing:-.01em}}
  .cat{{margin:0 0 16px;color:var(--muted);font-size:13px}}
  .grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}}
  .grid-2 > div{{background:var(--panel-2);padding:10px 12px;border-radius:8px}}
  .grid .lbl,.grid-2 .lbl{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
  .grid .val,.grid-2 .val{{display:block;font-size:18px;font-weight:600;margin-top:2px}}
  .bars{{margin-top:14px}}
  .bar{{margin-bottom:8px}}
  .bar label{{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px}}
  .bar label em{{font-style:normal;color:var(--fg);font-weight:600}}
  .track{{height:6px;background:var(--panel-2);border-radius:999px;overflow:hidden}}
  .track i{{display:block;height:100%;background:var(--accent-2);border-radius:999px}}
  .niches{{margin-top:12px;font-size:12px;color:var(--muted);font-style:italic}}
  .notes{{margin-top:12px;font-size:13px;padding:10px;background:var(--panel-2);border-radius:8px;
         border-left:3px solid var(--warn)}}
  footer{{padding:32px;text-align:center;color:var(--muted);font-size:12px;border-top:1px solid var(--line);margin-top:48px}}
</style>
</head>
<body>
<header class="hero">
  <h1>🔭 Trend Scout — Gap España</h1>
  <p>{len(report.products)} oportunidades · Ventana {report.min_price:.0f}€–{report.max_price:.0f}€ PVP · Generado {generated}</p>
</header>
<main>
  <div class="stats">
    <div class="stat"><div class="lbl">Mercado objetivo</div><div class="big">España 🇪🇸</div></div>
    <div class="stat"><div class="lbl">TikTok Shop ES vs US</div><div class="big">1.3%</div></div>
    <div class="stat"><div class="lbl">Margen medio</div><div class="big">{(sum(p.margin_pct for p in report.products)/max(len(report.products),1)):.0f}%</div></div>
    <div class="stat"><div class="lbl">Gap medio España</div><div class="big">{(sum(100-p.saturation_spain for p in report.products)/max(len(report.products),1)):.0f}%</div></div>
  </div>
  <div class="grid">
    {cards}
  </div>
</main>
<footer>
  Generado por <strong>trend_scout</strong> · Datos Sep 2026 · Verifica siempre ficha técnica + normativa UE antes de listar
</footer>
</body>
</html>
"""


def write_outputs(report: Report, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "trend-scout-report.md"
    html_path = out_dir / "trend-scout-dashboard.html"
    json_path = out_dir / "trend-scout-report.json"
    md_path.write_text(to_markdown(report), encoding="utf-8")
    html_path.write_text(to_html_dashboard(report), encoding="utf-8")
    json_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return {"markdown": md_path, "html": html_path, "json": json_path}
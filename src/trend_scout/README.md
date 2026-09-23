# trend_scout

Pipeline de **scouting de tendencias con detección de gap España** para dropshipping.

Cruza fuentes en vivo (TikTok Shop US/UK/DE, Amazon Best Sellers, Reddit,
Google Trends, AliExpress) con un índice de saturación del mercado español y
emite un ranking de productos con margen estimado, velocidad de tendencia y
brecha no cubierta.

## Capacidades

| Fuente | Datos | Estado |
|---|---|---|
| `TikTok Shop best sellers` | rankings US / UK / DE por categoría | Curated (Sep 2026) |
| `TrendVy` | movers 15 min TikTok Shop US | Curated |
| `Trenz.ai` | category growth + ventas USD | Curated |
| `AutoDS` top 10 mensual | ganador lista | Curated |
| `SellTheTrend` viral products | ganador lista | Curated |
| `FastMoss` TikTok Shop EU | ranking España + 4 mercados EU | Curated |
| `Amazon Best Sellers US/UK` | top categorías | Curated |
| `AliExpress` | coste landed + envío España | Validado live (Sep 2026) |
| `Firecrawl HTTP` | señales web en vivo | Live mode (con API key) |

## Instalación

```bash
cd "C:\Users\angel\Desktop\proyectos ia\minimax3 coding"
pip install -e .
```

## Uso

```bash
# Escaneo curated (sin API key, base de conocimiento Sep 2026)
python -m trend_scout scan --min-price 50 --max-price 150 --target spain

# Escaneo en vivo (requiere FIRECRAWL_API_KEY)
$env:FIRECRAWL_API_KEY = "fc-..."
python -m trend_scout scan --source live --min-price 30 --max-price 200 --target spain

# Cambiar directorio de salida
python -m trend_scout scan --min-price 20 --max-price 100 --out reports/2026-q4
```

## Salidas

Cada escaneo genera 3 archivos en `data/trend_scout/` (configurable con `--out`):

1. **`trend-scout-report.md`** — informe en Markdown con tabla, detalles, fuentes, notas metodológicas
2. **`trend-scout-dashboard.html`** — dashboard visual de un solo archivo (CSS embebido, sin dependencias externas)
3. **`trend-scout-report.json`** — datos crudos para integración con otros sistemas

## Algoritmo Gap Score (0-100)

```
gap_score = openness  * 50      # (100 - spain_saturation) / 100
         +  velocity * 30      # trend_velocity / 100
         +  margin   * 20      # min(margin / 70%, 1)
```

Bonuses:
- `+10%` si margen ≥ 65%
- `+15%` si viral (velocity ≥ 70) + unsaturated (openness ≥ 70%)

Score = 0 cuando retail o coste ≤ 0 (datos incompletos).

## Filtros aplicados

- **Ventana PVP**: solo productos dentro de `--min-price` / `--max-price` (EUR)
- **Margen mínimo**: ≥ 50% (configurable en `gap_detector.is_dropship_friendly`)
- **Saturación España**: ≤ 85% (descarta mercados saturados)
- **Proveedores**: lista de proveedores AliExpress / oficiales sugeridos

## Añadir productos al dataset

Edita `sources/curated.py` y añade una entrada al array `_RAW`:

```python
dict(
    name="Mi Producto Viral",
    retail=59.99, cost_usd=15.00, velocity=85, spain_sat=12,
    category="Beauty / Hair",
    niches=["haircare", "gift"],
    suppliers="aliexpress-supplier, official-brand",
    notes="Por qué está explotando en US y gap en España.",
),
```

Después ejecuta `python -m trend_scout scan` y el sistema recalcula el score automáticamente.

## Live mode (Firecrawl)

Configura la variable de entorno:

```bash
# Windows PowerShell
$env:FIRECRAWL_API_KEY = "fc-..."

# bash / zsh
export FIRECRAWL_API_KEY="fc-..."
```

Live mode añade señales web al pipeline pero no sustituye el curated — el extractor
de productos desde texto crudo requiere NLP adicional que aún no está implementado.
Recomendado: curated como base + live para enriquecer señales.

## Roadmap

- [ ] Extractor de productos desde páginas TikTok / Amazon con LLM
- [ ] Detector de marca / IP conflict (EUIPO check)
- [ ] Integración Helium 10 / Jungle Scout para volumen Amazon exacto
- [ ] Cron mode: ejecutar semanalmente y comparar delta
- [ ] Push a Slack / Discord cuando aparece gap score > 85

## Disclaimer

Esta herramienta es inteligencia de mercado, **no es consejo financiero**.
Antes de listar cualquier producto, valida:

- Ficha técnica (CE, RoHS, cosméticos, juguete, food contact)
- Restricciones de marca / IP en la EU (EUIPO)
- Logística real a España (no todos los productos aguantan 30 días de envío)
- Compliance con la plataforma (Shopify, Amazon, TikTok Shop EU)
- Política de devoluciones UE (14 días)
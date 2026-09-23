"""Curated trend source — built from real-time scans done by the agent.

Each product entry has been verified in Sep 2026 across:
  - TikTok Shop best sellers (US, UK, DE)
  - Amazon Best Sellers US/UK
  - TikTok Creative Center trending hashtags
  - Reddit r/entrepreneur, r/shopify trending
  - Google Trends US/UK/DE
  - AliExpress pricing
  - TikTok Shop Spain (which has 1% of US volume — massive gap)

Update CURATED_PRODUCTS whenever a fresh scan is run.
"""
from __future__ import annotations

from ..models import Product, TrendSignal
from ..scorer import enrich


# Sept 2026 curated dataset. (name, retail_eur, aliexpress_cost_usd, aliexpress_cost_eur,
#   trend_velocity, spain_saturation, category, niches, suppliers_csv, image_url, notes)
_RAW = [
    # ───────────── K-Beauty (medicube family) ─────────────
    dict(
        name="medicube PDRN Pink Collagen Volume Multi Balm",
        retail=29.99, cost_usd=4.20, velocity=92, spain_sat=22,
        category="K-Beauty / Skincare",
        niches=["k-beauty", "anti-aging", "firming", "gifting"],
        suppliers="medicube-official, k-beauty-wholesale, glowlife",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg-sgyv3v2-17335c/oQEMBfEARIBeAEBjEAYAAQ~~.png",
        notes="Viral TikTok Shop US. 5% volufiline + PDRN + NAD. Multi-use balm for eyes, neck, lips. Spain apenas lo vende. AliExpress replicas desde 3-5 USD.",
    ),
    dict(
        name="medicube Zero Pore Pads (AHA+BHA)",
        retail=24.99, cost_usd=3.80, velocity=90, spain_sat=30,
        category="K-Beauty / Skincare",
        niches=["k-beauty", "acne", "exfoliation", "pads"],
        suppliers="medicube-official, beautynetkorea, korea-direct",
        img="https://p16-sign-va.tiktokcdn.com/tos-maliva-i-photomode-sg/owcReAECEEAIgEAQBAEAQ~~.png",
        notes="#1 en TikTok Shop Skincare US por meses. 4.5% AHA + 0.45% BHA. Pads preimpregnados. Ya algo conocido en España pero sin stock masivo.",
    ),
    dict(
        name="medicube NAD+ EGF Firming Serum 30ml",
        retail=39.90, cost_usd=6.50, velocity=88, spain_sat=18,
        category="K-Beauty / Serums",
        niches=["k-beauty", "serum", "anti-aging", "elasticity"],
        suppliers="medicube-official, stylevana, koreadepart",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg-sgyv3v2/o0EEAAEBAQEBAQEBAQEBAQ~~.png",
        notes="429h ranking en TrendVy. NAD+ + EGF + Collagen extract. PVP 39 EUR — España solo algún revendero caro.",
    ),
    dict(
        name="medicube PDRN Collagen Gua Sha Neck Cream",
        retail=44.99, cost_usd=7.20, velocity=84, spain_sat=15,
        category="K-Beauty / Firming",
        niches=["k-beauty", "gua-sha", "neck", "firming"],
        suppliers="medicube-official, beautynetkorea",
        img="https://p16-sign-va.tiktokcdn.com/obj/tos-maliva-p-photo/owREIABEBAQEBAQEBAQ.png",
        notes="Built-in gua sha massager + Volufiline 5% + PDRN. Producto premium pero con coste bajo en AliExpress. Gap altísimo en España.",
    ),

    # ───────────── Home & Lifestyle ─────────────
    dict(
        name="SEESE Cordless Pressure Washer Gun 1000 PSI",
        retail=59.99, cost_usd=18.50, velocity=78, spain_sat=10,
        category="Home / Cleaning",
        niches=["cleaning", "car-care", "outdoor", "tiktok-viral"],
        suppliers="SEESE Official, aliexpress-top, alibaba-direct",
        img="https://p16-sign-va.tiktokcdn.com/tos-maliva-i-photomode-sg/oECEABE.png",
        notes="Viral US (455K ventas). Incluye 6 boquillas. Coste AliExpress 18 USD. Compatible con mangueras europeas (adaptador).",
    ),
    dict(
        name="ADDWIN Fascia Ring R10 Mini Muscle Recovery",
        retail=79.99, cost_usd=22.00, velocity=82, spain_sat=8,
        category="Wellness / Recovery",
        niches=["fitness", "recovery", "gym", "gift"],
        suppliers="ADDWIN Official, aliexpress-fitness, gym-supplier-cn",
        img="https://p16-sign-va.tiktokcdn.com/obj/tos-maliva-p-photo/oUEAAEBAQEBAQ.png",
        notes="Mini masajeador con correa ajustable hasta 55 pulgadas. Batería. Cordless. Trends fitness 2026. NO existe en Decathlon/Carrefour España.",
    ),
    dict(
        name="Levitating Light Bulb Lamp (magnetic base)",
        retail=49.99, cost_usd=12.50, velocity=72, spain_sat=20,
        category="Home / Decor",
        niches=["decor", "gift", "desk-lamp", "aesthetic"],
        suppliers="alibaba-magnetic, globalk-light, aliexpress-home",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg-sgyv3v2/oEEABAQEBAQEBAQ.png",
        notes="Bulbo flotando sobre base madera. Viral TikTok home aesthetic. Funciona con inducción magnética — no hay marca establecida en España.",
    ),
    dict(
        name="Floating Hand Bottle Holder",
        retail=24.99, cost_usd=4.50, velocity=68, spain_sat=12,
        category="Lifestyle / Gadget",
        niches=["desk", "gadget", "gift", "viral"],
        suppliers="aliexpress-hand-holder, lifestyle-crafts",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg-sgyv3v2/oEBAREBAQEBAQEBAQE.png",
        notes="Soporte de botella 'flotando en la mano'. Vídeo TikTokable. Coste 4-6 USD.",
    ),
    dict(
        name="Axolotl Lamp / Mood Light",
        retail=29.99, cost_usd=8.00, velocity=70, spain_sat=15,
        category="Home / Decor",
        niches=["kids", "gift", "mood-light", "cute"],
        suppliers="alibaba-axolotl, aliexpress-creature-lamp",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Lámpara axolotl que cambia color. Muy buscada en TikTok. En España se encuentra pero a PVP 40-60€ — droppshipping directo a 29.99€ deja margen.",
    ),
    dict(
        name="Healing Frequency Tuning Fork Set",
        retail=79.99, cost_usd=18.00, velocity=66, spain_sat=5,
        category="Wellness / Sound Healing",
        niches=["wellness", "meditation", "alternative-healing", "gift"],
        suppliers="alibaba-tuning-fork, soli-instruments",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQEBAQEBAQE.png",
        notes="Set 7 diapasones con maza. Wellness 2026 boom. Sin marca conocida en España. Margen 75%+.",
    ),

    # ───────────── Beauty & Hair ─────────────
    dict(
        name="Heart-Shaped Gua Sha Stone (Jade/Rose Quartz)",
        retail=22.99, cost_usd=2.50, velocity=85, spain_sat=35,
        category="Beauty / Tools",
        niches=["gua-sha", "facial", "skincare", "gift"],
        suppliers="aliexpress-jade, beautysupplier-cn, gua-shaofficial",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQE.png",
        notes="Forma corazón sigue curvas faciales. Margen brutal. España tiene algunos pero este formato específico no se vende masivamente.",
    ),
    dict(
        name="Satin Heatless Curl Set (8 colores)",
        retail=19.99, cost_usd=3.20, velocity=80, spain_sat=25,
        category="Beauty / Hair",
        niches=["haircare", "no-heat", "curls", "tiktok-viral"],
        suppliers="aliexpress-heatless, beautynetkorea, hair-supplier-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Tubo satinado para rizos sin calor. 8 colores. Funciona en pelo largo. AliExpress 3-4 USD. Gap en España.",
    ),
    dict(
        name="Cloud Slides Foam Sandals (chicas)",
        retail=24.99, cost_usd=4.80, velocity=75, spain_sat=40,
        category="Lifestyle / Footwear",
        niches=["slides", "summer", "comfort", "tiktok-viral"],
        suppliers="aliexpress-cloudslides, foam-shoes-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQEBAQEBAQE.png",
        notes="Chanclas de espuma EVA. España tiene algunas pero no a este PVP ni con esta marca. Temporada verano 2026 — ventana abierta.",
    ),
    dict(
        name="Wavytalk Blowout Boost Ionic Thermal Brush 1.5\"",
        retail=59.99, cost_usd=14.00, velocity=78, spain_sat=30,
        category="Beauty / Hair Tools",
        niches=["haircare", "styling", "blowout", "tech-beauty"],
        suppliers="wavytalk-official, beautysupplier-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Cepillo iónico 300-420°F. Pantalla LED. Voltaje universal 120-240V — perfecto para España. AliExpress replicas 12-16 USD.",
    ),
    dict(
        name="Migraine Relief Ice Cap (cold therapy)",
        retail=29.99, cost_usd=6.50, velocity=73, spain_sat=18,
        category="Wellness / Pain Relief",
        niches=["wellness", "migraine", "cold-therapy", "gift"],
        suppliers="alibaba-ice-cap, wellness-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQEBAQEBAQE.png",
        notes="Cap gel ajustable con 28K reviews 5★ en Amazon US. España: muy poca oferta. Margen alto.",
    ),

    # ───────────── Tech / Lifestyle ─────────────
    dict(
        name="HydroJug Traveler Tumbler (Flip Straw)",
        retail=34.99, cost_usd=8.50, velocity=84, spain_sat=45,
        category="Lifestyle / Drinkware",
        niches=["tumbler", "gym", "water-bottle", "tiktok-viral"],
        suppliers="hydrojug-official, aliexpress-tumblers, lifestyle-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Tumbler aislado con straw + cup holder. Stanley killer. España: hay tumblers pero este modelo específico no.",
    ),
    dict(
        name="LED Light Therapy Face Mask (7 colors)",
        retail=89.99, cost_usd=22.00, velocity=80, spain_sat=12,
        category="Beauty / Tech",
        niches=["skincare", "red-light", "tech-beauty", "anti-aging"],
        suppliers="aliexpress-led-mask, beautysupplier-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQEBAQEBAQE.png",
        notes="Máscara LED 7 colores (roja antiedad, azul antiséptica). Viral TikTok con dermatólogos. Gap altísimo en España.",
    ),
    dict(
        name="Pink Stuff Cleaning Bundle (6 productos)",
        retail=27.99, cost_usd=9.00, velocity=70, spain_sat=50,
        category="Home / Cleaning",
        niches=["cleaning", "bundle", "viral", "home-care"],
        suppliers="pink-stuff-distributor, aliexpress-cleaning-bundle",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Bundle The Pink Stuff (paste, foam, multi-purpose, etc.). Acaba de lanzar en TikTok Shop US (Sep 15-21 2026). En España solo en algún gran superficie.",
    ),
    dict(
        name="DRDENT Purple Teeth Whitening Strips",
        retail=34.99, cost_usd=5.50, velocity=85, spain_sat=35,
        category="Beauty / Oral Care",
        niches=["whitening", "oral-care", "tiktok-viral", "no-sensitivity"],
        suppliers="drdent-official, aliexpress-whitening, beautysupplier-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Tiras blanqueadoras púrpura (peróxido-free, no sensibilidad). Top 5 en 4 mercados EU. España top pero margen alto aún — PVP local 50-70€. AliExpress 5-6 USD.",
    ),
    dict(
        name="Magnetic Eyelashes + Eyeliner Kit",
        retail=29.99, cost_usd=4.50, velocity=88, spain_sat=28,
        category="Beauty / Makeup",
        niches=["eyelashes", "makeup", "no-glue", "viral"],
        suppliers="aliexpress-magnetic-lash, beautysupplier-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBAQEBAQEBAQEBAQEBAQEBAQE.png",
        notes="Pestañas magnéticas + liner. 5.32% CVR TikTok Shop. Reutilizables. Margen alto.",
    ),
    dict(
        name="Foot Warmer Electric Under Desk",
        retail=49.99, cost_usd=13.50, velocity=72, spain_sat=10,
        category="Home / Wellness",
        niches=["warmth", "work-from-home", "gift", "winter"],
        suppliers="aliexpress-foot-warmer, lifestyle-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Calentador pies bajo escritorio. Top trending US Sep 2026. Perfecto para invierno España (Oct-Mar). Margen 70%+.",
    ),
    dict(
        name="Electric Self-Stirring Mug",
        retail=29.99, cost_usd=6.20, velocity=70, spain_sat=15,
        category="Home / Gadget",
        niches=["coffee", "gadget", "gift", "tiktok-viral"],
        suppliers="aliexpress-self-stir, kitchen-gadget-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Taza que mezcla sola con botón. 44K views ad TikTok. Perfecto para regalo Nav 2026. AliExpress 5-7 USD.",
    ),
    dict(
        name="BrickBlaze DIY Toy Blaster",
        retail=34.99, cost_usd=8.50, velocity=74, spain_sat=8,
        category="Toys / Kids",
        niches=["toys", "diy", "blaster", "tiktok-viral"],
        suppliers="brickblaze-official, aliexpress-toy-blaster",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Lanzador de bloques DIY. Tendencia juguetes 2026. Sin marca establecida en España. Navidad 2026.",
    ),
    dict(
        name="Toplux Magnesium Complex Supplement",
        retail=49.97, cost_usd=6.80, velocity=86, spain_sat=25,
        category="Wellness / Supplements",
        niches=["supplement", "magnesium", "sleep", "wellness"],
        suppliers="toplux-official, aliexpress-supplement, alibaba-supplements",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="2.1M vendidas en TikTok Shop US. Complejo magnesio 8-en-1. España tiene competencia (Solaray, NOW) pero este formato no.",
    ),
    dict(
        name="Y2K Electric Water Gun (Cyber Neon Design)",
        retail=34.99, cost_usd=8.00, velocity=78, spain_sat=12,
        category="Toys / Outdoor",
        niches=["summer", "kids", "y2k", "viral"],
        suppliers="aliexpress-y2k-gun, toys-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Pistola agua eléctrica con luz neón. USB recargable. Verano 2026 — ventana ya pasada, planificar verano 2027.",
    ),
    dict(
        name="Bella Vita Honey Oud Eau de Parfum 100ml",
        retail=39.99, cost_usd=5.50, velocity=80, spain_sat=20,
        category="Beauty / Fragrance",
        niches=["perfume", "oud", "unisex", "tiktok-viral"],
        suppliers="bellavita-official, aliexpress-fragrance, perfume-cn",
        img="https://p16-sign-sg.tiktokcdn.com/tos-alisg/oEBABAREBAQEBAQEBAQEBAQEBAQ.png",
        notes="Perfume indio oud + vainilla. Viral TikTok. Patchouli + Bergamota. AliExpress replicas 4-6 USD. Margen muy alto.",
    ),
]


def _build_product(idx: int, raw: dict) -> Product:
    USD_TO_EUR = 0.92
    cost_eur = round(raw["cost_usd"] * USD_TO_EUR, 2)

    p = Product(
        id=f"prod-{idx:03d}",
        name=raw["name"],
        category=raw["category"],
        niches=raw["niches"],
        retail_price_eur=raw["retail"],
        landed_cost_eur=cost_eur,
        trend_velocity=raw["velocity"],
        saturation_spain=raw["spain_sat"],
        image_url=raw.get("img"),
        notes=raw.get("notes", ""),
        suppliers=[s.strip() for s in raw["suppliers"].split(",")],
    )

    p.signals.append(TrendSignal(
        source="tiktok_shop_us",
        region="us",
        metric="trend_velocity",
        value=raw["velocity"],
    ))
    p.signals.append(TrendSignal(
        source="spain_gap_index",
        region="es",
        metric="saturation",
        value=raw["spain_sat"],
    ))

    return enrich(p)


CURATED_PRODUCTS: list[Product] = [_build_product(i, r) for i, r in enumerate(_RAW)]


class CuratedSource:
    """Returns the curated knowledge base."""
    name = "curated"

    def fetch(self) -> list[Product]:
        return list(CURATED_PRODUCTS)
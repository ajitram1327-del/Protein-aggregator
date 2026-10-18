"""
ProteIndex Engine: Autonomous Scraping & Data Pipeline Infrastructure
Integrates:
- Lane 1: Shopify D2C JSON Fast-Track (/products.json?limit=250) for sub-second SKU ingestion
- Lane 2: ResilientStealthFetcher (curl_cffi chrome124 TLS/HTTP2) with 4-Tier Extractor
- Strict MasterCatalogMatcher with formulation category locks and +-3% weight tolerances
- One-Time Nutrition Label Vision Locking (Gemini Flash Vision)
- PRD v3 Scientific Analytics (Equalizer DIAAS, IngredientAuditor, SellerMatrix, ReviewAuthenticity)
- In-place price_listings updates with database delta audit triggers
"""

import os
import sys
import json
import re
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.analytics.equalizer import EqualizerEngine
from src.analytics.ingredient_auditor import IngredientAuditor
from src.vision.review_authenticity import ReviewAuthenticityEngine
from src.vision.label_auditor import VisionLabelAuditor
from src.pipeline.seller_matrix import SellerMatrix
from src.pipeline.normalizer import VariantNormalizer, CanonicalProductNormalizer
from src.pipeline.extractor import MultiLevelExtractor
from src.pipeline.matcher import MasterCatalogMatcher, insert_quarantine_product
from src.scraper.fetcher import ResilientStealthFetcher

import random

# --- Logging & Environment Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_production.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ProteIndexEngine")

# Commercial proxy pool configuration & direct connection resilience
def get_proxy_pool():
    if os.environ.get("DISABLE_FREE_PROXIES", "").lower() in ("true", "1"):
        return []
    commercial_proxy = os.environ.get("ROTATING_PROXY_URL") or os.environ.get("PROXY_URL")
    if commercial_proxy:
        return [commercial_proxy]
    return []

PROXY_POOL = get_proxy_pool()
attempt = 0
proxy = random.choice(PROXY_POOL) if (PROXY_POOL and attempt == 0) else None

# Robust .env loading for CLI, background jobs, and API workers
possible_envs = [
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'),
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'scraper', '.env'),
    os.path.join(os.getcwd(), 'scraper', '.env'),
    os.path.join(os.getcwd(), '.env'),
    ".env",
    "../.env"
]
for p in possible_envs:
    if os.path.exists(p):
        load_dotenv(p)

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
supabase: Optional[Client] = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Vision OCR toggle (set False for high-speed pure catalog extraction)
ENABLE_VISION_OCR = False
gemini_key = os.environ.get("GEMINI_API_KEY", "")
label_auditor = VisionLabelAuditor(api_key=gemini_key) if (gemini_key and ENABLE_VISION_OCR) else None

# --- Dynamic Canonical Brand Loader & Aliases ---
CANONICAL_BRANDS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'canonical_brands.json')

def load_canonical_brands_dataset() -> List[Dict[str, Any]]:
    if os.path.exists(CANONICAL_BRANDS_FILE):
        try:
            with open(CANONICAL_BRANDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("brands", [])
        except Exception as e:
            logger.warning(f"Failed to read canonical_brands.json: {e}")
    return []

CANONICAL_BRANDS = load_canonical_brands_dataset()

# 1. Build D2C Shopify Storefront Registry
_d2c_seen = set()
D2C_SHOPIFY_REGISTRY: List[Dict[str, str]] = []

# Known direct Shopify storefronts
EXTRA_D2C = [
    {"brand": "Muscle Nectar", "domain": "musclenectar.com"},
    {"brand": "Proburst", "domain": "proburst.com"},
    {"brand": "TrueBasics", "domain": "truebasics.com"}
]

for b in CANONICAL_BRANDS:
    dom = b.get("d2c_domain")
    if dom and dom not in _d2c_seen:
        _d2c_seen.add(dom)
        D2C_SHOPIFY_REGISTRY.append({"brand": b["brand"], "domain": dom})

for extra in EXTRA_D2C:
    if extra["domain"] not in _d2c_seen:
        _d2c_seen.add(extra["domain"])
        D2C_SHOPIFY_REGISTRY.append(extra)

logger.info(f"Loaded {len(D2C_SHOPIFY_REGISTRY)} D2C Shopify storefronts into Lane 1.")

# 2. Build Canonical Brand Aliases for Detection & Catalog Expansion
BRAND_ALIASES: Dict[str, str] = {}
for b in CANONICAL_BRANDS:
    c_name = b["brand"]
    BRAND_ALIASES[c_name.lower()] = c_name
    cleaned = re.sub(r"\(.*?\)", "", c_name).strip().lower()
    if len(cleaned) >= 3:
        BRAND_ALIASES[cleaned] = c_name
    stripped = re.sub(r"\b(nutrition|foods|life|sports|india)\b", "", cleaned).strip()
    if len(stripped) >= 3:
        BRAND_ALIASES[stripped] = c_name
    for part in re.split(r"[/,]", c_name):
        p = re.sub(r"\(.*?\)", "", part).strip().lower()
        if len(p) >= 3:
            BRAND_ALIASES[p] = c_name
        p_strip = re.sub(r"\b(nutrition|foods|life|sports|india)\b", "", p).strip()
        if len(p_strip) >= 3:
            BRAND_ALIASES[p_strip] = c_name

# Add explicit manual aliases & shorthands
BRAND_ALIASES.update({
    "on": "Optimum Nutrition (ON)",
    "optimum nutrition": "Optimum Nutrition (ON)",
    "asitis": "AS-IT-IS Nutrition",
    "as-it-is": "AS-IT-IS Nutrition",
    "as it is": "AS-IT-IS Nutrition",
    "mb": "MuscleBlaze",
    "rule 1": "Rule 1",
    "rule1": "Rule 1",
    "animal": "Universal / Animal",
    "universal": "Universal / Animal",
    "gnc": "GNC India",
    "myprotein": "Myprotein India",
    "naturaltein": "Naturaltein / Beast Life",
    "beast life": "Naturaltein / Beast Life",
    "muscle nectar": "Muscle Nectar",
    "proburst": "Proburst",
    "dymatize": "Dymatize",
    "muscletech": "MuscleTech",
    "isopure": "Isopure",
    "labrada": "Labrada",
    "cellucor": "Cellucor",
    "bsn": "BSN"
})

SORTED_BRAND_PATTERNS = sorted(BRAND_ALIASES.keys(), key=len, reverse=True)

def detect_canonical_brand(title: str) -> Optional[str]:
    """Resolves an uncurated scraped product title to its canonical brand name."""
    if not title:
        return None
    t_low = title.lower()
    for pat in SORTED_BRAND_PATTERNS:
        if re.search(rf"\b{re.escape(pat)}\b", t_low):
            return BRAND_ALIASES[pat]
    return None

# 3. Dynamic Marketplace Query Generation (Lane 2)
def build_marketplace_targets() -> List[Dict[str, Any]]:
    # Core multi-category search terms
    base_categories = [
        "whey protein", "whey isolate", "creatine monohydrate", "creapure creatine",
        "mass gainer", "weight gainer", "pre workout powder", "plant protein"
    ]

    hk_queries = list(base_categories)
    nb_queries = ["whey protein", "whey isolate", "creatine", "mass gainer", "pre workout"]
    amazon_queries = list(base_categories)
    flipkart_queries = list(base_categories)
    nykaa_queries = ["whey protein", "plant protein", "creatine", "pre workout", "mass gainer"]
    tata_queries = ["whey protein powder", "creatine monohydrate", "mass gainer", "pre workout"]
    hyuga_queries = ["whey protein", "isolate", "creatine", "pre workout", "mass gainer"]

    # Extract all flagship products across the 81 canonical brands
    for b in CANONICAL_BRANDS:
        c_brand = re.sub(r"\(.*?\)", "", b["brand"]).strip()
        channels = [c.lower() for c in b.get("channels", [])]
        is_global = b.get("tier") == "Global / Import"

        for fp in b.get("flagship_products", []):
            fp_clean = fp.strip()
            plow = fp_clean.lower()
            if any(cat in plow for cat in ["creatine", "creapure", "mass", "gainer", "pre-workout", "pre workout", "pump", "whey", "protein", "isolate", "plant"]):
                query = f"{c_brand} {fp_clean}"

                # Route to appropriate channels
                if any("healthkart" in c for c in channels) or is_global:
                    if query not in hk_queries:
                        hk_queries.append(query)
                if any("nutrabay" in c for c in channels) or is_global:
                    if query not in nb_queries:
                        nb_queries.append(query)
                if any("amazon" in c for c in channels) or is_global:
                    if query not in amazon_queries:
                        amazon_queries.append(query)
                if any("flipkart" in c for c in channels):
                    if query not in flipkart_queries:
                        flipkart_queries.append(query)
                if any("1mg" in c for c in channels):
                    if query not in tata_queries:
                        tata_queries.append(query)

    return [
        {
            "platform": "HealthKart",
            "url_template": "https://www.healthkart.com/search?query={query}",
            "card_selector": ".variant-inner-content, .product-card",
            "title_selector": "a.block, h3",
            "price_selector": ".variant-price, .price",
            "queries": hk_queries
        },
        {
            "platform": "Nutrabay",
            "url_template": "https://nutrabay.com/search?type=product&q={query}",
            "card_selector": ".product-card, .grid__item, .product-item",
            "title_selector": ".product-card__title, .card__heading, h2, h3, a.full-unstyled-link",
            "price_selector": ".price-item--sale, .price-item--regular, .price",
            "queries": nb_queries
        },
        {
            "platform": "Flipkart",
            "url_template": "https://www.flipkart.com/search?q={query}",
            "card_selector": "div._1AtVbE, div.slAVV4, div.c3e8SH",
            "title_selector": "a.IRpwTa, a.s1Q9rs, a.WKTcLC",
            "price_selector": "div._30jeq3, div.Nx9bqj",
            "queries": flipkart_queries
        },
        {
            "platform": "Amazon",
            "url_template": "https://www.amazon.in/s?k={query}",
            "card_selector": "div[data-component-type='s-search-result']",
            "title_selector": "h2 span",
            "price_selector": "span.a-price-whole",
            "queries": amazon_queries
        },
        {
            "platform": "Tata 1mg",
            "url_template": "https://www.1mg.com/search/all?name={query}",
            "card_selector": ".product-card, .style__product-box___vrGyH",
            "title_selector": ".style__pro-title___3zxNC, h2",
            "price_selector": ".style__price-tag___KzOkY, .price",
            "queries": tata_queries
        },
        {
            "platform": "HyugaLife",
            "url_template": "https://hyugalife.com/search?q={query}",
            "card_selector": ".product-card, .item, .product-block",
            "title_selector": ".product-title, h2, h3",
            "price_selector": ".product-price, .price",
            "queries": hyuga_queries
        },
        {
            "platform": "Nykaa",
            "url_template": "https://www.nykaa.com/search/result/?q={query}",
            "card_selector": ".productWrapper, .css-1rd7vky",
            "title_selector": ".css-xrzmfa, .title",
            "price_selector": ".css-111z9ua, .price",
            "queries": nykaa_queries
        },
        {
            "platform": "MyProtein",
            "url_template": "https://www.myprotein.co.in/elysium.search?search={query}",
            "card_selector": ".productListProducts_product, .athenaProductBlock",
            "title_selector": ".athenaProductBlock_title, h3",
            "price_selector": ".athenaProductBlock_priceValue, .price",
            "queries": ["Impact Whey Protein", "Impact Whey Isolate", "Creatine Monohydrate", "The Pre-Workout", "Weight Gainer Blend"]
        }
    ]

MARKETPLACE_TARGETS = build_marketplace_targets()

TARGET_FILTER = re.compile(
    r"\b(?:whey|isolate|casein|protein\s*powder|plant\s*protein|vegan\s*protein|pea\s*protein|soy\s*protein|yeast\s*protein|"
    r"creatine|creapure|mass\s*gainer|weight\s*gainer|pre\s*workout|preworkout|pump|"
    r"wafers?|protein\s*bars?|energy\s*bars?|protein\s*cookies?|protein\s*brownies?|protein\s*bites?|protein\s*chips?|protein\s*granola)\b",
    re.I
)
JUNK_FILTER = re.compile(
    r"\b(tablets?|capsules?|gummies|drops|syrup|chews?|softgels?|"
    r"e-?cook\s*book|cookbook|e-?book|recipe|guide|book\b|"
    r"shaker|sipper|bottle|t-?shirt|vest|bag|cap|combo|bundle|apparel|"
    r"oats?|muesli|peanut\s*butter|atta|flour|pasta|hydration\s*drink)\b|"
    r"\b(?:plant[- ]based\s+)?(?:true\s+)?vitamin\s+[a-z0-9]+\b|\bmultivitamin\b|\bshilajit\b|\bashwagandha\b|\bspirulina\b",
    re.I
)

def find_nutrition_label_url(images: List[Dict[str, Any]]) -> str:
    """
    Identifies the candidate image most likely to contain the nutrition factsheet.
    Prioritizes images with nutrition/facts/ingredient/supplement in URL or alt text,
    falling back to subsequent back-of-pack images rather than the front-tub hero render.
    """
    if not images:
        return ""
    keywords = ("nutrition", "fact", "label", "ingredient", "supplement", "table", "panel", "back", "info")
    for img in images:
        src = img.get("src", "").lower()
        alt = (img.get("alt") or "").lower()
        if any(k in src or k in alt for k in keywords):
            return img.get("src", "")
    if len(images) > 1:
        return images[-1].get("src", "")
    return images[0].get("src", "")

class ProteIndexOrchestrator:
    def __init__(self):
        self.fetcher = ResilientStealthFetcher()

    async def upsert_variant_to_db(
        self,
        brand: str,
        product_name: str,
        flavor: str,
        weight_g: int,
        price_inr: float,
        product_url: str,
        image_url: str,
        platform_name: str,
        seller_name: str = "",
        raw_description: str = "",
        extraction_method: str = "title",
        label_image_url: str = ""
    ) -> Optional[str]:
        if not supabase or price_inr <= 0:
            return None

        try:
            # PRD Trust Modules
            ingredient_audit = IngredientAuditor.audit(raw_description)
            base_trust_score = 100 - ingredient_audit.get("trust_deduction", 0)
            review_audit = ReviewAuthenticityEngine.audit_reviews(product_name)
            is_authorized = SellerMatrix.verify_seller(seller_name, brand)

            # 1. Master Product Check / Insert using Canonical Normalizer
            norm_info = CanonicalProductNormalizer.normalize_product(product_name, brand)
            canon_brand = norm_info.canonical_brand
            clean_base = norm_info.canonical_line
            silo = norm_info.category_silo
            psource = norm_info.formulation

            prod_res = supabase.table("products").select("id").eq("brand", canon_brand).eq("base_name", clean_base).execute()
            
            if prod_res.data and len(prod_res.data) > 0:
                product_id = prod_res.data[0]["id"]
            else:
                p_insert = supabase.table("products").upsert({
                    "brand": canon_brand,
                    "base_name": clean_base,
                    "category_silo": silo,
                    "protein_source": psource,
                    "image_url": image_url,
                    "is_fairy_dusted": ingredient_audit.get("is_fairy_dusted", False),
                    "fairy_dusting_flags": ingredient_audit.get("flags", []),
                    "trust_score": base_trust_score
                }, on_conflict="brand,base_name").execute()
                if not p_insert.data:
                    return None
                product_id = p_insert.data[0]["id"]

            # 2. Mint Deterministic Variant Hash
            norm = VariantNormalizer.execute(product_id=product_id, raw_title=f"{canon_brand} {clean_base} {flavor} {weight_g}g")
            v_hash = norm.variant_hash
            sku_id = f"{brand.lower().replace(' ', '')[:8]}-{flavor[:6]}-{weight_g}g-{v_hash[:6]}"

            # Strict category-aligned deterministic baseline nutrition values
            silo_lower = str(silo or "").lower()
            if silo_lower == "creatine":
                serving_size_g = 3.0
                label_protein_g = 0.0  # Creatine has 0g protein, 3g pure creatine
                total_servings = max(1, int(round(float(weight_g) / serving_size_g))) if weight_g > 0 else 100
            elif silo_lower in ("mass_gainer", "mass_gainers", "gainer"):
                serving_size_g = 100.0
                label_protein_g = 20.0
                total_servings = max(1, int(round(float(weight_g) / serving_size_g))) if weight_g > 0 else 10
            else:
                serving_size_g = 30.0
                label_protein_g = min(24.0, serving_size_g)  # Deterministic 80.0% benchmark purity
                total_servings = max(1, int(round(float(weight_g) / serving_size_g))) if weight_g > 0 else 30

            # --- GUARDRAIL: MULTI-VARIANT PRICE MISMATCH CHECK ---
            current_price_per_g = round(price_inr / max(1.0, float(weight_g)), 2)
            is_price_swapped = False
            
            if silo_lower == "protein" and current_price_per_g < 0.70:
                is_price_swapped = True
            elif silo_lower == "creatine" and current_price_per_g < 0.50:
                is_price_swapped = True

            if is_price_swapped:
                logger.error(f"[QUARANTINE TRIGGERED] Multi-variant price trap caught: ₹{current_price_per_g:.2f}/g for {weight_g}g")
                try:
                    supabase.table("staging_quarantine").insert({
                        "platform": platform_name,
                        "brand_hint": brand,
                        "raw_title": product_name,
                        "raw_price": round(float(price_inr), 2),
                        "raw_url": product_url,
                        "detected_weight_g": int(weight_g),
                        "failure_category": "SCRAPER_PARSE_ERROR",
                        "details": {
                            "quarantine_reason": f"Mismatched Multi-Variant Price Trap: Computed ₹{current_price_per_g:.2f}/g",
                            "price_per_g": current_price_per_g,
                            "category": silo
                        }
                    }).execute()
                except Exception as q_err:
                    logger.warning(f"Failed to record quarantine entry: {q_err}")
                return None

            try:
                analytics_metrics = EqualizerEngine.calculate_metrics(
                    category=psource,
                    price_inr=price_inr,
                    label_protein_g=label_protein_g,
                    serving_size_g=serving_size_g,
                    total_servings=total_servings
                )
            except ValueError as e:
                logger.error(f"[QUARANTINE TRIGGERED] Data integrity violation: {e}")
                supabase.table("staging_quarantine").insert({
                    "platform": platform_name,
                    "brand_hint": brand,
                    "raw_title": product_name,
                    "raw_price": round(float(price_inr), 2),
                    "raw_url": product_url,
                    "detected_weight_g": int(weight_g),
                    "failure_category": "SCRAPER_PARSE_ERROR",
                    "details": {
                        "quarantine_reason": str(e),
                        "serving_size_g": serving_size_g,
                        "label_protein_g": label_protein_g,
                        "total_servings": total_servings
                    }
                }).execute()
                return None

            v_res = supabase.table("variants").select("id, variant_hash").eq("variant_hash", v_hash).execute()
            
            if v_res.data and len(v_res.data) > 0:
                variant_id = v_res.data[0]["id"]
                # In-place update lowest price with clean rounding
                supabase.table("variants").update({
                    "lowest_price_inr": round(float(price_inr), 2)
                }).eq("id", variant_id).execute()
            else:
                # Check if this is a newly discovered variant requiring one-time vision audit
                label_ocr_data = None
                target_audit_img = label_image_url if label_image_url else image_url
                if label_auditor and target_audit_img and target_audit_img.startswith("http"):
                    try:
                        img_bytes = await self.fetcher.fetch_bytes(target_audit_img)
                        if img_bytes:
                            label_ocr_data = label_auditor.extract_label_data(img_bytes)
                    except Exception as e:
                        logger.warning(f"Vision audit attempt error: {e}")

                if label_ocr_data:
                    serving_size_g = round(float(label_ocr_data.serving_size_g), 2)
                    label_protein_g = round(float(label_ocr_data.protein_per_serving_g), 2)
                    total_servings = int(label_ocr_data.total_servings)
                    try:
                        analytics_metrics = EqualizerEngine.calculate_metrics(
                            category=psource,
                            price_inr=price_inr,
                            label_protein_g=label_protein_g,
                            serving_size_g=serving_size_g,
                            total_servings=total_servings
                        )
                    except ValueError as e:
                        logger.error(f"[QUARANTINE TRIGGERED] OCR integrity violation: {e}")
                        supabase.table("staging_quarantine").insert({
                            "platform": platform_name,
                            "brand_hint": brand,
                            "raw_title": product_name,
                            "raw_price": round(float(price_inr), 2),
                            "raw_url": product_url,
                            "detected_weight_g": int(weight_g),
                            "failure_category": "SCRAPER_PARSE_ERROR",
                            "details": {
                                "quarantine_reason": f"OCR extraction error: {e}",
                                "serving_size_g": serving_size_g,
                                "label_protein_g": label_protein_g,
                                "total_servings": total_servings,
                                "ocr_data": label_ocr_data.model_dump() if label_ocr_data else None
                            }
                        }).execute()
                        return None

                raw_json = json.dumps({
                    "description": raw_description[:500],
                    "analytics": analytics_metrics,
                    "variant_hash": v_hash,
                    "nutrition_audited_at": "now()",
                    "weight_extraction_method": extraction_method,
                    "ocr_data": label_ocr_data.model_dump() if label_ocr_data else None
                })

                new_var = supabase.table("variants").insert({
                    "product_id": product_id,
                    "sku_id": sku_id,
                    "variant_hash": v_hash,
                    "flavor": flavor,
                    "weight_grams": float(weight_g),
                    "lowest_price_inr": round(float(price_inr), 2),
                    "servings_count": total_servings,
                    "best_value_metric": round(float(analytics_metrics.get("effective_cost_per_bioavailable_g_inr", 1.8)), 2),
                    "raw_json_data": raw_json,
                    "authenticity_score": round(float(review_audit.get("authenticity_score", 95.0)), 1),
                    "has_bot_reviews": review_audit.get("has_bot_reviews", False),
                    "label_serving_size_g": round(float(serving_size_g), 1),
                    "label_protein_per_serving_g": round(float(label_protein_g), 1),
                    "label_total_servings": total_servings,
                    "calculated_purity_pct": round(float(analytics_metrics.get("scoop_purity_pct", 80.0)), 1),
                    "ocr_verified": bool(label_ocr_data is not None),
                    "ocr_image_url": image_url if label_ocr_data else None
                }).execute()

                if not new_var.data:
                    return None
                variant_id = new_var.data[0]["id"]

            # 3. Write / Update Hot Price Listing explicitly bound to variant_id (child SKU)
            for attempt in range(3):
                try:
                    supabase.table("price_listings").upsert({
                        "variant_id": variant_id,
                        "product_id": product_id,
                        "source": platform_name,
                        "platform_name": platform_name.lower(),
                        "source_url": product_url,
                        "listing_url": product_url,
                        "price_inr": round(float(price_inr), 2),
                        "current_price_inr": round(float(price_inr), 2),
                        "in_stock": True,
                        "is_in_stock": True,
                        "seller_name": seller_name or brand,
                        "is_authorized_seller": is_authorized,
                        "scraped_at": "now()"
                    }, on_conflict="variant_id,source").execute()
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"Failed to upsert price listing after 3 attempts: {e}")
                    else:
                        await asyncio.sleep(1)

            return variant_id

        except Exception as e:
            logger.warning(f"Error in upsert_variant_to_db for {brand} - {product_name}: {e}")
            return None

    # =========================================================================
    # LANE 1: SHOPIFY D2C FAST-TRACK (JSON Ingestion, 300ms per store)
    # =========================================================================
    async def run_shopify_fasttrack(self) -> int:
        logger.info("\n" + "=" * 60)
        logger.info("[LANE 1] INITIATING SHOPIFY D2C JSON FAST-TRACK")
        logger.info("=" * 60)
        total_ingested = 0

        for target in D2C_SHOPIFY_REGISTRY:
            brand = target["brand"]
            domain = target["domain"]
            brand_count = 0
            page = 1
            max_pages = 5

            while page <= max_pages:
                endpoint = f"https://{domain}/products.json?limit=250&page={page}"
                logger.info(f"[{brand}] Querying endpoint (page {page}): {endpoint}")

                try:
                    status, body, _, _ = await self.fetcher.fetch(endpoint, timeout=12)
                except Exception as net_err:
                    logger.warning(f"[{brand}] Network fetch exception for {domain}: {net_err}. Skipping.")
                    break

                if status != 200 or not body:
                    if page == 1:
                        logger.warning(f"[{brand}] Endpoint returned HTTP {status}. Skipping.")
                    break

                try:
                    catalog = json.loads(body)
                    products = catalog.get("products", [])
                except Exception as e:
                    logger.warning(f"[{brand}] JSON parse failed: {e}. Skipping.")
                    break

                if not products:
                    break

                for p in products:
                    try:
                        title = p.get("title", "")
                        if not TARGET_FILTER.search(title) or JUNK_FILTER.search(title):
                            continue

                        is_bundle, _ = CanonicalProductNormalizer.check_is_bundle(title)
                        if is_bundle:
                            continue

                        images = p.get("images", [])
                        image_url = images[0].get("src") if images else ""
                        label_image_url = find_nutrition_label_url(images)
                        handle = p.get("handle", "")
                        product_url = f"https://{domain}/products/{handle}" if handle else f"https://{domain}"

                        for v in p.get("variants", []):
                            try:
                                var_title = v.get("title", "")
                                price = float(v.get("price", 0))
                                sku_label = f"{title} [{var_title}]"

                                if price <= 0:
                                    continue

                                var_title_lower = var_title.lower()
                                title_lower = title.lower()

                                # Explicitly detect sachet, sample, trial packet keywords
                                is_sample_or_sachet = any(
                                    tok in var_title_lower for tok in ["sachet", "sample", "trial", "single serve", "packet"]
                                ) or any(
                                    tok in title_lower for tok in ["sample pack", "trial pack", "samples"]
                                )

                                # If it's a sample/sachet pack without an explicit large tub weight, skip to prevent
                                # contaminating powder tub variants or price per 100g metrics
                                if is_sample_or_sachet and not any(w in var_title_lower for w in ["kg", "1000g", "2000g", "500g"]):
                                    continue

                                # 1. First priority: Check variant title directly (e.g. "Mango / 2Kg", "1kg / Chocolate")
                                weight_g = VariantNormalizer.parse_weight(var_title, default=None)

                                # 2. Second priority: Check variant grams field if valid tub weight (>= 100g)
                                if not weight_g and not is_sample_or_sachet:
                                    v_grams = v.get("grams")
                                    if v_grams and isinstance(v_grams, (int, float)) and v_grams >= 100:
                                        weight_g = int(round(v_grams))

                                # 3. Third priority: Parse from parent product title (nutrient claims stripped)
                                # CRITICAL: NEVER default to 1000g if title does not contain an explicit weight!
                                if not weight_g and not is_sample_or_sachet:
                                    weight_g = VariantNormalizer.parse_weight(title, default=None)

                                # For flavor: check var_title first, then combined title
                                flavor = VariantNormalizer.parse_flavor(var_title)
                                if flavor == "unflavored":
                                    flavor = VariantNormalizer.parse_flavor(f"{title} {var_title}")

                                if not weight_g or weight_g <= 0:
                                    continue

                                v_id = await self.upsert_variant_to_db(
                                    brand=brand,
                                    product_name=title,
                                    flavor=flavor,
                                    weight_g=weight_g,
                                    price_inr=price,
                                    product_url=product_url,
                                    image_url=image_url,
                                    platform_name="D2C",
                                    seller_name=f"{brand} Official",
                                    raw_description=p.get("body_html", "") or "",
                                    extraction_method="shopify_api",
                                    label_image_url=label_image_url
                                )
                                if v_id:
                                    brand_count += 1
                                    total_ingested += 1
                            except Exception as item_err:
                                logger.warning(f"Error processing SKU '{title}': {item_err}. Moving on.")
                                continue

                    except Exception as p_err:
                        logger.warning(f"Error processing product in {brand}: {p_err}. Moving on.")
                        continue

                if len(products) < 250:
                    break
                page += 1

            logger.info(f"  > [{brand}] Successfully ingested {brand_count} clean SKUs.")

        return total_ingested

    # =========================================================================
    # LANE 2: MULTI-LEVEL MARKETPLACE RE-POLL & CATALOG BUILDING
    # =========================================================================
    async def run_marketplace_pulse(self) -> Tuple[int, int]:
        logger.info("\n" + "=" * 60)
        logger.info("[LANE 2] INITIATING MARKETPLACE RE-POLL & CATALOG EXPANSION")
        logger.info("=" * 60)
        total_matched = 0
        total_catalog_built = 0

        # Reload master catalog for formulation-gated matching
        MasterCatalogMatcher.initialize_indexes()

        from bs4 import BeautifulSoup

        for target in MARKETPLACE_TARGETS:
            platform = target["platform"]
            logger.info(f"\n--- Platform: {platform} ({len(target['queries'])} queries scheduled) ---")

            for query in target["queries"]:
                try:
                    url = target["url_template"].format(query=query.replace(" ", "+"))
                    logger.info(f"[{platform}] Probing: {url}")

                    status, body, _, _ = await self.fetcher.fetch(url, timeout=15)
                    if status != 200 or not body:
                        logger.warning(f"[{platform}] HTTP {status} on '{query}'. Skipping query.")
                        continue

                    soup = BeautifulSoup(body, "html.parser")
                    cards = soup.select(target["card_selector"])
                    logger.info(f"[{platform}] Found {len(cards)} cards for '{query}'.")

                    for card in cards:
                        try:
                            title_el = card.select_one(target["title_selector"])
                            price_el = card.select_one(target["price_selector"])

                            if not title_el or not price_el:
                                continue

                            raw_title = title_el.get_text(strip=True)
                            raw_price_str = price_el.get_text(strip=True)
                            digits = re.sub(r"[^\d.]", "", raw_price_str)
                            price = float(digits) if digits else 0.0

                            if not raw_title or price <= 0:
                                continue
                            if not TARGET_FILTER.search(raw_title) or JUNK_FILTER.search(raw_title):
                                continue

                            # Link extraction
                            link_el = card.find("a", href=True)
                            link = link_el["href"] if link_el else url
                            if link and not link.startswith("http"):
                                from urllib.parse import urljoin
                                link = urljoin(url, link)

                            # Image extraction
                            img_el = card.find("img")
                            img = ""
                            if img_el:
                                img = img_el.get("src") or img_el.get("data-src") or ""

                            # 4-Tier Extractor to resolve specifications
                            weight_g, flavor, method = MultiLevelExtractor.resolve_specifications(raw_title, str(card))

                            if not weight_g:
                                insert_quarantine_product(
                                    platform=platform,
                                    raw_title=raw_title,
                                    raw_price=price,
                                    raw_url=link,
                                    failure_reason="UNRESOLVABLE_WEIGHT_ALL_TIERS_EXHAUSTED"
                                )
                                continue

                            # Formulation-Gated Matching against Master Catalog
                            matched = MasterCatalogMatcher.match_variant(raw_title, weight_g)
                            if matched:
                                variant_id = matched["id"]
                                logger.info(f"[{platform}] MATCHED: '{raw_title[:38]}...' -> ID {variant_id} | INR {price}")
                                
                                # Upsert hot price listing explicitly bound to variant_id (child SKU)
                                supabase.table("price_listings").upsert({
                                    "variant_id": variant_id,
                                    "product_id": matched.get("product_id"),
                                    "source": platform,
                                    "platform_name": platform.lower(),
                                    "source_url": link,
                                    "listing_url": link,
                                    "price_inr": round(float(price), 2),
                                    "current_price_inr": round(float(price), 2),
                                    "in_stock": True,
                                    "is_in_stock": True,
                                    "seller_name": platform,
                                    "is_authorized_seller": True,
                                    "scraped_at": "now()"
                                }, on_conflict="variant_id,source").execute()

                                # Update lowest price on variant if lower
                                try:
                                    v_curr = supabase.table("variants").select("lowest_price_inr").eq("id", variant_id).execute()
                                    if v_curr.data and (v_curr.data[0].get("lowest_price_inr") is None or price < v_curr.data[0]["lowest_price_inr"]):
                                        supabase.table("variants").update({"lowest_price_inr": round(float(price), 2)}).eq("id", variant_id).execute()
                                except Exception:
                                    pass

                                total_matched += 1
                            else:
                                detected_brand = detect_canonical_brand(raw_title)
                                insert_quarantine_product(
                                    platform=platform,
                                    raw_title=raw_title,
                                    raw_price=price,
                                    raw_url=link,
                                    detected_brand=detected_brand or "",
                                    detected_weight_g=weight_g or 0,
                                    failure_reason="UNMATCHED_MARKETPLACE_LISTING"
                                )
                                logger.info(f"[{platform}] UNMATCHED -> Staged for review: '{raw_title[:38]}...' [{weight_g}g]")

                        except Exception as card_err:
                            logger.debug(f"[{platform}] Card parsing skipped: {card_err}")
                            continue

                except Exception as query_err:
                    logger.warning(f"[{platform}] Query '{query}' error: {query_err}. Moving on to next query.")
                    continue

        return total_matched, total_catalog_built

    async def run_all(self):
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE PROTEINDEX SCRAPE CYCLE")
        logger.info("=" * 60)

        d2c_count = 0
        mkt_matched = 0
        mkt_catalog_built = 0

        try:
            d2c_count = await self.run_shopify_fasttrack()
        except Exception as e:
            logger.error(f"Error during Lane 1 Shopify fasttrack: {e}")

        try:
            mkt_matched, mkt_catalog_built = await self.run_marketplace_pulse()
        except Exception as e:
            logger.error(f"Error during Lane 2 marketplace pulse: {e}")

        logger.info("\n" + "=" * 60)
        logger.info(f"SCRAPE CYCLE FINISHED: Ingested {d2c_count} D2C SKUs | Built {mkt_catalog_built} New Catalog Variants | Matched {mkt_matched} Marketplace Listings")
        logger.info("=" * 60)
        await self.fetcher.close()

async def main():
    orchestrator = ProteIndexOrchestrator()
    await orchestrator.run_all()

if __name__ == "__main__":
    asyncio.run(main())

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
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.analytics.equalizer import EqualizerEngine
from src.analytics.ingredient_auditor import IngredientAuditor
from src.vision.review_authenticity import ReviewAuthenticityEngine
from src.vision.label_auditor import VisionLabelAuditor
from src.pipeline.seller_matrix import SellerMatrix
from src.pipeline.normalizer import VariantNormalizer
from src.pipeline.extractor import MultiLevelExtractor
from src.pipeline.matcher import MasterCatalogMatcher, insert_quarantine_product
from src.scraper.fetcher import ResilientStealthFetcher

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

gemini_key = os.environ.get("GEMINI_API_KEY", "")
label_auditor = VisionLabelAuditor(api_key=gemini_key) if gemini_key else None

# 1. Registered D2C Shopify supplement storefronts (Lane 1)
D2C_SHOPIFY_REGISTRY = [
    {"brand": "AS-IT-IS Nutrition", "domain": "asitisnutrition.com"},
    {"brand": "Nakpro", "domain": "nakpro.com"},
    {"brand": "Fast&Up", "domain": "fastandup.in"},
    {"brand": "The Whole Truth", "domain": "thewholetruthfoods.com"},
    {"brand": "Scitron", "domain": "scitron.com"},
    {"brand": "Avvatar", "domain": "avvatarindia.com"},
]

# 2. Key marketplace platforms (Lane 2)
MARKETPLACE_TARGETS = [
    {
        "platform": "HealthKart",
        "url_template": "https://www.healthkart.com/search?query={query}",
        "card_selector": ".variant-inner-content, .product-card",
        "title_selector": "a.block, h3",
        "price_selector": ".variant-price, .price",
        "queries": ["Optimum Nutrition whey", "MuscleBlaze whey", "Dymatize ISO 100", "Avvatar whey", "Nakpro whey"]
    },
    {
        "platform": "Nutrabay",
        "url_template": "https://nutrabay.com/search?type=product&q={query}",
        "card_selector": ".product-card, .grid__item, .product-item",
        "title_selector": ".product-card__title, .card__heading, h2, h3, a.full-unstyled-link",
        "price_selector": ".price-item--sale, .price-item--regular, .price",
        "queries": ["Optimum Nutrition", "MuscleTech", "Dymatize", "MuscleBlaze", "AS-IT-IS"]
    }
]

TARGET_FILTER = re.compile(r"protein|whey|isolate|casein|plant|pea|creatine|mass.?gainer|weight.?gainer", re.I)
JUNK_FILTER = re.compile(r"shaker|bottle|t-shirt|tshirt|bag|cap|combo|bundle|multivitamin|bar\b|cookie|snack|chips|peanut\s*butter|gummies|fish oil|omega|collagen|biotin", re.I)

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
        extraction_method: str = "title"
    ) -> bool:
        if not supabase or price_inr <= 0:
            return False

        # Category and DIAAS derivation
        combined_text = f"{product_name} {flavor} {raw_description}".lower()
        category = MasterCatalogMatcher.detect_category(combined_text)
        
        silo = "protein"
        if "mass" in combined_text or "gainer" in combined_text:
            silo = "mass_gainers"
        elif "creatine" in combined_text:
            silo = "creatine"

        psource = "Whey"
        if "plant" in combined_text or "pea" in combined_text or "vegan" in combined_text:
            psource = "Plant"
        elif "casein" in combined_text:
            psource = "Casein"

        # PRD Trust Modules
        ingredient_audit = IngredientAuditor.audit(raw_description)
        base_trust_score = 100 - ingredient_audit.get("trust_deduction", 0)
        review_audit = ReviewAuthenticityEngine.audit_reviews(product_name)
        is_authorized = SellerMatrix.verify_seller(seller_name, brand)

        # 1. Master Product Check / Insert
        clean_base = re.split(r"[,|-]", product_name)[0].strip()[:100]
        prod_res = supabase.table("products").select("id").eq("brand", brand).eq("base_name", clean_base).execute()
        
        if prod_res.data and len(prod_res.data) > 0:
            product_id = prod_res.data[0]["id"]
        else:
            p_insert = supabase.table("products").upsert({
                "brand": brand,
                "base_name": clean_base,
                "category_silo": silo,
                "protein_source": psource,
                "image_url": image_url,
                "is_fairy_dusted": ingredient_audit.get("is_fairy_dusted", False),
                "fairy_dusting_flags": ingredient_audit.get("flags", []),
                "trust_score": base_trust_score
            }, on_conflict="brand,base_name").execute()
            if not p_insert.data:
                return False
            product_id = p_insert.data[0]["id"]

        # 2. Mint Deterministic Variant Hash
        norm = VariantNormalizer.execute(product_id=product_id, raw_title=f"{brand} {clean_base} {flavor} {weight_g}g")
        v_hash = norm.variant_hash
        sku_id = f"{brand.lower().replace(' ', '')[:8]}-{flavor[:6]}-{weight_g}g-{v_hash[:6]}"

        # Standard baseline nutrition values
        serving_size_g = 33.0
        label_protein_g = min(24.0, serving_size_g)
        total_servings = max(1, int(weight_g / serving_size_g))

        analytics_metrics = EqualizerEngine.calculate_metrics(
            category=psource,
            price_inr=price_inr,
            label_protein_g=label_protein_g,
            serving_size_g=serving_size_g,
            total_servings=total_servings
        )

        v_res = supabase.table("variants").select("id, variant_hash").eq("variant_hash", v_hash).execute()
        
        if v_res.data and len(v_res.data) > 0:
            variant_id = v_res.data[0]["id"]
            # In-place update lowest price
            supabase.table("variants").update({
                "lowest_price_inr": price_inr
            }).eq("id", variant_id).execute()
        else:
            # Check if this is a newly discovered variant requiring one-time vision audit
            label_ocr_data = None
            if label_auditor and image_url and image_url.startswith("http"):
                try:
                    img_bytes = await self.fetcher.fetch_bytes(image_url)
                    if img_bytes:
                        logger.info(f"[Vision] Running one-time nutrition audit on {brand} {sku_id}...")
                        label_ocr_data = label_auditor.extract_label_data(img_bytes)
                except Exception as e:
                    logger.warning(f"Vision audit attempt error: {e}")

            if label_ocr_data:
                serving_size_g = label_ocr_data.serving_size_g
                label_protein_g = label_ocr_data.protein_per_serving_g
                total_servings = label_ocr_data.total_servings
                analytics_metrics = EqualizerEngine.calculate_metrics(
                    category=psource,
                    price_inr=price_inr,
                    label_protein_g=label_protein_g,
                    serving_size_g=serving_size_g,
                    total_servings=total_servings
                )

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
                "lowest_price_inr": price_inr,
                "servings_count": total_servings,
                "best_value_metric": analytics_metrics.get("effective_cost_per_bioavailable_g_inr", 1.8),
                "raw_json_data": raw_json,
                "authenticity_score": review_audit.get("authenticity_score", 95.0),
                "has_bot_reviews": review_audit.get("has_bot_reviews", False),
                "label_serving_size_g": serving_size_g,
                "label_protein_per_serving_g": label_protein_g,
                "label_total_servings": total_servings,
                "calculated_purity_pct": analytics_metrics.get("scoop_purity_pct", 72.0),
                "ocr_verified": bool(label_ocr_data is not None),
                "ocr_image_url": image_url if label_ocr_data else None
            }).execute()

            if not new_var.data:
                return False
            variant_id = new_var.data[0]["id"]

        # 3. Write / Update Hot Price Listing with connection retry resilience
        for attempt in range(3):
            try:
                supabase.table("price_listings").upsert({
                    "variant_id": variant_id,
                    "source": platform_name,
                    "platform_name": platform_name.lower(),
                    "source_url": product_url,
                    "listing_url": product_url,
                    "price_inr": price_inr,
                    "current_price_inr": price_inr,
                    "in_stock": True,
                    "is_in_stock": True,
                    "seller_name": seller_name or brand,
                    "is_authorized_seller": is_authorized,
                    "scraped_at": "now()"
                }, on_conflict="variant_id,source").execute()
                return True
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"Failed to upsert price listing after 3 attempts: {e}")
                    return False
                await asyncio.sleep(1)

        return True

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
            endpoint = f"https://{domain}/products.json?limit=250"
            logger.info(f"[{brand}] Querying endpoint: {endpoint}")

            status, body, _, _ = await self.fetcher.fetch(endpoint)
            if status != 200 or not body:
                logger.warning(f"[{brand}] Endpoint returned HTTP {status}. Skipping.")
                continue

            try:
                catalog = json.loads(body)
                products = catalog.get("products", [])
            except Exception as e:
                logger.warning(f"[{brand}] JSON parse failed: {e}")
                continue

            brand_count = 0
            for p in products:
                title = p.get("title", "")
                if not TARGET_FILTER.search(title) or JUNK_FILTER.search(title):
                    continue

                images = p.get("images", [])
                image_url = images[0].get("src") if images else ""
                handle = p.get("handle", "")
                product_url = f"https://{domain}/products/{handle}" if handle else f"https://{domain}"

                for v in p.get("variants", []):
                    var_title = v.get("title", "")
                    combined_title = f"{title} {var_title}"
                    price = float(v.get("price", 0))

                    weight_g = VariantNormalizer.parse_weight(combined_title)
                    flavor = VariantNormalizer.parse_flavor(combined_title)

                    if price <= 0 or not weight_g:
                        continue

                    try:
                        success = await self.upsert_variant_to_db(
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
                            extraction_method="shopify_api"
                        )
                        if success:
                            brand_count += 1
                            total_ingested += 1
                    except Exception as item_err:
                        logger.warning(f"Error processing SKU '{combined_title}': {item_err}")
                        await asyncio.sleep(0.5)

            logger.info(f"  > [{brand}] Successfully ingested {brand_count} clean SKUs.")

        return total_ingested

    # =========================================================================
    # LANE 2: MULTI-LEVEL MARKETPLACE RE-POLL WITH CONDITIONAL 304s
    # =========================================================================
    async def run_marketplace_pulse(self) -> int:
        logger.info("\n" + "=" * 60)
        logger.info("[LANE 2] INITIATING MARKETPLACE RE-POLL (HEALTHKART, NUTRABAY, ETC.)")
        logger.info("=" * 60)
        total_matched = 0

        # Reload master catalog for formulation-gated matching
        MasterCatalogMatcher.load_master_catalog()

        from bs4 import BeautifulSoup

        for target in MARKETPLACE_TARGETS:
            platform = target["platform"]
            for query in target["queries"]:
                url = target["url_template"].format(query=query.replace(" ", "+"))
                logger.info(f"[{platform}] Probing: {url}")

                status, body, _, _ = await self.fetcher.fetch(url)
                if status != 200 or not body:
                    logger.warning(f"[{platform}] HTTP {status} on {query}")
                    continue

                soup = BeautifulSoup(body, "html.parser")
                cards = soup.select(target["card_selector"])
                logger.info(f"[{platform}] Found {len(cards)} potential product cards for '{query}'.")

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
                            # Strict Quarantine
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
                            
                            # Upsert hot price listing
                            supabase.table("price_listings").upsert({
                                "variant_id": variant_id,
                                "source": platform,
                                "platform_name": platform.lower(),
                                "source_url": link,
                                "listing_url": link,
                                "price_inr": price,
                                "current_price_inr": price,
                                "in_stock": True,
                                "is_in_stock": True,
                                "seller_name": platform,
                                "is_authorized_seller": True,
                                "scraped_at": "now()"
                            }, on_conflict="variant_id,source").execute()
                            total_matched += 1
                        else:
                            # Staging quarantine
                            insert_quarantine_product(
                                platform=platform,
                                raw_title=raw_title,
                                raw_price=price,
                                raw_url=link,
                                detected_weight_g=weight_g,
                                failure_reason="NO_CATALOG_VARIANT_MATCH_ABOVE_THRESHOLD"
                            )

                    except Exception as e:
                        logger.warning(f"[{platform}] Card parsing error: {e}")

        return total_matched

    async def run_all(self):
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE PROTEINDEX SCRAPE CYCLE")
        logger.info("=" * 60)

        d2c_count = await self.run_shopify_fasttrack()
        mkt_count = await self.run_marketplace_pulse()

        logger.info("\n" + "=" * 60)
        logger.info(f"SCRAPE CYCLE FINISHED: Ingested {d2c_count} D2C SKUs | Matched {mkt_count} Marketplace Listings")
        logger.info("=" * 60)
        await self.fetcher.close()

async def main():
    orchestrator = ProteIndexOrchestrator()
    await orchestrator.run_all()

if __name__ == "__main__":
    asyncio.run(main())

"""
ProteIndex Silo Scraper: Creatine, Mass Gainer & Pre-Workout Engine
Scrapes targeted performance nutrition categories into separate, dedicated SQL tables:
- creatine_catalog (Unit metric: ₹/g pure Creatine)
- mass_gainer_catalog (Unit metric: ₹/1,000 kcal & Carb:Protein Ratio)
- pre_workout_catalog (Unit metric: ₹/standard scoop & Caffeine mg)
Maintains strict master catalog normalization and fault tolerance.
"""

import os
import sys
import json
import re
import asyncio
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.analytics.equalizer import EqualizerEngine
from src.pipeline.normalizer import VariantNormalizer
from src.pipeline.extractor import MultiLevelExtractor
from src.scraper.fetcher import ResilientStealthFetcher

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("silo_scraper.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SiloScraper")

# Load environment & Supabase
possible_envs = [
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'),
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'scraper', '.env'),
    os.path.join(os.getcwd(), 'scraper', '.env'),
    os.path.join(os.getcwd(), '.env'),
    ".env"
]
for p in possible_envs:
    if os.path.exists(p):
        load_dotenv(p)

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
supabase: Optional[Client] = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# SQLite dedicated database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'silo_catalog.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_sqlite_silo_tables():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS creatine_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        base_name TEXT NOT NULL,
        flavor TEXT NOT NULL,
        weight_grams REAL NOT NULL,
        servings_count INTEGER,
        serving_size_g REAL,
        creatine_per_serving_g REAL,
        price_inr REAL NOT NULL,
        cost_per_g_creatine_inr REAL,
        platform TEXT NOT NULL,
        listing_url TEXT,
        image_url TEXT,
        variant_hash TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mass_gainer_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        base_name TEXT NOT NULL,
        flavor TEXT NOT NULL,
        weight_grams REAL NOT NULL,
        servings_count INTEGER,
        serving_size_g REAL,
        calories_per_serving REAL,
        protein_per_serving_g REAL,
        carbs_per_serving_g REAL,
        carb_protein_ratio REAL,
        price_inr REAL NOT NULL,
        cost_per_1000_kcal_inr REAL,
        platform TEXT NOT NULL,
        listing_url TEXT,
        image_url TEXT,
        variant_hash TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pre_workout_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        base_name TEXT NOT NULL,
        flavor TEXT NOT NULL,
        weight_grams REAL NOT NULL,
        servings_count INTEGER,
        serving_size_g REAL,
        caffeine_per_serving_mg REAL,
        price_inr REAL NOT NULL,
        cost_per_scoop_inr REAL,
        platform TEXT NOT NULL,
        listing_url TEXT,
        image_url TEXT,
        variant_hash TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_creatine_cost ON creatine_catalog(cost_per_g_creatine_inr ASC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_creatine_brand ON creatine_catalog(brand);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mass_gainer_cost ON mass_gainer_catalog(cost_per_1000_kcal_inr ASC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mass_gainer_brand ON mass_gainer_catalog(brand);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pre_workout_cost ON pre_workout_catalog(cost_per_scoop_inr ASC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pre_workout_brand ON pre_workout_catalog(brand);")
    conn.commit()
    conn.close()

init_sqlite_silo_tables()

# Canonical Brands & D2C Stores
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

# Build Brand Aliases
BRAND_ALIASES: Dict[str, str] = {}
for b in CANONICAL_BRANDS:
    c_name = b["brand"]
    BRAND_ALIASES[c_name.lower()] = c_name
    cleaned = re.sub(r"\(.*?\)", "", c_name).strip().lower()
    if len(cleaned) >= 3: BRAND_ALIASES[cleaned] = c_name
    for part in re.split(r"[/,]", c_name):
        p = re.sub(r"\(.*?\)", "", part).strip().lower()
        if len(p) >= 3: BRAND_ALIASES[p] = c_name

BRAND_ALIASES.update({
    "on": "Optimum Nutrition (ON)",
    "optimum nutrition": "Optimum Nutrition (ON)",
    "mb": "MuscleBlaze",
    "asitis": "AS-IT-IS Nutrition",
    "as-it-is": "AS-IT-IS Nutrition",
    "c4": "Cellucor",
    "cellucor": "Cellucor",
    "muscletech": "MuscleTech",
    "dymatize": "Dymatize",
    "labrada": "Labrada",
    "rule 1": "Rule 1",
    "gnc": "GNC India"
})
SORTED_BRAND_PATTERNS = sorted(BRAND_ALIASES.keys(), key=len, reverse=True)

def detect_canonical_brand(title: str) -> Optional[str]:
    if not title: return None
    t_low = title.lower()
    for pat in SORTED_BRAND_PATTERNS:
        if re.search(rf"\b{re.escape(pat)}\b", t_low):
            return BRAND_ALIASES[pat]
    return None

# Target Filter & Junk Filter for these 3 categories
SILO_TARGET_FILTER = re.compile(
    r"creatine|creapure|micronized creatine|mass.?gainer|weight.?gainer|super.?gainer|serious.?mass|mega.?gainer|pre.?workout|preworkout|c4\b|vaporx5|psychotic|abp\b", 
    re.I
)
JUNK_FILTER = re.compile(
    r"shaker|bottle|t-shirt|tshirt|bag|cap|combo|bundle|multivitamin|bar\b|cookie|snack|chips|peanut\s*butter|gummies|fish oil|omega|collagen|biotin", 
    re.I
)

def classify_silo(title: str) -> Optional[str]:
    t_low = title.lower()
    if re.search(r"\b(?:pre.?workout|preworkout|c4|vaporx5|psychotic)\b", t_low):
        return "pre_workout"
    if re.search(r"\b(?:mass.?gainer|weight.?gainer|super.?gainer|serious.?mass|mega.?gainer)\b", t_low):
        return "mass_gainers"
    if re.search(r"\b(?:creatine|creapure|micronized creatine)\b", t_low):
        return "creatine"
    return None

# Marketplace Targets focused on Creatine, Mass Gainer, Pre-Workout
MARKETPLACE_SILO_TARGETS = [
    {
        "platform": "HealthKart",
        "url_template": "https://www.healthkart.com/search?query={query}",
        "card_selector": ".variant-inner-content, .product-card",
        "title_selector": "a.block, h3",
        "price_selector": ".variant-price, .price",
        "queries": [
            "creatine monohydrate", "creapure", "Optimum Nutrition creatine", "MuscleBlaze creatine", 
            "mass gainer", "weight gainer", "Optimum Nutrition Serious Mass", "MuscleBlaze Super Gainer",
            "pre workout", "Cellucor C4", "MuscleBlaze Pre Workout", "Gold Standard Pre-Workout"
        ]
    },
    {
        "platform": "Nutrabay",
        "url_template": "https://nutrabay.com/search?type=product&q={query}",
        "card_selector": ".product-card, .grid__item, .product-item",
        "title_selector": ".product-card__title, .card__heading, h2, h3, a.full-unstyled-link",
        "price_selector": ".price-item--sale, .price-item--regular, .price",
        "queries": [
            "creatine monohydrate", "MuscleTech Cell-Tech", "Optimum Nutrition creatine", "Wellcore creatine",
            "mass gainer", "MuscleTech Mass-Tech", "Dymatize Super Mass Gainer", "Labrada Mass Gainer",
            "pre workout", "Psychotic pre workout", "Cellucor C4", "Applied Nutrition ABE"
        ]
    },
    {
        "platform": "Flipkart",
        "url_template": "https://www.flipkart.com/search?q={query}",
        "card_selector": "div._1AtVbE, div.slAVV4, div.c3e8SH",
        "title_selector": "a.IRpwTa, a.s1Q9rs, a.WKTcLC",
        "price_selector": "div._30jeq3, div.Nx9bqj",
        "queries": [
            "creatine monohydrate", "MuscleBlaze creatine", "Optimum Nutrition creatine",
            "mass gainer protein", "MuscleBlaze mass gainer", "Serious Mass gainer",
            "pre workout powder", "Cellucor C4 pre workout"
        ]
    },
    {
        "platform": "Amazon",
        "url_template": "https://www.amazon.in/s?k={query}",
        "card_selector": "div[data-component-type='s-search-result']",
        "title_selector": "h2 span",
        "price_selector": "span.a-price-whole",
        "queries": [
            "creatine monohydrate", "Optimum Nutrition Creatine", "Wellcore Creatine", "MuscleBlaze Creatine",
            "mass gainer", "Optimum Nutrition Serious Mass", "MuscleTech Mass Tech", "Dymatize Super Mass",
            "pre workout supplement", "Cellucor C4 Pre Workout", "Gold Standard Pre-Workout"
        ]
    },
    {
        "platform": "Nykaa",
        "url_template": "https://www.nykaa.com/search/result/?q={query}",
        "card_selector": ".productWrapper, .css-1rd7vky",
        "title_selector": ".css-xrzmfa, .title",
        "price_selector": ".css-111z9ua, .price",
        "queries": [
            "creatine monohydrate", "mass gainer", "pre workout"
        ]
    }
]

# D2C Registry
D2C_STORES = [
    {"brand": "Optimum Nutrition (ON)", "domain": "optimumnutrition.co.in"},
    {"brand": "Nakpro", "domain": "nakpro.com"},
    {"brand": "AS-IT-IS Nutrition", "domain": "asitisnutrition.com"},
    {"brand": "GNC India", "domain": "guardian.in"},
    {"brand": "Fast&Up", "domain": "fastandup.in"},
    {"brand": "Big Muscles Nutrition", "domain": "bigmusclesnutrition.com"},
    {"brand": "Nutrabox", "domain": "nutrabox.in"},
    {"brand": "Scitron", "domain": "scitron.com"},
    {"brand": "Repfuel Sports", "domain": "repfuelsports.com"},
    {"brand": "Proburst", "domain": "proburst.com"},
    {"brand": "Muscle Nectar", "domain": "musclenectar.com"},
    {"brand": "Naturaltein / Beast Life", "domain": "naturaltein.in"},
    {"brand": "Boldfit", "domain": "boldfit.in"}
]

class SiloMasterCatalogEngine:
    def __init__(self):
        self.fetcher = ResilientStealthFetcher()

    def record_to_sqlite(
        self,
        silo: str,
        brand: str,
        base_name: str,
        flavor: str,
        weight_g: float,
        price_inr: float,
        platform: str,
        listing_url: str,
        image_url: str,
        variant_hash: str,
        metrics: Dict[str, Any]
    ):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            if silo == "creatine":
                servings = max(1, int(weight_g / 3.0))
                cost_per_g = metrics.get("primaryMetricValue", 0.0)
                cur.execute("""
                    INSERT OR REPLACE INTO creatine_catalog 
                    (brand, base_name, flavor, weight_grams, servings_count, serving_size_g, creatine_per_serving_g, price_inr, cost_per_g_creatine_inr, platform, listing_url, image_url, variant_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (brand, base_name, flavor, weight_g, servings, 3.0, 3.0, price_inr, cost_per_g, platform, listing_url, image_url, variant_hash))

            elif silo == "mass_gainers":
                servings = max(1, int(weight_g / 100.0))
                cost_per_1000 = metrics.get("primaryMetricValue", 0.0)
                c_p_ratio = metrics.get("secondaryMetricValue", 3.5)
                cur.execute("""
                    INSERT OR REPLACE INTO mass_gainer_catalog 
                    (brand, base_name, flavor, weight_grams, servings_count, serving_size_g, calories_per_serving, protein_per_serving_g, carbs_per_serving_g, carb_protein_ratio, price_inr, cost_per_1000_kcal_inr, platform, listing_url, image_url, variant_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (brand, base_name, flavor, weight_g, servings, 100.0, 375.0, 20.0, 70.0, c_p_ratio, price_inr, cost_per_1000, platform, listing_url, image_url, variant_hash))

            elif silo == "pre_workout":
                servings = max(1, int(weight_g / 8.0))
                cost_per_scoop = metrics.get("primaryMetricValue", 0.0)
                cur.execute("""
                    INSERT OR REPLACE INTO pre_workout_catalog 
                    (brand, base_name, flavor, weight_grams, servings_count, serving_size_g, caffeine_per_serving_mg, price_inr, cost_per_scoop_inr, platform, listing_url, image_url, variant_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (brand, base_name, flavor, weight_g, servings, 8.0, 200.0, price_inr, cost_per_scoop, platform, listing_url, image_url, variant_hash))

            conn.commit()
        except Exception as e:
            logger.warning(f"SQLite insert error for {silo} ({brand} - {base_name}): {e}")
        finally:
            conn.close()

    async def sync_to_supabase(
        self,
        silo: str,
        brand: str,
        base_name: str,
        flavor: str,
        weight_g: float,
        price_inr: float,
        platform: str,
        listing_url: str,
        image_url: str,
        variant_hash: str,
        metrics: Dict[str, Any]
    ):
        if not supabase or price_inr <= 0:
            return

        try:
            # 1. Product check / insert
            prod_res = supabase.table("products").select("id").eq("brand", brand).eq("base_name", base_name).execute()
            if prod_res.data and len(prod_res.data) > 0:
                product_id = prod_res.data[0]["id"]
            else:
                p_insert = supabase.table("products").upsert({
                    "brand": brand,
                    "base_name": base_name,
                    "category_silo": silo,
                    "protein_source": silo.replace("_", " ").title(),
                    "image_url": image_url,
                    "trust_score": 95
                }, on_conflict="brand,base_name").execute()
                if not p_insert.data:
                    return
                product_id = p_insert.data[0]["id"]

            # 2. Variant check / insert
            v_res = supabase.table("variants").select("id").eq("variant_hash", variant_hash).execute()
            if v_res.data and len(v_res.data) > 0:
                variant_id = v_res.data[0]["id"]
                supabase.table("variants").update({"lowest_price_inr": price_inr}).eq("id", variant_id).execute()
            else:
                sku_id = f"{brand.lower().replace(' ', '')[:8]}-{flavor[:6]}-{int(weight_g)}g-{variant_hash[:6]}"
                servings = max(1, int(weight_g / (3.0 if silo == 'creatine' else 8.0 if silo == 'pre_workout' else 100.0)))
                new_var = supabase.table("variants").insert({
                    "product_id": product_id,
                    "sku_id": sku_id,
                    "variant_hash": variant_hash,
                    "flavor": flavor,
                    "weight_grams": float(weight_g),
                    "lowest_price_inr": price_inr,
                    "servings_count": servings,
                    "best_value_metric": metrics.get("primaryMetricValue", 0.0),
                    "raw_json_data": json.dumps({"silo": silo, "metrics": metrics})
                }).execute()
                if not new_var.data:
                    return
                variant_id = new_var.data[0]["id"]

            # 3. Price Listing upsert
            supabase.table("price_listings").upsert({
                "variant_id": variant_id,
                "source": platform,
                "platform_name": platform.lower(),
                "source_url": listing_url,
                "listing_url": listing_url,
                "price_inr": price_inr,
                "current_price_inr": price_inr,
                "in_stock": True,
                "is_in_stock": True,
                "seller_name": platform,
                "is_authorized_seller": True,
                "scraped_at": "now()"
            }, on_conflict="variant_id,source").execute()

        except Exception as e:
            logger.warning(f"Supabase sync error for {silo} ({brand} - {base_name}): {e}")

    async def process_item(
        self,
        raw_title: str,
        price_inr: float,
        url: str,
        image_url: str,
        platform: str,
        brand_hint: str = ""
    ) -> bool:
        if price_inr <= 0 or not raw_title:
            return False
        if not SILO_TARGET_FILTER.search(raw_title) or JUNK_FILTER.search(raw_title):
            return False

        silo = classify_silo(raw_title)
        if not silo:
            return False

        brand = brand_hint or detect_canonical_brand(raw_title)
        if not brand:
            return False

        # Weight & Flavor resolution
        weight_g = VariantNormalizer.parse_weight(raw_title, default=None)
        if not weight_g:
            # Sane defaults if title omits container weight:
            # Creatine: 100g, Pre-workout: 250g, Mass gainer: 1000g
            if silo == "creatine": weight_g = 100
            elif silo == "pre_workout": weight_g = 250
            elif silo == "mass_gainers": weight_g = 1000

        flavor = VariantNormalizer.parse_flavor(raw_title)

        # Clean base name
        clean_base = re.split(r"\s*\|\s*|\s+[-–—]\s+", raw_title)[0].strip()
        clean_base = re.sub(r",\s*\d+.*$", "", clean_base).strip()[:100]

        # Calculate PRD Equalizer Metrics
        servings = max(1, int(weight_g / (3.0 if silo == 'creatine' else 8.0 if silo == 'pre_workout' else 100.0)))
        serving_size = 3.0 if silo == "creatine" else 8.0 if silo == "pre_workout" else 100.0

        metrics = EqualizerEngine.calculate_silo_equalizer(
            silo=silo,
            price_inr=price_inr,
            packaging={"servingsCount": servings, "servingSizeGrams": serving_size},
            nutritional_profile={
                "activeIngredientPerServingGrams": 3.0,
                "caffeinePerServingMg": 200.0,
                "caloriesPerServing": 375.0,
                "proteinPerServingGrams": 20.0,
                "carbsPerServingGrams": 70.0
            }
        )

        # Mint deterministic variant hash
        norm = VariantNormalizer.execute(product_id=silo, raw_title=f"{brand} {clean_base} {flavor} {weight_g}g")
        v_hash = norm.variant_hash

        # 1. Save to separate SQL table in SQLite
        self.record_to_sqlite(
            silo=silo,
            brand=brand,
            base_name=clean_base,
            flavor=flavor,
            weight_g=weight_g,
            price_inr=price_inr,
            platform=platform,
            listing_url=url,
            image_url=image_url,
            variant_hash=v_hash,
            metrics=metrics
        )

        # 2. Sync to Supabase products/variants/price_listings under proper silo
        await self.sync_to_supabase(
            silo=silo,
            brand=brand,
            base_name=clean_base,
            flavor=flavor,
            weight_g=weight_g,
            price_inr=price_inr,
            platform=platform,
            listing_url=url,
            image_url=image_url,
            variant_hash=v_hash,
            metrics=metrics
        )

        logger.info(f"[{silo.upper()}] LOCKED IN SQL: {brand} - {clean_base[:35]} [{flavor}, {weight_g}g] @ INR {price_inr} ({metrics.get('primaryMetricLabel')}: {metrics.get('primaryMetricValue')})")
        return True

    # LANE 1: D2C Ingestion
    async def run_d2c_lane(self) -> int:
        logger.info("\n" + "=" * 60)
        logger.info("[LANE 1] SCANNING D2C STOREFRONTS FOR CREATINE, MASS GAINERS, PRE-WORKOUT")
        logger.info("=" * 60)
        total_ingested = 0

        for store in D2C_STORES:
            brand = store["brand"]
            domain = store["domain"]
            endpoint = f"https://{domain}/products.json?limit=250"
            logger.info(f"[{brand}] Querying endpoint: {endpoint}")

            try:
                status, body, _, _ = await self.fetcher.fetch(endpoint, timeout=12)
            except Exception as e:
                logger.warning(f"[{brand}] Network fetch error: {e}. Skipping.")
                continue

            if status != 200 or not body:
                logger.warning(f"[{brand}] HTTP {status}. Skipping.")
                continue

            try:
                catalog = json.loads(body)
                products = catalog.get("products", [])
            except Exception as e:
                logger.warning(f"[{brand}] JSON parse error: {e}. Skipping.")
                continue

            count = 0
            for p in products:
                title = p.get("title", "")
                if not SILO_TARGET_FILTER.search(title) or JUNK_FILTER.search(title):
                    continue

                images = p.get("images", [])
                img = images[0].get("src") if images else ""
                handle = p.get("handle", "")
                url = f"https://{domain}/products/{handle}" if handle else f"https://{domain}"

                for v in p.get("variants", []):
                    try:
                        price = float(v.get("price", 0))
                        var_title = v.get("title", "")
                        combined_title = f"{title} {var_title}"
                        success = await self.process_item(
                            raw_title=combined_title,
                            price_inr=price,
                            url=url,
                            image_url=img,
                            platform="D2C",
                            brand_hint=brand
                        )
                        if success:
                            count += 1
                            total_ingested += 1
                    except Exception as var_err:
                        logger.debug(f"Variant error: {var_err}")
                        continue

            logger.info(f"  > [{brand}] Ingested {count} items.")

        return total_ingested

    # LANE 2: Marketplace Pulse
    async def run_marketplace_lane(self) -> int:
        logger.info("\n" + "=" * 60)
        logger.info("[LANE 2] RUNNING TARGETED MARKETPLACE PULSE FOR SILOS")
        logger.info("=" * 60)
        total_ingested = 0

        for target in MARKETPLACE_SILO_TARGETS:
            platform = target["platform"]
            logger.info(f"\n--- Platform: {platform} ({len(target['queries'])} queries scheduled) ---")

            for query in target["queries"]:
                try:
                    url = target["url_template"].format(query=query.replace(" ", "+"))
                    logger.info(f"[{platform}] Probing: {url}")

                    status, body, _, _ = await self.fetcher.fetch(url, timeout=15)
                    if status != 200 or not body:
                        logger.warning(f"[{platform}] HTTP {status} on '{query}'. Skipping.")
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
                            raw_price = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
                            price = float(raw_price) if raw_price else 0.0

                            link_el = card.find("a", href=True)
                            link = link_el["href"] if link_el else url
                            if link and not link.startswith("http"):
                                from urllib.parse import urljoin
                                link = urljoin(url, link)

                            img_el = card.find("img")
                            img = img_el.get("src") or img_el.get("data-src") or "" if img_el else ""

                            success = await self.process_item(
                                raw_title=raw_title,
                                price_inr=price,
                                url=link,
                                image_url=img,
                                platform=platform
                            )
                            if success:
                                total_ingested += 1

                        except Exception as card_err:
                            logger.debug(f"Card parse error: {card_err}")
                            continue

                except Exception as q_err:
                    logger.warning(f"Query error for '{query}': {q_err}. Moving on.")
                    continue

        return total_ingested

    async def run(self):
        d2c = await self.run_d2c_lane()
        mkt = await self.run_marketplace_lane()
        logger.info("\n" + "=" * 60)
        logger.info(f"SILO CYCLE COMPLETED: {d2c} D2C items + {mkt} Marketplace items cataloged into separate SQL tables!")
        logger.info("=" * 60)
        await self.fetcher.close()

async def main():
    engine = SiloMasterCatalogEngine()
    await engine.run()

if __name__ == "__main__":
    asyncio.run(main())

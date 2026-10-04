"""
Scrapling-powered OMNI-CHANNEL scraper (14 Platforms)
Excludes Quick-Commerce. Covers Horizontal, Specialized Fitness, E-Pharmacy, Lifestyle, and D2C.
Stores everything in Supabase `price_listings`.
"""

import os
import sys
import json
import re
import asyncio
import logging
import traceback
from dotenv import load_dotenv
from supabase import create_client
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.analytics.equalizer import EqualizerEngine
from src.analytics.ingredient_auditor import IngredientAuditor
from src.vision.review_authenticity import ReviewAuthenticityEngine
from src.pipeline.seller_matrix import SellerMatrix
from src.pipeline.normalizer import VariantNormalizer
from src.pipeline.matcher import VariantMatcher, insert_unmatched_product
from supabase import Client
from scrapling.fetchers import StealthyFetcher

import random
import requests

# --- Logging & Environment Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_production.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OmniScraper")

# Load environment configuration from both local and root .env
load_dotenv(dotenv_path="../.env")
load_dotenv()

def get_proxy_pool() -> list:
    """
    Resolves proxy pool adhering to PRD Section 7 (Rotating Indian Residential Proxies).
    1. Checks environment variables (ROTATING_PROXY_URL, PROXY_URL, PROXIES_LIST).
    2. Respects DISABLE_FREE_PROXIES flag.
    3. Falls back to free public proxies from sslproxies.org with a 5s timeout.
    """
    env_proxies = (
        os.environ.get("ROTATING_PROXY_URL")
        or os.environ.get("PROXY_URL")
        or os.environ.get("PROXIES_LIST")
        or os.environ.get("PROXIES")
    )
    if env_proxies:
        proxies = [p.strip() for p in env_proxies.split(",") if p.strip()]
        if proxies:
            logger.info(f"Loaded {len(proxies)} residential/custom proxies from environment configuration.")
            return proxies

    if os.environ.get("DISABLE_FREE_PROXIES", "").lower() in ("1", "true", "yes"):
        logger.info("Free proxy rotation disabled via DISABLE_FREE_PROXIES.")
        return []

    try:
        logger.info("Fetching free IP proxies from sslproxies.org...")
        res = requests.get('https://www.sslproxies.org/', timeout=5)
        proxies = []
        for match in re.finditer(r"<tr><td>(\d{1,3}(?:\.\d{1,3}){3})</td><td>(\d+)</td>", res.text):
            proxies.append(f"http://{match.group(1)}:{match.group(2)}")
        logger.info(f"Loaded {len(proxies)} free proxies for IP rotation.")
        return proxies
    except Exception as e:
        logger.warning(f"Could not load free proxies from sslproxies.org: {e}")
        return []

PROXY_POOL = get_proxy_pool()
CONCURRENCY_LIMIT = asyncio.Semaphore(3)  # Max 3 concurrent requests

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

BRANDS = [
    {"brand": "Optimum Nutrition (ON)", "d2c": None, "hk": None}, {"brand": "MuscleTech", "d2c": None, "hk": None},
    {"brand": "Dymatize", "d2c": None, "hk": None}, {"brand": "BSN", "d2c": None, "hk": None},
    {"brand": "Isopure", "d2c": None, "hk": None}, {"brand": "Cellucor", "d2c": None, "hk": None},
    {"brand": "Nutrex", "d2c": None, "hk": None}, {"brand": "MusclePharm", "d2c": None, "hk": None},
    {"brand": "Universal / Animal", "d2c": None, "hk": None}, {"brand": "Ultimate Nutrition", "d2c": None, "hk": None},
    {"brand": "Rule 1", "d2c": None, "hk": None}, {"brand": "Labrada", "d2c": None, "hk": None},
    {"brand": "Scitec Nutrition", "d2c": None, "hk": None}, {"brand": "Olimp", "d2c": None, "hk": None},
    {"brand": "Applied Nutrition", "d2c": None, "hk": None}, {"brand": "PhD Nutrition", "d2c": None, "hk": None},
    {"brand": "Gaspari", "d2c": None, "hk": None}, {"brand": "Redcon1", "d2c": None, "hk": None},
    {"brand": "Ghost", "d2c": None, "hk": None}, {"brand": "Kaged", "d2c": None, "hk": None},
    {"brand": "Bucked Up", "d2c": None, "hk": None}, {"brand": "Six Star", "d2c": None, "hk": None},
    {"brand": "Muscle Milk", "d2c": None, "hk": None}, {"brand": "Orgain", "d2c": None, "hk": None},
    {"brand": "Garden of Life", "d2c": None, "hk": None}, {"brand": "NOW Sports", "d2c": None, "hk": None},
    {"brand": "Allmax", "d2c": None, "hk": None}, {"brand": "Beast Sports Nutrition", "d2c": None, "hk": None},
    {"brand": "Body Fortress", "d2c": None, "hk": None}, {"brand": "Evlution Nutrition (EVL)", "d2c": None, "hk": None},
    {"brand": "JNX Sports", "d2c": None, "hk": None}, {"brand": "Legion Athletics", "d2c": None, "hk": None},
    {"brand": "Mutant", "d2c": None, "hk": None}, {"brand": "Naked Nutrition", "d2c": None, "hk": None},
    {"brand": "Nutrabolics", "d2c": None, "hk": None}, {"brand": "Nutricost", "d2c": None, "hk": None},
    {"brand": "ProSupps", "d2c": None, "hk": None}, {"brand": "Sunwarrior", "d2c": None, "hk": None},
    {"brand": "Transparent Labs", "d2c": None, "hk": None}, {"brand": "Vega", "d2c": None, "hk": None},
    {"brand": "Scivation / Xtend", "d2c": None, "hk": None}, {"brand": "GAT Sport", "d2c": None, "hk": None},
    {"brand": "Insane Labz", "d2c": None, "hk": None}, {"brand": "Kevin Levrone Signature", "d2c": None, "hk": None},
    {"brand": "Ronnie Coleman Signature", "d2c": None, "hk": None}, {"brand": "MuscleBlaze", "d2c": None, "hk": None},
    {"brand": "Avvatar", "d2c": None, "hk": None}, {"brand": "AS-IT-IS Nutrition", "d2c": None, "hk": None},
    {"brand": "Nakpro", "d2c": None, "hk": None}, {"brand": "Fast&Up", "d2c": None, "hk": None},
    {"brand": "Wellcore", "d2c": None, "hk": None}, {"brand": "Big Muscles Nutrition", "d2c": None, "hk": None},
    {"brand": "Scitron", "d2c": None, "hk": None}, {"brand": "Repfuel Sports", "d2c": None, "hk": None},
    {"brand": "Nutrabox", "d2c": None, "hk": None}, {"brand": "GNC India", "d2c": None, "hk": None},
    {"brand": "Myprotein India", "d2c": None, "hk": None}, {"brand": "Pintola", "d2c": None, "hk": None},
    {"brand": "Alpino", "d2c": None, "hk": None}, {"brand": "MyFitness", "d2c": None, "hk": None},
    {"brand": "Yogabar", "d2c": None, "hk": None}, {"brand": "RiteBite Max Protein", "d2c": None, "hk": None},
    {"brand": "SuperYou", "d2c": None, "hk": None}, {"brand": "The Whole Truth Foods", "d2c": None, "hk": None},
    {"brand": "Phab", "d2c": None, "hk": None}, {"brand": "NutroActive", "d2c": None, "hk": None},
    {"brand": "Ketofy / Lo! Foods", "d2c": None, "hk": None}, {"brand": "True Elements", "d2c": None, "hk": None},
    {"brand": "Boldfit", "d2c": None, "hk": None}, {"brand": "Carbamide Forte", "d2c": None, "hk": None},
    {"brand": "HealthyHey Nutrition", "d2c": None, "hk": None}, {"brand": "Kapiva", "d2c": None, "hk": None},
    {"brand": "Upakarma Ayurveda", "d2c": None, "hk": None}, {"brand": "Neuherbs", "d2c": None, "hk": None},
    {"brand": "Man Matters", "d2c": None, "hk": None}, {"brand": "Zingavita", "d2c": None, "hk": None},
    {"brand": "TrueBasics", "d2c": None, "hk": None}, {"brand": "Cosmix", "d2c": None, "hk": None},
    {"brand": "Plix Life", "d2c": None, "hk": None}, {"brand": "OZiva", "d2c": None, "hk": None},
    {"brand": "Naturaltein / Beast Life", "d2c": None, "hk": None}
]


DEFAULT_SELECTORS = {
    "card": ".product-card, .grid-view-item, .product-item, .item, li.grid__item, .product-block",
    "title": ".product-title, .grid-view-item__title, h2, h3, .product-name",
    "price": ".price-item--sale, .price-item--regular, .price, .money, .product-price"
}

SITES_CONFIG = {
    "Amazon": {
        "search_url": "https://www.amazon.in/s?k={query}",
        "selectors": {
            "card": "div[data-component-type='s-search-result']",
            "title": "h2 span",
            "price": "span.a-price-whole"
        }
    },
    "Flipkart": {
        "search_url": "https://www.flipkart.com/search?q={query}",
        "selectors": {
            "card": "div._1AtVbE, div.slAVV4, div.c3e8SH",
            "title": "a.IRpwTa, a.s1Q9rs, a.WKTcLC",
            "price": "div._30jeq3, div.Nx9bqj"
        }
    },
    "HealthKart": {
        "search_url": "https://www.healthkart.com/search?query={query}",
        "selectors": {
            "card": ".variant-inner-content, .product-card",
            "title": "a.block, h3",
            "price": ".variant-price, .price"
        }
    },
    "Nutrabay_Mkt": {
        "search_url": "https://nutrabay.com/search?type=product&q={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "HyugaLife": {
        "search_url": "https://hyugalife.com/search?q={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "Nutriride": {
        "search_url": "https://nutriride.com/search?q={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "Tata 1mg": {
        "search_url": "https://www.1mg.com/search/all?name={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "PharmEasy": {
        "search_url": "https://pharmeasy.in/search/all?name={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "Netmeds": {
        "search_url": "https://www.netmeds.com/catalogsearch/result/{query}/all",
        "selectors": DEFAULT_SELECTORS
    },
    "JioMart": {
        "search_url": "https://www.jiomart.com/search/{query}",
        "selectors": DEFAULT_SELECTORS
    },
    "Nykaa": {
        "search_url": "https://www.nykaa.com/search/result/?q={query}",
        "selectors": DEFAULT_SELECTORS
    },
    "Apollo": {
        "search_url": "https://www.apollopharmacy.in/search-medicines/{query}",
        "selectors": DEFAULT_SELECTORS
    },
    "myproteinindia": {
        "search_url": "https://www.myprotein.co.in/elysium.search?search={query}",
        "selectors": DEFAULT_SELECTORS
    }
}

NEW_SITES = [
    ("nutristar", "nutristar.in"), ("neulife", "neulife.com"), ("proteinxpressindia", "proteinxpressindia.com"), 
    ("supplementsvilla", "supplementsvilla.com"), ("sourceofsupplements", "sourceofsupplements.in"), 
    ("broadwaylive", "shop.broadwaylive.in"), ("apexsupplements", "apexsupplements.in"), 
    ("muscleblaze", "muscleblaze.com"), ("optimumnutrition", "optimumnutrition.co.in"), ("gncindia", "guardian.in"), 
    ("asitisnutrition", "asitisnutrition.com"), ("nakpro", "nakpro.com"), ("avvatar", "avvatarindia.com"), 
    ("nutrabox", "nutrabox.in"), ("fastandup", "fastandup.in"), ("bigmusclesnutrition", "bigmusclesnutrition.com"), 
    ("healthfarmnutrition", "healthfarmnutrition.com"), ("thewholetruthfoods", "thewholetruthfoods.com"), 
    ("truebasics", "truebasics.com"), ("getmymettle", "getmymettle.com"), ("scitron", "scitron.com"), 
    ("musclenectar", "musclenectar.com"), ("sixpacknutrition", "sixpacknutrition.in"), ("repfuelsports", "repfuelsports.com"), 
    ("absolutenutrition", "absolutenutrition.co.in"), ("osoaa", "osoaa.in"), ("trunativ", "trunativ.co"), 
    ("proburst", "proburst.com"), ("cosmix", "cosmix.in"), ("plixlife", "plixlife.com"), ("oziva", "oziva.in"), 
    ("superyou", "superyou.in"), ("aceblend", "aceblend.com"), ("greenprotein", "greenprotein.co.in"), 
    ("sattuz", "sattuz.in"), ("boldfit", "boldfit.in"), ("unived", "unived.in"), ("cureveda", "cureveda.com"), 
    ("musclehouseindia", "musclehouseindia.com"), ("wellcore", "wellcore.in"), ("myprotein", "myprotein.co.in"), 
    ("pintola", "pintola.in"), ("alpino", "alpino.in"), ("myfitness", "myfitness.in"), ("yogabar", "yogabar.in"), 
    ("maxprotein", "maxprotein.in"), ("getphab", "getphab.com"), ("nutroactive", "nutroactive.com"), 
    ("trueelements", "trueelements.com"), ("cfstores", "cfstores.in"), ("healthyhey", "healthyhey.com"), 
    ("kapiva", "kapiva.in"), ("upakarma", "upakarma.com"), ("neuherbs", "neuherbs.com"), ("manmatters", "manmatters.com"), 
    ("zingavita", "zingavita.com"), ("naturaltein", "naturaltein.in"), ("desertcart", "desertcart.in"), ("ubuy", "ubuy.co.in")
]

for name, domain in NEW_SITES:
    prefix = "https://" if domain.startswith("shop.") else "https://www."
    SITES_CONFIG[name] = {
        "search_url": f"{prefix}{domain}/search?q={{query}}",
        "selectors": DEFAULT_SELECTORS
    }

TARGET_FILTER = re.compile(r"protein|whey|isolate|casein|plant|pea|creatine|mass.?gainer|weight.?gainer|pre.?workout", re.I)
JUNK_FILTER = re.compile(r"shaker|bottle|t-shirt|bag|cap|combo|bundle|multivitamin|bar\b|bars\b|cookie|snack|chips|biscuit|spread|peanut\s*butter|gummies|drink|rtd|trial|sachet|delay|climax|sex|testosterone|shilajit|ashwagandha|vitality|intimacy|fish oil|omega|collagen|biotin|immunity|wellness", re.I)

def extract_weight(text: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|lbs?)\b", text, re.I)
    if not m: return 1000.0
    val, unit = float(m.group(1)), m.group(2).lower()
    if unit == "kg": return val * 1000
    if unit == "g": return val
    return val * 453.592


def extract_seller(parent) -> str:
    # Attempt to extract seller name from common selectors
    if not parent: return ""
    seller_els = parent.css(".seller-name, [class*='seller'], [class*='soldBy'], #sellerProfileTriggerId")
    if seller_els:
        text = seller_els[0].get_all_text() if hasattr(seller_els[0], 'get_all_text') else getattr(seller_els[0], 'text', '')
        return text.replace("Sold by", "").replace("sold by", "").strip()
    return ""

def upsert_product_variant(brand: str, title: str, price: float, img: str, url: str, source: str, description: str = "", seller_name: str = ""):
    combined_text = (title + " " + description).lower()
    if not TARGET_FILTER.search(combined_text) or JUNK_FILTER.search(combined_text) or price <= 0:
        return False

    base_name = re.split(r"[,|-]", title)[0].strip()[:100]
    weight = extract_weight(combined_text)
    
    silo = "protein"
    if re.search(r"mass|gainer", combined_text): silo = "mass_gainer"
    elif "creatine" in combined_text: silo = "creatine"
    elif re.search(r"pre.?workout", combined_text): silo = "pre_workout"
    elif re.search(r"vitamin|omega|fish oil", combined_text): silo = "vitamins"

    psource = "Whey"
    if re.search(r"plant|pea|vegan|soy|brown rice", combined_text): psource = "Plant"
    elif re.search(r"yeast", combined_text): psource = "Yeast"
    elif "casein" in combined_text: psource = "Casein"


    # --- TRUST ENGINE MODULES ---
    # 1. Fairy-Dusting Check
    ingredient_audit = IngredientAuditor.audit(description)
    base_trust_score = 100 - ingredient_audit['trust_deduction']
    
    # 2. Review Authenticity (Mocked fetching for now)
    review_audit = ReviewAuthenticityEngine.audit_reviews(base_name)
    
    # 3. Seller Matrix
    is_authorized = SellerMatrix.verify_seller(seller_name, brand)
    # ----------------------------

    if not supabase:
        logger.error("Supabase client not initialized; cannot upsert product variant.")
        return False

    try:
        res = supabase.table("products").upsert({
            "brand": brand, "base_name": base_name, "category_silo": silo,
            "protein_source": psource, "image_url": img,
            "is_fairy_dusted": ingredient_audit['is_fairy_dusted'],
            "fairy_dusting_flags": ingredient_audit['flags'],
            "trust_score": base_trust_score
        }, on_conflict="brand,base_name").execute()

        if not res.data: return False
        product_id = res.data[0]["id"]

        # Deterministic normalization and hashing (PRD Section 3.1 & 4.1)
        normalized = VariantNormalizer.execute(product_id=product_id, raw_title=combined_text)
        weight = float(normalized.weight_grams)
        flavor = normalized.canonical_flavor
        v_hash = normalized.variant_hash
        sku_id = f"{brand.lower().replace(' ', '')[:8]}-{flavor[:6]}-{int(weight)}g-{v_hash[:6]}"

        # Use standard estimations until OCR Vision pipeline is connected
        serving_size_g = 33.0
        label_protein_g = min(24.0, serving_size_g)
        total_servings = max(1, int(weight / serving_size_g))
        
        analytics_metrics = EqualizerEngine.calculate_metrics(
            category=psource,
            price_inr=price,
            label_protein_g=label_protein_g,
            serving_size_g=serving_size_g,
            total_servings=total_servings
        )

        raw_json = json.dumps({
            "description": description.strip(),
            "analytics": analytics_metrics,
            "variant_hash": v_hash
        })
        
        vres = supabase.table("variants").upsert({
            "product_id": product_id,
            "sku_id": sku_id,
            "variant_hash": v_hash,
            "flavor": flavor,
            "weight_grams": weight,
            "lowest_price_inr": price,
            "servings_count": total_servings,
            "best_value_metric": analytics_metrics["effective_cost_per_bioavailable_g_inr"],
            "raw_json_data": raw_json,
            "authenticity_score": review_audit['authenticity_score'],
            "has_bot_reviews": review_audit['has_bot_reviews']
        }, on_conflict="sku_id").execute()

        if not vres.data: return False
        variant_id = vres.data[0]["id"]

        supabase.table("price_listings").upsert({
            "variant_id": variant_id,
            "source": source,
            "platform_name": source.lower(),
            "source_url": url,
            "listing_url": url,
            "price_inr": price,
            "current_price_inr": price,
            "in_stock": True,
            "is_in_stock": True,
            "seller_name": seller_name,
            "is_authorized_seller": is_authorized
        }, on_conflict="variant_id,source").execute()

        return True
    except Exception as e:
        logger.error(f"DB Upsert Failed [{brand} - {source}]: {str(e)}")
        return False


ALL_TRACKED_BRANDS = ["Optimum Nutrition", "MuscleBlaze", "MyProtein", "Dymatize", "Isopure", "GNC", "MuscleTech", "Avvatar", "Nakpro", "AS-IT-IS", "Nutrabay", "XLR8", "Fast&Up", "Yogabar", "The Whole Truth", "Amul", "Foodstrong", "MyFitFuel", "Cosmix", "TrueBasics", "Atom", "One Science"]

def detect_true_brand(title: str, fallback_brand: str) -> str:
    title_norm = title.lower().replace("-", "").replace(" ", "")
    for b in ALL_TRACKED_BRANDS:
        b_norm = b.lower().replace("-", "").replace(" ", "")
        if b_norm in title_norm:
            return b
    return fallback_brand

async def scrape_url(url: str, brand: str, source: str, is_trusted_seed: bool = False) -> int:
    count = 0
    from scrapling.fetchers import Fetcher
    
    async with CONCURRENCY_LIMIT:
        await asyncio.sleep(random.uniform(0.5, 2.5))
        proxy = random.choice(PROXY_POOL) if PROXY_POOL else None
        page = None
        
        for attempt in range(3):
            try:
                # Tier 1: Fast HTTP Request
                fast_fetcher = Fetcher(proxy=proxy)
                page = await asyncio.to_thread(fast_fetcher.get, url)
                
                # Check for anti-bot blocks
                html_lower = page.text.lower()
                bot_signs = ["cloudflare", "datadome", "captcha", "security check", "access denied", "verify you are human"]
                
                if page.status in [403, 429, 503] or any(b in html_lower for b in bot_signs):
                    logger.warning(f"[{source}] Anti-bot detected on fast fetch. Escalating to StealthyFetcher...")
                    # Tier 2: Headless Browser Escalation
                    page = await StealthyFetcher.async_fetch(url, headless=True, network_idle=True, timeout=25000, proxy=proxy)
                    
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to fetch {url} after retries: {e}")
                    return 0
                logger.warning(f"[{source}] Fetch attempt {attempt + 1} failed with proxy {proxy}: {e}")
                proxy = random.choice(PROXY_POOL) if (PROXY_POOL and attempt == 0) else None
                await asyncio.sleep(2)
        
        if not page: return 0
        try:
            site_config = SITES_CONFIG.get(source, {})
            selectors = site_config.get("selectors", DEFAULT_SELECTORS)
            cards = page.css(", ".join(selectors["card"].split(",")))
            logger.info(f"[{source.upper()}] Found {len(cards)} potential product cards.")

            for card in cards:
                try:
                    title_node = card.css(", ".join(selectors["title"].split(",")))
                    if hasattr(title_node, 'get_all_text'): title = title_node.get_all_text()
                    elif hasattr(title_node, 'get'): title = title_node.get(default="")
                    elif hasattr(title_node, 'text'): title = getattr(title_node, 'text', '')
                    else: title = ""
                    
                    price_node = card.css(", ".join(selectors["price"].split(",")))
                    if hasattr(price_node, 'get_all_text'): price_str = price_node.get_all_text()
                    elif hasattr(price_node, 'get'): price_str = price_node.get(default="")
                    elif hasattr(price_node, 'text'): price_str = getattr(price_node, 'text', '')
                    else: price_str = ""

                    title = title.strip()
                    digits = re.sub(r"[^\d.]", "", price_str or "")
                    price = float(digits) if digits else 0.0

                    if not title or price <= 0: continue

                    img_els = card.css("img")
                    img = img_els[0].attrib.get("src") or img_els[0].attrib.get("data-src") or "" if img_els else ""
                    
                    link_els = card.css("a")
                    link = link_els[0].attrib.get("href") or "" if link_els else ""
                    if link and not link.startswith("http"):
                        from urllib.parse import urljoin
                        link = urljoin(url, link)

                    card_desc = ""
                    if hasattr(card, "get_all_text"):
                        card_desc = card.get_all_text().replace(title, "").strip()

                    seller = extract_seller(card)
                    true_brand = detect_true_brand(title, brand)
                    
                    if is_trusted_seed:
                        if upsert_product_variant(true_brand, title, price, img, link, source, card_desc, seller):
                            count += 1
                    else:
                        verified_variant = VariantMatcher.match_variant(title)
                        if verified_variant:
                            logger.info(f"[{source.upper()}] MATCHED: '{title[:40]}...' -> DB ID {verified_variant['id']} | INR {price}")
                            if not supabase: continue
                            supabase.table("price_listings").upsert({
                                "variant_id": verified_variant['id'],
                                "source": source,
                                "platform_name": source.lower(),
                                "source_url": link,
                                "listing_url": link,
                                "price_inr": price,
                                "current_price_inr": price,
                                "in_stock": True,
                                "is_in_stock": True,
                                "seller_name": seller,
                                "is_authorized_seller": True
                            }, on_conflict="variant_id,source").execute()
                            count += 1
                        else:
                            inserted = insert_unmatched_product(true_brand, title, price, link, source)
                            if inserted:
                                logger.info(f"[{source.upper()}] LOGGED UNMATCHED PRODUCT: {title[:40]}")

                except Exception as e:
                    logger.warning(f"Error parsing card on {source}: {e}")
                    
            return count
        except Exception as e:
            logger.error(f"Scrape failed [{brand} - {source}]: {str(e)}")
            return 0


async def main():
    logger.info("=" * 60)
    logger.info("ULTIMATE OMNI-CHANNEL SCRAPER (14 PLATFORMS)")
    logger.info("Excluding Quick-Commerce. Extracting deeply across all sources.")
    logger.info("=" * 60 + "\n")

    for i, entry in enumerate(BRANDS):
        brand = entry["brand"]
        logger.info(f"[{i+1}/{len(BRANDS)}] Commencing extraction for: {brand}")

        # 1. D2C
        d2c = 0
        if entry.get("d2c"):
            d2c = await scrape_url(entry["d2c"], brand, "D2C", is_trusted_seed=True)
            logger.info(f"  > D2C [{brand}]: Found {d2c} valid products")
        
        # 2. HealthKart
        hk = await scrape_url(f"https://www.healthkart.com/{entry['hk']}/whey-protein?bss=1", brand, "HealthKart", is_trusted_seed=True)
        logger.info(f"  > HealthKart [{brand}]: Found {hk} valid products")

        # Execute all platform scrapes concurrently for the brand!
        brand_name = brand
        tasks = []
        for pf_name, config in SITES_CONFIG.items():
            url_template = config["search_url"]
            query = f"{brand_name} protein".replace(" ", "+")
            if pf_name == "Nutrabay_Mkt": query = brand_name.replace(" ", "-").lower()
            url = url_template.format(query=query)
            tasks.append(scrape_url(url, brand_name, pf_name))
            
        logger.info(f"[{brand_name}] Launching concurrent scrapes across {len(tasks)} platforms...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for pf_name, res in zip(SITES_CONFIG.keys(), results):
            if isinstance(res, Exception):
                logger.error(f"  > {pf_name} [{brand_name}]: Failed ({res})")
            else:
                logger.info(f"  > {pf_name} [{brand_name}]: Found {res} valid products")

        logger.info("-" * 40)
        
    logger.info("Scraping cycle complete.")
    
    try:
        import sys
        scraper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        if scraper_dir not in sys.path:
            sys.path.insert(0, scraper_dir)
        from gemini_nutrition import run as run_nutrition_update
        logger.info("Running post-scrape nutrition update via Gemini...")
        run_nutrition_update()
    except Exception as e:
        logger.error(f"Nutrition update error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

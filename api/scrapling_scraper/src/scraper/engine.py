"""
Scrapling-powered OMNI-CHANNEL scraper (14 Platforms)
Excludes Quick-Commerce. Covers Horizontal, Specialized Fitness, E-Pharmacy, Lifestyle, and D2C.
Stores everything in Supabase `price_listings`.
"""

import os
import re
import asyncio
import logging
import traceback
from dotenv import load_dotenv
from supabase import create_client
from src.analytics.ingredient_auditor import IngredientAuditor
from src.vision.review_authenticity import ReviewAuthenticityEngine
from src.pipeline.seller_matrix import SellerMatrix
from supabase import Client
from scrapling.fetchers import StealthyFetcher

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_production.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OmniScraper")

load_dotenv(dotenv_path="../.env")
supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

BRANDS = [
    {"brand": "MuscleBlaze",          "d2c": "https://www.muscleblaze.com/category/proteins",            "hk": "muscleblaze"},
    {"brand": "Nakpro",               "d2c": "https://nakpro.com/collections/all",                       "hk": "nakpro"},
    {"brand": "AS-IT-IS Nutrition",   "d2c": "https://asitisnutrition.com/collections/all",              "hk": "as-it-is-nutrition"},
    {"brand": "Nutrabay",             "d2c": "https://nutrabay.com/collections/protein",                  "hk": "nutrabay"},
    {"brand": "Avvatar",              "d2c": "https://avvatarindia.com/collections/all",                  "hk": "avvatar"},
    {"brand": "TrueBasics",           "d2c": "https://truebasics.com/collections/proteins",               "hk": "truebasics"},
    {"brand": "Cosmix",               "d2c": "https://cosmix.in/collections/all",                         "hk": "cosmix"},
    {"brand": "MyFitFuel",            "d2c": "https://www.myfitfuel.in/collections/all",                  "hk": "myfitfuel"},
    {"brand": "Foodstrong",           "d2c": "https://foodstrong.co/collections/all",                     "hk": "foodstrong"},
    {"brand": "Naturaltein",          "d2c": "https://naturaltein.in/collections/all",                    "hk": "naturaltein"},
    {"brand": "The Whole Truth",      "d2c": "https://thewholetruthfoods.com/collections/protein",        "hk": "the-whole-truth"},
    {"brand": "Amul",                 "d2c": "https://shop.amul.com/en/browse/fitness-nutrition",         "hk": "amul"},
    {"brand": "Yogabar",              "d2c": "https://www.yogabars.in/collections/proteins",              "hk": "yogabar"},
    {"brand": "Bigmuscles Nutrition", "d2c": "https://bigmusclesnutrition.com/collections/whey-protein",  "hk": "bigmuscles-nutrition"},
    {"brand": "Atom",                 "d2c": "https://asitisnutrition.com/collections/atom",              "hk": "atom"},
    {"brand": "Dymatize",             "d2c": None,                                                        "hk": "dymatize"},
]

SEARCH_PLATFORMS = {
    "Amazon":      "https://www.amazon.in/s?k={query}",
    "Flipkart":    "https://www.flipkart.com/search?q={query}",
    "Nutrabay_Mkt":"https://nutrabay.com/search?type=product&q={query}",
    "HyugaLife":   "https://hyugalife.com/search?q={query}",
    "Nutriride":   "https://nutriride.com/search?q={query}",
    "Tata 1mg":    "https://www.1mg.com/search/all?name={query}",
    "PharmEasy":   "https://pharmeasy.in/search/all?name={query}",
    "Netmeds":     "https://www.netmeds.com/catalogsearch/result/{query}",
    "JioMart":     "https://www.jiomart.com/search/{query}",
    "Nykaa":       "https://www.nykaa.com/search/result/?q={query}",
    "Apollo":      "https://www.apollopharmacy.in/search-medicines/{query}"
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
        sku_id = f"{source.lower()[:3]}-{brand[:10].replace(' ', '')}-{abs(hash(base_name)) % 1000000}"

        import sys, os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        from src.analytics.equalizer import EqualizerEngine

        # Use standard estimations until OCR Vision pipeline is connected
        serving_size_g = 33.0
        label_protein_g = 24.0
        total_servings = max(1, int(weight / serving_size_g))
        
        analytics_metrics = EqualizerEngine.calculate_metrics(
            category=psource,
            price_inr=price,
            label_protein_g=label_protein_g,
            serving_size_g=serving_size_g,
            total_servings=total_servings
        )

        import json
        raw_json = json.dumps({
            "description": description.strip(),
            "analytics": analytics_metrics
        })
        
        vres = supabase.table("variants").upsert({
            "product_id": product_id, "sku_id": sku_id, "flavor": "Varies",
            "weight_grams": weight, "lowest_price_inr": price,
            "servings_count": total_servings,
            "best_value_metric": analytics_metrics["effective_cost_per_bioavailable_g_inr"],
            "raw_json_data": raw_json,
            "authenticity_score": review_audit['authenticity_score'],
            "has_bot_reviews": review_audit['has_bot_reviews']
        }, on_conflict="sku_id").execute()

        if not vres.data: return False
        variant_id = vres.data[0]["id"]

        supabase.table("price_listings").upsert({
            "variant_id": variant_id, "source": source, "source_url": url,
            "price_inr": price, "in_stock": True,
            "seller_name": seller_name,
            "is_authorized_seller": is_authorized
        }, on_conflict="variant_id,source").execute()

        return True
    except Exception as e:
        logger.error(f"DB Upsert Failed [{brand} - {source}]: {str(e)}")
        return False

async def scrape_url(url: str, brand: str, source: str) -> int:
    count = 0
    try:
        page = await StealthyFetcher.async_fetch(url, headless=True, network_idle=True, timeout=25000)
        
        selectors = [
            "h2 a span", ".a-size-base-plus", ".a-size-medium", 
            "a.IRpwTa", "a.s1Q9rs", "a.WKTcLC",                 
            "[class*='productCard'] a", "[class*='Product'] a", "[class*='title'] a",
            "h3 a", "h2 a", "h1 a", ".style__pro-title___3G_-t"
        ]

        found = page.css(", ".join(selectors))

        for el in found:
            try:
                if hasattr(el, "get_all_text"):
                    title = el.get_all_text()
                else:
                    title = getattr(el, "text", "") or ""
                    if callable(title): title = title()
                
                if not title and hasattr(el, "attrib"):
                    title = el.attrib.get("title") or el.attrib.get("alt") or ""
            except Exception:
                title = ""
            title = title.strip()
            if not title: continue

            price = 0
            img = ""
            link = el.attrib.get("href") if hasattr(el, "attrib") else ""
            
            parent = el.parent
            for _ in range(5):
                if not parent: break
                
                price_els = parent.css(".a-price-whole, ._30jeq3, .Nx9bqj, [class*='price'], [class*='Price'], .price")
                if price_els and not price:
                    raw_price = price_els[0].get_all_text() if hasattr(price_els[0], "get_all_text") else getattr(price_els[0], "text", "")
                    digits = re.sub(r"[^\d.]", "", raw_price or "")
                    try: price = float(digits)
                    except: pass
                
                img_els = parent.css("img.s-image, img._396cs4, img.CXW8mj, img")
                if img_els and not img:
                    img = img_els[0].attrib.get("src") or img_els[0].attrib.get("data-src") or ""
                
                if not link:
                    link_els = parent.css("a")
                    if link_els: link = link_els[0].attrib.get("href") or ""

                parent = parent.parent

            card_desc = ""
            if parent and hasattr(parent, "get_all_text"):
                card_desc = parent.get_all_text().replace(title, "").strip()

            if link and not link.startswith("http"):
                from urllib.parse import urljoin
                link = urljoin(url, link)

            if price > 0:
                seller = extract_seller(parent)
                if upsert_product_variant(brand, title, price, img, link, source, card_desc, seller):
                    count += 1

    except Exception as e:
        logger.warning(f"Scrape Failed for {source} [{url}]: {str(e)}")
        # Optionally uncomment to see full tracebacks for debugging:
        # logger.debug(traceback.format_exc())
        
    return count

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
            d2c = await scrape_url(entry["d2c"], brand, "D2C")
            logger.info(f"  > D2C [{brand}]: Found {d2c} valid products")
        
        # 2. HealthKart
        hk = await scrape_url(f"https://www.healthkart.com/{entry['hk']}/whey-protein?bss=1", brand, "HealthKart")
        logger.info(f"  > HealthKart [{brand}]: Found {hk} valid products")

        # 3. All other platforms
        query = f"{brand} protein".replace(" ", "+")
        for platform_name, template in SEARCH_PLATFORMS.items():
            url = template.format(query=query)
            # Add a bit of jitter delay to avoid blasting connections too concurrently
            await asyncio.sleep(1.5)
            count = await scrape_url(url, brand, platform_name)
            if count > 0:
                logger.info(f"  > {platform_name} [{brand}]: Found {count} valid products")

        logger.info("-" * 40)
        
    logger.info("Scraping cycle complete.")

if __name__ == "__main__":
    asyncio.run(main())

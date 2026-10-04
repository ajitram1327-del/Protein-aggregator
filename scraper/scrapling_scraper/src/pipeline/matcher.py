import re
import json
from rapidfuzz import process, fuzz
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

from src.pipeline.normalizer import VariantNormalizer

def extract_weight_grams(text):
    return VariantNormalizer.parse_weight(text)
    if not text: return None
    kg_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilo)', text, re.IGNORECASE)
    if kg_match: return float(kg_match.group(1)) * 1000
    g_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g|gm|grams?)', text, re.IGNORECASE)
    if g_match: return float(g_match.group(1))
    lbs_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lbs|lb)', text, re.IGNORECASE)
    if lbs_match:
        lbs_val = float(lbs_match.group(1))
        if lbs_val == 2.2: return 1000.0
        if lbs_val == 4.4: return 2000.0
        return round(lbs_val * 453.592)
    return None

class VariantMatcher:
    _master_catalog = None

    @classmethod
    def load_master_catalog(cls):
        print("Downloading Master Catalog from Supabase...")
        if not supabase: return []
        try:
            res = supabase.table("variants").select("id, flavor, weight_grams, products(brand, base_name)").execute()
            catalog = []
            for row in res.data:
                brand = row['products']['brand']
                base = row['products']['base_name']
                flavor = row['flavor']
                weight = row['weight_grams']
                search_string = f"{brand} {base} {flavor} {weight}g"
                catalog.append({
                    "id": row['id'], 
                    "search_string": search_string,
                    "brand": brand,
                    "weight_grams": weight
                })
            cls._master_catalog = catalog
        except Exception as e:
            print(f"[ERROR] Could not load master catalog: {e}")
            cls._master_catalog = []
        return cls._master_catalog

    @classmethod
    def match_variant(cls, marketplace_title):
        if cls._master_catalog is None:
            cls.load_master_catalog()
            
        if not marketplace_title or not cls._master_catalog: return None
        title_lower = marketplace_title.lower()
        title_weight = extract_weight_grams(title_lower)
        
        BANNED_KEYWORDS = {"shaker", "funnel", "bottle", "ebook", "tshirt", "t-shirt", "pancake", "muesli", "oats", "test", "cookie", "bar"}
        BUNDLE_KEYWORDS = {"+", "combo", "pack of", "free"}
        
        if any(banned in title_lower for banned in BANNED_KEYWORDS):
            return None
        if any(bundle in title_lower for bundle in BUNDLE_KEYWORDS):
            return None
        
        candidates = []
        for item in cls._master_catalog:
            brand_lower = item['brand'].lower()
            if brand_lower not in title_lower and not any(part in title_lower for part in brand_lower.split()):
                continue
            if title_weight and item['weight_grams']:
                margin = item['weight_grams'] * 0.05
                if not (item['weight_grams'] - margin <= title_weight <= item['weight_grams'] + margin):
                    continue
            candidates.append(item)
            
        if not candidates: return None
            
        choices = [v["search_string"] for v in candidates]
        match = process.extractOne(marketplace_title, choices, scorer=fuzz.token_set_ratio)
        
        if match:
            best_string, score, index = match
            if score >= 75: return candidates[index]
        return None

def insert_unmatched_product(brand, title, price, url, source):
    if not supabase: return None
    try:
        supabase.table("unmatched_products").insert({
            "scraped_brand": brand,
            "scraped_title": title,
            "scraped_price_inr": float(price),
            "url": url,
            "platform_guess": source
        }).execute()
        return True
    except Exception as e:
        print(f"[ERROR] Could not insert into unmatched_products: {e}")
        return False

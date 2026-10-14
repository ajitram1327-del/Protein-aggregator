import re
import os
import sys
from typing import Dict, Any, Optional, List
from rapidfuzz import fuzz
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.pipeline.normalizer import VariantNormalizer

class MasterCatalogMatcher:
    """
    Enforces strict formulation category locks and weight bounds (+-3%)
    before allowing fuzzy Levenshtein confidence matching.
    Prevents category contamination (e.g., Whey Isolate vs Whey Concentrate).
    """

    FORMULATION_KEYWORDS = {
        "whey_isolate": ["isolate", "isopro", "iso-whey", "100% isolate", "iso zero", "iso 100", "iso-100", "hydrolyzed isolate"],
        "whey_concentrate": ["concentrate", "raw whey", "100% whey", "whey standard", "gold standard whey"],
        "casein": ["casein", "micellar casein", "night protein", "bedtime protein"],
        "plant": ["plant", "pea protein", "soy protein", "vegan protein", "brown rice protein", "organic plant"],
        "mass_gainer": ["mass gainer", "weight gainer", "super gainer", "serious mass", "mega gainer", "muscle juice"],
        "creatine": ["creatine", "creapure", "micronized creatine", "creatine monohydrate"]
    }

    _master_catalog: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def detect_category(cls, title: str) -> str:
        title_lower = title.lower()
        for cat, keywords in cls.FORMULATION_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", title_lower) for kw in keywords):
                return cat
        return "whey_blend"

    @classmethod
    def load_master_catalog(cls) -> List[Dict[str, Any]]:
        if not supabase: return []
        try:
            res = supabase.table("variants").select("id, flavor, weight_grams, sku_id, products(id, brand, base_name, category_silo)").execute()
            catalog = []
            for row in (res.data or []):
                p = row.get("products") or {}
                brand = p.get("brand", "")
                base = p.get("base_name", "")
                flavor = row.get("flavor", "")
                weight = row.get("weight_grams", 1000)
                category = cls.detect_category(base)
                search_string = f"{brand} {base} {flavor} {weight}g"
                catalog.append({
                    "id": row["id"],
                    "product_id": p.get("id"),
                    "brand": brand,
                    "product_name": base,
                    "category": category,
                    "flavor": flavor,
                    "weight_grams": weight,
                    "search_string": search_string
                })
            cls._master_catalog = catalog
        except Exception as e:
            print(f"[MasterCatalogMatcher] Could not load master catalog: {e}")
            cls._master_catalog = []
        return cls._master_catalog

    @classmethod
    def match_variant(
        cls, 
        scraped_title: str, 
        scraped_weight_g: int,
        brand_hint: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Stage 1: Hard Enums (Zero tolerance for category/weight drift)
        Stage 2: Levenshtein Confidence (Token Set Ratio >= 80)
        """
        if cls._master_catalog is None:
            cls.load_master_catalog()

        if not scraped_title or not cls._master_catalog:
            return None

        title_lower = scraped_title.lower()
        scraped_category = cls.detect_category(scraped_title)

        candidates = []
        for item in cls._master_catalog:
            # 1. Brand Gate
            item_brand_lower = item["brand"].lower()
            if brand_hint:
                if brand_hint.lower() not in item_brand_lower and item_brand_lower not in brand_hint.lower():
                    continue
            else:
                if item_brand_lower not in title_lower and not any(part in title_lower for part in item_brand_lower.split()):
                    continue

            # 2. Hard Gate: Category Formulation Lock
            if item["category"] != scraped_category:
                continue

            # 3. Hard Gate: Weight within +-3% bound
            expected_weight = item["weight_grams"]
            if expected_weight and scraped_weight_g:
                margin = max(30, expected_weight * 0.03) # 3% or 30g
                if abs(scraped_weight_g - expected_weight) > margin:
                    continue

            candidates.append(item)

        if not candidates:
            return None

        # Stage 2: Token Set Ratio Confidence
        choices = [c["search_string"] for c in candidates]
        from rapidfuzz import process
        match = process.extractOne(scraped_title, choices, scorer=fuzz.token_set_ratio)
        if match:
            best_string, score, index = match
            if score >= 80:
                return candidates[index]

        return None

def insert_quarantine_product(
    platform: str, 
    raw_title: str, 
    raw_price: float, 
    raw_url: str, 
    detected_brand: str = "", 
    detected_weight_g: int = 0,
    failure_reason: str = "UNRESOLVABLE_SPECIFICATIONS"
) -> bool:
    if not supabase: return False
    try:
        supabase.table("unmatched_staging_queue").insert({
            "platform_name": platform.lower()[:50],
            "raw_title": raw_title[:500],
            "raw_price": float(raw_price) if raw_price else None,
            "raw_url": raw_url,
            "detected_brand": detected_brand,
            "detected_weight_g": detected_weight_g if detected_weight_g > 0 else None,
            "failure_reason": failure_reason
        }).execute()
        return True
    except Exception as e:
        # Fallback to legacy unmatched_products if unmatched_staging_queue table doesn't exist yet
        try:
            supabase.table("unmatched_products").insert({
                "scraped_brand": detected_brand,
                "scraped_title": raw_title,
                "scraped_price_inr": float(raw_price) if raw_price else None,
                "url": raw_url,
                "platform_guess": platform
            }).execute()
            return True
        except Exception:
            return False

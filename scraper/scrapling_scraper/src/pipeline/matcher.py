import re
import os
import sys
import json
from typing import Dict, Any, Optional, List, Tuple
from rapidfuzz import fuzz, process
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.pipeline.normalizer import VariantNormalizer, CanonicalProductNormalizer, CanonicalProductInfo


class MasterCatalogMatcher:
    """
    ProteIndex Multi-Tier Entity Matching Cascade
    Tier 0: Sticky Hash / Exact URL lookup
    Tier 1: Canonical Rules & Line Taxonomy Match (Deterministic 100% confidence)
    Tier 2: Levenshtein Token-Set Ratio with Strict Formulation & Weight Gates (>=85% score)
    Tier 3: LLM Disambiguator (Groq / Gemini) for ambiguous candidate sets (65-84% score)
    Tier 4: Quarantine Fallback (Never creates duplicate products blindly)
    """

    _master_catalog: Optional[List[Dict[str, Any]]] = None
    _url_cache: Dict[str, str] = {} # url -> variant_id

    @classmethod
    def load_master_catalog(cls) -> List[Dict[str, Any]]:
        if not supabase: 
            return []
        try:
            res = supabase.table("variants").select(
                "id, flavor, weight_grams, sku_id, lowest_price_inr, "
                "products(id, brand, base_name, category_silo, protein_source)"
            ).execute()
            
            catalog = []
            for row in (res.data or []):
                p = row.get("products") or {}
                raw_brand = p.get("brand", "")
                base = p.get("base_name", "")
                flavor = row.get("flavor", "unflavored")
                weight = row.get("weight_grams", 1000)
                
                # Canonicalize using normalized taxonomy
                info = CanonicalProductNormalizer.normalize_product(base, raw_brand)
                canon_flavor = VariantNormalizer.parse_flavor(flavor)
                
                search_string = f"{info.canonical_brand} {info.canonical_line} {canon_flavor} {weight}g"
                catalog.append({
                    "id": row["id"],
                    "product_id": p.get("id"),
                    "raw_brand": raw_brand,
                    "canonical_brand": info.canonical_brand.lower(),
                    "canonical_line": info.canonical_line.lower(),
                    "canonical_full_name": info.canonical_full_name,
                    "category_silo": (p.get("category_silo") or info.category_silo).lower(),
                    "formulation": (p.get("protein_source") or info.formulation).lower(),
                    "flavor": canon_flavor.lower(),
                    "weight_grams": int(weight) if weight else 1000,
                    "search_string": search_string.lower(),
                    "raw_base_name": base
                })
            cls._master_catalog = catalog

            # Also preload active price listing URLs for Tier 0 sticky matching
            try:
                pl_res = supabase.table("price_listings").select("listing_url, source_url, variant_id").execute()
                for pl in (pl_res.data or []):
                    u = pl.get("listing_url") or pl.get("source_url")
                    vid = pl.get("variant_id")
                    if u and vid:
                        cls._url_cache[u] = vid
            except Exception:
                pass

        except Exception as e:
            print(f"[MasterCatalogMatcher] Could not load master catalog: {e}")
            cls._master_catalog = []
        return cls._master_catalog

    @classmethod
    def match_variant(
        cls, 
        scraped_title: str, 
        scraped_weight_g: int,
        brand_hint: str = "",
        raw_url: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Executes the 4-tier matching cascade.
        Returns matched dictionary with { 'id', 'product_id', 'method', 'confidence', ... } or None.
        """
        if cls._master_catalog is None:
            cls.load_master_catalog()

        if not scraped_title or not cls._master_catalog:
            return None

        # -------------------------------------------------------------
        # TIER 0: STICKY MATCH (Exact URL already recognized in system)
        # -------------------------------------------------------------
        if raw_url and raw_url in cls._url_cache:
            target_vid = cls._url_cache[raw_url]
            for item in cls._master_catalog:
                if item["id"] == target_vid:
                    res = dict(item)
                    res["match_method"] = "sticky"
                    res["confidence"] = 1.0
                    return res

        # -------------------------------------------------------------
        # PRE-PROCESSING & COMBO SANITIZATION
        # -------------------------------------------------------------
        norm_info = CanonicalProductNormalizer.normalize_product(scraped_title, brand_hint)
        if norm_info.is_bundle:
            return None

        scraped_flavor = VariantNormalizer.parse_flavor(scraped_title).lower()
        canon_brand = norm_info.canonical_brand.lower()
        canon_line = norm_info.canonical_line.lower()
        weight_g = max(1, int(scraped_weight_g))

        # -------------------------------------------------------------
        # TIER 1: DETERMINISTIC RULES & ALIAS MATCH (100% Confidence)
        # -------------------------------------------------------------
        for item in cls._master_catalog:
            # 1. Brand match
            if item["canonical_brand"] != canon_brand:
                continue

            # 2. Product line exact equality
            if item["canonical_line"] == canon_line:
                # 3. Weight match within 3% tolerance
                expected_w = item["weight_grams"]
                margin = max(30, expected_w * 0.03)
                if abs(weight_g - expected_w) <= margin:
                    # 4. Flavor match (or unflavored default compatibility)
                    if item["flavor"] == scraped_flavor or (item["flavor"] == "unflavored" and scraped_flavor == "unflavored"):
                        res = dict(item)
                        res["match_method"] = "alias_rules"
                        res["confidence"] = 1.0
                        return res

        # -------------------------------------------------------------
        # TIER 2: LEVENSHTEIN TOKEN SET RATIO WITH HARD GATES
        # -------------------------------------------------------------
        candidates = []
        for item in cls._master_catalog:
            # Brand Gate: Must be same canonical brand
            if item["canonical_brand"] != canon_brand:
                continue

            # Formulation Gate: Category silo must match
            if item["category_silo"] != norm_info.category_silo.lower():
                continue

            # Weight Gate: +-3%
            expected_w = item["weight_grams"]
            margin = max(30, expected_w * 0.03)
            if abs(weight_g - expected_w) > margin:
                continue

            # Flavor Gate: If flavor is known and not unflavored, must match
            if scraped_flavor != "unflavored" and item["flavor"] != "unflavored" and item["flavor"] != scraped_flavor:
                continue

            candidates.append(item)

        if not candidates:
            return None

        # Score candidate search strings against scraped title
        choices = [c["search_string"] for c in candidates]
        match = process.extractOne(scraped_title.lower(), choices, scorer=fuzz.token_set_ratio)
        
        if match:
            best_string, score, index = match
            if score >= 85:
                res = dict(candidates[index])
                res["match_method"] = "pg_trgm"
                res["confidence"] = round(float(score) / 100.0, 2)
                return res

            # -------------------------------------------------------------
            # TIER 3: LLM DISAMBIGUATOR (Groq / Gemini) FOR 65% - 84% SCORE
            # -------------------------------------------------------------
            if 65 <= score < 85 and len(candidates) <= 5:
                llm_matched = cls._query_llm_disambiguator(scraped_title, weight_g, scraped_flavor, candidates[:4])
                if llm_matched:
                    llm_matched["match_method"] = "llm_groq"
                    llm_matched["confidence"] = 0.90
                    return llm_matched

        # Tier 4: Uncertain -> Quarantine (Do not auto-generate a new product)
        return None

    @classmethod
    def _query_llm_disambiguator(
        cls, 
        raw_title: str, 
        weight_g: int, 
        flavor: str, 
        candidates: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Invokes Groq / Gemini LLM to cleanly disambiguate closely competing variants."""
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            return None

        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)

            candidate_prompts = []
            for i, c in enumerate(candidates):
                candidate_prompts.append(
                    f"Option {i + 1}: ID={c['id']}, Brand={c['canonical_brand']}, "
                    f"Product={c['canonical_full_name']}, Flavor={c['flavor']}, Weight={c['weight_grams']}g"
                )

            prompt = (
                f"You are a strict product matching engine. A customer wants to buy the product described as:\n"
                f"'{raw_title}' (Weight: {weight_g}g, Flavor: {flavor})\n\n"
                f"Select the single correct candidate from these options:\n"
                + "\n".join(candidate_prompts) +
                f"\n\nIf NONE of these options represent the EXACT same core supplement product formulation, reply with 'NONE'.\n"
                f"If an option matches, reply ONLY with the integer option number (e.g. '1', '2', etc.)."
            )

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0
            )

            reply = response.choices[0].message.content.strip()
            digits = re.findall(r"\b([1-9])\b", reply)
            if digits:
                chosen_idx = int(digits[0]) - 1
                if 0 <= chosen_idx < len(candidates):
                    return candidates[chosen_idx]
        except Exception:
            pass

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
    """Safely logs an unresolvable or ambiguous listing to the staging review buffer."""
    if not supabase: 
        return False
    try:
        supabase.table("staging_quarantine").insert({
            "platform_name": platform.lower()[:50],
            "raw_title": raw_title[:500],
            "raw_price": float(raw_price) if raw_price else None,
            "raw_url": raw_url,
            "detected_brand": detected_brand,
            "detected_weight_g": detected_weight_g if detected_weight_g > 0 else None,
            "failure_reason": failure_reason
        }).execute()
        return True
    except Exception:
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

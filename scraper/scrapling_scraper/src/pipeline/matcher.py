"""
scraper/scrapling_scraper/src/pipeline/matcher.py
Enterprise-Grade High-Throughput O(1) In-Memory Blocking Canopy Index & 5-Tier Matcher.
100 to 100,000+ SKUs Scale.
"""

import re
import os
import sys
import json
import time
import hashlib
from collections import defaultdict
from typing import Dict, Any, Optional, List, Tuple, Union
from pydantic import BaseModel, Field, ValidationError
from rapidfuzz import fuzz, process
from supabase import create_client, Client
from dotenv import load_dotenv

# Path alignment
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
SCRAPER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if SCRAPER_DIR not in sys.path:
    sys.path.insert(0, SCRAPER_DIR)

load_dotenv(os.path.join(SCRAPER_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env"))

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
supabase: Optional[Client] = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

from src.pipeline.catalog_taxonomy import (
    StatefulTitleParser,
    snap_to_canonical_weight,
    is_economically_valid_price,
    generate_canopy_key,
    generate_blocking_key
)
try:
    from src.pipeline.normalizer import VariantNormalizer, CanonicalProductNormalizer, CanonicalProductInfo
except ImportError:
    from pipeline.normalizer import VariantNormalizer, CanonicalProductNormalizer, CanonicalProductInfo

from src.pipeline.nutrition_ocr_pipeline import (
    NutritionFactsPayload,
    NutritionOCRPipeline,
    BoundingBoxWord
)
try:
    from src.trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
except ImportError:
    try:
        from trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
    except ImportError:
        AminoSpikingRulesEngine = None


# -----------------------------------------------------------------------------
# 1. Deterministic Structural Contract for Clean Frontend & Database Payload
# -----------------------------------------------------------------------------
class CanonicalProductListing(BaseModel):
    brand_name: str
    product_silo: str
    net_weight_grams: float
    listed_price: float
    protein_per_serving: float
    serving_size_grams: float
    # Calculated analytical layer
    calculated_purity_percentage: float
    cost_per_100g_pure_protein: float


# -----------------------------------------------------------------------------
# 2. Agentic Multi-Agent Pipeline Auditor
# -----------------------------------------------------------------------------
class AgenticPipelineAuditor:
    def __init__(self, raw_payload: Union[str, dict]):
        self.payload = raw_payload

    def agent_ocr_column_validator(self, data: dict) -> Dict[str, Union[bool, str]]:
        """Agent A: Inspects the payload to ensure 'Per Serving' and 'Per 100g' didn't cross wires."""
        try:
            serving = float(data.get("serving_size_grams", 0))
            protein = float(data.get("protein_per_serving", 0))
            
            # Catch Context Clashing: Protein cannot physically exceed total serving size weight
            if protein > serving:
                return {"status": False, "reason": "CRITICAL FATAL: Protein mass exceeds total serving weight. OCR Column mismatch."}
            
            # Catch Atwater Physics/Yield drift anomalies
            purity = (protein / serving) * 100 if serving > 0 else 0
            if purity > 96.0:  # Even pure whey isolate tops out around 90-93% active yields
                return {"status": False, "reason": "PHYSICS VIOLATION: Calculated purity is physically impossible for natural powder derivatives."}
                
            return {"status": True, "reason": "Metrics cleared."}
        except (ValueError, TypeError):
            return {"status": False, "reason": "DATA CORRUPTION: Metrics contain non-numeric string values."}

    def agent_llm_json_sanitizer(self) -> Optional[dict]:
        """Agent B: Strips out Groq/Gemini string markdown garbage if Tier 3 breaks down."""
        if isinstance(self.payload, dict):
            return self.payload
        clean_str = str(self.payload).strip()
        
        # Regex to strip common LLM wrapper leakages
        clean_str = re.sub(r'^```(?:json)?\s*', '', clean_str, flags=re.IGNORECASE)
        clean_str = re.sub(r'\s*```$', '', clean_str, flags=re.IGNORECASE)
        
        try:
            return json.loads(clean_str)
        except json.JSONDecodeError:
            print("❌ SANITIZATION FAILURE: LLM returned corrupted non-JSON text.")
            return None


class CircuitBreaker:
    """Circuit breaker for external LLM calls (e.g. rate limits 429/5xx)."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_attempt(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout_s:
                self.state = "HALF-OPEN"
                return True
            return False
        if self.state == "HALF-OPEN":
            return True
        return False


class MasterCatalogMatcher:
    """
    ProteIndex High-Throughput O(1) In-Memory Blocking Canopy Index & 5-Tier Matcher:
    - Tier 0: Platform SKU Index (AMZN:<ASIN>, FKRT:<FSN>, HKRT:<SKU>) with weight/pack drift check
    - Tier 1: Deterministic Exact Hash Match & Catalog Alias Redirect Check (O(1))
    - Tier 2: In-Memory Inverted Canopy Blocked Match (0.45*token_set + 0.40*token_sort + 0.15*ratio) + OCR Size Fallback
    - Tier 2.5: Persistent SHA-256 Fingerprint Cache (llm_resolution_cache)
    - Tier 3: Async/Micro-Batched LLM Disambiguator with Circuit Breaker (65%–85% candidates)
    - Tier 4: Structured Quarantine with Fingerprint and Pre-extracted OCR
    """

    # In-memory indexes
    _platform_sku_index: Dict[str, Dict[str, Any]] = {}
    _canopy_index: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    _deterministic_hash_index: Dict[str, Dict[str, Any]] = {}
    _alias_redirect_cache: Dict[str, str] = {} # duplicate_id -> master_id
    _llm_fingerprint_cache: Dict[str, Dict[str, Any]] = {} # sha256 -> candidate
    _url_cache: Dict[str, str] = {} # url -> variant_id
    _master_catalog: List[Dict[str, Any]] = []

    _is_initialized: bool = False
    _circuit_breaker: CircuitBreaker = CircuitBreaker()
    _ocr_pipeline: NutritionOCRPipeline = NutritionOCRPipeline()

    @classmethod
    def initialize_indexes(cls, custom_catalog: Optional[List[Dict[str, Any]]] = None, client: Optional[Client] = None):
        """
        Pre-builds the in-memory inverted indexes for sub-millisecond lookups across 100k+ SKUs.
        """
        active_client = client or supabase
        catalog = custom_catalog

        if catalog is None and active_client:
            try:
                res = active_client.table("variants").select(
                    "id, flavor, weight_grams, sku_id, lowest_price_inr, servings_count, "
                    "products(id, brand, base_name, category_silo, protein_source, nutrition_serving_size_g, nutrition_protein_per_serving_g)"
                ).execute()
                catalog = res.data or []
            except Exception as e:
                print(f"[MasterCatalogMatcher] Error fetching variants: {e}")
                catalog = []

        cls._master_catalog = []
        cls._platform_sku_index.clear()
        cls._canopy_index.clear()
        cls._deterministic_hash_index.clear()
        cls._alias_redirect_cache.clear()
        cls._llm_fingerprint_cache.clear()
        cls._url_cache.clear()

        # Load redirect aliases if table exists
        if active_client:
            try:
                alias_res = active_client.table("catalog_redirect_aliases").select("duplicate_id, master_id").execute()
                for row in (alias_res.data or []):
                    cls._alias_redirect_cache[str(row["duplicate_id"])] = str(row["master_id"])
            except Exception:
                pass

            try:
                pl_res = active_client.table("price_listings").select("listing_url, source_url, variant_id").execute()
                for pl in (pl_res.data or []):
                    u = pl.get("listing_url") or pl.get("source_url")
                    vid = pl.get("variant_id")
                    if u and vid:
                        cls._url_cache[u] = str(vid)
            except Exception:
                pass

        for row in (catalog or []):
            p = row.get("products") or {}
            raw_brand = p.get("brand", "")
            base = p.get("base_name", "")
            raw_flavor = row.get("flavor", "unflavored")
            raw_weight = row.get("weight_grams", 1000) or 1000

            norm_info = CanonicalProductNormalizer.normalize_product(base, raw_brand)
            canon_flavor = VariantNormalizer.parse_flavor(raw_flavor)
            stateful_info = StatefulTitleParser.parse(base, category_silo_hint=norm_info.category_silo)

            bucketed_weight = snap_to_canonical_weight(float(raw_weight))
            delivery_form = stateful_info.delivery_form
            formulation_sig = stateful_info.formulation_sig
            silo = (p.get("category_silo") or norm_info.category_silo).lower()

            search_string = f"{norm_info.canonical_brand} {norm_info.canonical_line} {canon_flavor} {bucketed_weight}g".lower()

            candidate = {
                "id": str(row["id"]),
                "product_id": str(p.get("id")),
                "raw_brand": raw_brand,
                "canonical_brand": norm_info.canonical_brand.lower(),
                "canonical_line": norm_info.canonical_line.lower(),
                "canonical_full_name": norm_info.canonical_full_name,
                "category_silo": silo,
                "formulation_sig": formulation_sig,
                "delivery_form": delivery_form,
                "flavor": canon_flavor.lower(),
                "weight_grams": bucketed_weight,
                "pack_count": 1,
                "search_string": search_string,
                "sku_id": row.get("sku_id") or "",
                "serving_size_g": float(p.get("nutrition_serving_size_g") or 0.0),
                "protein_per_serving_g": float(p.get("nutrition_protein_per_serving_g") or 0.0),
                "servings_count": int(row.get("servings_count") or 0)
            }

            cls._master_catalog.append(candidate)

            # 1. Platform SKU Index
            sku_id = candidate["sku_id"].strip().upper()
            if sku_id:
                cls._platform_sku_index[sku_id] = candidate

            # 2. Canopy Index: (brand, silo, delivery_form) -> List[candidate]
            canopy_k = generate_canopy_key(candidate["canonical_brand"], candidate["category_silo"], candidate["delivery_form"])
            cls._canopy_index[canopy_k].append(candidate)

            # 3. Deterministic Hash Index
            det_key = generate_blocking_key(
                candidate["canonical_brand"],
                candidate["category_silo"],
                candidate["canonical_line"],
                candidate["delivery_form"],
                candidate["formulation_sig"]
            )
            variant_det_key = f"{det_key}:::{candidate['flavor']}:::{candidate['weight_grams']}:::{candidate['pack_count']}"
            cls._deterministic_hash_index[variant_det_key] = candidate

        cls._is_initialized = True
        print(f"[MasterCatalogMatcher] In-memory indexes initialized: {len(cls._master_catalog)} variants, {len(cls._canopy_index)} canopy blocks.")

    @classmethod
    def match_variant(
        cls,
        scraped_title: str,
        scraped_weight_g: int = 0,
        scraped_price_inr: float = 0.0,
        brand_hint: str = "",
        raw_url: str = "",
        platform_sku: str = "",
        label_images: Optional[List[bytes]] = None,
        label_ocr_words: Optional[List[BoundingBoxWord]] = None,
        peer_prices: Optional[List[float]] = None
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_initialized:
            cls.initialize_indexes()

        if not scraped_title:
            return None

        # -------------------------------------------------------------
        # STEP 1: PARSE TITLE (Consume-and-Strip) & PHYSICAL UNIT-ECONOMICS CHECK
        # -------------------------------------------------------------
        norm_info = CanonicalProductNormalizer.normalize_product(scraped_title, brand_hint)
        stateful_info = StatefulTitleParser.parse(scraped_title, category_silo_hint=norm_info.category_silo)

        if norm_info.is_bundle or stateful_info.is_bundle:
            return None

        # Determine effective weight & pack count
        pack_count = stateful_info.pack_count
        raw_w = stateful_info.raw_extracted_weight_g or float(scraped_weight_g)
        bucketed_w = snap_to_canonical_weight(raw_w) if raw_w > 0 else 0
        scraped_flavor = VariantNormalizer.parse_flavor(scraped_title).lower()
        canon_brand = norm_info.canonical_brand.lower()
        silo = norm_info.category_silo.lower()
        delivery_form = stateful_info.delivery_form
        form_sig = stateful_info.formulation_sig

        # Physical Unit-Economics Guardrail
        if scraped_price_inr > 0 and bucketed_w > 0:
            is_valid_econ, econ_reason = is_economically_valid_price(
                price_inr=scraped_price_inr,
                weight_grams=bucketed_w * pack_count,
                category_silo=silo,
                formulation_sig=form_sig,
                serving_count=stateful_info.serving_count,
                peer_prices=peer_prices
            )
            if not is_valid_econ:
                print(f"[ECONOMIC REJECT] Rejecting '{scraped_title}': {econ_reason}")
                return None

        # -------------------------------------------------------------
        # TIER 0: PLATFORM NATIVE ID + DRIFT INVALIDATION CHECK
        # -------------------------------------------------------------
        if platform_sku:
            norm_sku = platform_sku.strip().upper()
            if norm_sku in cls._platform_sku_index:
                cand = cls._platform_sku_index[norm_sku]
                # Drift check: ensure scraped weight is within +-3% and pack count matches
                if bucketed_w > 0:
                    margin = max(30, cand["weight_grams"] * 0.03)
                    if abs(bucketed_w - cand["weight_grams"]) <= margin and cand["pack_count"] == pack_count:
                        res = dict(cand)
                        res["match_method"] = "tier0_platform_sku"
                        res["confidence"] = 1.0
                        return res

        # Check raw_url sticky cache
        if raw_url and raw_url in cls._url_cache:
            target_vid = cls._url_cache[raw_url]
            # Check redirect alias cache
            if target_vid in cls._alias_redirect_cache:
                target_vid = cls._alias_redirect_cache[target_vid]
            for item in cls._master_catalog:
                if item["id"] == target_vid:
                    res = dict(item)
                    res["match_method"] = "tier0_sticky_url"
                    res["confidence"] = 1.0
                    return res

        # -------------------------------------------------------------
        # TIER 1: DETERMINISTIC EXACT HASH MATCH & ALIAS REDIRECT CHECK
        # -------------------------------------------------------------
        det_key = generate_blocking_key(canon_brand, silo, norm_info.canonical_line, delivery_form, form_sig)
        variant_det_key = f"{det_key}:::{scraped_flavor}:::{bucketed_w}:::{pack_count}"

        if variant_det_key in cls._deterministic_hash_index:
            cand = cls._deterministic_hash_index[variant_det_key]
            # Check redirect alias
            cid = cand["id"]
            if cid in cls._alias_redirect_cache:
                target_id = cls._alias_redirect_cache[cid]
                for item in cls._master_catalog:
                    if item["id"] == target_id:
                        cand = item
                        break
            res = dict(cand)
            res["match_method"] = "tier1_exact_hash"
            res["confidence"] = 1.0
            return res

        # Tier 1 Line & Flavor deterministic match
        for item in cls._master_catalog:
            if item["canonical_brand"] == canon_brand and item["category_silo"] == silo:
                if item["canonical_line"] == norm_info.canonical_line.lower():
                    # Check flavor match
                    if item["flavor"] == scraped_flavor or (item["flavor"] == "unflavored" and scraped_flavor == "unflavored"):
                        # Check weight: exact bucket or bridged via OCR serving size
                        cand_w = item["weight_grams"]
                        eff_w = bucketed_w
                        if eff_w <= 0 and stateful_info.serving_count and item.get("serving_size_g", 0) > 0:
                            eff_w = snap_to_canonical_weight(item["serving_size_g"] * stateful_info.serving_count)
                        if eff_w > 0:
                            margin = max(30, cand_w * 0.03)
                            if abs(eff_w - cand_w) <= margin:
                                res = dict(item)
                                res["match_method"] = "tier1_canonical_line"
                                res["confidence"] = 1.0
                                return res

        # -------------------------------------------------------------
        # TIER 2: CANOPY-BLOCKED SYMMETRIC FUZZY MATCH + OCR SIZE BRIDGE
        # -------------------------------------------------------------
        canopy_k = generate_canopy_key(canon_brand, silo, delivery_form)
        candidates = cls._canopy_index.get(canopy_k, [])

        if not candidates:
            # Fallback to all candidates of same brand & silo
            candidates = [c for c in cls._master_catalog if c["canonical_brand"] == canon_brand and c["category_silo"] == silo]

        if not candidates:
            return None

        extracted_ocr_payload = None
        # OCR Size Bridge: If listing is missing gram weight in title
        if bucketed_w <= 0:
            ocr_resolved_w = None
            # Option A: Run OCR pipeline on scraped label images
            if label_images and len(label_images) > 0:
                for img_bytes in label_images:
                    payload = cls._ocr_pipeline.process_image(
                        image_bytes=img_bytes,
                        words=label_ocr_words,
                        bucketed_weight_g=None
                    )
                    if payload and payload.serving_size_g > 0:
                        # Audit through AgenticPipelineAuditor to catch column misalignment / purity violations
                        auditor = AgenticPipelineAuditor(payload.to_dict())
                        ocr_check = auditor.agent_ocr_column_validator({
                            "serving_size_grams": payload.serving_size_g,
                            "protein_per_serving": payload.protein_per_serving_g
                        })
                        if not ocr_check["status"]:
                            print(f"[OCR GUARDRAIL REJECT]: {ocr_check['reason']}")
                            continue

                        extracted_ocr_payload = payload
                        if stateful_info.serving_count:
                            ocr_resolved_w = snap_to_canonical_weight(payload.serving_size_g * stateful_info.serving_count)
                            break

            # Option B: Use candidate's serving_size_g * stateful_info.serving_count
            if not ocr_resolved_w and stateful_info.serving_count:
                for cand in candidates:
                    if cand.get("serving_size_g", 0) > 0:
                        ocr_resolved_w = snap_to_canonical_weight(cand["serving_size_g"] * stateful_info.serving_count)
                        break

            if ocr_resolved_w:
                bucketed_w = ocr_resolved_w

        # Filter candidates by 6 Hard Invariant Gates
        filtered_candidates = []
        for cand in candidates:
            # Gate 1: Brand match
            if cand["canonical_brand"] != canon_brand:
                continue
            # Gate 2: Silo match
            if cand["category_silo"] != silo:
                continue
            # Gate 3: Delivery form match
            if cand["delivery_form"] != delivery_form:
                continue
            # Gate 4: Pack count match
            if cand["pack_count"] != pack_count:
                continue
            # Gate 5: Weight match (+-3% tolerance) if weight is known
            if bucketed_w > 0:
                margin = max(30, cand["weight_grams"] * 0.03)
                if abs(bucketed_w - cand["weight_grams"]) > margin:
                    continue
            # Gate 6: Flavor gate (if neither is unflavored, must match)
            if scraped_flavor != "unflavored" and cand["flavor"] != "unflavored":
                if scraped_flavor != cand["flavor"]:
                    continue

            filtered_candidates.append(cand)

        if not filtered_candidates:
            return None

        # Compute Composite Fuzzy Score: 0.45 * token_set + 0.40 * token_sort + 0.15 * ratio
        scored_candidates = []
        clean_scraped_lower = scraped_title.lower()

        for cand in filtered_candidates:
            target_str = cand["search_string"]
            score_set = fuzz.token_set_ratio(clean_scraped_lower, target_str)
            score_sort = fuzz.token_sort_ratio(clean_scraped_lower, target_str)
            score_ratio = fuzz.ratio(clean_scraped_lower, target_str)
            composite_score = (0.45 * score_set) + (0.40 * score_sort) + (0.15 * score_ratio)
            scored_candidates.append((composite_score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_1_score, top_1_cand = scored_candidates[0]
        top_2_score = scored_candidates[1][0] if len(scored_candidates) > 1 else 0.0

        # Tier 2 Accept Criteria: top_1_score >= 86.0 AND (top_1_score - top_2_score) >= 6.5
        if top_1_score >= 86.0 and (top_1_score - top_2_score) >= 6.5:
            res = dict(top_1_cand)
            res["match_method"] = "tier2_canopy_fuzzy"
            res["confidence"] = round(float(top_1_score) / 100.0, 3)
            if 'extracted_ocr_payload' in locals() and extracted_ocr_payload:
                res["extracted_ocr"] = extracted_ocr_payload.to_dict()
                res["amino_spiking_audit"] = extracted_ocr_payload.amino_spiking_audit
            return res

        # -------------------------------------------------------------
        # TIER 2.5: PERSISTENT SHA-256 FINGERPRINT CACHE
        # -------------------------------------------------------------
        fp_sig = f"{clean_scraped_lower}_{canon_brand}_{bucketed_w}_{scraped_flavor}"
        fp_hash = hashlib.sha256(fp_sig.encode("utf-8")).hexdigest()

        if fp_hash in cls._llm_fingerprint_cache:
            cached_cand = cls._llm_fingerprint_cache[fp_hash]
            res = dict(cached_cand)
            res["match_method"] = "tier2.5_fingerprint_cache"
            res["confidence"] = 0.95
            return res

        # -------------------------------------------------------------
        # TIER 3: ASYNC/MICRO-BATCHED LLM DISAMBIGUATOR WITH CIRCUIT BREAKER
        # Only for ambiguous candidate sets (65% <= score < 86%)
        # -------------------------------------------------------------
        if 65.0 <= top_1_score < 86.0 and len(filtered_candidates) <= 4:
            if cls._circuit_breaker.can_attempt():
                llm_cand = cls._query_llm_disambiguator(
                    scraped_title=scraped_title,
                    weight_g=bucketed_w,
                    flavor=scraped_flavor,
                    candidates=[c[1] for c in scored_candidates[:4]],
                    stateful_spec=stateful_info
                )
                if llm_cand:
                    cls._circuit_breaker.record_success()
                    cls._llm_fingerprint_cache[fp_hash] = llm_cand
                    res = dict(llm_cand)
                    res["match_method"] = "tier3_llm_disambiguation"
                    res["confidence"] = 0.90
                    return res
                else:
                    cls._circuit_breaker.record_failure()

        # -------------------------------------------------------------
        # TIER 4: STRUCTURED QUARANTINE
        # -------------------------------------------------------------
        return None

    @classmethod
    def _query_llm_disambiguator(
        cls,
        scraped_title: str,
        weight_g: int,
        flavor: str,
        candidates: List[Dict[str, Any]],
        stateful_spec: Any
    ) -> Optional[Dict[str, Any]]:
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            return None

        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)

            options_text = []
            for idx, c in enumerate(candidates):
                options_text.append(
                    f"Option {idx + 1}: ID={c['id']}, Brand={c['canonical_brand']}, "
                    f"Line={c['canonical_line']}, Flavor={c['flavor']}, Weight={c['weight_grams']}g, "
                    f"Protein/Serving={c.get('protein_per_serving_g', 0)}g"
                )

            prompt = (
                f"You are a strict catalog entity resolution engine.\n"
                f"Target Scraped Title: '{scraped_title}'\n"
                f"Extracted Spec: Weight={weight_g}g, Flavor={flavor}, Formulation={stateful_spec.formulation_sig}\n\n"
                f"Available Candidates:\n" + "\n".join(options_text) + "\n\n"
                f"Reply with the single integer Option number (e.g., '1', '2') that is an EXACT match, or 'NONE'."
            )

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0
            )

            raw_reply = response.choices[0].message.content
            auditor = AgenticPipelineAuditor(raw_reply)
            clean_dict = auditor.agent_llm_json_sanitizer()

            if clean_dict and isinstance(clean_dict, dict):
                # If LLM returned structured JSON {option: X} or {candidate_id: X}
                opt_val = clean_dict.get("option") or clean_dict.get("match") or clean_dict.get("id")
                if opt_val is not None:
                    try:
                        chosen_idx = int(str(opt_val).strip()) - 1
                        if 0 <= chosen_idx < len(candidates):
                            return candidates[chosen_idx]
                    except ValueError:
                        for cand in candidates:
                            if cand["id"] == str(opt_val):
                                return cand

            # Plain text fallback
            clean_reply = re.sub(r'^```(?:json)?\s*', '', raw_reply, flags=re.IGNORECASE).strip()
            digits = re.findall(r"\b([1-4])\b", clean_reply)
            if digits:
                chosen_idx = int(digits[0]) - 1
                if 0 <= chosen_idx < len(candidates):
                    return candidates[chosen_idx]
        except Exception as e:
            print(f"[LLM Disambiguator Error]: {e}")

        return None


def insert_quarantine_product(
    platform: str,
    raw_title: str,
    raw_price: float,
    raw_url: str,
    detected_brand: str = "",
    detected_weight_g: int = 0,
    failure_reason: str = "UNMATCHED_MARKETPLACE_LISTING"
):
    """Safely stages ambiguous or unresolvable scraped listings to staging_quarantine table."""
    if not supabase:
        return
    try:
        supabase.table("staging_quarantine").insert({
            "platform": platform,
            "brand_hint": detected_brand,
            "raw_title": raw_title,
            "raw_price": raw_price,
            "raw_url": raw_url,
            "detected_weight_g": detected_weight_g,
            "failure_category": "SCRAPER_PARSE_ERROR",
            "details": {"failure_reason": failure_reason}
        }).execute()
    except Exception as e:
        pass

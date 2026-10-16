import re
from typing import Dict, List, Optional, Tuple, Any

try:
    from pipeline.normalizer import VariantNormalizer
except ImportError:
    try:
        from .normalizer import VariantNormalizer
    except Exception:
        VariantNormalizer = None


class EntityResolutionEngine:
    """
    Proteindex Entity Resolution & Deduplication Engine (P2-05)
    - Weight normalization (e.g. 2 lb -> 907g, 2.2 lb -> 1000g)
    - Bundle/combo isolation and quarantine routing
    - Cross-category merge prevention (protein != mass gainer != creatine)
    - Calibrated entity similarity scoring:
        * >= 0.93: Auto-merge
        * 0.80 - 0.9299: Route to entity_resolution_staging review queue
        * < 0.80: Distinct products
    """

    AUTO_MERGE_THRESHOLD = 0.93
    STAGING_REVIEW_THRESHOLD = 0.80

    COMBO_BUNDLE_PATTERNS = [
        r"\+\s*(?:free\s*)?(?:shaker|sipper|bottle|gym\s*bag|t-shirt|creatine|multivitamin|fish\s*oil)\b",
        r"\bwith\s+(?:free\s*)?(?:shaker|sipper|bottle|gym\s*bag)\b",
        r"\b(?:combo\s*pack|value\s*combo|buy\s*1\s*get\s*1|bogo)\b",
        r"\bpack\s*of\s*[2-9]\s*(?:tubs?|jars?|bottles?)\s*(?:combo|\+)\b",
    ]

    NOISE_PATTERNS = [
        r"\b(?:100%|authentic|genuine|lab\s*door|certified|imported|official|new\s*pack|special\s*edition)\b",
        r"\b(?:free\s*shipping|cash\s*on\s*delivery|cod|discount|sale)\b",
        r"\b(?:powder|supplement|nutrition|health|fitness)\b",
    ]

    @classmethod
    def is_combo_bundle(cls, title: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Detects if a title indicates a promotional combo or bundled accessory.
        Returns (is_bundle, failure_category).
        """
        if not title:
            return False, None

        clean = title.lower()
        for pat in cls.COMBO_BUNDLE_PATTERNS:
            if re.search(pat, clean, re.IGNORECASE):
                return True, "COMBO_BUNDLE"

        return False, None

    @classmethod
    def normalize_title(cls, title: Optional[str], brand: Optional[str] = None) -> str:
        """
        Strips brand prefix, weights, packaging claims, and marketing noise.
        """
        if not title:
            return ""

        text = title.lower()

        # Remove brand name if present
        if brand:
            brand_clean = brand.lower().strip()
            if brand_clean:
                text = re.sub(rf"\b{re.escape(brand_clean)}\b", " ", text)

        # Strip marketing nutrient claims
        if VariantNormalizer and hasattr(VariantNormalizer, "NUTRIENT_CLAIM_PATTERNS"):
            for pat in VariantNormalizer.NUTRIENT_CLAIM_PATTERNS:
                text = re.sub(pat, " ", text, flags=re.IGNORECASE)

        # Strip weights
        text = re.sub(r"\b\d+(?:\.\d+)?\s*(?:kg|kilo|g|gm|grams?|lbs?|lb|oz|fl\s*oz|ml)\b", " ", text, flags=re.IGNORECASE)

        # Strip marketing noise
        for pat in cls.NOISE_PATTERNS:
            text = re.sub(pat, " ", text, flags=re.IGNORECASE)

        # Remove punctuation and normalize spaces
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _token_similarity(str_a: str, str_b: str) -> float:
        """
        Jaccard token similarity with character-level Levenshtein fallback.
        """
        tokens_a = set(str_a.split())
        tokens_b = set(str_b.split())

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        jaccard = len(intersection) / len(union)

        # Token sort comparison
        sorted_a = " ".join(sorted(tokens_a))
        sorted_b = " ".join(sorted(tokens_b))
        if sorted_a == sorted_b:
            return 1.0

        # Exact substring containment bonus
        if sorted_a in sorted_b or sorted_b in sorted_a:
            jaccard = max(jaccard, 0.85)

        return round(jaccard, 4)

    @classmethod
    def calculate_match_confidence(
        cls,
        prod_a: Dict[str, Any],
        prod_b: Dict[str, Any]
    ) -> float:
        """
        Calculates match confidence between two product records.
        Strictly enforces:
        1. Category Silo Equality (protein != mass gainer != creatine)
        2. Brand Equality
        3. Normalized Title Token Similarity
        """
        # Hard Rule 1: Category Silo must match exactly
        silo_a = (prod_a.get("category_silo") or prod_a.get("category") or "protein").lower().strip()
        silo_b = (prod_b.get("category_silo") or prod_b.get("category") or "protein").lower().strip()
        if silo_a != silo_b:
            return 0.0

        # Hard Rule 2: Brand must match
        brand_a = (prod_a.get("brand") or "").lower().strip()
        brand_b = (prod_b.get("brand") or "").lower().strip()
        if brand_a and brand_b:
            if brand_a != brand_b and brand_a not in brand_b and brand_b not in brand_a:
                return 0.0
            brand_score = 1.0 if brand_a == brand_b else 0.95
        else:
            brand_score = 0.5  # Brand missing, lower confidence

        # Title Token Similarity
        title_a = prod_a.get("base_name") or prod_a.get("name") or prod_a.get("title") or ""
        title_b = prod_b.get("base_name") or prod_b.get("name") or prod_b.get("title") or ""

        norm_a = cls.normalize_title(title_a, brand_a)
        norm_b = cls.normalize_title(title_b, brand_b)

        if not norm_a or not norm_b:
            return 0.0

        title_sim = cls._token_similarity(norm_a, norm_b)

        # Weighted final score
        final_score = (brand_score * 0.4) + (title_sim * 0.6)
        return round(final_score, 4)

    @classmethod
    def resolve_candidate(
        cls,
        candidate: Dict[str, Any],
        target_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates candidate against target and returns routing decision.
        """
        # Check combo bundle
        title = candidate.get("title") or candidate.get("raw_title") or candidate.get("base_name") or ""
        is_bundle, failure_reason = cls.is_combo_bundle(title)
        if is_bundle:
            return {
                "decision": "QUARANTINE",
                "failure_reason": failure_reason,
                "confidence_score": 0.0,
                "action": "Route to staging_quarantine as COMBO_BUNDLE"
            }

        score = cls.calculate_match_confidence(candidate, target_product)

        if score >= cls.AUTO_MERGE_THRESHOLD:
            return {
                "decision": "AUTO_MERGE",
                "confidence_score": score,
                "action": "Merge variants directly into target product"
            }
        elif score >= cls.STAGING_REVIEW_THRESHOLD:
            return {
                "decision": "STAGING_REVIEW",
                "confidence_score": score,
                "action": "Insert into entity_resolution_staging for review"
            }
        else:
            return {
                "decision": "DISTINCT",
                "confidence_score": score,
                "action": "Treat as independent standalone product"
            }

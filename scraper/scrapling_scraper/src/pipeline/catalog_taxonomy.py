"""
src/pipeline/catalog_taxonomy.py
Enterprise-Grade Hierarchical Tokenizer, Stateful Consume-and-Strip Title Parser,
Category Formulation Bitmasks, Blocking Key Generator, and Physical Unit-Economics Bounds.
"""

import re
import math
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field


# -----------------------------------------------------------------------------
# Canonical Weights & Dynamic Tolerances
# -----------------------------------------------------------------------------
CANONICAL_WEIGHT_BUCKETS = [
    83, 100, 120, 150, 200, 225, 250, 300, 350, 400, 454, 500,
    680, 750, 907, 1000, 1360, 1500, 1814, 2000, 2270, 2500, 2720,
    3000, 3628, 4000, 4536, 5000, 5443, 6000, 6804
]

# Tolerance specification: +-2.5% for <= 500g, +-1.8% for > 500g
TOLERANCE_LE_500 = 0.025
TOLERANCE_GT_500 = 0.018


def snap_to_canonical_weight(weight_g: float) -> int:
    """
    Snaps raw gram weights to canonical industry buckets with dynamic tolerance:
    +-2.5% for <= 500g and +-1.8% for > 500g.
    If no bucket matches within tolerance, returns the rounded integer weight.
    """
    if weight_g <= 0:
        return 0

    best_bucket = None
    min_diff = float("inf")

    for bucket in CANONICAL_WEIGHT_BUCKETS:
        tolerance = TOLERANCE_LE_500 if bucket <= 500 else TOLERANCE_GT_500
        allowed_margin = bucket * tolerance
        diff = abs(weight_g - bucket)
        if diff <= allowed_margin:
            if diff < min_diff:
                min_diff = diff
                best_bucket = bucket

    if best_bucket is not None:
        return best_bucket
    return int(round(weight_g))


# -----------------------------------------------------------------------------
# Category Formulation Keyword Definitions
# -----------------------------------------------------------------------------
CATEGORY_FORMULATION_KEYWORDS: Dict[str, List[str]] = {
    "protein": [
        "isolate", "hydrolyzed", "concentrate", "raw", "clear", "plant",
        "casein", "gold", "nitro", "ripped", "diet", "beginner",
        "performance", "biozyme"
    ],
    "creatine": [
        "creapure", "hcl", "nitrate", "buffered", "kre_alkalyn",
        "chewable", "effervescent"
        # plain monohydrate / micronized defaults to 'standard' if no bit matches
    ],
    "mass_gainer": [
        "super", "serious", "extreme", "lean", "anabolic", "bulk",
        "xxl", "gold", "complex", "clean"
    ],
    "pre_workout": [
        "extreme", "black", "gold", "total", "psychotic", "pump",
        "non_stim", "lite", "ripped"
    ]
}

# Stopwords & noise to eliminate for clean residual tokens
STOP_WORDS = {
    "100%", "100", "pure", "powder", "supplement", "imported", "authentic",
    "with", "and", "&", "for", "in", "of", "the", "a", "an", "at", "by",
    "premium", "nutrition", "instantized", "formula", "series", "edition",
    "original", "flavour", "flavor", "unflavoured", "unflavored"
}


@dataclass
class ParsedCatalogProduct:
    original_title: str
    is_bundle: bool = False
    bundle_reason: Optional[str] = None
    pack_count: int = 1
    raw_extracted_weight_g: Optional[float] = None
    single_unit_weight_g: Optional[int] = None
    bucketed_weight_g: Optional[int] = None
    serving_count: Optional[int] = None
    unit_count: Optional[int] = None
    unit_type: Optional[str] = None  # capsules, tablets, softgels, sachets, shots
    category_silo: str = "protein"
    formulation_sig: str = "standard"
    formulation_bits: List[str] = field(default_factory=list)
    clean_residual_tokens: List[str] = field(default_factory=list)
    canonical_flavor: str = "unflavored"
    delivery_form: str = "powder"  # powder, capsules, tablets, liquid, bar


class StatefulTitleParser:
    """
    Hierarchical consume-and-strip stateful title parser.
    Executes in strict priority order so numbers never cross-contaminate.
    """

    # Step 1: Bundle / Combo patterns
    BUNDLE_PATTERNS = [
        (re.compile(r"\bwith\s+free\s+[a-z0-9\s\-]+", re.I), "with free item"),
        (re.compile(r"\bfree\s+(?:shaker|sipper|bottle|creatine|t-?shirt|multivitamin|gym\s*bag)\b", re.I), "freebie item"),
        (re.compile(r"\bcombo\s*(?:pack|of|\b)", re.I), "combo"),
        (re.compile(r"\bstack\b", re.I), "stack"),
        (re.compile(r"\b(?:twin\s*pack|buy\s*1\s*get\s*1|bogo)\b", re.I), "bundle deal"),
        (re.compile(r"\+\s*(?:free|shaker|sipper|bottle|creatine|pre[- ]?workout|gym\s*vest)", re.I), "plus add-on"),
        (re.compile(r"(\d+(?:\.\d+)?\s*(?:kg|g|lbs?))\s*\+\s*(\d+(?:\.\d+)?\s*(?:kg|g|lbs?))", re.I), "dual weight combo"),
    ]

    # Step 2: Multi-pack multiplier patterns
    MULTIPACK_PATTERNS = [
        # 2 x 1kg, 2x500g, 2 * 1 kg
        re.compile(r"\b(\d+)\s*(?:x|\*)\s*(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz)\b", re.I),
        # Pack of 2 (1kg each), Pack of 2, 500g
        re.compile(r"\bpack\s*of\s*(\d+)\b[^\d]*?(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz)\b", re.I),
        # 2 tubs of 1kg, 2 packs of 500g
        re.compile(r"\b(\d+)\s*(?:tubs?|packs?|bottles?|jars?|units?)\s*(?:of)?\s*(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz)\b", re.I),
    ]

    # General pack-count patterns where weight is elsewhere
    PACK_ONLY_PATTERNS = [
        re.compile(r"\bpack\s*of\s*(\d+)\b", re.I),
        re.compile(r"\btwin\s*pack\s*\(?(\d+)?\)?", re.I),
        re.compile(r"\bbuy\s*1\s*get\s*1\b", re.I),
        re.compile(r"\b(\d+)\s*(?:pack|tubs?|bottles?|units?)\b", re.I),
    ]

    # Step 3: Micro-dosage claims to strip BEFORE weight extraction
    DOSAGE_STRIP_PATTERNS = [
        # 1000mg, 500 mcg, 5000 IU
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|iu)\b", re.I),
        # 5g BCAAs/Creatine per serving, 24g Protein per scoop
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*(?:of\s*)?(?:protein|protien|bcaa|bcaas|eaa|eaas|glutamine|creatine|tribulus|citrulline|arginine|carnitine|beta[- ]alanine|carbs?|carbohydrates?|fat|sugar|fiber|fibre)(?:\s*(?:per|\/)\s*(?:serving|scoop))?\b", re.I),
        # protein : 24g, creatine: 3g
        re.compile(r"\b(?:protein|protien|bcaa|bcaas|eaa|glutamine|creatine|tribulus)\s*[:\-]?\s*\d+(?:\.\d+)?\s*(?:g|gm|grams?)\b", re.I),
        # per serving / per scoop with grams
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*(?:per|\/)\s*(?:serving|scoop)\b", re.I),
        re.compile(r"\b(?:per|\/)\s*(?:serving|scoop)\s*[:\-]?\s*\d+(?:\.\d+)?\s*(?:g|gm|grams?)\b", re.I),
    ]

    # Step 4: Primary Net Weight Extraction
    WEIGHT_PATTERNS = [
        re.compile(r"\b(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz|fl\s*\.?\s*oz|ml)\b", re.I),
        re.compile(r"\b(\d+(?:\.\d+)?)\s*kg\b", re.I),
    ]

    # Step 6: Servings & Unit Count
    SERVING_PATTERNS = [
        re.compile(r"\b(\d+)\s*(?:servings?|scoops?)\b", re.I),
        re.compile(r"\b(?:servings?|scoops?)\s*[:\-]?\s*(\d+)\b", re.I),
        re.compile(r"\((\d+)\s*servings?\)", re.I)
    ]

    UNIT_PATTERNS = [
        (re.compile(r"\b(\d+)\s*(capsules?|caps?)\b", re.I), "capsules"),
        (re.compile(r"\b(\d+)\s*(tablets?|tabs?)\b", re.I), "tablets"),
        (re.compile(r"\b(\d+)\s*(softgels?)\b", re.I), "softgels"),
        (re.compile(r"\b(\d+)\s*(sachets?|packets?)\b", re.I), "sachets"),
        (re.compile(r"\b(\d+)\s*(shots?)\b", re.I), "shots"),
    ]

    @classmethod
    def parse(cls, title: str, category_silo_hint: Optional[str] = None) -> ParsedCatalogProduct:
        result = ParsedCatalogProduct(original_title=title)
        working_text = title

        # Step 1: Combo / Freebie Detection
        for pat, reason in cls.BUNDLE_PATTERNS:
            m = pat.search(working_text)
            if m:
                result.is_bundle = True
                result.bundle_reason = reason
                break

        # Step 2: Multi-Pack Multiplier Extraction & Span Stripping
        pack_count = 1
        mult_extracted_weight = None

        for pat in cls.MULTIPACK_PATTERNS:
            m = pat.search(working_text)
            if m:
                pack_count = max(1, int(m.group(1)))
                val = float(m.group(2))
                unit = m.group(3).lower().replace(" ", "").replace(".", "")
                mult_extracted_weight = cls._unit_to_grams(val, unit)
                # Strip the matched span
                working_text = working_text[:m.start()] + " " + working_text[m.end():]
                break

        if pack_count == 1:
            for pat in cls.PACK_ONLY_PATTERNS:
                m = pat.search(working_text)
                if m:
                    if "buy 1 get 1" in m.group(0).lower():
                        pack_count = 2
                    elif m.groups() and m.group(1):
                        pack_count = max(1, int(m.group(1)))
                    else:
                        pack_count = 2
                    working_text = working_text[:m.start()] + " " + working_text[m.end():]
                    break

        result.pack_count = pack_count

        # Step 3: Dosage Strip - Strip micro-dosages so e.g. 1000mg is never parsed as weight
        for pat in cls.DOSAGE_STRIP_PATTERNS:
            working_text = pat.sub(" ", working_text)

        # Step 4: Primary Net Weight Extraction
        single_weight_g = None
        if mult_extracted_weight is not None:
            single_weight_g = mult_extracted_weight
        else:
            for pat in cls.WEIGHT_PATTERNS:
                m = pat.search(working_text)
                if m:
                    val = float(m.group(1))
                    unit = m.group(2).lower().replace(" ", "").replace(".", "") if len(m.groups()) > 1 else "kg"
                    single_weight_g = cls._unit_to_grams(val, unit)
                    # Strip span
                    working_text = working_text[:m.start()] + " " + working_text[m.end():]
                    break

        result.raw_extracted_weight_g = single_weight_g
        if single_weight_g is not None:
            result.single_unit_weight_g = int(round(single_weight_g))
            # Step 5: Canonical Weight Bucketing with Dynamic Tolerance
            result.bucketed_weight_g = snap_to_canonical_weight(single_weight_g)

        # Step 6: Servings & Unit Count Extraction
        for pat in cls.SERVING_PATTERNS:
            m = pat.search(working_text)
            if m:
                result.serving_count = int(m.group(1))
                working_text = working_text[:m.start()] + " " + working_text[m.end():]
                break

        for pat, utype in cls.UNIT_PATTERNS:
            m = pat.search(working_text)
            if m:
                result.unit_count = int(m.group(1))
                result.unit_type = utype
                result.delivery_form = utype
                working_text = working_text[:m.start()] + " " + working_text[m.end():]
                break

        # Detect delivery form if not already tablets/capsules
        if not result.unit_type:
            low = title.lower()
            if any(k in low for k in ["capsule", "cap"]):
                result.delivery_form = "capsules"
            elif any(k in low for k in ["tablet", "tab"]):
                result.delivery_form = "tablets"
            elif any(k in low for k in ["bar", "cookie", "wafer", "snack"]):
                result.delivery_form = "bar"
            elif any(k in low for k in ["liquid", "drink", "shot", "rtd"]):
                result.delivery_form = "liquid"
            else:
                result.delivery_form = "powder"

        # Detect category silo
        silo = category_silo_hint or cls._detect_silo(title)
        result.category_silo = silo

        # Step 7: Category Formulation Bitmask & Negative Tokens
        sig, bits = cls._extract_formulation_signature(title, silo)
        result.formulation_sig = sig
        result.formulation_bits = bits

        # Step 8: Residual Line Tokenization
        result.clean_residual_tokens = cls._tokenize_residual(working_text)

        return result

    @staticmethod
    def _unit_to_grams(val: float, unit: str) -> float:
        if unit in ("kg", "kilo"):
            return val * 1000.0
        elif unit in ("g", "gm", "gram", "grams", "ml"):
            return val
        elif unit in ("lb", "lbs"):
            # Industry conversions
            if abs(val - 2.2) < 0.05:
                return 1000.0
            elif abs(val - 4.4) < 0.05:
                return 2000.0
            elif abs(val - 5.0) < 0.05:
                return 2268.0
            elif abs(val - 10.0) < 0.05:
                return 4536.0
            return val * 453.592
        elif unit == "oz":
            return val * 28.3495
        elif unit in ("floz", "fl.oz"):
            return val * 29.5735
        return val

    @staticmethod
    def _detect_silo(text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["mass gainer", "weight gainer", "super gainer", "serious mass", "mega gainer"]):
            return "mass_gainer"
        if any(w in t for w in ["creatine", "creapure"]):
            return "creatine"
        if any(w in t for w in ["pre workout", "pre-workout", "preworkout"]):
            return "pre_workout"
        return "protein"

    @classmethod
    def _extract_formulation_signature(cls, text: str, silo: str) -> Tuple[str, List[str]]:
        t = text.lower()
        keywords = CATEGORY_FORMULATION_KEYWORDS.get(silo, CATEGORY_FORMULATION_KEYWORDS["protein"])
        matched_bits = []

        for kw in keywords:
            # Match word boundary or hyphen
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, t):
                matched_bits.append(kw)

        if not matched_bits:
            return "standard", []

        matched_bits.sort()
        sig = "_".join(matched_bits)
        return sig, matched_bits

    @staticmethod
    def _tokenize_residual(text: str) -> List[str]:
        # Remove punctuation, lowercase, split
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = [t.strip() for t in clean.split() if t.strip()]
        residual = []
        for tok in tokens:
            if tok in STOP_WORDS:
                continue
            if tok.isdigit():
                continue
            if len(tok) <= 1:
                continue
            residual.append(tok)
        return residual


# -----------------------------------------------------------------------------
# Blocking Key Generator
# -----------------------------------------------------------------------------
def generate_blocking_key(
    canonical_brand: str,
    category_silo: str,
    canonical_line: str,
    delivery_form: str,
    formulation_sig: str = "standard"
) -> str:
    """
    Generates deterministic Cluster / Blocking Key:
    brand ::: silo ::: canonical_line ::: delivery_form ::: formulation_sig
    """
    b = (canonical_brand or "").strip().lower()
    s = (category_silo or "protein").strip().lower()
    line = (canonical_line or "").strip().lower()
    df = (delivery_form or "powder").strip().lower()
    f_sig = (formulation_sig or "standard").strip().lower()

    return f"{b}:::{s}:::{line}:::{df}:::{f_sig}"


def generate_canopy_key(
    canonical_brand: str,
    category_silo: str,
    delivery_form: str = "powder"
) -> Tuple[str, str, str]:
    """
    Generates coarse-grained canopy key for O(1) in-memory index blocking.
    """
    return (
        (canonical_brand or "").strip().lower(),
        (category_silo or "protein").strip().lower(),
        (delivery_form or "powder").strip().lower()
    )


# -----------------------------------------------------------------------------
# Layer 3: Physical Unit-Economics Guardrails
# -----------------------------------------------------------------------------
def is_economically_valid_price(
    price_inr: float,
    weight_grams: float,
    category_silo: str,
    formulation_sig: str = "standard",
    serving_count: Optional[int] = None,
    ocr_protein_per_serving_g: Optional[float] = None,
    peer_prices: Optional[List[float]] = None
) -> Tuple[bool, str]:
    """
    Validates physical unit-economics bounds across supplement categories.
    
    Rules:
    - protein: Reject if price < ₹1.10 / gram of powder (or < ₹1.80 / gram for isolate/hydrolyzed),
      OR if OCR protein_per_serving_g is present, reject if Cost Per Gram of True Unspiked Protein
      (price_inr / (serving_count * true_protein_g)) is < ₹1.45 / g protein.
    - creatine: Reject if price < ₹0.75 / gram (or < ₹1.50 / gram for creapure).
    - mass_gainer: Reject if price < ₹0.45 / gram.
    - pre_workout: Reject if price < ₹18.0 / serving or < ₹1.50 / gram.
    - Combine with MAD (Median Absolute Deviation) when >= 3 offers exist:
      reject any offer where price < median_price * 0.48.
    """
    if price_inr <= 0:
        return False, "Price must be greater than 0"

    silo = (category_silo or "protein").lower()
    form_sig = (formulation_sig or "standard").lower()
    w_g = max(1.0, float(weight_grams or 1000.0))
    price_per_g = price_inr / w_g

    # 1. Category Floor Checks
    if silo == "protein":
        is_isolate = "isolate" in form_sig or "hydrolyzed" in form_sig
        min_powder_per_g = 1.80 if is_isolate else 1.10
        if price_per_g < min_powder_per_g:
            return False, f"Protein price ₹{price_per_g:.2f}/g is below physical floor ₹{min_powder_per_g}/g"

        # OCR True Protein Cost Floor
        if ocr_protein_per_serving_g and serving_count and serving_count > 0:
            total_protein_g = serving_count * ocr_protein_per_serving_g
            if total_protein_g > 0:
                cost_per_g_protein = price_inr / total_protein_g
                if cost_per_g_protein < 1.45:
                    return False, f"Cost per gram of true protein ₹{cost_per_g_protein:.2f}/g is below ₹1.45/g floor"

    elif silo == "creatine":
        is_creapure = "creapure" in form_sig
        min_creatine_per_g = 1.50 if is_creapure else 0.75
        if price_per_g < min_creatine_per_g:
            return False, f"Creatine price ₹{price_per_g:.2f}/g is below physical floor ₹{min_creatine_per_g}/g"

    elif silo == "mass_gainer":
        if price_per_g < 0.45:
            return False, f"Mass gainer price ₹{price_per_g:.2f}/g is below physical floor ₹0.45/g"

    elif silo == "pre_workout":
        # Check per serving if available, otherwise per gram
        if serving_count and serving_count > 0:
            cost_per_serving = price_inr / serving_count
            if cost_per_serving < 18.0:
                return False, f"Pre-workout price ₹{cost_per_serving:.2f}/serving is below ₹18.00/serving floor"
        elif price_per_g < 1.50:
            return False, f"Pre-workout price ₹{price_per_g:.2f}/g is below physical floor ₹1.50/g"

    # 2. MAD (Median Absolute Deviation) when >= 3 peer prices exist
    if peer_prices and len(peer_prices) >= 3:
        valid_peers = sorted([p for p in peer_prices if p > 0])
        if len(valid_peers) >= 3:
            n = len(valid_peers)
            median = valid_peers[n // 2] if n % 2 != 0 else (valid_peers[n // 2 - 1] + valid_peers[n // 2]) / 2.0
            if price_inr < median * 0.48:
                return False, f"Price ₹{price_inr:.2f} is an extreme outlier (< 48% of median ₹{median:.2f})"

    return True, "Valid"

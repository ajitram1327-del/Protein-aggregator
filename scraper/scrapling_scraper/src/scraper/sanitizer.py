"""
ProteIndex Scraper Engine — Module 1: Pre-Ingestion Sanitizer & Weight Normalizer
Provides:
- COMBO_KEYWORD_PATTERN: Regex identifying combo/promotional bundles for quarantine.
- MULTI_WEIGHT_PATTERN: Regex detecting multi-pack/multi-unit packs.
- extract_normalized_grams: 4-tier weight normalizer converting arbitrary descriptions
  into clean integer net grams.
- is_promotional_combo: High-precision discriminator for quarantine triage.
"""

import re
from typing import Optional, Tuple


# Regex 1: Identifies multi-product bundles, promotional freebies, shakers, and non-supplement gear
COMBO_KEYWORD_PATTERN = re.compile(
    r"""(?ix)
    \b(?:
        combo(?:[- ]?pack)? |
        pack\s+of\s+[2-9]\d* |
        buy\s+[1-9]\s+get\s+[1-9] |
        bogo |
        twin\s+pack |
        duo\s+pack |
        starter\s+kit |
        bundle |
        value\s+pack |
        special\s+pack |
        super\s+saver |
        stack |
        with\s+(?:free\s+)?(?:shaker|sipper|t-?shirt|bottle|creatine|fish\s*oil|multivitamin|gym\s+bag|wrist\s*band|strap|smart\s*watch) |
        \+\s*(?:free\s+)?(?:shaker|sipper|bottle|creatine|t-?shirt|bag) |
        free\s+(?:shaker|sipper|bottle|t-?shirt|creatine|multivitamin)
    )\b
    """,
    re.VERBOSE
)

# Regex 2: Catches multi-weight declarations within a single title (e.g., "1kg + 250g")
MULTI_WEIGHT_PATTERN = re.compile(
    r"""(?ix)
    \b\d+(?:\.\d+)?\s*(?:kg|g|lbs?)\s*\+\s*\d+(?:\.\d+)?\s*(?:kg|g|lbs?)\b
    """,
    re.VERBOSE
)


try:
    from src.pipeline.catalog_taxonomy import StatefulTitleParser, snap_to_canonical_weight
except ImportError:
    StatefulTitleParser = None
    snap_to_canonical_weight = None


def is_promotional_combo(title: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates product title against blacklist patterns.
    Returns: (is_combo: bool, reason: str or None)
    """
    if not title:
        return False, None

    if StatefulTitleParser is not None:
        parsed = StatefulTitleParser.parse(title)
        if parsed.is_bundle:
            return True, f"BUNDLE:{parsed.bundle_reason}"

    if MULTI_WEIGHT_PATTERN.search(title):
        return True, "MULTI_WEIGHT_BUNDLE"

    match = COMBO_KEYWORD_PATTERN.search(title)
    if match:
        return True, f"COMBO_PROMO_KEYWORD:{match.group(0).strip().upper()}"

    return False, None


def extract_normalized_grams(
    title: str,
    raw_weight_field: Optional[str] = None,
    description: Optional[str] = None
) -> Optional[int]:
    """
    Tiered regex extraction with explicit noise cancellation.
    Strips out micro-dosages (mg, mcg) and per-serving callouts before matching tub weight.
    """
    # 0. Primary pass with StatefulTitleParser if available
    if StatefulTitleParser is not None and title:
        parsed = StatefulTitleParser.parse(title)
        if parsed.bucketed_weight_g and parsed.bucketed_weight_g > 0:
            return parsed.bucketed_weight_g

    raw_candidates = [raw_weight_field or "", title or "", description or ""]

    # Pre-clean corpus: Strip serving noise to prevent "5g Creatine" or "1000mg" from corrupting weight
    search_corpus = []
    for text in raw_candidates:
        if not text:
            continue
        cleaned = text
        # Strip micro dosages (e.g. 1000mg, 500mcg)
        cleaned = re.sub(r'(?i)\b\d+(?:\.\d+)?\s*(?:mg|mcg)\b', ' ', cleaned)
        # Strip common additive callouts (e.g. "with 5g Creatine", "5.5g BCAA")
        cleaned = re.sub(r'(?i)\b(?:\d+(?:\.\d+)?\s*g\s*(?:creatine|bcaa|glutamine|protein|leucine))\b', ' ', cleaned)
        search_corpus.append(cleaned)

    # 1. Metric: Kilograms (Priority 1)
    for text in search_corpus:
        kg_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*k(?:ilo)?g(?:s|ram|rams)?\b', text)
        if kg_match:
            try:
                kg_val = float(kg_match.group(1))
                if 0.1 <= kg_val <= 25.0:
                    return int(round(kg_val * 1000.0))
            except (ValueError, TypeError):
                pass

    # 2. Imperial: Pounds (Priority 2)
    for text in search_corpus:
        lb_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\b', text)
        if lb_match:
            try:
                lb_val = float(lb_match.group(1))
                if 0.2 <= lb_val <= 55.0:
                    return int(round(lb_val * 453.59237))
            except (ValueError, TypeError):
                pass

    # 3. Metric: Grams (Priority 3 - Floor set to 150g to ignore single scoops/micro packs)
    for text in search_corpus:
        g_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams)\b', text)
        if g_match:
            try:
                g_val = float(g_match.group(1))
                # Enforce physical tub floor of 150g to prevent capturing leftover additive noise
                if 150.0 <= g_val <= 25000.0:
                    return int(round(g_val))
            except (ValueError, TypeError):
                pass

    # 4. Servings x Serving Size Fallback
    for text in search_corpus:
        servings_match = re.search(r'(?i)\b(\d+)\s*servings\b', text)
        scoop_match = re.search(r'(?i)\b(?:serving\s*size|scoop|per\s*serving)[\s:]*(\d+(?:\.\d+)?)\s*g\b', text)
        if servings_match and scoop_match:
            try:
                servings = int(servings_match.group(1))
                scoop = float(scoop_match.group(1))
                total_grams = servings * scoop
                if 150.0 <= total_grams <= 25000.0:
                    return int(round(total_grams))
            except (ValueError, TypeError):
                pass

    return None

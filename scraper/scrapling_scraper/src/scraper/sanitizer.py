"""
ProteIndex Scraper Engine — Module 1: Pre-Ingestion Sanitizer & Weight Normalizer
Provides:
- COMBO_KEYWORD_PATTERN: Regex identifying combo/promotional bundles for quarantine.
- MULTI_WEIGHT_PATTERN: Regex detecting multi-pack/multi-unit packs.
- extract_normalized_grams: Enterprise strip-and-consume weight normalizer converting
  arbitrary descriptions into clean integer net grams.
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
        try:
            parsed = StatefulTitleParser.parse(title)
            if parsed.is_bundle:
                return True, f"BUNDLE:{parsed.bundle_reason}"
        except Exception:
            pass

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
    Enterprise strip-and-consume sequence for clean container weight extraction.
    1. Preserves flavor keywords (e.g. 'Double Rich Chocolate').
    2. Converts written number tokens ('pack of two', 'twin', 'double') to multipliers.
    3. Completely removes micro-dosage additive noise (mg, mcg) and per-serving callouts (g BCAAs, Plant Protein).
    4. Handles multi-pack multipliers (e.g. 2 x 1kg = 2000g, 2 x 500g = 1000g).
    5. Prioritizes primary metric declarations over auxiliary parenthesized units.
    6. Snaps to canonical industry weights with dynamic tolerance.
    """
    raw_candidates = [raw_weight_field or "", title or "", description or ""]

    for raw in raw_candidates:
        if not raw:
            continue

        text = raw

        # Step 1: Protect known flavor keywords containing written numbers
        text = re.sub(r'(?i)\bdouble\s+(?:rich|chocolate|choco|fudge|cocoa|dutch)\b', 'FLAVOR_DOUBLE_CHOCO', text)

        # Step 2: Normalize written number tokens (Multi-word phrases first)
        written_number_rules = [
            (r'(?i)\bpack\s+of\s+two\b', '2 x'),
            (r'(?i)\bpack\s+of\s+three\b', '3 x'),
            (r'(?i)\bpack\s+of\s+four\b', '4 x'),
            (r'(?i)\bpack\s+of\s+six\b', '6 x'),
            (r'(?i)\btwin\s*(?:pack|tub|unit)?\b', '2 x'),
            (r'(?i)\bdouble\s*(?:pack|tub|unit)?\b', '2 x'),
            (r'(?i)\bduo\s*(?:pack|tub|unit)?\b', '2 x'),
            (r'(?i)\btwo\s*(?:tubs?|packs?|jars?|bottles?|units?|pieces?|pcs)\b', '2 x'),
            (r'(?i)\bthree\s*(?:tubs?|packs?|jars?|bottles?|units?|pieces?|pcs)\b', '3 x'),
            (r'(?i)\bfour\s*(?:tubs?|packs?|jars?|bottles?|units?|pieces?|pcs)\b', '4 x'),
            (r'(?i)\bsix\s*(?:tubs?|packs?|jars?|bottles?|units?|pieces?|pcs)\b', '6 x'),
            (r'(?i)\b(?:twin|duo)\b', '2 x'),
            (r'(?i)\btwo\b', '2 x'),
        ]
        for pat, repl in written_number_rules:
            text = re.sub(pat, repl, text)

        # Step 3: Strip-and-Consume Layer: Remove micro-dosages and additives
        # Remove mg, mcg, IU
        text = re.sub(r'(?i)\b\d+(?:\.\d+)?\s*(?:mg|mcg|mcgs|iu)\b', ' ', text)

        # Remove per-serving nutrient declarations & additive noise (e.g. '25g Plant Protein', '5.5g BCAA')
        text = re.sub(
            r'(?i)\b\d+(?:\.\d+)?\s*(?:g|gm|gms|gram|grams)?\s*(?:of\s*)?'
            r'(?:plant\s+|whey\s+|pea\s+|soy\s+|casein\s+|raw\s+|pure\s+)?'
            r'(?:protein|protien|bcaa|bcaas|creatine|glutamine|leucine|taurine|tribulus|carnitine|citrulline|arginine|carbs?|carbohydrates?|sugar|fat|fiber|fibre)\b',
            ' ',
            text
        )

        # Remove per-serving / per-scoop callouts
        text = re.sub(r'(?i)\b\d+(?:\.\d+)?\s*(?:g|gm|gms|gram|grams)?\s*(?:per|\/)\s*(?:serving|scoop)\b', ' ', text)
        text = re.sub(r'(?i)\b(?:serving\s*size|per\s*serving|per\s*scoop)[\s:]*\d+(?:\.\d+)?\s*(?:g|gm|gms|gram|grams)?\b', ' ', text)
        text = re.sub(r'(?i)\b(?:100%|100\s*percent)\b', ' ', text)

        # Step 4: Multiplier Pattern Detection: N x Weight (e.g. 2 x 1kg, 2 x 500g, 2x1kg)
        mult_match = re.search(
            r'(?i)\b(\d+)\s*(?:x|\*)\s*(\d+(?:\.\d+)?)\s*(k(?:ilo)?g(?:s|ram|rams)?|lbs?|pounds?|g|gm|gms|gram|grams)\b',
            text
        )
        if mult_match:
            try:
                count = int(mult_match.group(1))
                val = float(mult_match.group(2))
                unit = mult_match.group(3).lower()
                if count > 0 and val > 0:
                    if 'k' in unit:
                        total_g = int(round(count * val * 1000.0))
                    elif 'lb' in unit or 'pound' in unit:
                        total_g = int(round(count * val * 453.59237))
                    else:
                        total_g = int(round(count * val))
                    
                    if 100 <= total_g <= 30000:
                        if snap_to_canonical_weight is not None:
                            return snap_to_canonical_weight(total_g)
                        return total_g
            except (ValueError, TypeError):
                pass

        # Step 5: Primary Metric: Kilograms (Priority 1)
        kg_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*k(?:ilo)?g(?:s|ram|rams)?\b', text)
        if kg_match:
            try:
                kg_val = float(kg_match.group(1))
                if 0.1 <= kg_val <= 30.0:
                    raw_g = int(round(kg_val * 1000.0))
                    if snap_to_canonical_weight is not None:
                        return snap_to_canonical_weight(raw_g)
                    return raw_g
            except (ValueError, TypeError):
                pass

        # Step 6: Imperial: Pounds (Priority 2)
        lb_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\b', text)
        if lb_match:
            try:
                lb_val = float(lb_match.group(1))
                if 0.2 <= lb_val <= 65.0:
                    raw_g = int(round(lb_val * 453.59237))
                    if snap_to_canonical_weight is not None:
                        return snap_to_canonical_weight(raw_g)
                    return raw_g
            except (ValueError, TypeError):
                pass

        # Step 7: Metric: Grams (Priority 3 - Tub floor 100g)
        g_match = re.search(r'(?i)\b(\d+(?:\.\d+)?)\s*(?:g|gm|gms|gram|grams)\b', text)
        if g_match:
            try:
                g_val = float(g_match.group(1))
                if 100.0 <= g_val <= 30000.0:
                    raw_g = int(round(g_val))
                    if snap_to_canonical_weight is not None:
                        return snap_to_canonical_weight(raw_g)
                    return raw_g
            except (ValueError, TypeError):
                pass

        # Step 8: Servings x Scoop Size Fallback
        servings_match = re.search(r'(?i)\b(\d+)\s*servings\b', text)
        scoop_match = re.search(r'(?i)\b(?:serving\s*size|scoop|per\s*serving)[\s:]*(\d+(?:\.\d+)?)\s*g\b', text)
        if servings_match and scoop_match:
            try:
                servings = int(servings_match.group(1))
                scoop = float(scoop_match.group(1))
                total_grams = servings * scoop
                if 100.0 <= total_grams <= 30000.0:
                    raw_g = int(round(total_grams))
                    if snap_to_canonical_weight is not None:
                        return snap_to_canonical_weight(raw_g)
                    return raw_g
            except (ValueError, TypeError):
                pass

    # Fallback to StatefulTitleParser if regex exhausted
    if StatefulTitleParser is not None and title:
        try:
            parsed = StatefulTitleParser.parse(title)
            if parsed.bucketed_weight_g and parsed.bucketed_weight_g > 0:
                return parsed.bucketed_weight_g
        except Exception:
            pass

    return None

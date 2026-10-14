import re
import hashlib
from typing import Dict, Optional

try:
    from pydantic import BaseModel, Field
    class NormalizedVariant(BaseModel):
        weight_grams: int = Field(..., description="Normalized weight in integer grams")
        canonical_flavor: str = Field(..., description="Canonical flavor descriptor")
        variant_hash: str = Field(..., description="SHA-256 deterministic variant hash")
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class NormalizedVariant:
        weight_grams: int
        canonical_flavor: str
        variant_hash: str

        def dict(self) -> dict:
            return {
                "weight_grams": self.weight_grams,
                "canonical_flavor": self.canonical_flavor,
                "variant_hash": self.variant_hash
            }

        def model_dump(self) -> dict:
            return self.dict()

class VariantNormalizer:
    """
    Standardized Variant Normalization and Deterministic Hashing Engine
    Compliant with Proteindex PRD Section 3.1 & 4.1.
    Eliminates duplicate variants across divergent retailer titles.
    Supports multipack multiplier detection (2 x 1kg, 2x500g, Pack of 2),
    fluid ounces, and canonical flavor taxonomy.
    """

    FLAVOR_CANONICAL_MAP: Dict[str, str] = {
        r"rich choco.*|double rich.*|belgian choco.*|chocolate fudge|dark choco.*|chocolate.*|choco.*|cocoa|brownie": "chocolate",
        r"vanilla.*|french vanilla|creamy vanilla|vanila": "vanilla",
        r"alphonso mango|mango swirl|mango.*": "mango",
        r"cafe mocha|coffee|espresso|cappuccino|mocha|latte|cold coffee": "coffee",
        r"unflavored|raw|natural|naked|unflavoured|raw whey|zero flavor": "unflavored",
        r"strawberry.*|berries|wild berry|blueberry|berry blast": "strawberry",
        r"kulfi|kesar pista|malai kulfi|kesar badam|pistachio": "kesar_pista",
        r"cookies\s*(?:&|and|n)\s*cream|oreo": "cookies_and_cream",
        r"peanut\s*butter": "peanut_butter",
        r"banana|banana cream": "banana",
        r"salted caramel|caramel": "salted_caramel",
        r"watermelon": "watermelon",
        r"green apple": "green_apple",
        r"blue raspberry|blue razz": "blue_raspberry",
        r"fruit punch": "fruit_punch",
        r"lemon.*|lime|citrus": "lemon",
        r"orange": "orange",
        r"cola": "cola"
    }

    @staticmethod
    def _clean_title(raw_title: Optional[str]) -> str:
        if not raw_title:
            return ""
        # Clean unicode spaces, non-breaking spaces, zero-width characters
        cleaned = re.sub(r"[\u00a0\u200b\u200e\u200f\t\n\r]+", " ", str(raw_title))
        return re.sub(r"\s+", " ", cleaned).strip()

    NUTRIENT_CLAIM_PATTERNS = [
        r"\b\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*(?:of\s*)?(?:protein|protien|bcaa|eaa|glutamine|creatine|carbs?|carbohydrates?|fat|sugar|fiber|fibre)(?:\s*(?:per|\/)\s*(?:serving|scoop))?\b",
        r"\b(?:protein|protien|bcaa|eaa|glutamine|creatine|carbs?|carbohydrates?|fat|sugar)\s*[:\-]?\s*\d+(?:\.\d+)?\s*(?:g|gm|grams?)\b",
        r"\b\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*(?:per|\/)\s*(?:serving|scoop)\b",
        r"\b(?:per|\/)\s*(?:serving|scoop)\s*[:\-]?\s*\d+(?:\.\d+)?\s*(?:g|gm|grams?)\b",
    ]

    @classmethod
    def parse_weight(cls, raw_title: Optional[str], default: Optional[int] = 1000) -> Optional[int]:
        """
        Extracts total weight from title and standardizes to integer grams.
        Handles kg, g, gm, lbs, lb, oz, fl oz, ml, and multipacks (e.g. '2 x 1kg', 'Pack of 2 (1kg each)').
        Strips marketing nutrient claims (e.g. '65g Protein', '24g Protein per serving') before matching.
        """
        text = cls._clean_title(raw_title)
        if not text:
            return default

        # Strip marketing nutrient claims so '65g Protein' is not misidentified as tub weight
        for pat in cls.NUTRIENT_CLAIM_PATTERNS:
            text = re.sub(pat, " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return default

        multiplier = 1
        single_val = 0.0
        unit = ""

        # Pattern 1: Explicit multiplier notation (e.g. "2 x 1kg", "2x500g", "2 * 1 kg", "3 x 2 lbs")
        mult_match = re.search(
            r"(\d+)\s*(?:x|\*)\s*(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz|fl\s*\.?\s*oz|ml)\b",
            text,
            re.IGNORECASE
        )

        if mult_match:
            multiplier = max(1, int(mult_match.group(1)))
            single_val = float(mult_match.group(2))
            unit = mult_match.group(3).lower().replace(" ", "").replace(".", "")
        else:
            # Pattern 2: "Pack of 2" / "Combo of 2" followed by weight (e.g. "Pack of 2 (1kg each)", "Pack of 2, 500g")
            pack_match = re.search(
                r"(?:pack|combo|set)\s*(?:of)?\s*(\d+)\b.*?(?:(?:\(|\,|each|\:|\-)?\s*(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz|fl\s*\.?\s*oz|ml)\b)",
                text,
                re.IGNORECASE
            )
            if pack_match:
                multiplier = max(1, int(pack_match.group(1)))
                single_val = float(pack_match.group(2))
                unit = pack_match.group(3).lower().replace(" ", "").replace(".", "")
            else:
                # Pattern 3: "2 tubs of 1kg", "2 packs of 500g", "2 bottles of 1kg"
                tubs_match = re.search(
                    r"(\d+)\s*(?:tubs?|packs?|bottles?|jars?|units?)\s*(?:of)?\s*(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz|fl\s*\.?\s*oz|ml)\b",
                    text,
                    re.IGNORECASE
                )
                if tubs_match:
                    multiplier = max(1, int(tubs_match.group(1)))
                    single_val = float(tubs_match.group(2))
                    unit = tubs_match.group(3).lower().replace(" ", "").replace(".", "")
                else:
                    # Pattern 4: Single standard weight expression (e.g. "1.5 kg", "1000g", "2.2 lbs", "16 fl oz")
                    single_match = re.search(
                        r"(\d+(?:\.\d+)?)\s*(kg|kilo|g|gm|grams?|lbs?|oz|fl\s*\.?\s*oz|ml)\b",
                        text,
                        re.IGNORECASE
                    )
                    if single_match:
                        multiplier = 1
                        single_val = float(single_match.group(1))
                        unit = single_match.group(2).lower().replace(" ", "").replace(".", "")
                    else:
                        # Fallback check for plain digits directly attached to 'kg'
                        fallback_kg = re.search(r"(\d+(?:\.\d+)?)\s*kg", text, re.IGNORECASE)
                        if fallback_kg:
                            multiplier = 1
                            single_val = float(fallback_kg.group(1))
                            unit = "kg"
                        else:
                            return default

        # Unit conversions to integer grams
        if unit in ("kg", "kilo"):
            single_grams = int(round(single_val * 1000))
        elif unit in ("g", "gm", "gram", "grams", "ml"):
            single_grams = int(round(single_val))
        elif unit in ("lb", "lbs"):
            # Industry packaging rounding (2.2 lbs = 1000g, 4.4 lbs = 2000g)
            if abs(single_val - 2.2) < 0.05:
                single_grams = 1000.0
            elif abs(single_val - 4.4) < 0.05:
                single_grams = 2000.0
            elif abs(single_val - 5.0) < 0.05:
                single_grams = 2268.0
            elif abs(single_val - 10.0) < 0.05:
                single_grams = 4536.0
            else:
                single_grams = single_val * 453.592
        elif unit == "oz":
            single_grams = single_val * 28.3495
        elif unit in ("floz", "fl.oz"):
            single_grams = single_val * 29.5735
        else:
            single_grams = 1000.0

        total_grams = int(round(multiplier * single_grams))
        # Plausibility sanity bounds (10g to 50kg)
        if total_grams <= 0 or total_grams > 50000:
            return default

        return total_grams

        return total_grams

    @classmethod
    def parse_flavor(cls, raw_title: Optional[str]) -> str:
        """
        Extracts and normalizes flavor into canonical taxonomy.
        """
        text = cls._clean_title(raw_title)
        if not text:
            return "unflavored"

        for pattern, canonical in cls.FLAVOR_CANONICAL_MAP.items():
            if re.search(pattern, text, re.IGNORECASE):
                return canonical

        return "unflavored"

    @staticmethod
    def compute_hash(product_id: str, weight_grams: int, canonical_flavor: str) -> str:
        """
        Deterministic Hash Specification (PRD Section 3.1 & 4.1):
        SHA256(product_id || weight_in_grams || canonical_flavor)
        Normalized: lowercased, whitespace-trimmed, alphanumeric standard.
        """
        pid = str(product_id or "").strip().lower()
        w = str(max(1, int(weight_grams))).strip()
        f = str(canonical_flavor or "unflavored").strip().lower()
        
        # Clean non-alphanumeric except hyphen/underscore
        clean_pid = re.sub(r'[^a-z0-9_-]', '', pid)
        clean_f = re.sub(r'[^a-z0-9_]', '', f)

        raw_signature = f"{clean_pid}_{w}_{clean_f}"
        return hashlib.sha256(raw_signature.encode('utf-8')).hexdigest()

    @classmethod
    def execute(cls, product_id: str, raw_title: str) -> NormalizedVariant:
        """
        Normalizes a scraped title into structured variant attributes and SHA256 hash.
        """
        weight_g = cls.parse_weight(raw_title)
        flavor = cls.parse_flavor(raw_title)
        v_hash = cls.compute_hash(product_id, weight_g, flavor)

        return NormalizedVariant(
            weight_grams=weight_g,
            canonical_flavor=flavor,
            variant_hash=v_hash
        )

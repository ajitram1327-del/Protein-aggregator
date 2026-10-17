import re
import os
import json
import hashlib
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

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
        Leverages StatefulTitleParser (Hierarchical consume-and-strip with canonical snapping)
        with regex fallback.
        """
        text = cls._clean_title(raw_title)
        if not text:
            return default

        # Delegate to high-precision StatefulTitleParser when available
        try:
            from src.pipeline.catalog_taxonomy import StatefulTitleParser
            parsed = StatefulTitleParser.parse(text)
            pack_cnt = int(parsed.pack_count) if (parsed.pack_count and parsed.pack_count > 1) else 1
            if parsed.raw_extracted_weight_g and parsed.raw_extracted_weight_g > 0:
                return int(round(parsed.raw_extracted_weight_g * pack_cnt))
            if parsed.bucketed_weight_g and parsed.bucketed_weight_g > 0:
                return int(round(parsed.bucketed_weight_g * pack_cnt))
        except (ImportError, Exception):
            pass

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


@dataclass
class CanonicalProductInfo:
    canonical_brand: str
    canonical_line: str
    canonical_full_name: str
    category_silo: str
    formulation: str
    is_bundle: bool = False
    bundle_reason: Optional[str] = None


class CanonicalProductNormalizer:
    """
    Normalizes divergent brand storefront & marketplace titles into canonical product lines.
    Strips retailer SEO stuffing, brand variations, marketing boilerplate, and embedded tub weights.
    Categorizes clean formulations (guaranteeing Isolate & Concentrate blends map to whey_blend).
    """

    _BASE_BRAND_ALIASES: Dict[str, str] = {
        "nakpro nutrition": "Nakpro",
        "nakpro": "Nakpro",
        "optimum nutrition (on)": "Optimum Nutrition",
        "optimum nutrition": "Optimum Nutrition",
        "(on)": "Optimum Nutrition",
        "on": "Optimum Nutrition",
        "muscleblaze": "MuscleBlaze",
        "mb": "MuscleBlaze",
        "as-it-is nutrition": "AS-IT-IS",
        "as-it-is": "AS-IT-IS",
        "asitis": "AS-IT-IS",
        "avvatar": "Avvatar",
        "gnc india": "GNC India",
        "gnc": "GNC India",
        "muscletech": "MuscleTech",
        "dymatize": "Dymatize",
        "bigmuscles nutrition": "Big Muscles Nutrition",
        "big muscles nutrition": "Big Muscles Nutrition",
        "bigmuscles": "Big Muscles Nutrition",
        "myprotein india": "Myprotein",
        "myprotein": "Myprotein",
        "isopure": "Isopure",
        "labrada": "Labrada",
        "nutrabay": "Nutrabay",
        "muscle nectar": "Muscle Nectar",
        "proburst": "Proburst",
        "naturaltein": "Naturaltein",
        "beast life": "Naturaltein",
        "oziva": "Oziva",
        "boldfit": "Boldfit",
        "fast&up": "Fast&Up",
        "wellcore": "Wellcore"
    }

    @classmethod
    def _build_brand_aliases(cls) -> Dict[str, str]:
        aliases = dict(cls._BASE_BRAND_ALIASES)
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "canonical_brands.json")
        if os.path.exists(data_path):
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    brands = json.load(f).get("brands", [])
                for b in brands:
                    c_name = b["brand"]
                    clean_c = re.sub(r"\(.*?\)", "", c_name).strip()
                    if c_name.lower() not in aliases:
                        aliases[c_name.lower()] = clean_c
                    cleaned = clean_c.lower()
                    if len(cleaned) >= 3 and cleaned not in aliases:
                        aliases[cleaned] = clean_c
                    stripped = re.sub(r"\b(nutrition|foods|life|sports|india)\b", "", cleaned).strip()
                    if len(stripped) >= 3 and stripped not in aliases:
                        aliases[stripped] = clean_c
                    for part in re.split(r"[/,]", c_name):
                        p = re.sub(r"\(.*?\)", "", part).strip().lower()
                        if len(p) >= 3 and p not in aliases:
                            aliases[p] = clean_c
                        p_strip = re.sub(r"\b(nutrition|foods|life|sports|india)\b", "", p).strip()
                        if len(p_strip) >= 3 and p_strip not in aliases:
                            aliases[p_strip] = clean_c
            except Exception:
                pass
        return aliases

    BRAND_ALIASES: Dict[str, str] = {}

    FLAVORS_ORDERED = [
        "double rich chocolate", "chocolate fudge", "belgian chocolate", "dark chocolate",
        "chocolate milkshake", "chocolate supreme", "cookies and cream", "cookies & cream",
        "cookies n cream", "vanilla ice cream", "french vanilla", "creamy vanilla",
        "cafe mocha", "cold coffee", "kesar pista", "kesar badam", "malai kulfi",
        "peanut butter", "banana cream", "salted caramel", "blue raspberry", "fruit punch",
        "green apple", "chocolate", "vanilla", "mango", "coffee", "strawberry",
        "unflavored", "unflavoured", "raw", "banana", "watermelon", "orange", "lemon", "cola"
    ]

    COMBO_PATTERNS = [
        re.compile(r"\b(combo|bundle|twin\s*pack|pack\s*of\s*[2-9]|buy\s*1\s*get\s*1|bogo)\b", re.I),
        re.compile(r"\b(free\s*(?:shaker|sipper|bottle|creatine|t-?shirt|multivitamin))\b", re.I),
        re.compile(r"\b(with\s+(?:free\s+)?(?:shaker|sipper|bottle|creatine|gym\s*bag|t-?shirt|vest))\b", re.I),
        re.compile(r"\b(creatine\s*(?:\+|and|&)\s*whey|whey\s*(?:\+|and|&)\s*creatine|pre[- ]?workout\s*(?:\+|and|&)\s*whey)\b", re.I),
        re.compile(r"\+\s*(?:free|shaker|sipper|bottle|creatine|pre[- ]?workout|gym\s*vest)", re.I),
        re.compile(r"(\d+(?:\.\d+)?\s*(?:kg|g|lbs?))\s*(?:\+|and|&)\s*(\d+(?:\.\d+)?\s*(?:kg|g|lbs?))", re.I),
        re.compile(r"\b(tablets?|capsules?|gummies|drops|syrup|chews?|softgels?|e-?cook\s*book|cookbook|e-?book|recipe|guide|vest|apparel)\b", re.I),
        re.compile(r"\b(?:plant[- ]based\s+)?(?:true\s+)?vitamin\s+[a-z0-9]+\b|\bmultivitamin\b|\bshilajit\b|\bashwagandha\b|\bspirulina\b", re.I),
    ]

    @classmethod
    def canonicalize_brand(cls, raw_brand: Optional[str], title: str) -> str:
        b_low = (raw_brand or "").lower().strip()
        if b_low in cls.BRAND_ALIASES:
            return cls.BRAND_ALIASES[b_low]
        t_low = (title or "").lower()
        for alias, canon in sorted(cls.BRAND_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", t_low):
                return canon
        return raw_brand.strip().title() if raw_brand else "Unknown"

    @classmethod
    def check_is_bundle(cls, title: str) -> Tuple[bool, Optional[str]]:
        for pat in cls.COMBO_PATTERNS:
            m = pat.search(title)
            if m:
                return True, m.group(0)
        return False, None

    @classmethod
    def detect_category_and_formulation(cls, text: str) -> Tuple[str, str]:
        t_low = text.lower()
        
        # 1. Category Silo detection
        if any(w in t_low for w in ["mass gainer", "weight gainer", "super gainer", "serious mass", "mega gainer"]):
            return "mass_gainers", "Mass Gainer"
        if any(w in t_low for w in ["creatine", "creapure"]):
            return "creatine", "Creatine Monohydrate"
        if any(w in t_low for w in ["pre workout", "pre-workout", "preworkout"]):
            return "pre_workout", "Pre-Workout"

        # 2. Snacks Silo detection (Wafers, Bars, Cookies, Brownies, Granola, Chips, RTD Milkshakes)
        # Exclude powder flavor names (e.g. "Cookies & Cream Whey Protein", "Chocolate Brownie Whey Isolate")
        is_powder_flavor = bool(re.search(r"\b(?:cookies\s*(?:and|&|n)\s*cream|chocolate\s*brownie|fudge\s*brownie)\b", t_low))
        has_powder_kw = bool(re.search(r"\b(?:whey|isolate|concentrate|casein|plant\s*protein|raw\s*whey|powder)\b", t_low))
        
        if re.search(r"\b(?:wafers?|granola|protein\s*spread|milkshake)\b", t_low):
            return "snacks", "Protein Snack"
        if re.search(r"\b(?:protein\s*bars?|energy\s*bars?|active\s*bar|snack\s*bars?|protein\s*bites?|protein\s*chips?|protein\s*crisps?)\b", t_low):
            return "snacks", "Protein Snack"
        if re.search(r"\b(?:cookies?|brownies?)\b", t_low):
            if not (is_powder_flavor and has_powder_kw and not re.search(r"\b(?:pack\s*of|box\s*of|piece|baked)\b", t_low)):
                return "snacks", "Protein Snack"

        # 3. Protein Formulations
        silo = "protein"
        if any(w in t_low for w in ["plant protein", "pea protein", "soy protein", "vegan protein", "brown rice protein", "organic plant", "plant-based protein", "yeast protein"]):
            return silo, "Plant"
        if "casein" in t_low:
            return silo, "Casein"
        
        # Crucial: If both isolate and concentrate are listed -> Whey Blend
        has_iso = bool(re.search(r"\bisolate\b|\bisopro\b|\biso-whey\b|\b100%\s*isolate\b|\biso\s*100\b", t_low))
        has_conc = bool(re.search(r"\bconcentrate\b|\braw whey\b|\b100%\s*whey\b", t_low))
        if has_iso and has_conc:
            return silo, "Whey Blend"
        if has_iso:
            return silo, "Whey Isolate"
        if has_conc:
            return silo, "Whey Concentrate"

        return silo, "Whey Blend"

    @classmethod
    def normalize_product(cls, raw_title: str, raw_brand: Optional[str] = None) -> CanonicalProductInfo:
        is_bundle, bundle_reason = cls.check_is_bundle(raw_title)
        canon_brand = cls.canonicalize_brand(raw_brand, raw_title)
        silo, formulation = cls.detect_category_and_formulation(raw_title)

        t = raw_title

        # Strip brand variations and brand tokens
        for b_pat in [
            r"\boptimum\s+nutrition\s*\(\s*on\s*\)", r"\boptimum\s+nutrition\b", r"\b\(on\)\b",
            r"\bnakpro\s+nutrition\b", r"\bnakpro\b",
            r"\bmuscleblaze\b", r"\bas\-it\-is\s+nutrition\b", r"\bas\-it\-is\b", r"\basitis\b",
            r"\bbigmuscles\s+nutrition\b", r"\bbig\s+muscles\s+nutrition\b", r"\bbigmuscles\b",
            r"\bgnc\s+india\b", r"\bgnc\b", r"\bmuscletech\b", r"\bdymatize\b", r"\bmyprotein\b",
            r"\bbrand\b", r"\bnutrition\b"
        ]:
            t = re.sub(b_pat, "", t, flags=re.IGNORECASE)

        # Strip nutrient claims and serving claims
        t = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|gm|grams?)\s*(?:of\s*)?(?:protein|bcaa|eaa|glutamine|creatine)(?:\s*(?:per|\/)\s*(?:serving|scoop))?\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\b\d+\s*(?:servings?|scoops?)\b", "", t, flags=re.IGNORECASE)

        # Strip packaging weights
        t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|g|gm|grams?|lbs?|pounds?|oz)\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\b\d+(?:\.\d+)?\s*\/\s*\d+(?:\.\d+)?\s*(?:kg|lbs?)\b", "", t, flags=re.IGNORECASE)

        # Strip flavor descriptors
        for f in cls.FLAVORS_ORDERED:
            t = re.sub(rf"\b{re.escape(f)}\b", "", t, flags=re.IGNORECASE)

        # Strip marketing blend noise
        t = re.sub(r"\b(?:protein\s+)?isolate\s*(?:&|\+|\band\b)\s*concentrate\b", "", t, flags=re.IGNORECASE)

        # Strip generic boilerplate
        boilerplate = [
            r"\b(?:whey\s+)?protein\s+powder\b",
            r"\b(?:health|dietary|sports)\s+supplement\b",
            r"\bprotein\s+supplement\b",
            r"\bprotein\s+shake\b",
            r"\bpowder\b",
            r"\bfor\s+(?:muscle\s+building|men\s+and\s+women|workout|recovery|fitness)\b",
            r"\b(?:ultra\s+)?filtered\b",
            r"\binstantized\b",
            r"\bclean\s+recovery\b",
            r"\bbetter\s+absorption\b",
            r"\beveryday\s+performance\b",
            r"\bdefault\s+title\b",
            r"\bwith\s+us\s+patent.*$",
            r"\bdigesting\s+supplement\b",
            r"\bhigh\s+protein\b",
            r"\bhigh\s+calorie\b",
            r"\bweight\s+gain.*$",
            r"\bwhey\s+protein\b",
            r"\bprotein\b"
        ]
        for b in boilerplate:
            t = re.sub(b, "", t, flags=re.IGNORECASE)

        t = re.sub(r"[\(\)\[\]\{\}\-\–\—\,\/\|\:\+]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()

        tokens = [w.capitalize() if not w.isupper() else w for w in t.split()]
        clean_line = " ".join(tokens)

        # Canonicalize established anchor product lines with Silo safety locks
        clean_low = clean_line.lower()
        raw_low = raw_title.lower()
        if silo == "pre_workout" or "pre workout" in raw_low or "pre-workout" in raw_low:
            silo = "pre_workout"
            if "gold standard" in raw_low:
                clean_line = "Gold Standard Pre-Workout"
            else:
                clean_line = f"{clean_line} Pre-Workout" if "pre" not in clean_line.lower() else clean_line
        elif silo == "creatine" or "creatine" in raw_low:
            silo = "creatine"
            if "micronized" in raw_low or "micronised" in raw_low:
                clean_line = "Micronized Creatine Powder"
            else:
                clean_line = "Creatine Monohydrate"
        elif silo == "mass_gainers" or "mass gainer" in raw_low or "weight gainer" in raw_low or "gainer" in raw_low:
            silo = "mass_gainers"
            if "atom" in clean_low:
                clean_line = "ATOM Mass Gainer"
            elif "serious mass" in raw_low:
                clean_line = "Serious Mass High Protein Weight Gainer"
            elif "super mass" in raw_low:
                clean_line = "Super Mass Gainer"
            else:
                clean_line = f"{clean_line} Mass Gainer" if "gainer" not in clean_line.lower() else clean_line
        elif "impact" in clean_low:
            clean_line = "Impact Whey"
        elif "biozyme" in clean_low:
            if "iso zero" in clean_low or "iso-zero" in clean_low:
                clean_line = "Biozyme Iso-Zero"
            elif "clear" in clean_low:
                clean_line = "Biozyme Clear Whey Isolate"
            else:
                clean_line = "Biozyme Performance Whey"
        elif "atom" in clean_low:
            if "isolate" in clean_low:
                clean_line = "ATOM Whey Isolate"
            elif "pea" in clean_low:
                clean_line = "ATOM Pea Protein"
            elif "plant" in clean_low:
                clean_line = "ATOM Plant Protein"
            elif "beginner" in clean_low:
                clean_line = "ATOM Beginners Whey"
            elif "performance" in clean_low:
                clean_line = "ATOM Performance Whey"
            else:
                clean_line = "ATOM Whey Protein"
        elif "perform" in clean_low:
            if "plus" in clean_low:
                clean_line = "Perform Plus Whey Concentrate"
            else:
                clean_line = "Perform Whey Concentrate"
        elif "gold standard" in clean_low:
            clean_line = "Gold Standard 100% Whey"
        elif "zero carb" in clean_low or "isopure" in canon_brand.lower():
            clean_line = "Zero Carb Whey Isolate"
        else:
            if not clean_line:
                clean_line = "Whey Protein" if silo == "protein" else "Supplement"

        canonical_full_name = f"{canon_brand} {clean_line}".strip()
        canonical_full_name = re.sub(r"\s+", " ", canonical_full_name)

        return CanonicalProductInfo(
            canonical_brand=canon_brand,
            canonical_line=clean_line,
            canonical_full_name=canonical_full_name,
            category_silo=silo,
            formulation=formulation,
            is_bundle=is_bundle,
            bundle_reason=bundle_reason
        )

# Initialize brand aliases dynamically from canonical dataset
CanonicalProductNormalizer.BRAND_ALIASES = CanonicalProductNormalizer._build_brand_aliases()


"""
src/pipeline/nutrition_ocr_pipeline.py
Deterministic Nutrition Label OCR, Perceptual Hash Deduplication,
Spatial Row-Bounding-Box OCR Parser, Atwater Thermodynamic Validator,
and Amino-Spiking Telemetry Feed.
"""

import os
import re
import io
import math
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from PIL import Image, ImageFilter, ImageStat

# Optional imports for image hashing / LLM fallback
try:
    import imagehash
except ImportError:
    imagehash = None

try:
    from src.trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
except ImportError:
    try:
        from trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
    except ImportError:
        AminoSpikingRulesEngine = None


@dataclass
class BoundingBoxWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float = 1.0


@dataclass
class NutritionFactsPayload:
    # Core sizing
    serving_size_g: float = 0.0
    servings_per_container: int = 0
    bucketed_weight_g: Optional[int] = None
    derived_weight_g: Optional[float] = None
    
    # Core macros (Per Serving)
    energy_kcal: float = 0.0
    protein_per_serving_g: float = 0.0
    carbs_per_serving_g: float = 0.0
    total_sugars_g: float = 0.0
    added_sugars_g: float = 0.0
    fat_per_serving_g: float = 0.0
    sodium_mg: float = 0.0
    
    # Optional Per 100g columns
    per_100g_protein: Optional[float] = None
    per_100g_energy: Optional[float] = None

    # Free-form / Cheap nitrogen spikers (g per serving)
    glycine_g: float = 0.0
    taurine_g: float = 0.0
    creatine_g: float = 0.0
    l_glutamine_g: float = 0.0
    l_arginine_g: float = 0.0
    l_alanine_g: float = 0.0

    # True intact protein markers (BCAA / EAA Profile)
    l_leucine_g: float = 0.0
    l_isoleucine_g: float = 0.0
    l_valine_g: float = 0.0
    total_bcaa_g: float = 0.0
    total_eaa_g: float = 0.0

    # Ingredient statements & flags
    raw_ingredients_text: str = ""
    ingredients_ordered: List[str] = field(default_factory=list)
    has_added_free_form_aminos: bool = False
    protein_claim_basis: str = "as_is"  # "as_is" or "dry_basis"

    # Pre-computed telemetry ratios
    protein_concentration_pct: float = 0.0
    leucine_to_protein_ratio: float = 0.0
    bcaa_to_protein_ratio: float = 0.0
    spiking_nitrogen_delta_g: float = 0.0
    true_protein_g: float = 0.0

    # Integrated Amino Spiking Engine Audit (Proteindex PRD v2.1 & v3)
    amino_spiking_audit: Dict[str, Any] = field(default_factory=dict)

    # Validation flags
    is_valid_physics: bool = False
    physics_validation_notes: List[str] = field(default_factory=list)
    extraction_source: str = "spatial_ocr"  # "spatial_ocr", "phash_cache", "vision_llm"
    image_phash: Optional[str] = None

    def execute_amino_spiking_audit(self, category_silo: str = "protein") -> Dict[str, Any]:
        """
        Executes audit against our AminoSpikingRulesEngine using the extracted OCR panel data.
        Returns full audit payload including riskLevel, trustDeduction, and mpsAnalysis.
        """
        if AminoSpikingRulesEngine is not None:
            audit = AminoSpikingRulesEngine.evaluate(
                raw_ingredients=self.raw_ingredients_text,
                declared_protein_g=self.protein_per_serving_g or 24.0,
                declared_leucine_g=self.l_leucine_g if self.l_leucine_g > 0 else None,
                serving_size_g=self.serving_size_g or 30.0,
                category=category_silo
            )
            self.amino_spiking_audit = audit
            return audit
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PerceptualHashDeduplicator:
    """
    Stage 0: Computes 8x8 perceptual image hash (pHash) and normalizes image URLs.
    Checks memory/database cache to avoid re-running heavy OCR when identical images
    appear across different marketplace platforms (e.g. Amazon, Flipkart, HealthKart).
    """

    @staticmethod
    def normalize_image_url(url: str) -> str:
        """Strip dynamic resize query params and trailing CDN tokens."""
        if not url:
            return ""
        # Remove query string
        clean_url = url.split("?")[0].split("#")[0].strip()
        # Strip common Amazon image scaling modifiers like ._AC_SX679_
        clean_url = re.sub(r"\._[A-Z0-9_,]+_\.", ".", clean_url)
        return clean_url

    @staticmethod
    def compute_phash(image_bytes: bytes) -> str:
        """
        Computes 64-bit perceptual hash (pHash).
        Falls back to 8x8 DCT/grayscale difference if imagehash library is absent.
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if imagehash is not None:
                return str(imagehash.phash(img))
            
            # Pure PIL fallback: 8x8 grayscale dHash
            img = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            diff = []
            for row in range(8):
                for col in range(8):
                    pixel_left = pixels[row * 9 + col]
                    pixel_right = pixels[row * 9 + col + 1]
                    diff.append("1" if pixel_left > pixel_right else "0")
            bit_string = "".join(diff)
            return f"{int(bit_string, 2):016x}"
        except Exception as e:
            # Fallback to MD5 if image parsing fails
            return hashlib.md5(image_bytes).hexdigest()[:16]


class LabelCandidateClassifier:
    """
    Stage 1: Fast Label Candidate Classifier (< 15ms).
    Rejects front-of-tub hero shots and lifestyle banners via OpenCV / PIL heuristics
    and table contour / text-density / anchor-keyword checks.
    """

    LABEL_ANCHOR_KEYWORDS = [
        "supplement facts", "nutritional information", "nutrition facts",
        "serving size", "servings per container", "per serve", "per serving",
        "amino acid profile", "typical amino acid", "ingredients", "approximate composition",
        "energy", "protein", "carbohydrate"
    ]

    @classmethod
    def is_likely_nutrition_label(cls, image_bytes: bytes, fast_ocr_text: Optional[str] = None) -> bool:
        """
        1. Dimension Gate: Minimum 250x250.
        2. Aspect Ratio Gate: 0.35 <= ratio <= 1.6 (Rejects wide banners).
        3. Variance & Contrast Gate: High grayscale standard deviation (stddev >= 20).
        4. High-Frequency Edge Energy: mean >= 10.0 (Tabular text & gridlines).
        5. Fast Keyword Check (if partial text available).
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size

            # 1. Dimension Gate
            if w < 250 or h < 250:
                return False

            # 2. Aspect Ratio Gate
            aspect = w / float(h)
            if aspect < 0.35 or aspect > 1.6:
                return False

            gray = img.convert("L")

            # 3. Variance & Contrast Gate
            stat = ImageStat.Stat(gray)
            if stat.stddev[0] < 20.0:
                return False

            # 4. Edge Density Gate
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            if edge_stat.mean[0] < 10.0:
                return False

            # 5. Anchor keywords check if sample OCR text is passed
            if fast_ocr_text:
                low_text = fast_ocr_text.lower()
                matches = sum(1 for kw in cls.LABEL_ANCHOR_KEYWORDS if kw in low_text)
                if matches >= 1:
                    return True

            return True
        except Exception:
            return False


class SpatialRowBoundingBoxParser:
    """
    Stage 2: Spatial Bounding-Box Coordinate Extraction.
    Solves the "Per Serving" vs "Per 100g" Column Trap on Indian & international nutrition labels.
    Groups OCR tokens into horizontal rows by Y-coordinate and detects column X-anchors.
    """

    ROW_HEIGHT_THRESHOLD_RATIO = 0.7  # Fraction of word height to cluster into row

    @classmethod
    def parse_bounding_boxes(
        cls,
        words: List[BoundingBoxWord],
        raw_text_fallback: str = ""
    ) -> NutritionFactsPayload:
        payload = NutritionFactsPayload()

        if not words:
            # Fallback to text parsing if no bounding boxes are supplied
            return cls._parse_raw_text(raw_text_fallback)

        # 1. Cluster words into horizontal rows by Y-coordinate
        # Sort words primarily by top Y-coordinate, secondarily by X0
        sorted_words = sorted(words, key=lambda w: (w.y0, w.x0))
        rows: List[List[BoundingBoxWord]] = []

        for w in sorted_words:
            matched_row = False
            for row in rows:
                # Compare Y-overlap with row representative
                rep = row[0]
                avg_height = (rep.y1 - rep.y0 + w.y1 - w.y0) / 2.0
                if abs(w.y0 - rep.y0) <= max(6.0, avg_height * cls.ROW_HEIGHT_THRESHOLD_RATIO):
                    row.append(w)
                    matched_row = True
                    break
            if not matched_row:
                rows.append([w])

        # Sort words inside each row by X0 (left-to-right)
        for row in rows:
            row.sort(key=lambda w: w.x0)

        # 2. Detect Header Columns (Per Serving vs Per 100g vs % RDA)
        per_serve_x_center = None
        per_100g_x_center = None

        for row in rows:
            row_text = " ".join(w.text for w in row).lower()
            if "per" in row_text or "100" in row_text or "serving" in row_text or "serve" in row_text:
                for idx, w in enumerate(row):
                    t = w.text.lower()
                    if "serving" in t or "serve" in t or "scoop" in t:
                        per_serve_x_center = (w.x0 + w.x1) / 2.0
                    elif "100" in t or "100g" in t or "100 g" in t:
                        per_100g_x_center = (w.x0 + w.x1) / 2.0

        # 3. Extract Row-by-Row Values
        full_extracted_lines = []
        for row in rows:
            row_text = " ".join(w.text for w in row)
            full_extracted_lines.append(row_text)
            low_row = row_text.lower()

            # Serving Size extraction
            if "serving size" in low_row or "per serve" in low_row or "serving" in low_row and "size" in low_row:
                cls._extract_serving_size(row_text, payload)

            # Servings Per Container
            if "servings per container" in low_row or "no. of servings" in low_row or "servings:" in low_row or "servings per pack" in low_row:
                cls._extract_servings_count(row_text, payload)

            # Protein row
            if "protein" in low_row and not any(k in low_row for k in ["source", "ingredients", "whey protein", "isolate"]):
                val_serving, val_100g = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.protein_per_serving_g == 0.0:
                    payload.protein_per_serving_g = val_serving
                if val_100g is not None and payload.per_100g_protein is None:
                    payload.per_100g_protein = val_100g

            # Energy / Calories row
            if "energy" in low_row or "calories" in low_row or "kcal" in low_row:
                val_serving, val_100g = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.energy_kcal == 0.0:
                    payload.energy_kcal = val_serving
                if val_100g is not None and payload.per_100g_energy is None:
                    payload.per_100g_energy = val_100g

            # Carbohydrates row
            if "carbohydrate" in low_row or "carbs" in low_row:
                val_serving, _ = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.carbs_per_serving_g == 0.0:
                    payload.carbs_per_serving_g = val_serving

            # Total Sugars / Added Sugars
            if "added sugar" in low_row or "added sugars" in low_row:
                val_serving, _ = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None:
                    payload.added_sugars_g = val_serving
            elif "sugar" in low_row or "sugars" in low_row:
                val_serving, _ = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.total_sugars_g == 0.0:
                    payload.total_sugars_g = val_serving

            # Fat row
            if "fat" in low_row and "safety" not in low_row:
                val_serving, _ = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.fat_per_serving_g == 0.0:
                    payload.fat_per_serving_g = val_serving

            # Sodium row
            if "sodium" in low_row or "salt" in low_row:
                val_serving, _ = cls._extract_column_values_from_row(row, per_serve_x_center, per_100g_x_center)
                if val_serving is not None and payload.sodium_mg == 0.0:
                    payload.sodium_mg = val_serving

        # Extract Amino Acid Profile & Ingredients from full text
        full_text = "\n".join(full_extracted_lines) + "\n" + raw_text_fallback
        cls._extract_aminos_and_ingredients(full_text, payload)

        return payload

    @classmethod
    def _extract_column_values_from_row(
        cls,
        row: List[BoundingBoxWord],
        per_serve_x: Optional[float],
        per_100g_x: Optional[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Assigns numerical values in a row to the 'Per Serving' vs 'Per 100g' column
        based on X-coordinate proximity to header anchors.
        """
        # Find all numerical words in the row
        num_candidates = []
        for w in row:
            clean_num = re.sub(r"[^\d\.]", "", w.text)
            if clean_num:
                try:
                    val = float(clean_num)
                    num_candidates.append((val, (w.x0 + w.x1) / 2.0, w))
                except ValueError:
                    pass

        if not num_candidates:
            return None, None

        if len(num_candidates) == 1:
            # If only one number exists, assign to per_serving
            return num_candidates[0][0], None

        # When two or more numbers exist, use X-anchors if available
        if per_serve_x is not None and per_100g_x is not None:
            val_serving = None
            val_100g = None
            for val, x_center, _ in num_candidates:
                dist_serve = abs(x_center - per_serve_x)
                dist_100g = abs(x_center - per_100g_x)
                if dist_serve < dist_100g:
                    if val_serving is None or dist_serve < abs(num_candidates[0][1] - per_serve_x):
                        val_serving = val
                else:
                    if val_100g is None:
                        val_100g = val
            return val_serving, val_100g

        # Fallback if no header anchors: in Indian/US nutrition tables,
        # Column 1 is typically Per Serving (smaller), Column 2 is Per 100g (larger)
        num_candidates.sort(key=lambda x: x[1])  # left to right
        first_num = num_candidates[0][0]
        second_num = num_candidates[1][0]
        return first_num, second_num

    @classmethod
    def _extract_serving_size(cls, text: str, payload: NutritionFactsPayload):
        # e.g., "Serving Size: 1 Scoop (32g)" or "Serving Size: 30 g" or "Per Serve 33 g"
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gm|grams?)\b", text, re.I)
        if m:
            payload.serving_size_g = float(m.group(1))

    @classmethod
    def _extract_servings_count(cls, text: str, payload: NutritionFactsPayload):
        # e.g., "Servings Per Container: ~30" or "No. of Servings: 33"
        m = re.search(r"(?:servings?|pack|container)?\s*[:\-~]?\s*(\d+)\b", text, re.I)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 500:
                payload.servings_per_container = num

    @classmethod
    def _parse_raw_text(cls, text: str) -> NutritionFactsPayload:
        payload = NutritionFactsPayload()
        cls._extract_serving_size(text, payload)
        cls._extract_servings_count(text, payload)

        # Protein
        m_prot = re.search(r"\bprotein\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|gm)?", text, re.I)
        if m_prot:
            payload.protein_per_serving_g = float(m_prot.group(1))

        # Energy / Calories
        m_kcal = re.search(r"\b(?:energy|calories|kcal)\b[^\d\n]*?(\d+(?:\.\d+)?)", text, re.I)
        if m_kcal:
            payload.energy_kcal = float(m_kcal.group(1))

        # Carbs
        m_carb = re.search(r"\b(?:carbohydrates?|carbs?)\b[^\d\n]*?(\d+(?:\.\d+)?)", text, re.I)
        if m_carb:
            payload.carbs_per_serving_g = float(m_carb.group(1))

        # Sugars
        m_sugar = re.search(r"\b(?:total\s+)?sugars?\b[^\d\n]*?(\d+(?:\.\d+)?)", text, re.I)
        if m_sugar:
            payload.total_sugars_g = float(m_sugar.group(1))

        # Fat
        m_fat = re.search(r"\b(?:total\s+)?fat\b[^\d\n]*?(\d+(?:\.\d+)?)", text, re.I)
        if m_fat:
            payload.fat_per_serving_g = float(m_fat.group(1))

        cls._extract_aminos_and_ingredients(text, payload)
        return payload

    @classmethod
    def _extract_aminos_and_ingredients(cls, text: str, payload: NutritionFactsPayload):
        """
        Stage 3: Extracts free-form aminos, BCAA profile, ingredients list,
        and computes telemetry ratios for the Amino-Spiking engine.
        """
        low = text.lower()

        # Free-form aminos / cheap nitrogen donors
        amino_patterns = {
            "glycine_g": r"\b(?:l-)?glycine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "taurine_g": r"\b(?:l-)?taurine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "creatine_g": r"\bcreatine(?:\s+monohydrate)?\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_glutamine_g": r"\b(?:l-)?glutamine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_arginine_g": r"\b(?:l-)?arginine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_alanine_g": r"\b(?:l-)?alanine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_leucine_g": r"\b(?:l-)?leucine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_isoleucine_g": r"\b(?:l-)?isoleucine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "l_valine_g": r"\b(?:l-)?valine\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "total_bcaa_g": r"\b(?:total\s+)?bcaas?\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
            "total_eaa_g": r"\b(?:total\s+)?eaas?\b[^\d\n]*?(\d+(?:\.\d+)?)\s*(?:g|mg|gm)?",
        }

        for attr, pat in amino_patterns.items():
            m = re.search(pat, low)
            if m:
                val = float(m.group(1))
                # Check if unit in context is mg -> convert to g
                matched_span = low[m.start():m.end() + 5]
                if "mg" in matched_span and val > 50:
                    val = val / 1000.0
                setattr(payload, attr, val)

        # Ingredients list extraction
        ing_match = re.search(r"ingredients\s*[:\-]\s*(.*?)(?:\n\s*\n|nutrition|directions|contains|allergen|$)", text, re.I | re.DOTALL)
        if ing_match:
            raw_ing = ing_match.group(1).strip()
            payload.raw_ingredients_text = raw_ing
            # Split ordered tokens
            tokens = [t.strip().rstrip(".") for t in re.split(r"[,;]", raw_ing) if t.strip()]
            payload.ingredients_ordered = tokens

            # Check for added free form aminos in ingredient list
            spiking_keywords = ["glycine", "l-glycine", "taurine", "l-taurine", "creatine monohydrate", "creatine"]
            has_spiker = any(sk in raw_ing.lower() for sk in spiking_keywords)
            payload.has_added_free_form_aminos = has_spiker

        # Protein claim basis
        if "dry basis" in low:
            payload.protein_claim_basis = "dry_basis"
        else:
            payload.protein_claim_basis = "as_is"

        # Pre-compute Amino Spiking Engine ratios
        if payload.serving_size_g > 0 and payload.protein_per_serving_g > 0:
            payload.protein_concentration_pct = round((payload.protein_per_serving_g / payload.serving_size_g) * 100.0, 2)
            
            if payload.l_leucine_g > 0:
                payload.leucine_to_protein_ratio = round(payload.l_leucine_g / payload.protein_per_serving_g, 3)
            
            if payload.total_bcaa_g > 0:
                payload.bcaa_to_protein_ratio = round(payload.total_bcaa_g / payload.protein_per_serving_g, 3)

            # Spiking Nitrogen Delta: estimated inflated protein from added Creatine/Glycine/Taurine
            # Nitrogen multiplier equivalents: Creatine * 1.81, Glycine * 1.16, Taurine * 0.70
            delta = (payload.creatine_g * 1.81) + (payload.glycine_g * 1.16) + (payload.taurine_g * 0.70)
            payload.spiking_nitrogen_delta_g = round(delta, 2)
            payload.true_protein_g = max(0.0, round(payload.protein_per_serving_g - delta, 2))
        else:
            payload.true_protein_g = payload.protein_per_serving_g

        # Auto-trigger integrated Amino Spiking Rules Engine
        payload.execute_amino_spiking_audit()


class AtwaterThermodynamicValidator:
    """
    Stage 4: Deterministic Physics & Atwater Thermodynamic Sanity Validator.
    Every OCR extraction MUST pass physical laws before entering the database.
    """

    @classmethod
    def validate_and_correct(
        cls,
        payload: NutritionFactsPayload,
        bucketed_weight_g: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        notes: List[str] = []

        if payload.serving_size_g <= 0.0:
            notes.append("Invalid serving_size_g <= 0")
            payload.is_valid_physics = False
            payload.physics_validation_notes = notes
            return False, notes

        # -------------------------------------------------------------
        # Rule 1: Decimal Point Auto-Correction
        # -------------------------------------------------------------
        # OCR frequently misreads decimals (e.g., 24.0g -> 240g, 1.5g -> 15g)
        if payload.protein_per_serving_g > payload.serving_size_g:
            if (payload.protein_per_serving_g / 10.0) <= payload.serving_size_g:
                notes.append(f"Auto-corrected protein decimal: {payload.protein_per_serving_g}g -> {payload.protein_per_serving_g / 10.0}g")
                payload.protein_per_serving_g = round(payload.protein_per_serving_g / 10.0, 2)
            else:
                notes.append(f"Physical violation: protein ({payload.protein_per_serving_g}g) > serving size ({payload.serving_size_g}g)")
                payload.is_valid_physics = False
                payload.physics_validation_notes = notes
                return False, notes

        if payload.carbs_per_serving_g > payload.serving_size_g:
            if (payload.carbs_per_serving_g / 10.0) <= payload.serving_size_g:
                payload.carbs_per_serving_g = round(payload.carbs_per_serving_g / 10.0, 2)

        if payload.fat_per_serving_g > payload.serving_size_g:
            if (payload.fat_per_serving_g / 10.0) <= payload.serving_size_g:
                payload.fat_per_serving_g = round(payload.fat_per_serving_g / 10.0, 2)

        # -------------------------------------------------------------
        # Rule 2: Conservation of Mass
        # protein_g + carbs_g + fat_g <= serving_size_g * 1.05 (5% tolerance)
        # -------------------------------------------------------------
        sum_macros = payload.protein_per_serving_g + payload.carbs_per_serving_g + payload.fat_per_serving_g
        max_allowed_mass = payload.serving_size_g * 1.05
        if sum_macros > max_allowed_mass:
            notes.append(f"Conservation of mass violated: sum({sum_macros:.1f}g) > serving_size({payload.serving_size_g}g * 1.05)")
            payload.is_valid_physics = False
            payload.physics_validation_notes = notes
            return False, notes

        # Purity check: Even pure whey isolate tops out around 90-93% active yields
        purity_pct = (payload.protein_per_serving_g / payload.serving_size_g) * 100.0 if payload.serving_size_g > 0 else 0.0
        if purity_pct > 96.0:
            notes.append(f"PHYSICS VIOLATION: Calculated purity {purity_pct:.1f}% exceeds maximum natural powder ceiling of 96.0%")
            payload.is_valid_physics = False
            payload.physics_validation_notes = notes
            return False, notes

        # -------------------------------------------------------------
        # Rule 3: Atwater Calorie Cross-Check
        # Expected kcal = (4 * protein) + (4 * carbs) + (9 * fat)
        # 15% tolerance for fiber/polyols
        # -------------------------------------------------------------
        if payload.energy_kcal > 0:
            expected_kcal = (4.0 * payload.protein_per_serving_g) + (4.0 * payload.carbs_per_serving_g) + (9.0 * payload.fat_per_serving_g)
            kcal_diff_ratio = abs(expected_kcal - payload.energy_kcal) / payload.energy_kcal
            if kcal_diff_ratio > 0.15:
                notes.append(f"Atwater calorie discrepancy: expected ~{expected_kcal:.1f} kcal vs declared {payload.energy_kcal:.1f} kcal (diff {kcal_diff_ratio*100:.1f}%)")
                payload.is_valid_physics = False
                payload.physics_validation_notes = notes
                return False, notes

        # -------------------------------------------------------------
        # Rule 4: Container Weight Consistency
        # Derived Weight = serving_size_g * servings_per_container
        # Within +-12% of bucketed_weight_g
        # -------------------------------------------------------------
        if payload.servings_per_container > 0:
            payload.derived_weight_g = round(payload.serving_size_g * payload.servings_per_container, 1)
            if bucketed_weight_g and bucketed_weight_g > 0:
                diff_weight_ratio = abs(payload.derived_weight_g - bucketed_weight_g) / float(bucketed_weight_g)
                if diff_weight_ratio > 0.12:
                    notes.append(f"Container weight mismatch: derived {payload.derived_weight_g}g vs bucketed {bucketed_weight_g}g (diff {diff_weight_ratio*100:.1f}%)")
        elif bucketed_weight_g and bucketed_weight_g > 0 and payload.serving_size_g > 0:
            # Impute missing servings_per_container
            payload.servings_per_container = int(round(bucketed_weight_g / payload.serving_size_g))
            payload.derived_weight_g = float(bucketed_weight_g)
            notes.append(f"Imputed servings_per_container = {payload.servings_per_container} from bucketed weight {bucketed_weight_g}g")

        # Recalculate ratios
        payload.protein_concentration_pct = round((payload.protein_per_serving_g / payload.serving_size_g) * 100.0, 2)
        if payload.l_leucine_g > 0:
            payload.leucine_to_protein_ratio = round(payload.l_leucine_g / payload.protein_per_serving_g, 3)

        delta = (payload.creatine_g * 1.81) + (payload.glycine_g * 1.16) + (payload.taurine_g * 0.70)
        payload.spiking_nitrogen_delta_g = round(delta, 2)
        payload.true_protein_g = max(0.0, round(payload.protein_per_serving_g - delta, 2))

        payload.is_valid_physics = True
        payload.physics_validation_notes = notes
        return True, notes


class NutritionOCRPipeline:
    """
    End-to-End Orchestrator:
    Stage 0 (pHash Deduplication) -> Stage 1 (Fast Classifier) ->
    Stage 2 (Spatial Bounding-Box Parser) -> Stage 3 (Amino Spiking Extraction) ->
    Stage 4 (Deterministic Physics Validator) -> Optional Stage 5 (Vision LLM Fallback).
    """

    def __init__(self, in_memory_phash_cache: Optional[Dict[str, NutritionFactsPayload]] = None):
        self.phash_cache: Dict[str, NutritionFactsPayload] = in_memory_phash_cache or {}

    def process_image(
        self,
        image_bytes: bytes,
        image_url: str = "",
        words: Optional[List[BoundingBoxWord]] = None,
        raw_text_fallback: str = "",
        bucketed_weight_g: Optional[int] = None
    ) -> Optional[NutritionFactsPayload]:
        # Stage 0: pHash & URL Deduplication Cache
        phash = PerceptualHashDeduplicator.compute_phash(image_bytes)
        if phash in self.phash_cache:
            cached = self.phash_cache[phash]
            cached.extraction_source = "phash_cache"
            return cached

        # Stage 1: Fast Label Candidate Classifier
        if not LabelCandidateClassifier.is_likely_nutrition_label(image_bytes, raw_text_fallback):
            return None

        # Stage 2 & 3: Spatial Bounding-Box OCR & Amino Extraction
        payload = SpatialRowBoundingBoxParser.parse_bounding_boxes(words or [], raw_text_fallback)
        payload.image_phash = phash

        # Stage 4: Deterministic Physics & Atwater Sanity Check
        is_valid, _ = AtwaterThermodynamicValidator.validate_and_correct(payload, bucketed_weight_g)

        if is_valid:
            self.phash_cache[phash] = payload
            return payload

        # Stage 5: Vision LLM Fallback (if physics failed due to distortion/OCR decimal error)
        llm_payload = self._vision_llm_fallback(image_bytes, bucketed_weight_g)
        if llm_payload:
            self.phash_cache[phash] = llm_payload
            return llm_payload

        return None

    def _vision_llm_fallback(
        self,
        image_bytes: bytes,
        bucketed_weight_g: Optional[int]
    ) -> Optional[NutritionFactsPayload]:
        """
        Invoked selectively when local spatial OCR fails physics sanity.
        Calls Gemini / Groq Vision with strict JSON schema.
        """
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            return None

        try:
            from google import genai
            from google.genai import types
            from pydantic import BaseModel, Field

            class StrictNutritionSchema(BaseModel):
                serving_size_g: float = Field(..., description="Serving scoop weight in grams")
                servings_per_container: int = Field(default=30, description="Total servings per tub")
                energy_kcal: float = Field(..., description="Energy per serving in kcal")
                protein_per_serving_g: float = Field(..., description="Protein grams per serving")
                carbs_per_serving_g: float = Field(default=0.0, description="Carbohydrates in grams")
                fat_per_serving_g: float = Field(default=0.0, description="Fat in grams")
                raw_ingredients: str = Field(default="", description="Full ingredients list")
                leucine_g: Optional[float] = Field(default=None, description="Leucine per serving")
                creatine_g: Optional[float] = Field(default=0.0, description="Added creatine per serving")
                glycine_g: Optional[float] = Field(default=0.0, description="Added glycine per serving")
                taurine_g: Optional[float] = Field(default=0.0, description="Added taurine per serving")

            client = genai.Client(api_key=gemini_api_key)
            prompt = "Extract exact quantitative nutrition facts per serving. Obey conservation of mass and Atwater factors."

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StrictNutritionSchema,
                    temperature=0.0
                )
            )

            import json
            data = json.loads(response.text)
            payload = NutritionFactsPayload(
                serving_size_g=data.get("serving_size_g", 0.0),
                servings_per_container=data.get("servings_per_container", 0),
                energy_kcal=data.get("energy_kcal", 0.0),
                protein_per_serving_g=data.get("protein_per_serving_g", 0.0),
                carbs_per_serving_g=data.get("carbs_per_serving_g", 0.0),
                fat_per_serving_g=data.get("fat_per_serving_g", 0.0),
                raw_ingredients_text=data.get("raw_ingredients", ""),
                l_leucine_g=data.get("leucine_g") or 0.0,
                creatine_g=data.get("creatine_g") or 0.0,
                glycine_g=data.get("glycine_g") or 0.0,
                taurine_g=data.get("taurine_g") or 0.0,
                extraction_source="vision_llm"
            )

            payload.execute_amino_spiking_audit()
            is_valid, _ = AtwaterThermodynamicValidator.validate_and_correct(payload, bucketed_weight_g)
            if is_valid:
                return payload
        except Exception:
            pass

        return None

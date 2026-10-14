import json
import logging
from typing import Optional, Dict, Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger("VisionLabelAuditor")

class NutritionLabelSchema(BaseModel):
    serving_size_g: float = Field(..., description="Weight of one scoop in grams")
    protein_per_serving_g: float = Field(..., description="Grams of protein per single scoop")
    total_servings: int = Field(..., description="Total number of scoops/servings per container")
    detected_enzymes: list[str] = Field(default=[], description="Detected digestive enzymes: DigeZyme, Lactase, Papain, etc.")
    contains_lactose: bool = Field(default=True, description="Flag indicating presence of whey concentrate or lactose")
    raw_ingredients_list: str = Field(default="", description="The full, raw comma-separated list of ingredients extracted exactly as written on the label.")

class VisionLabelAuditor:
    """
    Multimodal image analysis extracting nutrition panels with structured JSON schema.
    Uses Gemini Flash for high-precision extraction on complex Indian supplement labels.
    """
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.quota_exhausted = False

    @staticmethod
    def is_likely_nutrition_panel(image_bytes: bytes) -> bool:
        """
        Hardened local PIL heuristic pre-filter (Zero API cost, < 2ms execution):
        1. Dimension Gate: Minimum 250x250 to ensure tabular text is legibly resolvable.
        2. Aspect Ratio Gate: Nutrition tables are portrait or square (0.35 <= ratio <= 1.6). Rejects wide promo banners.
        3. Variance & Contrast Gate: High text tables exhibit high grayscale standard deviation (stddev >= 22).
        4. Edge Density Gate: Convolves image with FIND_EDGES filter. High-density tabular text and gridlines
           generate edge energy (mean >= 11.0). Smooth glossy plastic tubs and lifestyle photos average 3-7 and are rejected.
        """
        try:
            import io
            from PIL import Image, ImageStat, ImageFilter

            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size

            # 1. Size Gate
            if width < 250 or height < 250:
                logger.info(f"[Pre-Filter REJECT]: Image too small for OCR ({width}x{height})")
                return False

            # 2. Aspect Ratio Gate
            aspect_ratio = width / float(height)
            if aspect_ratio > 1.6 or aspect_ratio < 0.35:
                logger.info(f"[Pre-Filter REJECT]: Aspect ratio {aspect_ratio:.2f} is a banner, not a nutrition panel.")
                return False

            gray = img.convert('L')

            # 3. Grayscale Contrast / Variance Gate
            stat = ImageStat.Stat(gray)
            stddev = stat.stddev[0]
            if stddev < 22:
                logger.info(f"[Pre-Filter REJECT]: Low contrast/entropy (stddev={stddev:.1f} < 22), not a text table.")
                return False

            # 4. High-Frequency Edge Energy Gate (Distinguishes text tables from glossy plastic tubs)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            edge_mean = edge_stat.mean[0]
            if edge_mean < 11.0:
                logger.info(f"[Pre-Filter REJECT]: Low edge density ({edge_mean:.1f} < 11.0). Image is a smooth tub/photo, not a tabular factsheet.")
                return False

            logger.info(f"[Pre-Filter PASS]: Verified nutrition panel candidate (size={width}x{height}, ratio={aspect_ratio:.2f}, edge_mean={edge_mean:.1f})")
            return True
        except Exception as e:
            logger.warning(f"Pre-filter evaluation error: {e}")
            return False

    def extract_label_data(self, image_bytes: bytes) -> Optional[NutritionLabelSchema]:
        if self.quota_exhausted:
            return None

        # 0. Local Pre-Filter Pass (Saves up to 85% AI Vision API calls)
        if not self.is_likely_nutrition_panel(image_bytes):
            return None

        prompt = """
        Analyze this dietary supplement nutritional panel.
        Extract exact quantitative values for serving size, protein per serving, and total servings.
        Identify any listed digestive enzyme complexes (e.g., DigeZyme, Pepsin, Papain).
        Extract the raw ingredient list in descending order.
        Adhere strictly to the JSON schema.
        """
        for model_name in ['gemini-3.5-flash-lite', 'gemini-flash-latest']:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=NutritionLabelSchema,
                        temperature=0.0
                    )
                )
                if response and response.text:
                    parsed = NutritionLabelSchema.model_validate_json(response.text)
                    # Mathematical sanity check
                    if parsed.serving_size_g > 0 and parsed.protein_per_serving_g > 0 and parsed.protein_per_serving_g <= parsed.serving_size_g:
                        return parsed
            except Exception as e:
                err_str = str(e).lower()
                logger.warning(f"Gemini model {model_name} extraction attempt error: {e}")
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    logger.warning("Gemini Vision API quota exhausted (429). Circuit breaker tripped: skipping Vision OCR for remaining run.")
                    self.quota_exhausted = True
                    return None
                continue
        return None

    def verify_discrepancy(self, scraped_servings: int, scraped_protein_g: float, ocr_data: NutritionLabelSchema) -> bool:
        """
        Returns True if the OCR data diverges from scraped data,
        indicating the OCR data should be persisted as the canonical source-of-truth.
        """
        delta_servings = abs(scraped_servings - ocr_data.total_servings)
        delta_protein = abs(scraped_protein_g - ocr_data.protein_per_serving_g)

        if delta_servings > 0 or delta_protein > 1.0:
            return True
        return False

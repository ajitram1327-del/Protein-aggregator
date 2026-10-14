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

    def extract_label_data(self, image_bytes: bytes) -> Optional[NutritionLabelSchema]:
        prompt = """
        Analyze this dietary supplement nutritional panel.
        Extract exact quantitative values for serving size, protein per serving, and total servings.
        Identify any listed digestive enzyme complexes (e.g., DigeZyme, Pepsin, Papain).
        Extract the raw ingredient list in descending order.
        Adhere strictly to the JSON schema.
        """
        for model_name in ['gemini-2.5-flash', 'gemini-3.8-flash']:
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
                    # Daily/minute quota exhausted; skip OCR immediately to keep pipeline moving
                    break
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

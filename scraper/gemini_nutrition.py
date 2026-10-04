import os
import sys
import json

# Fix Windows console emoji printing error
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

class NutritionFacts(BaseModel):
    serving_size_g: float
    protein_per_serving_g: float

def extract_nutrition(brand, base_name):
    prompt = f"""
    You are a precise nutritional data extractor.
    Find the official nutritional supplement facts for this specific protein product:
    Brand: {brand}
    Product: {base_name}
    
    Extract exactly two numbers:
    1. The serving size in grams (just the number).
    2. The amount of protein per serving in grams (just the number).
    """
    
    print(f"[*] Querying Gemini for: {brand} {base_name}...")
    try:
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                response_mime_type="application/json",
                response_schema=NutritionFacts,
                temperature=0.0
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[!] Gemini Error for {brand}: {e}")
        return None

def extract_nutrition_from_image(image_path, brand, base_name):
    print(f"[*] Analyzing image for {brand} {base_name}...")
    try:
        img = Image.open(image_path)
        prompt = f"""
        You are a precise nutritional data extractor.
        Analyze the provided nutrition facts label image for:
        Brand: {brand}
        Product: {base_name}
        
        Extract exactly two numbers:
        1. The serving size in grams (just the number).
        2. The amount of protein per serving in grams (just the number).
        """
        
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=NutritionFacts,
                temperature=0.0
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[!] Image Extraction Error for {brand}: {e}")
        return None

def run():
    print("Fetching products missing nutrition data...")
    # Get products where nutrition_serving_size_g is null
    res = supabase.table("products").select("id, brand, base_name").is_("nutrition_serving_size_g", "null").execute()
    products = res.data
    
    if not products:
        print("All products have nutritional data! Exiting.")
        return
        
    print(f"Found {len(products)} products needing analysis.")
    
    for p in products:
        data = extract_nutrition(p['brand'], p['base_name'])
        if data:
            print(f"    -> Serving: {data.get('serving_size_g')}g | Protein: {data.get('protein_per_serving_g')}g")
            # Update Supabase
            supabase.table("products").update({
                "nutrition_serving_size_g": data.get('serving_size_g'),
                "nutrition_protein_per_serving_g": data.get('protein_per_serving_g'),
                "nutrition_source": "gemini_search"
            }).eq("id", p["id"]).execute()
            print("    -> Updated DB successfully.")

def run_image_processing(image_path, product_id, brand, base_name):
    print(f"Processing image {image_path} for {brand}...")
    data = extract_nutrition_from_image(image_path, brand, base_name)
    if data:
        print(f"    -> Serving: {data.get('serving_size_g')}g | Protein: {data.get('protein_per_serving_g')}g")
        supabase.table("products").update({
            "nutrition_serving_size_g": data.get('serving_size_g'),
            "nutrition_protein_per_serving_g": data.get('protein_per_serving_g'),
            "nutrition_source": "gemini_image"
        }).eq("id", product_id).execute()
        print("    -> Image data updated in DB successfully.")

if __name__ == "__main__":
    run()

import os
import sys
import json
import base64
import time

# Fix Windows console emoji printing error
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# Explicitly load from scraper/.env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def extract_nutrition(brand, base_name):
    prompt = f"""
    You are a precise nutritional data extractor.
    Rely on your internal knowledge base to find the official nutritional supplement facts for this specific protein product:
    Brand: {brand}
    Product: {base_name}
    
    Output ONLY a raw JSON object (no markdown formatting, no backticks) with exactly two keys:
    "serving_size_g": The serving size in grams (just the number).
    "protein_per_serving_g": The amount of protein per serving in grams (just the number).
    """
    
    print(f"[*] Querying OpenRouter for: {brand} {base_name}...")
    try:
        # Using Qwen 3.8 27B (Available on OpenRouter Free tier)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        # Clean up in case the model added markdown despite instructions
        if result.startswith("```json"): result = result[7:]
        if result.startswith("```"): result = result[3:]
        if result.endswith("```"): result = result[:-3]
        
        return json.loads(result)
    except Exception as e:
        print(f"[!] OpenRouter Error for {brand}: {e}")
        return None

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_nutrition_from_image(image_path, brand, base_name):
    print(f"[*] Analyzing image for {brand} {base_name}...")
    try:
        base64_image = encode_image(image_path)
        prompt = f"""
        You are a precise nutritional data extractor.
        Analyze the provided nutrition facts label image for:
        Brand: {brand}
        Product: {base_name}
        
        Output ONLY a raw JSON object (no markdown formatting) with exactly two keys:
        "serving_size_g": The serving size in grams (just the number).
        "protein_per_serving_g": The amount of protein per serving in grams (just the number).
        """
        
        # Using Gemma 4 31B (Available on OpenRouter Free tier)
        response = client.chat.completions.create(
            model="google/gemma-4-31b-it:free",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        if result.startswith("```json"): result = result[7:]
        if result.startswith("```"): result = result[3:]
        if result.endswith("```"): result = result[:-3]
        
        return json.loads(result)
    except Exception as e:
        print(f"[!] Image Extraction Error for {brand}: {e}")
        return None

def run():
    print("Fetching products missing nutrition data...")
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
            supabase.table("products").update({
                "nutrition_serving_size_g": data.get('serving_size_g'),
                "nutrition_protein_per_serving_g": data.get('protein_per_serving_g'),
                "nutrition_source": "openrouter_gemma4"
            }).eq("id", p["id"]).execute()
            print("    -> Updated DB successfully.")
        
        print("[*] Sleeping 3.5 seconds to respect OpenRouter rate limit...")
        time.sleep(3.5)


def run_image_processing(image_path, product_id, brand, base_name):
    print(f"Processing image {image_path} for {brand}...")
    data = extract_nutrition_from_image(image_path, brand, base_name)
    if data:
        print(f"    -> Serving: {data.get('serving_size_g')}g | Protein: {data.get('protein_per_serving_g')}g")
        supabase.table("products").update({
            "nutrition_serving_size_g": data.get('serving_size_g'),
            "nutrition_protein_per_serving_g": data.get('protein_per_serving_g'),
            "nutrition_source": "openrouter_vision"
        }).eq("id", product_id).execute()
        print("    -> Image data updated in DB successfully.")

if __name__ == "__main__":
    run()

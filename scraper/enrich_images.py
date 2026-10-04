import os
import json
import time
from dotenv import load_dotenv
from supabase import create_client, Client
from duckduckgo_search import DDGS
from openai import OpenAI

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

ddgs = DDGS()

def fetch_nutrition_image_for_product(product):
    brand = product.get("brand", "")
    base_name = product.get("base_name", "")
    
    query = f"{brand} {base_name} nutritional label supplement facts back"
    print(f"[*] Searching DDG Images for: {query}")
    
    try:
        results = list(ddgs.images(query, max_results=3))
        if not results:
            print("  -> No images found.")
            return None
            
        for img in results:
            image_url = img.get("image")
            if not image_url: continue
            
            print(f"  -> Verifying image with AI: {image_url}")
            
            # Verify with Vision AI
            prompt = f"Is this image a nutritional label (supplement facts) for {brand} {base_name}? Reply strictly with a JSON object: {{\"is_valid\": true}} or {{\"is_valid\": false}}"
            
            try:
                response = openai_client.chat.completions.create(
                    model="meta-llama/llama-3.2-11b-vision-instruct:free",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": image_url}}
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                
                result = json.loads(response.choices[0].message.content)
                if result.get("is_valid") is True:
                    print("  [+] Vision AI verified image!")
                    return image_url
                else:
                    print("  [-] AI rejected image.")
                    
            except Exception as ai_e:
                print(f"  [!] AI Error: {ai_e}")
                
        return None
    except Exception as e:
        print(f"[!] Search Error: {e}")
        return None

def run():
    print("Fetching products missing nutrition_label_url...")
    # Add column if it doesn't exist via update fallback
    try:
        supabase.table("products").update({"nutrition_label_url": None}).eq("id", "00000000-0000-0000-0000-000000000000").execute()
    except:
        pass
        
    res = supabase.table("products").select("id, brand, base_name").is_("nutrition_label_url", "null").limit(5).execute()
    products = res.data
    
    if not products:
        print("All products have nutrition images! Exiting.")
        return
        
    for p in products:
        img_url = fetch_nutrition_image_for_product(p)
        if img_url:
            supabase.table("products").update({"nutrition_label_url": img_url}).eq("id", p["id"]).execute()
            print(f"  -> Saved to DB for {p['brand']} {p['base_name']}")
        time.sleep(2) # rate limiting

if __name__ == "__main__":
    run()

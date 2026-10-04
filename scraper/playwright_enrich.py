import os
import json
import time
import urllib.parse
from dotenv import load_dotenv
from supabase import create_client, Client
from playwright.sync_api import sync_playwright
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

def run():
    print("Fetching products missing nutrition_label_url...")
    res = supabase.table("products").select("id, brand, base_name").is_("nutrition_label_url", "null").execute()
    products = res.data
    if not products:
        print("All products have nutrition images! Exiting.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for prod in products:
            brand = prod.get("brand", "")
            base_name = prod.get("base_name", "")
            query = f"{brand} {base_name} nutritional label supplement facts back"
            url = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(query)}"
            
            print(f"\n[*] Navigating to Google Images for: {query.encode('ascii', 'ignore').decode()}")
            page.goto(url)
            time.sleep(2)  # Wait for images to load
            
            # Extract image URLs
            img_urls = page.eval_on_selector_all("img", """elements => {
                return elements
                    .map(el => el.src || el.dataset.src)
                    .filter(src => src && src.startsWith('http'))
                    .slice(0, 5);
            }""")
            
            MODELS_TO_TRY = [
                "google/gemini-1.5-flash",
                "meta-llama/llama-3.2-11b-vision-instruct:free",
                "google/gemini-pro-1.5-exp",
                "openai/gpt-4o-mini"
            ]
            
            found_valid = False
            for image_url in img_urls:
                print(f"  -> Verifying image with AI: {image_url[:60]}...")
                
                prompt = f"""
                Analyze this image. Is it a nutritional label (supplement facts) for {brand} {base_name}? 
                If yes, extract the serving size in grams and protein per serving in grams.
                Reply STRICTLY with a JSON object: 
                {{"is_valid": true/false, "serving_size_g": number, "protein_per_serving_g": number}}
                """
                
                for model_name in MODELS_TO_TRY:
                    try:
                        response = openai_client.chat.completions.create(
                            model=model_name,
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
                            print(f"  [+] Vision AI ({model_name}) verified! Serving: {result.get('serving_size_g')}g, Protein: {result.get('protein_per_serving_g')}g")
                            
                            update_data = {
                                "nutrition_label_url": image_url
                            }
                            if result.get("serving_size_g"):
                                update_data["nutrition_serving_size_g"] = result.get("serving_size_g")
                            if result.get("protein_per_serving_g"):
                                update_data["nutrition_protein_per_serving_g"] = result.get("protein_per_serving_g")
                                
                            supabase.table("products").update(update_data).eq("id", prod["id"]).execute()
                            found_valid = True
                            break
                        else:
                            print(f"  [-] AI ({model_name}) rejected image.")
                            break # Move to next image, model worked but image is bad
                            
                    except Exception as ai_e:
                        print(f"  [!] AI Error on {model_name}: {str(ai_e)[:80]}")
                        # Loop continues to next model
                        
                if found_valid:
                    break
            
            if not found_valid:
                print(f"  [!] Could not find valid nutrition label for {brand} {base_name}")
            
            time.sleep(3) # Be nice to Google
            
        browser.close()

if __name__ == "__main__":
    run()

import os
import json
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import AsyncOpenAI
import rapidfuzz
from rapidfuzz import process, fuzz
import uuid
import re

load_dotenv("../.env")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Connect to OpenRouter instead of Groq
openrouter_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

PROMPT = """You are a master catalog creator for a supplements aggregator.
Your job is to normalize dirty scraped product titles into a master catalog.
1. If the product clearly matches a brand and formulation in the Existing Catalog, return the exact Existing Catalog name.
2. If it is a completely new formulation that does not exist in the catalog yet, create a clean, canonical "Master Catalog" name for it.

CRITICAL: Do NOT merge "Isolate", "Concentrate", and "Blend" products. Even if they sound 95% identical, they are different products. 
Separate the core product name from its Weight and Flavor. 

Example Input:
Dirty Title: "Optimum Nutrition (ON) Gold Standard 100% Whey Protein - 2 lbs (Chocolate)"
Existing Catalog: ["Optimum Nutrition Serious Mass", "ON Gold Standard 100% Whey"]
Expected Output: {
    "clean_name": "ON Gold Standard 100% Whey",
    "weight_string": "2 lbs",
    "flavor": "Chocolate",
    "category": "protein"
}

Return ONLY a valid JSON object with the keys "clean_name", "weight_string", "flavor", and "category". 
Category MUST be one of: "protein", "mass_gainer", "creatine", "pre_workout", "vitamins", "other".
"""

async def normalize_catalog():
    print("Fetching unmatched raw products (BOTTOM UP for OpenRouter)...")
    # Fetch from the bottom of the table to meet Groq in the middle
    res = supabase.table("unmatched_products").select("*").order("id", desc=True).limit(1000).execute()
    
    if not res.data:
        print("No unmatched products to normalize.")
        return
        
    print(f"Found {len(res.data)} raw scraped listings. Firing up OpenRouter (Llama 3.1 8B Instruct) for Entity Resolution...")
    
    TITLE_CACHE = {}
    
    for row in res.data:
        dirty_title = row.get("scraped_title", "")
        brand = row.get("scraped_brand", "")
        price = row.get("scraped_price_inr")
        url = row.get("url")
        source = row.get("platform_guess")
        
        # Grab existing catalog names for this brand
        existing = supabase.table("products").select("base_name").eq("brand", brand).execute()
        existing_names = [p["base_name"] for p in existing.data] if existing.data else []
        
        parsed_json = None
        
        # 1. Fuzzy Match against already-parsed titles in cache
        if TITLE_CACHE:
            match = process.extractOne(dirty_title, TITLE_CACHE.keys(), scorer=fuzz.ratio, score_cutoff=95)
            if match:
                parsed_json = TITLE_CACHE[match[0]]
                print(f"  [FAST] RapidFuzz Cache Hit! ({match[1]}% match to '{match[0][:20]}')")

        # 2. Ask OpenRouter if no cache match
        if not parsed_json:
            try:
                response = await openrouter_client.chat.completions.create(
                    model="google/gemma-2-9b-it:free",
                    messages=[
                        {"role": "system", "content": PROMPT},
                        {"role": "user", "content": f"Existing Catalog: {existing_names}\nDirty Title: {dirty_title}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                parsed_json = json.loads(response.choices[0].message.content)
                TITLE_CACHE[dirty_title] = parsed_json
            except Exception as e:
                print(f"OpenRouter LLM failed: {e}".encode("ascii", "ignore").decode())
                await asyncio.sleep(2) # Backoff on error
                continue
            
        clean_name = parsed_json.get("clean_name")
        weight_string = parsed_json.get("weight_string")
        flavor = parsed_json.get("flavor")
        category = parsed_json.get("category", "other")
        print(f"Normalized: '{dirty_title[:30]}...' -> '{clean_name}' [{weight_string} | {flavor}] ({category})")
        
        # 3. Check if the LLM mapped this to an existing product
        existing_match = supabase.table("products").select("id").eq("brand", brand).eq("base_name", clean_name).execute()
        
        if existing_match.data:
            master_id = existing_match.data[0]["id"]
            print(f"  [~] Entity Resolution Matched to existing Catalog ID {master_id}")
        else:
            # 3. Create the new Master Product!
            new_prod = supabase.table("products").insert({
                "brand": brand,
                "base_name": clean_name,
                "category_silo": category
            }).execute()
            master_id = new_prod.data[0]["id"]
            print(f"  [+] Created new Master Product in Catalog: {clean_name}")
            
        # Sanitize and bucketize weight string into a numeric value for weight_grams
        weight_val = 0
        if weight_string:
            nums = re.findall(r'\d+\.?\d*', str(weight_string))
            if nums:
                raw_weight = float(nums[0])
                if "lb" in str(weight_string).lower():
                    raw_weight = raw_weight * 453.592 # convert lbs to grams
                elif "kg" in str(weight_string).lower():
                    raw_weight = raw_weight * 1000 # convert kg to grams
                
                # Bucketize to nearest common metric sizes (e.g., 2lbs/907g -> 1kg)
                if 800 <= raw_weight <= 1200:
                    weight_val = 1000
                elif 1800 <= raw_weight <= 2200:
                    weight_val = 2000
                elif 2201 <= raw_weight <= 2600:
                    weight_val = 2500
                elif 2601 <= raw_weight <= 3300:
                    weight_val = 3000
                elif 3500 <= raw_weight <= 4500:
                    weight_val = 4000
                elif 4501 <= raw_weight <= 5500:
                    weight_val = 5000
                else:
                    weight_val = raw_weight # Leave small or weird sizes as-is

        if not flavor:
            flavor = ""
            
        # Sanitize Price (to avoid numeric overflow from HTML parsing bugs)
        try:
            if price and float(price) > 99999:
                price = None # Impossible price for a supplement, likely a corrupted HTML extraction
        except (ValueError, TypeError):
            price = None
            
        # 4. Handle the Variant (Flavor/Weight combo)
        # Check if this exact variant exists for this master product
        variant_match = supabase.table("variants").select("id").eq("product_id", master_id).eq("flavor", flavor).eq("weight_grams", weight_val).execute()
        
        if variant_match.data:
            variant_id = variant_match.data[0]["id"]
            print(f"  [~] Matched existing Variant ID: {variant_id}")
        else:
            new_var = supabase.table("variants").insert({
                "product_id": master_id,
                "flavor": flavor,
                "weight_grams": weight_val,
                "sku_id": f"RAW_{str(uuid.uuid4())[:8]}"
            }).execute()
            variant_id = new_var.data[0]["id"]
            print(f"  [+] Created new Variant: {flavor} - {weight_val}g")
            
        # 5. Insert the price listing linked to the Variant
        try:
            supabase.table("price_listings").insert({
                "variant_id": variant_id,
                "source": source,
                "price_inr": price,
                "listing_url": url,
                "is_in_stock": True
            }).execute()
        except Exception as e:
            if "duplicate key value" in str(e):
                print(f"  [i] Price listing already exists for {source}. Appending to multiple sellers tag in raw_payload...")
                # Fetch existing row
                existing_listing = supabase.table("price_listings").select("id, raw_payload").eq("variant_id", variant_id).eq("source", source).execute()
                if existing_listing.data:
                    listing_id = existing_listing.data[0]["id"]
                    payload = existing_listing.data[0].get("raw_payload") or {}
                    
                    if "multiple_sellers" not in payload:
                        payload["multiple_sellers"] = []
                        
                    payload["multiple_sellers"].append({
                        "url": url,
                        "price_inr": price
                    })
                    
                    # Update row
                    supabase.table("price_listings").update({"raw_payload": payload}).eq("id", listing_id).execute()
            else:
                print(f"  [!] Failed to insert price listing: {e}")
        
        # 6. Delete from unmatched now that it's correctly cataloged
        supabase.table("unmatched_products").delete().eq("id", row["id"]).execute()
        
        # OpenRouter's free tier has a generous 200 RPM, but we keep a tiny 0.5s sleep just to be safe with DB connections
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    while True:
        # Loop endlessly until the database is empty
        asyncio.run(normalize_catalog())

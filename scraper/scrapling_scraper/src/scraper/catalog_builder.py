import os
import json
import asyncio
import re
import uuid
from dotenv import load_dotenv
from supabase import create_client
from openai import AsyncOpenAI
from flashtext import KeywordProcessor
from rapidfuzz import process, fuzz

load_dotenv(dotenv_path="../.env")

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
kimi_client = AsyncOpenAI(api_key=os.environ.get("MOONSHOT_API_KEY"), base_url="https://api.moonshot.cn/v1")

# --- SETUP DICTIONARIES & PARSERS ---
brand_processor = KeywordProcessor(case_sensitive=False)
brand_processor.add_keywords_from_dict({
    "Optimum Nutrition": ["optimum nutrition", "on", "gold standard", "serious mass"],
    "MuscleBlaze": ["muscleblaze", "mb", "biozyme"],
    "Myprotein": ["myprotein", "my protein", "impact whey"],
    "As-It-Is": ["asitis", "as-it-is", "as it is"],
    "Avvatar": ["avvatar"],
    "Dymatize": ["dymatize", "iso 100", "iso-100"],
    "MuscleTech": ["muscletech", "nitrotech", "nitro tech"],
    "GNC": ["gnc"],
    "Ultimate Nutrition": ["ultimate nutrition"]
})

flavor_processor = KeywordProcessor(case_sensitive=False)
flavor_processor.add_keywords_from_dict({
    "Double Rich Chocolate": ["double rich chocolate", "rich chocolate"],
    "Chocolate": ["chocolate", "choco", "dutch chocolate", "milk chocolate"],
    "Cafe Mocha": ["cafe mocha", "mocha", "coffee"],
    "Vanilla": ["vanilla", "french vanilla", "vanila"],
    "Cookies and Cream": ["cookies and cream", "cookies & cream", "cookie and cream"],
    "Unflavored": ["unflavored", "raw", "unflavoured"],
    "Strawberry": ["strawberry"],
    "Mango": ["mango"]
})

WEIGHT_REGEX = re.compile(r'(\d+(?:\.\d+)?)\s*(kg|g|lbs?|lb|oz)\b', re.IGNORECASE)

def normalize_weight(title: str):
    match = WEIGHT_REGEX.search(title)
    if not match:
        return None
    val, unit = float(match.group(1)), match.group(2).lower()
    raw_weight = val
    if unit in ('kg',): raw_weight = val * 1000
    elif unit in ('g',): raw_weight = val
    elif unit in ('lb', 'lbs'): raw_weight = val * 453.592
    elif unit in ('oz',): raw_weight = val * 28.3495
    else: return None
    
    # Bucketize
    if 800 <= raw_weight <= 1200: return 1000
    if 1800 <= raw_weight <= 2200: return 2000
    if 2201 <= raw_weight <= 2600: return 2500
    if 2601 <= raw_weight <= 3300: return 3000
    if 3500 <= raw_weight <= 4500: return 4000
    if 4501 <= raw_weight <= 5500: return 5000
    return int(raw_weight)

def extract_local(title: str):
    brands = brand_processor.extract_keywords(title)
    flavors = flavor_processor.extract_keywords(title)
    weight_g = normalize_weight(title)
    
    brand = brands[0] if brands else None
    flavor = flavors[0] if flavors else ""
    return brand, flavor, weight_g

PROMPT = """You are a master catalog creator. Extract canonical JSON for the following dirty product titles.
Return a valid JSON array of objects, one for each input.
Keys required: "id" (must match input id), "clean_name" (brand + core product), "flavor", "weight_g" (integer), "category" (protein/creatine/mass_gainer/other).
Separate the flavor and weight from the clean_name. Do not merge Isolate and Concentrate.
Input:
"""

async def resolve_llm_batch(batch_records):
    print(f"  [LLM] Firing Kimi for a batch of {len(batch_records)} items...")
    input_data = [{"id": r[0], "raw": r[1]} for r in batch_records]
    try:
        response = await kimi_client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(input_data)}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        # Kimi might return {"results": [...]} or just [...] depending on formatting, let's aggressively parse array
        import re
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        # fallback if it's an object containing an array
        parsed = json.loads(content)
        for val in parsed.values():
            if isinstance(val, list): return val
        return []
    except Exception as e:
        print(f"  [!] LLM Batch Failed: {e}")
        return []

async def process_queue():
    print("Fetching unmatched raw products (Sorted by Title)...")
    res = supabase.table("unmatched_products").select("*").order("scraped_title").limit(500).execute()
    
    if not res.data:
        print("No unmatched products left!")
        return False
        
    print(f"Found {len(res.data)} raw listings in this batch.")
    
    # We will build a list of processed results
    processed_items = [] # list of dicts: id, raw_row, clean_name, brand, flavor, weight_g, category
    unresolved_buffer = []
    
    TITLE_CACHE = {} # in-memory cache for this run
    
    for row in res.data:
        row_id = row["id"]
        dirty_title = row.get("scraped_title", "")
        scraped_brand = row.get("scraped_brand", "")
        
        # 1. Deterministic Extraction
        brand, flavor, weight_g = extract_local(dirty_title)
        
        if brand and weight_g is not None:
            # We have enough to assume a clean name (Brand + regex stripped)
            # Just use the dirty title minus the weight/flavor as base name
            # Or default to scraped_brand if brand is none
            clean_name = brand if brand else scraped_brand
            processed_items.append({
                "id": row_id, "row": row, "clean_name": clean_name, "brand": brand, 
                "flavor": flavor, "weight_g": weight_g, "category": "protein"
            })
            continue
            
        # 2. Fuzzy Cache
        if TITLE_CACHE:
            match = process.extractOne(dirty_title, TITLE_CACHE.keys(), scorer=fuzz.ratio, score_cutoff=95)
            if match:
                cached = TITLE_CACHE[match[0]]
                processed_items.append({
                    "id": row_id, "row": row, "clean_name": cached["clean_name"], 
                    "brand": scraped_brand, "flavor": cached["flavor"], 
                    "weight_g": cached["weight_g"], "category": cached.get("category", "other")
                })
                continue
                
        # 3. Queue for LLM Batch
        unresolved_buffer.append((row_id, dirty_title, row, scraped_brand))
        
        if len(unresolved_buffer) >= 20: # batch size
            results = await resolve_llm_batch([(u[0], u[1]) for u in unresolved_buffer])
            for res_obj in results:
                # Find matching row in unresolved_buffer
                match_u = next((u for u in unresolved_buffer if u[0] == res_obj.get("id")), None)
                if match_u:
                    processed_items.append({
                        "id": match_u[0], "row": match_u[2], 
                        "clean_name": res_obj.get("clean_name", match_u[1][:30]),
                        "brand": match_u[3],
                        "flavor": res_obj.get("flavor", ""),
                        "weight_g": res_obj.get("weight_g", 0) or 0,
                        "category": res_obj.get("category", "other")
                    })
                    # Update cache
                    TITLE_CACHE[match_u[1]] = res_obj
            unresolved_buffer.clear()
            
    # Flush remaining
    if unresolved_buffer:
        results = await resolve_llm_batch([(u[0], u[1]) for u in unresolved_buffer])
        for res_obj in results:
            match_u = next((u for u in unresolved_buffer if u[0] == res_obj.get("id")), None)
            if match_u:
                processed_items.append({
                    "id": match_u[0], "row": match_u[2], 
                    "clean_name": res_obj.get("clean_name", match_u[1][:30]),
                    "brand": match_u[3],
                    "flavor": res_obj.get("flavor", ""),
                    "weight_g": res_obj.get("weight_g", 0) or 0,
                    "category": res_obj.get("category", "other")
                })
                TITLE_CACHE[match_u[1]] = res_obj
        unresolved_buffer.clear()

    # --- SUPABASE INSERTS ---
    for item in processed_items:
        row = item["row"]
        source = row.get("platform_guess")
        price = row.get("scraped_price_inr")
        url = row.get("url")
        
        try:
            if price and float(price) > 99999: price = None
        except: price = None

        brand = item["brand"] or row.get("scraped_brand", "Unknown")
        
        # 1. Master Product
        existing_match = supabase.table("products").select("id").eq("brand", brand).eq("base_name", item["clean_name"]).execute()
        if existing_match.data:
            master_id = existing_match.data[0]["id"]
        else:
            new_prod = supabase.table("products").insert({
                "brand": brand, "base_name": item["clean_name"], "category_silo": item["category"]
            }).execute()
            master_id = new_prod.data[0]["id"]
            
        # 2. Variant
        variant_match = supabase.table("variants").select("id").eq("product_id", master_id).eq("flavor", item["flavor"]).eq("weight_grams", item["weight_g"]).execute()
        if variant_match.data:
            variant_id = variant_match.data[0]["id"]
        else:
            new_var = supabase.table("variants").insert({
                "product_id": master_id, "flavor": item["flavor"], "weight_grams": item["weight_g"], "sku_id": f"RAW_{str(uuid.uuid4())[:8]}"
            }).execute()
            variant_id = new_var.data[0]["id"]
            
        # 3. Price Listing
        try:
            supabase.table("price_listings").insert({
                "variant_id": variant_id, "source": source, "price_inr": price, "listing_url": url, "is_in_stock": True
            }).execute()
        except Exception as e:
            if "duplicate key value" in str(e):
                existing_listing = supabase.table("price_listings").select("id, raw_payload").eq("variant_id", variant_id).eq("source", source).execute()
                if existing_listing.data:
                    listing_id = existing_listing.data[0]["id"]
                    payload = existing_listing.data[0].get("raw_payload") or {}
                    if "multiple_sellers" not in payload: payload["multiple_sellers"] = []
                    payload["multiple_sellers"].append({"url": url, "price_inr": price})
                    supabase.table("price_listings").update({"raw_payload": payload}).eq("id", listing_id).execute()
                    
        # 4. Delete from queue
        supabase.table("unmatched_products").delete().eq("id", row["id"]).execute()
        
    return True

if __name__ == "__main__":
    while True:
        try:
            has_more = asyncio.run(process_queue())
            if not has_more: break
        except Exception as e:
            print(f"Network error: {e}")
            import time
            time.sleep(5)

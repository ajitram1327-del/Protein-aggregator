import os
import json
import asyncio
from dotenv import load_dotenv
from supabase import create_client
from phase2_enrichment import extract_product_data

load_dotenv(dotenv_path="../.env")

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

async def batch_process_phase2():
    print("Fetching products that need Phase 2 Deep Dive enrichment...")
    
    TABLE_NAME = "products" 
    
    # Grab 50 rows where metadata is null AND category is 'protein'
    response = supabase.table(TABLE_NAME).select("*").is_("metadata", "null").eq("category", "protein").limit(50).execute()
    
    if not response.data:
        print("No products need enrichment right now. All caught up!")
        return

    print(f"Found {len(response.data)} products to process. Starting the slow burn...")

    for row in response.data:
        product_id = row.get("id")
        
        # Products table doesn't have a URL, so we fetch all URLs from price_listings linked to this product.
        price_rows = supabase.table("price_listings").select("url").eq("product_id", product_id).execute()
        if not price_rows.data:
            print(f"Row {product_id} has no linked URLs. Skipping.")
            continue
            
        # Prioritize D2C and reputable supplement sites over Amazon/Flipkart
        urls = [r["url"] for r in price_rows.data if r.get("url")]
        
        def score_url(u):
            u_lower = u.lower()
            if "amazon" in u_lower or "flipkart" in u_lower or "jiomart" in u_lower: return 10
            if "healthkart" in u_lower or "nutrabay" in u_lower or "1mg" in u_lower: return 5
            return 1 # Highest priority (assumed D2C / Brand Site)
            
        urls.sort(key=score_url)
        url = urls[0]
            
        print(f"\n[PHASE 2] Processing ID {product_id} | Selected High-Priority URL: {url}")
        
        # 1. Run the Gemini Vision Extraction
        extracted_data = await extract_product_data(url)
        
        if extracted_data:
            try:
                # 2. Update Supabase with the JSONB payload
                supabase.table(TABLE_NAME).update({
                    "metadata": extracted_data
                }).eq("id", product_id).execute()
                print(f"Successfully saved 15-point metadata to Supabase for ID {product_id}!")
            except Exception as e:
                print(f"Failed to save to Supabase: {e}")
        else:
            print(f"Failed to extract data for {url}")
            
        # 3. Slow down. Stay under Gemini's 15 Requests Per Minute limit (4 seconds per URL)
        print("Sleeping for 4 seconds to respect API limits...")
        await asyncio.sleep(4)
        
if __name__ == "__main__":
    asyncio.run(batch_process_phase2())

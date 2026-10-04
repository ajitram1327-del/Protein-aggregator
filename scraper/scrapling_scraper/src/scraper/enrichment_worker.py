import asyncio
import os
import json
import httpx
import logging
from dotenv import load_dotenv
from supabase import create_client
from scrapling import StealthyFetcher

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.vision.label_auditor import VisionLabelAuditor
from src.analytics.equalizer import EqualizerEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnrichmentWorker")

async def fetch_image_bytes(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15.0)
        resp.raise_for_status()
        return resp.content

async def enrich_product():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'))
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment.")
        return
        
    auditor = VisionLabelAuditor(api_key=api_key)

    # 1. Query price_listings to find D2C or HealthKart URLs for variants that haven't been OCR audited
    # We will use raw SQL or just fetch recent listings. Since we can't do complex JSON filters easily in the basic SDK without postgrest advanced, 
    # we'll fetch variants and check locally to save complex queries.
    
    res = supabase.table("price_listings").select("variant_id, source_url, source").in_("source", ["D2C", "HealthKart"]).limit(50).execute()
    
    if not res.data:
        logger.info("No source listings found.")
        return
        
    for listing in res.data:
        variant_id = listing["variant_id"]
        source_url = listing["source_url"]
        
        # Check if variant is already audited
        v_res = supabase.table("variants").select("id, weight_grams, lowest_price_inr, raw_json_data").eq("id", variant_id).execute()
        if not v_res.data: continue
        
        variant = v_res.data[0]
        raw_json = json.loads(variant.get("raw_json_data", "{}"))
        
        if raw_json.get("ocr_audited", False):
            continue # Already audited, skip!
            
        logger.info(f"Auditing Variant ID: {variant_id} from {source_url}")
        
        try:
            # Fetch the product page to find gallery images
            page = await StealthyFetcher.async_fetch(source_url, headless=True)
            
            # Extract all images
            images = page.css("img")
            target_image_url = None
            
            # Filter purely by URL strings (Zero Cost)
            for img in images:
                src = img.attrib.get("src") or img.attrib.get("data-src") or ""
                if "nutrition" in src.lower() or "label" in src.lower() or "fact" in src.lower() or "back" in src.lower():
                    target_image_url = src
                    break
                    
            if not target_image_url:
                logger.warning(f"No nutrition label keyword found in images for {source_url}. Falling back to 2nd image if exists.")
                if len(images) > 1:
                    target_image_url = images[1].attrib.get("src") or images[1].attrib.get("data-src")
            
            if target_image_url:
                if not target_image_url.startswith("http"):
                    from urllib.parse import urljoin
                    target_image_url = urljoin(source_url, target_image_url)
                
                logger.info(f"Downloading image purely in-memory: {target_image_url}")
                img_bytes = await fetch_image_bytes(target_image_url)
                
                # Send to Gemini
                logger.info("Passing bytes to Gemini Flash-8B for structured extraction...")
                ocr_data = auditor.extract_label_data(img_bytes)
                logger.info(f"Extracted: {ocr_data}")
                
                # Re-calculate scientific metrics with truth data
                psource_res = supabase.table("variants").select("products(protein_source)").eq("id", variant_id).execute()
                psource = psource_res.data[0]["products"]["protein_source"] if psource_res.data else "Whey"
                
                analytics_metrics = EqualizerEngine.calculate_metrics(
                    category=psource,
                    price_inr=variant["lowest_price_inr"],
                    label_protein_g=ocr_data.protein_per_serving_g,
                    serving_size_g=ocr_data.serving_size_g,
                    total_servings=ocr_data.total_servings
                )
                
                # Update Database with scientific truth
                raw_json["ocr_audited"] = True
                raw_json["analytics"] = analytics_metrics
                raw_json["ocr_data"] = ocr_data.model_dump()
                
                supabase.table("variants").update({
                    "raw_json_data": json.dumps(raw_json),
                    "servings_count": ocr_data.total_servings,
                    "best_value_metric": analytics_metrics["effective_cost_per_bioavailable_g_inr"]
                }).eq("id", variant_id).execute()
                
                logger.info(f"Database successfully updated for variant {variant_id}!")
                
            else:
                logger.warning("Could not identify any valid image.")
                
        except Exception as e:
            logger.error(f"Enrichment failed for {variant_id}: {e}")

if __name__ == "__main__":
    asyncio.run(enrich_product())

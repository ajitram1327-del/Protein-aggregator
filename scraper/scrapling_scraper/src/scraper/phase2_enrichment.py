import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from scrapling.fetchers import StealthyFetcher
from supabase import create_client

load_dotenv(dotenv_path="../.env")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

PROMPT = """
You are a ruthless sports nutrition auditor. 
Extract the following high-signal data points from this product page and its nutrition label images.
Return ONLY a valid JSON object matching these exact keys. If a value is unknown, use null.

Keys to extract:
PricePerServing (number), 
ProteinPerServing (number), 
ServingSizeGrams (number), 
TotalServings (number), 
ProteinPercentage (number - calculate as ProteinPerServing / ServingSizeGrams * 100), 
AddedCreatine (boolean - true if creatine is added to the ingredient list), 
AddedTaurine (boolean - true if taurine or glycine is added as a cheap filler), 
BCAAPerServing (number), 
SweetenerType (string - e.g. Sucralose, Stevia, Aspartame, Acesulfame Potassium, None),
NutritionLabelImageURL (string - the exact URL of the image that contains the physical nutrition label/ingredients list, choose from the provided list)
"""

import io
from PIL import Image

async def download_and_compress_image(url: str):
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(url, timeout=10.0)
            if resp.status_code == 200:
                # Compress the image aggressively to save Gemini tokens
                img = Image.open(io.BytesIO(resp.content))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Resize if it's massive
                img.thumbnail((800, 800))
                
                output = io.BytesIO()
                # Save as highly compressed JPEG
                img.save(output, format='JPEG', quality=60)
                return output.getvalue()
    except:
        pass
    return None

async def extract_product_data(url: str):
    print(f"Fetching URL: {url}")
    try:
        page = await StealthyFetcher.async_fetch(url, headless=True)
        
        page_text = page.text[:10000]
        
        # 1. Smart URL Filtering
        all_imgs = [img.attrib.get('src') for img in page.css('img') if img.attrib.get('src') and ('http' in img.attrib.get('src'))]
        valid_imgs = []
        for src in all_imgs:
            lower_src = src.lower()
            if any(junk in lower_src for junk in ['logo', 'icon', 'banner', 'footer', 'avatar', 'gif']):
                continue
            valid_imgs.append(src)
            
        # Prioritize images that actually say "label" or "nutrition" or "back"
        prioritized = [src for src in valid_imgs if any(k in src.lower() for k in ['label', 'nutri', 'back', 'ingredient', 'fact'])]
        others = [src for src in valid_imgs if src not in prioritized]
        
        # Combine them, taking the prioritized ones first, up to a massive 8 images instead of 3
        images_urls = (prioritized + others)[:8]
        
        print(f"Found {len(images_urls)} images. Downloading and Compressing...")
        image_bytes_list = []
        for img_url in images_urls:
            b = await download_and_compress_image(img_url)
            if b: image_bytes_list.append(b)
        
        image_urls_context = "\n".join([f"Image {i+1} URL: {url}" for i, url in enumerate(images_urls)])
        
        contents = [
            types.Part.from_text(text=f"Product Page Text:\n{page_text}\n\nAvailable Images:\n{image_urls_context}\n\n{PROMPT}")
        ]
        
        for b in image_bytes_list:
            contents.append(
                types.Part.from_bytes(data=b, mime_type="image/jpeg") # using jpeg as generic
            )
            
        print("Querying gemini-3.6-flash...")
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        
        result_json = response.text
        print("Successfully extracted data!")
        return json.loads(result_json)
        
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return None

async def main():
    print("Testing Phase 2 Gemini 3.8 Vision Pipeline on a single URL...")
    test_url = "https://nakpro.com/products/nakpro-platinum-100-whey-protein-isolate"
    data = await extract_product_data(test_url)
    
    if data:
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

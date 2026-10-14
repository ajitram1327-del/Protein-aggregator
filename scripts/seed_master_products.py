import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv("scraper/.env")
load_dotenv()

supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

sys.path.append(os.path.abspath("scraper/scrapling_scraper"))
from src.scraper.engine import upsert_product_variant

seeds = [
    {
        "brand": "Optimum Nutrition (ON)",
        "title": "Optimum Nutrition (ON) Gold Standard 100% Whey Protein Powder Double Rich Chocolate 2 kg (4.4 lb)",
        "price": 6999.0,
        "img": "https://m.media-amazon.com/images/I/7162YStgVUL._SL1500_.jpg",
        "url": "https://www.optimumnutrition.co.in/gold-standard-100-whey",
        "source": "D2C",
        "desc": "24g protein per serving with whey protein isolate as the primary ingredient. 5.5g BCAAs and 4g Glutamine.",
        "seller": "Optimum Nutrition India"
    },
    {
        "brand": "MuscleBlaze",
        "title": "MuscleBlaze Biozyme Performance Whey Protein Rich Chocolate 2 kg (4.4 lb)",
        "price": 4499.0,
        "img": "https://m.media-amazon.com/images/I/61b7U2-d+QL._SL1500_.jpg",
        "url": "https://www.muscleblaze.com/biozyme-performance-whey",
        "source": "D2C",
        "desc": "Enhanced Absorption Formula with 25g protein per scoop clinically tested for 50% higher protein absorption.",
        "seller": "MuscleBlaze"
    },
    {
        "brand": "AS-IT-IS Nutrition",
        "title": "AS-IT-IS Nutrition Whey Protein Concentrate 80% Unflavoured 1 kg",
        "price": 1749.0,
        "img": "https://asitisnutrition.com/cdn/shop/products/whey-concentrate.jpg",
        "url": "https://asitisnutrition.com/products/whey-protein-concentrate-80",
        "source": "D2C",
        "desc": "Pure unflavoured whey protein concentrate 80% offering 24g protein and 5.4g BCAA per 30g serving.",
        "seller": "AS-IT-IS Nutrition"
    },
    {
        "brand": "Dymatize",
        "title": "Dymatize ISO 100 Hydrolyzed 100% Whey Isolate Gourmet Chocolate 2.3 kg (5 lb)",
        "price": 9499.0,
        "img": "https://m.media-amazon.com/images/I/71u9s8+a+QL._SL1500_.jpg",
        "url": "https://dymatize.com/iso-100",
        "source": "D2C",
        "desc": "Hydrolyzed 100% whey protein isolate with 25g protein, 5.5g BCAAs, and less than 1g sugar per serving.",
        "seller": "Dymatize"
    },
    {
        "brand": "Avvatar",
        "title": "Avvatar 100% Whey Protein Malai Kulfi 2 kg",
        "price": 4899.0,
        "img": "https://avvatarindia.com/cdn/shop/products/malai-kulfi.jpg",
        "url": "https://avvatarindia.com/products/whey-protein-malai-kulfi",
        "source": "D2C",
        "desc": "100% fresh whey protein directly processed from cow milk within 24 hours. 27g protein per scoop.",
        "seller": "Parag Milk Foods"
    }
]

print("Seeding pristine master products into DB...")
for s in seeds:
    ok = upsert_product_variant(s["brand"], s["title"], s["price"], s["img"], s["url"], s["source"], s["desc"], s["seller"])
    print(f"  {s['brand']}: {'Success' if ok else 'Failed'}")

p_count = supabase.table("products").select("*", count="exact", head=True).execute().count
v_count = supabase.table("variants").select("*", count="exact", head=True).execute().count
pl_count = supabase.table("price_listings").select("*", count="exact", head=True).execute().count
print(f"Verification Counts -> Products: {p_count}, Variants: {v_count}, Price Listings: {pl_count}")

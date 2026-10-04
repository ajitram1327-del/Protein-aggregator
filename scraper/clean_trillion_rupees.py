import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

print("Cleaning corrupted prices from price_listings...")
try:
    res = supabase.table("price_listings").delete().gt("price_inr", 100000).execute()
    print(f"Deleted corrupted exact matches: {len(res.data) if hasattr(res, 'data') else 'Success'}")
except Exception as e:
    print(f"Error cleaning price_listings: {e}")

print("Cleaning corrupted prices from unmatched_products...")
try:
    res2 = supabase.table("unmatched_products").delete().gt("scraped_price_inr", 100000).execute()
    print(f"Deleted corrupted unmatched rows: {len(res2.data) if hasattr(res2, 'data') else 'Success'}")
except Exception as e:
    print(f"Error cleaning unmatched_products: {e}")

print("Cleanup complete!")

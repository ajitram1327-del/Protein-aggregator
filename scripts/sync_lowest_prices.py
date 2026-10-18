import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

print("Synchronizing variants.lowest_price_inr from active price_listings...")

# Fetch all price listings
pl_res = sb.table('price_listings').select('variant_id, price_inr, in_stock, is_in_stock').gt('price_inr', 0).execute()
listings = pl_res.data
print(f"Total active price listings: {len(listings)}")

# Map variant_id to min price
min_prices = {}
for l in listings:
    vid = l['variant_id']
    price = float(l['price_inr'])
    if vid not in min_prices or price < min_prices[vid]:
        min_prices[vid] = price

# Fetch all variants
v_res = sb.table('variants').select('id, lowest_price_inr, weight_grams, flavor').execute()
variants = v_res.data
print(f"Total variants: {len(variants)}")

updated_count = 0
for v in variants:
    vid = v['id']
    current_low = v['lowest_price_inr']
    true_low = min_prices.get(vid)
    
    if true_low and round(true_low, 2) != round(current_low or 0, 2):
        sb.table('variants').update({'lowest_price_inr': round(true_low, 2)}).eq('id', vid).execute()
        updated_count += 1

print(f"Updated {updated_count} variants to match true price_listings minimums.")

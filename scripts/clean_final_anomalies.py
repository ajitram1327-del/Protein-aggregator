import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')
sb = create_client(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY'))

print("Cleaning up final remaining contaminated listings...")

# 1. Purge any price listing containing 'isopure' or 'karnage' on Creatine products
sb.table('price_listings').delete().ilike('listing_url', '%isopure%').execute()
sb.table('price_listings').delete().ilike('listing_url', '%karnage%').execute()

# 2. Purge search results URLs (e.g. /search/result/?q=) which are search pages, not product listings
sb.table('price_listings').delete().ilike('listing_url', '%/search/%').execute()
sb.table('price_listings').delete().ilike('listing_url', '%/search?%').execute()

# 3. Clean up ghost variants that lost listings
def fetch_all(table_name, select_cols='*'):
    rows = []
    page_size = 1000
    offset = 0
    while True:
        res = sb.table(table_name).select(select_cols).range(offset, offset + page_size - 1).execute()
        data = res.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return rows

listings = fetch_all('price_listings', 'variant_id')
active_vids = {l['variant_id'] for l in listings if l.get('variant_id')}

variants = fetch_all('variants', 'id, lowest_price_inr, weight_grams')
for v in variants:
    if v['id'] not in active_vids:
        print(f"Purging variant with 0 listings: {v['id']}")
        sb.table('variants').delete().eq('id', v['id']).execute()

# 4. Sync lowest_price_inr for all remaining variants
all_listings = fetch_all('price_listings')
min_map = {}
for l in all_listings:
    vid = l.get('variant_id')
    p = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and p > 0 and in_stock:
        if vid not in min_map or p < min_map[vid]:
            min_map[vid] = p

all_vars = fetch_all('variants')
for v in all_vars:
    vid = v['id']
    curr = v.get('lowest_price_inr')
    expected = min_map.get(vid)
    if expected and (curr is None or abs(float(curr) - expected) > 0.05):
        sb.table('variants').update({'lowest_price_inr': round(expected, 2)}).eq('id', vid).execute()

print("Cleanup complete!")

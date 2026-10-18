import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')
sb = create_client(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY'))

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

variants = fetch_all('variants', 'id, product_id, lowest_price_inr, weight_grams, flavor')
empty_variants = [v for v in variants if v['id'] not in active_vids]

print(f"Purging {len(empty_variants)} ghost variants with 0 listings...")
for ev in empty_variants:
    vid = ev['id']
    w = ev['weight_grams']
    p = ev['lowest_price_inr']
    print(f"Deleting ghost variant {vid}: {w}g @ Rs.{p}")
    sb.table('variants').delete().eq('id', vid).execute()

print("Purge complete!")

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')
sb = create_client(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY'))

print("Cleaning up ON multi-item combos and Muscle Nectar Creapure...")

# 1. Delete ON multi-product combo listings on Creatine and Pre-Workout
combo_listings = [
    'e281e8ce-0182-402c-8840-e524f9c56122',
    '8257ea20-6ccc-48ce-9859-d4b789316e0b',
    'e1282510-dd5c-4d7b-8d38-46077ba96153'
]
for lid in combo_listings:
    sb.table('price_listings').delete().eq('id', lid).execute()

combo_vars = [
    'b4b94d2e-afda-4a5c-83ed-73f0ac6abc98',
    '03f27647-7a59-4966-9d11-317edc790770',
    'effcffe5-1f86-40cf-8834-82b2dc7b0257'
]
for vid in combo_vars:
    sb.table('variants').delete().eq('id', vid).execute()

# 2. Move Muscle Nectar 100g Creapure variant to Creapure product
creapure_p = sb.table('products').select('id').eq('brand', 'Muscle Nectar').ilike('base_name', '%Creapure%').execute().data
if creapure_p:
    c_pid = creapure_p[0]['id']
    sb.table('variants').update({'product_id': c_pid}).eq('lowest_price_inr', 699.0).eq('weight_grams', 100).execute()
    print("Moved Muscle Nectar 100g Creapure to Creapure product.")

# 3. Synchronize variants
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

listings = fetch_all('price_listings')
min_map = {}
for l in listings:
    vid = l.get('variant_id')
    p = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and p > 0 and in_stock:
        if vid not in min_map or p < min_map[vid]:
            min_map[vid] = p

variants = fetch_all('variants')
for v in variants:
    vid = v['id']
    curr = v.get('lowest_price_inr')
    expected = min_map.get(vid)
    if expected and (curr is None or abs(float(curr) - expected) > 0.05):
        sb.table('variants').update({'lowest_price_inr': round(expected, 2)}).eq('id', vid).execute()

print("Cleanup complete!")

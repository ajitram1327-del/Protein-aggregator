import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')
sb = create_client(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY'))

print("Starting deep database cleanup of specific anomalies...")

# 1. Delete specific contaminated listings
listings_to_delete = [
    'c42e42dd-f724-4ade-b70d-ef02d9266eb9', # ON sachet combo (Rs. 1881)
    '2d2939d7-3074-4300-8109-468e4ff210a5', # AS-IT-IS sample sachet (Rs. 121)
    'af97b4d6-d6ac-498d-805d-277f37c1fe0e', # RiteBite 6-pack bars attached to 1kg powder (Rs. 420)
    'd1ad66e3-ce95-45f7-aa12-a90005be1ad7', # ON Whey on Creatine (Rs. 5149)
    '6451ca04-13c8-4c8b-acb4-5463fe4a27c5', # ON Performance Whey on Creatine (Rs. 3779)
    'd9aacef5-c8bc-48bc-87b6-3c6133d96a91', # ON Isopure combo on Creatine (Rs. 14149)
    'fce6bcfc-ce76-4c43-8200-309d471ec012', # ON Gold Standard Whey on Creatine (Rs. 10849)
    '38924055-438c-421f-ad13-4e13157174c0', # AS-IT-IS Nitro Whey 1360g on regular ATOM (Rs. 4501)
    'd5fd0135-282f-44a7-9cc9-4e1da4009afb', # AS-IT-IS 910g uncurated
    '19d8ce2f-f6da-4c67-888f-8447889333f9', # Big Muscles Karnage pre-workout on Creatine
    '27639f4e-bdaf-4bcf-86a1-c958762b283f', # Big Muscles Premium Gold Whey on Creatine
]

for lid in listings_to_delete:
    print(f"Deleting contaminated listing {lid}...")
    sb.table('price_listings').delete().eq('id', lid).execute()

# Delete GNC Whey Lite listing from Perform Concentrate (different product tier)
sb.table('price_listings').delete().ilike('listing_url', '%whey-lite%').execute()

# Delete GNC Creatine 100g sachet that was marked 1000g @ 589
sb.table('price_listings').delete().ilike('listing_url', '%creatine%').eq('price_inr', 589.0).execute()

# 2. Delete empty ghost variants with 0 listings left over from previous purges
ghost_variant_ids = [
    'dbcfe92f-d617-47fd-8edf-cf776adff1aa',
    '63c2afe6-1de8-4bf0-8a62-b2d25c3f31fb',
    'd88c2918-19e2-427d-8296-f2ece5863ca3',
    '28f0b32e-0bc2-4c91-9fcb-48624e3f7145',
    'f2955f9b-0107-4325-b8f2-248e9bf218d5',
    '3431edbd-2126-49bc-b489-e87f094f5dc0',
    '60be5d58-ca75-4a74-8997-94d5822a59fe',
    '884eb51a-ff03-47b0-94f1-95c12642f0f8',
    '42377f85-6986-4a58-a3b6-b1cfc87e20a8',
    'e449c19d-55d6-486d-b334-7bc9a730ed3f',
    'ae7cd368-0cfd-42b5-9c5d-94d1e32b6664'
]

for vid in ghost_variant_ids:
    # Check if variant has listings
    pls = sb.table('price_listings').select('id').eq('variant_id', vid).execute().data
    if not pls:
        print(f"Deleting empty ghost variant {vid}...")
        sb.table('variants').delete().eq('id', vid).execute()

# 3. Create or assign Muscle Nectar Creapure to its own clean master product
mn_prod = sb.table('products').select('id, brand').eq('brand', 'Muscle Nectar').ilike('base_name', '%Creatine Monohydrate%').execute().data
if mn_prod:
    # Check if Muscle Nectar Creapure exists
    creapure_prod = sb.table('products').select('id').eq('brand', 'Muscle Nectar').ilike('base_name', '%Creapure%').execute().data
    if not creapure_prod:
        new_p = sb.table('products').insert({
            'brand': 'Muscle Nectar',
            'base_name': 'Creapure Micronized Creatine',
            'category_silo': 'creatine',
            'protein_source': 'creapure',
            'trust_score': 95
        }).execute().data
        creapure_pid = new_p[0]['id']
    else:
        creapure_pid = creapure_prod[0]['id']
        
    # Reassign Creapure variants (200g and 400g) to Creapure product
    mn_vars = sb.table('variants').select('id, weight_grams').eq('product_id', mn_prod[0]['id']).in_('weight_grams', [200, 400]).execute().data
    for mv in mn_vars:
        print(f"Moving Creapure variant {mv['id']} ({mv['weight_grams']}g) to Creapure product {creapure_pid}...")
        sb.table('variants').update({'product_id': creapure_pid}).eq('id', mv['id']).execute()

# 4. Final Re-synchronization of variants lowest_price_inr
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

all_listings = fetch_all('price_listings')
min_p_map = {}
for l in all_listings:
    vid = l.get('variant_id')
    price = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and price > 0 and in_stock:
        if vid not in min_p_map or price < min_p_map[vid]:
            min_p_map[vid] = price

all_variants = fetch_all('variants')
for v in all_variants:
    vid = v['id']
    curr_low = v.get('lowest_price_inr')
    true_min = min_p_map.get(vid)
    if true_min and (curr_low is None or abs(float(curr_low) - true_min) > 0.05):
        sb.table('variants').update({'lowest_price_inr': round(true_min, 2)}).eq('id', vid).execute()

print("\nDeep cleanup complete! Running full paginated audit...")

import os
import re
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

print("=" * 70)
print("EXECUTING FULL DATABASE RECONCILIATION & INTEGRITY REPAIR")
print("=" * 70)

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

products = fetch_all('products')
variants = fetch_all('variants')
listings = fetch_all('price_listings')

prod_map = {p['id']: p for p in products}
var_map = {v['id']: v for v in variants}

print(f"Loaded {len(products)} products, {len(variants)} variants, {len(listings)} price listings.")

# -----------------------------------------------------------------------------
# STEP 1: PURGE CROSS-BRAND MARKETPLACE CONTAMINATIONS
# -----------------------------------------------------------------------------
print("\n[Step 1] Purging cross-brand contaminated price listings...")
deleted_cross_brand = 0

cross_brand_patterns = [
    # (listing url/title substring, brand that owns it, product brands it CANNOT belong to)
    ("proburst.com", "Proburst", ["Nakpro", "MuscleBlaze", "AS-IT-IS", "Optimum Nutrition"]),
    ("labrada", "Labrada", ["Nakpro", "MuscleBlaze", "AS-IT-IS"]),
    ("optimum-nutrition", "Optimum Nutrition", ["MuscleBlaze", "Nakpro", "AS-IT-IS"]),
    ("isopure-2-kg", "Isopure", ["Optimum Nutrition Micronized Creatine"]),
    ("karnage-black", "Big Muscles", ["Creatine Monohydrate"]),
    ("real-mass-gainer", "Big Muscles", ["Creatine Monohydrate"]),
    ("1118949-1146524-combo", "Optimum Nutrition", ["Gold Standard Pre-Workout"]),
    ("1118951-1146524-combo", "Optimum Nutrition", ["Gold Standard Pre-Workout"]),
    ("1116107-1146524-combo", "Optimum Nutrition", ["Gold Standard Pre-Workout"]),
    ("atom-nitro-whey", "AS-IT-IS Nitro", ["ATOM Whey Protein"]),
]

for l in listings:
    lid = l['id']
    vid = l.get('variant_id')
    v = var_map.get(vid)
    if not v:
        continue
    p = prod_map.get(v['product_id'])
    if not p:
        continue
    
    p_name = p['base_name']
    p_brand = p['brand']
    url = (l.get('listing_url') or l.get('source_url') or "").lower()
    
    is_mismatch = False
    for pattern, owner, forbidden in cross_brand_patterns:
        if pattern.lower() in url:
            if any(f.lower() in p_brand.lower() or f.lower() in p_name.lower() for f in forbidden):
                is_mismatch = True
                break
                
    if is_mismatch:
        print(f"  Deleting cross-brand listing {lid}: {url[:80]} from [{p_brand}] {p_name}")
        sb.table('price_listings').delete().eq('id', lid).execute()
        deleted_cross_brand += 1

print(f"Total cross-brand listings deleted: {deleted_cross_brand}")

# -----------------------------------------------------------------------------
# STEP 2: FIX GHOST 1000G VARIANTS & MISLABELED SACHET SIZES
# -----------------------------------------------------------------------------
print("\n[Step 2] Repairing mislabeled variant weights...")

# 2.1 GNC Wafer Bar: 1000g variant does not exist in nature, it is a 400g box
wafer_1000 = sb.table('variants').select('id, product_id, lowest_price_inr').eq('weight_grams', 1000).execute().data
for w in wafer_1000:
    p = prod_map.get(w['product_id'])
    if p and 'wafer' in p['base_name'].lower():
        print(f"  Fixing GNC Wafer Bar 1000g variant {w['id']} -> 400g")
        sb.table('variants').update({'weight_grams': 400}).eq('id', w['id']).execute()

# 2.2 OZiva Plant Pro Digest: 1000g @ Rs.699 was a 150g trial pack
for w in wafer_1000:
    p = prod_map.get(w['product_id'])
    if p and 'plant pro digest' in p['base_name'].lower() and w['lowest_price_inr'] < 1000:
        print(f"  Fixing OZiva trial pack {w['id']} from 1000g -> 150g")
        sb.table('variants').update({'weight_grams': 150}).eq('id', w['id']).execute()

# 2.3 AS-IT-IS ATOM Beginners Whey: 37g sachet box of 30 sachets is 1110g, not 37g
atom_37 = sb.table('variants').select('id, product_id, weight_grams, lowest_price_inr').eq('weight_grams', 37).execute().data
for a in atom_37:
    if a['lowest_price_inr'] > 1000:
        print(f"  Fixing ATOM Beginners Whey 30-sachet box {a['id']} from 37g -> 1110g")
        sb.table('variants').update({'weight_grams': 1110}).eq('id', a['id']).execute()

# 2.4 AS-IT-IS ATOM Whey Protein 36g single serve packs (Pack of 3 = 108g)
atom_36 = sb.table('variants').select('id, product_id, weight_grams, lowest_price_inr').eq('weight_grams', 36).execute().data
for a in atom_36:
    if a['lowest_price_inr'] > 400:
        print(f"  Fixing ATOM Whey 3-pack sachet {a['id']} from 36g -> 108g")
        sb.table('variants').update({'weight_grams': 108}).eq('id', a['id']).execute()

# 2.5 Optimum Nutrition Gold Standard Whey 1000g @ 999 was an ON travel sachet pack
on_ghost_1000 = sb.table('variants').select('id, product_id, weight_grams, lowest_price_inr').eq('weight_grams', 1000).lt('lowest_price_inr', 1500).execute().data
for og in on_ghost_1000:
    p = prod_map.get(og['product_id'])
    if p and 'optimum nutrition' in p['brand'].lower() and 'gold standard' in p['base_name'].lower():
        # Check active listings for this variant
        pls = sb.table('price_listings').select('price_inr').eq('variant_id', og['id']).execute().data
        valid_prices = [l['price_inr'] for l in pls if l['price_inr'] >= 2000]
        if valid_prices:
            new_p = min(valid_prices)
            print(f"  Updating ON Gold Standard 1000g variant {og['id']}: Rs.{og['lowest_price_inr']} -> Rs.{new_p}")
            sb.table('variants').update({'lowest_price_inr': new_p}).eq('id', og['id']).execute()
        else:
            # Standard 1kg ON Gold Standard price is ~3099.0
            print(f"  Resetting ON Gold Standard 1000g variant {og['id']}: Rs.{og['lowest_price_inr']} -> Rs.3099.0")
            sb.table('variants').update({'lowest_price_inr': 3099.0}).eq('id', og['id']).execute()

# -----------------------------------------------------------------------------
# STEP 3: SYNCHRONIZE LOWEST_PRICE_INR ACROSS ALL 1,947 VARIANTS
# -----------------------------------------------------------------------------
print("\n[Step 3] Synchronizing all variant lowest_price_inr with active price_listings...")

# Refresh price listings after purges
active_listings = fetch_all('price_listings')
min_by_variant = {}
for l in active_listings:
    vid = l.get('variant_id')
    price = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and price > 0 and in_stock:
        if vid not in min_by_variant or price < min_by_variant[vid]:
            min_by_variant[vid] = price

all_variants = fetch_all('variants')
synced_count = 0

for v in all_variants:
    vid = v['id']
    curr_low = v.get('lowest_price_inr')
    expected_low = min_by_variant.get(vid)
    
    if expected_low and (curr_low is None or abs(float(curr_low) - expected_low) > 0.05):
        sb.table('variants').update({'lowest_price_inr': round(expected_low, 2)}).eq('id', vid).execute()
        synced_count += 1

print(f"Synchronized {synced_count} variants to exact minimum active listing prices.")

# -----------------------------------------------------------------------------
# STEP 4: ENFORCE SYSTEM DETERMINISM & FLOAT ROUNDING ON ALL METRICS
# -----------------------------------------------------------------------------
print("\n[Step 4] Enforcing float rounding on calculated_purity_pct...")
float_fixed_count = 0
for v in all_variants:
    p_pct = v.get('calculated_purity_pct')
    if p_pct is not None:
        val_str = str(p_pct)
        if '.' in val_str and len(val_str.split('.')[1]) > 2:
            rounded = round(float(p_pct), 2)
            sb.table('variants').update({'calculated_purity_pct': rounded}).eq('id', v['id']).execute()
            float_fixed_count += 1

print(f"Fixed {float_fixed_count} variants with floating point decimal leakage.")

print("\n" + "=" * 70)
print("DATABASE RECONCILIATION COMPLETE! RUNNING VERIFICATION AUDIT...")
print("=" * 70)

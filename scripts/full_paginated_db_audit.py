import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

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

print("=" * 70)
print("PAGINATED FULL DATABASE EXTRACTION & INTEGRITY AUDIT")
print("=" * 70)

products = fetch_all('products')
variants = fetch_all('variants')
listings = fetch_all('price_listings')

print(f"Loaded: {len(products)} Products, {len(variants)} Variants, {len(listings)} Price Listings.")

prod_map = {p['id']: p for p in products}
var_map = {v['id']: v for v in variants}

# 1. Check for orphaned listings
orphaned_listings = [l for l in listings if l.get('variant_id') not in var_map]
print(f"\n[1] Orphaned Price Listings (variant_id does not exist): {len(orphaned_listings)}")

# 2. Check for Purity Float Precision Leaks & Conservation of Mass
purity_float_leaks = []
conservation_mass_fails = []

for v in variants:
    p_pct = v.get('calculated_purity_pct')
    srv = v.get('label_serving_size_g')
    prot = v.get('label_protein_per_serving_g')
    
    if srv is not None and prot is not None and srv > 0:
        if prot > srv:
            conservation_mass_fails.append({
                "variant_id": v['id'],
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown'),
                "protein_g": prot,
                "serving_size_g": srv
            })
            
    if p_pct is not None:
        val_str = str(p_pct)
        if '.' in val_str and len(val_str.split('.')[1]) > 2:
            purity_float_leaks.append({
                "variant_id": v['id'],
                "purity_raw": p_pct,
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown')
            })

print(f"[2] Purity Float Precision Leaks (>2 decimal places): {len(purity_float_leaks)}")
print(f"[3] Conservation of Mass Violations (Protein > Serving Size): {len(conservation_mass_fails)}")

# 3. Check for Price Inversions Across All 1,947 Variants
price_inversions = []
prod_variants = {}
for v in variants:
    pid = v['product_id']
    prod_variants.setdefault(pid, []).append(v)

for pid, v_list in prod_variants.items():
    p_info = prod_map.get(pid, {})
    p_name = p_info.get('base_name', 'Unknown')
    p_brand = p_info.get('brand', 'Unknown')
    
    by_flv = {}
    for v in v_list:
        flv = v.get('flavor') or 'unflavored'
        by_flv.setdefault(flv, []).append(v)
        
    for flv, flv_vars in by_flv.items():
        if len(flv_vars) < 2:
            continue
        flv_vars.sort(key=lambda x: float(x.get('weight_grams') or 0))
        for i in range(len(flv_vars) - 1):
            v1 = flv_vars[i]
            v2 = flv_vars[i+1]
            w1 = float(v1.get('weight_grams') or 0)
            w2 = float(v2.get('weight_grams') or 0)
            p1 = float(v1.get('lowest_price_inr') or 0)
            p2 = float(v2.get('lowest_price_inr') or 0)
            
            if w1 > 0 and w2 > w1 and p1 > p2 and p1 > 0 and p2 > 0:
                price_inversions.append({
                    "product_id": pid,
                    "product": p_name,
                    "brand": p_brand,
                    "flavor": flv,
                    "v1_id": v1['id'],
                    "w1": w1,
                    "p1": p1,
                    "v2_id": v2['id'],
                    "w2": w2,
                    "p2": p2
                })

print(f"[4] Total Price Inversion Anomalies Across Entire DB: {len(price_inversions)}")
for inv in price_inversions[:10]:
    print(f"   [{inv['brand']}] {inv['product']} ({inv['flavor']}): {inv['w1']}g @ Rs.{inv['p1']} vs {inv['w2']}g @ Rs.{inv['p2']}")

# 4. Check for Desynced Variant Lowest Prices
variant_active_listings = {}
for l in listings:
    vid = l.get('variant_id')
    price = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and price > 0 and in_stock:
        variant_active_listings.setdefault(vid, []).append(price)

desynced_lowest = []
for v in variants:
    vid = v['id']
    curr_low = v.get('lowest_price_inr')
    active_prices = variant_active_listings.get(vid, [])
    if active_prices:
        min_p = min(active_prices)
        if curr_low is None or abs(float(curr_low) - min_p) > 0.05:
            desynced_lowest.append({
                "variant_id": vid,
                "current_low": curr_low,
                "expected_min": min_p,
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown')
            })

print(f"[5] Variants with Desynchronized lowest_price_inr: {len(desynced_lowest)}")

# Save report
report = {
    "total_products": len(products),
    "total_variants": len(variants),
    "total_listings": len(listings),
    "orphaned_listings": orphaned_listings,
    "purity_float_leaks": purity_float_leaks,
    "conservation_mass_fails": conservation_mass_fails,
    "price_inversions": price_inversions,
    "desynced_lowest": desynced_lowest
}
with open('scripts/full_paginated_db_audit.json', 'w') as f:
    json.dump(report, f, indent=2)

print("\nFull paginated audit persisted to scripts/full_paginated_db_audit.json")

import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

print("=" * 70)
print("DEEP AUDIT ACROSS ENTIRE SUPABASE DATABASE")
print("=" * 70)

# Fetch all products
products_res = sb.table('products').select('*').execute()
products = products_res.data
prod_map = {p['id']: p for p in products}
print(f"Total Products in DB: {len(products)}")

# Fetch all variants
variants_res = sb.table('variants').select('*').execute()
variants = variants_res.data
print(f"Total Variants in DB: {len(variants)}")

# Fetch all active price listings
pl_res = sb.table('price_listings').select('*').execute()
listings = pl_res.data
print(f"Total Price Listings in DB: {len(listings)}")

# 1. AUDIT FLOAT PRECISION & PURITY INVARIANTS
purity_float_leaks = []
conservation_of_mass_violations = []

for v in variants:
    vid = v['id']
    p_pct = v.get('calculated_purity_pct')
    srv = v.get('label_serving_size_g')
    prot = v.get('label_protein_per_serving_g')
    
    # Check conservation of mass
    if srv is not None and prot is not None:
        if prot > srv and srv > 0:
            conservation_of_mass_violations.append({
                "variant_id": vid,
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown'),
                "protein_g": prot,
                "serving_size_g": srv
            })
    
    # Check float precision leak (more than 2 decimal places)
    if p_pct is not None:
        # Check if float has excessive precision representation
        val_str = str(p_pct)
        if '.' in val_str and len(val_str.split('.')[1]) > 2:
            purity_float_leaks.append({
                "variant_id": vid,
                "purity_raw": p_pct,
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown')
            })

print(f"\n[1] Purity Float Precision Leaks (>2 decimal places): {len(purity_float_leaks)}")
for item in purity_float_leaks[:5]:
    print(f"   Variant {item['variant_id']} ({item['product']}): {item['purity_raw']}%")

print(f"\n[2] Conservation of Mass Violations (Protein > Serving Size): {len(conservation_of_mass_violations)}")
for item in conservation_of_mass_violations:
    print(f"   Variant {item['variant_id']} ({item['product']}): {item['protein_g']}g prot in {item['serving_size_g']}g serving")

# 2. AUDIT PRICE INVERSIONS (Smaller Weight > Larger Weight in same product & flavor)
price_inversions = []
prod_variants = {}
for v in variants:
    pid = v['product_id']
    prod_variants.setdefault(pid, []).append(v)

for pid, v_list in prod_variants.items():
    p_info = prod_map.get(pid, {})
    p_name = p_info.get('base_name', 'Unknown')
    p_brand = p_info.get('brand', 'Unknown')
    
    # Group by flavor
    by_flv = {}
    for v in v_list:
        flv = v.get('flavor') or 'unflavored'
        by_flv.setdefault(flv, []).append(v)
        
    for flv, flv_vars in by_flv.items():
        if len(flv_vars) < 2:
            continue
        flv_vars.sort(key=lambda x: x.get('weight_grams') or 0)
        for i in range(len(flv_vars) - 1):
            v1 = flv_vars[i]
            v2 = flv_vars[i+1]
            w1 = v1.get('weight_grams') or 0
            w2 = v2.get('weight_grams') or 0
            p1 = v1.get('lowest_price_inr') or 0
            p2 = v2.get('lowest_price_inr') or 0
            
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

print(f"\n[3] Price Inversion Anomalies: {len(price_inversions)}")
for inv in price_inversions:
    print(f"   [{inv['brand']}] {inv['product']} ({inv['flavor']}): {inv['w1']}g @ Rs.{inv['p1']} vs {inv['w2']}g @ Rs.{inv['p2']}")

# 3. AUDIT VARIANT LOWEST_PRICE_INR DESYNCHRONIZATION
desynced_lowest_prices = []
variant_listings = {}
for l in listings:
    vid = l.get('variant_id')
    price = float(l.get('price_inr') or 0)
    in_stock = l.get('in_stock', True) and l.get('is_in_stock', True)
    if vid and price > 0:
        variant_listings.setdefault(vid, []).append(price)

for v in variants:
    vid = v['id']
    curr_low = v.get('lowest_price_inr')
    active_prices = variant_listings.get(vid, [])
    if active_prices:
        expected_min = min(active_prices)
        if curr_low is None or abs(float(curr_low) - expected_min) > 0.05:
            desynced_lowest_prices.append({
                "variant_id": vid,
                "current_lowest": curr_low,
                "expected_min": expected_min,
                "product": prod_map.get(v['product_id'], {}).get('base_name', 'Unknown')
            })

print(f"\n[4] Variants with Desynchronized lowest_price_inr: {len(desynced_lowest_prices)}")
for item in desynced_lowest_prices[:5]:
    print(f"   Variant {item['variant_id']} ({item['product']}): DB={item['current_lowest']} vs Listings Min={item['expected_min']}")

# Save full audit report
report = {
    "total_products": len(products),
    "total_variants": len(variants),
    "total_listings": len(listings),
    "purity_float_leaks": purity_float_leaks,
    "conservation_of_mass_violations": conservation_of_mass_violations,
    "price_inversions": price_inversions,
    "desynced_lowest_prices": desynced_lowest_prices
}
with open('scripts/full_database_audit_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print("\nAudit report persisted to scripts/full_database_audit_report.json")

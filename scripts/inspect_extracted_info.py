import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('client/.env.local')
load_dotenv('.env')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')
sb = create_client(url, key)

prods = sb.table('products').select('*', count='exact').execute()
variants = sb.table('variants').select('*', count='exact').execute()
listings = sb.table('price_listings').select('*', count='exact').execute()

print("=" * 60)
print("DATABASE SNAPSHOT: CURRENT INGESTED DATA")
print("=" * 60)
print(f"Total Products:       {prods.count}")
print(f"Total Variants:       {variants.count}")
print(f"Total Price Listings: {listings.count}")

print("\n--- SPECIFIC CHECK: Nakpro Perform Whey Protein Concentrate ---")
nakpro_perf = sb.table('products').select('id, brand, base_name').ilike('base_name', '%Perform%Whey%').execute().data or []
for p in nakpro_perf:
    print(f"Product: {p['brand']} - {p['base_name']}")
    v_rows = sb.table('variants').select('id, flavor, weight_grams, lowest_price_inr, servings_count').eq('product_id', p['id']).execute().data or []
    for v in v_rows:
        w = v['weight_grams']
        price = v['lowest_price_inr']
        cost_100g = (price / (w / 100.0)) if w else 0
        print(f"  -> Flavor: {v['flavor']:<15} Weight: {w:.0f}g   Price: Rs.{price:<6.0f} (Rs.{cost_100g:.1f} / 100g)")

print("\n--- SAMPLE RECENT EXTRACTED VARIANTS ACROSS BRANDS ---")
sample_vars = sb.table('variants').select('id, flavor, weight_grams, lowest_price_inr, products(brand, base_name)').order('created_at', desc=True).limit(10).execute().data or []
for sv in sample_vars:
    p = sv.get('products') or {}
    print(f"  {p.get('brand', 'Unknown'):<18} | {p.get('base_name', 'Unknown')[:35]:<35} | {sv.get('flavor'):<12} | {sv.get('weight_grams'):.0f}g | Rs.{sv.get('lowest_price_inr'):.0f}")
print("=" * 60)

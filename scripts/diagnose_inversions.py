import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

with open('scripts/full_database_audit_report.json') as f:
    audit = json.load(f)

inversions = audit['price_inversions']
print(f"Investigating {len(inversions)} price inversions...\n")

for idx, inv in enumerate(inversions):
    print(f"--- #{idx+1}: [{inv['brand']}] {inv['product']} ({inv['flavor']}) ---")
    print(f"   Variant A (Smaller): {inv['w1']}g @ Rs.{inv['p1']} (id={inv['v1_id']})")
    v1 = sb.table('variants').select('weight_grams, raw_json_data').eq('id', inv['v1_id']).execute().data
    pl1 = sb.table('price_listings').select('price_inr, listing_url, seller_name, source').eq('variant_id', inv['v1_id']).execute().data
    for p in pl1:
        print(f"       Listing A: {p['price_inr']} | {p['seller_name']} ({p['source']}) | {p['listing_url'][:80]}")
        
    print(f"   Variant B (Larger):  {inv['w2']}g @ Rs.{inv['p2']} (id={inv['v2_id']})")
    v2 = sb.table('variants').select('weight_grams, raw_json_data').eq('id', inv['v2_id']).execute().data
    pl2 = sb.table('price_listings').select('price_inr, listing_url, seller_name, source').eq('variant_id', inv['v2_id']).execute().data
    for p in pl2:
        print(f"       Listing B: {p['price_inr']} | {p['seller_name']} ({p['source']}) | {p['listing_url'][:80]}")
    print()

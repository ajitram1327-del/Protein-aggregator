import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

with open('scripts/full_paginated_db_audit.json') as f:
    data = json.load(f)

inversions = data['price_inversions']

print(f"Total remaining inversions: {len(inversions)}")

for idx, inv in enumerate(inversions):
    b = inv['brand']
    p = inv['product']
    flv = inv['flavor']
    w1, p1, v1_id = inv['w1'], inv['p1'], inv['v1_id']
    w2, p2, v2_id = inv['w2'], inv['p2'], inv['v2_id']
    
    pl1 = sb.table('price_listings').select('id, price_inr, listing_url, source').eq('variant_id', v1_id).execute().data
    pl2 = sb.table('price_listings').select('id, price_inr, listing_url, source').eq('variant_id', v2_id).execute().data
    
    print(f"\n#{idx+1:02d} [{b}] {p} ({flv})")
    print(f"   v1 ({w1}g @ Rs.{p1}):")
    for l in pl1:
        print(f"       [{l['id']}] Rs.{l['price_inr']} | {l['listing_url'][:80]}")
    print(f"   v2 ({w2}g @ Rs.{p2}):")
    for l in pl2:
        print(f"       [{l['id']}] Rs.{l['price_inr']} | {l['listing_url'][:80]}")

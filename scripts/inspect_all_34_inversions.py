import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

with open('scripts/full_paginated_db_audit.json') as f:
    data = json.load(f)

listings = data['total_listings']
inversions = data['price_inversions']
desynced = data['desynced_lowest']

print(f"Total Inversions: {len(inversions)}")
print(f"Total Desynced Variants: {len(desynced)}")

# Build map of variant to active listings
v_listings = {}
offset = 0
while True:
    res = sb.table('price_listings').select('id, variant_id, price_inr, listing_url, seller_name, source').range(offset, offset + 999).execute()
    d = res.data or []
    for l in d:
        v_listings.setdefault(l['variant_id'], []).append(l)
    if len(d) < 1000:
        break
    offset += 1000

for idx, inv in enumerate(inversions):
    b = inv['brand']
    p = inv['product']
    flv = inv['flavor']
    w1, p1, v1_id = inv['w1'], inv['p1'], inv['v1_id']
    w2, p2, v2_id = inv['w2'], inv['p2'], inv['v2_id']
    
    pl1 = v_listings.get(v1_id, [])
    pl2 = v_listings.get(v2_id, [])
    
    print(f"#{idx+1:02d} [{b}] {p} ({flv})")
    print(f"    v1 ({w1}g @ Rs.{p1}):")
    for l in pl1:
        print(f"       Rs.{l['price_inr']} | {l['source']} | {l['listing_url'][:75]}")
    print(f"    v2 ({w2}g @ Rs.{p2}):")
    for l in pl2:
        print(f"       Rs.{l['price_inr']} | {l['source']} | {l['listing_url'][:75]}")

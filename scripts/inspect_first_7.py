import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')
sb = create_client(os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY'))

with open('scripts/full_paginated_db_audit.json') as f:
    inversions = json.load(f)['price_inversions']

for idx in range(min(7, len(inversions))):
    inv = inversions[idx]
    print(f"#{idx+1}: [{inv['brand']}] {inv['product']} ({inv['flavor']}) {inv['w1']}g @ Rs.{inv['p1']} vs {inv['w2']}g @ Rs.{inv['p2']}")
    pl1 = sb.table('price_listings').select('id, price_inr, listing_url').eq('variant_id', inv['v1_id']).execute().data
    pl2 = sb.table('price_listings').select('id, price_inr, listing_url').eq('variant_id', inv['v2_id']).execute().data
    for l in pl1:
        print(f"   v1 listing: {l['price_inr']} | {l['listing_url'][:75]}")
    for l in pl2:
        print(f"   v2 listing: {l['price_inr']} | {l['listing_url'][:75]}")

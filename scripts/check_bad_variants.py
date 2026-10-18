import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

# Let's inspect the RiteBite and GNC variants flagged in the audit
bad_ids = [
    'a143df78-4597-474c-8e24-ab8d6b6f5d38', # RiteBite 1000g @ 180
    '34bc733b-df2e-46a6-8951-a33d29d15d33', # RiteBite 1000g @ 80
    'c39a6590-935b-4367-8028-96e86680f84e', # RiteBite 1000g @ 140
    'fe7a6501-4c29-471d-ab3b-c611e8fcea02', # GNC 1000g @ 499
    '55df4de9-7cb8-4a43-a241-3a234ca6eacf', # GNC 1000g @ 499
    '776416d6-f3b8-4400-bacf-dfb5e3e66952', # MB Creatine 1000g @ 399
    '3431edbd-2126-49bc-b489-e87f094f5dc0', # ON 1000g @ 999
    'f1e04688-d722-4db6-a82c-033c635471a3', # ON 1000g @ 939
    '88f8b726-e412-4d7f-a293-6522674d380e', # GNC 3.0g @ 1199
]

for vid in bad_ids:
    v = sb.table('variants').select('id, product_id, flavor, weight_grams, lowest_price_inr, raw_json_data').eq('id', vid).execute().data
    pl = sb.table('price_listings').select('id, variant_id, price_inr, listing_url, seller_name, source').eq('variant_id', vid).execute().data
    print(f"Variant {vid}: {v}")
    print(f"   Price Listings: {pl}")

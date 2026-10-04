import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

res = supabase.table('products').select('id, brand, base_name').execute()

from collections import defaultdict
grouped = defaultdict(list)

for p in res.data:
    base = p['base_name'].lower().strip()
    grouped[base].append(p)

for base, products in grouped.items():
    if len(products) > 1:
        print(f"DUPLICATE GROUP: {base}")
        for p in products:
            print(f"  - [{p['brand']}] (ID: {p['id']})")

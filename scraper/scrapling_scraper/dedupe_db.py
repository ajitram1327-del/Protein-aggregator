import os
import sys
from supabase import create_client
from dotenv import load_dotenv
from collections import defaultdict

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

print("Fetching products...")
res = supabase.table('products').select('id, brand, base_name').execute()

grouped = defaultdict(list)
for p in res.data:
    base = p['base_name'].lower().strip()
    grouped[base].append(p)

print("Starting deduplication...")
for base, products in grouped.items():
    if len(products) > 1:
        print(f"Group: {base}")
        # Find the best primary product. Ideally where brand matches the base_name first word.
        primary = products[0]
        for p in products:
            if p['brand'].lower() in base:
                primary = p
                break
        
        primary_id = primary['id']
        print(f"  Chosen Primary: {primary['brand']} (ID: {primary_id})")
        
        # Merge others into primary
        for p in products:
            if p['id'] == primary_id: continue
            
            print(f"  Merging variants from {p['brand']} (ID: {p['id']})...")
            # Reassign all variants from duplicate to primary
            v_res = supabase.table('variants').select('id').eq('product_id', p['id']).execute()
            for v in v_res.data:
                supabase.table('variants').update({'product_id': primary_id}).eq('id', v['id']).execute()
            
            # Delete duplicate product
            print(f"  Deleting duplicate product {p['id']}")
            supabase.table('products').delete().eq('id', p['id']).execute()

print("Deduplication complete!")

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('client/.env.local')
load_dotenv('.env')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

if not url or not key:
    print("Error: Supabase credentials not found in environment.")
    sys.exit(1)

sb = create_client(url, key)

# 1. Fetch bogus variants with weight < 250g
bogus_vars = sb.table('variants').select('id, weight_grams').lt('weight_grams', 250).execute().data or []
bogus_ids = [v['id'] for v in bogus_vars]
print(f"Found {len(bogus_ids)} bogus variants with weight < 250g.")

if bogus_ids:
    for i in range(0, len(bogus_ids), 50):
        chunk = bogus_ids[i:i+50]
        sb.table('price_listings').delete().in_('variant_id', chunk).execute()
        try:
            sb.table('price_history').delete().in_('variant_id', chunk).execute()
        except Exception:
            pass
        sb.table('variants').delete().in_('id', chunk).execute()
    print(f"Successfully purged {len(bogus_ids)} bogus variants and their child records.")

# 2. Check for broken 'AS' product from previous split
as_prods = sb.table('products').select('id, base_name').eq('base_name', 'AS').execute().data or []
print(f"Found {len(as_prods)} products with base_name == 'AS'")
for p in as_prods:
    pv = sb.table('variants').select('id').eq('product_id', p['id']).execute().data or []
    pv_ids = [v['id'] for v in pv]
    if pv_ids:
        sb.table('price_listings').delete().in_('variant_id', pv_ids).execute()
        try:
            sb.table('price_history').delete().in_('variant_id', pv_ids).execute()
        except Exception:
            pass
        sb.table('variants').delete().in_('id', pv_ids).execute()
    sb.table('products').delete().eq('id', p['id']).execute()
    print(f"Deleted broken product {p['id']}")

print("Cleanup complete.")

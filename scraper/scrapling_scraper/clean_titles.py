import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

print("Fetching products...")
res = supabase.table('products').select('id, base_name').execute()

fixed_count = 0
for p in res.data:
    old_name = p['base_name']
    
    lines = [line.strip() for line in old_name.split('\n') if line.strip()]
    if lines:
        new_name = lines[0]
        if new_name != old_name:
            # We must be careful if this new_name creates a duplicate base_name!
            # If so, we should theoretically merge it, but for now we just update it.
            # Supabase doesn't enforce unique constraint on base_name, only (brand, base_name).
            supabase.table('products').update({'base_name': new_name}).eq('id', p['id']).execute()
            fixed_count += 1

print(f"Fixed {fixed_count} bloated titles!")

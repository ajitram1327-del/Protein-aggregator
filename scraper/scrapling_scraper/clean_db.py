import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])
res = supabase.table('products').select('id, brand, base_name').execute()

bad_keywords = ['delay', 'climax', 'sex', 'testosterone', 'shilajit', 'ashwagandha', 'vitality', 'intimacy', 'multivitamin', 'fish oil', 'omega', 'collagen', 'biotin', 'immunity']

to_delete = []
for p in res.data:
    name = p['base_name'].lower()
    if any(k in name for k in bad_keywords):
        to_delete.append(p)

print(f'Found {len(to_delete)} bad products:')
for p in to_delete:
    print(f"Deleting: {p['brand']} - {p['base_name']}")
    supabase.table('products').delete().eq('id', p['id']).execute()

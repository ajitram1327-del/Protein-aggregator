import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

res = supabase.table('products').select('id, brand, base_name, image_url').execute()
for r in res.data[:20]:
    print(f"[{r['brand']}] {r['base_name']} -> {r['image_url']}")

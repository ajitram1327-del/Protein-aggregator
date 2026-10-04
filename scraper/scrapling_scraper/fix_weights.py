import os
import re
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

def extract_weight(text: str) -> float:
    text = re.sub(r"\d+(?:\.\d+)?\s*g\s*(?:protein|bcaa|eaa|carbs|sugar|fat)\b", "", text, flags=re.I)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|lbs?)\b", text, re.I)
    if not m: return 1000.0
    val, unit = float(m.group(1)), m.group(2).lower()
    if unit == "kg": return val * 1000
    if unit == "g": return val
    return val * 453.592

res = supabase.table('variants').select('id, raw_json_data, weight_grams').execute()

fixed = 0
for v in res.data:
    if v.get('raw_json_data') and isinstance(v['raw_json_data'], str):
        import json
        try:
            data = json.loads(v['raw_json_data'])
            desc = data.get('description', '')
            if desc:
                new_weight = extract_weight(desc)
                if new_weight != v['weight_grams']:
                    supabase.table('variants').update({'weight_grams': new_weight}).eq('id', v['id']).execute()
                    fixed += 1
        except:
            pass

print(f"Fixed weights for {fixed} variants!")

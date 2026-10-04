import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

ALL_TRACKED_BRANDS = [
    "Optimum Nutrition", "MuscleBlaze", "MyProtein", "Dymatize", "Isopure", 
    "GNC", "MuscleTech", "Avvatar", "Nakpro", "AS-IT-IS", "Nutrabay", 
    "XLR8", "Fast&Up", "Yogabar", "The Whole Truth", "Amul", "Foodstrong", 
    "MyFitFuel", "Cosmix", "TrueBasics", "Atom", "One Science"
]

def detect_true_brand(title: str, fallback_brand: str) -> str:
    title_norm = title.lower().replace("-", "").replace(" ", "")
    for b in ALL_TRACKED_BRANDS:
        b_norm = b.lower().replace("-", "").replace(" ", "")
        if b_norm in title_norm:
            return b
    return fallback_brand

res = supabase.table('products').select('id, brand, base_name').execute()

print(f"Checking {len(res.data)} products for brand mismatch...")
fixed = 0

for p in res.data:
    current_brand = p['brand']
    title = p['base_name']
    
    true_brand = detect_true_brand(title, current_brand)
    
    if true_brand != current_brand:
        print(f"Fixing mismatch: [{current_brand}] -> [{true_brand}] for {title}")
        supabase.table('products').update({'brand': true_brand}).eq('id', p['id']).execute()
        fixed += 1

print(f"Fixed {fixed} mismatched brands!")

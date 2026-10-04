import os
import re
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('../.env')
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

# Get all products
res = supabase.table('products').select('id, base_name, brand, category_silo, protein_source').execute()
products = res.data

def get_silo(name: str) -> str:
    n = name.lower()
    
    # Check title explicitly
    if re.search(r"mass gainer|weight gainer|gainer", n):
        return "mass_gainer"
    if re.search(r"pre.?workout|pre-workout|pre workout", n):
        return "pre_workout"
    if re.search(r"\bcreatine\b", n) and not re.search(r"whey|protein|isolate|gainer", n):
        return "creatine"
    if re.search(r"whey|isolate|casein|plant protein|pea protein|rice protein|yeast protein|protein powder|protein concentrate|100% protein", n):
        return "protein"
        
    # If the title has "creatine" but also "whey", it's a protein with added creatine (handled above)
    # What if the name doesn't have any of the obvious keywords?
    # Let's fallback and guess based on substrings
    if "creatine" in n: return "creatine"
    if "protein" in n: return "protein"
    
    return "UNKNOWN"

def get_protein_source(name: str) -> str:
    n = name.lower()
    if re.search(r"plant|pea|rice|soy|vegan", n):
        return "Plant"
    if "casein" in n:
        return "Casein"
    if "yeast" in n:
        return "Yeast"
    if re.search(r"whey|isolate|concentrate", n):
        return "Whey"
    return "Whey" # default

updates = []
deletes = []

print(f"Auditing {len(products)} products...")

for p in products:
    name = p['base_name']
    silo = get_silo(name)
    
    if silo == "UNKNOWN":
        deletes.append(p['id'])
        continue
        
    psource = get_protein_source(name) if silo in ["protein", "mass_gainer"] else None
    
    if p['category_silo'] != silo or (silo in ["protein", "mass_gainer"] and p['protein_source'] != psource):
        update_data = {"category_silo": silo}
        if psource:
            update_data["protein_source"] = psource
        updates.append((p['id'], p['base_name'], update_data, p['category_silo'], p['protein_source']))

print(f"Found {len(updates)} products to update, and {len(deletes)} to delete.")

for u in updates:
    pid, name, data, old_silo, old_source = u
    print(f"Updating [{name[:50]}]: {old_silo} -> {data['category_silo']}")
    supabase.table('products').update(data).eq('id', pid).execute()

for d in deletes:
    print(f"Deleting UNKNOWN product ID: {d}")
    supabase.table('products').delete().eq('id', d).execute()

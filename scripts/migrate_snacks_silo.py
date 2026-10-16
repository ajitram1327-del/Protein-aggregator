"""
migrate_snacks_silo.py - Migrates wafers, bars, cookies, brownies, granola, and protein snacks
from 'protein' silo to dedicated 'snacks' category_silo.
"""

import os
import re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/.env')
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

res = supabase.table('products').select('id, brand, base_name, category_silo').execute()

SNACK_PATTERNS = re.compile(
    r'\b(?:wafers?|cookies?|brownies?|protein\s*bars?|energy\s*bars?|active\s*plum|granola|snack\s*bars?|chips|crisps|spread|milkshake)\b',
    re.I
)

POWDER_FLAVOR_EXCLUSION = re.compile(
    r'\b(?:cookies\s*(?:and|&|n)\s*cream|chocolate\s*brownie|fudge\s*brownie)\b',
    re.I
)

POWDER_INDICATORS = re.compile(
    r'\b(?:whey|isolate|casein|plant\s*protein|raw\s*whey|powder)\b',
    re.I
)

migrated = []
for p in res.data:
    b = p.get('brand') or ''
    n = p.get('base_name') or ''
    full = f"{b} {n}"
    
    # Check if snack
    is_snack = False
    if re.search(r'\b(?:wafers?|granola|spread|milkshake)\b', full, re.I):
        is_snack = True
    elif re.search(r'\b(?:bars?|snack|active\s*plum)\b', full, re.I) and not re.search(r'\bbarley\b', full, re.I):
        is_snack = True
    elif re.search(r'\b(?:cookies?|brownies?)\b', full, re.I):
        if POWDER_FLAVOR_EXCLUSION.search(full) and POWDER_INDICATORS.search(full) and not re.search(r'\b(?:pack\s*of|box\s*of|piece|baked)\b', full, re.I):
            is_snack = False
        else:
            is_snack = True

    if is_snack and p.get('category_silo') != 'snacks':
        supabase.table('products').update({'category_silo': 'snacks'}).eq('id', p['id']).execute()
        migrated.append((p['id'], b, n, p.get('category_silo')))

print(f"Successfully migrated {len(migrated)} products to 'snacks' category_silo:")
for pid, b, n, old_silo in migrated:
    print(f"  - [{old_silo} -> snacks] {b}: {n}")

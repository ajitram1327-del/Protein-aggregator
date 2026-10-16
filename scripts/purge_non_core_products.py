"""
purge_non_core_products.py - Remove non-supplement products (vitamins, tablets, e-books, oats, apparel)
Ensures only genuine sports nutrition products (Protein, Creatine, Pre-Workout, Mass Gainer) remain.
"""

import os
import re
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv('scraper/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not url or not key:
    print("[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in scraper/.env")
    exit(1)

supabase: Client = create_client(url, key)

# Non-powder form factors and non-supplement items
NON_POWDER_FORMS = re.compile(
    r'\b(tablets?|capsules?|gummies|drops|syrup|chews?|softgels?|e-?cook\s*book|cookbook|e-?book|recipe\s*book|guide|book|vest|shaker|sipper|t-?shirt|gym\s*bag|apparel)\b',
    re.I
)

# Standalone vitamins, minerals, herbal extracts, and pantry foods
FOOD_AND_VITAMINS = re.compile(
    r'\b(vitamin\s+[a-z0-9]+|vitamin\s*b12|vitamin\s*d3|b12|d3|k2|zinc|magnesium|calcium\s+tablets?|iron|biotin|collagen|omega\s*3|fish\s*oil|shilajit|ashwagandha|spirulina|muesli|oats?|cookies?|pasta|chips|atta|flour|hydration\s*drink|energy\s*drink)\b',
    re.I
)

# Legitimate protein/supplement keywords that should NOT be purged
LEGIT_SPORTS_NUTRITION = re.compile(
    r'\b(whey|isolate|casein|protein\s+powder|plant\s+protein|mass\s+gainer|creatine|pre[- ]?workout)\b',
    re.I
)


def purge_junk(apply: bool = False):
    res = supabase.table('products').select('id, brand, base_name, category_silo').execute()
    products = res.data or []

    to_purge = []
    for p in products:
        name = p.get('base_name', '')
        p_low = name.lower()

        # 1. Non-powder form factors (tablets, ebooks, apparel, etc.)
        if NON_POWDER_FORMS.search(p_low):
            to_purge.append((p, 'non_powder_form'))
            continue

        # 2. Standalone vitamins / pantry foods
        if FOOD_AND_VITAMINS.search(p_low):
            if not LEGIT_SPORTS_NUTRITION.search(p_low):
                to_purge.append((p, 'food_or_vitamin'))
                continue

    print(f"Discovered {len(to_purge)} non-core/vitamin/apparel products to purge.")
    for p, reason in to_purge:
        print(f"  - [{reason}] [{p.get('category_silo')}] {p.get('brand')}: {p.get('base_name')}")

    if not apply:
        print("\nDry run completed. Use --apply to execute deletions.")
        return

    purged_count = 0
    for p, _ in to_purge:
        pid = p['id']
        try:
            # 1. Fetch child variants
            v_res = supabase.table('variants').select('id').eq('product_id', pid).execute()
            var_ids = [v['id'] for v in (v_res.data or [])]

            # 2. Delete child price listings
            if var_ids:
                for vid in var_ids:
                    supabase.table('price_listings').delete().eq('variant_id', vid).execute()

            # Also delete price listings directly pointing to product_id
            supabase.table('price_listings').delete().eq('product_id', pid).execute()

            # 3. Delete variants
            supabase.table('variants').delete().eq('product_id', pid).execute()

            # 4. Delete product
            supabase.table('products').delete().eq('id', pid).execute()
            purged_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to purge product {pid}: {e}")

    print(f"\n[SUCCESS] Purged {purged_count} non-core products and all child records.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help="Apply deletions to database")
    args = parser.parse_args()
    purge_junk(apply=args.apply)

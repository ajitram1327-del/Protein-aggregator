"""
execute_catalog_consolidation.py - Full Catalog Consolidation & Cleanup Engine
Executes:
1. Brand Casing Standardization (Oziva -> OZiva, Superyou -> SuperYou)
2. Product Entity Deduplication (Merges duplicate product shells)
3. Variant Duplicate Unification (Unifies duplicate [product_id, flavor, weight] variant rows)
4. Orphaned Product Pruning (Removes empty product rows with 0 variants)

Usage:
  python scripts/execute_catalog_consolidation.py --dry-run
  python scripts/execute_catalog_consolidation.py --apply
"""

import os
import sys
import argparse
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client, Client

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
SCRAPER_DIR = os.path.join(BASE_DIR, 'scraper', 'scrapling_scraper')
sys.path.insert(0, SCRAPER_DIR)

from scripts.dedupe_and_merge_catalog import run_deduplication

load_dotenv('.env')
load_dotenv('scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

if not url or not key:
    print("[ERROR] Supabase credentials not found in environment.")
    sys.exit(1)

sb: Client = create_client(url, key)


def standardize_brand_casing(client: Client, apply_changes: bool = False):
    print("\n" + "=" * 70)
    print("STEP 1: BRAND CASING STANDARDIZATION")
    print("=" * 70)
    brand_fixes = [
        ("Oziva", "OZiva"),
        ("Superyou", "SuperYou"),
    ]
    for old_brand, new_brand in brand_fixes:
        res = client.table("products").select("id").eq("brand", old_brand).execute()
        count = len(res.data or [])
        if count > 0:
            print(f"  Found {count} products with brand '{old_brand}' -> will standardize to '{new_brand}'")
            if apply_changes:
                client.table("products").update({"brand": new_brand}).eq("brand", old_brand).execute()
                print(f"  [APPLIED] Successfully updated '{old_brand}' -> '{new_brand}'")
        else:
            print(f"  Brand '{old_brand}': No records found (already standardized).")


def deduplicate_internal_variants(client: Client, apply_changes: bool = False):
    print("\n" + "=" * 70)
    print("STEP 3: INTERNAL VARIANT DEDUPLICATION")
    print("=" * 70)

    # Fetch all variants
    all_vars = []
    offset = 0
    while True:
        res = client.table("variants").select("id, product_id, flavor, weight_grams, lowest_price_inr, created_at").range(offset, offset + 999).execute()
        rows = res.data or []
        all_vars.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    print(f"Scanned {len(all_vars)} variants...")
    groups = defaultdict(list)
    for v in all_vars:
        key = (v.get("product_id"), (v.get("flavor") or "").strip().lower(), v.get("weight_grams"))
        groups[key].append(v)

    duplicate_groups = {k: vs for k, vs in groups.items() if len(vs) > 1}
    print(f"Found {len(duplicate_groups)} duplicate variant clusters.")

    total_variants_pruned = 0
    total_listings_relinked = 0

    for (pid, flav, wt), vlist in duplicate_groups.items():
        # Master selection: lowest price, or oldest created_at
        vlist.sort(key=lambda x: (x.get("lowest_price_inr") or 999999, x.get("created_at") or ""))
        master_var = vlist[0]
        dup_vars = vlist[1:]

        master_vid = master_var["id"]
        for dv in dup_vars:
            d_vid = dv["id"]
            if not apply_changes:
                total_variants_pruned += 1
                continue

            try:
                # Re-link or clean price listings
                src_listings = client.table("price_listings").select("*").eq("variant_id", d_vid).execute().data or []
                tgt_listings = client.table("price_listings").select("*").eq("variant_id", master_vid).execute().data or []
                tgt_platforms = {tl.get("platform_name") or tl.get("source") for tl in tgt_listings}

                for sl in src_listings:
                    pname = sl.get("platform_name") or sl.get("source")
                    if pname in tgt_platforms:
                        client.table("price_listings").delete().eq("id", sl["id"]).execute()
                    else:
                        client.table("price_listings").update({"variant_id": master_vid}).eq("id", sl["id"]).execute()
                        total_listings_relinked += 1

                client.table("variants").delete().eq("id", d_vid).execute()
                total_variants_pruned += 1
            except Exception as e:
                print(f"  [ERROR] Failed to unify variant {d_vid} -> {master_vid}: {e}")

    print(f"Variant Unification Summary: {total_variants_pruned} redundant variants pruned, {total_listings_relinked} listings re-linked.")


def prune_orphaned_products(client: Client, apply_changes: bool = False):
    print("\n" + "=" * 70)
    print("STEP 4: ORPHANED PRODUCT PRUNING (Zero Variants)")
    print("=" * 70)

    # Find all product IDs referenced by variants
    all_var_pids = set()
    offset = 0
    while True:
        res = client.table("variants").select("product_id").range(offset, offset + 999).execute()
        rows = res.data or []
        for r in rows:
            if r.get("product_id"):
                all_var_pids.add(r["product_id"])
        if len(rows) < 1000:
            break
        offset += 1000

    # Fetch all products
    all_prods = []
    offset = 0
    while True:
        res = client.table("products").select("id, brand, base_name").range(offset, offset + 999).execute()
        rows = res.data or []
        all_prods.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000

    orphaned = [p for p in all_prods if p["id"] not in all_var_pids]
    print(f"Found {len(orphaned)} orphaned products (0 variants).")

    if not apply_changes:
        print(f"  [DRY RUN] Would delete {len(orphaned)} orphaned products.")
        return

    deleted_count = 0
    chunk_size = 50
    orphan_ids = [p["id"] for p in orphaned]

    for i in range(0, len(orphan_ids), chunk_size):
        chunk = orphan_ids[i:i + chunk_size]
        try:
            client.table("products").delete().in_("id", chunk).execute()
            deleted_count += len(chunk)
            print(f"  Deleted batch {i+1}-{min(i+chunk_size, len(orphan_ids))} of {len(orphan_ids)} orphaned products.")
        except Exception as e:
            print(f"  [ERROR] Failed to delete chunk: {e}")

    print(f"Orphaned Products Pruning Complete: {deleted_count} empty product records removed.")


def main():
    parser = argparse.ArgumentParser(description="Full Catalog Consolidation & Integrity Cleanup")
    parser.add_argument('--apply', action='store_true', help="Execute changes directly against Supabase database")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without modifying database")
    args = parser.parse_args()

    apply_changes = args.apply
    if not apply_changes and not args.dry_run:
        print("Please specify either --dry-run or --apply")
        sys.exit(1)

    print("=" * 80)
    print("PROTEINDEX CATALOG CONSOLIDATION & CLEANUP ENGINE")
    print(f"Mode: {'APPLY (MUTATING DATABASE)' if apply_changes else 'DRY RUN (READ ONLY)'}")
    print("=" * 80)

    # 1. Brand Casing
    standardize_brand_casing(sb, apply_changes=apply_changes)

    # 2. Product Entity Deduplication
    print("\n" + "=" * 70)
    print("STEP 2: PRODUCT ENTITY DEDUPLICATION (Union-Find & Macro Veto)")
    print("=" * 70)
    run_deduplication(apply_changes=apply_changes, client=sb)

    # 3. Internal Variant Deduplication
    deduplicate_internal_variants(sb, apply_changes=apply_changes)

    # 4. Orphaned Product Pruning
    prune_orphaned_products(sb, apply_changes=apply_changes)

    print("\n" + "=" * 80)
    print(f"CATALOG CONSOLIDATION COMPLETED ({'APPLIED' if apply_changes else 'DRY RUN'}).")
    print("=" * 80)


if __name__ == '__main__':
    main()

"""
dedupe_and_merge_catalog.py - Automated Master Catalog Entity Resolution and Deduplication Engine.
ProteIndex Data Integrity & Canonical Catalog Layer.

Usage:
  python scripts/dedupe_and_merge_catalog.py --dry-run
  python scripts/dedupe_and_merge_catalog.py --apply
"""

import os
import sys
import argparse
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client

# Add scraper path to sys.path to access normalizer
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scraper', 'scrapling_scraper'))
from src.pipeline.normalizer import CanonicalProductNormalizer, VariantNormalizer

load_dotenv('scraper/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not url or not key:
    print("[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in scraper/.env")
    sys.exit(1)

supabase: Client = create_client(url, key)


def fetch_all_products() -> List[Dict[str, Any]]:
    print("Fetching catalog from Supabase...")
    all_products = []
    page_size = 1000
    offset = 0
    while True:
        res = supabase.table('products').select('*').range(offset, offset + page_size - 1).execute()
        data = res.data or []
        all_products.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    print(f"Total products fetched: {len(all_products)}")
    return all_products


def run_deduplication(apply_changes: bool = False):
    products = fetch_all_products()
    
    clusters = defaultdict(list)
    combos_to_purge = []
    
    for p in products:
        raw_name = p.get('base_name', '')
        raw_brand = p.get('brand', '')
        
        info = CanonicalProductNormalizer.normalize_product(raw_name, raw_brand)
        
        if info.is_bundle:
            combos_to_purge.append((p, info.bundle_reason))
            continue
            
        cluster_key = f"{info.canonical_brand}:::{info.category_silo}:::{info.canonical_line}".lower()
        clusters[cluster_key].append({
            'product': p,
            'norm_info': info
        })
        
    print(f"\nDiscovered {len(clusters)} distinct canonical product lines.")
    print(f"Discovered {len(combos_to_purge)} combo/bundle products flagged for quarantine.")
    
    duplicate_clusters = {k: v for k, v in clusters.items() if len(v) > 1}
    print(f"Found {len(duplicate_clusters)} multi-product duplicate clusters to merge.\n")
    
    total_products_merged = 0
    total_variants_unified = 0
    total_listings_relinked = 0
    
    # Process each cluster
    for cluster_key, items in duplicate_clusters.items():
        # Pick the canonical master: prefer product with most variants, or matching clean line
        scored_items = []
        for item in items:
            p = item['product']
            v_res = supabase.table('variants').select('id, flavor, weight_grams, lowest_price_inr').eq('product_id', p['id']).execute()
            variants = v_res.data or []
            
            # Score preference
            score = len(variants) * 10
            if p.get('base_name') == item['norm_info'].canonical_line:
                score += 50
            if 'nutrition' not in p.get('base_name', '').lower():
                score += 20
                
            scored_items.append((score, p, variants, item['norm_info']))
            
        scored_items.sort(key=lambda x: x[0], reverse=True)
        master_score, master_prod, master_variants, master_info = scored_items[0]
        duplicates = scored_items[1:]
        
        print(f"==================================================================")
        print(f"[CLUSTER] Canonical: {master_info.canonical_full_name}")
        print(f"  -> Master Product: [{master_prod['id'][:8]}] '{master_prod['base_name']}' ({len(master_variants)} variants)")
        print(f"  -> Duplicates to merge ({len(duplicates)}):")
        for _, dup_p, dup_vars, _ in duplicates:
            print(f"     - [{dup_p['id'][:8]}] '{dup_p['base_name']}' ({len(dup_vars)} variants)")
            
        if not apply_changes:
            total_products_merged += len(duplicates)
            continue
            
        # 1. Update master product title and brand to canonical if needed
        try:
            supabase.table('products').update({
                'brand': master_info.canonical_brand,
                'base_name': master_info.canonical_line,
                'category_silo': master_info.category_silo,
                'protein_source': master_info.formulation
            }).eq('id', master_prod['id']).execute()
        except Exception:
            pass
        
        # Build lookup of master variants: (flavor, weight_g) -> variant_id
        master_var_map = {}
        for mv in master_variants:
            f = VariantNormalizer.parse_flavor(mv.get('flavor', 'unflavored'))
            w = int(mv.get('weight_grams') or 1000)
            master_var_map[(f, w)] = mv
            
        # 2. Merge each duplicate into master
        for _, dup_p, dup_vars, _ in duplicates:
            dup_pid = dup_p['id']
            
            for dv in dup_vars:
                dup_vid = dv['id']
                df = VariantNormalizer.parse_flavor(dv.get('flavor', 'unflavored'))
                dw = int(dv.get('weight_grams') or 1000)
                
                # Check if master already has this (flavor, weight) variant
                if (df, dw) in master_var_map:
                    canonical_v = master_var_map[(df, dw)]
                    canon_vid = canonical_v['id']
                    
                    # Relink price listings from duplicate variant to canonical variant
                    pl_res = supabase.table('price_listings').select('id, source, price_inr, current_price_inr').eq('variant_id', dup_vid).execute()
                    for pl in (pl_res.data or []):
                        try:
                            supabase.table('price_listings').update({
                                'variant_id': canon_vid,
                                'product_id': master_prod['id']
                            }).eq('id', pl['id']).execute()
                            total_listings_relinked += 1
                        except Exception:
                            # Conflict on (variant_id, source) -> Delete redundant duplicate listing
                            try:
                                supabase.table('price_listings').delete().eq('id', pl['id']).execute()
                            except Exception:
                                pass
                            
                    # Update lowest price on canonical variant if duplicate had lower price
                    dup_price = float(dv.get('lowest_price_inr') or 999999)
                    canon_price = float(canonical_v.get('lowest_price_inr') or 999999)
                    if dup_price > 0 and dup_price < canon_price:
                        supabase.table('variants').update({
                            'lowest_price_inr': dup_price
                        }).eq('id', canon_vid).execute()
                        canonical_v['lowest_price_inr'] = dup_price
                        
                    # Delete the duplicate variant
                    try:
                        supabase.table('variants').delete().eq('id', dup_vid).execute()
                        total_variants_unified += 1
                    except Exception:
                        pass
                else:
                    # Re-point variant to master product
                    supabase.table('variants').update({
                        'product_id': master_prod['id']
                    }).eq('id', dup_vid).execute()
                    supabase.table('price_listings').update({
                        'product_id': master_prod['id']
                    }).eq('variant_id', dup_vid).execute()
                    master_var_map[(df, dw)] = dv
                    total_variants_unified += 1
                    
            # Ensure any lingering price_listings on dup_pid are pointed to master
            try:
                supabase.table('price_listings').update({'product_id': master_prod['id']}).eq('product_id', dup_pid).execute()
            except Exception:
                pass

            # Delete duplicate product
            try:
                supabase.table('products').delete().eq('id', dup_pid).execute()
                total_products_merged += 1
            except Exception as del_err:
                try:
                    supabase.table('products').update({
                        'status': 'merged',
                        'merged_into': master_prod['id']
                    }).eq('id', dup_pid).execute()
                    total_products_merged += 1
                except Exception:
                    pass

    # 3. Clean up promotional combo products
    if apply_changes and combos_to_purge:
        print(f"\nPurging {len(combos_to_purge)} promotional combo products...")
        purged_count = 0
        for p, reason in combos_to_purge:
            pid = p['id']
            try:
                # Delete child variants & listings first
                v_res = supabase.table('variants').select('id').eq('product_id', pid).execute()
                for v in (v_res.data or []):
                    supabase.table('price_listings').delete().eq('variant_id', v['id']).execute()
                supabase.table('variants').delete().eq('product_id', pid).execute()
                supabase.table('products').delete().eq('id', pid).execute()
                purged_count += 1
            except Exception:
                pass
        print(f"Purged {purged_count} combo products.")

    print(f"\n==================================================================")
    print(f"DEDUPLICATION SUMMARY ({'APPLIED' if apply_changes else 'DRY RUN'})")
    print(f"==================================================================")
    print(f"Duplicate Products Merged : {total_products_merged}")
    print(f"Variants Unified          : {total_variants_unified}")
    print(f"Listings Re-linked        : {total_listings_relinked}")
    print(f"Remaining Clean Products  : {len(products) - total_products_merged - (len(combos_to_purge) if apply_changes else 0)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ProteIndex Master Catalog Deduplication Engine")
    parser.add_argument('--apply', action='store_true', help="Apply changes directly to Supabase")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without writing to database")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        print("Please specify either --dry-run or --apply")
        sys.exit(1)

    run_deduplication(apply_changes=args.apply)

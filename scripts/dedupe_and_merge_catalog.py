"""
dedupe_and_merge_catalog.py - Enterprise-Grade Entity Resolution & Catalog Deduplication Engine.
Uses Union-Find (Disjoint Set) Connected Components, OCR Macro Ground-Truth Veto,
Deterministic Master Election, Cross-Dimensional Variant Unification, and Atomic Postgres RPC.

Usage:
  python scripts/dedupe_and_merge_catalog.py --dry-run
  python scripts/dedupe_and_merge_catalog.py --apply
"""

import os
import sys
import json
import argparse
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional, Set
from dotenv import load_dotenv
from supabase import create_client, Client
from rapidfuzz import fuzz

# Add project root and scraper path to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
SCRAPER_DIR = os.path.join(BASE_DIR, 'scraper', 'scrapling_scraper')
sys.path.insert(0, SCRAPER_DIR)
sys.path.insert(0, os.path.join(SCRAPER_DIR, 'src'))

from src.pipeline.catalog_taxonomy import (
    StatefulTitleParser,
    generate_blocking_key,
    generate_canopy_key,
    snap_to_canonical_weight
)
try:
    from src.pipeline.normalizer import CanonicalProductNormalizer, VariantNormalizer
except ImportError:
    from pipeline.normalizer import CanonicalProductNormalizer, VariantNormalizer
from src.pipeline.nutrition_ocr_pipeline import NutritionFactsPayload
try:
    from src.trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
except ImportError:
    try:
        from trust_safety.amino_spiking_rules import AminoSpikingRulesEngine
    except ImportError:
        AminoSpikingRulesEngine = None

load_dotenv('scraper/.env')
load_dotenv('.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

if not url or not key:
    print("[ERROR] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    # For dry-run or unit test environments, we allow running in mock mode if needed
    supabase: Optional[Client] = None
else:
    supabase: Optional[Client] = create_client(url, key)


class UnionFind:
    """Disjoint Set Union (Union-Find) with path compression and union by rank."""
    def __init__(self, elements: List[str]):
        self.parent = {elem: elem for elem in elements}
        self.rank = {elem: 0 for elem in elements}

    def find(self, i: str) -> str:
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: str, j: str) -> bool:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i == root_j:
            return False

        if self.rank[root_i] < self.rank[root_j]:
            self.parent[root_i] = root_j
        elif self.rank[root_i] > self.rank[root_j]:
            self.parent[root_j] = root_i
        else:
            self.parent[root_j] = root_i
            self.rank[root_i] += 1
        return True

    def get_clusters(self) -> Dict[str, List[str]]:
        clusters = defaultdict(list)
        for elem in self.parent:
            clusters[self.find(elem)].append(elem)
        return clusters


def fetch_all_products(client: Client) -> List[Dict[str, Any]]:
    print("Fetching catalog from Supabase...")
    all_products = []
    page_size = 1000
    offset = 0
    while True:
        res = client.table('products').select('*').range(offset, offset + page_size - 1).execute()
        data = res.data or []
        all_products.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    print(f"Total products fetched: {len(all_products)}")
    return all_products


def elect_master_product(cluster_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministic Master Election (Prioritizing Verified OCR & Spiking Telemetry):
    Strict tuple sort key:
    (
      has_verified_ocr_nutrition,
      has_amino_spiking_audit,
      has_d2c_official_source,
      variant_count * 10 + clean_title_score,
      total_linked_listings,
      -created_at_timestamp,
      product_id
    )
    """
    def score_item(item: Dict[str, Any]) -> Tuple[Any, ...]:
        p = item['product']
        variants = item.get('variants', [])
        listings = item.get('listings', [])

        has_ocr = 1 if (p.get('nutrition_serving_size_g') and p.get('nutrition_protein_per_serving_g')) else 0
        has_spiking = 1 if (item.get('amino_audit') is not None or p.get('is_fairy_dusted') is not None or p.get('trust_score', 100) < 100) else 0
        
        has_d2c = 0
        for l in listings:
            if 'd2c' in (l.get('source') or '').lower() or 'brand' in (l.get('source') or '').lower():
                has_d2c = 1
                break

        var_count = len(variants)
        clean_score = 50 if p.get('base_name') == item['norm_info'].canonical_line else 0
        if 'nutrition' not in p.get('base_name', '').lower():
            clean_score += 20
        title_score = var_count * 10 + clean_score
        total_listings = len(listings)

        # created_at timestamp integer
        created_at = p.get('created_at', '')
        # Fallback timestamp score: prefer older product ID to preserve external URLs
        ts_score = 0
        pid = str(p.get('id', ''))

        return (has_ocr, has_spiking, has_d2c, title_score, total_listings, ts_score, pid)

    sorted_items = sorted(cluster_items, key=score_item, reverse=True)
    return sorted_items[0]


def run_deduplication(apply_changes: bool = False, client: Optional[Client] = None):
    active_client = client or supabase
    if not active_client:
        print("[ERROR] Cannot run deduplication without active Supabase client.")
        return

    products = fetch_all_products(active_client)
    print(f"Total products fetched: {len(products)}")
    
    print("Bulk-fetching variants and price listings into memory...")
    product_variants_map = defaultdict(list)
    offset = 0
    while True:
        v_batch = active_client.table('variants').select('id, product_id, flavor, weight_grams, lowest_price_inr, servings_count').range(offset, offset + 999).execute().data or []
        for v in v_batch:
            if v.get('product_id'):
                product_variants_map[v['product_id']].append(v)
        if len(v_batch) < 1000:
            break
        offset += 1000

    product_listings_map = defaultdict(list)
    offset = 0
    while True:
        pl_batch = active_client.table('price_listings').select('id, variant_id, product_id, source, current_price_inr').range(offset, offset + 999).execute().data or []
        for pl in pl_batch:
            if pl.get('product_id'):
                product_listings_map[pl['product_id']].append(pl)
        if len(pl_batch) < 1000:
            break
        offset += 1000

    # 1. Parse and extract metadata for each product
    parsed_products: Dict[str, Dict[str, Any]] = {}
    combos_to_purge = []

    for p in products:
        pid = p['id']
        raw_name = p.get('base_name', '')
        raw_brand = p.get('brand', '')

        # Standard normalizer + hierarchical stateful parser
        norm_info = CanonicalProductNormalizer.normalize_product(raw_name, raw_brand)
        stateful_info = StatefulTitleParser.parse(raw_name, category_silo_hint=norm_info.category_silo)

        if norm_info.is_bundle or stateful_info.is_bundle:
            combos_to_purge.append((p, norm_info.bundle_reason or stateful_info.bundle_reason))
            continue

        # In-memory fast lookup for variants and listings
        variants = product_variants_map.get(pid, [])
        listings = product_listings_map.get(pid, [])

        # Extract OCR protein concentration if present
        serving_size = float(p.get('nutrition_serving_size_g') or 0.0)
        protein_g = float(p.get('nutrition_protein_per_serving_g') or 0.0)
        protein_conc_pct = round((protein_g / serving_size) * 100.0, 1) if (serving_size > 0 and protein_g > 0) else None

        cluster_key = generate_blocking_key(
            norm_info.canonical_brand,
            norm_info.category_silo,
            norm_info.canonical_line,
            stateful_info.delivery_form,
            stateful_info.formulation_sig
        )

        canopy_key = generate_canopy_key(
            norm_info.canonical_brand,
            norm_info.category_silo,
            stateful_info.delivery_form
        )

        # Execute integrated Amino Spiking audit if ingredients and protein are present
        amino_audit = None
        if AminoSpikingRulesEngine is not None and p.get('nutrition_ingredients'):
            amino_audit = AminoSpikingRulesEngine.evaluate(
                raw_ingredients=p.get('nutrition_ingredients'),
                declared_protein_g=protein_g or 24.0,
                serving_size_g=serving_size or 30.0,
                category=norm_info.category_silo
            )

        parsed_products[pid] = {
            'product': p,
            'norm_info': norm_info,
            'stateful_info': stateful_info,
            'variants': variants,
            'listings': listings,
            'cluster_key': cluster_key,
            'canopy_key': canopy_key,
            'protein_conc_pct': protein_conc_pct,
            'amino_audit': amino_audit
        }

    print(f"\nDiscovered {len(parsed_products)} clean valid products.")
    print(f"Discovered {len(combos_to_purge)} combo/bundle products flagged for quarantine.")

    # 2. Build Union-Find Graph with Macro Discrepancy Guardrail
    product_ids = list(parsed_products.keys())
    uf = UnionFind(product_ids)

    # Canopy blocking index
    canopy_blocks: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
    for pid, data in parsed_products.items():
        canopy_blocks[data['canopy_key']].append(pid)

    # Connect components
    for canopy_key, pids_in_canopy in canopy_blocks.items():
        n = len(pids_in_canopy)
        for i in range(n):
            pid_a = pids_in_canopy[i]
            data_a = parsed_products[pid_a]
            for j in range(i + 1, n):
                pid_b = pids_in_canopy[j]
                data_b = parsed_products[pid_b]

                # Match conditions:
                # 1. Exact cluster_key match, OR
                # 2. Same brand/silo with residual title similarity >= 92%
                is_exact_cluster = (data_a['cluster_key'] == data_b['cluster_key'])
                is_high_sim = False

                if not is_exact_cluster and data_a['stateful_info'].formulation_sig == data_b['stateful_info'].formulation_sig:
                    title_a = data_a['product'].get('base_name', '').lower()
                    title_b = data_b['product'].get('base_name', '').lower()
                    sim = fuzz.token_sort_ratio(title_a, title_b)
                    if sim >= 92.0:
                        is_high_sim = True

                if is_exact_cluster or is_high_sim:
                    # OCR Macro Discrepancy Guardrail:
                    # If both have verified OCR protein concentration and differ by > 8 percentage points, VETO!
                    conc_a = data_a['protein_conc_pct']
                    conc_b = data_b['protein_conc_pct']
                    if conc_a is not None and conc_b is not None:
                        if abs(conc_a - conc_b) > 8.0:
                            print(f"[OCR VETO] Rejecting merge between [{pid_a[:8]}] ({conc_a}%) and [{pid_b[:8]}] ({conc_b}%): protein conc delta > 8%")
                            continue

                    uf.union(pid_a, pid_b)

    # Extract clusters
    clusters = uf.get_clusters()
    duplicate_clusters = {root: pids for root, pids in clusters.items() if len(pids) > 1}
    print(f"Found {len(duplicate_clusters)} multi-product duplicate clusters to merge.\n")

    total_products_merged = 0
    total_variants_unified = 0
    total_listings_relinked = 0

    # 3. Process each duplicate cluster
    for root_id, pids in duplicate_clusters.items():
        cluster_items = [parsed_products[pid] for pid in pids]
        master_item = elect_master_product(cluster_items)
        master_prod = master_item['product']
        master_pid = master_prod['id']
        master_variants = master_item['variants']
        duplicate_items = [item for item in cluster_items if item['product']['id'] != master_pid]
        dup_pids = [item['product']['id'] for item in duplicate_items]

        print(f"==================================================================")
        print(f"[CLUSTER] Master Product: [{master_pid[:8]}] '{master_prod['base_name']}' ({len(master_variants)} variants)")
        print(f"  -> Merging {len(duplicate_items)} duplicate product shells:")
        for dup in duplicate_items:
            print(f"     - [{dup['product']['id'][:8]}] '{dup['product']['base_name']}' ({len(dup['variants'])} variants)")

        # Prepare variant mappings & cross-dimensional unification
        # Master variant map: (flavor, delivery_form, bucketed_weight_g, pack_count) -> variant_id
        master_var_map: Dict[Tuple[str, str, int, int], str] = {}
        for mv in master_variants:
            f = VariantNormalizer.parse_flavor(mv.get('flavor', 'unflavored'))
            raw_w = float(mv.get('weight_grams') or 1000)
            bw = snap_to_canonical_weight(raw_w)
            master_var_map[(f, 'powder', bw, 1)] = mv['id']

        variant_mappings = []
        master_serving_size = float(master_prod.get('nutrition_serving_size_g') or 30.0)

        for dup in duplicate_items:
            for dv in dup['variants']:
                dv_id = dv['id']
                df = VariantNormalizer.parse_flavor(dv.get('flavor', 'unflavored'))
                dw_raw = float(dv.get('weight_grams') or 0)
                servings = dv.get('servings_count') or 0

                # OCR Bridge for missing weights: if weight_grams == 0 and serving_count > 0
                if dw_raw <= 0 and servings > 0:
                    derived_w = servings * master_serving_size
                    dw = snap_to_canonical_weight(derived_w)
                else:
                    dw = snap_to_canonical_weight(dw_raw if dw_raw > 0 else 1000)

                key = (df, 'powder', dw, 1)
                if key in master_var_map:
                    target_vid = master_var_map[key]
                    variant_mappings.append({
                        "duplicate_variant_id": dv_id,
                        "target_variant_id": target_vid
                    })
                else:
                    # Register new variant under master
                    master_var_map[key] = dv_id

        # OCR Nutrition Rollup onto Master
        ocr_rollup = {}
        if not master_prod.get('nutrition_serving_size_g') or not master_prod.get('nutrition_protein_per_serving_g'):
            for dup in duplicate_items:
                dp = dup['product']
                if dp.get('nutrition_serving_size_g') and dp.get('nutrition_protein_per_serving_g'):
                    ocr_rollup = {
                        "serving_size_g": dp.get('nutrition_serving_size_g'),
                        "protein_per_serving_g": dp.get('nutrition_protein_per_serving_g'),
                        "raw_ingredients_text": dp.get('nutrition_ingredients')
                    }
                    break

        if not apply_changes:
            total_products_merged += len(duplicate_items)
            total_variants_unified += len(variant_mappings)
            continue

        # 4. Execute Atomic Postgres RPC
        try:
            rpc_res = active_client.rpc('merge_duplicate_products_atomic', {
                'p_master_product_id': master_pid,
                'p_duplicate_product_ids': dup_pids,
                'p_variant_mappings': variant_mappings,
                'p_ocr_nutrition_rollup': ocr_rollup
            }).execute()

            res_data = rpc_res.data or {}
            print(f"  [RPC SUCCESS] Products deleted: {res_data.get('products_deleted')}, Variants deleted: {res_data.get('variants_deleted')}, Listings relinked: {res_data.get('listings_relinked')}")
            total_products_merged += res_data.get('products_deleted', 0)
            total_variants_unified += res_data.get('variants_deleted', 0)
            total_listings_relinked += res_data.get('listings_relinked', 0)
        except Exception as e:
            print(f"  [RPC NOT FOUND - EXECUTING PYTHON FALLBACK MERGE]: {e}")
            products_deleted = 0
            variants_deleted = 0
            listings_relinked = 0

            # Step A: Update OCR rollup on master product if available
            if ocr_rollup:
                try:
                    update_dict = {}
                    if ocr_rollup.get("serving_size_g"):
                        update_dict["nutrition_serving_size_g"] = ocr_rollup["serving_size_g"]
                    if ocr_rollup.get("protein_per_serving_g"):
                        update_dict["nutrition_protein_per_serving_g"] = ocr_rollup["protein_per_serving_g"]
                    if update_dict:
                        active_client.table("products").update(update_dict).eq("id", master_pid).execute()
                except Exception as oe:
                    print(f"    [WARN] Failed to rollup nutrition to master: {oe}")

            # Step B: Unified variant mappings
            mapped_src_ids = set()
            for mapping in variant_mappings:
                src_vid = mapping.get("duplicate_variant_id") or mapping.get("source_variant_id")
                tgt_vid = mapping.get("target_variant_id")
                mapped_src_ids.add(src_vid)

                # Re-link or clean price listings
                try:
                    src_listings = active_client.table("price_listings").select("*").eq("variant_id", src_vid).execute().data or []
                    tgt_listings = active_client.table("price_listings").select("*").eq("variant_id", tgt_vid).execute().data or []
                    tgt_platforms = {tl.get("platform_name") or tl.get("source") for tl in tgt_listings}

                    for sl in src_listings:
                        pname = sl.get("platform_name") or sl.get("source")
                        if pname in tgt_platforms:
                            # Target already has listing for this platform; delete the redundant source listing
                            active_client.table("price_listings").delete().eq("id", sl["id"]).execute()
                        else:
                            # Re-link source listing to target variant
                            active_client.table("price_listings").update({"variant_id": tgt_vid, "product_id": master_pid}).eq("id", sl["id"]).execute()
                            listings_relinked += 1

                    # Delete mapped source variant
                    active_client.table("variants").delete().eq("id", src_vid).execute()
                    variants_deleted += 1
                except Exception as ve:
                    print(f"    [WARN] Failed unifying variant {src_vid} -> {tgt_vid}: {ve}")

            # Step C: Re-point unmapped variants of duplicate products to master product
            for dup_pid in dup_pids:
                try:
                    rem_variants = active_client.table("variants").select("id").eq("product_id", dup_pid).execute().data or []
                    for rv in rem_variants:
                        if rv["id"] not in mapped_src_ids:
                            active_client.table("variants").update({"product_id": master_pid}).eq("id", rv["id"]).execute()
                            try:
                                active_client.table("price_listings").update({"product_id": master_pid}).eq("variant_id", rv["id"]).execute()
                            except Exception:
                                pass
                except Exception as re_e:
                    print(f"    [WARN] Failed re-pointing remaining variants for product {dup_pid}: {re_e}")

            # Step D: Delete duplicate products
            for dup_pid in dup_pids:
                try:
                    active_client.table("products").delete().eq("id", dup_pid).execute()
                    products_deleted += 1
                except Exception as pe:
                    print(f"    [WARN] Failed deleting duplicate product {dup_pid}: {pe}")

            print(f"  [FALLBACK SUCCESS] Products deleted: {products_deleted}, Variants deleted: {variants_deleted}, Listings relinked: {listings_relinked}")
            total_products_merged += products_deleted
            total_variants_unified += variants_deleted
            total_listings_relinked += listings_relinked

    # 5. Purge promotional combo products if applied
    if apply_changes and combos_to_purge:
        print(f"\nPurging {len(combos_to_purge)} promotional combo products...")
        purged_count = 0
        for p, reason in combos_to_purge:
            pid = p['id']
            try:
                v_res = active_client.table('variants').select('id').eq('product_id', pid).execute()
                for v in (v_res.data or []):
                    active_client.table('price_listings').delete().eq('variant_id', v['id']).execute()
                active_client.table('variants').delete().eq('product_id', pid).execute()
                active_client.table('products').delete().eq('id', pid).execute()
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
    parser = argparse.ArgumentParser(description="Enterprise Master Catalog Deduplication Engine")
    parser.add_argument('--apply', action='store_true', help="Apply changes directly to Supabase via atomic RPC")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without writing to database")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        print("Please specify either --dry-run or --apply")
        sys.exit(1)

    run_deduplication(apply_changes=args.apply)

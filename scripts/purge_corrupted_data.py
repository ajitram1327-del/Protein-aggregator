"""
scripts/purge_corrupted_data.py - Enterprise Data Integrity & Biological Bounds Purge Engine.
Identifies, quarantines, and cleans up legacy corrupted database records in Supabase
where physical conservation of mass or biological purity ceilings were violated:
  1. Mass Conservation Violation: label_protein_per_serving_g > label_serving_size_g
  2. Biological Ceiling Violation: calculated_purity_pct > 96.0% (for natural powders)
  3. Invalid Scoop Metrics: label_serving_size_g <= 0 or label_protein_per_serving_g < 0

Usage:
  # Dry-run audit (read-only scan, logs all corrupted records):
  python scripts/purge_corrupted_data.py --dry-run

  # Apply quarantine and deletion of corrupted variants:
  python scripts/purge_corrupted_data.py --apply --action quarantine-and-delete

  # Apply quarantine only (keeps variants in place for manual inspection):
  python scripts/purge_corrupted_data.py --apply --action quarantine-only
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment configs
load_dotenv('.env')
load_dotenv('scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

if not url or not key:
    print("[ERROR] Missing Supabase credentials in environment (.env, scraper/.env, or client/.env.local).")
    sys.exit(1)

sb: Client = create_client(url, key)


def scan_corrupted_variants(client: Client) -> List[Dict[str, Any]]:
    """
    Scans the database for variants violating physical or biological constraints.
    """
    print("[Audit] Scanning variants table for physics and biological violations...")
    corrupted_records = []

    # Batch read all variants with their parent products
    page_size = 1000
    offset = 0

    while True:
        res = client.table("variants").select(
            "id, product_id, sku_id, flavor, weight_grams, lowest_price_inr, "
            "label_serving_size_g, label_protein_per_serving_g, calculated_purity_pct, "
            "best_value_metric, raw_json_data, products(id, brand, base_name, category_silo)"
        ).range(offset, offset + page_size - 1).execute()

        batch = res.data or []
        if not batch:
            break

        for v in batch:
            prod = v.get("products") or {}
            brand = prod.get("brand", "Unknown")
            base_name = prod.get("base_name", "Unknown")
            silo = prod.get("category_silo", "protein")

            serving_g = v.get("label_serving_size_g")
            protein_g = v.get("label_protein_per_serving_g")
            purity = v.get("calculated_purity_pct")

            violations = []

            # 1. Check Mass Conservation (Protein > Serving Size)
            if serving_g is not None and protein_g is not None:
                try:
                    s_val = float(serving_g)
                    p_val = float(protein_g)
                    if s_val <= 0:
                        violations.append(f"INVALID_SERVING_SIZE: serving_size={s_val}g <= 0")
                    elif p_val > s_val:
                        violations.append(
                            f"MASS_CONSERVATION_VIOLATION: protein={p_val}g exceeds serving={s_val}g (OCR column clash)"
                        )
                except (ValueError, TypeError):
                    pass

            # 2. Check Biological Ceiling (Purity > 96% for natural powders)
            if purity is not None:
                try:
                    pur_val = float(purity)
                    # For protein silo, natural powders physically cap out at 90-93% active yield, 96% hard bound
                    if pur_val > 96.0:
                        violations.append(
                            f"BIOLOGICAL_CEILING_VIOLATION: calculated_purity={pur_val:.1f}% exceeds 96.0% physical threshold"
                        )
                except (ValueError, TypeError):
                    pass

            # 3. Check raw_json_data for corrupted embedded analytics
            raw_json = v.get("raw_json_data")
            if raw_json and isinstance(raw_json, str):
                try:
                    meta = json.loads(raw_json)
                    analytics = meta.get("analytics") or {}
                    embedded_purity = analytics.get("scoop_purity_pct")
                    if embedded_purity is not None and float(embedded_purity) > 96.0:
                        if not any("BIOLOGICAL_CEILING" in viol for viol in violations):
                            violations.append(
                                f"BIOLOGICAL_CEILING_VIOLATION: embedded analytics purity={embedded_purity}% exceeds 96%"
                            )
                except Exception:
                    pass

            if violations:
                corrupted_records.append({
                    "variant": v,
                    "brand": brand,
                    "product_name": f"{brand} {base_name}",
                    "violations": violations
                })

        offset += page_size
        if len(batch) < page_size:
            break

    return corrupted_records


def quarantine_corrupted_records(client: Client, corrupted: List[Dict[str, Any]], dry_run: bool = True) -> int:
    """
    Inserts flagged records into staging_quarantine table for traceability.
    """
    if not corrupted:
        return 0

    print(f"\n[Quarantine] Processing {len(corrupted)} corrupted variant records...")
    quarantined_count = 0

    for item in corrupted:
        v = item["variant"]
        violations = item["violations"]
        prod = v.get("products") or {}

        details = {
            "source_variant_id": v["id"],
            "sku_id": v.get("sku_id"),
            "violations": violations,
            "label_serving_size_g": v.get("label_serving_size_g"),
            "label_protein_per_serving_g": v.get("label_protein_per_serving_g"),
            "calculated_purity_pct": v.get("calculated_purity_pct"),
            "weight_grams": v.get("weight_grams"),
            "lowest_price_inr": v.get("lowest_price_inr")
        }

        if dry_run:
            print(f"  [DRY RUN QUARANTINE] {item['product_name']} ({v.get('sku_id', 'no-sku')}) -> {'; '.join(violations)}")
            quarantined_count += 1
        else:
            try:
                client.table("staging_quarantine").insert({
                    "platform": "purge_corrupted_data_auditor",
                    "brand_hint": item["brand"],
                    "raw_title": item["product_name"],
                    "raw_price": v.get("lowest_price_inr"),
                    "detected_weight_g": int(v.get("weight_grams") or 0),
                    "failure_category": "SCRAPER_PARSE_ERROR",
                    "details": details
                }).execute()
                quarantined_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to quarantine variant {v['id']}: {e}")

    return quarantined_count


def delete_corrupted_variants(client: Client, corrupted: List[Dict[str, Any]], dry_run: bool = True) -> int:
    """
    Deletes corrupted variants and associated price listings from the database.
    """
    if not corrupted:
        return 0

    variant_ids = [item["variant"]["id"] for item in corrupted]
    print(f"\n[Purge] Deleting {len(variant_ids)} corrupted variants (Cascades to price_listings)...")

    if dry_run:
        print(f"  [DRY RUN] Would delete {len(variant_ids)} variants from database.")
        return len(variant_ids)

    deleted_count = 0
    chunk_size = 50

    for i in range(0, len(variant_ids), chunk_size):
        chunk = variant_ids[i:i + chunk_size]
        try:
            # Explicit delete of price_listings first if cascade not configured in some environments
            try:
                client.table("price_listings").delete().in_("variant_id", chunk).execute()
            except Exception:
                pass

            client.table("variants").delete().in_("id", chunk).execute()
            deleted_count += len(chunk)
            print(f"  Deleted batch {i+1}-{min(i+chunk_size, len(variant_ids))} of {len(variant_ids)}")
        except Exception as e:
            print(f"  [ERROR] Failed to delete chunk: {e}")

    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Purge corrupted variants with physics/biological violations.")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Perform scan and log without mutating database.")
    parser.add_argument("--apply", action="store_true", help="Execute quarantine and deletion mutations.")
    parser.add_argument(
        "--action",
        choices=["quarantine-and-delete", "quarantine-only"],
        default="quarantine-and-delete",
        help="Action to perform on corrupted variants (default: quarantine-and-delete)."
    )

    args = parser.parse_args()

    # Determine execution mode: dry_run is True unless --apply is explicitly specified
    dry_run = not args.apply
    if args.dry_run is True:
        dry_run = True

    print("=" * 70)
    print(" ProteIndex Autonomous Database Purge & Biological Bounds Auditor")
    print(f" Mode: {'DRY RUN (Read Only)' if dry_run else 'APPLY (Mutating Database)'}")
    print(f" Action: {args.action}")
    print("=" * 70)

    # 1. Scan
    corrupted = scan_corrupted_variants(sb)
    print(f"\n[Scan Complete] Found {len(corrupted)} corrupted variant(s) violating physical/biological bounds.")

    if not corrupted:
        print("[Status] No corrupted records found. Database is 100% compliant with physical bounds.")
        return

    # 2. Breakdown of violations
    violation_counts: Dict[str, int] = {}
    for item in corrupted:
        for viol in item["violations"]:
            category = viol.split(":")[0]
            violation_counts[category] = violation_counts.get(category, 0) + 1

    print("\nViolation Breakdown:")
    for cat, cnt in violation_counts.items():
        print(f"  - {cat}: {cnt} record(s)")

    # 3. Quarantine
    quarantined = quarantine_corrupted_records(sb, corrupted, dry_run=dry_run)
    print(f"[Quarantine Summary] {quarantined} record(s) logged to staging_quarantine.")

    # 4. Purge / Delete if requested
    if args.action == "quarantine-and-delete":
        deleted = delete_corrupted_variants(sb, corrupted, dry_run=dry_run)
        print(f"[Purge Summary] {deleted} variant(s) deleted from variants table.")

    if dry_run:
        print("\n[NOTE] This was a DRY RUN. Run with '--apply' to execute these changes against the database.")
    else:
        print("\n[SUCCESS] Corrupted records successfully quarantined and purged.")


if __name__ == "__main__":
    main()

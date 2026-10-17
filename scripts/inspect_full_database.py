"""
inspect_full_database.py - Comprehensive deep-dive database audit.
Analyzes every single row across products, variants, and price_listings.
"""

import os
import sys
import json
from collections import Counter, defaultdict
from dotenv import load_dotenv
from supabase import create_client, Client

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv('.env')
load_dotenv('scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY')

if not url or not key:
    print("Error: Supabase credentials not found.")
    sys.exit(1)

sb: Client = create_client(url, key)

def fetch_all(table_name, select_cols="*"):
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        res = sb.table(table_name).select(select_cols).range(offset, offset + page_size - 1).execute()
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows

print("=" * 80)
print("FETCHING ENTIRE DATABASE RECORDS...")
print("=" * 80)

products = fetch_all("products")
variants = fetch_all("variants")
price_listings = fetch_all("price_listings")

print(f"Loaded: {len(products)} products, {len(variants)} variants, {len(price_listings)} price listings.\n")

# ============================================================================
# 1. PRODUCTS AUDIT
# ============================================================================
print("=" * 80)
print("1. PRODUCTS AUDIT (Total: {})".format(len(products)))
print("=" * 80)

prod_by_id = {p["id"]: p for p in products}

silo_counts = Counter(p.get("category_silo") or "None" for p in products)
print("Category Silo Breakdown:")
for silo, cnt in silo_counts.most_common():
    print(f"  - {silo}: {cnt} ({cnt/len(products)*100:.1f}%)")

source_counts = Counter(p.get("protein_source") or "None" for p in products)
print("\nFormulation / Protein Source Breakdown (Top 10):")
for src, cnt in source_counts.most_common(10):
    print(f"  - {src}: {cnt}")

brands = [p.get("brand") for p in products if p.get("brand")]
brand_counts = Counter(brands)
print(f"\nUnique Brands: {len(brand_counts)}")
print("Top 15 Brands by Product Count:")
for b, cnt in brand_counts.most_common(15):
    print(f"  - {b}: {cnt}")

# Brand casing / alias check
lower_to_brands = defaultdict(set)
for b in brand_counts:
    lower_to_brands[b.strip().lower()].add(b)
casing_inconsistencies = {k: v for k, v in lower_to_brands.items() if len(v) > 1}
if casing_inconsistencies:
    print("\nBrand Casing Inconsistencies Detected:")
    for k, v in casing_inconsistencies.items():
        print(f"  - '{k}': variants exist as {list(v)}")
else:
    print("\nNo brand casing inconsistencies detected.")

# Trust score & fairy dusting
trust_scores = [float(p.get("trust_score") or 0) for p in products if p.get("trust_score") is not None]
fairy_dusted = [p for p in products if p.get("is_fairy_dusted")]
print(f"\nTrust Scores: Min={min(trust_scores) if trust_scores else 0}, Max={max(trust_scores) if trust_scores else 0}, Avg={sum(trust_scores)/len(trust_scores):.1f}" if trust_scores else "No trust scores")
print(f"Fairy Dusted Products: {len(fairy_dusted)} ({len(fairy_dusted)/len(products)*100:.1f}%)")

# Duplicate (brand, base_name)
name_groups = defaultdict(list)
for p in products:
    key_name = (p.get("brand", "").strip().lower(), p.get("base_name", "").strip().lower())
    name_groups[key_name].append(p)
duplicates = {k: v for k, v in name_groups.items() if len(v) > 1}
print(f"\nDuplicate (Brand, Base Name) Clusters: {len(duplicates)}")
for (b, bn), prods in list(duplicates.items())[:10]:
    print(f"  - '{b}' / '{bn}': {len(prods)} products (IDs: {[p['id'] for p in prods]})")

# Products without variants (orphans)
prod_ids_with_variants = set(v["product_id"] for v in variants if v.get("product_id"))
orphaned_products = [p for p in products if p["id"] not in prod_ids_with_variants]
print(f"\nOrphaned Products (Zero Variants): {len(orphaned_products)}")
for p in orphaned_products[:5]:
    print(f"  - [{p['id']}] {p.get('brand')} - {p.get('base_name')}")

# ============================================================================
# 2. VARIANTS AUDIT
# ============================================================================
print("\n" + "=" * 80)
print("2. VARIANTS AUDIT (Total: {})".format(len(variants)))
print("=" * 80)

var_by_id = {v["id"]: v for v in variants}

# Orphaned variants (pointing to non-existent product)
orphaned_variants = [v for v in variants if v.get("product_id") not in prod_by_id]
print(f"Orphaned Variants (Invalid product_id): {len(orphaned_variants)}")

# Weight distributions
weights = [float(v.get("weight_grams") or 0) for v in variants if v.get("weight_grams") is not None]
null_weights = [v for v in variants if v.get("weight_grams") is None or v.get("weight_grams") <= 0]
print(f"\nWeights Recorded: {len(weights)} (Null/Zero: {len(null_weights)})")
if weights:
    print(f"  Min Weight: {min(weights)}g, Max Weight: {max(weights)}g, Avg Weight: {sum(weights)/len(weights):.1f}g")
    unusual_low_weights = [v for v in variants if v.get("weight_grams") and v.get("weight_grams") < 100]
    unusual_high_weights = [v for v in variants if v.get("weight_grams") and v.get("weight_grams") > 6000]
    print(f"  Variants with Weight < 100g: {len(unusual_low_weights)}")
    for uv in unusual_low_weights[:5]:
        p = prod_by_id.get(uv.get("product_id"), {})
        print(f"    - {p.get('brand')} {p.get('base_name')} | Flavor: {uv.get('flavor')} | Weight: {uv.get('weight_grams')}g")
    print(f"  Variants with Weight > 6000g: {len(unusual_high_weights)}")
    for uv in unusual_high_weights[:5]:
        p = prod_by_id.get(uv.get("product_id"), {})
        print(f"    - {p.get('brand')} {p.get('base_name')} | Flavor: {uv.get('flavor')} | Weight: {uv.get('weight_grams')}g")

# Purity and Nutrition checks
purities = [float(v["calculated_purity_pct"]) for v in variants if v.get("calculated_purity_pct") is not None]
null_purities = [v for v in variants if v.get("calculated_purity_pct") is None]
print(f"\nPurity Distribution: Recorded={len(purities)}, Null={len(null_purities)}")
if purities:
    print(f"  Min Purity: {min(purities)}%, Max Purity: {max(purities)}%, Avg: {sum(purities)/len(purities):.1f}%")
    over_96_purity = [v for v in variants if v.get("calculated_purity_pct") and float(v.get("calculated_purity_pct")) > 96.0]
    zero_purity = [v for v in variants if v.get("calculated_purity_pct") is not None and float(v.get("calculated_purity_pct")) <= 0]
    print(f"  Purity > 96%: {len(over_96_purity)}")
    print(f"  Purity <= 0%: {len(zero_purity)}")

# Serving sizes and protein
serving_anomalies = []
for v in variants:
    s = v.get("label_serving_size_g")
    p = v.get("label_protein_per_serving_g")
    if s is not None and p is not None:
        try:
            if float(p) > float(s):
                serving_anomalies.append((v, f"Protein ({p}g) > Serving ({s}g)"))
        except Exception:
            pass
print(f"\nConservation of Mass Anomalies (Protein > Serving Size): {len(serving_anomalies)}")

# Prices on variants
prices = [float(v.get("lowest_price_inr") or 0) for v in variants if v.get("lowest_price_inr") is not None]
print(f"\nLowest Price Distribution: Min=₹{min(prices) if prices else 0}, Max=₹{max(prices) if prices else 0}, Avg=₹{sum(prices)/len(prices):.1f}" if prices else "No prices")
zero_prices = [v for v in variants if v.get("lowest_price_inr") is not None and float(v.get("lowest_price_inr")) <= 0]
print(f"  Zero or Negative Variant Prices: {len(zero_prices)}")

# OCR verification
ocr_verified = [v for v in variants if v.get("ocr_verified")]
print(f"\nOCR Verified Variants: {len(ocr_verified)} ({len(ocr_verified)/len(variants)*100:.1f}%)")

# Duplicate variants on (product_id, flavor, weight_grams)
var_group = defaultdict(list)
for v in variants:
    key = (v.get("product_id"), (v.get("flavor") or "").strip().lower(), v.get("weight_grams"))
    var_group[key].append(v)
dup_variants = {k: v for k, v in var_group.items() if len(v) > 1}
print(f"\nDuplicate Variant Combinations (product_id, flavor, weight): {len(dup_variants)}")
for k, vs in list(dup_variants.items())[:5]:
    p = prod_by_id.get(k[0], {})
    print(f"  - {p.get('brand')} {p.get('base_name')} | Flavor: '{k[1]}' | {k[2]}g -> {len(vs)} records (IDs: {[x['id'] for x in vs]})")

# Variants without price listings
var_ids_with_listings = set(pl["variant_id"] for pl in price_listings if pl.get("variant_id"))
variants_without_listings = [v for v in variants if v["id"] not in var_ids_with_listings]
print(f"\nVariants without Price Listings: {len(variants_without_listings)} ({len(variants_without_listings)/len(variants)*100:.1f}%)")

# ============================================================================
# 3. PRICE LISTINGS AUDIT
# ============================================================================
print("\n" + "=" * 80)
print("3. PRICE LISTINGS AUDIT (Total: {})".format(len(price_listings)))
print("=" * 80)

# Orphaned price listings
orphaned_listings = [pl for pl in price_listings if pl.get("variant_id") not in var_by_id]
print(f"Orphaned Price Listings (Invalid variant_id): {len(orphaned_listings)}")

# Platform breakdown
platform_counts = Counter(pl.get("platform_name") or pl.get("source") or "Unknown" for pl in price_listings)
print("\nPlatform Breakdown:")
for plat, cnt in platform_counts.most_common():
    print(f"  - {plat}: {cnt} ({cnt/len(price_listings)*100:.1f}%)")

# Stock status
in_stock = [pl for pl in price_listings if pl.get("is_in_stock") is True or pl.get("in_stock") is True]
print(f"\nStock Status: In Stock = {len(in_stock)} ({len(in_stock)/len(price_listings)*100:.1f}%), Out of Stock = {len(price_listings) - len(in_stock)}")

# Price ranges
pl_prices = [float(pl.get("current_price_inr") or pl.get("price_inr") or 0) for pl in price_listings if (pl.get("current_price_inr") or pl.get("price_inr")) is not None]
if pl_prices:
    print(f"\nListing Prices: Min=₹{min(pl_prices)}, Max=₹{max(pl_prices)}, Avg=₹{sum(pl_prices)/len(pl_prices):.1f}")
    suspicious_cheap = [pl for pl in price_listings if 0 < float(pl.get("current_price_inr") or pl.get("price_inr") or 0) < 200]
    suspicious_expensive = [pl for pl in price_listings if float(pl.get("current_price_inr") or pl.get("price_inr") or 0) > 30000]
    zero_price_listings = [pl for pl in price_listings if float(pl.get("current_price_inr") or pl.get("price_inr") or 0) <= 0]
    print(f"  Suspiciously Cheap (< ₹200): {len(suspicious_cheap)}")
    for spl in suspicious_cheap[:5]:
        v = var_by_id.get(spl.get("variant_id"), {})
        p = prod_by_id.get(v.get("product_id"), {})
        print(f"    - ₹{spl.get('current_price_inr')} | {p.get('brand')} {p.get('base_name')} | {v.get('weight_grams')}g | URL: {spl.get('listing_url')[:60]}")
    print(f"  Suspiciously Expensive (> ₹30,000): {len(suspicious_expensive)}")
    print(f"  Zero Price Listings: {len(zero_price_listings)}")

# Authorized sellers
auth_sellers = [pl for pl in price_listings if pl.get("is_authorized_seller")]
print(f"\nAuthorized Sellers: {len(auth_sellers)} ({len(auth_sellers)/len(price_listings)*100:.1f}%)")

print("\n" + "=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)

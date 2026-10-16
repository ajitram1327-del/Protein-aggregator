import os
import sys
from collections import defaultdict
from dotenv import load_dotenv

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add src to path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pipeline.dedupe_engine import EntityResolutionEngine

load_dotenv(os.path.join(CURRENT_DIR, "..", ".env"))
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Supabase credentials not configured in environment. Running in offline dry-run mode.")
    sys.exit(0)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Fetching products for entity resolution...")
res = supabase.table("products").select("id, brand, base_name, category_silo").execute()
products = res.data or []
print(f"Loaded {len(products)} products.")

# Step 1: Detect and quarantine bundle combos
clean_products = []
for p in products:
    is_bundle, reason = EntityResolutionEngine.is_combo_bundle(p.get("base_name"))
    if is_bundle:
        print(f"Quarantining combo bundle: '{p.get('base_name')}' (Brand: {p.get('brand')})")
        try:
            supabase.table("staging_quarantine").insert({
                "platform": "internal_catalog",
                "brand_hint": p.get("brand"),
                "raw_title": p.get("base_name"),
                "failure_category": "COMBO_BUNDLE",
                "details": {"product_id": p.get("id"), "silo": p.get("category_silo")}
            }).execute()
        except Exception as e:
            print(f"  Note: quarantine staging logged ({e})")
    else:
        clean_products.append(p)

print(f"{len(clean_products)} clean products retained for resolution.")

# Step 2: Compare pairs and resolve
merged_count = 0
staged_count = 0

# Group by brand first to keep comparisons fast and high-precision
by_brand = defaultdict(list)
for p in clean_products:
    b = (p.get("brand") or "unknown").lower().strip()
    by_brand[b].append(p)

for brand, brand_prods in by_brand.items():
    if len(brand_prods) <= 1:
        continue

    for i in range(len(brand_prods)):
        prod_a = brand_prods[i]
        for j in range(i + 1, len(brand_prods)):
            prod_b = brand_prods[j]

            # Cross-category merge blocker
            if (prod_a.get("category_silo") or "protein") != (prod_b.get("category_silo") or "protein"):
                continue

            resolution = EntityResolutionEngine.resolve_candidate(prod_b, prod_a)
            score = resolution["confidence_score"]

            if resolution["decision"] == "AUTO_MERGE":
                print(f"[AUTO-MERGE score={score:.2f}] '{prod_b['base_name']}' -> '{prod_a['base_name']}'")
                try:
                    # Reassign variants
                    supabase.table("variants").update({"product_id": prod_a["id"]}).eq("product_id", prod_b["id"]).execute()
                    # Delete merged duplicate
                    supabase.table("products").delete().eq("id", prod_b["id"]).execute()
                    merged_count += 1
                except Exception as e:
                    print(f"  Error executing merge: {e}")

            elif resolution["decision"] == "STAGING_REVIEW":
                print(f"[STAGING-REVIEW score={score:.2f}] '{prod_b['base_name']}' vs '{prod_a['base_name']}'")
                try:
                    supabase.table("entity_resolution_staging").insert({
                        "raw_title": prod_b.get("base_name"),
                        "raw_brand": prod_b.get("brand"),
                        "raw_silo": prod_b.get("category_silo"),
                        "candidate_canonical_sku_id": None,
                        "confidence_score": score,
                        "resolution_status": "PENDING_REVIEW",
                        "resolution_notes": f"Potential match with product {prod_a['id']} ('{prod_a['base_name']}')"
                    }).execute()
                    staged_count += 1
                except Exception as e:
                    print(f"  Note: review stage logged ({e})")

print(f"\nEntity resolution complete: {merged_count} auto-merged, {staged_count} queued for staging review.")

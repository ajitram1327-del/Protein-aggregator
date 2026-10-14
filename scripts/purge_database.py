import os
import sys
import time
from dotenv import load_dotenv
from supabase import create_client

# Load environment configuration
load_dotenv(dotenv_path="scraper/.env")
load_dotenv()

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("[ERROR] SUPABASE_URL or SUPABASE_KEY not found in environment.")
    sys.exit(1)

supabase = create_client(supabase_url, supabase_key)

def delete_table_in_batches(table_name: str, id_col: str = "id", batch_size: int = 500):
    print(f"\n[WIPE] Purging table '{table_name}'...")
    total_deleted = 0
    while True:
        try:
            # Fetch a batch of IDs
            res = supabase.table(table_name).select(id_col).limit(batch_size).execute()
            rows = res.data or []
            if not rows:
                break
            
            ids = [r[id_col] for r in rows if id_col in r]
            if not ids:
                break

            # Delete the batch using .in_()
            del_res = supabase.table(table_name).delete().in_(id_col, ids).execute()
            count = len(ids)
            total_deleted += count
            print(f"  -> Deleted {count} records from {table_name} (Cumulative: {total_deleted})")
            time.sleep(0.1)
        except Exception as e:
            print(f"  [ERROR] Error deleting batch from {table_name}: {e}")
            break
            
    print(f"[DONE] Purged {total_deleted} total records from '{table_name}'.")

def reset_entire_catalogue():
    print("=" * 60)
    print("ERASING MASTER CATALOGUE & COLLECTED DATA POINTS (CLEAN SLATE)")
    print("=" * 60)
    
    # Order of deletion to respect foreign keys:
    # 1. price_listings (FK -> variants)
    # 2. offers (FK -> variants)
    # 3. unmatched_products (isolated)
    # 4. comparison_snapshots (isolated)
    # 5. variants (FK -> products)
    # 6. products (parent)
    
    delete_table_in_batches("price_listings", "id")
    delete_table_in_batches("offers", "id")
    delete_table_in_batches("unmatched_products", "id")
    delete_table_in_batches("variants", "id")
    delete_table_in_batches("products", "id")

    # Optional tables if any
    try:
        delete_table_in_batches("comparison_snapshots", "id")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("VERIFYING CLEAN SLATE STATUS:")
    print("=" * 60)
    for tbl in ["price_listings", "offers", "variants", "products", "unmatched_products"]:
        try:
            c = supabase.table(tbl).select("*", count="exact", head=True).execute().count
            print(f"  {tbl}: {c} records remaining")
        except Exception as e:
            print(f"  {tbl}: check failed ({e})")

if __name__ == "__main__":
    reset_entire_catalogue()

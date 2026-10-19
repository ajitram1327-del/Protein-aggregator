"""
sync_price_history.py
High-speed bulk synchronization and linkage of all current active price listings
to the 'offers' and 'price_history' tables in Supabase, establishing a complete
price tracking baseline for all catalog products and variants.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

for p in ['.env', '.env.local', 'client/.env.local', 'scraper/scrapling_scraper/.env']:
    if os.path.exists(p):
        load_dotenv(p)

url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
if not url or not key:
    print("Error: Supabase URL/Key missing.")
    sys.exit(1)

sb = create_client(url, key)

def sync_price_history_baseline():
    print("Fetching all price listings from Supabase...", flush=True)
    all_listings = []
    page_size = 1000
    offset = 0

    while True:
        res = sb.table("price_listings").select(
            "id, variant_id, product_id, platform_name, source, listing_url, source_url, current_price_inr, price_inr, is_in_stock, in_stock, scraped_at"
        ).range(offset, offset + page_size - 1).execute()

        data = res.data or []
        all_listings.extend(data)
        if len(data) < page_size:
            break
        offset += page_size

    print(f"Total price listings loaded: {len(all_listings)}", flush=True)

    # Deduplicate listings by (variant_id, platform) to ensure clean upserts
    unique_offers = {}
    for l in all_listings:
        vid = l.get("variant_id")
        if not vid:
            continue
        platform = (l.get("platform_name") or l.get("source") or "direct").lower()
        url_val = l.get("listing_url") or l.get("source_url") or "#"
        price_val = float(l.get("current_price_inr") or l.get("price_inr") or 0.0)
        if price_val <= 0:
            continue

        clean_price = round(price_val, 2)
        in_stock = bool(l.get("is_in_stock") if l.get("is_in_stock") is not None else l.get("in_stock", True))

        key_pair = (str(vid), platform)
        unique_offers[key_pair] = {
            "variant_id": str(vid),
            "platform": platform,
            "url": url_val,
            "current_price_inr": clean_price,
            "stock_status": "in_stock" if in_stock else "out_of_stock",
            "last_scraped_at": l.get("scraped_at") or "now()"
        }

    offer_records = list(unique_offers.values())
    print(f"Unique offers to synchronize: {len(offer_records)}", flush=True)

    # Batch upsert offers in chunks of 100
    batch_size = 100
    linked_offer_ids = []

    for i in range(0, len(offer_records), batch_size):
        chunk = offer_records[i:i + batch_size]
        try:
            res = sb.table("offers").upsert(chunk, on_conflict="variant_id,platform").execute()
            if res.data:
                for row in res.data:
                    linked_offer_ids.append((row["id"], row["current_price_inr"]))
        except Exception as e:
            print(f"Batch offer error at {i}: {e}", flush=True)
            # Fallback to individual inserts for this chunk
            for item in chunk:
                try:
                    single_res = sb.table("offers").upsert(item, on_conflict="variant_id,platform").execute()
                    if single_res.data:
                        linked_offer_ids.append((single_res.data[0]["id"], single_res.data[0]["current_price_inr"]))
                except Exception:
                    pass

        print(f"Synchronized offers: {min(i + batch_size, len(offer_records))}/{len(offer_records)}", flush=True)

    print(f"Total offers active in database: {len(linked_offer_ids)}", flush=True)

    # Query existing price_history records to avoid duplicates
    print("Checking existing price history records...", flush=True)
    existing_hist_res = sb.table("price_history").select("offer_id, price_inr").execute()
    existing_set = set()
    for h in (existing_hist_res.data or []):
        existing_set.add(h["offer_id"])

    # Prepare price history entries for offers without records
    new_history_entries = []
    for off_id, price_val in linked_offer_ids:
        if off_id not in existing_set:
            new_history_entries.append({
                "offer_id": off_id,
                "price_inr": round(float(price_val), 2)
            })

    print(f"New price history entries to create: {len(new_history_entries)}", flush=True)

    # Batch insert price_history in chunks of 200
    created_history = 0
    for i in range(0, len(new_history_entries), 200):
        chunk = new_history_entries[i:i + 200]
        try:
            hist_res = sb.table("price_history").insert(chunk).execute()
            if hist_res.data:
                created_history += len(hist_res.data)
        except Exception as e:
            print(f"Batch history insert error at {i}: {e}", flush=True)

    print("\n=======================================================", flush=True)
    print("Price Tracking Baseline Complete!", flush=True)
    print(f"Offers Synced & Linked: {len(linked_offer_ids)}", flush=True)
    print(f"Price History Records Created: {created_history}", flush=True)
    print("=======================================================", flush=True)

if __name__ == "__main__":
    sync_price_history_baseline()

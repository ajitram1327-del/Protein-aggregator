import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_database():
    print("Fetching all variants...")
    res = supabase.table("variants").select("id, flavor, weight_grams").execute()
    variants = res.data
    
    deleted_count = 0
    
    BANNED_KEYWORDS = ["pack of", "combo", "+", "free", "shaker", "t-shirt", "tshirt", "bottle"]
    
    for v in variants:
        flavor = (v.get("flavor") or "").lower()
        weight = v.get("weight_grams")
        
        should_delete = False
        reason = ""
        
        # Check for bundle/banned keywords in flavor
        for banned in BANNED_KEYWORDS:
            if banned in flavor:
                should_delete = True
                reason = f"Contains banned keyword: {banned}"
                break
                
        # Check for unrealistic weights (e.g., 25g protein misread as 25g tub weight)
        if weight is not None and weight < 100:
            should_delete = True
            reason = f"Unrealistic tub weight: {weight}g (Likely a regex misread of '25g protein')"
            
        if should_delete:
            print(f"Deleting variant {v['id']} | Flavor: {flavor} | Weight: {weight}g -> Reason: {reason}")
            # Delete from offers first due to foreign key constraints, then variants
            supabase.table("offers").delete().eq("variant_id", v["id"]).execute()
            supabase.table("variants").delete().eq("id", v["id"]).execute()
            deleted_count += 1
            
    print(f"\nCleanup complete. Deleted {deleted_count} garbage variants.")

if __name__ == "__main__":
    clean_database()

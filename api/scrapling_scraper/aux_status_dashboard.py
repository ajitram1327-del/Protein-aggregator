import os
import re
import math
from dotenv import load_dotenv
from supabase import create_client

def generate_dashboard():
    # Load environment to query Supabase
    load_dotenv("../.env")
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    # Path to log file
    log_path = "scraper_production.log"
    total_brands = 16
    current_brand = 0
    current_brand_name = "Initializing..."

    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                m = re.search(r"\[(\d+)/\d+\] Commencing extraction for: (.*)", line)
                if m:
                    current_brand = int(m.group(1))
                    current_brand_name = m.group(2).strip()

    # Query DB for metrics
    try:
        prod_res = supabase.table("products").select("id", count="exact").execute()
        total_products = prod_res.count if prod_res.count else 0
        
        list_res = supabase.table("price_listings").select("id", count="exact").execute()
        total_listings = list_res.count if list_res.count else 0
    except Exception:
        total_products = 0
        total_listings = 0

    # Calculate Progress Bar (Length 40)
    percent = (current_brand / total_brands) * 100 if total_brands > 0 else 0
    filled = int((percent / 100) * 40)
    bar = "█" * filled + "░" * (40 - filled)

    # Generate Markdown
    artifact_path = r"C:\Users\ajith\.gemini\antigravity\brain\584882f0-3237-4b78-af13-adbc9b6147be\Scraping_Dashboard.md"
    
    md = f"""# 🚀 Omni-Channel Scraper Live Dashboard

> [!NOTE]
> The engine is actively scraping and bypassing anti-bot measures across 14 platforms to aggregate the supplement market.

### 📊 Live Progress

**Current Target:** `{current_brand_name}` ({current_brand} / {total_brands} Brands)

`[{bar}] {percent:.1f}%`

---

### 💾 Database Metrics (Supabase)

| Metric | Count |
| :--- | :--- |
| **Unique Products Mastered** | `{total_products}` |
| **Live Cross-Platform Prices** | `{total_listings}` |

*Dashboard auto-refreshes every 2 minutes while the engine runs.*
"""
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    generate_dashboard()

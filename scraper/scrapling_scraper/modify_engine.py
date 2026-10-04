import re

with open('src/scraper/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
imports = """from src.analytics.ingredient_auditor import IngredientAuditor
from src.vision.review_authenticity import ReviewAuthenticityEngine
from src.pipeline.seller_matrix import SellerMatrix
"""
if "IngredientAuditor" not in content:
    content = content.replace("from supabase import create_client", "from supabase import create_client\n" + imports)

# 2. Modify upsert_product_variant signature
old_sig = "def upsert_product_variant(brand: str, title: str, price: float, img: str, url: str, source: str, description: str = \"\"):"
new_sig = "def upsert_product_variant(brand: str, title: str, price: float, img: str, url: str, source: str, description: str = \"\", seller_name: str = \"\"):"
content = content.replace(old_sig, new_sig)

# 3. Add Trust Engine logic before product upsert
trust_logic = """
    # --- TRUST ENGINE MODULES ---
    # 1. Fairy-Dusting Check
    ingredient_audit = IngredientAuditor.audit(description)
    base_trust_score = 100 - ingredient_audit['trust_deduction']
    
    # 2. Review Authenticity (Mocked fetching for now)
    review_audit = ReviewAuthenticityEngine.audit_reviews(base_name)
    
    # 3. Seller Matrix
    is_authorized = SellerMatrix.verify_seller(seller_name, brand)
    # ----------------------------
"""
replace_point = """    psource = "Whey"
    if re.search(r"plant|pea|vegan|soy|brown rice", combined_text): psource = "Plant"
    elif re.search(r"yeast", combined_text): psource = "Yeast"
    elif "casein" in combined_text: psource = "Casein"

    try:"""
new_replace_point = replace_point.replace("    try:", trust_logic + "\n    try:")
content = content.replace(replace_point, new_replace_point)

# 4. Modify Products upsert
old_p_upsert = """        res = supabase.table("products").upsert({
            "brand": brand, "base_name": base_name, "category_silo": silo,
            "protein_source": psource, "image_url": img
        }, on_conflict="brand,base_name").execute()"""
new_p_upsert = """        res = supabase.table("products").upsert({
            "brand": brand, "base_name": base_name, "category_silo": silo,
            "protein_source": psource, "image_url": img,
            "is_fairy_dusted": ingredient_audit['is_fairy_dusted'],
            "fairy_dusting_flags": ingredient_audit['flags'],
            "trust_score": base_trust_score
        }, on_conflict="brand,base_name").execute()"""
content = content.replace(old_p_upsert, new_p_upsert)

# 5. Modify Variants upsert
old_v_upsert = """        vres = supabase.table("variants").upsert({
            "product_id": product_id, "sku_id": sku_id, "flavor": "Varies",
            "weight_grams": weight, "lowest_price_inr": price,
            "servings_count": total_servings,
            "best_value_metric": analytics_metrics["effective_cost_per_bioavailable_g_inr"],
            "raw_json_data": raw_json
        }, on_conflict="sku_id").execute()"""
new_v_upsert = """        vres = supabase.table("variants").upsert({
            "product_id": product_id, "sku_id": sku_id, "flavor": "Varies",
            "weight_grams": weight, "lowest_price_inr": price,
            "servings_count": total_servings,
            "best_value_metric": analytics_metrics["effective_cost_per_bioavailable_g_inr"],
            "raw_json_data": raw_json,
            "authenticity_score": review_audit['authenticity_score'],
            "has_bot_reviews": review_audit['has_bot_reviews']
        }, on_conflict="sku_id").execute()"""
content = content.replace(old_v_upsert, new_v_upsert)

# 6. Modify Price Listings upsert
old_l_upsert = """        supabase.table("price_listings").upsert({
            "variant_id": variant_id, "source": source, "source_url": url,
            "price_inr": price, "in_stock": True
        }, on_conflict="variant_id,source").execute()"""
new_l_upsert = """        supabase.table("price_listings").upsert({
            "variant_id": variant_id, "source": source, "source_url": url,
            "price_inr": price, "in_stock": True,
            "seller_name": seller_name,
            "is_authorized_seller": is_authorized
        }, on_conflict="variant_id,source").execute()"""
content = content.replace(old_l_upsert, new_l_upsert)

# 7. Add extract_seller to engine
extract_seller = """
def extract_seller(parent) -> str:
    # Attempt to extract seller name from common selectors
    if not parent: return ""
    seller_els = parent.css(".seller-name, [class*='seller'], [class*='soldBy'], #sellerProfileTriggerId")
    if seller_els:
        text = seller_els[0].get_all_text() if hasattr(seller_els[0], 'get_all_text') else getattr(seller_els[0], 'text', '')
        return text.replace("Sold by", "").replace("sold by", "").strip()
    return ""
"""
if "def extract_seller" not in content:
    content = content.replace("def upsert_product_variant", extract_seller + "\ndef upsert_product_variant")

# 8. Modify the call to upsert_product_variant in scrape_url
old_upsert_call = """            if price > 0:
                if upsert_product_variant(brand, title, price, img, link, source, card_desc):"""
new_upsert_call = """            if price > 0:
                seller = extract_seller(parent)
                if upsert_product_variant(brand, title, price, img, link, source, card_desc, seller):"""
content = content.replace(old_upsert_call, new_upsert_call)

with open('src/scraper/engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

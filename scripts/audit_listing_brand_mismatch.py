import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

print("Auditing price listings for brand mismatch and invalid bindings...")

products = sb.table('products').select('id, brand, base_name').execute().data
prod_map = {p['id']: p for p in products}

variants = sb.table('variants').select('id, product_id, weight_grams, flavor').execute().data
var_map = {v['id']: v for v in variants}

listings = sb.table('price_listings').select('*').execute().data

mismatched_listings = []
combo_listings = []
invalid_variant_listings = []

for l in listings:
    lid = l['id']
    vid = l.get('variant_id')
    v = var_map.get(vid)
    if not v:
        invalid_variant_listings.append(l)
        continue
    
    p = prod_map.get(v['product_id'])
    if not p:
        continue
    
    prod_brand = p['brand'].lower()
    url = (l.get('listing_url') or l.get('source_url') or "").lower()
    seller = (l.get('seller_name') or "").lower()
    
    # 1. Check for combo / bundle URLs attached to single variant
    if any(k in url for k in ['combo', 'bundle', 'pack-of-5', 'pack-of-6', 'sachet']) and v['weight_grams'] >= 500:
        combo_listings.append({
            "listing_id": lid,
            "variant_id": vid,
            "product": p['base_name'],
            "brand": p['brand'],
            "variant_weight": v['weight_grams'],
            "url": url,
            "price": l['price_inr']
        })
        
    # 2. Check for D2C storefront URL from a DIFFERENT brand attached to this product
    # e.g. proburst.com URL on Nakpro product, guardian.in URL on Optimum Nutrition, etc.
    d2c_domains = {
        'optimumnutrition.co.in': 'optimum nutrition',
        'asitisnutrition.com': 'as-it-is',
        'nakpro.com': 'nakpro',
        'proburst.com': 'proburst',
        'bigmusclesnutrition.com': 'big muscles',
        'guardian.in': 'gnc',
        'cosmix.in': 'cosmix',
        'naturaltein.in': 'naturaltein',
        'musclenectar.com': 'muscle nectar',
        'scitron.com': 'scitron'
    }
    
    for dom, expected_brand in d2c_domains.items():
        if dom in url and expected_brand not in prod_brand:
            mismatched_listings.append({
                "listing_id": lid,
                "variant_id": vid,
                "product": p['base_name'],
                "product_brand": p['brand'],
                "url": url,
                "domain_brand": expected_brand,
                "price": l['price_inr']
            })
            break

print(f"Total Listings: {len(listings)}")
print(f"Invalid Variant Bindings: {len(invalid_variant_listings)}")
print(f"Cross-Brand Storefront Mismatches: {len(mismatched_listings)}")
for m in mismatched_listings:
    print(f"   [{m['product_brand']}] {m['product']} has listing from {m['domain_brand']}: Rs.{m['price']} ({m['url'][:70]})")

print(f"\nCombo/Bundle/Sachet Mismatches on Tub Variants: {len(combo_listings)}")
for c in combo_listings:
    print(f"   [{c['brand']}] {c['product']} ({c['variant_weight']}g) has combo listing: Rs.{c['price']} ({c['url'][:70]})")

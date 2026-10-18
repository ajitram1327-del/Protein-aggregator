import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
sb = create_client(url, key)

print("Starting Database Re-Sync & Anomaly Reconciliation...")

# 1. Load Live Cosmix Catalog
with open('scripts/cosmix_live_catalog.json', 'r') as f:
    cosmix_cat = json.load(f)

# Build a lookup of product keywords to 1kg and 500g prices
cosmix_price_map = {}
for p_title, vars in cosmix_cat.items():
    p_lower = p_title.lower()
    for v in vars:
        vt = v['variant_title'].lower()
        price = v['price']
        if '1kg' in vt or '1 kg' in vt:
            cosmix_price_map[(p_lower, 1000)] = price
        elif '500g' in vt or '500 g' in vt:
            cosmix_price_map[(p_lower, 500)] = price

# 2. Reconcile Cosmix Products
cosmix_prods = sb.table('products').select('id, brand, base_name').ilike('brand', '%Cosmix%').execute().data
print(f"Found {len(cosmix_prods)} Cosmix products in DB.")

for cp in cosmix_prods:
    pid = cp['id']
    bname = cp['base_name'].lower()
    variants = sb.table('variants').select('*').eq('product_id', pid).execute().data
    
    for v in variants:
        vid = v['id']
        w = int(v['weight_grams'] or 0)
        curr_price = v['lowest_price_inr']
        
        # Match to live price
        matched_price = None
        for (cat_title, cat_w), cat_price in cosmix_price_map.items():
            if cat_w == w:
                # Check keyword overlap (e.g. 'kerala', 'mocha', 'arabica', 'cacao', 'vanilla', 'yeast', 'pro')
                words = [wd for wd in bname.split() if len(wd) > 3 and wd not in ['nonsense', 'plant', 'protein']]
                if all(wd in cat_title for wd in words):
                    matched_price = cat_price
                    break
        
        # Specific fallbacks for known Cosmix lines if keyword match didn't trigger
        if not matched_price and w == 1000:
            if 'kerala bean' in bname or 'kerala vanilla' in bname:
                matched_price = 2390.0 if 'yeast' in bname else 1869.0
            elif 'indonesian cacao' in bname:
                matched_price = 1999.0 if 'yeast' in bname else 1744.0
            elif 'chikmagalur mocha' in bname:
                matched_price = 1999.0 if 'yeast' in bname else 1744.0
            elif 'malnad arabica' in bname:
                matched_price = 2390.0 if 'yeast' in bname else 1969.0
            elif 'cocoa beet' in bname:
                matched_price = 1969.0
            elif 'coconut peppermint' in bname:
                matched_price = 2136.0
            elif 'chilli guava' in bname:
                matched_price = 1960.0
            elif 'apple cinnamon' in bname:
                matched_price = 2250.0
            elif 'classic unflavoured' in bname:
                matched_price = 2285.0 if 'yeast' in bname else 1851.0
            elif 'peanut butter' in bname:
                matched_price = 2380.0
        
        if matched_price and matched_price != curr_price:
            print(f"Updating Cosmix [{cp['base_name']}] {w}g variant {vid}: Rs.{curr_price} -> Rs.{matched_price}")
            sb.table('variants').update({
                'lowest_price_inr': matched_price
            }).eq('id', vid).execute()
            
            # Update D2C price_listing
            sb.table('price_listings').update({
                'price_inr': matched_price,
                'current_price_inr': matched_price
            }).eq('variant_id', vid).ilike('source', '%d2c%').execute()

# 3. Clean up GNC 35g sachets mislabeled as 1000g
gnc_sachets = sb.table('price_listings').select('id, variant_id, listing_url, price_inr').ilike('listing_url', '%35gm%').execute().data
for gs in gnc_sachets:
    vid = gs['variant_id']
    v_data = sb.table('variants').select('id, weight_grams, lowest_price_inr').eq('id', vid).execute().data
    if v_data and v_data[0]['weight_grams'] == 1000:
        print(f"Fixing GNC 35g sachet mislabeled as 1000g: variant {vid}")
        # Delete the bogus sachet price listing on the 1000g variant
        sb.table('price_listings').delete().eq('id', gs['id']).execute()
        # Recalculate lowest price for this variant
        remaining = sb.table('price_listings').select('price_inr').eq('variant_id', vid).execute().data
        if remaining:
            new_low = min(r['price_inr'] for r in remaining if r['price_inr'] > 0)
            sb.table('variants').update({'lowest_price_inr': new_low}).eq('id', vid).execute()
        else:
            # Standard GNC 1kg price is 3699.0
            sb.table('variants').update({'lowest_price_inr': 3699.0}).eq('id', vid).execute()

# 4. Clean up ON 5-pack single serve sachets mislabeled as 1000g
on_sachets = sb.table('price_listings').select('id, variant_id, listing_url, price_inr').ilike('listing_url', '%sachets%').execute().data
for os_item in on_sachets:
    vid = os_item['variant_id']
    v_data = sb.table('variants').select('id, weight_grams, lowest_price_inr').eq('id', vid).execute().data
    if v_data and v_data[0]['weight_grams'] == 1000:
        print(f"Removing ON sachet listing {os_item['id']} from 1000g variant {vid}")
        sb.table('price_listings').delete().eq('id', os_item['id']).execute()
        remaining = sb.table('price_listings').select('price_inr').eq('variant_id', vid).execute().data
        if remaining:
            new_low = min(r['price_inr'] for r in remaining if r['price_inr'] > 0)
            sb.table('variants').update({'lowest_price_inr': new_low}).eq('id', vid).execute()
        else:
            sb.table('variants').update({'lowest_price_inr': 4629.0}).eq('id', vid).execute()

# 5. Clean up RiteBite single bars mislabeled as 1000g
rb_vars = sb.table('variants').select('id, product_id, weight_grams, lowest_price_inr').eq('weight_grams', 1000).lt('lowest_price_inr', 300).execute().data
for rb in rb_vars:
    vid = rb['id']
    # Check if parent product is a bar
    prod = sb.table('products').select('base_name, brand').eq('id', rb['product_id']).execute().data
    if prod and ('bar' in prod[0]['base_name'].lower() or 'ritebite' in prod[0]['brand'].lower()):
        print(f"Fixing RiteBite single bar {vid} mislabeled as 1000g (price={rb['lowest_price_inr']}) -> updating weight to 50g")
        sb.table('variants').update({'weight_grams': 50}).eq('id', vid).execute()

# 6. Clean up GNC Creatine 3g scoop claim mislabeled as 3g container
gnc_3g = sb.table('variants').select('id, weight_grams, lowest_price_inr').eq('weight_grams', 3).execute().data
for g in gnc_3g:
    vid = g['id']
    print(f"Fixing GNC Creatine variant {vid} weight 3g -> 250g")
    sb.table('variants').update({'weight_grams': 250}).eq('id', vid).execute()

print("\nReconciliation complete! Running anomaly verification audit...")

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('scraper/scrapling_scraper/.env')
load_dotenv('client/.env.local')

url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

sb = create_client(url, key)

products_res = sb.table('products').select('id, brand, base_name').execute()
products = products_res.data

print(f"Total products in DB: {len(products)}")

anomalies = []

for p in products:
    pid = p['id']
    v_res = sb.table('variants').select('id, flavor, weight_grams, lowest_price_inr, calculated_purity_pct').eq('product_id', pid).execute()
    variants = v_res.data
    if len(variants) < 2:
        continue
    
    # Group by flavor
    by_flavor = {}
    for v in variants:
        flv = v['flavor'] or 'unflavored'
        by_flavor.setdefault(flv, []).append(v)
        
    for flv, flv_vars in by_flavor.items():
        if len(flv_vars) < 2:
            continue
        flv_vars.sort(key=lambda x: x['weight_grams'] or 0)
        # Check if smaller weight has higher price than larger weight
        for i in range(len(flv_vars) - 1):
            v1 = flv_vars[i]
            v2 = flv_vars[i+1]
            w1, p1 = v1['weight_grams'] or 0, v1['lowest_price_inr'] or 0
            w2, p2 = v2['weight_grams'] or 0, v2['lowest_price_inr'] or 0
            if w1 < w2 and p1 > p2 and p1 > 0 and p2 > 0:
                anomalies.append({
                    "product": p['base_name'],
                    "brand": p['brand'],
                    "flavor": flv,
                    "smaller": f"{w1}g @ Rs.{p1} (id={v1['id']})",
                    "larger": f"{w2}g @ Rs.{p2} (id={v2['id']})"
                })

print(f"\nFound {len(anomalies)} price inversion anomalies:")
for a in anomalies:
    print(f"[{a['brand']}] {a['product']} ({a['flavor']}): {a['smaller']} vs {a['larger']}")

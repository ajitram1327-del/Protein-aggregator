import urllib.request
import json

page = 1
all_products = []
while True:
    url = f"https://cosmix.in/products.json?limit=250&page={page}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            prods = data.get('products', [])
            if not prods:
                break
            all_products.extend(prods)
            page += 1
    except Exception as e:
        print("Fetch error:", e)
        break

print(f"Total Cosmix products fetched: {len(all_products)}")
cosmix_catalog = {}
for p in all_products:
    title = p['title']
    for v in p['variants']:
        v_title = v['title']
        price = float(v['price'])
        cosmix_catalog.setdefault(title, []).append({
            "variant_title": v_title,
            "price": price,
            "id": v['id']
        })

with open('scripts/cosmix_live_catalog.json', 'w') as f:
    json.dump(cosmix_catalog, f, indent=2)

print("Saved cosmix_live_catalog.json")

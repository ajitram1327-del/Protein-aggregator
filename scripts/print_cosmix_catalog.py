import json

with open('scripts/cosmix_live_catalog.json') as f:
    cat = json.load(f)

for title, vars in cat.items():
    if any(k in title.lower() for k in ['plant', 'yeast', 'protein']):
        print(f"=== {title} ===")
        for v in vars:
            print(f"   {v['variant_title']} -> {v['price']}")

import urllib.request
import json

req = urllib.request.Request('https://cosmix.in/products.json?limit=50', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for p in data.get('products', []):
            title = p['title']
            if any(k in title.lower() for k in ['protein', 'plant', 'pancake', 'yeast']):
                print(f"Product: {title} (handle: {p.get('handle')})")
                for v in p['variants']:
                    print(f"    var: '{v['title']}' | price: {v['price']} | grams: {v.get('grams')}")
except Exception as e:
    print('Error:', e)

import subprocess
import re

out = subprocess.check_output(['git', 'show', '0752ab2^:scraper/scrapling_scraper/src/scraper/engine.py']).decode('utf-8', errors='ignore')
brands = re.findall(r'\{\s*"brand":\s*"([^"]+)"', out)
print(f"Total brands found: {len(brands)}")

sites_match = re.search(r'NEW_SITES\s*=\s*\[(.*?)\]', out, re.DOTALL)
if sites_match:
    sites_str = sites_match.group(1)
    sites = re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', sites_str)
    print(f"\nTotal NEW_SITES found: {len(sites)}")
    for name, domain in sites:
        print(f"  {name}: {domain}")

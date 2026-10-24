import urllib.request
import re
from urllib.parse import urljoin

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

urls_to_check = [
    'https://www.nintendo.co.jp/ir/library/financial/index.html',
    'https://global.toyota/jp/ir/financial-results/',
    'https://www.sony.com/ja/SonyInfo/IR/library/presen/er/',
    'https://www.fastretailing.com/jp/ir/library/results.html'
]

for base_url in urls_to_check:
    print("Checking:", base_url)
    try:
        req = urllib.request.Request(base_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html)
            full_links = [urljoin(base_url, link) for link in links]
            print(f"Found {len(full_links)} pdf links. Sample:")
            for l in full_links[:5]:
                print("  ", l)
    except Exception as e:
        print("  Error:", e)

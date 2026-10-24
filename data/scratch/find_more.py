import urllib.request
import re
from urllib.parse import urljoin

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

urls = [
    'https://www.nintendo.co.jp/ir/finance/index.html',
    'https://www.nintendo.co.jp/ir/events/index.html',
    'https://www.nintendo.co.jp/ir/index.html',
    'https://www.softbank.jp/corp/ir/documents/presentations/',
    'https://www.panasonic.com/jp/corporate/ir/relevant.html',
    'https://www.canon.co.jp/ir/results/index.html',
    'https://ir.rakuten.co.jp/investors/financials/quarterly_library.html'
]

for u in urls:
    try:
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html)
            links = [urljoin(u, l) for l in links if 'tanshin' in l.lower() or 'summary' in l.lower() or 'financial' in l.lower() or 'kessan' in l.lower()]
            if links:
                print(f"Success for {u}: {len(links)} candidate links")
                for l in links[:3]:
                    print("  ", l)
    except Exception as e:
        pass

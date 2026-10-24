import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import urllib.request
import re
from urllib.parse import urljoin
import os

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# Let's search some IR pages for PDFs
urls = [
    ("https://www.nintendo.co.jp/ir/finance/results/index.html", "nintendo"),
    ("https://www.sony.com/ja/SonyInfo/IR/library/presen/er/archive.html", "sony"),
    ("https://group.softbank/ir/financials/financial_reports", "softbank"),
    ("https://www.canon.co.jp/ir/results/index.html", "canon"),
    ("https://www.mhi.com/jp/finance/library/result/", "mhi"),
    ("https://www.panasonic.com/jp/corporate/ir/financial-results.html", "panasonic"),
    ("https://holdings.panasonic/jp/corporate/investors/financial-results.html", "panasonic_hd"),
    ("https://ir.hitachi.co.jp/ir_lib/er/", "hitachi"),
    ("https://www.ntt.co.jp/ir/library/financial/index.html", "ntt"),
    ("https://www.fastretailing.com/jp/ir/library/summary.html", "fastretailing")
]

found = []
for u, name in urls:
    try:
        req = urllib.request.Request(u, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            html = r.read().decode('utf-8', 'ignore')
            links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html)
            for l in links:
                full = urljoin(u, l)
                if any(w in full.lower() for w in ["tanshin", "summary", "kessan", "report", "er_"]):
                    found.append((name, full))
                    print(f"[{name}] {full}")
                    break
    except Exception as e:
        # print(f"Error for {name}: {e}")
        pass

print(f"Found {len(found)} candidates.")

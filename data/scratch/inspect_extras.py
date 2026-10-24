import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import urllib.request
import os
import fitz

os.makedirs("data/extra", exist_ok=True)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

targets = [
    ("softbank_q1_2026.pdf", "https://group.softbank/media/Project/sbg/sbg/pdf/ir/financials/financial_reports/financial-report_q1fy2026_01_ja.pdf"),
    ("mhi_tanshin_2026_1q.pdf", "https://www.mhi.com/jp/finance/library/result/pdf/fy20261q/kessan_tansin.pdf")
]

for filename, url in targets:
    path = os.path.join("data/extra", filename)
    print(f"Downloading {filename} from {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(path, "wb") as f:
                f.write(resp.read())
        print(f"Saved {filename}, size: {os.path.getsize(path)}")
    except Exception as e:
        print(f"Failed {filename}: {e}")

# Now inspect pages in data/extra
for f in os.listdir("data/extra"):
    if not f.endswith(".pdf"):
        continue
    p = os.path.join("data/extra", f)
    try:
        doc = fitz.open(p)
        print(f"\n--- {f} (Total pages: {len(doc)}) ---")
        for p_idx in range(len(doc)):
            txt = doc[p_idx].get_text()
            if any(k in txt for k in ["貸借対照表", "財政状態計算書", "資産の部", "負債の部", "純資産の部", "負債及び純資産"]):
                # Find title line
                title = [l.strip() for l in txt.split("\n") if any(k in l for k in ["貸借対照表", "財政状態計算書"])][:2]
                print(f"  Page {p_idx+1}: {title}")
    except Exception as e:
        print(f"Error reading {f}: {e}")

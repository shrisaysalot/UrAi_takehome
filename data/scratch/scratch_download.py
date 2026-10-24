import urllib.request
import os
import fitz

os.makedirs("data/extra", exist_ok=True)

# 1. Download Toyota 2027 1Q summary
toyota_url = "https://global.toyota/pages/global_toyota/ir/financial-results/2027_1q_summary_jp.pdf"
toyota_dest = "data/extra/toyota_2027_1q.pdf"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

print(f"Downloading {toyota_url}...")
try:
    req = urllib.request.Request(toyota_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        with open(toyota_dest, "wb") as f:
            f.write(resp.read())
    print("Toyota downloaded successfully! Size:", os.path.getsize(toyota_dest))
    
    doc = fitz.open(toyota_dest)
    print("Toyota doc pages:", len(doc))
    for i in range(len(doc)):
        text = doc[i].get_text()
        if "連結財政状態計算書" in text or "連結貸借対照表" in text or "資産" in text and "負債" in text:
            print(f"  Page {i+1} has balance sheet keywords!")
            lines = [l for l in text.split("\n") if l.strip()][:5]
            print(f"    Sample: {lines}")
except Exception as e:
    print("Toyota error:", e)

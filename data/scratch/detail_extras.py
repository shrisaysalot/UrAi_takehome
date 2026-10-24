import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
import fitz

checks = [
    ("Toyota (p8)", "data/extra/toyota_2027_1q.pdf", 7),
    ("MHI (p5)", "data/extra/mhi_tanshin_2026_1q.pdf", 4),
    ("Softbank (p33)", "data/extra/softbank_q1_2026.pdf", 32)
]

for name, path, p_idx in checks:
    doc = fitz.open(path)
    page = doc[p_idx]
    print(f"\n=================== {name} ===================")
    print("Page rect:", page.rect)
    blocks = page.get_text("blocks")
    print("Number of blocks:", len(blocks))
    lines = [b[4].strip().replace('\n', ' | ') for b in blocks if b[4].strip()][:15]
    for l in lines:
        print(" ", l[:90])

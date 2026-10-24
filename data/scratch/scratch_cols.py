import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import fitz
import numpy as np
from src.number_parser import parse_number

def test_column_detection(pdf_path, page_idx=0):
    doc = fitz.open(pdf_path)
    page = doc[page_idx]
    words = page.get_text("words")
    
    # 1. Identify numeric tokens
    num_tokens = []
    for w in words:
        text = w[4].strip()
        status, val = parse_number(text)
        # Check if text is numeric or nil
        if status in ("present", "nil") and any(c.isdigit() or c in "－-—" for c in text):
            num_tokens.append({
                "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3],
                "text": text, "val": val
            })
            
    print(f"\n--- {pdf_path} (p{page_idx+1}) ---")
    print(f"Total words: {len(words)}, Numeric tokens found: {len(num_tokens)}")
    if not num_tokens:
        print("No numeric tokens!")
        return
        
    # Sort right edges
    right_edges = sorted([t["x1"] for t in num_tokens])
    
    # Cluster right edges by gap threshold (e.g. gap > 20)
    clusters = []
    curr_c = [right_edges[0]]
    for r in right_edges[1:]:
        if r - curr_c[-1] > 20.0:  # Column separation gap
            clusters.append(curr_c)
            curr_c = [r]
        else:
            curr_c.append(r)
    if curr_c:
        clusters.append(curr_c)
        
    print(f"Detected {len(clusters)} column clusters from right edges:")
    for idx, c in enumerate(clusters):
        print(f"  Col {idx+1}: count={len(c)}, min={min(c):.1f}, median={np.median(c):.1f}, max={max(c):.1f}")
        
    # First numeric column start
    min_num_x0 = min(t["x0"] for t in num_tokens)
    print(f"First numeric col x0 start: {min_num_x0:.1f}")

test_column_detection("data/balance_sheet_page4.pdf", 0)
test_column_detection("data/synthetic/scaled_08x.pdf", 0)
test_column_detection("data/synthetic/scaled_12x.pdf", 0)
test_column_detection("data/synthetic/shifted_margins.pdf", 0)
test_column_detection("data/synthetic/three_columns.pdf", 0)
test_column_detection("data/extra/toyota_2027_1q.pdf", 7)
test_column_detection("data/extra/mhi_tanshin_2026_1q.pdf", 4)
test_column_detection("data/extra/mhi_tanshin_2026_1q.pdf", 5)

import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import fitz
import numpy as np
from src.row_clustering import RowClusterer

def test_indent_clustering(pdf_path, page_idx=0):
    doc = fitz.open(pdf_path)
    page = doc[page_idx]
    clusterer = RowClusterer()
    extracted_words = []
    for w in page.get_text("words"):
        extracted_words.append({
            "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3],
            "text": w[4]
        })
    lines = clusterer.cluster_visual_lines(extracted_words)
    title_raw, unit_dict, columns, start_idx = clusterer.extract_metadata(lines)
    
    # Extract candidate rows
    # Collect all label x0
    label_x0s = []
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        w_label = [w for w in line if w["x1"] < 330.0]
        if w_label:
            label_x0s.append(w_label[0]["x0"])
            
    # Cluster unique x0 within tolerance (e.g. 3.0pt)
    sorted_x = sorted(label_x0s)
    clusters = []
    curr = [sorted_x[0]]
    for x in sorted_x[1:]:
        if x - np.mean(curr) > 4.0:  # Gap threshold between distinct indentation tiers
            clusters.append(curr)
            curr = [x]
        else:
            curr.append(x)
    if curr:
        clusters.append(curr)
        
    print(f"\n--- {pdf_path} (p{page_idx+1}) ---")
    print(f"Total label rows: {len(label_x0s)}, Indent clusters detected: {len(clusters)}")
    centers = [round(float(np.mean(c)), 1) for c in clusters]
    print(f"Cluster centers: {centers}")
    if len(centers) > 1:
        diffs = [round(centers[i+1] - centers[i], 1) for i in range(len(centers)-1)]
        print(f"Indent steps between levels: {diffs}, median: {round(float(np.median(diffs)), 1)}")

test_indent_clustering("data/balance_sheet_page4.pdf", 0)
test_indent_clustering("data/synthetic/scaled_08x.pdf", 0)
test_indent_clustering("data/synthetic/indent_step_20pt.pdf", 0)
test_indent_clustering("data/synthetic/shifted_margins.pdf", 0)
test_indent_clustering("data/extra/toyota_2027_1q.pdf", 7)
test_indent_clustering("data/extra/mhi_tanshin_2026_1q.pdf", 4)

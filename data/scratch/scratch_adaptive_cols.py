import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import fitz
import numpy as np
import re
from src.row_clustering import RowClusterer
from src.number_parser import parse_number

def analyze_adaptive_columns(pdf_path, page_idx=0):
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
    
    # Collect candidate numbers strictly from table body lines (start_idx to end)
    # Exclude page footers (e.g. "- 4 -")
    body_num_tokens = []
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        line_str = "".join(w["text"] for w in line)
        if re.match(r"^[\s\-–—]*\d+[\s\-–—]*$", line_str.strip()):
            continue
        for w in line:
            status, val = parse_number(w["text"])
            if status in ("present", "nil") and any(c.isdigit() or c in "－-—" for c in w["text"]):
                body_num_tokens.append(w)
                
    # Right-edge projection
    if not body_num_tokens:
        print(f"[{pdf_path}] No body numbers found!")
        return
        
    sorted_tokens = sorted(body_num_tokens, key=lambda t: t["x1"])
    right_edges = [t["x1"] for t in sorted_tokens]
    
    # 1D gap-based clustering on right edges
    # Standard column gap in A4 portrait is at least 15-20pt
    clusters = []
    curr_c = [sorted_tokens[0]]
    for t in sorted_tokens[1:]:
        if t["x1"] - curr_c[-1]["x1"] > 20.0:
            clusters.append(curr_c)
            curr_c = [t]
        else:
            curr_c.append(t)
    if curr_c:
        clusters.append(curr_c)
        
    # Filter clusters: must have substantial support (e.g. >= 5 tokens or >= 20% of max cluster)
    max_c_len = max(len(c) for c in clusters)
    valid_col_clusters = [c for c in clusters if len(c) >= max(4, int(0.25 * max_c_len))]
    
    # For each valid column cluster, determine column span [x_min, x_max] and right boundary
    col_bounds = []
    for c in valid_col_clusters:
        min_x0 = min(t["x0"] for t in c)
        max_x1 = max(t["x1"] for t in c)
        col_bounds.append((min_x0, max_x1))
        
    # Derive column separators (midpoint between col_k max_x1 and col_{k+1} min_x0)
    col_splits = []
    for k in range(len(col_bounds) - 1):
        split = (col_bounds[k][1] + col_bounds[k+1][0]) / 2.0
        col_splits.append(split)
        
    # Derive label-number separation gutter (max_label_x)
    first_col_x0 = col_bounds[0][0]
    
    # Label tokens in body lines are tokens with x1 < first_col_x0
    label_tokens = []
    for idx in range(start_idx, len(lines)):
        for w in lines[idx]:
            if w["x1"] < first_col_x0:
                label_tokens.append(w)
    max_label_token_x1 = max(w["x1"] for w in label_tokens) if label_tokens else first_col_x0 - 20.0
    gutter_split = (max_label_token_x1 + first_col_x0) / 2.0
    
    print(f"\n--- {pdf_path} (p{page_idx+1}) ---")
    print(f"Detected columns: {len(col_bounds)}")
    print(f"Col bounds: {[(round(b[0],1), round(b[1],1)) for b in col_bounds]}")
    print(f"Col splits: {[round(s,1) for s in col_splits]}")
    print(f"Label gutter split (max_label_x): {round(gutter_split,1)} (labels end at {round(max_label_token_x1,1)}, col 1 starts at {round(first_col_x0,1)})")

analyze_adaptive_columns("data/balance_sheet_page4.pdf", 0)
analyze_adaptive_columns("data/synthetic/scaled_08x.pdf", 0)
analyze_adaptive_columns("data/synthetic/scaled_12x.pdf", 0)
analyze_adaptive_columns("data/synthetic/shifted_margins.pdf", 0)
analyze_adaptive_columns("data/synthetic/indent_step_20pt.pdf", 0)
analyze_adaptive_columns("data/synthetic/three_columns.pdf", 0)
analyze_adaptive_columns("data/extra/toyota_2027_1q.pdf", 7)
analyze_adaptive_columns("data/extra/mhi_tanshin_2026_1q.pdf", 4)
analyze_adaptive_columns("data/extra/mhi_tanshin_2026_1q.pdf", 5)
analyze_adaptive_columns("data/extra/softbank_q1_2026.pdf", 32)

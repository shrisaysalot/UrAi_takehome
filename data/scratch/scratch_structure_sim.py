import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
from eval.aligner import normalize_label

def test_adaptive_structure():
    with open("data/ground_truth_v0.json", "r", encoding="utf-8") as f:
        gt = json.load(f)

    rows = gt["tables"][0]["rows"]
    cols = ["c1", "c2"]
    
    def cell_val(row, c_id):
        return row.get("cells", {}).get(c_id, {}).get("value_in_unit")

    # 1. Type classification
    for r in rows:
        lbl = normalize_label(r.get("label_raw", ""))
        has_val = bool(r.get("cells"))
        if not has_val:
            r["type"] = "header"
        elif lbl in ("資産合計", "負債及び純資産合計", "負債及び資本合計") or lbl.endswith("総計"):
            r["type"] = "total"
        elif "合計" in lbl or "計" in lbl or "純額" in lbl:
            r["type"] = "subtotal"
        else:
            r["type"] = "item"

    # 2. Indentation clustering
    label_x0s = [r.get("bbox", [62.3])[0] for r in rows]
    sorted_x = sorted(label_x0s)
    clusters = []
    curr = [sorted_x[0]]
    for x in sorted_x[1:]:
        if x - (sum(curr) / len(curr)) > 3.5:
            clusters.append(curr)
            curr = [x]
        else:
            curr.append(x)
    if curr:
        clusters.append(curr)
    cluster_centers = sorted([sum(c)/len(c) for c in clusters])
    print("Cluster centers:", [round(c, 1) for c in cluster_centers])

    for r in rows:
        x0 = r.get("bbox", [62.3])[0]
        level = min(range(len(cluster_centers)), key=lambda k: abs(x0 - cluster_centers[k]))
        r["_indent_level"] = level

    # Stack-based parent assignment
    header_stack = []
    for i, r in enumerate(rows):
        lvl = r["_indent_level"]
        lbl = normalize_label(r.get("label_raw", ""))

        if r["type"] == "total":
            lvl0_headers = [idx for idx, row in enumerate(rows[:i]) if row.get("type") == "header" and row.get("_indent_level") == 0]
            r["parent_row_idx"] = lvl0_headers[0] if lvl0_headers else (0 if i > 0 else None)
            continue

        if ("減価償却累計額" in lbl or "貸倒引当金" in lbl) and i > 0 and rows[i - 1]["type"] == "item":
            r["parent_row_idx"] = i - 1
            continue

        if "純額" in lbl:
            sec_parent = None
            for plvl, pidx in reversed(header_stack):
                if plvl <= lvl - 1 and rows[pidx]["type"] == "header":
                    sec_parent = pidx
                    break
            r["parent_row_idx"] = sec_parent if sec_parent is not None else (header_stack[-1][1] if header_stack else None)
            continue

        while header_stack and header_stack[-1][0] >= lvl:
            header_stack.pop()

        if header_stack:
            r["parent_row_idx"] = header_stack[-1][1]
        else:
            r["parent_row_idx"] = None

        if r["type"] == "header":
            header_stack.append((lvl, i))

    # Compare parents with GT parents
    parent_matches = sum(1 for i, r in enumerate(rows) if r["parent_row_idx"] == gt["tables"][0]["rows"][i]["parent_row_idx"])
    print(f"Parent accuracy: {parent_matches}/{len(rows)} ({parent_matches/len(rows)*100:.1f}%)")

test_adaptive_structure()

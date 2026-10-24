import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
from eval.aligner import normalize_label

with open("data/ground_truth_v0.json", "r", encoding="utf-8") as f:
    gt = json.load(f)["tables"][0]["rows"]

cols = ["c1", "c2"]
tolerance_per_term = 1

def get_val(r, c_id):
    return r.get("cells", {}).get(c_id, {}).get("value_in_unit")

# Type classification test
for r in gt:
    lbl = normalize_label(r.get("label_raw", ""))
    has_val = bool(r.get("cells"))
    if not has_val:
        t = "header"
    elif lbl in ("資産合計", "負債及び純資産合計", "負債及び資本合計") or lbl.endswith("総計"):
        t = "total"
    elif "合計" in lbl or "小計" in lbl or "純額" in lbl or lbl.endswith("計"):
        t = "subtotal"
    else:
        t = "item"
    if t != r["type"]:
        print(f"Type mismatch on {lbl}: expected {r['type']}, got {t}")

# Check Candidate selection for 有形固定資産合計, 固定資産合計, 資産合計
for i, r in enumerate(gt):
    lbl = normalize_label(r.get("label_raw", ""))
    if r.get("type") in ("subtotal", "total") and "純額" not in lbl:
        print(f"\nRow {i} {lbl}:")
        # Candidate 1: Leaf items under enclosing header
        # Find enclosing header
        p_idx = r.get("parent_row_idx")
        start = (p_idx + 1) if p_idx is not None else 0
        for prev in range(i - 1, start - 1, -1):
            if gt[prev]["type"] in ("subtotal", "total") and "純額" not in normalize_label(gt[prev]["label_raw"]):
                start = prev + 1
                break
        
        # Exclude gross and contra if there is a net row
        gross_contra = set()
        for ci in range(start, i):
            if "純額" in normalize_label(gt[ci]["label_raw"]) and gt[ci].get("derived_from"):
                gross_contra.update(gt[ci]["derived_from"])
                
        leaf_items = [ci for ci in range(start, i) if ci not in gross_contra and gt[ci]["type"] in ("item", "subtotal") and gt[ci].get("cells")]
        
        # Candidate 2: Major section subtotals
        # Subtotals immediately under the parent or major sections
        sec_subtotals = [ci for ci in range(i) if gt[ci]["type"] == "subtotal" and "純額" not in normalize_label(gt[ci]["label_raw"])]
        # Filter sec_subtotals: only those not already summed by another subtotal
        
        for cand_name, cand in [("leaf_items", leaf_items), ("sec_subtotals", sec_subtotals)]:
            if not cand or len(cand) < 2:
                continue
            all_match = True
            for c in cols:
                tot = get_val(r, c)
                c_vals = [get_val(gt[ci], c) for ci in cand if get_val(gt[ci], c) is not None]
                if len(c_vals) != len(cand) or tot is None:
                    all_match = False
                    break
                diff = abs(sum(c_vals) - tot)
                max_tol = len(cand) * tolerance_per_term
                if diff > max_tol:
                    all_match = False
                    break
            if all_match:
                print(f"  MATCHED {cand_name}: {cand} vs GT={r.get('derived_from')}")
                break

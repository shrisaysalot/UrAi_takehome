import os
import sys
sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
from src.parser import FinancialTableParser
from eval.aligner import normalize_label

with open("data/ground_truth_v0.json", "r", encoding="utf-8") as f:
    gt = json.load(f)

gt_rows = gt["tables"][0]["rows"]
cols = ["c1", "c2"]

def get_val(r, c_id):
    c = r.get("cells", {}).get(c_id, {})
    return c.get("value_in_unit")

# Let's inspect each subtotal row in GT and see its derived_from
for i, r in enumerate(gt_rows):
    if r.get("derived_from"):
        lbl = r["label_raw"]
        gt_derived = r["derived_from"]
        print(f"Row {i:2d} ({lbl:<20}): GT derived_from = {gt_derived}")
        for c in cols:
            tot = get_val(r, c)
            # Check sum of gt_derived
            if "純額" in lbl:
                gross = get_val(gt_rows[gt_derived[0]], c)
                contra = get_val(gt_rows[gt_derived[1]], c)
                diff = abs((gross + contra if contra < 0 else gross - contra) - tot)
                print(f"   [{c}] Net calc diff = {diff}")
            else:
                s = sum(get_val(gt_rows[ci], c) for ci in gt_derived if get_val(gt_rows[ci], c) is not None)
                diff = abs(s - tot)
                print(f"   [{c}] Sum calc diff = {diff} (k={len(gt_derived)})")

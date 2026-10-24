import json
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open('data/ground_truth_v0.json', 'r', encoding='utf-8') as f:
    gt = json.load(f)['tables'][0]['rows']
with open('out/page4.json', 'r', encoding='utf-8') as f:
    pred = json.load(f)['tables'][0]['rows']

for i in range(len(gt)):
    g_type, p_type = gt[i]['type'], pred[i]['type']
    g_p, p_p = gt[i]['parent_row_idx'], pred[i]['parent_row_idx']
    g_d, p_d = gt[i]['derived_from'], pred[i]['derived_from']
    lbl = gt[i]['label_raw']
    if g_type != p_type:
        print(f"Row {i} {lbl}: type GT={g_type} vs Pred={p_type}")
    if g_p != p_p:
        print(f"Row {i} {lbl}: parent GT={g_p} vs Pred={p_p}")
    if g_d != p_d:
        print(f"Row {i} {lbl}: derived_from GT={g_d} vs Pred={p_d}")

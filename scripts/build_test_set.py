import os
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import json
import copy
import fitz

def build_test_set():
    os.makedirs("data/synthetic", exist_ok=True)
    os.makedirs("data/extra", exist_ok=True)
    
    src_pdf = "data/balance_sheet_page4.pdf"
    gt_file = "data/ground_truth_v0.json"
    
    with open(gt_file, "r", encoding="utf-8") as f:
        base_gt = json.load(f)
        
    doc = fitz.open(src_pdf)
    orig_page = doc[0]
    orig_rect = orig_page.rect
    
    # -------------------------------------------------------------
    # 1. Scaled 0.8x
    # -------------------------------------------------------------
    scaled_08_pdf = "data/synthetic/scaled_08x.pdf"
    scaled_08_gt_file = "data/synthetic/scaled_08x_gt.json"
    d_08 = fitz.open()
    p_08 = d_08.new_page(width=orig_rect.width * 0.8, height=orig_rect.height * 0.8)
    p_08.show_pdf_page(p_08.rect, doc, 0)
    d_08.save(scaled_08_pdf)
    d_08.close()
    
    gt_08 = copy.deepcopy(base_gt)
    for r in gt_08["tables"][0]["rows"]:
        if "bbox" in r and r["bbox"]:
            r["bbox"] = [round(coord * 0.8, 2) for coord in r["bbox"]]
    with open(scaled_08_gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_08, f, ensure_ascii=False, indent=2)
    print("Created scaled_08x.pdf and GT")

    # -------------------------------------------------------------
    # 2. Scaled 1.2x
    # -------------------------------------------------------------
    scaled_12_pdf = "data/synthetic/scaled_12x.pdf"
    scaled_12_gt_file = "data/synthetic/scaled_12x_gt.json"
    d_12 = fitz.open()
    p_12 = d_12.new_page(width=orig_rect.width * 1.2, height=orig_rect.height * 1.2)
    p_12.show_pdf_page(p_12.rect, doc, 0)
    d_12.save(scaled_12_pdf)
    d_12.close()
    
    gt_12 = copy.deepcopy(base_gt)
    for r in gt_12["tables"][0]["rows"]:
        if "bbox" in r and r["bbox"]:
            r["bbox"] = [round(coord * 1.2, 2) for coord in r["bbox"]]
    with open(scaled_12_gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_12, f, ensure_ascii=False, indent=2)
    print("Created scaled_12x.pdf and GT")

    # -------------------------------------------------------------
    # 3. Shifted Margins (+50pt x, +40pt y)
    # -------------------------------------------------------------
    dx, dy = 50.0, 40.0
    shifted_pdf = "data/synthetic/shifted_margins.pdf"
    shifted_gt_file = "data/synthetic/shifted_margins_gt.json"
    d_sh = fitz.open()
    p_sh = d_sh.new_page(width=orig_rect.width + 100, height=orig_rect.height + 80)
    target_rect = fitz.Rect(dx, dy, dx + orig_rect.width, dy + orig_rect.height)
    p_sh.show_pdf_page(target_rect, doc, 0)
    d_sh.save(shifted_pdf)
    d_sh.close()
    
    gt_sh = copy.deepcopy(base_gt)
    for r in gt_sh["tables"][0]["rows"]:
        if "bbox" in r and r["bbox"]:
            r["bbox"] = [
                round(r["bbox"][0] + dx, 2),
                round(r["bbox"][1] + dy, 2),
                round(r["bbox"][2] + dx, 2),
                round(r["bbox"][3] + dy, 2)
            ]
    with open(shifted_gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_sh, f, ensure_ascii=False, indent=2)
    print("Created shifted_margins.pdf and GT")

    # -------------------------------------------------------------
    # 4. Scanned Page (No text layer)
    # -------------------------------------------------------------
    scanned_pdf = "data/synthetic/scanned_page.pdf"
    d_sc = fitz.open()
    pix = orig_page.get_pixmap(dpi=150)
    p_sc = d_sc.new_page(width=orig_rect.width, height=orig_rect.height)
    p_sc.insert_image(orig_rect, pixmap=pix)
    d_sc.save(scanned_pdf)
    d_sc.close()
    print("Created scanned_page.pdf")

    # -------------------------------------------------------------
    # 5. Garbled Text Layer
    # -------------------------------------------------------------
    garbled_pdf = "data/synthetic/garbled_text.pdf"
    d_gar = fitz.open()
    p_gar = d_gar.new_page(width=orig_rect.width, height=orig_rect.height)
    # Render background image
    p_gar.insert_image(orig_rect, pixmap=pix)
    # Insert corrupted text overlay with \ufffd replacement characters
    cjk_font = "C:/Windows/Fonts/msgothic.ttc"
    # Insert corrupted blocks
    for i in range(15):
        y = 100 + i * 40
        corrupted_text = "\ufffd\ufffd\ue001\ue002\ufffd" * 4 + " 12345"
        p_gar.insert_text(fitz.Point(60, y), corrupted_text, fontfile=cjk_font, fontsize=9)
    d_gar.save(garbled_pdf)
    d_gar.close()
    print("Created garbled_text.pdf")

    # -------------------------------------------------------------
    # 6. Indentation Step Changed (Render table with 20.0pt indent)
    # -------------------------------------------------------------
    indent_pdf = "data/synthetic/indent_step_20pt.pdf"
    indent_gt_file = "data/synthetic/indent_step_20pt_gt.json"
    
    # We build a page with a clean rendering where indent step is 20pt instead of 12.9pt
    d_ind = fitz.open()
    p_ind = d_ind.new_page(width=orig_rect.width, height=orig_rect.height)
    
    # Header metadata
    p_ind.insert_text(fitz.Point(54.7, 73.6), "（１）連結貸借対照表", fontname="japan", fontsize=10)
    p_ind.insert_text(fitz.Point(490.0, 100.0), "（単位：千円）", fontname="japan", fontsize=8)
    
    # Column headers
    # c1 header
    p_ind.insert_text(fitz.Point(340.0, 115.0), "前連結会計年度", fontname="japan", fontsize=8)
    p_ind.insert_text(fitz.Point(340.0, 127.0), "(2025 年３月 31 日)", fontname="japan", fontsize=8)
    # c2 header
    p_ind.insert_text(fitz.Point(445.0, 115.0), "当連結会計年度", fontname="japan", fontsize=8)
    p_ind.insert_text(fitz.Point(445.0, 127.0), "(2026 年３月 31 日)", fontname="japan", fontsize=8)
    
    # Compute levels from base GT
    # level 0: 資産の部
    # level 1: 流動資産, 固定資産, 資産合計
    # level 2: 有形固定資産, 無形固定資産, 投資その他の資産
    # level 4: contra accounts (減価償却累計額)
    # level 3: normal items
    gt_ind = copy.deepcopy(base_gt)
    base_x = 60.0
    new_step = 20.0  # 20.0pt instead of 12.9pt
    
    y_start = 148.0
    y_step = 14.5
    
    for idx, r in enumerate(gt_ind["tables"][0]["rows"]):
        lbl = r["label_raw"]
        # Determine level from original bbox x0
        orig_x0 = r["bbox"][0]
        level = int(round((orig_x0 - 62.3) / 12.9))
        x_pos = base_x + level * new_step
        y_pos = y_start + idx * y_step
        
        # Render label
        p_ind.insert_text(fitz.Point(x_pos, y_pos), lbl, fontname="japan", fontsize=8)
        
        # Render cells
        c1_cell = r["cells"].get("c1")
        if c1_cell and c1_cell["raw"] is not None:
            # Right-aligned around x=415
            p_ind.insert_text(fitz.Point(365.0, y_pos), c1_cell["raw"], fontname="japan", fontsize=8)
        c2_cell = r["cells"].get("c2")
        if c2_cell and c2_cell["raw"] is not None:
            # Right-aligned around x=520
            p_ind.insert_text(fitz.Point(470.0, y_pos), c2_cell["raw"], fontname="japan", fontsize=8)
            
        r["bbox"] = [round(x_pos, 2), round(y_pos - 9, 2), round(520.0, 2), round(y_pos + 2, 2)]
        
    d_ind.save(indent_pdf)
    d_ind.close()
    
    with open(indent_gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_ind, f, ensure_ascii=False, indent=2)
    print("Created indent_step_20pt.pdf and GT")

    # -------------------------------------------------------------
    # 7. Three Numeric Columns (Add c0 column: 2024年3月31日)
    # -------------------------------------------------------------
    three_col_pdf = "data/synthetic/three_columns.pdf"
    three_col_gt_file = "data/synthetic/three_columns_gt.json"
    
    # Use wider page (e.g. landscape or 700 width)
    d_3c = fitz.open()
    p_3c = d_3c.new_page(width=700.0, height=842.0)
    
    # Headers
    p_3c.insert_text(fitz.Point(54.7, 73.6), "（１）連結貸借対照表", fontname="japan", fontsize=10)
    p_3c.insert_text(fitz.Point(580.0, 100.0), "（単位：千円）", fontname="japan", fontsize=8)
    
    # 3 Column Headers:
    # c1: 前々連結会計年度 (2024-03-31)
    p_3c.insert_text(fitz.Point(320.0, 115.0), "前々連結会計年度", fontname="japan", fontsize=7.5)
    p_3c.insert_text(fitz.Point(320.0, 127.0), "(2024 年３月 31 日)", fontname="japan", fontsize=7.5)
    # c2: 前連結会計年度 (2025-03-31)
    p_3c.insert_text(fitz.Point(440.0, 115.0), "前連結会計年度", fontname="japan", fontsize=7.5)
    p_3c.insert_text(fitz.Point(440.0, 127.0), "(2025 年３月 31 日)", fontname="japan", fontsize=7.5)
    # c3: 当連結会計年度 (2026-03-31)
    p_3c.insert_text(fitz.Point(560.0, 115.0), "当連結会計年度", fontname="japan", fontsize=7.5)
    p_3c.insert_text(fitz.Point(560.0, 127.0), "(2026 年３月 31 日)", fontname="japan", fontsize=7.5)
    
    gt_3c = copy.deepcopy(base_gt)
    gt_3c["tables"][0]["columns"] = [
        {"id": "c1", "header_raw": "前々連結会計年度\n(2024 年３月 31 日)", "period_end": "2024-03-31"},
        {"id": "c2", "header_raw": "前連結会計年度\n(2025 年３月 31 日)", "period_end": "2025-03-31"},
        {"id": "c3", "header_raw": "当連結会計年度\n(2026 年３月 31 日)", "period_end": "2026-03-31"}
    ]
    
    for idx, r in enumerate(gt_3c["tables"][0]["rows"]):
        lbl = r["label_raw"]
        orig_x0 = r["bbox"][0]
        level = int(round((orig_x0 - 62.3) / 12.9))
        x_pos = 50.0 + level * 14.0
        y_pos = y_start + idx * y_step
        
        p_3c.insert_text(fitz.Point(x_pos, y_pos), lbl, fontname="japan", fontsize=8)
        
        # c1 in new table is a synthetic prior year value (e.g. 90% of old c1 or identical)
        old_c1 = r["cells"].get("c1")
        old_c2 = r["cells"].get("c2")
        
        new_cells = {}
        if old_c1:
            val1 = old_c1["value_in_unit"]
            # prior year synthetic
            if val1 is not None:
                syn_val = int(val1 * 0.95)
                syn_raw = f"{syn_val:,}"
            else:
                syn_val = None
                syn_raw = old_c1["raw"]
            new_cells["c1"] = {"raw": syn_raw, "status": old_c1["status"], "value_in_unit": syn_val}
            p_3c.insert_text(fitz.Point(345.0, y_pos), syn_raw, fontname="japan", fontsize=8)
            
            # c2 is old c1
            new_cells["c2"] = copy.deepcopy(old_c1)
            if old_c1["raw"]:
                p_3c.insert_text(fitz.Point(465.0, y_pos), old_c1["raw"], fontname="japan", fontsize=8)
                
            # c3 is old c2
            new_cells["c3"] = copy.deepcopy(old_c2)
            if old_c2 and old_c2["raw"]:
                p_3c.insert_text(fitz.Point(585.0, y_pos), old_c2["raw"], fontname="japan", fontsize=8)
                
        r["cells"] = new_cells
        r["bbox"] = [round(x_pos, 2), round(y_pos - 9, 2), round(650.0, 2), round(y_pos + 2, 2)]
        
    d_3c.save(three_col_pdf)
    d_3c.close()
    
    with open(three_col_gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_3c, f, ensure_ascii=False, indent=2)
    print("Created three_columns.pdf and GT")
    
    doc.close()
    print("Successfully built all synthetic test variants!")

if __name__ == "__main__":
    build_test_set()

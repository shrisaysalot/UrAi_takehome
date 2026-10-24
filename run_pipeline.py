"""
Evaluation and Pipeline Execution Script.
Runs both baseline and improved parsers on data/balance_sheet_page4.pdf,
scores both against data/ground_truth_v0.json,
tests the OCR route escalation on a synthetic scanned page,
and produces detailed comparative evaluation reports.
"""

import json
import os
import sys
import fitz
from src.parser import FinancialTableParser
from eval.scorer import TableScorer
from eval.report import format_report

# Ensure utf-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def run_pipeline():
    pdf_path = "data/balance_sheet_page4.pdf"
    gt_path = "data/ground_truth_v0.json"
    
    with open(gt_path, "r", encoding="utf-8") as f:
        gt_doc = json.load(f)
        
    scorer = TableScorer(tolerance_per_term=1)
    
    print("=" * 70)
    print("1. RUNNING BASELINE PARSER")
    print("=" * 70)
    baseline_parser = FinancialTableParser(mode="baseline")
    baseline_out = baseline_parser.parse_pdf(pdf_path, page_num=4, out_path="out/page4_baseline.json")
    baseline_scores = scorer.score(gt_doc, baseline_out)
    baseline_report = format_report(baseline_scores)
    with open("out/baseline_report.txt", "w", encoding="utf-8") as f:
        f.write(baseline_report)
    print(baseline_report)
    
    print("\n" + "=" * 70)
    print("2. RUNNING IMPROVED PARSER")
    print("=" * 70)
    improved_parser = FinancialTableParser(mode="improved")
    improved_out = improved_parser.parse_pdf(pdf_path, page_num=4, out_path="out/page4.json")
    improved_scores = scorer.score(gt_doc, improved_out)
    improved_report = format_report(improved_scores)
    with open("out/improved_report.txt", "w", encoding="utf-8") as f:
        f.write(improved_report)
    print(improved_report)
    
    print("\n" + "=" * 70)
    print("3. TESTING OCR ESCALATION ROUTE (SYNTHETIC SCANNED PAGE)")
    print("=" * 70)
    # Create synthetic scanned PDF: render page to pixmap and insert into new doc without text layer
    src_doc = fitz.open(pdf_path)
    page = src_doc[0]
    pix = page.get_pixmap(dpi=150)
    scanned_doc = fitz.open()
    new_page = scanned_doc.new_page(width=page.rect.width, height=page.rect.height)
    new_page.insert_image(page.rect, pixmap=pix)
    
    os.makedirs("data/scratch", exist_ok=True)
    scanned_pdf_path = "data/scratch/synthetic_scanned_page4.pdf"
    scanned_doc.save(scanned_pdf_path)
    scanned_doc.close()
    src_doc.close()
    
    # Run router on scanned document
    scanned_parser = FinancialTableParser(mode="improved")
    scanned_out = scanned_parser.parse_pdf(scanned_pdf_path, page_num=4, out_path="out/page4_ocr_stub.json")
    print("Scanned Page Routing Result:")
    print(f"  Extraction Method: {scanned_out['extraction_method']}")
    print(f"  Route Reason:      {scanned_out['route_reason']}")
    print(f"  Tables stub note:  {scanned_out['tables'][0].get('stub_note')}")
    
    # Save score comparison summary
    comparison = {
        "baseline": {
            "row_recall": baseline_scores["alignment"]["row_recall"],
            "row_precision": baseline_scores["alignment"]["row_precision"],
            "exact_label_accuracy": baseline_scores["alignment"]["exact_label_accuracy"],
            "cell_raw_accuracy": baseline_scores["extraction"]["cell_raw_accuracy"],
            "parsing_accuracy": baseline_scores["parsing"]["parsing_accuracy"],
            "header_vs_item_accuracy": baseline_scores["structure"]["header_vs_item_accuracy"],
            "subtotal_total_accuracy": baseline_scores["structure"]["subtotal_total_accuracy"],
            "parent_accuracy": baseline_scores["structure"]["parent_accuracy"],
            "invariants_all_passed": baseline_scores["invariants"]["all_passed"],
            "alignment_cost": baseline_scores["alignment"]["total_alignment_cost"],
        },
        "improved": {
            "row_recall": improved_scores["alignment"]["row_recall"],
            "row_precision": improved_scores["alignment"]["row_precision"],
            "exact_label_accuracy": improved_scores["alignment"]["exact_label_accuracy"],
            "cell_raw_accuracy": improved_scores["extraction"]["cell_raw_accuracy"],
            "parsing_accuracy": improved_scores["parsing"]["parsing_accuracy"],
            "header_vs_item_accuracy": improved_scores["structure"]["header_vs_item_accuracy"],
            "subtotal_total_accuracy": improved_scores["structure"]["subtotal_total_accuracy"],
            "parent_accuracy": improved_scores["structure"]["parent_accuracy"],
            "invariants_all_passed": improved_scores["invariants"]["all_passed"],
            "alignment_cost": improved_scores["alignment"]["total_alignment_cost"],
        },
        "ocr_route": {
            "extraction_method": scanned_out["extraction_method"],
            "route_reason": scanned_out["route_reason"],
        }
    }
    
    with open("out/evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
        
    print("\nSummary saved to out/evaluation_summary.json")


if __name__ == "__main__":
    run_pipeline()

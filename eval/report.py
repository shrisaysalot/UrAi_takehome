"""
Evaluation Report Formatter.
Generates human-readable and structured markdown/text reports of evaluation runs.
"""

from typing import Any, Dict


def format_report(score_dict: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("           FINANCIAL TABLE EXTRACTION EVALUATION REPORT")
    lines.append("=" * 70)
    
    gate = score_dict.get("page_level_gate", "UNKNOWN")
    lines.append(f"Page-level Gate: {gate}")
    if gate != "PASSED":
        lines.append(f"Failure Reason: {score_dict.get('failure_reason', 'N/A')}")
        lines.append("=" * 70)
        return "\n".join(lines)
        
    align = score_dict["alignment"]
    extract = score_dict["extraction"]
    parse = score_dict["parsing"]
    struct = score_dict["structure"]
    invars = score_dict["invariants"]
    
    lines.append(f"Alignment Cost per page: {align['total_alignment_cost']:.4f}")
    lines.append("")
    lines.append("--- LAYER 1: ROW ALIGNMENT ---")
    lines.append(f"  Confirmed Rows:        {align['confirmed']} (Exact: {align['exact']}, Fuzzy: {align['fuzzy']})")
    lines.append(f"  Unresolved Rows:       {align['unresolved']}")
    lines.append(f"  Dropped GT Rows:       {align['dropped']}")
    lines.append(f"  Inserted Pred Rows:    {align['inserted']}")
    lines.append(f"  Row Recall:            {align['row_recall'] * 100:.2f}%")
    lines.append(f"  Row Precision:         {align['row_precision'] * 100:.2f}%")
    lines.append(f"  Exact Label Accuracy:  {align['exact_label_accuracy'] * 100:.2f}%")
    lines.append("")
    lines.append("--- LAYER 2: CELL EXTRACTION (RAW TEXT) ---")
    lines.append(f"  Total GT Data Cells:   {extract['total_gt_cells']}")
    lines.append(f"  Raw Matched Cells:     {extract['raw_matched_cells']}")
    lines.append(f"  Cell Raw Accuracy:     {extract['cell_raw_accuracy'] * 100:.2f}%")
    lines.append("")
    lines.append("--- LAYER 3: VALUE PARSING (OVER CONFIRMED RAW-MATCHED CELLS) ---")
    lines.append(f"  Eligible Cells:        {parse['eligible_cells']}")
    lines.append(f"  Status Accuracy:       {parse['status_accuracy'] * 100:.2f}%")
    lines.append(f"  Value Accuracy:        {parse['value_accuracy'] * 100:.2f}%")
    lines.append(f"  Full Parsing Accuracy: {parse['parsing_accuracy'] * 100:.2f}%")
    lines.append("")
    lines.append("--- LAYER 4: STRUCTURE & HIERARCHY (OVER CONFIRMED ROWS) ---")
    lines.append(f"  Header-vs-Item Acc:    {struct['header_vs_item_accuracy'] * 100:.2f}%")
    lines.append(f"  Subtotal/Total Acc:    {struct['subtotal_total_accuracy'] * 100:.2f}%")
    lines.append(f"  Parent Chain Accuracy: {struct['parent_accuracy'] * 100:.2f}%")
    lines.append("")
    lines.append("--- LAYER 5: DOMAIN INVARIANTS (GROUND-TRUTH INDEPENDENT) ---")
    lines.append(f"  All Invariants Passed: {invars['all_passed']}")
    lines.append(f"  Tolerance per term:    ±{invars['tolerance_per_term']} unit(s)")
    lines.append("  Detailed Invariant Checks:")
    for c in invars.get("checks", []):
        status_sym = "PASS" if c["passed"] else "FAIL"
        lines.append(f"    [{status_sym}] {c['name']}")
        lines.append(f"           Calculated: {c['calculated']:,} | Reported: {c['reported']:,} | Diff: {c['difference']} (Max Tol: {c['max_allowed_tolerance']})")
        
    diag = align.get("diagnostics", {})
    if diag.get("splits") or diag.get("merges"):
        lines.append("")
        lines.append("--- DIAGNOSTICS: MERGES & SPLITS ---")
        if diag.get("splits"):
            lines.append(f"  Splits detected: {diag['splits']}")
        if diag.get("merges"):
            lines.append(f"  Merges detected: {diag['merges']}")
            
    lines.append("=" * 70)
    return "\n".join(lines)

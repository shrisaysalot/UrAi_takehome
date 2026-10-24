"""
Layered scoring engine for financial table parsing.
Computes evaluation metrics across multiple layers:
1. Alignment layer (Recall, Precision, Unresolved, Exact Label)
2. Extraction layer (Cell raw exact match over all GT cells)
3. Parsing layer (Status and value_in_unit over confirmed matching cells)
4. Structure layer (Header-vs-Item, Subtotal/Total, Parent hierarchy)
5. Invariants (Accounting integrity independent of ground truth)
"""

from typing import Any, Dict, List, Optional, Tuple
from eval.aligner import RowAligner, normalize_label


class TableScorer:
    def __init__(self, aligner: Optional[RowAligner] = None, tolerance_per_term: int = 1):
        self.aligner = aligner or RowAligner()
        self.tolerance_per_term = tolerance_per_term

    def score(
        self,
        gt_doc: Dict[str, Any],
        pred_doc: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculates all layered metrics between ground truth document and predicted document.
        """
        # Page-level Gate Check
        gt_tables = gt_doc.get("tables", [])
        pred_tables = pred_doc.get("tables", [])
        
        # Check text layer presence & basic validity
        if not pred_tables or len(pred_tables) == 0:
            return {
                "page_level_gate": "FAILED",
                "failure_reason": "No tables found in predicted document",
            }
            
        pred_table = pred_tables[0]
        gt_table = gt_tables[0] if gt_tables else {}
        
        pred_rows = pred_table.get("rows", [])
        gt_rows = gt_table.get("rows", [])
        
        pred_cols = pred_table.get("columns", [])
        gt_cols = gt_table.get("columns", [])
        
        if len(pred_rows) == 0:
            return {
                "page_level_gate": "FAILED",
                "failure_reason": "Predicted table contains 0 rows",
            }
            
        if len(pred_cols) != len(gt_cols) and len(gt_cols) > 0:
            return {
                "page_level_gate": "FAILED",
                "failure_reason": f"Column count mismatch: expected {len(gt_cols)}, got {len(pred_cols)}",
            }
            
        # 1. Alignment Layer
        alignment_res = self.aligner.align(gt_rows, pred_rows)
        pairings = alignment_res["pairings"]
        
        exact_cnt = alignment_res["exact"]
        fuzzy_cnt = alignment_res["fuzzy"]
        unres_cnt = alignment_res["unresolved"]
        drop_cnt = alignment_res["dropped"]
        ins_cnt = alignment_res["inserted"]
        confirmed_cnt = exact_cnt + fuzzy_cnt
        
        total_gt = len(gt_rows)
        total_pred = len(pred_rows)
        
        row_recall = confirmed_cnt / total_gt if total_gt > 0 else 0.0
        row_precision = confirmed_cnt / total_pred if total_pred > 0 else 0.0
        exact_label_acc = exact_cnt / total_gt if total_gt > 0 else 0.0
        
        # Build mapping for confirmed rows: gt_idx -> pred_idx
        # Also build pred_idx -> gt_idx mapping
        gt_to_pred_confirmed: Dict[int, int] = {}
        pred_to_gt_confirmed: Dict[int, int] = {}
        for p in pairings:
            if p["outcome"] in ("Exact", "Fuzzy") and p["pred_idx"] is not None:
                gt_to_pred_confirmed[p["gt_idx"]] = p["pred_idx"]
                pred_to_gt_confirmed[p["pred_idx"]] = p["gt_idx"]
                
        # 2. Extraction Layer: cell raw match over ALL GT cells
        # Denominator = total cells across all GT rows
        total_gt_cells = 0
        raw_matched_cells = 0
        
        # Track confirmed rows whose raw matched completely for parsing layer
        confirmed_rows_cell_matched: List[Tuple[int, int]] = []
        
        col_ids = [c["id"] for c in gt_cols]
        
        for g_idx, g_row in enumerate(gt_rows):
            g_cells = g_row.get("cells", {})
            for c_id in col_ids:
                if c_id in g_cells:
                    total_gt_cells += 1
                    # Check if this GT row was confirmed
                    if g_idx in gt_to_pred_confirmed:
                        p_idx = gt_to_pred_confirmed[g_idx]
                        p_cells = pred_rows[p_idx].get("cells", {})
                        if c_id in p_cells:
                            g_raw = g_cells[c_id].get("raw")
                            p_raw = p_cells[c_id].get("raw")
                            if g_raw == p_raw:
                                raw_matched_cells += 1
                                
        extraction_acc = raw_matched_cells / total_gt_cells if total_gt_cells > 0 else 0.0
        
        # 3. Parsing Layer: accuracy of status and value_in_unit
        # Denominator: cells in confirmed rows whose raw matched GT
        parsing_eligible_cells = 0
        status_matched_cells = 0
        value_matched_cells = 0
        both_matched_cells = 0
        
        for g_idx in gt_to_pred_confirmed:
            p_idx = gt_to_pred_confirmed[g_idx]
            g_cells = gt_rows[g_idx].get("cells", {})
            p_cells = pred_rows[p_idx].get("cells", {})
            
            for c_id in col_ids:
                if c_id in g_cells and c_id in p_cells:
                    g_c = g_cells[c_id]
                    p_c = p_cells[c_id]
                    # Only score parsing on cells where raw matched GT
                    if g_c.get("raw") == p_c.get("raw"):
                        parsing_eligible_cells += 1
                        s_match = (g_c.get("status") == p_c.get("status"))
                        v_match = (g_c.get("value_in_unit") == p_c.get("value_in_unit"))
                        if s_match:
                            status_matched_cells += 1
                        if v_match:
                            value_matched_cells += 1
                        if s_match and v_match:
                            both_matched_cells += 1
                            
        parsing_acc = both_matched_cells / parsing_eligible_cells if parsing_eligible_cells > 0 else 0.0
        status_acc = status_matched_cells / parsing_eligible_cells if parsing_eligible_cells > 0 else 0.0
        value_acc = value_matched_cells / parsing_eligible_cells if parsing_eligible_cells > 0 else 0.0
        
        # 4. Structure Layer: accuracy of type and parent_row_idx over confirmed rows
        # Denominator: confirmed rows count
        total_confirmed = len(gt_to_pred_confirmed)
        header_vs_item_correct = 0
        subtotal_total_correct = 0
        type_exact_correct = 0
        parent_correct = 0
        
        for g_idx, p_idx in gt_to_pred_confirmed.items():
            g_row = gt_rows[g_idx]
            p_row = pred_rows[p_idx]
            
            g_type = g_row.get("type")
            p_type = p_row.get("type")
            
            # (a) Header-vs-item
            g_is_header = (g_type == "header")
            p_is_header = (p_type == "header")
            if g_is_header == p_is_header:
                header_vs_item_correct += 1
                
            # (b) Subtotal/Total accuracy among non-headers
            if not g_is_header:
                g_is_sub_or_tot = g_type in ("subtotal", "total")
                p_is_sub_or_tot = p_type in ("subtotal", "total")
                if g_is_sub_or_tot == p_is_sub_or_tot:
                    subtotal_total_correct += 1
            else:
                # Headers naturally pass subtotal/total check
                subtotal_total_correct += 1
                
            if g_type == p_type:
                type_exact_correct += 1
                
            # Parent hierarchy check:
            # Map predicted parent_row_idx back to GT space via alignment
            g_parent = g_row.get("parent_row_idx")
            p_parent_idx = p_row.get("parent_row_idx")
            
            if g_parent is None and p_parent_idx is None:
                parent_correct += 1
            elif g_parent is not None and p_parent_idx is not None:
                # Map p_parent_idx to GT
                mapped_parent = pred_to_gt_confirmed.get(p_parent_idx)
                if mapped_parent == g_parent:
                    parent_correct += 1
                    
        header_item_acc = header_vs_item_correct / total_confirmed if total_confirmed > 0 else 0.0
        subtotal_total_acc = subtotal_total_correct / total_confirmed if total_confirmed > 0 else 0.0
        parent_acc = parent_correct / total_confirmed if total_confirmed > 0 else 0.0
        
        # 5. Invariants (no ground truth needed)
        invariants_res = self.check_invariants(pred_table)
        
        return {
            "page_level_gate": "PASSED",
            "alignment": {
                "confirmed": confirmed_cnt,
                "exact": exact_cnt,
                "fuzzy": fuzzy_cnt,
                "unresolved": unres_cnt,
                "dropped": drop_cnt,
                "inserted": ins_cnt,
                "row_recall": round(row_recall, 4),
                "row_precision": round(row_precision, 4),
                "exact_label_accuracy": round(exact_label_acc, 4),
                "total_alignment_cost": alignment_res["total_cost"],
                "diagnostics": alignment_res["diagnostics"],
                "pairings": pairings,
            },
            "extraction": {
                "total_gt_cells": total_gt_cells,
                "raw_matched_cells": raw_matched_cells,
                "cell_raw_accuracy": round(extraction_acc, 4),
            },
            "parsing": {
                "eligible_cells": parsing_eligible_cells,
                "both_matched": both_matched_cells,
                "status_matched": status_matched_cells,
                "value_matched": value_matched_cells,
                "parsing_accuracy": round(parsing_acc, 4),
                "status_accuracy": round(status_acc, 4),
                "value_accuracy": round(value_acc, 4),
            },
            "structure": {
                "confirmed_rows": total_confirmed,
                "header_vs_item_accuracy": round(header_item_acc, 4),
                "subtotal_total_accuracy": round(subtotal_total_acc, 4),
                "parent_accuracy": round(parent_acc, 4),
            },
            "invariants": invariants_res,
        }

    def check_invariants(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifies domain accounting invariants on predicted table data:
        1. 流動資産 + 固定資産 = 資産合計
        2. Section totals equal the sum of their items
        3. gross - 累計額 = 純額
        Tolerance = ±1 unit per summed term.
        """
        rows = table.get("rows", [])
        cols = [c["id"] for c in table.get("columns", [])]
        
        results: List[Dict[str, Any]] = []
        all_passed = True
        
        # Helper to find row by normalized label or type
        def find_rows_by_label(target: str) -> List[Tuple[int, Dict[str, Any]]]:
            norm_target = normalize_label(target)
            return [(i, r) for i, r in enumerate(rows) if normalize_label(r.get("label_raw")) == norm_target]
            
        def get_val(r: Dict[str, Any], c_id: str) -> Optional[int]:
            c = r.get("cells", {}).get(c_id, {})
            return c.get("value_in_unit")
            
        # Invariant 1: 流動資産合計 + 固定資産合計 = 資産合計
        r_current = find_rows_by_label("流動資産合計")
        r_fixed = find_rows_by_label("固定資産合計")
        r_total = find_rows_by_label("資産合計")
        
        if r_current and r_fixed and r_total:
            curr_row = r_current[0][1]
            fix_row = r_fixed[0][1]
            tot_row = r_total[0][1]
            
            for c_id in cols:
                v_curr = get_val(curr_row, c_id)
                v_fix = get_val(fix_row, c_id)
                v_tot = get_val(tot_row, c_id)
                
                if v_curr is not None and v_fix is not None and v_tot is not None:
                    calc_sum = v_curr + v_fix
                    diff = abs(calc_sum - v_tot)
                    # 2 terms summed -> max tolerance = 2 * tolerance_per_term
                    max_tol = 2 * self.tolerance_per_term
                    passed = (diff <= max_tol)
                    if not passed:
                        all_passed = False
                    results.append({
                        "name": f"Balance Sheet Identity (流動資産合計 + 固定資産合計 = 資産合計) [{c_id}]",
                        "calculated": calc_sum,
                        "reported": v_tot,
                        "difference": diff,
                        "max_allowed_tolerance": max_tol,
                        "passed": passed,
                    })
                    
        # Invariant 2: Pure net calculation (gross - 累計額 = 純額)
        # Using derived_from if available, or searching for （純額） rows
        for i, r in enumerate(rows):
            lbl = normalize_label(r.get("label_raw", ""))
            if "純額" in lbl and r.get("derived_from") and len(r.get("derived_from")) == 2:
                gross_idx, contra_idx = r["derived_from"][0], r["derived_from"][1]
                if gross_idx < len(rows) and contra_idx < len(rows):
                    gross_row = rows[gross_idx]
                    contra_row = rows[contra_idx]
                    for c_id in cols:
                        v_gross = get_val(gross_row, c_id)
                        v_contra = get_val(contra_row, c_id)
                        v_net = get_val(r, c_id)
                        if v_gross is not None and v_contra is not None and v_net is not None:
                            # Note: contra account is already negative (e.g. -1,923,585),
                            # so gross + contra = net, or gross - abs(contra) = net
                            expected_net = v_gross + v_contra if v_contra < 0 else v_gross - v_contra
                            diff = abs(expected_net - v_net)
                            max_tol = 2 * self.tolerance_per_term
                            passed = (diff <= max_tol)
                            if not passed:
                                all_passed = False
                            results.append({
                                "name": f"Net Asset Check ({r.get('label_raw')}) [{c_id}]",
                                "calculated": expected_net,
                                "reported": v_net,
                                "difference": diff,
                                "max_allowed_tolerance": max_tol,
                                "passed": passed,
                            })
                            
        # Invariant 3: Section totals with derived_from
        for i, r in enumerate(rows):
            if r.get("type") == "subtotal" and r.get("derived_from") and "純額" not in normalize_label(r.get("label_raw", "")):
                child_indices = r.get("derived_from", [])
                for c_id in cols:
                    child_vals = [get_val(rows[ci], c_id) for ci in child_indices if ci < len(rows) and get_val(rows[ci], c_id) is not None]
                    v_tot = get_val(r, c_id)
                    if child_vals and v_tot is not None:
                        calc_sum = sum(child_vals)
                        diff = abs(calc_sum - v_tot)
                        max_tol = len(child_vals) * self.tolerance_per_term
                        passed = (diff <= max_tol)
                        if not passed:
                            all_passed = False
                        results.append({
                            "name": f"Section Sum ({r.get('label_raw')}) [{c_id}]",
                            "calculated": calc_sum,
                            "reported": v_tot,
                            "difference": diff,
                            "max_allowed_tolerance": max_tol,
                            "passed": passed,
                        })
                        
        return {
            "all_passed": all_passed,
            "tolerance_per_term": self.tolerance_per_term,
            "checks_count": len(results),
            "checks": results,
        }

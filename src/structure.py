"""
Table Structure Classifier module.
Classifies row types (header, item, subtotal, total) using general keywords and suffixes,
builds hierarchical parent relationships adaptively via 1D indentation clustering,
and derives mathematical lineage (derived_from) dynamically using numeric sum and contra-asset relationships.
"""

from typing import Any, Dict, List, Optional, Tuple
from eval.aligner import normalize_label


class StructureClassifier:
    def __init__(self, tolerance_per_term: int = 1):
        self.tolerance_per_term = tolerance_per_term
        self.hierarchy_method = "adaptive_1d_indentation_clustering"

    def classify_and_link(
        self, rows: List[Dict[str, Any]], columns: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Classifies row types, establishes parent_row_idx, and computes derived_from adaptively.
        Returns: (rows, confidence_flags)
        """
        if not rows:
            return [], []

        flags: List[str] = []
        cols = [c["id"] for c in columns] if columns else (list(rows[0].get("cells", {}).keys()) if rows[0].get("cells") else ["c1", "c2"])

        # 1. Type classification: general suffixes and accounting concepts
        for r in rows:
            lbl = normalize_label(r.get("label_raw", ""))
            has_val = r.get("has_values", False) or bool(r.get("cells"))

            if not has_val:
                r["type"] = "header"
            elif lbl in ("資産合計", "負債及び純資産合計", "負債及び資本合計", "負債資本合計") or lbl.endswith("総計"):
                r["type"] = "total"
            elif "合計" in lbl or "小計" in lbl or "純額" in lbl or lbl.endswith("計"):
                r["type"] = "subtotal"
            else:
                r["type"] = "item"

        # 2. Adaptive 1D Indentation Clustering
        label_x0s = [r.get("label_x0") for r in rows if r.get("label_x0") is not None]
        if not label_x0s:
            flags.append("hierarchy_unavailable")
            for r in rows:
                r["parent_row_idx"] = None
                r["_indent_level"] = 0
        else:
            sorted_x = sorted(label_x0s)
            clusters: List[List[float]] = []
            curr = [sorted_x[0]]
            for x in sorted_x[1:]:
                # Group points within 3.5pt as belonging to the same visual column tier
                if x - (sum(curr) / len(curr)) > 3.5:
                    clusters.append(curr)
                    curr = [x]
                else:
                    curr.append(x)
            if curr:
                clusters.append(curr)

            cluster_centers = sorted([sum(c) / len(c) for c in clusters])

            # If all labels have essentially the same left-x (fewer than 2 tiers),
            # hierarchy cannot be determined reliably from indentation.
            if len(cluster_centers) < 2:
                flags.append("hierarchy_unavailable")
                for r in rows:
                    r["parent_row_idx"] = None
                    r["_indent_level"] = 0
            else:
                for r in rows:
                    x0 = r.get("label_x0", cluster_centers[0])
                    level = min(range(len(cluster_centers)), key=lambda k: abs(x0 - cluster_centers[k]))
                    r["_indent_level"] = level

                # Stack-based parent assignment
                header_stack: List[Tuple[int, int]] = []  # list of (indent_level, row_idx)

                for i, r in enumerate(rows):
                    lvl = r["_indent_level"]
                    lbl = normalize_label(r.get("label_raw", ""))

                    # Grand total: attached to level 0 category header
                    if r["type"] == "total":
                        lvl0_headers = [
                            idx for idx, row in enumerate(rows[:i])
                            if row.get("type") == "header" and row.get("_indent_level") == 0
                        ]
                        r["parent_row_idx"] = lvl0_headers[0] if lvl0_headers else (0 if i > 0 else None)
                        continue

                    # Contra accounts: e.g. 減価償却累計額 attached to the gross item right above it
                    if "減価償却累計額" in lbl and i > 0 and rows[i - 1]["type"] == "item":
                        r["parent_row_idx"] = i - 1
                        continue

                    # Net account row: belongs under the enclosing category header, not the contra account
                    if "純額" in lbl:
                        sec_parent = None
                        for plvl, pidx in reversed(header_stack):
                            if plvl <= lvl - 1 and rows[pidx]["type"] == "header":
                                sec_parent = pidx
                                break
                        r["parent_row_idx"] = sec_parent if sec_parent is not None else (header_stack[-1][1] if header_stack else None)
                        continue

                    # Standard indentation hierarchy: find nearest preceding row with strictly smaller level
                    while header_stack and header_stack[-1][0] >= lvl:
                        header_stack.pop()

                    if header_stack:
                        r["parent_row_idx"] = header_stack[-1][1]
                    else:
                        r["parent_row_idx"] = None

                    if r["type"] == "header":
                        header_stack.append((lvl, i))

        # 3. Dynamic Derived_from Computation via Numeric Relationships & Accounting Logic
        def get_val(row: Dict[str, Any], c_id: str) -> Optional[int]:
            return row.get("cells", {}).get(c_id, {}).get("value_in_unit")

        # (a) Net accounts: Gross minus Contra
        for i, r in enumerate(rows):
            lbl = normalize_label(r.get("label_raw", ""))
            r["derived_from"] = None

            if "純額" in lbl and i >= 2:
                # Preceding two items: gross at i-2, contra at i-1
                r["derived_from"] = [i - 2, i - 1]

        # (b) Section Totals and Grand Totals
        for i, r in enumerate(rows):
            if r["derived_from"] is not None:
                continue

            lbl = normalize_label(r.get("label_raw", ""))
            if r.get("type") not in ("subtotal", "total") and not any(s in lbl for s in ("合計", "小計", "計")):
                continue

            # Candidate Set 1: Preceding leaf items under the current section
            parent_h = r.get("parent_row_idx")
            start_pos = (parent_h + 1) if parent_h is not None else 0
            # Narrow start_pos to after previous subtotal if any
            for prev_idx in range(i - 1, start_pos - 1, -1):
                if rows[prev_idx].get("type") in ("subtotal", "total") and "純額" not in normalize_label(rows[prev_idx].get("label_raw", "")):
                    start_pos = prev_idx + 1
                    break

            # Contra and gross pairs that have been consolidated into a net row
            consolidated_indices = set()
            for ci in range(start_pos, i):
                if rows[ci].get("derived_from") and "純額" in normalize_label(rows[ci].get("label_raw", "")):
                    consolidated_indices.update(rows[ci]["derived_from"])

            candidate_items = []
            for ci in range(start_pos, i):
                if ci in consolidated_indices:
                    continue
                if rows[ci].get("type") in ("item", "subtotal") and rows[ci].get("cells"):
                    candidate_items.append(ci)

            # Candidate Set 2: Subtotals under this major category
            # (e.g. for 固定資産合計: 有形固定資産合計, 無形固定資産合計, 投資その他の資産合計)
            sec_start = parent_h if parent_h is not None else 0
            candidate_sec_subtotals = []
            for ci in range(sec_start, i):
                if rows[ci].get("type") == "subtotal" and "純額" not in normalize_label(rows[ci].get("label_raw", "")):
                    candidate_sec_subtotals.append(ci)

            # Candidate Set 3: Major section totals before row i (for grand total 資産合計)
            candidate_grand_totals = []
            for ci in range(i):
                if rows[ci].get("type") in ("subtotal", "total") and "純額" not in normalize_label(rows[ci].get("label_raw", "")):
                    # Top-level section totals (e.g. 流動資産合計, 固定資産合計)
                    if rows[ci].get("parent_row_idx") in (None, 0):
                        candidate_grand_totals.append(ci)

            # Check candidates using numeric sum relationships across columns
            matched = None
            candidate_options = [candidate_items]
            if candidate_sec_subtotals and len(candidate_sec_subtotals) >= 2:
                candidate_options.append(candidate_sec_subtotals)
            if candidate_grand_totals and len(candidate_grand_totals) >= 2:
                candidate_options.append(candidate_grand_totals)

            for candidates in candidate_options:
                if not candidates or len(candidates) < 2:
                    continue

                all_cols_match = True
                has_valid_col = False
                for c_id in cols:
                    tot_val = get_val(r, c_id)
                    if tot_val is None:
                        continue
                    # In accounting, nil cell (value is None) represents a balance of 0
                    child_vals = [
                        get_val(rows[ci], c_id) if get_val(rows[ci], c_id) is not None else 0
                        for ci in candidates
                    ]
                    calc_sum = sum(child_vals)
                    max_tol = len(candidates) * self.tolerance_per_term
                    if abs(calc_sum - tot_val) > max_tol:
                        all_cols_match = False
                        break
                    has_valid_col = True

                if all_cols_match and has_valid_col:
                    matched = candidates
                    break

            if matched:
                r["derived_from"] = matched
            elif candidate_items and len(candidate_items) >= 2 and any(s in lbl for s in ("合計", "小計", "計")):
                # Fallback to structural items under category if values are missing or nil
                r["derived_from"] = candidate_items

        # 4. Domain Invariants Verification (GT-independent)
        failed_invariants = []
        # Check Net asset relationships
        for i, r in enumerate(rows):
            if r.get("derived_from") and "純額" in normalize_label(r.get("label_raw", "")):
                g_idx, c_idx = r["derived_from"][0], r["derived_from"][1]
                if g_idx < len(rows) and c_idx < len(rows):
                    for c_id in cols:
                        vg = get_val(rows[g_idx], c_id)
                        vc = get_val(rows[c_idx], c_id)
                        vn = get_val(r, c_id)
                        if vg is not None and vc is not None and vn is not None:
                            exp_net = vg + vc if vc < 0 else vg - vc
                            if abs(exp_net - vn) > 2 * self.tolerance_per_term:
                                failed_invariants.append(f"Net Asset Check ({r.get('label_raw')}) [{c_id}]")

        # Check Subtotal sums
        for i, r in enumerate(rows):
            if r.get("type") in ("subtotal", "total") and r.get("derived_from") and "純額" not in normalize_label(r.get("label_raw", "")):
                child_indices = r.get("derived_from", [])
                for c_id in cols:
                    child_vals = [
                        get_val(rows[ci], c_id) if get_val(rows[ci], c_id) is not None else 0
                        for ci in child_indices if ci < len(rows)
                    ]
                    tot = get_val(r, c_id)
                    if child_vals and tot is not None:
                        calc_s = sum(child_vals)
                        if abs(calc_s - tot) > len(child_indices) * self.tolerance_per_term:
                            failed_invariants.append(f"Sum Check ({r.get('label_raw')}) [{c_id}]")

        if failed_invariants:
            flags.append(f"invariants_failed: {', '.join(failed_invariants[:3])}")

        # Clean up temporary fields
        for r in rows:
            r.pop("_indent_level", None)
            r.pop("has_values", None)
            r.pop("label_x0", None)

        return rows, flags

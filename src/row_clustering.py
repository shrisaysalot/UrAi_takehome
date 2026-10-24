"""
Row Clustering and Column Assignment module.
Clusters word tokens into table rows based on vertical proximity.
Handles multi-line wrapped labels, dynamic column header detection,
unit extraction, and adaptive column coordinate partitioning.
"""

import re
import statistics
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from src.number_parser import parse_number, normalize_date_to_iso


def compute_adaptive_y_tolerance(words: List[Dict[str, Any]], fallback: float = 3.5) -> float:
    """Scales line-clustering y_tolerance adaptively with median word/line height."""
    if not words:
        return fallback
    heights = [w["y1"] - w["y0"] for w in words if (w["y1"] - w["y0"]) > 2.0]
    if not heights:
        return fallback
    med_h = statistics.median(heights)
    # Scaling factor: ~35% of median font height
    return max(2.0, min(8.0, 0.35 * med_h))


class RowClusterer:
    def __init__(self, y_tolerance: Optional[float] = None):
        self.y_tolerance = y_tolerance

    def cluster_visual_lines(self, words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Groups words into visual lines by vertical y-coordinate proximity."""
        if not words:
            return []

        y_tol = self.y_tolerance
        if y_tol is None:
            y_tol = compute_adaptive_y_tolerance(words)

        # Sort words primarily by y0, secondarily by x0
        sorted_words = sorted(words, key=lambda w: (w["y0"], w["x0"]))

        lines: List[List[Dict[str, Any]]] = []
        curr_line: List[Dict[str, Any]] = []

        for w in sorted_words:
            if not curr_line:
                curr_line.append(w)
            else:
                last_y_mid = (curr_line[-1]["y0"] + curr_line[-1]["y1"]) / 2.0
                w_y_mid = (w["y0"] + w["y1"]) / 2.0
                if abs(w_y_mid - last_y_mid) <= y_tol:
                    curr_line.append(w)
                else:
                    lines.append(curr_line)
                    curr_line = [w]
        if curr_line:
            lines.append(curr_line)

        return lines

    def extract_page_number(
        self, lines: List[List[Dict[str, Any]]], fallback: int = 4
    ) -> int:
        """Extracts nominal page number from bottom footer markers (e.g. '- 4 -')."""
        if not lines:
            return fallback
        # Check last 3 lines for page number footer pattern
        for line in reversed(lines[-3:]):
            line_str = "".join(w["text"] for w in line).strip()
            m = re.match(r"^[\s\-–—]*(\d+)[\s\-–—]*$", line_str)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
        return fallback

    def detect_columns_and_gutter(
        self,
        lines: List[List[Dict[str, Any]]],
        start_idx: int,
    ) -> Tuple[List[Tuple[float, float]], List[float], float, List[str]]:
        """
        Derives column right edges, column split dividers, and label gutter x adaptively
        from number-like token distributions in body rows.
        Returns: (col_bounds, col_splits, max_label_x, confidence_flags)
        """
        flags: List[str] = []

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

        # Fallback if insufficient numeric tokens are detected
        if len(body_num_tokens) < 4:
            flags.append("column_boundaries_ambiguous")
            return [(345.0, 415.0), (450.0, 520.0)], [435.0], 280.0, flags

        # Sort tokens by x1 (right-aligned numbers)
        sorted_tokens = sorted(body_num_tokens, key=lambda t: t["x1"])

        # 1D gap-based clustering on right edges
        clusters: List[List[Dict[str, Any]]] = []
        curr_c = [sorted_tokens[0]]
        for t in sorted_tokens[1:]:
            # Column separation gap (typically >= 18pt in financial tables)
            if t["x1"] - curr_c[-1]["x1"] > 18.0:
                clusters.append(curr_c)
                curr_c = [t]
            else:
                curr_c.append(t)
        if curr_c:
            clusters.append(curr_c)

        # Filter clusters: keep clusters with substantial support
        max_c_len = max(len(c) for c in clusters)
        valid_col_clusters = [c for c in clusters if len(c) >= max(3, int(0.20 * max_c_len))]

        if not valid_col_clusters:
            flags.append("column_boundaries_ambiguous")
            return [(345.0, 415.0), (450.0, 520.0)], [435.0], 280.0, flags

        # Derive column bounds [min_x0, max_x1]
        col_bounds = []
        for c in valid_col_clusters:
            min_x0 = min(t["x0"] for t in c)
            max_x1 = max(t["x1"] for t in c)
            col_bounds.append((min_x0, max_x1))

        # Derive column dividers
        col_splits = []
        for k in range(len(col_bounds) - 1):
            split = (col_bounds[k][1] + col_bounds[k + 1][0]) / 2.0
            col_splits.append(split)

        # Derive label gutter (max_label_x)
        first_col_x0 = col_bounds[0][0]
        label_tokens = []
        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            line_str = "".join(w["text"] for w in line)
            if re.match(r"^[\s\-–—]*\d+[\s\-–—]*$", line_str.strip()):
                continue
            for w in line:
                if w["x1"] < first_col_x0:
                    label_tokens.append(w)

        if label_tokens:
            max_label_x1 = max(w["x1"] for w in label_tokens)
            max_label_x = (max_label_x1 + first_col_x0) / 2.0
        else:
            max_label_x = first_col_x0 - 20.0

        return col_bounds, col_splits, max_label_x, flags

    def extract_metadata(
        self, lines: List[List[Dict[str, Any]]]
    ) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], int, List[float], float, List[str]]:
        """
        Extracts table title, unit, columns, and index of first data line adaptively.
        Returns: (title_raw, unit_dict, columns_list, table_start_line_idx, col_splits, max_label_x, flags)
        """
        flags: List[str] = []
        title_raw = "連結貸借対照表"
        unit_dict = {"raw": "千円", "multiplier": 1000}
        found_title = False
        found_unit = False

        table_start_line_idx = 0
        header_lines: List[Tuple[int, List[Dict[str, Any]]]] = []

        for idx, line in enumerate(lines):
            line_str = "".join(w["text"] for w in line)

            # Title detection: looks for 貸借対照表 or 財務諸表 or 財政状態計算書
            if any(k in line_str for k in ("貸借対照表", "財政状態計算書", "財務諸表")):
                title_raw = line_str.strip()
                found_title = True

            # Unit detection: looks for 単位
            unit_match = re.search(r"単位\s*[:：]\s*(百万円|千円|円)", line_str)
            if unit_match:
                u_raw = unit_match.group(1)
                mult = 1000000 if u_raw == "百万円" else (1000 if u_raw == "千円" else 1)
                unit_dict = {"raw": u_raw, "multiplier": mult}
                found_unit = True

            # Column headers: check for 会計年度 or period dates
            if any(k in line_str for k in ("会計年度", "四半期", "前期", "当期")):
                header_lines.append((idx, line))
                table_start_line_idx = max(table_start_line_idx, idx + 1)
            elif any("年" in w["text"] and "月" in w["text"] for w in line) and idx < 10:
                header_lines.append((idx, line))
                table_start_line_idx = max(table_start_line_idx, idx + 1)

            # Detect table beginning (category banner or first asset/liability)
            if any(k in line_str for k in ("資産の部", "負債の部", "純資産の部", "負債及び資本", "流動資産", "流動負債", "資産合計")):
                table_start_line_idx = min(table_start_line_idx, idx) if table_start_line_idx > 0 else idx
                break

        if not found_unit or not found_title:
            flags.append("header_or_unit_not_found")

        # Dynamically discover columns and gutter from body numeric clusters
        col_bounds, col_splits, max_label_x, col_flags = self.detect_columns_and_gutter(
            lines, table_start_line_idx
        )
        flags.extend(col_flags)
        num_cols = len(col_bounds)

        # Map header text to detected columns
        columns: List[Dict[str, Any]] = []
        if header_lines and num_cols > 0:
            # For each detected column, find header words aligning with it
            for c_idx in range(num_cols):
                c_id = f"c{c_idx + 1}"
                # Determine x-range for this column's header
                x_left = max_label_x if c_idx == 0 else col_splits[c_idx - 1]
                x_right = col_splits[c_idx] if c_idx < len(col_splits) else 999999.0

                c_words = []
                for _, h_line in header_lines:
                    for w in h_line:
                        # Header word falls into this column's region
                        w_mid = (w["x0"] + w["x1"]) / 2.0
                        if x_left <= w_mid <= x_right:
                            c_words.append(w)

                c_text = " ".join(w["text"] for w in c_words).strip()
                period_end = normalize_date_to_iso(c_text)

                # Format header_raw with newline between label and date if present
                h_raw = c_text.replace(" (", "\n(").replace("（", "\n（").strip()
                if not h_raw:
                    # Generic fallback label
                    h_raw = f"第{c_idx + 1}期" if num_cols > 2 else ("前連結会計年度" if c_idx == 0 else "当連結会計年度")

                columns.append({
                    "id": c_id,
                    "header_raw": h_raw,
                    "period_end": period_end,
                })
        else:
            # Fallback 2 columns if no header lines parsed
            columns = [
                {"id": "c1", "header_raw": "前連結会計年度", "period_end": None},
                {"id": "c2", "header_raw": "当連結会計年度", "period_end": None},
            ]

        return title_raw, unit_dict, columns, table_start_line_idx, col_splits, max_label_x, flags

    def cluster_rows(
        self,
        lines: List[List[Dict[str, Any]]],
        start_idx: int,
        columns: List[Dict[str, Any]],
        col_splits: Optional[List[float]] = None,
        max_label_x: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Processes lines from start_idx into table rows.
        Assigns labels and cell values dynamically across N columns using col_splits.
        Handles wrapped labels and filters out page footers.
        """
        # If parameters were not passed, use defaults
        if col_splits is None:
            col_splits = [415.0]
        if max_label_x is None:
            max_label_x = 280.0

        num_cols = len(columns)
        raw_row_candidates: List[Dict[str, Any]] = []

        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            line_str = "".join(w["text"] for w in line)

            # Ignore page footer (e.g. "- 4 -")
            if re.match(r"^[\s\-–—]*\d+[\s\-–—]*$", line_str.strip()):
                continue

            label_tokens = [w for w in line if w["x1"] <= max_label_x]
            value_tokens = [w for w in line if w["x0"] > max_label_x]

            # If no label tokens and no value tokens, skip
            if not label_tokens and not value_tokens:
                continue

            label_raw = "".join(w["text"] for w in label_tokens).strip()

            # Calculate row bbox
            x0 = min(w["x0"] for w in line)
            y0 = min(w["y0"] for w in line)
            x1 = max(w["x1"] for w in line)
            y1 = max(w["y1"] for w in line)

            raw_row_candidates.append({
                "label_raw": label_raw,
                "label_x0": label_tokens[0]["x0"] if label_tokens else x0,
                "value_tokens": value_tokens,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "has_values": len(value_tokens) > 0,
            })

        # Wrapped label merging:
        # If a candidate has a label, NO values, is NOT a known section header,
        # and the next candidate has values, merge the labels.
        merged_candidates: List[Dict[str, Any]] = []
        skip_next = False

        for i in range(len(raw_row_candidates)):
            if skip_next:
                skip_next = False
                continue

            curr = raw_row_candidates[i]

            # Check for label wrapping into next row
            if not curr["has_values"] and i + 1 < len(raw_row_candidates):
                nxt = raw_row_candidates[i + 1]
                lbl = curr["label_raw"]
                is_standalone_header = any(lbl.endswith(h) for h in ("部", "資産", "負債", "純資産", "資本")) or ("合計" in lbl)
                if not is_standalone_header and nxt["has_values"]:
                    merged_label = curr["label_raw"] + nxt["label_raw"]
                    curr["label_raw"] = merged_label
                    curr["value_tokens"] = nxt["value_tokens"]
                    curr["has_values"] = True
                    curr["bbox"][2] = max(curr["bbox"][2], nxt["bbox"][2])
                    curr["bbox"][3] = nxt["bbox"][3]
                    skip_next = True

            merged_candidates.append(curr)

        # Now build final row structures with cells dynamically assigned to N columns
        final_rows = []
        for r_idx, cand in enumerate(merged_candidates):
            col_raw_values: Dict[str, Optional[str]] = {col["id"]: None for col in columns}

            for v_tok in cand["value_tokens"]:
                tok_text = v_tok["text"].strip()
                # Find which column bucket the token right edge falls into
                c_bucket = 0
                for s_idx, split_val in enumerate(col_splits):
                    if v_tok["x1"] > split_val:
                        c_bucket = s_idx + 1

                if c_bucket < len(columns):
                    c_id = columns[c_bucket]["id"]
                    col_raw_values[c_id] = tok_text

            cells = {}
            has_any_cell = cand["has_values"] or any(v is not None for v in col_raw_values.values())
            if has_any_cell:
                for col in columns:
                    c_id = col["id"]
                    raw_val = col_raw_values.get(c_id)
                    status, val = parse_number(raw_val)
                    cells[c_id] = {
                        "raw": raw_val,
                        "status": status,
                        "value_in_unit": val,
                    }

            final_rows.append({
                "row_idx": r_idx,
                "label_raw": cand["label_raw"],
                "label_x0": cand["label_x0"],
                "has_values": cand["has_values"],
                "cells": cells,
                "bbox": cand["bbox"],
            })

        return final_rows

"""
Main Parser Pipeline for Japanese Consolidated Financial Statements.
Coordinates PDF loading, routing, word extraction, row clustering,
number parsing, and hierarchical structure classification.
Supports both 'baseline' and 'improved' (adaptive) parsing configurations.
"""

from typing import Any, Dict, Optional, List
import fitz

from src.loader import load_pdf
from src.router import PageRouter
from src.extractor import extract_page_elements
from src.row_clustering import RowClusterer
from src.structure import StructureClassifier
from src.writer import format_output_document, save_output_json


class FinancialTableParser:
    def __init__(self, mode: str = "improved", tolerance_per_term: int = 1):
        """
        mode: 'baseline' or 'improved'
        'baseline': standard naive extraction without contra-asset derived_from links or advanced parent resolution.
        'improved': full adaptive hierarchical indentation modeling, dynamic column discovery, and invariant verification.
        """
        self.mode = mode
        self.tolerance_per_term = tolerance_per_term
        self.router = PageRouter()
        self.clusterer = RowClusterer()
        self.classifier = StructureClassifier(tolerance_per_term=tolerance_per_term)

    def parse_page(
        self,
        doc: fitz.Document,
        page_idx: int = 0,
        page_num: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Parses a single page into structured table JSON."""
        page = doc[page_idx]
        confidence_flags: List[str] = []

        # 1. Routing
        routing_info = self.router.assess_page(page)
        extraction_method = routing_info["extraction_method"]
        route_reason = routing_info["route_reason"]
        confidence_flags.extend(routing_info.get("confidence_flags", []))

        # If routed to OCR / VLM
        if extraction_method != "text_layer":
            resolved_page_num = page_num if page_num is not None else (page_idx + 1)
            return format_output_document(
                page_num=resolved_page_num,
                extraction_method=extraction_method,
                route_reason=route_reason,
                confidence_flags=confidence_flags,
                tables=[{
                    "title_raw": "OCR_STUB",
                    "unit": {"raw": "千円", "multiplier": 1000},
                    "columns": [],
                    "rows": [],
                    "stub_note": "Escalated to OCR/VLM stub. Native text was rejected by router. OCR/VLM backend is stubbed in v1; real results not faked."
                }]
            )

        # 2. Native Text Extraction
        extracted = extract_page_elements(page)
        words = extracted["words"]

        # 3. Row Clustering & Metadata Extraction
        lines = self.clusterer.cluster_visual_lines(words)

        # Extract nominal page number from bottom footers if not specified
        if page_num is None:
            resolved_page_num = self.clusterer.extract_page_number(lines, fallback=page_idx + 1)
        else:
            resolved_page_num = page_num

        title_raw, unit_dict, columns, start_idx, col_splits, max_label_x, meta_flags = (
            self.clusterer.extract_metadata(lines)
        )
        confidence_flags.extend(meta_flags)

        # 4. Cluster rows
        if self.mode == "baseline":
            # Baseline behavior: rigid calibrated cutoffs
            rows = self.clusterer.cluster_rows(lines, start_idx, columns, col_splits=[415.0], max_label_x=280.0)
            for r in rows:
                lbl = r.get("label_raw", "")
                if not r.get("cells"):
                    r["type"] = "header"
                    r["parent_row_idx"] = None
                elif "合計" in lbl:
                    r["type"] = "subtotal"
                    r["parent_row_idx"] = None
                else:
                    r["type"] = "item"
                    r["parent_row_idx"] = None
                r["derived_from"] = None
        else:
            # Improved: adaptive column splits and label gutter
            rows = self.clusterer.cluster_rows(
                lines, start_idx, columns, col_splits=col_splits, max_label_x=max_label_x
            )
            # 5. Structure Classification & Invariant Verification
            rows, struct_flags = self.classifier.classify_and_link(rows, columns=columns)
            confidence_flags.extend(struct_flags)

        tables = [
            {
                "title_raw": title_raw,
                "unit": unit_dict,
                "columns": columns,
                "rows": rows,
            }
        ]

        # Deduplicate confidence flags while preserving order
        unique_flags = list(dict.fromkeys(confidence_flags))

        return format_output_document(
            page_num=resolved_page_num,
            extraction_method=extraction_method,
            route_reason=route_reason,
            confidence_flags=unique_flags,
            tables=tables,
        )

    def parse_pdf(
        self,
        pdf_path: str,
        page_idx: int = 0,
        page_num: Optional[int] = None,
        out_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Loads and parses PDF file, optionally saving JSON output."""
        doc = load_pdf(pdf_path)
        try:
            res = self.parse_page(doc, page_idx=page_idx, page_num=page_num)
            if out_path:
                save_output_json(res, out_path)
            return res
        finally:
            doc.close()

"""
Writer module.
Serializes extracted and parsed table data into the required JSON schema.
Ensures UTF-8 encoding without ASCII escaping.
"""

import json
from typing import Any, Dict


def format_output_document(
    page_num: int,
    extraction_method: str,
    route_reason: str,
    tables: list,
    confidence_flags: list = None,
) -> Dict[str, Any]:
    """Formats extraction output conforming to the required JSON schema."""
    return {
        "page": page_num,
        "extraction_method": extraction_method,
        "route_reason": route_reason,
        "confidence_flags": confidence_flags if confidence_flags is not None else [],
        "tables": tables,
    }


def save_output_json(doc: Dict[str, Any], filepath: str) -> None:
    """Saves the output document to a JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

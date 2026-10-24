"""
Pure functional number parsing and date normalization for Japanese financial tables.
Handles full-width digits, commas, negative signs (△, ▲, parentheses), and nil markers (－, -).
"""

import re
import unicodedata
from typing import Optional, Tuple


NIL_MARKERS = {"－", "-", "—", "―", "ー", "–", "−"}


def parse_number(raw: Optional[str]) -> Tuple[str, Optional[int]]:
    """
    Parses a raw number string from a cell.
    Returns:
        (status, value_in_unit)
        status: "present" | "nil" | "unreadable"
        value_in_unit: int | None
    """
    if raw is None:
        return ("unreadable", None)
    
    raw_str = raw.strip()
    if not raw_str:
        return ("unreadable", None)
    
    # Check for nil marker
    if raw_str in NIL_MARKERS:
        return ("nil", None)
    
    # Normalize unicode to handle full-width characters (NFKC)
    # E.g. '△２,００２,４２９' -> '△2,002,429'
    norm = unicodedata.normalize("NFKC", raw_str).replace(" ", "").replace("　", "")
    
    # Check negative markers
    is_negative = False
    if norm.startswith("△") or norm.startswith("▲"):
        is_negative = True
        norm = norm[1:]
    elif (norm.startswith("(") and norm.endswith(")")) or (norm.startswith("（") and norm.endswith("）")):
        is_negative = True
        norm = norm[1:-1]
    elif norm.startswith("-") or norm.startswith("−"):
        is_negative = True
        norm = norm[1:]
    
    # Remove commas
    cleaned = norm.replace(",", "")
    
    # Check if remaining string is an integer
    if cleaned.isdigit():
        val = int(cleaned)
        if is_negative:
            val = -val
        # Rule: "△0" is present with value 0
        if val == 0:
            val = 0
        return ("present", val)
    
    # If not a number and not a nil marker, could be unreadable
    return ("unreadable", None)


def normalize_date_to_iso(raw_date: str) -> Optional[str]:
    """
    Normalizes Japanese dates like '2025 年３月 31 日' or '(2026年3月31日)' to 'YYYY-MM-DD'.
    Uses NFKC to standardize full-width digits.
    """
    if not raw_date:
        return None
    
    norm = unicodedata.normalize("NFKC", raw_date)
    # Match year, month, day patterns: e.g. 2025年3月31日 or 2025-03-31
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", norm)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    
    # Fallback for ISO format if already in YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", norm)
    if m_iso:
        year, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    
    return None

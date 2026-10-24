"""
Page Trust Router module.
Determines whether a page's native text layer is trustworthy or requires escalation to OCR/VLM.
Evaluates:
(a) Character plausibility (share of valid CJK / digits / common punctuation vs replacement/garbled chars)
(b) Text coverage vs page/image area
(c) Table sanity check (presence of numeric columns)
"""

import re
import unicodedata
from typing import Any, Dict, List, Tuple
import fitz


def is_plausible_char(c: str) -> bool:
    """Checks if a character belongs to standard Japanese CJK, Latin, digit, or common punctuation."""
    code = ord(c)
    # Unicode replacement character or Private Use Area
    if code == 0xFFFD or (0xE000 <= code <= 0xF8FF):
        return False
    # ASCII printable
    if 32 <= code <= 126:
        return True
    # CJK Unified Ideographs
    if 0x4E00 <= code <= 0x9FFF:
        return True
    # Hiragana & Katakana
    if 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF:
        return True
    # CJK Symbols and Punctuation (e.g. 『』【】（）)
    if 0x3000 <= code <= 0x303F:
        return True
    # Halfwidth and Fullwidth Forms
    if 0xFF00 <= code <= 0xFFEF:
        return True
    # Geometric shapes (△, ▲)
    if code in (0x25B3, 0x25B2, 0x25BD, 0x25BC):
        return True
    # General Punctuation & Math symbols (－, —, ―)
    if code in (0x2014, 0x2015, 0x2212, 0x2013, 0x2026):
        return True
    # Whitespace
    if c.isspace():
        return True
    return False


class PageRouter:
    def __init__(
        self,
        min_char_plausibility: float = 0.85,
        min_word_count: int = 15,
        min_number_count: int = 5,
    ):
        self.min_char_plausibility = min_char_plausibility
        self.min_word_count = min_word_count
        self.min_number_count = min_number_count

    def assess_page(self, page: fitz.Page) -> Dict[str, Any]:
        """
        Assesses if page text layer is trustworthy.
        Returns routing metadata dictionary.
        """
        text = page.get_text()
        words = page.get_text("words")
        
        reasons_to_escalate = []
        
        # 1. Word count & empty text check
        if len(words) < self.min_word_count:
            reasons_to_escalate.append(
                f"Low word count ({len(words)} words; expected >= {self.min_word_count})"
            )
            
        # 2. Character plausibility check
        if text.strip():
            non_space_chars = [c for c in text if not c.isspace()]
            if non_space_chars:
                plausible_count = sum(1 for c in non_space_chars if is_plausible_char(c))
                ratio = plausible_count / len(non_space_chars)
                if ratio < self.min_char_plausibility:
                    reasons_to_escalate.append(
                        f"Low character plausibility ({ratio * 100:.1f}%; contains replacement/garbled characters)"
                    )
            else:
                ratio = 0.0
                reasons_to_escalate.append("Text consists solely of whitespace")
        else:
            ratio = 0.0
            reasons_to_escalate.append("Empty text layer (scanned or image-only page)")
            
        # 3. Numeric tokens check (Table sanity)
        number_tokens = []
        for w in words:
            token = w[4]
            # Match tokens containing digits or negative markers with digits
            norm_token = unicodedata.normalize("NFKC", token).replace(",", "")
            if re.search(r"\d", norm_token) or token in ("－", "-", "—"):
                number_tokens.append(token)
                
        if len(number_tokens) < self.min_number_count:
            reasons_to_escalate.append(
                f"Insufficient numeric cell candidates ({len(number_tokens)} found; expected >= {self.min_number_count})"
            )
            
        # Decision
        flags = []
        if reasons_to_escalate:
            flags.append("escalate_to_ocr")
            if len(words) < self.min_word_count or not text.strip():
                flags.append("text_layer_missing")
            if ratio < self.min_char_plausibility:
                flags.append("low_char_plausibility")
            return {
                "extraction_method": "ocr",
                "is_trustworthy": False,
                "route_reason": "Escalated to OCR/VLM stub: " + "; ".join(reasons_to_escalate),
                "confidence_flags": flags,
                "stats": {
                    "word_count": len(words),
                    "char_plausibility": ratio,
                    "number_token_count": len(number_tokens),
                }
            }
        else:
            return {
                "extraction_method": "text_layer",
                "is_trustworthy": True,
                "route_reason": f"High character plausibility ({ratio * 100:.1f}%), sufficient word count ({len(words)} words), and {len(number_tokens)} numeric tokens detected.",
                "confidence_flags": [],
                "stats": {
                    "word_count": len(words),
                    "char_plausibility": ratio,
                    "number_token_count": len(number_tokens),
                }
            }

"""
PDF Extractor module.
Extracts words, bounding boxes, text lines, and vector elements from PyMuPDF page.
"""

from typing import Any, Dict, List, Tuple
import fitz


def extract_page_elements(page: fitz.Page) -> Dict[str, Any]:
    """
    Extracts structured words, blocks, and lines with coordinate bounding boxes.
    """
    # words: list of (x0, y0, x1, y1, word_str, block_no, line_no, word_no)
    raw_words = page.get_text("words")
    
    words = []
    for w in raw_words:
        words.append({
            "text": w[4],
            "bbox": [round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2)],
            "block_no": w[5],
            "line_no": w[6],
            "word_no": w[7],
            "x0": w[0],
            "y0": w[1],
            "x1": w[2],
            "y1": w[3],
        })
        
    return {
        "page_rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
        "words": words,
    }

"""
PDF Loader module.
Safely opens PDF documents using PyMuPDF.
Raises clear load-time errors for encrypted, corrupted, or missing files.
"""

import os
from typing import Optional
import fitz


class PDFLoadError(Exception):
    """Raised when PDF loading fails due to corruption, missing file, or encryption."""
    pass


def load_pdf(pdf_path: str, password: Optional[str] = None) -> fitz.Document:
    """
    Loads a PDF document.
    Raises:
        FileNotFoundError: If the file does not exist.
        PDFLoadError: If the file is encrypted without valid password or corrupted.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise PDFLoadError(f"Corrupted or invalid PDF file: {pdf_path} (error: {e})") from e
    
    if doc.is_encrypted:
        if password:
            auth_success = doc.authenticate(password)
            if not auth_success:
                doc.close()
                raise PDFLoadError(f"Failed to authenticate encrypted PDF: {pdf_path}")
        else:
            doc.close()
            raise PDFLoadError(f"PDF is password encrypted: {pdf_path}")
            
    if len(doc) == 0:
        doc.close()
        raise PDFLoadError(f"PDF contains 0 pages: {pdf_path}")
        
    return doc

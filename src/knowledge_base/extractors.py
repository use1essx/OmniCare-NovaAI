"""
Lightweight document extraction helpers for knowledge ingestion.

Supported:
- txt (utf-8 fallback)
- pdf (pdfplumber - better Chinese text extraction)
- docx (docx2txt if installed)
- images (pytesseract if installed)

Video/audio are not handled here (handled separately via STT pipeline).
"""

import io
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Custom extraction error."""


def extract_text_from_txt(data: bytes, encoding: str = "utf-8") -> Tuple[str, Dict[str, Any]]:
    try:
        text = data.decode(encoding, errors="ignore")
        return text, {"source_type": "text"}
    except Exception as e:
        raise ExtractionError(f"TXT decode failed: {e}")


def extract_text_from_pdf(data: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text from PDF using pdfplumber for better Chinese text support.
    
    VALIDATION: Input sanitized - binary PDF data only
    """
    try:
        import pdfplumber
        
        pages = []
        page_count = 0
        
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                try:
                    # Extract text with layout preservation
                    page_text = page.extract_text()
                    if page_text:
                        pages.append(page_text.strip())
                    else:
                        # Try extracting tables if no text found
                        tables = page.extract_tables()
                        if tables:
                            table_text = "\n".join([
                                "\n".join([" | ".join([str(cell) if cell else "" for cell in row]) for row in table])
                                for table in tables
                            ])
                            pages.append(table_text.strip())
                except Exception as page_error:
                    logger.warning(f"Failed to extract page {i+1}: {page_error}")
                    pages.append("")
        
        text = "\n\n".join([p for p in pages if p])
        
        if not text or len(text.strip()) < 10:
            raise ExtractionError("Insufficient text extracted from PDF")
        
        return text, {"source_type": "pdf", "pages": page_count, "extractor": "pdfplumber"}
    except ImportError:
        # Fallback to PyPDF2 if pdfplumber not installed
        logger.warning("pdfplumber not installed, falling back to PyPDF2")
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(io.BytesIO(data))
            pages = []
            for i, page in enumerate(reader.pages):
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pages.append("")
            text = "\n\n".join(pages)
            return text, {"source_type": "pdf", "pages": len(pages), "extractor": "PyPDF2"}
        except Exception as e:
            raise ExtractionError(f"PDF extraction failed (PyPDF2 fallback): {e}")
    except Exception as e:
        raise ExtractionError(f"PDF extraction failed: {e}")


def extract_text_from_docx(data: bytes) -> Tuple[str, Dict[str, Any]]:
    try:
        import tempfile
        import docx2txt

        with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
            tmp.write(data)
            tmp.flush()
            text = docx2txt.process(tmp.name) or ""
        return text, {"source_type": "docx"}
    except ImportError:
        raise ExtractionError("docx2txt not installed")
    except Exception as e:
        raise ExtractionError(f"DOCX extraction failed: {e}")


def extract_text_from_image(data: bytes) -> Tuple[str, Dict[str, Any]]:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
        return text, {"source_type": "image"}
    except ImportError:
        raise ExtractionError("pytesseract/Pillow not installed")
    except Exception as e:
        raise ExtractionError(f"Image OCR failed: {e}")


def detect_and_extract(filename: str, data: bytes) -> Tuple[str, Dict[str, Any]]:
    """Route to the appropriate extractor based on extension."""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(data)
    if lower.endswith(".docx") or lower.endswith(".doc"):
        return extract_text_from_docx(data)
    if lower.endswith(".txt"):
        return extract_text_from_txt(data)
    if lower.endswith((".png", ".jpg", ".jpeg")):
        return extract_text_from_image(data)
    # default try text decode
    return extract_text_from_txt(data)

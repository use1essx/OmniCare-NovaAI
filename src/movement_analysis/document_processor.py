"""
Healthcare AI V2 - Document Processor
Handles PDF and DOCX document text extraction for assessment rules
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_docx_text(doc_path: str, max_chars: int = 4000) -> str:
    """
    Extract text from DOCX file
    
    Args:
        doc_path: Path to DOCX file
        max_chars: Maximum characters to extract
        
    Returns:
        Extracted text string
    """
    if not Path(doc_path).exists():
        logger.warning(f"DOCX file not found: {doc_path}")
        return ""
    
    try:
        from docx import Document
        
        document = Document(doc_path)
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
            logger.info(f"Truncated DOCX text to {max_chars} characters")
        
        logger.info(f"Extracted {len(text)} characters from DOCX: {doc_path}")
        return text
        
    except ImportError:
        logger.error("python-docx not installed. Install with: pip install python-docx")
        return ""
    except Exception as e:
        logger.error(f"Failed to extract DOCX text: {e}")
        return ""


def extract_pdf_text(pdf_path: str, max_chars: int = 4000) -> str:
    """
    Extract text from PDF file
    
    Args:
        pdf_path: Path to PDF file
        max_chars: Maximum characters to extract
        
    Returns:
        Extracted text string
    """
    if not Path(pdf_path).exists():
        logger.warning(f"PDF file not found: {pdf_path}")
        return ""
    
    try:
        import PyPDF2
        
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)
                
                # Check if we've reached max_chars
                if max_chars and sum(len(t) for t in text_parts) >= max_chars:
                    break
        
        full_text = "\n".join(text_parts)
        
        if max_chars and len(full_text) > max_chars:
            full_text = full_text[:max_chars]
            logger.info(f"Truncated PDF text to {max_chars} characters")
        
        logger.info(f"Extracted {len(full_text)} characters from PDF: {pdf_path}")
        return full_text
        
    except ImportError:
        logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
        return ""
    except Exception as e:
        logger.error(f"Failed to extract PDF text: {e}")
        return ""


def extract_document_text(file_path: str, max_chars: int = 4000) -> str:
    """
    Auto-detect file type and extract text
    
    Args:
        file_path: Path to document file
        max_chars: Maximum characters to extract
        
    Returns:
        Extracted text string
    """
    path = Path(file_path)
    
    if not path.exists():
        logger.warning(f"Document file not found: {file_path}")
        return ""
    
    ext = path.suffix.lower()
    
    if ext == '.docx':
        return extract_docx_text(file_path, max_chars)
    elif ext == '.pdf':
        return extract_pdf_text(file_path, max_chars)
    else:
        logger.warning(f"Unsupported document type: {ext}")
        return ""


def is_document_supported(filename: str) -> bool:
    """
    Check if document type is supported
    
    Args:
        filename: Name of the file
        
    Returns:
        True if supported, False otherwise
    """
    ext = Path(filename).suffix.lower()
    return ext in ['.pdf', '.docx']

"""Document extraction and resume structuring."""

from __future__ import annotations

from resume_analyzer.parsing.document import (
    ExtractedDocument,
    extract_docx_text,
    extract_document,
    extract_pdf_text,
    validate_upload,
)

__all__ = [
    "ExtractedDocument",
    "extract_docx_text",
    "extract_document",
    "extract_pdf_text",
    "validate_upload",
]

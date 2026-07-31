"""Backwards-compatible facade over :mod:`resume_analyzer.parsing.document`.

The original v1 contract is preserved exactly: ``extract_text`` returns a
string and returns ``""`` instead of raising, so legacy callers keep working.
"""

from __future__ import annotations

from typing import Any

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.exceptions import ResumeAnalyzerError
from resume_analyzer.parsing.document import (
    extract_docx_text,
    extract_document,
    extract_pdf_text,
)

logger = get_logger(__name__)

__all__ = ["extract_text", "extract_pdf", "extract_docx", "extract_document"]


def extract_pdf(file: Any) -> str:
    """Extract plain text from a PDF file object."""
    text, _pages, _warnings = extract_pdf_text(file)
    return text


def extract_docx(file: Any) -> str:
    """Extract plain text from a DOCX file object."""
    text, _blocks, _warnings = extract_docx_text(file)
    return text


def extract_text(file: Any) -> str:
    """Extract text from an uploaded resume.

    Args:
        file: Streamlit ``UploadedFile`` or file-like object with a ``name``.

    Returns:
        The extracted text, or an empty string when the document is
        unsupported or unreadable (legacy v1 behaviour).
    """
    try:
        return extract_document(file).text
    except ResumeAnalyzerError as exc:
        logger.info("extract_text returning empty string: %s", exc)
        return ""

"""Presentation layer.

This is the only package permitted to import Streamlit. Everything below it
stays framework-agnostic so the core remains reusable and testable.
"""

from __future__ import annotations

from resume_analyzer.ui.theme import PALETTE, build_css, score_color

__all__ = ["PALETTE", "build_css", "score_color"]

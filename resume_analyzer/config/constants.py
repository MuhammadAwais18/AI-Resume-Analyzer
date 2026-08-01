"""Named constants shared across the application.

Centralising these values removes magic numbers from the business logic and
gives every threshold a single, documented source of truth.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Files & uploads
# --------------------------------------------------------------------------

#: File extensions the resume parser knows how to read.
SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = (".pdf", ".docx")

#: Largest upload accepted before the request is rejected (bytes).
MAX_UPLOAD_BYTES: Final[int] = 10 * 1024 * 1024

#: Below this character count a document is treated as unreadable/scanned.
MIN_MEANINGFUL_TEXT_LENGTH: Final[int] = 80

#: Hard cap on the amount of resume text forwarded to the language model.
MAX_TEXT_CHARS_FOR_LLM: Final[int] = 14_000

#: Characters shown in the in-app resume preview panel.
RESUME_PREVIEW_CHARS: Final[int] = 2_500


# --------------------------------------------------------------------------
# Scoring thresholds
# --------------------------------------------------------------------------

#: An overall score at or above this value is an excellent match.
SCORE_EXCELLENT: Final[int] = 80

#: An overall score at or above this value is a good match.
SCORE_GOOD: Final[int] = 60

#: An overall score at or above this value is a partial match.
SCORE_FAIR: Final[int] = 40

#: Fuzzy string ratio above which two skill names are considered the same.
FUZZY_MATCH_THRESHOLD: Final[float] = 0.87


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------

#: Brand palette, reused by charts, the PDF report and the Streamlit theme.
COLOR_PRIMARY: Final[str] = "#6366F1"
COLOR_SECONDARY: Final[str] = "#8B5CF6"
COLOR_ACCENT: Final[str] = "#06B6D4"
COLOR_SUCCESS: Final[str] = "#10B981"
COLOR_WARNING: Final[str] = "#F59E0B"
COLOR_DANGER: Final[str] = "#EF4444"
COLOR_INK: Final[str] = "#0F172A"
COLOR_MUTED: Final[str] = "#64748B"

#: Number of history rows rendered in the dashboard by default.
HISTORY_PAGE_SIZE: Final[int] = 10

"""Backwards-compatible facade over :mod:`resume_analyzer.analytics`.

Retained so existing imports (``from utils.stats import resume_statistics``)
keep working. New code should use the package API directly.
"""

from __future__ import annotations

from resume_analyzer.analytics.statistics import compute_statistics

__all__ = ["resume_statistics", "compute_statistics"]


def resume_statistics(text: str) -> dict[str, int]:
    """Return the classic ``{"Words", "Characters", "Sentences"}`` mapping.

    Args:
        text: Raw resume text.

    Returns:
        Dictionary with the three legacy statistic keys.
    """
    return compute_statistics(text).as_legacy_dict()

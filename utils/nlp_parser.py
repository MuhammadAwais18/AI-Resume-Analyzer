"""Backwards-compatible facade over :mod:`resume_analyzer.parsing`.

v1 loaded the spaCy model at import time and then never used the resulting
document, which made the whole application fail to start when the model was
missing. The pipeline is now loaded lazily by the parsing layer.

The returned dictionary keeps its original five keys so existing callers are
unaffected.
"""

from __future__ import annotations

from typing import Any

from resume_analyzer.parsing.resume_parser import parse_resume

__all__ = ["extract_resume_info"]


def extract_resume_info(text: str) -> dict[str, Any]:
    """Extract the legacy resume information dictionary.

    Args:
        text: Raw resume or job description text.

    Returns:
        Mapping with ``email``, ``phone``, ``skills``, ``education`` and
        ``experience`` keys, matching the original v1 contract.
    """
    profile = parse_resume(text)

    education = (
        str(profile.education[0].degree) if profile.education else "Not Found"
    )
    if profile.total_experience_years:
        years = profile.total_experience_years
        rendered = int(years) if float(years).is_integer() else round(years, 1)
        experience = f"{rendered} years"
    else:
        experience = "Not Found"

    return {
        "email": profile.contact.email or "",
        "phone": profile.contact.phone or "",
        "skills": profile.skill_names,
        "education": education,
        "experience": experience,
    }

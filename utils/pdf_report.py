"""Backwards-compatible facade over :mod:`resume_analyzer.reporting`.

v1 exposed ``generate_pdf(score, stats, matched, missing, feedback)`` and
returned PDF bytes. That signature is preserved: the loose arguments are
adapted into the domain objects the new renderer expects, so old callers get
the upgraded report without any change.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import (
    AIReview,
    AnalysisResult,
    ATSResult,
    JobRequirements,
    ResumeProfile,
    ResumeStatistics,
    Skill,
)
from resume_analyzer.reporting.pdf_report import build_report

logger = get_logger(__name__)

__all__ = ["generate_pdf", "build_report"]


def _to_statistics(stats: Mapping[str, Any] | None) -> ResumeStatistics:
    """Adapt the legacy statistics dictionary onto the domain model."""
    data = dict(stats or {})
    return ResumeStatistics(
        words=int(data.get("Words", 0) or 0),
        characters=int(data.get("Characters", 0) or 0),
        sentences=int(data.get("Sentences", 0) or 0),
    )


def _to_skills(names: Iterable[Any] | None) -> list[Skill]:
    """Adapt plain skill names onto :class:`Skill` objects."""
    return [
        item if isinstance(item, Skill) else Skill(name=str(item))
        for item in (names or [])
        if str(item).strip()
    ]


def generate_pdf(
    score: float,
    stats: Mapping[str, Any] | None,
    matched: Iterable[Any] | None,
    missing: Iterable[Any] | None,
    feedback: str = "",
) -> bytes:
    """Generate the PDF report from legacy v1 arguments.

    Args:
        score: Overall ATS score.
        stats: Legacy statistics mapping.
        matched: Matched skill names.
        missing: Missing skill names.
        feedback: AI feedback rendered as markdown.

    Returns:
        The report as PDF bytes.
    """
    matched_skills = _to_skills(matched)
    missing_skills = _to_skills(missing)

    ats = ATSResult(
        overall_score=float(score),
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        missing_required_skills=missing_skills,
    )
    ats.recruiter_verdict = (
        f"Overall ATS match of {float(score):.0f}/100 "
        f"({ats.match_level.value.lower()})."
    )

    review = AIReview(raw_markdown=feedback or "", executive_summary="") if feedback else None
    if review is not None:
        review.ats_review = feedback.strip()[:1800]

    result = AnalysisResult(
        resume_name="Resume",
        profile=ResumeProfile(),
        requirements=JobRequirements(),
        ats=ats,
        statistics=_to_statistics(stats),
        review=review,
    )
    return build_report(result)

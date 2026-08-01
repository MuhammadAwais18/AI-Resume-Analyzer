"""Backwards-compatible facade over :mod:`resume_analyzer.ai`.

v1 exposed ``analyze_resume(resume_text, job_description) -> str`` and returned
error strings such as ``"AI Error: ..."`` on failure. That contract is kept,
but failures now yield a useful deterministic review instead of a raw
exception message.

The environment variables (``OPENAI_API_KEY``, ``OPENAI_BASE_URL``, ``MODEL``)
and the OpenAI-compatible client are unchanged.
"""

from __future__ import annotations

from resume_analyzer.ai.reviewer import request_review, review_to_markdown
from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import score_resume
from resume_analyzer.scoring.job_parser import parse_job_description

__all__ = ["analyze_resume"]


def analyze_resume(resume_text: str, job_description: str) -> str:
    """Generate an AI resume review rendered as markdown.

    Args:
        resume_text: Raw resume text.
        job_description: Raw job description text.

    Returns:
        Markdown review. Never raises: provider failures fall back to a
        deterministic review derived from the local ATS analysis.
    """
    profile = parse_resume(resume_text)
    requirements = parse_job_description(job_description)
    ats = score_resume(profile, requirements)
    review = request_review(
        resume_text, job_description, profile, requirements, ats
    )
    return review_to_markdown(review)

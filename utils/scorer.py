"""Backwards-compatible facade over :mod:`resume_analyzer.scoring`.

v1 exposed three functions that each re-parsed both documents (six parses per
analysis). The heavy lifting now happens once behind an LRU cache, so these
helpers stay cheap while returning the same shapes as before.
"""

from __future__ import annotations

from functools import lru_cache

from resume_analyzer.domain.models import ATSResult, JobRequirements, ResumeProfile
from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import score_resume
from resume_analyzer.scoring.job_parser import parse_job_description

__all__ = ["calculate_score", "matched_skills", "missing_skills", "analyze"]


@lru_cache(maxsize=8)
def _analyze_cached(
    resume_text: str, job_description: str
) -> tuple[ResumeProfile, JobRequirements, ATSResult]:
    """Parse and score a resume/job pair, memoised on the text inputs."""
    profile = parse_resume(resume_text)
    requirements = parse_job_description(job_description)
    return profile, requirements, score_resume(profile, requirements)


def analyze(
    resume_text: str, job_description: str
) -> tuple[ResumeProfile, JobRequirements, ATSResult]:
    """Return the parsed profile, requirements and ATS result for a pair."""
    return _analyze_cached(resume_text, job_description)


def calculate_score(resume_text: str, job_description: str) -> int:
    """Return the overall ATS match score as an integer percentage."""
    if not resume_text.strip() or not job_description.strip():
        return 0
    return _analyze_cached(resume_text, job_description)[2].rounded_score


def matched_skills(resume_text: str, job_description: str) -> list[str]:
    """Return the sorted names of job skills present in the resume."""
    if not resume_text.strip() or not job_description.strip():
        return []
    _profile, _requirements, result = _analyze_cached(resume_text, job_description)
    return sorted(skill.name for skill in result.matched_skills)


def missing_skills(resume_text: str, job_description: str) -> list[str]:
    """Return the sorted names of job skills absent from the resume."""
    if not resume_text.strip() or not job_description.strip():
        return []
    _profile, _requirements, result = _analyze_cached(resume_text, job_description)
    return sorted(skill.name for skill in result.missing_skills)

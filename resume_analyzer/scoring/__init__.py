"""ATS scoring engine, job description parsing and similarity metrics."""

from __future__ import annotations

from resume_analyzer.scoring.ats_engine import (
    DEFAULT_WEIGHTS,
    ScoringWeights,
    recruiter_readiness,
    resume_health_score,
    score_resume,
)
from resume_analyzer.scoring.job_parser import parse_job_description
from resume_analyzer.scoring.similarity import (
    keyword_coverage,
    semantic_similarity,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "ScoringWeights",
    "keyword_coverage",
    "parse_job_description",
    "recruiter_readiness",
    "resume_health_score",
    "score_resume",
    "semantic_similarity",
]

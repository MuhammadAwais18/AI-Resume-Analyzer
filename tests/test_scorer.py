"""Tests for the ATS scoring engine."""

from __future__ import annotations

import pytest

from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import (
    DEFAULT_WEIGHTS,
    ScoringWeights,
    recruiter_readiness,
    resume_health_score,
    score_resume,
)
from resume_analyzer.scoring.job_parser import parse_job_description
from resume_analyzer.scoring.similarity import keyword_coverage, semantic_similarity


@pytest.fixture
def scored(resume_text: str, job_text: str):
    profile = parse_resume(resume_text)
    requirements = parse_job_description(job_text)
    return profile, requirements, score_resume(profile, requirements)


def test_weights_form_convex_combination() -> None:
    DEFAULT_WEIGHTS.validate()


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError):
        ScoringWeights(required_skills=0.9, optional_skills=0.9).validate()


def test_score_within_bounds(scored) -> None:
    _profile, _requirements, ats = scored
    assert 0 <= ats.overall_score <= 100


def test_strong_candidate_scores_well(scored) -> None:
    _profile, _requirements, ats = scored
    assert ats.overall_score >= 60


def test_all_components_present(scored) -> None:
    _profile, _requirements, ats = scored
    names = {component.name for component in ats.components}
    assert names == {
        "Required Skills",
        "Preferred Skills",
        "Semantic Match",
        "Keyword Relevance",
        "Experience",
        "Education",
    }


def test_required_and_optional_skills_are_separated(job_text: str) -> None:
    requirements = parse_job_description(job_text)
    required = {skill.name for skill in requirements.required_skills}
    optional = {skill.name for skill in requirements.optional_skills}
    assert "Python" in required
    assert "Rust" in optional
    assert not required & optional


def test_missing_required_skills_detected(scored) -> None:
    _profile, _requirements, ats = scored
    missing = {skill.name for skill in ats.missing_skills}
    assert "Rust" in missing


def test_irrelevant_resume_scores_low(job_text: str) -> None:
    profile = parse_resume(
        "Pastry chef with 10 years in French patisserie. Skills: baking, plating."
    )
    ats = score_resume(profile, parse_job_description(job_text))
    assert ats.overall_score < 45


def test_empty_job_description_is_safe() -> None:
    profile = parse_resume("Python developer")
    ats = score_resume(profile, parse_job_description(""))
    assert 0 <= ats.overall_score <= 100


def test_weighted_skills_beat_raw_counts() -> None:
    """A resume with the high-weight required skill must beat a keyword-stuffed one."""
    job = "Must have strong experience with Kubernetes. Nice to have Excel and Jira."
    focused = score_resume(parse_resume("Kubernetes engineer"), parse_job_description(job))
    stuffed = score_resume(parse_resume("Excel Jira user"), parse_job_description(job))
    assert focused.overall_score > stuffed.overall_score


def test_experience_gap_reduces_score() -> None:
    job = "Must have Python. We require 10 years of experience."
    junior = score_resume(
        parse_resume("Python developer with 1 years of experience"),
        parse_job_description(job),
    )
    senior = score_resume(
        parse_resume("Python developer with 12 years of experience"),
        parse_job_description(job),
    )
    assert senior.overall_score > junior.overall_score


def test_recruiter_verdict_and_recommendations(scored) -> None:
    _profile, _requirements, ats = scored
    assert ats.recruiter_verdict
    assert isinstance(ats.recommendations, list)


def test_health_and_readiness_scores(scored) -> None:
    profile, _requirements, ats = scored
    health = resume_health_score(profile, 600)
    assert 0 <= health <= 100
    assert 0 <= recruiter_readiness(ats, health, profile) <= 100


def test_semantic_similarity_bounds(resume_text: str, job_text: str) -> None:
    assert 0.0 <= semantic_similarity(resume_text, job_text) <= 1.0
    assert semantic_similarity("", "") == 0.0


def test_identical_documents_are_highly_similar(resume_text: str) -> None:
    assert semantic_similarity(resume_text, resume_text) > 0.9


def test_keyword_coverage_bounds(resume_text: str, job_text: str) -> None:
    assert 0.0 <= keyword_coverage(resume_text, job_text) <= 1.0

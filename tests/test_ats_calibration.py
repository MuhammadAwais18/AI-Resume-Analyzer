"""Calibration tests for the ATS engine.

These tests encode the *behavioural contract* of the scoring engine — the
properties a commercial ATS must satisfy — rather than exact numbers, so the
engine can be tuned without churning the suite.
"""

from __future__ import annotations

import pytest

from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import (
    CRITICAL_COVERAGE_THRESHOLD,
    KNOCKOUT_SCORE_CEILING,
    score_resume,
)
from resume_analyzer.scoring.job_parser import parse_job_description

JOB = """Senior Backend Engineer. We require 5+ years of professional experience.
Must have strong experience with Python, Kubernetes, PostgreSQL, AWS and Docker.
Proficiency in building REST APIs is essential. Bachelor's degree required.
Nice to have: Terraform, Go, GraphQL. Familiarity with Rust is a bonus."""

PERFECT = """Senior Engineer, 8 years of experience. BSc Computer Science.
Skills: Python, Kubernetes, PostgreSQL, AWS, Docker, REST API, Terraform, Go,
GraphQL, Rust"""

STRONG = """Senior Engineer with 6 years of experience. Bachelor of Science in CS.
Skills: Python, Kubernetes, PostgreSQL, AWS, Docker, REST APIs"""

SYNONYMS_ONLY = """Senior Engineer with 6 years of experience. BSc Computer Science.
Skills: python3, k8s, postgres, amazon web services, containerization, restful api"""

PARTIAL = """Developer, 3 years of experience. BSc. Skills: Python, MySQL, Flask"""

UNRELATED = """Pastry chef, 10 years in French patisserie.
Skills: baking, plating, menu design."""


def _score(resume: str, job: str = JOB) -> float:
    return score_resume(parse_resume(resume), parse_job_description(job)).overall_score


@pytest.fixture(scope="module")
def scores() -> dict[str, float]:
    return {
        "perfect": _score(PERFECT),
        "strong": _score(STRONG),
        "synonyms": _score(SYNONYMS_ONLY),
        "partial": _score(PARTIAL),
        "unrelated": _score(UNRELATED),
    }


def test_scores_are_strictly_ordered(scores: dict[str, float]) -> None:
    """Better-fitting candidates must always outrank weaker ones."""
    assert scores["perfect"] > scores["strong"] > scores["partial"] > scores["unrelated"]


def test_ideal_candidate_reaches_excellent_band(scores: dict[str, float]) -> None:
    assert scores["perfect"] >= 80


def test_strong_candidate_reaches_good_band(scores: dict[str, float]) -> None:
    assert 60 <= scores["strong"] < 90


def test_unrelated_candidate_is_filtered_out(scores: dict[str, float]) -> None:
    assert scores["unrelated"] < 40


def test_synonym_only_resume_scores_comparably(scores: dict[str, float]) -> None:
    """A resume written with synonyms must not be unfairly penalised."""
    assert scores["synonyms"] >= scores["strong"] - 15
    assert scores["synonyms"] >= 55


def test_synonyms_match_the_same_skills() -> None:
    result = score_resume(parse_resume(SYNONYMS_ONLY), parse_job_description(JOB))
    matched = {skill.name for skill in result.matched_skills}
    assert {"Python", "Kubernetes", "PostgreSQL", "AWS"} <= matched


def test_knockout_rule_caps_capability_gaps() -> None:
    """Verbose prose must not lift a candidate who lacks the must-have skills."""
    verbose = (
        "Highly motivated senior backend engineer with proven experience "
        "delivering scalable production systems and REST services. " * 12
        + " 10 years of experience. Bachelor's degree in Computer Science."
    )
    assert _score(verbose) <= KNOCKOUT_SCORE_CEILING


def test_knockout_threshold_is_sane() -> None:
    assert 0.0 < CRITICAL_COVERAGE_THRESHOLD < 0.5


def test_required_skills_outweigh_optional_ones() -> None:
    job = "Must have Kubernetes. Nice to have Excel, Jira and Tableau."
    required_only = _score("Kubernetes platform engineer", job)
    optional_only = _score("Excel, Jira and Tableau power user", job)
    assert required_only > optional_only


def test_score_is_deterministic() -> None:
    assert _score(STRONG) == _score(STRONG)


def test_components_reconstruct_overall_score() -> None:
    """The weighted components must explain the headline number."""
    result = score_resume(parse_resume(STRONG), parse_job_description(JOB))
    reconstructed = sum(component.weighted_score for component in result.components)
    assert result.overall_score == pytest.approx(reconstructed, abs=0.05)


def test_every_component_is_explainable() -> None:
    result = score_resume(parse_resume(STRONG), parse_job_description(JOB))
    for component in result.components:
        assert component.detail
        assert 0 <= component.score <= 100

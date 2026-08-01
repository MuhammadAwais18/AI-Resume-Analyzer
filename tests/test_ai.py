"""Tests for the AI reviewer: parsing, validation and failure handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from resume_analyzer.ai import reviewer
from resume_analyzer.ai.prompts import build_review_prompt
from resume_analyzer.exceptions import AIResponseError
from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import score_resume
from resume_analyzer.scoring.job_parser import parse_job_description

VALID_PAYLOAD = """{
  "executive_summary": "Strong senior backend candidate.",
  "ats_review": "Passes keyword screening comfortably.",
  "strengths": ["Deep Kubernetes experience", "Quantified impact"],
  "weaknesses": ["No Rust exposure"],
  "missing_skills": ["Rust"],
  "improvements": ["Add a metrics-driven summary"],
  "recruiter_impression": "Would shortlist.",
  "interview_readiness": "Ready; revise system design.",
  "resume_rating": 8.5,
  "career_advice": ["Target platform engineering roles"]
}"""


@pytest.fixture
def analysis(resume_text: str, job_text: str):
    profile = parse_resume(resume_text)
    requirements = parse_job_description(job_text)
    return profile, requirements, score_resume(profile, requirements)


def _fake_client(content: str):
    """Build a stub client returning ``content`` from the chat endpoint."""
    message = SimpleNamespace(content=content)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    completions = SimpleNamespace(create=lambda **_kwargs: response)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------


def test_parses_plain_json() -> None:
    payload = reviewer._extract_json(VALID_PAYLOAD)
    assert payload["resume_rating"] == 8.5


def test_parses_fenced_json() -> None:
    payload = reviewer._extract_json(f"```json\n{VALID_PAYLOAD}\n```")
    assert payload["strengths"]


def test_parses_json_with_surrounding_prose() -> None:
    payload = reviewer._extract_json(f"Here you go:\n{VALID_PAYLOAD}\nHope that helps!")
    assert payload["executive_summary"]


def test_invalid_json_raises() -> None:
    with pytest.raises(AIResponseError):
        reviewer._extract_json("this is not json at all")


def test_empty_response_raises() -> None:
    with pytest.raises(AIResponseError):
        reviewer._extract_json("")


def test_rating_normalised_from_100_scale() -> None:
    assert reviewer._as_rating(85) == 8.5
    assert reviewer._as_rating("7.5/10") == 7.5
    assert reviewer._as_rating("garbage") == 0.0


def test_string_lists_are_coerced() -> None:
    assert reviewer._as_str_list("- one\n- two") == ["one", "two"]
    assert reviewer._as_str_list(None) == []
    assert reviewer._as_str_list(["a", "b"]) == ["a", "b"]


# --------------------------------------------------------------------------
# End-to-end behaviour with a stubbed provider
# --------------------------------------------------------------------------


def test_successful_review(monkeypatch, resume_text, job_text, analysis) -> None:
    profile, requirements, ats = analysis
    monkeypatch.setattr(reviewer, "_build_client", lambda: _fake_client(VALID_PAYLOAD))

    review = reviewer.request_review(resume_text, job_text, profile, requirements, ats)

    assert review.succeeded
    assert review.resume_rating == 8.5
    assert "Rust" in review.missing_skills


def test_missing_api_key_returns_fallback(monkeypatch, resume_text, job_text, analysis) -> None:
    profile, requirements, ats = analysis

    def _raise():
        from resume_analyzer.exceptions import AIConfigurationError

        raise AIConfigurationError("no key")

    monkeypatch.setattr(reviewer, "_build_client", _raise)
    review = reviewer.request_review(resume_text, job_text, profile, requirements, ats)

    assert review.is_fallback
    assert review.strengths
    assert review.error_message


def test_provider_failure_falls_back(monkeypatch, resume_text, job_text, analysis) -> None:
    profile, requirements, ats = analysis
    monkeypatch.setattr(reviewer, "_build_client", lambda: (_ for _ in ()).throw(
        TimeoutError("request timed out")
    ))
    monkeypatch.setattr(reviewer.time, "sleep", lambda _seconds: None)

    review = reviewer.request_review(resume_text, job_text, profile, requirements, ats)

    assert review.is_fallback
    assert review.improvements


def test_malformed_response_falls_back(monkeypatch, resume_text, job_text, analysis) -> None:
    profile, requirements, ats = analysis
    monkeypatch.setattr(reviewer, "_build_client", lambda: _fake_client("nonsense"))
    monkeypatch.setattr(reviewer.time, "sleep", lambda _seconds: None)

    review = reviewer.request_review(resume_text, job_text, profile, requirements, ats)
    assert review.is_fallback


def test_error_classification() -> None:
    from resume_analyzer.exceptions import AIRateLimitError, AITimeoutError

    assert isinstance(reviewer._classify(TimeoutError("timed out")), AITimeoutError)
    assert isinstance(reviewer._classify(Exception("429 rate limit")), AIRateLimitError)


def test_fallback_review_is_useful(analysis) -> None:
    profile, requirements, ats = analysis
    review = reviewer.build_fallback_review(profile, requirements, ats, "offline")

    assert review.executive_summary
    assert review.strengths
    assert review.recruiter_impression
    assert 0 <= review.resume_rating <= 10


def test_markdown_rendering(analysis) -> None:
    profile, requirements, ats = analysis
    markdown = reviewer.review_to_markdown(
        reviewer.build_fallback_review(profile, requirements, ats, "offline")
    )
    assert "### Executive Summary" in markdown
    assert "### Strengths" in markdown


def test_prompt_contains_grounding_data(resume_text, job_text, analysis) -> None:
    profile, requirements, ats = analysis
    prompt = build_review_prompt(resume_text, job_text, profile, requirements, ats)

    assert "ground truth" in prompt
    assert "JSON" in prompt
    assert "untrusted data" in prompt

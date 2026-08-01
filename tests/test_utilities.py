"""Tests for text utilities, statistics, services and legacy facades."""

from __future__ import annotations

import pytest

from resume_analyzer.analytics.statistics import compute_statistics
from resume_analyzer.exceptions import ValidationError
from resume_analyzer.services.analysis_service import (
    analyze_text,
    validate_job_description,
)
from resume_analyzer.utils_text import (
    content_tokens,
    count_action_verbs,
    count_bullets,
    count_quantified_achievements,
    normalize_whitespace,
    truncate,
    unique_preserving_order,
)

# --------------------------------------------------------------------------
# Text utilities
# --------------------------------------------------------------------------


def test_normalize_whitespace_collapses_noise() -> None:
    assert normalize_whitespace("a   b\r\n\n\n\nc  ") == "a b\n\nc"


def test_normalize_whitespace_handles_empty() -> None:
    assert normalize_whitespace("") == ""


def test_content_tokens_strip_stop_words() -> None:
    tokens = content_tokens("The engineer built the platform with Python")
    assert "the" not in tokens
    assert "python" in tokens


def test_counts() -> None:
    text = "- Increased revenue by 40%\n- Saved $1.2M\n- Shipped 3x faster"
    assert count_bullets(text) == 3
    assert count_quantified_achievements(text) >= 3
    assert count_action_verbs("Led and optimized and delivered") == 3


def test_truncate_respects_limit() -> None:
    assert len(truncate("word " * 500, 100)) < 200
    assert truncate("short", 100) == "short"


def test_unique_preserving_order() -> None:
    assert unique_preserving_order(["A", "a", "B", " b ", "C"]) == ["A", "B", "C"]


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------


def test_statistics(resume_text: str) -> None:
    stats = compute_statistics(resume_text)
    assert stats.words > 50
    assert stats.characters > stats.words
    assert stats.sentences >= 1
    assert stats.quantified_achievements >= 1


def test_statistics_on_empty_text() -> None:
    stats = compute_statistics("")
    assert stats.words == 0
    assert stats.sentences == 0


def test_legacy_statistics_shape(resume_text: str) -> None:
    legacy = compute_statistics(resume_text).as_legacy_dict()
    assert set(legacy) == {"Words", "Characters", "Sentences"}


# --------------------------------------------------------------------------
# Service layer
# --------------------------------------------------------------------------


def test_validate_job_description_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        validate_job_description("   ")


def test_validate_job_description_rejects_short_text() -> None:
    with pytest.raises(ValidationError):
        validate_job_description("dev job")


def test_analyze_text_pipeline(resume_text: str, job_text: str, temp_database) -> None:
    result = analyze_text(
        resume_text, job_text, resume_name="jane.pdf", include_ai_review=False
    )

    assert result.resume_name == "jane.pdf"
    assert 0 <= result.score <= 100
    assert 0 <= result.health_score <= 100
    assert 0 <= result.recruiter_readiness <= 100
    assert result.profile.skills
    assert result.ats.components


def test_analyze_text_persists_history(resume_text: str, job_text: str, temp_database) -> None:
    from resume_analyzer.persistence import repository

    analyze_text(resume_text, job_text, resume_name="x.pdf", include_ai_review=False)
    assert len(repository.fetch_history()) == 1


# --------------------------------------------------------------------------
# Legacy v1 facades must keep working
# --------------------------------------------------------------------------


def test_legacy_scorer_facade(resume_text: str, job_text: str) -> None:
    from utils.scorer import calculate_score, matched_skills, missing_skills

    score = calculate_score(resume_text, job_text)
    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert isinstance(matched_skills(resume_text, job_text), list)
    assert isinstance(missing_skills(resume_text, job_text), list)


def test_legacy_scorer_handles_empty_input() -> None:
    from utils.scorer import calculate_score

    assert calculate_score("", "") == 0


def test_legacy_nlp_facade(resume_text: str) -> None:
    from utils.nlp_parser import extract_resume_info

    info = extract_resume_info(resume_text)
    assert set(info) == {"email", "phone", "skills", "education", "experience"}
    assert info["email"] == "jane.doe@example.com"
    assert isinstance(info["skills"], list)


def test_legacy_stats_facade(resume_text: str) -> None:
    from utils.stats import resume_statistics

    stats = resume_statistics(resume_text)
    assert set(stats) == {"Words", "Characters", "Sentences"}


def test_legacy_parser_returns_empty_string_on_bad_file() -> None:
    import io

    from utils.parser import extract_text

    class FakeUpload(io.BytesIO):
        name = "resume.txt"

    assert extract_text(FakeUpload(b"hello")) == ""


def test_legacy_database_facade(temp_database) -> None:
    from utils.database import create_database, get_history, save_analysis

    create_database()
    save_analysis("legacy.pdf", 77)
    history = get_history()

    assert history
    assert history[0][0] == "legacy.pdf"
    assert history[0][1] == 77

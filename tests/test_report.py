"""Tests for PDF report generation."""

from __future__ import annotations

import io

import pdfplumber
import pytest

from resume_analyzer.domain.models import (
    AIReview,
    AnalysisResult,
    ATSResult,
    JobRequirements,
    ResumeProfile,
    ResumeStatistics,
)
from resume_analyzer.reporting.pdf_report import build_report
from resume_analyzer.services import analyze_text


@pytest.fixture(scope="module")
def result(request) -> AnalysisResult:
    from tests.conftest import SAMPLE_JOB, SAMPLE_RESUME

    return analyze_text(
        SAMPLE_RESUME,
        SAMPLE_JOB,
        resume_name="jane_doe.pdf",
        include_ai_review=True,
        persist=False,
    )


@pytest.fixture(scope="module")
def pdf_bytes(result: AnalysisResult) -> bytes:
    return build_report(result)


@pytest.fixture(scope="module")
def pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def test_produces_a_valid_pdf(pdf_bytes: bytes) -> None:
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 5_000


def test_report_is_multi_page(pdf_bytes: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as document:
        assert len(document.pages) >= 3


def test_cover_page_content(pdf_bytes: bytes) -> None:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as document:
        cover = document.pages[0].extract_text() or ""
    assert "ANALYSIS REPORT" in cover
    assert "jane_doe.pdf" in cover


@pytest.mark.parametrize(
    "section",
    [
        "Executive Overview",
        "Recruiter Verdict",
        "Score Breakdown",
        "Candidate Profile",
        "Skill Analysis",
        "MATCHED SKILLS",
        "MISSING SKILLS",
        "AI Review",
    ],
)
def test_required_sections_present(pdf_text: str, section: str) -> None:
    assert section in pdf_text


def test_score_appears_in_report(pdf_text: str, result: AnalysisResult) -> None:
    assert str(result.score) in pdf_text


def test_component_weights_are_documented(pdf_text: str) -> None:
    assert "weight" in pdf_text.lower()


def test_no_font_substitution_artifacts(pdf_text: str) -> None:
    """Glyphs missing from Helvetica render as '(cid:N)' — none may remain."""
    assert "(cid:" not in pdf_text


def test_no_double_escaped_entities(pdf_text: str) -> None:
    """Regression: escape(quote=True) previously mangled apostrophes."""
    for entity in ("&#x27;", "&amp;", "&lt;", "&gt;"):
        assert entity not in pdf_text


def test_handles_missing_ai_review() -> None:
    from tests.conftest import SAMPLE_JOB, SAMPLE_RESUME

    result = analyze_text(
        SAMPLE_RESUME, SAMPLE_JOB, include_ai_review=False, persist=False
    )
    assert build_report(result).startswith(b"%PDF")


def test_handles_empty_analysis() -> None:
    """A minimal result must still produce a valid document."""
    minimal = AnalysisResult(
        resume_name="empty.pdf",
        profile=ResumeProfile(),
        requirements=JobRequirements(),
        ats=ATSResult(),
        statistics=ResumeStatistics(),
    )
    assert build_report(minimal).startswith(b"%PDF")


def test_escapes_html_in_resume_content() -> None:
    """Markup inside a resume must not corrupt the PDF."""
    profile = ResumeProfile()
    profile.contact.full_name = "<b>Bold</b> & <script>alert(1)</script>"
    result = AnalysisResult(
        resume_name="x.pdf",
        profile=profile,
        requirements=JobRequirements(),
        ats=ATSResult(),
        statistics=ResumeStatistics(),
    )
    assert build_report(result).startswith(b"%PDF")


def test_long_content_is_truncated_safely() -> None:
    review = AIReview(
        executive_summary="word " * 5_000,
        strengths=[f"strength {index}" for index in range(50)],
        improvements=["improve " * 300],
    )
    result = AnalysisResult(
        resume_name="long.pdf",
        profile=ResumeProfile(),
        requirements=JobRequirements(),
        ats=ATSResult(),
        statistics=ResumeStatistics(),
        review=review,
    )
    assert build_report(result).startswith(b"%PDF")


def test_legacy_facade_still_works() -> None:
    from utils.pdf_report import generate_pdf

    pdf = generate_pdf(
        72,
        {"Words": 500, "Characters": 3000, "Sentences": 40},
        ["Python", "AWS"],
        ["Rust"],
        "## Review\nSolid resume overall.",
    )
    assert pdf.startswith(b"%PDF")


def test_legacy_facade_tolerates_empty_arguments() -> None:
    from utils.pdf_report import generate_pdf

    assert generate_pdf(0, None, None, None, "").startswith(b"%PDF")

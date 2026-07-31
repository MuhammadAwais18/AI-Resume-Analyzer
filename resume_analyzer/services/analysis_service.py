"""Application service orchestrating a full resume analysis.

This is the seam between the UI and the domain.  The UI hands over an upload
and a job description; the service validates, parses, scores, persists and
(optionally) requests an AI review, returning one :class:`AnalysisResult`.

Keeping orchestration here means the same pipeline can be driven from a CLI,
an HTTP API or a batch job without touching Streamlit.
"""

from __future__ import annotations

from typing import Any

from resume_analyzer.ai.reviewer import request_review
from resume_analyzer.analytics.statistics import compute_statistics
from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import (
    AnalysisRecord,
    AnalysisResult,
    JobRequirements,
    ResumeProfile,
)
from resume_analyzer.exceptions import ValidationError
from resume_analyzer.parsing.document import ExtractedDocument, extract_document
from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.persistence import repository
from resume_analyzer.scoring.ats_engine import (
    recruiter_readiness,
    resume_health_score,
    score_resume,
)
from resume_analyzer.scoring.job_parser import parse_job_description

logger = get_logger(__name__)

#: A job description shorter than this is not a real posting.
MIN_JOB_DESCRIPTION_CHARS = 40


def validate_job_description(text: str) -> str:
    """Validate and normalise the job description.

    Args:
        text: Raw user input.

    Returns:
        The stripped job description.

    Raises:
        ValidationError: The description is missing or too short.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValidationError(
            "empty job description",
            user_message="Please paste a job description to compare against.",
        )
    if len(cleaned) < MIN_JOB_DESCRIPTION_CHARS:
        raise ValidationError(
            "job description too short",
            user_message=(
                "That job description looks too short. Paste the full posting "
                "for an accurate ATS score."
            ),
        )
    return cleaned


def analyze_text(
    resume_text: str,
    job_description: str,
    *,
    resume_name: str = "resume",
    include_ai_review: bool = True,
    persist: bool = True,
) -> AnalysisResult:
    """Run the complete analysis pipeline on already-extracted text.

    Args:
        resume_text: Plain resume text.
        job_description: Plain job description text.
        resume_name: Label stored in history and shown in the report.
        include_ai_review: Request an AI review when credentials allow.
        persist: Save the run to the analytics database.

    Returns:
        A fully populated :class:`AnalysisResult`.

    Raises:
        ValidationError: The job description is missing or too short.
    """
    job_description = validate_job_description(job_description)

    profile: ResumeProfile = parse_resume(resume_text)
    requirements: JobRequirements = parse_job_description(job_description)
    ats = score_resume(profile, requirements)
    statistics = compute_statistics(profile.raw_text or resume_text)

    health = resume_health_score(profile, statistics.words)
    readiness = recruiter_readiness(ats, health, profile)

    result = AnalysisResult(
        resume_name=resume_name,
        profile=profile,
        requirements=requirements,
        ats=ats,
        statistics=statistics,
        health_score=health,
        recruiter_readiness=readiness,
    )

    if include_ai_review:
        result.review = request_review(
            profile.raw_text or resume_text,
            job_description,
            profile,
            requirements,
            ats,
        )

    if persist:
        repository.save_record(
            AnalysisRecord(
                resume_name=resume_name,
                score=ats.rounded_score,
                match_level=ats.match_level.value,
                matched_count=len(ats.matched_skills),
                missing_count=len(ats.missing_skills),
                experience_years=profile.total_experience_years,
                job_title=requirements.title,
            )
        )

    logger.info(
        "Analysis complete for %s: score=%s health=%s readiness=%s",
        resume_name,
        ats.rounded_score,
        health,
        readiness,
    )
    return result


def analyze_upload(
    uploaded_file: Any,
    job_description: str,
    *,
    include_ai_review: bool = True,
    persist: bool = True,
) -> tuple[AnalysisResult, ExtractedDocument]:
    """Extract an uploaded resume and run the analysis pipeline.

    Args:
        uploaded_file: Streamlit ``UploadedFile`` or compatible object.
        job_description: Raw job description text.
        include_ai_review: Request an AI review when credentials allow.
        persist: Save the run to the analytics database.

    Returns:
        Tuple of the analysis result and the extracted document.

    Raises:
        ResumeAnalyzerError: Any validation, extraction or parsing failure,
            each carrying a user-safe ``user_message``.
    """
    document = extract_document(uploaded_file)
    result = analyze_text(
        document.text,
        job_description,
        resume_name=document.filename,
        include_ai_review=include_ai_review,
        persist=persist,
    )
    return result, document

"""AI resume reviewer with graceful degradation.

The reviewer is resilient by construction:

* Missing credentials, timeouts, rate limits, network faults and malformed
  payloads are each mapped to a typed exception with a user-safe message.
* Transient failures are retried with exponential backoff.
* When the model is unreachable, a **deterministic fallback review** is built
  from the local ATS analysis, so the user always receives useful feedback and
  the PDF report is never empty.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Final

from resume_analyzer.ai.prompts import SYSTEM_PROMPT, build_review_prompt
from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.config.settings import get_settings
from resume_analyzer.domain.models import (
    AIReview,
    ATSResult,
    JobRequirements,
    ResumeProfile,
)
from resume_analyzer.exceptions import (
    AIConfigurationError,
    AIRateLimitError,
    AIResponseError,
    AIServiceError,
    AITimeoutError,
)

logger = get_logger(__name__)

#: Seconds to wait before the first retry; doubled on each attempt.
_BACKOFF_BASE_SECONDS: Final[float] = 1.5

#: Maximum rating on the 0-10 scale returned by the model.
_MAX_RATING: Final[float] = 10.0

_JSON_BLOCK_RE: Final[re.Pattern[str]] = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL
)


def _build_client() -> Any:
    """Create the OpenAI-compatible client.

    Returns:
        A configured ``OpenAI`` client.

    Raises:
        AIConfigurationError: No API key is configured.
        AIServiceError: The SDK is missing or the client cannot be built.
    """
    settings = get_settings()
    if not settings.ai.is_configured:
        raise AIConfigurationError("no API key configured")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - dependency guaranteed
        raise AIServiceError(f"openai sdk missing: {exc}") from exc

    return OpenAI(
        api_key=settings.ai.api_key,
        base_url=settings.ai.base_url,
        timeout=settings.ai.timeout_seconds,
        max_retries=0,  # Retries are handled here so they can be logged.
    )


def _classify(exc: Exception) -> AIServiceError:
    """Map a provider exception onto the application error hierarchy."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()

    if "timeout" in name or "timeout" in message or "timed out" in message:
        return AITimeoutError(str(exc))
    if "ratelimit" in name or "rate limit" in message or "429" in message:
        return AIRateLimitError(str(exc))
    if "authentication" in name or "401" in message or "invalid api key" in message:
        return AIConfigurationError(str(exc))
    if "connection" in name or "network" in message or "connect" in message:
        return AIServiceError(
            str(exc),
            user_message="Could not reach the AI service. Check your connection and retry.",
        )
    return AIServiceError(str(exc))


def _extract_json(content: str) -> dict[str, Any]:
    """Parse the model's response into a dictionary.

    Handles bare JSON, fenced code blocks and prose-wrapped JSON.

    Raises:
        AIResponseError: No valid JSON object could be recovered.
    """
    text = (content or "").strip()
    if not text:
        raise AIResponseError("empty response body")

    for candidate in (text, *(match.group(1) for match in _JSON_BLOCK_RE.finditer(text))):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise AIResponseError("response did not contain valid JSON")


def _as_str_list(value: Any, limit: int = 8) -> list[str]:
    """Coerce a model field into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [
            re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            for line in value.split("\n")
        ]
        return [part for part in parts if part][:limit]
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
            elif isinstance(item, dict):
                items.append(" — ".join(str(v) for v in item.values() if v))
        return items[:limit]
    return [str(value)]


def _as_text(value: Any) -> str:
    """Coerce a model field into a single paragraph."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(item).strip() for item in value if item)
    return str(value).strip()


def _as_rating(value: Any) -> float:
    """Coerce the rating field onto the 0-10 scale."""
    try:
        rating = float(re.sub(r"[^\d.]", "", str(value)) or 0)
    except (TypeError, ValueError):
        return 0.0
    if rating > _MAX_RATING:  # Model answered on a 0-100 scale.
        rating /= 10.0
    return round(max(0.0, min(_MAX_RATING, rating)), 1)


def _to_review(payload: dict[str, Any], raw: str) -> AIReview:
    """Build a validated :class:`AIReview` from the model payload."""
    return AIReview(
        executive_summary=_as_text(payload.get("executive_summary")),
        ats_review=_as_text(payload.get("ats_review")),
        strengths=_as_str_list(payload.get("strengths")),
        weaknesses=_as_str_list(payload.get("weaknesses")),
        missing_skills=_as_str_list(payload.get("missing_skills"), limit=15),
        improvements=_as_str_list(payload.get("improvements")),
        recruiter_impression=_as_text(payload.get("recruiter_impression")),
        interview_readiness=_as_text(payload.get("interview_readiness")),
        resume_rating=_as_rating(payload.get("resume_rating")),
        career_advice=_as_str_list(payload.get("career_advice"), limit=6),
        raw_markdown=raw,
    )


#: Maps markdown headings the model may emit onto :class:`AIReview` fields.
_HEADING_FIELDS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("executive summary", "executive_summary", False),
    ("ats review", "ats_review", False),
    ("overall ats review", "ats_review", False),
    ("strengths", "strengths", True),
    ("weaknesses", "weaknesses", True),
    ("missing skills", "missing_skills", True),
    ("improvement suggestions", "improvements", True),
    ("improvements", "improvements", True),
    ("recruiter impression", "recruiter_impression", False),
    ("interview readiness", "interview_readiness", False),
    ("career advice", "career_advice", True),
    # Recognised so their bodies are not appended to the preceding section.
    ("resume rating", "_rating", False),
    ("final verdict", "_verdict", False),
    ("overall rating", "_rating", False),
    ("conclusion", "_verdict", False),
)

#: Headings captured only to terminate the previous section; not rendered.
_DISCARDED_FIELDS: Final[frozenset[str]] = frozenset({"_rating", "_verdict"})

_MARKDOWN_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*|\*\*)?(?:\d+[.)]\s*)?([A-Za-z][A-Za-z /&']{2,40}?)"
    r"(?:\*\*)?\s*:?\s*$",
    re.MULTILINE,
)

_RATING_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:rating|score)\D{0,15}(\d{1,3}(?:\.\d)?)\s*(?:/\s*(\d{1,3}))?", re.IGNORECASE
)


def _salvage_markdown(content: str) -> AIReview | None:
    """Recover a review from a markdown answer that ignored the JSON schema.

    Args:
        content: The raw model response.

    Returns:
        A populated :class:`AIReview`, or ``None`` when too little is
        recoverable to be worth showing.
    """
    if not content or len(content.strip()) < 60:
        return None

    lines = content.split("\n")
    buckets: dict[str, list[str]] = {}
    current: str | None = None

    for line in lines:
        heading = _MARKDOWN_HEADING_RE.match(line)
        matched_field = None
        if heading:
            label = heading.group(1).strip().lower()
            matched_field = next(
                (field for name, field, _is_list in _HEADING_FIELDS if name == label),
                None,
            )
        if matched_field:
            current = matched_field
            buckets.setdefault(current, [])
            continue
        if current and line.strip():
            buckets[current].append(line.strip())

    if not buckets:
        return None

    review = AIReview(raw_markdown=content)
    list_fields = {field for _name, field, is_list in _HEADING_FIELDS if is_list}

    for field, collected in buckets.items():
        if field in _DISCARDED_FIELDS:
            continue
        if field in list_fields:
            setattr(review, field, _as_str_list("\n".join(collected)))
        else:
            setattr(review, field, " ".join(collected).strip())

    rating_match = _RATING_RE.search(content)
    if rating_match:
        value = float(rating_match.group(1))
        scale = float(rating_match.group(2) or 10)
        review.resume_rating = round(min(_MAX_RATING, value / scale * _MAX_RATING), 1)

    has_content = bool(
        review.executive_summary
        or review.strengths
        or review.weaknesses
        or review.improvements
    )
    return review if has_content else None


def build_fallback_review(
    profile: ResumeProfile, requirements: JobRequirements, ats: ATSResult, reason: str
) -> AIReview:
    """Construct a deterministic review from local analysis only.

    Used whenever the language model is unavailable, so the product keeps
    working without AI.

    Args:
        profile: Parsed resume.
        requirements: Parsed job requirements.
        ats: Deterministic scoring result.
        reason: User-facing explanation of why AI feedback is unavailable.

    Returns:
        A populated :class:`AIReview` flagged with ``is_fallback=True``.
    """
    matched = [skill.name for skill in ats.matched_skills]
    missing = [skill.name for skill in ats.missing_required_skills]

    strengths: list[str] = []
    if matched:
        strengths.append(
            f"Matches {len(matched)} of the role's skills, including "
            f"{', '.join(matched[:5])}."
        )
    if profile.total_experience_years:
        strengths.append(
            f"Around {profile.total_experience_years:g} years of experience detected."
        )
    if profile.achievements:
        strengths.append(
            f"{len(profile.achievements)} quantified achievement(s) demonstrate impact."
        )
    if profile.certifications:
        strengths.append(f"Holds {len(profile.certifications)} certification(s).")
    if profile.contact.linkedin and profile.contact.github:
        strengths.append("Complete online presence with both LinkedIn and GitHub.")

    weaknesses: list[str] = []
    if missing:
        weaknesses.append(f"Missing required skills: {', '.join(missing[:6])}.")
    if ats.keyword_coverage < 0.5:
        weaknesses.append(
            f"Only {ats.keyword_coverage:.0%} of the posting's key terms appear "
            "in the resume."
        )
    if not profile.achievements:
        weaknesses.append("No quantified achievements were detected.")
    if not profile.contact.email:
        weaknesses.append("No e-mail address was found in the resume.")
    if requirements.min_experience_years > profile.total_experience_years:
        weaknesses.append(
            f"Experience appears below the {requirements.min_experience_years:g}-year "
            "requirement."
        )

    return AIReview(
        executive_summary=(
            f"Deterministic analysis scored this resume {ats.overall_score:.0f}/100 "
            f"against the role ({ats.match_level.value}). {ats.recruiter_verdict}"
        ),
        ats_review=(
            f"Weighted ATS score: {ats.overall_score:.0f}/100. "
            + " ".join(
                f"{component.name} {component.score:.0f}/100."
                for component in ats.components
            )
        ),
        strengths=strengths or ["Resume parsed successfully."],
        weaknesses=weaknesses or ["No significant structural gaps detected."],
        missing_skills=missing,
        improvements=ats.recommendations
        or ["Tailor the resume wording to the job description."],
        recruiter_impression=ats.recruiter_verdict,
        interview_readiness=(
            "Prepare to discuss "
            + (", ".join(matched[:4]) if matched else "your core technical strengths")
            + (f", and be ready for gaps in {', '.join(missing[:3])}." if missing else ".")
        ),
        resume_rating=round(ats.overall_score / 10.0, 1),
        career_advice=[
            "Keep a master resume and tailor a copy per application.",
            "Lead every bullet with an action verb and close with a measurable result.",
        ],
        is_fallback=True,
        error_message=reason,
    )


def request_review(
    resume_text: str,
    job_description: str,
    profile: ResumeProfile,
    requirements: JobRequirements,
    ats: ATSResult,
) -> AIReview:
    """Request a structured AI review, retrying transient failures.

    Args:
        resume_text: Raw resume text.
        job_description: Raw job description.
        profile: Parsed resume profile.
        requirements: Parsed job requirements.
        ats: Deterministic ATS result used for grounding.

    Returns:
        A model-generated review, or a deterministic fallback review when the
        provider is unavailable. This function does not raise.
    """
    settings = get_settings()
    prompt = build_review_prompt(
        resume_text, job_description, profile, requirements, ats
    )

    last_error: AIServiceError | None = None

    for attempt in range(1, settings.ai.max_retries + 2):
        try:
            client = _build_client()
            response = client.chat.completions.create(
                model=settings.ai.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.ai.temperature,
                max_tokens=settings.ai.max_tokens,
            )

            choices = getattr(response, "choices", None)
            if not choices:
                raise AIResponseError(f"no choices in response: {response!r}")

            content = choices[0].message.content or ""
            try:
                review = _to_review(_extract_json(content), content)
            except AIResponseError:
                # Some models ignore the JSON instruction and answer in
                # markdown. Rather than discard a usable review, salvage it by
                # parsing the headings; only give up if nothing is recoverable.
                review = _salvage_markdown(content)
                if review is None:
                    raise
                logger.info("Recovered a markdown review on attempt %s.", attempt)
                return review

            logger.info("AI review generated on attempt %s.", attempt)
            return review

        except AIConfigurationError as exc:
            logger.warning("AI not configured: %s", exc)
            return build_fallback_review(
                profile, requirements, ats, exc.user_message
            )

        except Exception as exc:
            error = exc if isinstance(exc, AIServiceError) else _classify(exc)
            last_error = error
            logger.warning(
                "AI review attempt %s/%s failed: %s",
                attempt,
                settings.ai.max_retries + 1,
                error,
            )
            if attempt <= settings.ai.max_retries:
                time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    reason = last_error.user_message if last_error else "AI review unavailable."
    logger.error("AI review failed after all retries; using fallback.")
    return build_fallback_review(profile, requirements, ats, reason)


def review_to_markdown(review: AIReview) -> str:
    """Render an :class:`AIReview` as presentation-ready markdown."""
    sections: list[str] = []

    def add_paragraph(title: str, body: str) -> None:
        if body:
            sections.append(f"### {title}\n\n{body}")

    def add_list(title: str, items: list[str]) -> None:
        if items:
            bullets = "\n".join(f"- {item}" for item in items)
            sections.append(f"### {title}\n\n{bullets}")

    add_paragraph("Executive Summary", review.executive_summary)
    add_paragraph("ATS Review", review.ats_review)
    add_list("Strengths", review.strengths)
    add_list("Weaknesses", review.weaknesses)
    add_list("Missing Skills", review.missing_skills)
    add_list("Improvement Suggestions", review.improvements)
    add_paragraph("Recruiter Impression", review.recruiter_impression)
    add_paragraph("Interview Readiness", review.interview_readiness)
    if review.resume_rating:
        add_paragraph("Resume Rating", f"**{review.resume_rating}/10**")
    add_list("Career Advice", review.career_advice)

    return "\n\n".join(sections) if sections else "_No review content available._"

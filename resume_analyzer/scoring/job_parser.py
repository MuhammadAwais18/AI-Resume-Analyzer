"""Job description understanding.

Recruiters write requirements in predictable ways.  This module separates
**required** from **preferred** skills by reading the sentence a skill appears
in, and extracts the minimum experience and education bar.
"""

from __future__ import annotations

import re
from typing import Final

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import JobRequirements, Skill
from resume_analyzer.parsing.patterns import JOB_TITLE_HINTS, YEARS_EXPERIENCE_RE
from resume_analyzer.parsing.resume_parser import education_level
from resume_analyzer.skills.registry import detect_skills
from resume_analyzer.utils_text import normalize_whitespace, split_lines

logger = get_logger(__name__)

#: Phrases marking a hard requirement.
REQUIRED_MARKERS: Final[tuple[str, ...]] = (
    "required",
    "requirement",
    "must have",
    "must-have",
    "essential",
    "you have",
    "you will need",
    "we require",
    "minimum qualifications",
    "basic qualifications",
    "mandatory",
    "proven experience",
    "strong experience",
    "demonstrated experience",
    "expertise in",
    "proficiency in",
    "proficient in",
    "solid understanding",
    "hands-on experience",
    "responsibilities",
)

#: Phrases marking a nice-to-have.
OPTIONAL_MARKERS: Final[tuple[str, ...]] = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "plus",
    "desirable",
    "advantageous",
    "good to have",
    "optional",
    "familiarity with",
    "exposure to",
    "ideally",
    "would be great",
    "we'd love",
)

_SENTENCE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?;])\s+|\n")


def _classify_segment(segment: str) -> str:
    """Classify one sentence as ``"required"``, ``"optional"`` or ``"neutral"``."""
    lowered = segment.lower()
    optional_hit = next(
        (lowered.index(marker) for marker in OPTIONAL_MARKERS if marker in lowered),
        None,
    )
    required_hit = next(
        (lowered.index(marker) for marker in REQUIRED_MARKERS if marker in lowered),
        None,
    )
    if optional_hit is not None and required_hit is not None:
        return "optional" if optional_hit < required_hit else "required"
    if optional_hit is not None:
        return "optional"
    if required_hit is not None:
        return "required"
    return "neutral"


def _extract_title(text: str) -> str | None:
    """Guess the job title from the first meaningful lines."""
    for line in split_lines(text)[:6]:
        lowered = line.lower()
        if len(line) <= 80 and any(hint in lowered for hint in JOB_TITLE_HINTS):
            return re.sub(r"^\s*(job title|position|role)\s*[:\-]\s*", "", line,
                          flags=re.IGNORECASE).strip()
    return None


def _minimum_experience(text: str) -> float:
    """Extract the smallest stated experience requirement, in years."""
    values = []
    for match in YEARS_EXPERIENCE_RE.finditer(text):
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 < value <= 40:
            values.append(value)
    return min(values) if values else 0.0


def parse_job_description(text: str) -> JobRequirements:
    """Parse a job description into structured requirements.

    Args:
        text: Raw job description.

    Returns:
        A :class:`JobRequirements` with skills split into required and
        optional buckets. Skills mentioned in neutral context default to
        required, mirroring how ATS platforms treat unqualified keywords.
    """
    if not text or not text.strip():
        return JobRequirements()

    normalized = normalize_whitespace(text)
    all_skills = detect_skills(normalized)
    if not all_skills:
        logger.info("No catalog skills detected in the job description.")

    by_name: dict[str, Skill] = {skill.name: skill for skill in all_skills}
    classification: dict[str, str] = {}

    # A skill inherits the strongest marker of any sentence that mentions it.
    for segment in _SENTENCE_SPLIT_RE.split(normalized):
        if not segment.strip():
            continue
        label = _classify_segment(segment)
        if label == "neutral":
            continue
        for skill in detect_skills(segment):
            if skill.name not in by_name:
                continue
            current = classification.get(skill.name)
            if current == "required":
                continue
            classification[skill.name] = label

    required: list[Skill] = []
    optional: list[Skill] = []
    for name, skill in by_name.items():
        if classification.get(name) == "optional":
            optional.append(skill)
        else:
            required.append(skill)

    education_label, education_rank = education_level(normalized)

    requirements = JobRequirements(
        raw_text=normalized,
        required_skills=required,
        optional_skills=optional,
        min_experience_years=_minimum_experience(normalized),
        required_education_level=education_rank,
        education_label=education_label,
        title=_extract_title(normalized),
    )
    logger.info(
        "Parsed job description: %s required, %s optional skills.",
        len(required),
        len(optional),
    )
    return requirements

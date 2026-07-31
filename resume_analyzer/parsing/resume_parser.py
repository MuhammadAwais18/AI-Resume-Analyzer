"""Structured resume parsing.

The parser turns raw text into a :class:`ResumeProfile`.  It is built around
three cooperating strategies, applied in order of reliability:

1. **Section segmentation** — headings are detected so that later extractors
   look in the right place (certifications are searched inside the
   certifications section first, and only then across the document).
2. **Deterministic patterns** — regular expressions for e-mail, phone, URLs,
   degrees and date ranges. These are precise and always available.
3. **Optional NER** — spaCy refines person names when the model is installed.

Every extractor is individually guarded: a failure in one field degrades that
field to ``None`` and records a warning instead of aborting the parse.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Final

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import (
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    ResumeProfile,
)
from resume_analyzer.parsing import nlp
from resume_analyzer.parsing.patterns import (
    AWARD_HINTS,
    BULLET_PREFIX_RE,
    CERTIFICATION_HINTS,
    DATE_RANGE_RE,
    DEGREE_LEVELS,
    DEGREE_QUALIFIERS,
    EMAIL_RE,
    FIELD_OF_STUDY_RE,
    GITHUB_RE,
    HEADING_LOOKUP,
    INSTITUTION_RE,
    JOB_TITLE_HINTS,
    KNOWN_LANGUAGES,
    LINKEDIN_RE,
    NAME_STOP_TOKENS,
    NON_PORTFOLIO_HOSTS,
    PHONE_RE,
    URL_RE,
    YEAR_RE,
    YEARS_EXPERIENCE_RE,
)
from resume_analyzer.skills.registry import detect_skills
from resume_analyzer.utils_text import (
    normalize_whitespace,
    split_lines,
    unique_preserving_order,
)

logger = get_logger(__name__)

#: Lines longer than this are prose, never headings.
_MAX_HEADING_LENGTH: Final[int] = 60

#: Lines scanned at the top of a resume when looking for the candidate name.
_NAME_SCAN_LINES: Final[int] = 12

#: Months per year, used when converting employment durations.
_MONTHS_PER_YEAR: Final[int] = 12

_MONTH_NUMBERS: Final[dict[str, int]] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_PRESENT_TOKENS: Final[frozenset[str]] = frozenset(
    {"present", "current", "now", "ongoing", "today"}
)


# ---------------------------------------------------------------------------
# Section segmentation
# ---------------------------------------------------------------------------


def _normalize_heading(line: str) -> str:
    """Strip decoration from a candidate heading line."""
    cleaned = re.sub(r"[^A-Za-z&\s]", " ", line)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _is_heading(line: str) -> str | None:
    """Return the canonical section name when ``line`` is a heading."""
    if not line or len(line) > _MAX_HEADING_LENGTH:
        return None
    if line.endswith(('.', ',', ';')):
        return None

    normalized = _normalize_heading(line)
    if not normalized or len(normalized.split()) > 4:
        return None

    canonical = HEADING_LOOKUP.get(normalized)
    if canonical:
        return canonical

    # Headings are frequently uppercase or title case with no sentence text.
    if line.isupper() and normalized in HEADING_LOOKUP:
        return HEADING_LOOKUP[normalized]
    return None


def split_sections(text: str) -> dict[str, str]:
    """Split resume text into canonical sections.

    Args:
        text: Normalised resume text.

    Returns:
        Mapping of canonical section name to its body text. Content appearing
        before the first heading is stored under ``"header"``.
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"

    for line in text.split("\n"):
        stripped = line.strip()
        heading = _is_heading(stripped)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        if stripped:
            sections.setdefault(current, []).append(stripped)

    return {
        name: "\n".join(lines).strip()
        for name, lines in sections.items()
        if any(line.strip() for line in lines)
    }


# ---------------------------------------------------------------------------
# Contact extraction
# ---------------------------------------------------------------------------


def extract_email(text: str) -> str | None:
    """Return the first valid e-mail address found."""
    for match in EMAIL_RE.finditer(text):
        candidate = match.group().strip(".,;:")
        # Skip image/file names that happen to contain '@'.
        if not candidate.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            return candidate
    return None


def extract_phone(text: str) -> str | None:
    """Return the first plausible phone number found."""
    for match in PHONE_RE.finditer(text):
        candidate = match.group().strip()
        digits = re.sub(r"\D", "", candidate)
        if not 7 <= len(digits) <= 15:
            continue
        # Reject year ranges such as "2019 - 2022".
        if YEAR_RE.fullmatch(digits[:4]) and len(digits) <= 8:
            continue
        return re.sub(r"\s{2,}", " ", candidate)
    return None


def _clean_url(url: str) -> str:
    """Normalise a URL for display."""
    cleaned = url.strip().strip(".,;:)")
    if not cleaned.lower().startswith("http"):
        cleaned = f"https://{cleaned}"
    return cleaned


def extract_linkedin(text: str) -> str | None:
    """Return the candidate's LinkedIn profile URL."""
    match = LINKEDIN_RE.search(text)
    return _clean_url(match.group()) if match else None


def extract_github(text: str) -> str | None:
    """Return the candidate's GitHub profile URL."""
    match = GITHUB_RE.search(text)
    return _clean_url(match.group()) if match else None


def extract_portfolio(text: str) -> str | None:
    """Return a personal site URL that is not a known social network."""
    for match in URL_RE.finditer(text):
        url = match.group().strip().strip(".,;:)")
        lowered = url.lower()
        if any(host in lowered for host in NON_PORTFOLIO_HOSTS):
            continue
        if lowered.endswith((".png", ".jpg", ".jpeg", ".pdf")):
            continue
        return _clean_url(url)
    return None


def _looks_like_name(line: str) -> bool:
    """Heuristically decide whether ``line`` is a person's name."""
    stripped = BULLET_PREFIX_RE.sub("", line).strip()
    if not 2 <= len(stripped.split()) <= 5 or len(stripped) > 48:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    if "@" in stripped or "http" in stripped.lower() or "|" in stripped:
        return False

    tokens = [token.strip(".,") for token in stripped.split()]
    if any(token.lower() in NAME_STOP_TOKENS for token in tokens):
        return False
    # Names are title case or upper case, and mostly alphabetic.
    alphabetic = [token for token in tokens if token.replace("-", "").isalpha()]
    if len(alphabetic) < 2:
        return False
    return all(token[0].isupper() for token in alphabetic)


def extract_full_name(text: str, email: str | None = None) -> str | None:
    """Extract the candidate's full name.

    Strategy: scan the top lines for a name-shaped line, then fall back to
    spaCy NER, then to the local-part of the e-mail address.

    Args:
        text: Resume text.
        email: Previously extracted e-mail, used as a last resort.

    Returns:
        The candidate's name, or ``None``.
    """
    lines = split_lines(text)[:_NAME_SCAN_LINES]

    for line in lines:
        if _looks_like_name(line):
            return BULLET_PREFIX_RE.sub("", line).strip().title()

    for entity in nlp.extract_entities(text, ("PERSON",)):
        if _looks_like_name(entity):
            return entity.title()

    if email:
        local = re.split(r"[._\-0-9]+", email.split("@")[0])
        parts = [part for part in local if len(part) > 1]
        if len(parts) >= 2:
            return " ".join(part.capitalize() for part in parts[:3])

    return None


def extract_contact(text: str) -> ContactInfo:
    """Extract all contact and online-presence fields."""
    email = extract_email(text)
    return ContactInfo(
        full_name=extract_full_name(text, email),
        email=email,
        phone=extract_phone(text),
        linkedin=extract_linkedin(text),
        github=extract_github(text),
        portfolio=extract_portfolio(text),
        location=_extract_location(text),
    )


def _extract_location(text: str) -> str | None:
    """Best-effort city/country extraction from the resume header."""
    header = "\n".join(split_lines(text)[:_NAME_SCAN_LINES])
    for entity in nlp.extract_entities(header, ("GPE", "LOC")):
        if 2 < len(entity) < 40:
            return entity
    match = re.search(
        r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+)\b", header
    )
    return match.group().strip() if match else None


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


def education_level(text: str) -> tuple[str | None, int]:
    """Return the highest degree label and its seniority rank.

    Args:
        text: Resume or job description text.

    Returns:
        ``(label, rank)`` where rank is 0 when nothing was found.
    """
    lowered = text.lower()
    best_label: str | None = None
    best_rank = 0
    for keyword, (label, rank) in DEGREE_LEVELS.items():
        if keyword in lowered and rank > best_rank:
            best_label, best_rank = label, rank
    return best_label, best_rank


def _field_of_study(line: str) -> str | None:
    """Extract the subject studied, skipping degree qualifiers.

    ``"Master of Science in Computer Science"`` yields ``"Computer Science"``
    rather than ``"Science"``, because ``of Science`` is part of the degree
    name, not the field.
    """
    for match in FIELD_OF_STUDY_RE.finditer(line):
        candidate = match.group(1).strip(" ,-–—")
        lowered = candidate.lower()
        if lowered in DEGREE_QUALIFIERS or len(candidate) < 3:
            continue
        # Drop a leading qualifier such as "Science in Computer Science".
        for qualifier in DEGREE_QUALIFIERS:
            prefix = f"{qualifier} in "
            if lowered.startswith(prefix):
                candidate = candidate[len(prefix):].strip()
                break
        return candidate.title() if candidate else None
    return None


def extract_education(text: str, sections: dict[str, str]) -> list[EducationEntry]:
    """Extract education entries, preferring the dedicated section."""
    source = sections.get("education") or text
    entries: list[EducationEntry] = []
    seen: set[str] = set()

    for line in split_lines(source):
        lowered = line.lower()
        matched = next(
            (
                (label, keyword)
                for keyword, (label, _rank) in DEGREE_LEVELS.items()
                if keyword in lowered
            ),
            None,
        )
        if not matched:
            continue

        label, _keyword = matched
        if label in seen and len(entries) >= 4:
            continue

        institution_match = INSTITUTION_RE.search(line)
        year_matches = YEAR_RE.findall(line)

        entries.append(
            EducationEntry(
                degree=label,
                field_of_study=_field_of_study(line),
                institution=(
                    institution_match.group(1).strip() if institution_match else None
                ),
                year=(
                    re.findall(r"(?:19|20)\d{2}", line)[-1] if year_matches else None
                ),
                raw_text=line,
            )
        )
        seen.add(label)

    entries.sort(key=lambda entry: -DEGREE_LEVELS.get(entry.degree.lower(), ("", 0))[1])
    return entries[:5]


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------


def _parse_month_year(token: str) -> tuple[int, int] | None:
    """Parse ``"Jan 2020"`` / ``"2020"`` into ``(year, month)``."""
    token = token.strip().lower().replace(".", "")
    if token in _PRESENT_TOKENS:
        now = datetime.now()
        return now.year, now.month

    year_match = re.search(r"(19|20)\d{2}", token)
    if not year_match:
        return None
    year = int(year_match.group())
    month = 1
    for name, number in _MONTH_NUMBERS.items():
        if token.startswith(name) or f" {name}" in token:
            month = number
            break
    return year, month


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Inclusive month count between two ``(year, month)`` tuples."""
    return max(0, (end[0] - start[0]) * _MONTHS_PER_YEAR + (end[1] - start[1]))


def total_experience_years(text: str, sections: dict[str, str]) -> float:
    """Estimate total professional experience in years.

    Two independent signals are combined and the larger is returned:
    an explicit claim (``"5+ years of experience"``) and the union of
    employment date ranges.
    """
    stated = 0.0
    for match in YEARS_EXPERIENCE_RE.finditer(text):
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 < value <= 50:
            stated = max(stated, value)

    source = sections.get("experience") or text
    intervals: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for match in DATE_RANGE_RE.finditer(source):
        start = _parse_month_year(match.group(1))
        end = _parse_month_year(match.group(2))
        if start and end and end >= start:
            intervals.append((start, end))

    computed = 0.0
    if intervals:
        intervals.sort()
        merged: list[list[tuple[int, int]]] = [list(intervals[0])]
        for start, end in intervals[1:]:
            if start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        months = sum(_months_between(start, end) for start, end in merged)
        computed = round(months / _MONTHS_PER_YEAR, 1)

    return max(stated, computed)


def _looks_like_job_title(line: str) -> bool:
    """Return ``True`` when the line reads like a role header."""
    lowered = line.lower()
    if len(line) > 90 or len(line.split()) > 12:
        return False
    return any(hint in lowered for hint in JOB_TITLE_HINTS)


def extract_experience(text: str, sections: dict[str, str]) -> list[ExperienceEntry]:
    """Extract professional experience entries."""
    source = sections.get("experience")
    if not source:
        return []

    entries: list[ExperienceEntry] = []
    lines = split_lines(source)

    for index, line in enumerate(lines):
        if BULLET_PREFIX_RE.match(line) or not _looks_like_job_title(line):
            continue

        date_match = DATE_RANGE_RE.search(line)
        context = line
        if not date_match and index + 1 < len(lines):
            date_match = DATE_RANGE_RE.search(lines[index + 1])
            context = f"{line} {lines[index + 1]}"

        duration = None
        start = end = None
        if date_match:
            start, end = date_match.group(1).strip(), date_match.group(2).strip()
            parsed_start = _parse_month_year(start)
            parsed_end = _parse_month_year(end)
            if parsed_start and parsed_end:
                duration = _months_between(parsed_start, parsed_end)

        # Strip dates *before* splitting so a trailing "Jun 2018 - Dec 2020"
        # is never mistaken for the employer name.
        header = DATE_RANGE_RE.sub("", BULLET_PREFIX_RE.sub("", line))
        header = re.sub(r"\s{2,}", " ", header).strip(" ,|-–—\t")

        title, company = header, None
        for separator in (" at ", " | ", " · ", " – ", " - ", ", "):
            if separator in header:
                head, _, tail = header.partition(separator)
                title, company = head.strip(), tail.strip(" ,|-–—")
                break

        entries.append(
            ExperienceEntry(
                title=title or "Role",
                company=company or None,
                start_date=start,
                end_date=end,
                duration_months=duration,
                description=context,
            )
        )

    return entries[:12]


# ---------------------------------------------------------------------------
# List-style sections
# ---------------------------------------------------------------------------


def _collect_lines(
    sections: dict[str, str],
    section_name: str,
    text: str,
    predicate: Callable[[str], bool],
    limit: int = 12,
) -> list[str]:
    """Collect matching lines from a section, falling back to the whole text."""
    source = sections.get(section_name)
    candidates: list[str] = []

    if source:
        candidates = [BULLET_PREFIX_RE.sub("", line) for line in split_lines(source)]
    else:
        candidates = [
            BULLET_PREFIX_RE.sub("", line)
            for line in split_lines(text)
            if predicate(line.lower())
        ]

    cleaned = [
        line
        for line in candidates
        if 3 < len(line) <= 160 and not _is_heading(line)
    ]
    return unique_preserving_order(cleaned)[:limit]


def extract_certifications(text: str, sections: dict[str, str]) -> list[str]:
    """Extract certifications and professional training."""
    return _collect_lines(
        sections,
        "certifications",
        text,
        lambda line: any(hint in line for hint in CERTIFICATION_HINTS),
    )


def extract_projects(text: str, sections: dict[str, str]) -> list[str]:
    """Extract project titles or one-line project descriptions."""
    return _collect_lines(sections, "projects", text, lambda line: False)


def extract_awards(text: str, sections: dict[str, str]) -> list[str]:
    """Extract awards and honours."""
    return _collect_lines(
        sections,
        "awards",
        text,
        lambda line: any(hint in line for hint in AWARD_HINTS),
    )


def extract_achievements(text: str, sections: dict[str, str]) -> list[str]:
    """Extract achievement statements, preferring quantified bullets."""
    achievements = _collect_lines(sections, "achievements", text, lambda line: False)
    if achievements:
        return achievements

    quantified = [
        BULLET_PREFIX_RE.sub("", line)
        for line in split_lines(sections.get("experience", ""))
        if BULLET_PREFIX_RE.match(line)
        and re.search(r"\d+\s*%|\$\s?\d|\b\d{3,}\b|\b\d+x\b", line)
    ]
    return unique_preserving_order(quantified)[:8]


def extract_languages(text: str, sections: dict[str, str]) -> list[str]:
    """Extract spoken languages."""
    source = sections.get("languages", "")
    haystack = source if source else text
    found = [
        language
        for language in KNOWN_LANGUAGES
        if re.search(rf"\b{re.escape(language)}\b", haystack, re.IGNORECASE)
    ]
    # Outside a dedicated section, a lone "English" is too weak a signal.
    if not source and len(found) <= 1:
        return []
    return found[:12]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def parse_resume(text: str) -> ResumeProfile:
    """Parse raw resume text into a structured profile.

    Individual extractors are isolated so a failure degrades one field rather
    than the whole parse.

    Args:
        text: Raw or normalised resume text.

    Returns:
        A populated :class:`ResumeProfile`; empty input yields an empty profile.
    """
    if not text or not text.strip():
        return ResumeProfile(warnings=["The document contained no text."])

    normalized = normalize_whitespace(text)
    profile = ResumeProfile(raw_text=normalized)

    try:
        profile.sections = split_sections(normalized)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Section segmentation failed: %s", exc)
        profile.sections = {}
        profile.warnings.append("Resume sections could not be detected.")

    sections = profile.sections

    extractors: tuple[tuple[str, Callable[[], object]], ...] = (
        ("contact", lambda: extract_contact(normalized)),
        ("skills", lambda: detect_skills(normalized)),
        ("education", lambda: extract_education(normalized, sections)),
        ("experience", lambda: extract_experience(normalized, sections)),
        ("certifications", lambda: extract_certifications(normalized, sections)),
        ("projects", lambda: extract_projects(normalized, sections)),
        ("awards", lambda: extract_awards(normalized, sections)),
        ("achievements", lambda: extract_achievements(normalized, sections)),
        ("languages", lambda: extract_languages(normalized, sections)),
        (
            "total_experience_years",
            lambda: total_experience_years(normalized, sections),
        ),
    )

    for field_name, extractor in extractors:
        try:
            setattr(profile, field_name, extractor())
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Extractor %r failed: %s", field_name, exc)
            profile.warnings.append(f"Could not extract {field_name.replace('_', ' ')}.")

    if not profile.skills:
        profile.warnings.append("No recognised technical skills were detected.")
    if not profile.contact.email:
        profile.warnings.append("No e-mail address found — recruiters need one.")

    logger.info(
        "Parsed resume: %s skills, %s education, %s experience entries.",
        len(profile.skills),
        len(profile.education),
        len(profile.experience),
    )
    return profile

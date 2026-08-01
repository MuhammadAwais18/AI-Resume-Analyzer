"""Recruiter-grade ATS scoring engine.

Commercial applicant tracking systems do not compute a naive keyword
intersection.  They weight *required* skills far above *preferred* ones, check
seniority and education gates, and reward overall document relevance.  This
engine reproduces that behaviour with six transparent, weighted components:

============================  ======  ====================================
Component                     Weight  Measures
============================  ======  ====================================
Required skills                0.35   Weighted coverage of must-have skills
Optional skills                0.10   Coverage of nice-to-have skills
Semantic similarity            0.20   Overall topical alignment
Keyword relevance              0.15   Distinctive job keywords present
Experience match               0.12   Years vs. the stated minimum
Education match                0.08   Degree level vs. the requirement
============================  ======  ====================================

Every component reports its own 0-100 sub-score, so the UI can explain *why*
a resume scored the way it did — the single most requested feature in real
ATS products.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import (
    ATSResult,
    JobRequirements,
    MatchLevel,
    ResumeProfile,
    ScoreComponent,
    Skill,
)
from resume_analyzer.scoring.similarity import keyword_coverage, semantic_similarity
from resume_analyzer.skills.registry import related_skills

logger = get_logger(__name__)

MAX_SCORE: Final[float] = 100.0


#: Below this required-skill coverage a commercial ATS applies a knock-out
#: rule: the candidate cannot rank highly regardless of other strengths.
CRITICAL_COVERAGE_THRESHOLD: Final[float] = 0.30

#: Ceiling applied when the knock-out rule fires.
KNOCKOUT_SCORE_CEILING: Final[float] = 48.0

#: Exponent applied to raw cosine similarity. Resumes are far shorter than
#: postings, so raw cosine is structurally low; the curve maps realistic
#: alignment onto a usable 0-100 range without inflating unrelated documents.
SEMANTIC_CURVE_EXPONENT: Final[float] = 0.55


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    """Relative weights of the scoring components. Must sum to 1.0."""

    required_skills: float = 0.40
    optional_skills: float = 0.10
    semantic: float = 0.15
    keywords: float = 0.13
    experience: float = 0.14
    education: float = 0.08

    def validate(self) -> None:
        """Raise when the weights do not form a convex combination."""
        total = (
            self.required_skills
            + self.optional_skills
            + self.semantic
            + self.keywords
            + self.experience
            + self.education
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total:.4f}")


DEFAULT_WEIGHTS: Final[ScoringWeights] = ScoringWeights()


def _weighted_coverage(
    required: list[Skill], owned: set[str]
) -> tuple[float, list[Skill], list[Skill]]:
    """Compute market-weighted coverage of a skill set.

    Args:
        required: Skills the job asks for.
        owned: Canonical names present in the resume.

    Returns:
        ``(coverage 0-1, matched skills, missing skills)``.
    """
    if not required:
        return 1.0, [], []

    matched = [skill for skill in required if skill.name in owned]
    missing = [skill for skill in required if skill.name not in owned]
    total_weight = sum(skill.weight for skill in required)
    matched_weight = sum(skill.weight for skill in matched)
    coverage = matched_weight / total_weight if total_weight else 0.0
    return coverage, matched, missing


def _experience_score(actual_years: float, required_years: float) -> tuple[float, str]:
    """Score seniority fit and explain it.

    Meeting the bar scores full marks; exceeding it slightly is neutral, and
    being far over it is mildly penalised because recruiters screen out
    over-qualified candidates.
    """
    if required_years <= 0:
        if actual_years <= 0:
            return 70.0, "No explicit requirement; experience not detected."
        return 90.0, f"{actual_years:g} years of experience detected."

    if actual_years <= 0:
        return 25.0, f"Requires {required_years:g} years; none detected in the resume."

    ratio = actual_years / required_years
    if ratio >= 1.0:
        score = 100.0 if ratio <= 2.0 else 92.0
        detail = f"{actual_years:g} years meets the {required_years:g}-year requirement."
    elif ratio >= 0.75:
        score = 80.0
        detail = f"{actual_years:g} years is slightly under the {required_years:g}-year bar."
    elif ratio >= 0.5:
        score = 60.0
        detail = f"{actual_years:g} years is below the {required_years:g}-year requirement."
    else:
        score = 35.0
        detail = f"{actual_years:g} years is well under the {required_years:g}-year bar."
    return score, detail


def _education_score(candidate_rank: int, required_rank: int) -> tuple[float, str]:
    """Score education fit against the required degree level."""
    if required_rank <= 0:
        return (85.0, "No specific degree required.") if candidate_rank else (
            70.0,
            "No degree requirement stated and none detected.",
        )
    if candidate_rank <= 0:
        return 40.0, "A degree is requested but none was detected."
    if candidate_rank >= required_rank:
        return 100.0, "Education requirement satisfied."
    gap = required_rank - candidate_rank
    return max(45.0, 100.0 - gap * 22.0), "Education is below the requested level."


def _highest_education_rank(profile: ResumeProfile) -> int:
    """Return the seniority rank of the candidate's highest degree."""
    from resume_analyzer.parsing.patterns import DEGREE_LEVELS

    ranks = [
        rank
        for entry in profile.education
        for label, rank in DEGREE_LEVELS.values()
        if label == entry.degree
    ]
    if ranks:
        return max(ranks)

    _label, rank = _fallback_education_rank(profile.raw_text)
    return rank


def _fallback_education_rank(text: str) -> tuple[str | None, int]:
    """Scan raw text for a degree when no structured entry was parsed."""
    from resume_analyzer.parsing.resume_parser import education_level

    return education_level(text)


def _build_recommendations(
    result: ATSResult, profile: ResumeProfile, requirements: JobRequirements
) -> list[str]:
    """Produce concrete, deterministic improvement actions."""
    recommendations: list[str] = []

    critical = sorted(
        result.missing_required_skills, key=lambda skill: -skill.weight
    )[:5]
    if critical:
        names = ", ".join(skill.name for skill in critical)
        recommendations.append(
            f"Add evidence of these required skills to your resume: {names}."
        )

    if result.keyword_coverage < 0.5:
        recommendations.append(
            "Mirror more of the job description's exact wording — ATS filters "
            "match on literal keywords before a human ever reads the resume."
        )

    if requirements.min_experience_years > profile.total_experience_years > 0:
        recommendations.append(
            f"The role asks for {requirements.min_experience_years:g} years; make your "
            f"{profile.total_experience_years:g} years more prominent near the top."
        )

    if not profile.contact.linkedin:
        recommendations.append("Add a LinkedIn URL — most recruiters look for it first.")
    if not profile.contact.github and any(
        skill.category.value in {"Programming Languages", "Frameworks"}
        for skill in profile.skills
    ):
        recommendations.append("Add a GitHub link to evidence your engineering work.")

    adjacent = related_skills(profile.skills, limit=4)
    if adjacent:
        recommendations.append(
            "Consider highlighting adjacent technologies you likely use: "
            + ", ".join(adjacent)
            + "."
        )

    if not profile.achievements:
        recommendations.append(
            "Quantify your impact — add metrics such as '%', 'x' or currency "
            "figures to at least three bullet points."
        )

    return recommendations[:7]


def _recruiter_verdict(score: float, missing_required: list[Skill]) -> str:
    """One-sentence screening decision in a recruiter's voice."""
    level = MatchLevel.from_score(score)
    blockers = ", ".join(skill.name for skill in missing_required[:3])

    if level is MatchLevel.EXCELLENT:
        return (
            "Strong shortlist candidate — the resume clears automated screening "
            "and aligns closely with the role."
        )
    if level is MatchLevel.GOOD:
        base = "Likely to pass screening with a solid profile"
        return f"{base}; strengthen coverage of {blockers}." if blockers else f"{base}."
    if level is MatchLevel.FAIR:
        base = "Borderline — an ATS may filter this resume out"
        return f"{base}. Address {blockers} first." if blockers else f"{base}."
    return (
        "Unlikely to pass automated screening for this role. "
        + (f"Critical gaps: {blockers}." if blockers else "Tailor the resume to the posting.")
    )


def score_resume(
    profile: ResumeProfile,
    requirements: JobRequirements,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> ATSResult:
    """Score a resume against a job description.

    Args:
        profile: Parsed resume.
        requirements: Parsed job requirements.
        weights: Component weights; defaults to the tuned production values.

    Returns:
        A fully populated :class:`ATSResult`.
    """
    weights.validate()

    owned = {skill.name for skill in profile.skills}

    required_coverage, matched_required, missing_required = _weighted_coverage(
        requirements.required_skills, owned
    )
    optional_coverage, matched_optional, missing_optional = _weighted_coverage(
        requirements.optional_skills, owned
    )

    semantic = semantic_similarity(profile.raw_text, requirements.raw_text)
    keywords = keyword_coverage(profile.raw_text, requirements.raw_text)

    experience_score, experience_detail = _experience_score(
        profile.total_experience_years, requirements.min_experience_years
    )
    education_score, education_detail = _education_score(
        _highest_education_rank(profile), requirements.required_education_level
    )

    components = [
        ScoreComponent(
            name="Required Skills",
            score=required_coverage * MAX_SCORE,
            weight=weights.required_skills,
            detail=(
                f"{len(matched_required)} of "
                f"{len(requirements.required_skills)} must-have skills matched."
            ),
        ),
        ScoreComponent(
            name="Preferred Skills",
            score=optional_coverage * MAX_SCORE,
            weight=weights.optional_skills,
            detail=(
                f"{len(matched_optional)} of "
                f"{len(requirements.optional_skills)} nice-to-have skills matched."
            ),
        ),
        ScoreComponent(
            name="Semantic Match",
            score=min(MAX_SCORE, (semantic ** SEMANTIC_CURVE_EXPONENT) * MAX_SCORE),
            weight=weights.semantic,
            detail="Overall topical alignment between the resume and the posting.",
        ),
        ScoreComponent(
            name="Keyword Relevance",
            score=min(MAX_SCORE, keywords * 125),
            weight=weights.keywords,
            detail=f"{round(keywords * 100)}% of key job terms appear in the resume.",
        ),
        ScoreComponent(
            name="Experience",
            score=experience_score,
            weight=weights.experience,
            detail=experience_detail,
        ),
        ScoreComponent(
            name="Education",
            score=education_score,
            weight=weights.education,
            detail=education_detail,
        ),
    ]

    overall = sum(component.weighted_score for component in components)

    # Knock-out rule: commercial ATS platforms cap candidates who miss most
    # must-have skills, so strong prose can never mask a hard capability gap.
    if requirements.required_skills and required_coverage < CRITICAL_COVERAGE_THRESHOLD:
        overall = min(overall, KNOCKOUT_SCORE_CEILING)
        logger.info(
            "Knock-out applied: required-skill coverage %.0f%% below threshold.",
            required_coverage * 100,
        )

    overall = max(0.0, min(MAX_SCORE, overall))

    job_skill_names = {skill.name for skill in requirements.all_skills}
    result = ATSResult(
        overall_score=round(overall, 1),
        components=components,
        matched_skills=sorted(
            matched_required + matched_optional, key=lambda skill: -skill.weight
        ),
        missing_skills=sorted(
            missing_required + missing_optional, key=lambda skill: -skill.weight
        ),
        missing_required_skills=missing_required,
        additional_skills=[
            skill for skill in profile.skills if skill.name not in job_skill_names
        ],
        keyword_coverage=round(keywords, 3),
        semantic_similarity=round(semantic, 3),
    )
    result.recruiter_verdict = _recruiter_verdict(overall, missing_required)
    result.recommendations = _build_recommendations(result, profile, requirements)

    logger.info(
        "ATS score %.1f (required %.0f%%, semantic %.2f, keywords %.2f).",
        result.overall_score,
        required_coverage * 100,
        semantic,
        keywords,
    )
    return result


def resume_health_score(profile: ResumeProfile, statistics_words: int) -> float:
    """Rate the resume's intrinsic quality, independent of any job.

    Considers contact completeness, section coverage, quantified impact,
    skill breadth and document length.
    """
    score = 0.0

    score += profile.contact.completeness * 25.0

    expected_sections = {"experience", "education", "skills"}
    present = expected_sections & set(profile.sections)
    score += len(present) / len(expected_sections) * 20.0

    bonus_sections = {"projects", "certifications", "summary", "awards"}
    score += len(bonus_sections & set(profile.sections)) / len(bonus_sections) * 10.0

    score += min(1.0, len(profile.skills) / 15.0) * 20.0
    score += min(1.0, len(profile.achievements) / 5.0) * 15.0

    if 350 <= statistics_words <= 950:
        score += 10.0
    elif 250 <= statistics_words < 350 or 950 < statistics_words <= 1300:
        score += 6.0
    else:
        score += 2.0

    return round(min(MAX_SCORE, score), 1)


def recruiter_readiness(ats: ATSResult, health: float, profile: ResumeProfile) -> float:
    """Blend job fit and resume quality into a screening-readiness score."""
    contactable = 100.0 if profile.contact.email else 50.0
    readiness = 0.55 * ats.overall_score + 0.30 * health + 0.15 * contactable
    return round(min(MAX_SCORE, readiness), 1)

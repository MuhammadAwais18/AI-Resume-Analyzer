"""Framework-agnostic domain models.

These dataclasses are the contract between layers.  They contain no I/O and no
Streamlit imports, which makes them trivial to construct in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from resume_analyzer.config.constants import (
    SCORE_EXCELLENT,
    SCORE_FAIR,
    SCORE_GOOD,
)


class SkillCategory(str, Enum):
    """Top-level taxonomy used to group detected skills."""

    PROGRAMMING_LANGUAGE = "Programming Languages"
    FRAMEWORK = "Frameworks"
    LIBRARY = "Libraries"
    FRONTEND = "Frontend"
    BACKEND = "Backend"
    MOBILE = "Mobile"
    DATABASE = "Databases"
    CLOUD = "Cloud Platforms"
    DEVOPS = "DevOps"
    CONTAINERIZATION = "Containerization"
    DATA_ENGINEERING = "Data Engineering"
    DATA_SCIENCE = "Data Science"
    MACHINE_LEARNING = "Machine Learning"
    DEEP_LEARNING = "Deep Learning"
    NLP = "NLP"
    AI = "AI"
    CYBERSECURITY = "Cybersecurity"
    TESTING = "Testing"
    NETWORKING = "Networking"
    OPERATING_SYSTEM = "Operating Systems"
    VERSION_CONTROL = "Version Control"
    TOOL = "Tools"
    SOFT_SKILL = "Soft Skills"
    OTHER = "Other"


class MatchLevel(str, Enum):
    """Human-readable verdict derived from the overall score."""

    EXCELLENT = "Excellent Match"
    GOOD = "Good Match"
    FAIR = "Partial Match"
    LOW = "Low Match"

    @classmethod
    def from_score(cls, score: float) -> "MatchLevel":
        """Map a 0-100 score onto a verdict."""
        if score >= SCORE_EXCELLENT:
            return cls.EXCELLENT
        if score >= SCORE_GOOD:
            return cls.GOOD
        if score >= SCORE_FAIR:
            return cls.FAIR
        return cls.LOW


@dataclass(frozen=True, slots=True)
class Skill:
    """A single normalised skill detected in a document.

    Attributes:
        name: Canonical display name, e.g. ``"PostgreSQL"``.
        category: Taxonomy bucket the skill belongs to.
        weight: Relative market importance (1.0 = baseline).
        aliases: Alternative spellings that map to this skill.
        matched_alias: The literal token found in the source document.
        occurrences: How many times the skill appeared.
    """

    name: str
    category: SkillCategory = SkillCategory.OTHER
    weight: float = 1.0
    aliases: tuple[str, ...] = ()
    matched_alias: str | None = None
    occurrences: int = 1

    def __str__(self) -> str:
        return self.name


@dataclass(slots=True)
class ContactInfo:
    """Contact and online-presence details extracted from a resume."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    location: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Return the contact fields as a plain dictionary."""
        return {
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "linkedin": self.linkedin,
            "github": self.github,
            "portfolio": self.portfolio,
            "location": self.location,
        }

    @property
    def completeness(self) -> float:
        """Fraction of the seven contact fields that were found (0-1)."""
        values = list(self.as_dict().values())
        return sum(1 for value in values if value) / len(values)


@dataclass(slots=True)
class EducationEntry:
    """A single education record."""

    degree: str
    field_of_study: str | None = None
    institution: str | None = None
    year: str | None = None
    raw_text: str = ""

    def __str__(self) -> str:
        parts = [self.degree]
        if self.field_of_study:
            parts.append(f"in {self.field_of_study}")
        if self.institution:
            parts.append(f"— {self.institution}")
        if self.year:
            parts.append(f"({self.year})")
        return " ".join(parts)


@dataclass(slots=True)
class ExperienceEntry:
    """A single professional experience record."""

    title: str
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    description: str = ""

    def __str__(self) -> str:
        header = self.title if not self.company else f"{self.title} · {self.company}"
        if self.start_date or self.end_date:
            period = f"{self.start_date or '?'} – {self.end_date or 'Present'}"
            return f"{header} ({period})"
        return header


@dataclass(slots=True)
class ResumeProfile:
    """The complete structured view of a parsed resume."""

    raw_text: str = ""
    contact: ContactInfo = field(default_factory=ContactInfo)
    skills: list[Skill] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    experience: list[ExperienceEntry] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    awards: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    total_experience_years: float = 0.0
    sections: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def skill_names(self) -> list[str]:
        """Canonical names of every detected skill."""
        return [skill.name for skill in self.skills]

    def skills_by_category(self) -> dict[str, list[Skill]]:
        """Group detected skills by their taxonomy category."""
        grouped: dict[str, list[Skill]] = {}
        for skill in self.skills:
            grouped.setdefault(skill.category.value, []).append(skill)
        return dict(sorted(grouped.items(), key=lambda item: -len(item[1])))


@dataclass(slots=True)
class JobRequirements:
    """Structured requirements extracted from a job description."""

    raw_text: str = ""
    required_skills: list[Skill] = field(default_factory=list)
    optional_skills: list[Skill] = field(default_factory=list)
    min_experience_years: float = 0.0
    required_education_level: int = 0
    education_label: str | None = None
    title: str | None = None

    @property
    def all_skills(self) -> list[Skill]:
        """Required and optional skills combined."""
        return [*self.required_skills, *self.optional_skills]


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    """One weighted dimension of the overall ATS score."""

    name: str
    score: float
    weight: float
    detail: str = ""

    @property
    def weighted_score(self) -> float:
        """The component's contribution to the final score."""
        return self.score * self.weight


@dataclass(slots=True)
class ATSResult:
    """The full output of the ATS scoring engine."""

    overall_score: float = 0.0
    components: list[ScoreComponent] = field(default_factory=list)
    matched_skills: list[Skill] = field(default_factory=list)
    missing_skills: list[Skill] = field(default_factory=list)
    missing_required_skills: list[Skill] = field(default_factory=list)
    additional_skills: list[Skill] = field(default_factory=list)
    keyword_coverage: float = 0.0
    semantic_similarity: float = 0.0
    recruiter_verdict: str = ""
    recommendations: list[str] = field(default_factory=list)

    @property
    def match_level(self) -> MatchLevel:
        """Verdict derived from :attr:`overall_score`."""
        return MatchLevel.from_score(self.overall_score)

    @property
    def rounded_score(self) -> int:
        """Integer score, matching the value persisted in the database."""
        return int(round(self.overall_score))

    def component_map(self) -> dict[str, float]:
        """Component name to score, useful for charts and reports."""
        return {component.name: component.score for component in self.components}


@dataclass(slots=True)
class AIReview:
    """A structured AI review with graceful-degradation metadata."""

    executive_summary: str = ""
    ats_review: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    recruiter_impression: str = ""
    interview_readiness: str = ""
    resume_rating: float = 0.0
    career_advice: list[str] = field(default_factory=list)
    raw_markdown: str = ""
    is_fallback: bool = False
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """``True`` when the review came from the language model."""
        return not self.is_fallback


@dataclass(slots=True)
class ResumeStatistics:
    """Readability and volume statistics for a resume."""

    words: int = 0
    characters: int = 0
    sentences: int = 0
    unique_words: int = 0
    avg_sentence_length: float = 0.0
    bullet_points: int = 0
    action_verbs: int = 0
    quantified_achievements: int = 0
    estimated_reading_seconds: int = 0

    def as_legacy_dict(self) -> dict[str, int]:
        """Return the original three-key shape used by the v1 report."""
        return {
            "Words": self.words,
            "Characters": self.characters,
            "Sentences": self.sentences,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return every statistic as a plain dictionary."""
        return {
            "Words": self.words,
            "Characters": self.characters,
            "Sentences": self.sentences,
            "Unique Words": self.unique_words,
            "Avg Sentence Length": round(self.avg_sentence_length, 1),
            "Bullet Points": self.bullet_points,
            "Action Verbs": self.action_verbs,
            "Quantified Achievements": self.quantified_achievements,
        }


@dataclass(slots=True)
class AnalysisRecord:
    """A persisted analysis row."""

    id: int | None = None
    resume_name: str = ""
    score: int = 0
    match_level: str = ""
    matched_count: int = 0
    missing_count: int = 0
    experience_years: float = 0.0
    job_title: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class AnalysisResult:
    """Everything a single analysis run produces.

    This is the object the UI renders and the PDF report serialises.
    """

    resume_name: str
    profile: ResumeProfile
    requirements: JobRequirements
    ats: ATSResult
    statistics: ResumeStatistics
    review: AIReview | None = None
    health_score: float = 0.0
    recruiter_readiness: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def score(self) -> int:
        """Integer ATS score for the run."""
        return self.ats.rounded_score

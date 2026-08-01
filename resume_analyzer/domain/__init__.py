"""Domain models shared by every layer of the application."""

from __future__ import annotations

from resume_analyzer.domain.models import (
    AIReview,
    AnalysisRecord,
    AnalysisResult,
    ATSResult,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    JobRequirements,
    MatchLevel,
    ResumeProfile,
    ResumeStatistics,
    ScoreComponent,
    Skill,
    SkillCategory,
)

__all__ = [
    "AIReview",
    "ATSResult",
    "AnalysisRecord",
    "AnalysisResult",
    "ContactInfo",
    "EducationEntry",
    "ExperienceEntry",
    "JobRequirements",
    "MatchLevel",
    "ResumeProfile",
    "ResumeStatistics",
    "ScoreComponent",
    "Skill",
    "SkillCategory",
]

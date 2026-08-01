"""Skill catalog and detection engine."""

from __future__ import annotations

from resume_analyzer.skills.registry import (
    all_skill_names,
    catalog_size,
    detect_skills,
    related_skills,
    resolve,
)

__all__ = [
    "all_skill_names",
    "catalog_size",
    "detect_skills",
    "related_skills",
    "resolve",
]

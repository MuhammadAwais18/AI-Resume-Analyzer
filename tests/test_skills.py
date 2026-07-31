"""Tests for the skill detection engine."""

from __future__ import annotations

from resume_analyzer.skills.registry import (
    catalog_size,
    detect_skills,
    related_skills,
    resolve,
)


def test_detects_common_skills(resume_text: str) -> None:
    names = {skill.name for skill in detect_skills(resume_text)}
    assert {"Python", "Kubernetes", "Docker", "PostgreSQL", "AWS"} <= names


def test_symbol_skills_are_matched() -> None:
    names = {skill.name for skill in detect_skills("Experienced in C++ and C# development")}
    assert "C++" in names
    assert "C#" in names


def test_word_boundaries_prevent_false_positives() -> None:
    names = {skill.name for skill in detect_skills("I used Google to research reactions")}
    assert "Go" not in names
    assert "React" not in names
    assert "R" not in names


def test_synonyms_resolve_to_canonical_names() -> None:
    assert resolve("k8s").name == "Kubernetes"
    assert resolve("postgres").name == "PostgreSQL"
    assert resolve("js").name == "JavaScript"
    assert resolve("golang").name == "Go"


def test_fuzzy_matching_tolerates_typos() -> None:
    match = resolve("kubernets")
    assert match is not None
    assert match.name == "Kubernetes"


def test_unknown_terms_resolve_to_none() -> None:
    assert resolve("quidditch") is None


def test_occurrences_are_counted() -> None:
    skills = {skill.name: skill for skill in detect_skills("Python python PYTHON")}
    assert skills["Python"].occurrences == 3


def test_empty_text_returns_no_skills() -> None:
    assert detect_skills("") == []
    assert detect_skills("   ") == []


def test_related_skills_exclude_owned_ones() -> None:
    detected = detect_skills("I work with Docker every day")
    suggestions = related_skills(detected)
    assert "Kubernetes" in suggestions
    assert "Docker" not in suggestions


def test_catalog_is_populated() -> None:
    assert catalog_size() > 50

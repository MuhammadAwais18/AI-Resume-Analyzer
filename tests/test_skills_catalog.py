"""Tests for the enterprise skill catalog.

These guard the two properties that matter at 500+ skills: **recall** (real
technologies are found across every category) and **precision** (ordinary
English prose does not trigger false skill matches).
"""

from __future__ import annotations

import time

import pytest

from resume_analyzer.domain.models import SkillCategory
from resume_analyzer.skills.catalog import SKILL_CATALOG
from resume_analyzer.skills.registry import (
    RELATED_SKILLS,
    all_skill_names,
    catalog_size,
    detect_skills,
    related_skills,
    resolve,
)

#: The brief requires broad coverage across the technology landscape.
MINIMUM_CATALOG_SIZE = 500


# --------------------------------------------------------------------------
# Catalog integrity
# --------------------------------------------------------------------------


def test_catalog_meets_size_requirement() -> None:
    assert catalog_size() >= MINIMUM_CATALOG_SIZE


def test_catalog_has_no_duplicate_names() -> None:
    names = [spec[0].lower() for spec in SKILL_CATALOG]
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates, f"duplicate canonical names: {sorted(duplicates)}"


def test_weights_are_within_range() -> None:
    for name, _category, weight, _aliases in SKILL_CATALOG:
        assert 0.4 <= weight <= 1.5, f"{name} has an implausible weight {weight}"


def test_aliases_are_lowercase() -> None:
    for name, _category, _weight, aliases in SKILL_CATALOG:
        for alias in aliases:
            assert alias == alias.lower(), f"{name}: alias {alias!r} must be lowercase"


def test_aliases_do_not_collide_across_skills() -> None:
    """One alias must never be claimed by two different canonical skills."""
    owners: dict[str, str] = {}
    collisions: list[str] = []
    for name, _category, _weight, aliases in SKILL_CATALOG:
        for alias in aliases:
            if alias in owners and owners[alias] != name:
                collisions.append(f"{alias!r}: {owners[alias]} vs {name}")
            owners.setdefault(alias, name)
    assert not collisions, f"alias collisions: {collisions}"


@pytest.mark.parametrize(
    "category",
    [
        SkillCategory.PROGRAMMING_LANGUAGE,
        SkillCategory.FRONTEND,
        SkillCategory.BACKEND,
        SkillCategory.DATABASE,
        SkillCategory.CLOUD,
        SkillCategory.DEVOPS,
        SkillCategory.CONTAINERIZATION,
        SkillCategory.MACHINE_LEARNING,
        SkillCategory.DEEP_LEARNING,
        SkillCategory.NLP,
        SkillCategory.AI,
        SkillCategory.DATA_ENGINEERING,
        SkillCategory.DATA_SCIENCE,
        SkillCategory.MOBILE,
        SkillCategory.CYBERSECURITY,
        SkillCategory.TESTING,
        SkillCategory.NETWORKING,
        SkillCategory.OPERATING_SYSTEM,
        SkillCategory.VERSION_CONTROL,
        SkillCategory.TOOL,
        SkillCategory.SOFT_SKILL,
        SkillCategory.FRAMEWORK,
    ],
)
def test_every_required_category_is_populated(category: SkillCategory) -> None:
    assert any(spec[1] is category for spec in SKILL_CATALOG), category.value


# --------------------------------------------------------------------------
# Recall
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill",
    [
        "Python", "Rust", "Kotlin", "Solidity",          # languages
        "React", "Svelte", "WebAssembly",                 # frontend
        "FastAPI", "gRPC", "Apache Kafka",                # backend
        "PostgreSQL", "Snowflake", "Pinecone",            # databases
        "AWS", "Cloudflare", "AWS Lambda",                # cloud
        "Kubernetes", "ArgoCD", "Prometheus",             # devops
        "PyTorch", "Hugging Face", "RAG", "MLOps",        # AI/ML
        "Apache Airflow", "dbt", "Power BI",              # data
        "Flutter", "React Native",                        # mobile
        "Penetration Testing", "Burp Suite", "SIEM",      # security
        "Playwright", "Cypress", "pytest",                # testing
        "Linux", "TCP/IP", "Git",                         # systems
        "Figma", "Jira", "Leadership",                    # tools/soft
    ],
)
def test_key_technologies_are_in_the_catalog(skill: str) -> None:
    assert skill in set(all_skill_names())


def test_detects_skills_across_a_full_resume() -> None:
    text = """TECHNICAL SKILLS
    Languages: Python, Go, TypeScript, Rust
    Cloud: AWS, Kubernetes, Terraform, ArgoCD
    Data: Apache Spark, Airflow, dbt, Snowflake
    AI: PyTorch, Hugging Face, LangChain, RAG
    Security: OWASP, Burp Suite, DevSecOps
    Testing: pytest, Playwright, Cypress
    """
    names = {skill.name for skill in detect_skills(text)}
    assert len(names) >= 15
    assert {"Python", "Kubernetes", "PyTorch", "RAG", "Playwright"} <= names


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("k8s", "Kubernetes"),
        ("postgres", "PostgreSQL"),
        ("js", "JavaScript"),
        ("golang", "Go"),
        ("gcp", "Google Cloud Platform"),
        ("llm", "Large Language Models"),
        ("iac", "Infrastructure as Code"),
        ("tdd", "Test-Driven Development"),
        ("sre", "Site Reliability Engineering"),
        ("oop", "Object-Oriented Programming"),
        ("cicd", "CI/CD"),
        ("nlp", "Natural Language Processing"),
    ],
)
def test_synonyms_resolve(alias: str, canonical: str) -> None:
    match = resolve(alias)
    assert match is not None and match.name == canonical


# --------------------------------------------------------------------------
# Precision
# --------------------------------------------------------------------------


def test_plain_prose_yields_no_false_positives() -> None:
    """Ordinary English must not register as technical skills."""
    prose = """I am a motivated professional who likes to go to the office early.
    I have a car and a cat that likes to sit by the window all day long.
    Our whole team is agile in spirit and we always help each other out.
    The rust on the garden gate needs painting before the winter arrives.
    Please chef the dinner tonight for the family and all of our friends."""
    assert detect_skills(prose) == []


def test_ambiguous_skills_match_in_a_skills_list() -> None:
    names = {skill.name for skill in detect_skills("Skills: Python, Go, Rust, R, Agile")}
    assert {"Go", "Rust", "R", "Agile"} <= names


def test_ambiguous_skills_match_with_technical_context() -> None:
    text = "Built production microservices in Go and systems software in Rust."
    names = {skill.name for skill in detect_skills(text)}
    assert {"Go", "Rust"} <= names


@pytest.mark.parametrize(
    ("text", "absent"),
    [
        ("I used Google to research the topic", "Go"),
        ("The chemical reaction was observed", "React"),
        ("We reviewed the java coffee shop menu prices", "Excel"),
    ],
)
def test_no_substring_false_positives(text: str, absent: str) -> None:
    assert absent not in {skill.name for skill in detect_skills(text)}


# --------------------------------------------------------------------------
# Related skills graph
# --------------------------------------------------------------------------


def test_related_graph_has_no_dangling_references() -> None:
    known = set(all_skill_names())
    dangling = {
        source: [target for target in targets if target not in known]
        for source, targets in RELATED_SKILLS.items()
    }
    dangling = {key: value for key, value in dangling.items() if value}
    assert not dangling, f"unknown related skills: {dangling}"


def test_related_graph_keys_exist() -> None:
    known = set(all_skill_names())
    assert not [source for source in RELATED_SKILLS if source not in known]


def test_related_suggestions_are_relevant() -> None:
    suggestions = related_skills(detect_skills("Skills: Docker"))
    assert "Kubernetes" in suggestions


# --------------------------------------------------------------------------
# Performance
# --------------------------------------------------------------------------


def test_detection_stays_fast_on_a_long_document() -> None:
    """A full two-page resume must scan well under half a second."""
    text = "Python, Kubernetes, Docker, AWS, PyTorch, React, PostgreSQL. " * 60
    detect_skills(text)  # warm the compiled patterns

    start = time.perf_counter()
    detect_skills(text)
    assert time.perf_counter() - start < 0.5

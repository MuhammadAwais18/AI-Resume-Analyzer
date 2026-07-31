"""Shared pytest fixtures.

The database fixture redirects storage to a temporary file so tests never
touch the developer's real history database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project importable when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from resume_analyzer.config.settings import get_settings  # noqa: E402

SAMPLE_RESUME = """
Jane Alexandra Doe
Senior Software Engineer
jane.doe@example.com | +1 (415) 555-0198 | San Francisco, CA
linkedin.com/in/janedoe | github.com/janedoe | janedoe.dev

PROFESSIONAL SUMMARY
Senior engineer with 7 years of experience building distributed systems.

WORK EXPERIENCE
Senior Software Engineer at Stripe                     Jan 2021 - Present
- Reduced p99 latency by 43% by rewriting the ledger service in Go.
- Led migration of 120 microservices to Kubernetes.
Software Engineer, Acme Corp                            Jun 2018 - Dec 2020
- Built REST APIs with Python, Django and PostgreSQL serving 2M requests/day.

EDUCATION
Master of Science in Computer Science - Stanford University (2018)
Bachelor of Science in Software Engineering, MIT 2016

TECHNICAL SKILLS
Python, Go, TypeScript, React, Django, FastAPI, PostgreSQL, Redis, Docker,
Kubernetes, AWS, Terraform, CI/CD, pytest, Git

CERTIFICATIONS
AWS Certified Solutions Architect - Professional
Certified Kubernetes Administrator (CKA)

PROJECTS
Realtime Analytics Engine - Spark and Kafka pipeline processing 4TB/day

AWARDS
Winner, Internal Hackathon 2022

LANGUAGES
English, Spanish, French
"""

SAMPLE_JOB = """
Senior Backend Engineer

We require 5+ years of professional experience.
Must have strong experience with Python, Kubernetes, PostgreSQL and AWS.
Proficiency in Docker and building REST APIs is essential.
Bachelor's degree in Computer Science required.

Nice to have: Terraform, Go and GraphQL exposure.
Familiarity with Rust is a bonus.
"""


@pytest.fixture
def resume_text() -> str:
    """A realistic senior-engineer resume."""
    return SAMPLE_RESUME


@pytest.fixture
def job_text() -> str:
    """A realistic backend job description."""
    return SAMPLE_JOB


@pytest.fixture
def temp_database(tmp_path, monkeypatch) -> Path:
    """Point the repository at a throwaway SQLite file."""
    from resume_analyzer.persistence import repository

    database_path = tmp_path / "test_history.db"
    monkeypatch.setattr(repository, "_database_path", lambda: database_path)
    repository.initialize_database()
    return database_path


@pytest.fixture(autouse=True)
def _clear_caches():
    """Reset memoised state between tests."""
    yield
    get_settings.cache_clear()

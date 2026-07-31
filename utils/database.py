"""Backwards-compatible facade over :mod:`resume_analyzer.persistence`.

The v1 function names and return shapes are preserved: ``get_history`` still
yields ``(resume_name, score, analysis_date)`` tuples.
"""

from __future__ import annotations

from resume_analyzer.domain.models import AnalysisRecord
from resume_analyzer.persistence import repository

__all__ = ["create_database", "save_analysis", "get_history", "DB_PATH"]

#: Kept for compatibility with any code that imported the old constant.
DB_PATH = str(repository._database_path())  # noqa: SLF001 - intentional alias


def create_database() -> None:
    """Create the history table and apply pending migrations."""
    repository.initialize_database()


def save_analysis(resume_name: str, score: int) -> None:
    """Store an analysis result.

    Args:
        resume_name: Uploaded file name.
        score: Integer ATS score between 0 and 100.
    """
    repository.save_record(
        AnalysisRecord(resume_name=resume_name, score=int(score))
    )


def get_history() -> list[tuple[str, int, str]]:
    """Return history rows as ``(resume_name, score, analysis_date)`` tuples."""
    return [
        (
            record.resume_name,
            record.score,
            record.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if record.created_at
            else "",
        )
        for record in repository.fetch_history(limit=200)
    ]

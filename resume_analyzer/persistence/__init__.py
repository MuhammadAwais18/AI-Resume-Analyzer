"""Persistence adapters (SQLite analysis history)."""

from __future__ import annotations

from resume_analyzer.persistence.repository import (
    clear_history,
    fetch_history,
    initialize_database,
    save_record,
    score_timeline,
    summary_statistics,
)

__all__ = [
    "clear_history",
    "fetch_history",
    "initialize_database",
    "save_record",
    "score_timeline",
    "summary_statistics",
]

"""SQLite persistence layer for analysis history and analytics.

Design notes:

* One connection per operation, opened through a context manager so the handle
  is always closed even on failure.
* WAL journaling for concurrent reads while Streamlit reruns the script.
* Idempotent migrations, so an existing v1 database is upgraded in place
  without losing rows.
* Storage failures never crash the app: they raise :class:`StorageError`, and
  the read paths return empty results.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.config.settings import get_settings
from resume_analyzer.domain.models import AnalysisRecord
from resume_analyzer.exceptions import StorageError

logger = get_logger(__name__)

_TABLE: Final[str] = "history"

#: Columns added after v1. Applied with ``ALTER TABLE`` when missing.
_MIGRATIONS: Final[tuple[tuple[str, str], ...]] = (
    ("match_level", "TEXT DEFAULT ''"),
    ("matched_count", "INTEGER DEFAULT 0"),
    ("missing_count", "INTEGER DEFAULT 0"),
    ("experience_years", "REAL DEFAULT 0"),
    ("job_title", "TEXT"),
)


def _database_path() -> Path:
    """Return the configured SQLite file path, creating its directory."""
    settings = get_settings()
    settings.database.ensure_parent()
    return settings.database.path


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection and always close it."""
    settings = get_settings()
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            _database_path(),
            timeout=settings.database.timeout_seconds,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        yield connection
        connection.commit()
    except sqlite3.Error as exc:
        if connection is not None:
            connection.rollback()
        logger.error("Database operation failed: %s", exc)
        raise StorageError(f"sqlite error: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


def initialize_database() -> None:
    """Create the schema and apply pending migrations. Safe to call often."""
    try:
        with _connect() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resume_name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({_TABLE})")
            }
            for column, definition in _MIGRATIONS:
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE {_TABLE} ADD COLUMN {column} {definition}"
                    )
                    logger.info("Applied migration: added column %r.", column)

            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_history_date "
                f"ON {_TABLE}(analysis_date DESC)"
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_history_score ON {_TABLE}(score)"
            )
    except StorageError:
        logger.warning("Database initialisation failed; history is disabled.")


def save_record(record: AnalysisRecord) -> int | None:
    """Persist one analysis run.

    Args:
        record: The record to store; ``id`` and ``created_at`` are assigned by
            the database.

    Returns:
        The new row id, or ``None`` when persistence is unavailable.
    """
    try:
        with _connect() as connection:
            cursor = connection.execute(
                f"""
                INSERT INTO {_TABLE} (
                    resume_name, score, match_level, matched_count,
                    missing_count, experience_years, job_title
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.resume_name,
                    int(record.score),
                    record.match_level,
                    int(record.matched_count),
                    int(record.missing_count),
                    float(record.experience_years),
                    record.job_title,
                ),
            )
            return cursor.lastrowid
    except StorageError:
        return None


def _to_record(row: sqlite3.Row) -> AnalysisRecord:
    """Map a database row onto an :class:`AnalysisRecord`."""
    keys = row.keys()
    raw_date = row["analysis_date"] if "analysis_date" in keys else None
    created_at: datetime | None
    if isinstance(raw_date, datetime):
        created_at = raw_date
    elif isinstance(raw_date, str):
        try:
            created_at = datetime.fromisoformat(raw_date)
        except ValueError:
            created_at = None
    else:
        created_at = None

    def value(name: str, default: Any) -> Any:
        return row[name] if name in keys and row[name] is not None else default

    return AnalysisRecord(
        id=value("id", None),
        resume_name=value("resume_name", ""),
        score=int(value("score", 0)),
        match_level=value("match_level", ""),
        matched_count=int(value("matched_count", 0)),
        missing_count=int(value("missing_count", 0)),
        experience_years=float(value("experience_years", 0.0)),
        job_title=value("job_title", None),
        created_at=created_at,
    )


def fetch_history(
    limit: int = 50,
    *,
    min_score: int | None = None,
    search: str | None = None,
) -> list[AnalysisRecord]:
    """Return recent analyses, newest first.

    Args:
        limit: Maximum number of rows.
        min_score: Optional inclusive lower bound on the score.
        search: Optional case-insensitive substring filter on the file name.

    Returns:
        Matching records, or an empty list when storage is unavailable.
    """
    query = f"SELECT * FROM {_TABLE}"
    clauses: list[str] = []
    params: list[Any] = []

    if min_score is not None:
        clauses.append("score >= ?")
        params.append(int(min_score))
    if search:
        clauses.append("LOWER(resume_name) LIKE ?")
        params.append(f"%{search.lower()}%")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY analysis_date DESC, id DESC LIMIT ?"
    params.append(int(limit))

    try:
        with _connect() as connection:
            return [_to_record(row) for row in connection.execute(query, params)]
    except StorageError:
        return []


def summary_statistics() -> dict[str, Any]:
    """Aggregate history metrics for the dashboard.

    Returns:
        Totals, averages and the best score. All zeros when empty.
    """
    empty = {
        "total_analyses": 0,
        "average_score": 0.0,
        "best_score": 0,
        "latest_score": 0,
        "unique_resumes": 0,
        "trend": 0.0,
    }
    try:
        with _connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total,
                       COALESCE(AVG(score), 0) AS average,
                       COALESCE(MAX(score), 0) AS best,
                       COUNT(DISTINCT resume_name) AS unique_resumes
                FROM {_TABLE}
                """
            ).fetchone()
            if not row or not row["total"]:
                return empty

            recent = [
                item["score"]
                for item in connection.execute(
                    f"SELECT score FROM {_TABLE} "
                    f"ORDER BY analysis_date DESC, id DESC LIMIT 10"
                )
            ]

    except StorageError:
        return empty

    latest = recent[0] if recent else 0
    previous = recent[1:]
    trend = latest - (sum(previous) / len(previous)) if previous else 0.0

    return {
        "total_analyses": int(row["total"]),
        "average_score": round(float(row["average"]), 1),
        "best_score": int(row["best"]),
        "latest_score": int(latest),
        "unique_resumes": int(row["unique_resumes"]),
        "trend": round(float(trend), 1),
    }


def score_timeline(limit: int = 30) -> list[tuple[str, int]]:
    """Return ``(timestamp, score)`` pairs in chronological order for charts."""
    try:
        with _connect() as connection:
            rows = connection.execute(
                f"""
                SELECT analysis_date, score FROM {_TABLE}
                ORDER BY analysis_date DESC, id DESC LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
    except StorageError:
        return []

    return [(str(row["analysis_date"]), int(row["score"])) for row in reversed(rows)]


def clear_history() -> bool:
    """Delete every stored analysis. Returns ``True`` on success."""
    try:
        with _connect() as connection:
            connection.execute(f"DELETE FROM {_TABLE}")
        logger.info("Analysis history cleared.")
        return True
    except StorageError:
        return False

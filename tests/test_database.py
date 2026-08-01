"""Tests for the SQLite persistence layer."""

from __future__ import annotations

from resume_analyzer.domain.models import AnalysisRecord
from resume_analyzer.persistence import repository


def _record(name: str = "resume.pdf", score: int = 80) -> AnalysisRecord:
    return AnalysisRecord(
        resume_name=name,
        score=score,
        match_level="Good Match",
        matched_count=8,
        missing_count=2,
        experience_years=5.0,
        job_title="Backend Engineer",
    )


def test_initialisation_is_idempotent(temp_database) -> None:
    repository.initialize_database()
    repository.initialize_database()
    assert temp_database.exists()


def test_save_and_fetch(temp_database) -> None:
    assert repository.save_record(_record()) is not None
    history = repository.fetch_history()

    assert len(history) == 1
    assert history[0].resume_name == "resume.pdf"
    assert history[0].score == 80
    assert history[0].match_level == "Good Match"
    assert history[0].created_at is not None


def test_history_ordered_newest_first(temp_database) -> None:
    for index in range(3):
        repository.save_record(_record(f"resume{index}.pdf", 70 + index))

    scores = [record.score for record in repository.fetch_history()]
    assert scores == sorted(scores, reverse=True) or len(scores) == 3


def test_history_limit(temp_database) -> None:
    for index in range(10):
        repository.save_record(_record(f"r{index}.pdf", 50 + index))
    assert len(repository.fetch_history(limit=4)) == 4


def test_filter_by_min_score(temp_database) -> None:
    repository.save_record(_record("low.pdf", 30))
    repository.save_record(_record("high.pdf", 95))

    results = repository.fetch_history(min_score=80)
    assert [record.resume_name for record in results] == ["high.pdf"]


def test_search_filter(temp_database) -> None:
    repository.save_record(_record("alice_cv.pdf", 70))
    repository.save_record(_record("bob_cv.pdf", 75))

    results = repository.fetch_history(search="alice")
    assert len(results) == 1
    assert results[0].resume_name == "alice_cv.pdf"


def test_summary_statistics(temp_database) -> None:
    for score in (60, 80, 100):
        repository.save_record(_record(score=score))

    summary = repository.summary_statistics()
    assert summary["total_analyses"] == 3
    assert summary["best_score"] == 100
    assert summary["average_score"] == 80.0


def test_summary_statistics_when_empty(temp_database) -> None:
    summary = repository.summary_statistics()
    assert summary["total_analyses"] == 0
    assert summary["average_score"] == 0.0


def test_score_timeline(temp_database) -> None:
    for score in (55, 65, 75):
        repository.save_record(_record(score=score))

    timeline = repository.score_timeline()
    assert len(timeline) == 3
    assert timeline[-1][1] == 75


def test_clear_history(temp_database) -> None:
    repository.save_record(_record())
    assert repository.clear_history() is True
    assert repository.fetch_history() == []


def test_legacy_v1_database_is_migrated(tmp_path, monkeypatch) -> None:
    """An existing v1 schema must be upgraded in place without data loss."""
    import sqlite3

    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_name TEXT,
            score INTEGER,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute("INSERT INTO history (resume_name, score) VALUES ('old.pdf', 55)")
    connection.commit()
    connection.close()

    monkeypatch.setattr(repository, "_database_path", lambda: database_path)
    repository.initialize_database()

    history = repository.fetch_history()
    assert len(history) == 1
    assert history[0].resume_name == "old.pdf"
    assert history[0].score == 55

    assert repository.save_record(_record("new.pdf", 90)) is not None
    assert len(repository.fetch_history()) == 2

"""Resume readability and quality statistics."""

from __future__ import annotations

from resume_analyzer.domain.models import ResumeStatistics
from resume_analyzer.utils_text import (
    count_action_verbs,
    count_bullets,
    count_quantified_achievements,
    count_sentences,
    reading_time_seconds,
    tokenize,
)


def compute_statistics(text: str) -> ResumeStatistics:
    """Compute volume and quality statistics for a resume.

    Args:
        text: Raw resume text.

    Returns:
        A populated :class:`ResumeStatistics` instance. Empty input yields an
        all-zero object rather than raising.
    """
    if not text or not text.strip():
        return ResumeStatistics()

    words = text.split()
    word_count = len(words)
    sentences = count_sentences(text)

    return ResumeStatistics(
        words=word_count,
        characters=len(text),
        sentences=sentences,
        unique_words=len(set(tokenize(text))),
        avg_sentence_length=word_count / sentences if sentences else 0.0,
        bullet_points=count_bullets(text),
        action_verbs=count_action_verbs(text),
        quantified_achievements=count_quantified_achievements(text),
        estimated_reading_seconds=reading_time_seconds(word_count),
    )

"""Pure text helpers shared by the parsing, scoring and analytics layers.

Keeping these functions free of I/O makes them cheap to unit-test and safe to
memoise.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from functools import lru_cache
from typing import Final

#: Words with no discriminative value when comparing two documents.
STOP_WORDS: Final[frozenset[str]] = frozenset(
    ["a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "of", "to", "in", "on", "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "doing", "have", "has", "had", "having", "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they", "them", "this", "that", "these", "those", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "not", "no", "nor", "so", "than", "too", "very", "just", "about", "above", "after", "again", "against", "all", "also", "am", "any", "because", "before", "below", "between", "both", "during", "each", "few", "further", "here", "how", "into", "more", "most", "only", "other", "out", "over", "own", "same", "some", "such", "through", "under", "until", "up", "while", "who", "whom", "why", "what", "when", "where", "which", "within", "without", "work", "working", "works", "experience", "experienced", "role", "roles", "job", "jobs", "candidate", "candidates", "team", "teams", "ability", "able", "strong", "good", "great", "excellent", "using", "use", "used", "etc", "via", "per"]
)

#: Verbs that signal impact-oriented resume writing.
ACTION_VERBS: Final[frozenset[str]] = frozenset(
    ["achieved", "accelerated", "architected", "automated", "built", "collaborated", "created", "delivered", "designed", "developed", "directed", "drove", "enabled", "engineered", "enhanced", "established", "executed", "expanded", "generated", "implemented", "improved", "increased", "initiated", "introduced", "launched", "led", "maintained", "managed", "migrated", "modernised", "modernized", "negotiated", "optimised", "optimized", "orchestrated", "overhauled", "pioneered", "planned", "produced", "programmed", "reduced", "refactored", "resolved", "restructured", "scaled", "shipped", "simplified", "spearheaded", "standardised", "standardized", "streamlined", "strengthened", "supervised", "transformed", "troubleshot", "mentored", "coached", "owned", "founded"]
)

_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z+#.\-]*")
_SENTENCE_RE: Final[re.Pattern[str]] = re.compile(r"[.!?]+(?:\s|$)")
_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^\s*[•▪◦*\-–—]\s+", re.MULTILINE)
_QUANTIFIED_RE: Final[re.Pattern[str]] = re.compile(
    r"(\d+(?:\.\d+)?\s*%|\$\s?\d[\d,.]*\s*(?:k|m|bn|b|million|billion)?"
    r"|\b\d[\d,]{2,}\b|\b\d+(?:\.\d+)?\s*x\b)",
    re.IGNORECASE,
)
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"[ \t\u00a0]+")
_MULTI_NEWLINE_RE: Final[re.Pattern[str]] = re.compile(r"\n{3,}")

#: Average adult reading speed, used for the "time to read" statistic.
WORDS_PER_MINUTE: Final[int] = 220


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces and blank lines while preserving structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def normalize_token(token: str) -> str:
    """Lowercase and strip punctuation noise from a single token."""
    return token.strip().strip(".,;:()[]{}\"'").lower()


@lru_cache(maxsize=256)
def tokenize(text: str) -> tuple[str, ...]:
    """Return lowercase word tokens for ``text``.

    The result is cached because scoring compares the same documents several
    times within a single analysis run.
    """
    return tuple(match.group().lower() for match in _WORD_RE.finditer(text))


def content_tokens(text: str) -> list[str]:
    """Return meaningful tokens: no stop words, no single characters."""
    return [
        token
        for token in tokenize(text)
        if len(token) > 2 and token not in STOP_WORDS
    ]


def count_sentences(text: str) -> int:
    """Count sentence-terminating punctuation, with a sane minimum."""
    if not text.strip():
        return 0
    return max(1, len(_SENTENCE_RE.findall(text)))


def count_bullets(text: str) -> int:
    """Count bullet-style lines."""
    return len(_BULLET_RE.findall(text))


def count_quantified_achievements(text: str) -> int:
    """Count metrics such as ``35%``, ``$1.2M`` or ``3x``."""
    return len(_QUANTIFIED_RE.findall(text))


def count_action_verbs(text: str) -> int:
    """Count distinct impact verbs used in the document."""
    return len({token for token in tokenize(text) if token in ACTION_VERBS})


def reading_time_seconds(word_count: int) -> int:
    """Estimate reading time in seconds for ``word_count`` words."""
    return int(round(word_count / WORDS_PER_MINUTE * 60))


def truncate(text: str, limit: int, suffix: str = "\n\n[... truncated ...]") -> str:
    """Truncate ``text`` to ``limit`` characters on a word boundary."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = cut.rfind(" ")
    if boundary > limit * 0.8:
        cut = cut[:boundary]
    return cut + suffix


def unique_preserving_order(items: Iterable[str]) -> list[str]:
    """De-duplicate ``items`` case-insensitively while keeping first order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def split_lines(text: str) -> list[str]:
    """Return non-empty, stripped lines."""
    return [line.strip() for line in text.split("\n") if line.strip()]

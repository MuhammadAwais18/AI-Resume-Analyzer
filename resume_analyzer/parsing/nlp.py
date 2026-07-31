"""Optional spaCy integration.

spaCy meaningfully improves person-name and organisation detection, but the
application must never hard-fail when the ``en_core_web_sm`` model is not
installed (fresh clones, slim containers, offline CI).  The pipeline is loaded
lazily, cached, and every consumer degrades to regex heuristics when it is
unavailable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from resume_analyzer.config.logging_config import get_logger

logger = get_logger(__name__)

#: Only the first part of a resume is fed to spaCy — names live at the top and
#: NER over a full document is needlessly expensive.
NER_CHAR_BUDGET = 3_000

_SPACY_MODEL = "en_core_web_sm"


@lru_cache(maxsize=1)
def load_pipeline() -> Any | None:
    """Load and cache the spaCy pipeline, or return ``None`` if unavailable.

    Returns:
        The loaded ``Language`` object, or ``None`` when spaCy or the model is
        not installed. The failure is logged once thanks to the cache.
    """
    try:
        import spacy
    except ImportError:
        logger.info("spaCy is not installed; using regex-only extraction.")
        return None

    try:
        # The parser and lemmatizer are not needed for NER-only usage.
        pipeline = spacy.load(_SPACY_MODEL, disable=["parser", "lemmatizer"])
        logger.info("Loaded spaCy pipeline '%s'.", _SPACY_MODEL)
        return pipeline
    except Exception as exc:  # OSError in practice, but stay defensive.
        logger.info(
            "spaCy model '%s' unavailable (%s); using regex-only extraction.",
            _SPACY_MODEL,
            exc,
        )
        return None


def is_available() -> bool:
    """Return ``True`` when the spaCy pipeline can be used."""
    return load_pipeline() is not None


def extract_entities(text: str, labels: tuple[str, ...]) -> list[str]:
    """Extract named entities of the requested ``labels`` from ``text``.

    Args:
        text: Source text; only the first :data:`NER_CHAR_BUDGET` characters
            are analysed.
        labels: spaCy entity labels to keep, e.g. ``("PERSON",)``.

    Returns:
        Entity strings in document order. Empty when spaCy is unavailable.
    """
    pipeline = load_pipeline()
    if pipeline is None or not text.strip():
        return []

    try:
        doc = pipeline(text[:NER_CHAR_BUDGET])
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("spaCy inference failed: %s", exc)
        return []

    return [entity.text.strip() for entity in doc.ents if entity.label_ in labels]

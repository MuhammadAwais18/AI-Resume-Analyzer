"""Lightweight semantic similarity.

A full transformer embedding model would add hundreds of megabytes to the
deployment for a marginal gain in this use case.  Instead we combine two
classical signals that are fast, dependency-free and deterministic:

* **TF-IDF cosine similarity** over content tokens — captures topical overlap.
* **Weighted Jaccard over bigrams** — captures phrase-level agreement
  (``"machine learning"`` vs. two unrelated mentions of the words).

Both are computed with the standard library only.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, Sequence

from resume_analyzer.utils_text import content_tokens


def _term_frequency(tokens: Sequence[str]) -> dict[str, float]:
    """Sub-linear term frequency, damping repeated keyword stuffing."""
    counts = Counter(tokens)
    return {term: 1.0 + math.log(count) for term, count in counts.items()}


def _inverse_document_frequency(
    documents: Iterable[Sequence[str]], vocabulary: Iterable[str]
) -> dict[str, float]:
    """IDF over the two documents being compared."""
    docs = [set(document) for document in documents]
    total = len(docs) or 1
    return {
        term: math.log((total + 1) / (1 + sum(term in doc for doc in docs))) + 1.0
        for term in vocabulary
    }


def _cosine(vector_a: dict[str, float], vector_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not vector_a or not vector_b:
        return 0.0
    shared = set(vector_a) & set(vector_b)
    numerator = sum(vector_a[term] * vector_b[term] for term in shared)
    norm_a = math.sqrt(sum(value * value for value in vector_a.values()))
    norm_b = math.sqrt(sum(value * value for value in vector_b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return numerator / (norm_a * norm_b)


def _bigrams(tokens: Sequence[str]) -> set[str]:
    """Adjacent token pairs."""
    return {f"{first} {second}" for first, second in zip(tokens, tokens[1:])}


def tfidf_similarity(text_a: str, text_b: str) -> float:
    """Return TF-IDF cosine similarity between two documents (0-1)."""
    tokens_a, tokens_b = content_tokens(text_a), content_tokens(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    vocabulary = set(tokens_a) | set(tokens_b)
    idf = _inverse_document_frequency([tokens_a, tokens_b], vocabulary)

    vector_a = {
        term: value * idf.get(term, 1.0)
        for term, value in _term_frequency(tokens_a).items()
    }
    vector_b = {
        term: value * idf.get(term, 1.0)
        for term, value in _term_frequency(tokens_b).items()
    }
    return _cosine(vector_a, vector_b)


def bigram_similarity(text_a: str, text_b: str) -> float:
    """Return Jaccard similarity over token bigrams (0-1)."""
    bigrams_a = _bigrams(content_tokens(text_a))
    bigrams_b = _bigrams(content_tokens(text_b))
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = len(bigrams_a & bigrams_b)
    union = len(bigrams_a | bigrams_b)
    return intersection / union if union else 0.0


def semantic_similarity(resume_text: str, job_text: str) -> float:
    """Blend the similarity signals into a single 0-1 score.

    The TF-IDF signal dominates; bigram agreement acts as a precision bonus.
    """
    tfidf = tfidf_similarity(resume_text, job_text)
    bigram = bigram_similarity(resume_text, job_text)
    return min(1.0, 0.75 * tfidf + 0.25 * min(1.0, bigram * 4))


def keyword_coverage(resume_text: str, job_text: str, top_n: int = 40) -> float:
    """Fraction of the job's most distinctive keywords present in the resume.

    Args:
        resume_text: Candidate resume text.
        job_text: Job description text.
        top_n: How many of the job's most frequent content words to check.

    Returns:
        Coverage ratio between 0 and 1.
    """
    job_tokens = content_tokens(job_text)
    if not job_tokens:
        return 0.0

    resume_vocabulary = set(content_tokens(resume_text))
    keywords = [term for term, _count in Counter(job_tokens).most_common(top_n)]
    if not keywords:
        return 0.0

    hits = sum(1 for keyword in keywords if keyword in resume_vocabulary)
    return hits / len(keywords)

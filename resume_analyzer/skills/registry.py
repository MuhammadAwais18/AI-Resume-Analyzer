"""Skill detection engine.

The registry compiles the catalog into an alias lookup plus one regular
expression per skill, then reuses those compiled patterns for every document.
Detection is therefore ``O(skills)`` regex scans with no per-call compilation.

Matching rules:

* **Word-boundary aware** — ``"R"`` does not match *react*, ``"Go"`` does not
  match *Google*.
* **Symbol safe** — ``C++`` and ``C#`` are matched literally.
* **Synonym aware** — ``k8s`` resolves to *Kubernetes*, ``postgres`` to
  *PostgreSQL*.
* **Fuzzy fallback** — near-miss spellings resolve via difflib above a
  configurable ratio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable

from resume_analyzer.config.constants import FUZZY_MATCH_THRESHOLD
from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import Skill, SkillCategory
from resume_analyzer.skills.catalog import SKILL_CATALOG, SkillSpec

logger = get_logger(__name__)

#: Skills that commonly travel together, used to suggest adjacent technologies.
RELATED_SKILLS: dict[str, tuple[str, ...]] = {
    "Docker": ("Kubernetes", "CI/CD", "Linux"),
    "Kubernetes": ("Docker", "Terraform", "AWS"),
    "React": ("TypeScript", "Redux", "Next.js"),
    "Next.js": ("React", "TypeScript"),
    "Django": ("Python", "PostgreSQL", "REST API"),
    "Flask": ("Python", "REST API"),
    "FastAPI": ("Python", "REST API", "Docker"),
    "Machine Learning": ("Python", "scikit-learn", "Pandas"),
    "Deep Learning": ("PyTorch", "TensorFlow", "Python"),
    "PyTorch": ("Deep Learning", "Python", "NumPy"),
    "TensorFlow": ("Deep Learning", "Python"),
    "AWS": ("Docker", "Terraform", "Linux"),
    "Terraform": ("AWS", "Kubernetes", "CI/CD"),
    "Pandas": ("NumPy", "Python", "SQL"),
    "Node.js": ("JavaScript", "Express.js", "REST API"),
    "TypeScript": ("JavaScript", "React"),
    "PostgreSQL": ("SQL", "Database Design"),
    "Apache Spark": ("Python", "SQL", "Data Engineering"),
}


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """A catalog entry with its compiled detection pattern."""

    name: str
    category: SkillCategory
    weight: float
    aliases: tuple[str, ...]
    pattern: re.Pattern[str]

    def to_skill(self, matched_alias: str | None = None, occurrences: int = 1) -> Skill:
        """Build an immutable :class:`Skill` from this definition."""
        return Skill(
            name=self.name,
            category=self.category,
            weight=self.weight,
            aliases=self.aliases,
            matched_alias=matched_alias,
            occurrences=occurrences,
        )


def _build_pattern(terms: Iterable[str]) -> re.Pattern[str]:
    """Compile a case-insensitive alternation with smart word boundaries.

    Terms ending in a non-word character (``C++``, ``C#``) get a lookahead
    instead of ``\\b``, because ``\\b`` after ``+`` or ``#`` never matches.
    """
    fragments: list[str] = []
    for term in sorted(set(terms), key=len, reverse=True):
        if not term:
            continue
        escaped = re.escape(term)
        prefix = r"(?<![A-Za-z0-9_])" if term[0].isalnum() else r"(?<!\S)"
        suffix = r"(?![A-Za-z0-9_+#])" if term[-1].isalnum() else r"(?!\S)"
        fragments.append(f"{prefix}{escaped}{suffix}")
    return re.compile("|".join(fragments) if fragments else r"(?!x)x", re.IGNORECASE)


@lru_cache(maxsize=1)
def _definitions() -> tuple[SkillDefinition, ...]:
    """Compile the catalog once per process."""
    definitions: list[SkillDefinition] = []
    for name, category, weight, aliases in _catalog_specs():
        terms = (name, *aliases)
        definitions.append(
            SkillDefinition(
                name=name,
                category=category,
                weight=weight,
                aliases=tuple(aliases),
                pattern=_build_pattern(terms),
            )
        )
    logger.info("Compiled %s skill definitions.", len(definitions))
    return tuple(definitions)


def _catalog_specs() -> tuple[SkillSpec, ...]:
    """Return catalog entries, de-duplicated by canonical name."""
    seen: set[str] = set()
    unique: list[SkillSpec] = []
    for spec in SKILL_CATALOG:
        key = spec[0].lower()
        if key not in seen:
            seen.add(key)
            unique.append(spec)
    return tuple(unique)


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, SkillDefinition]:
    """Map every lowercase alias and canonical name to its definition."""
    index: dict[str, SkillDefinition] = {}
    for definition in _definitions():
        index[definition.name.lower()] = definition
        for alias in definition.aliases:
            index.setdefault(alias.lower(), definition)
    return index


def all_skill_names() -> list[str]:
    """Return every canonical skill name in the catalog."""
    return [definition.name for definition in _definitions()]


def catalog_size() -> int:
    """Number of distinct skills known to the engine."""
    return len(_definitions())


def resolve(term: str, *, fuzzy: bool = True) -> Skill | None:
    """Resolve a free-text term to a canonical skill.

    Args:
        term: Raw text such as ``"k8s"`` or ``"postgress"``.
        fuzzy: Allow approximate matching for near-miss spellings.

    Returns:
        The matching :class:`Skill`, or ``None``.
    """
    key = term.strip().lower()
    if not key:
        return None

    definition = _alias_index().get(key)
    if definition is not None:
        return definition.to_skill(matched_alias=term.strip())

    if not fuzzy or len(key) < 4:
        return None

    best_ratio = FUZZY_MATCH_THRESHOLD
    best: SkillDefinition | None = None
    for alias, candidate in _alias_index().items():
        if abs(len(alias) - len(key)) > 3:
            continue
        ratio = SequenceMatcher(None, key, alias).ratio()
        if ratio > best_ratio:
            best_ratio, best = ratio, candidate

    return best.to_skill(matched_alias=term.strip()) if best else None


def detect_skills(text: str, *, min_occurrences: int = 1) -> list[Skill]:
    """Detect every catalog skill present in ``text``.

    Args:
        text: Document text to scan.
        min_occurrences: Minimum mentions required to report a skill.

    Returns:
        Skills sorted by weight and frequency, highest signal first.
    """
    if not text or not text.strip():
        return []

    found: list[Skill] = []
    for definition in _definitions():
        matches = definition.pattern.findall(text)
        if len(matches) >= min_occurrences:
            first = matches[0]
            alias = first if isinstance(first, str) else definition.name
            found.append(
                definition.to_skill(
                    matched_alias=alias or definition.name,
                    occurrences=len(matches),
                )
            )

    found.sort(key=lambda skill: (-skill.weight, -skill.occurrences, skill.name))
    return found


def related_skills(skills: Iterable[Skill], limit: int = 8) -> list[str]:
    """Suggest adjacent technologies for the supplied skills.

    Args:
        skills: Skills already detected.
        limit: Maximum number of suggestions.

    Returns:
        Canonical names the candidate does not yet list.
    """
    owned = {skill.name for skill in skills}
    suggestions: list[str] = []
    for skill in skills:
        for candidate in RELATED_SKILLS.get(skill.name, ()):
            if candidate not in owned and candidate not in suggestions:
                suggestions.append(candidate)
            if len(suggestions) >= limit:
                return suggestions
    return suggestions

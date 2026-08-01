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
from typing import Final, Iterable

from resume_analyzer.config.constants import FUZZY_MATCH_THRESHOLD
from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import Skill, SkillCategory
from resume_analyzer.skills.catalog import SKILL_CATALOG, SkillSpec

logger = get_logger(__name__)

#: Word splitter used when inspecting the context around an ambiguous match.
_WORD_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"[a-z]+")

#: Skills that commonly travel together in real job postings. Used to suggest
#: adjacent technologies a candidate probably knows but forgot to list.
RELATED_SKILLS: dict[str, tuple[str, ...]] = {
    # Containers, cloud and platform
    "Docker": ("Kubernetes", "CI/CD", "Linux", "Docker Compose"),
    "Kubernetes": ("Docker", "Helm", "Terraform", "Prometheus"),
    "Helm": ("Kubernetes", "ArgoCD"),
    "Terraform": ("AWS", "Kubernetes", "CI/CD", "Infrastructure as Code"),
    "AWS": ("Docker", "Terraform", "Linux", "Amazon S3"),
    "Microsoft Azure": ("Azure DevOps", "Docker", "Terraform"),
    "Google Cloud Platform": ("Kubernetes", "Terraform", "Google BigQuery"),
    "CI/CD": ("GitHub Actions", "Docker", "Test Automation"),
    "GitHub Actions": ("CI/CD", "Docker", "Git"),
    "Prometheus": ("Grafana", "Kubernetes", "Observability"),
    "Site Reliability Engineering": ("Observability", "Kubernetes", "Incident Management"),
    # Frontend
    "React": ("TypeScript", "Redux", "Next.js", "Jest"),
    "Next.js": ("React", "TypeScript", "Vercel"),
    "Vue.js": ("JavaScript", "TypeScript", "Vite"),
    "Angular": ("TypeScript", "REST API", "Jest"),
    "TypeScript": ("JavaScript", "React", "Node.js"),
    "Tailwind CSS": ("CSS", "React", "Design Systems"),
    # Backend
    "Node.js": ("JavaScript", "Express.js", "REST API", "MongoDB"),
    "Django": ("Python", "PostgreSQL", "REST API", "Celery"),
    "Flask": ("Python", "REST API", "PostgreSQL"),
    "FastAPI": ("Python", "REST API", "Docker", "PostgreSQL"),
    "Spring Boot": ("Java", "REST API", "PostgreSQL", "Maven"),
    ".NET": ("C#", "Microsoft SQL Server", "Microsoft Azure"),
    "REST API": ("OpenAPI", "Postman", "JWT"),
    "GraphQL": ("REST API", "Node.js", "TypeScript"),
    "Microservices": ("Docker", "Kubernetes", "Apache Kafka", "System Design"),
    "Apache Kafka": ("Stream Processing", "Microservices", "Java"),
    # Databases
    "PostgreSQL": ("SQL", "Database Design", "Query Optimization"),
    "MySQL": ("SQL", "Database Design"),
    "MongoDB": ("Node.js", "Database Design"),
    "Redis": ("Caching Strategies", "PostgreSQL", "Node.js"),
    "Snowflake": ("SQL", "dbt", "Data Warehousing"),
    # Data
    "Pandas": ("NumPy", "Python", "SQL", "Data Analysis"),
    "NumPy": ("Pandas", "Python", "SciPy"),
    "Apache Spark": ("Python", "SQL", "ETL", "Apache Airflow"),
    "Apache Airflow": ("Python", "ETL", "Data Warehousing"),
    "dbt": ("SQL", "Data Warehousing", "Snowflake"),
    "ETL": ("SQL", "Apache Airflow", "Data Warehousing"),
    "Power BI": ("SQL", "Data Visualization", "Excel"),
    "Tableau": ("SQL", "Data Visualization"),
    # AI / ML
    "Machine Learning": ("Python", "scikit-learn", "Pandas", "Model Deployment"),
    "Deep Learning": ("PyTorch", "TensorFlow", "Python", "CUDA"),
    "PyTorch": ("Deep Learning", "Python", "NumPy", "Hugging Face"),
    "TensorFlow": ("Deep Learning", "Python", "Keras"),
    "scikit-learn": ("Pandas", "NumPy", "Machine Learning"),
    "Natural Language Processing": ("Hugging Face", "Transformers", "Python"),
    "Large Language Models": ("Prompt Engineering", "RAG", "LangChain", "Fine-Tuning"),
    "RAG": ("Embeddings", "Pinecone", "LangChain", "Large Language Models"),
    "LangChain": ("Large Language Models", "RAG", "Python"),
    "MLOps": ("MLflow", "Docker", "Kubernetes", "Model Monitoring"),
    "Computer Vision": ("OpenCV", "PyTorch", "Deep Learning"),
    # Mobile
    "React Native": ("React", "TypeScript", "iOS Development"),
    "Flutter": ("Dart", "Mobile UI Design"),
    "Android Development": ("Kotlin", "Java", "Room Database"),
    "iOS Development": ("Swift", "Core Data"),
    # Security
    "Cybersecurity": ("Network Security", "Penetration Testing", "Cryptography"),
    "Penetration Testing": ("Burp Suite", "Nmap", "Kali Linux"),
    "DevSecOps": ("CI/CD", "SonarQube", "Snyk", "Application Security"),
    # Languages & practices
    "Python": ("Pandas", "pytest", "Django", "SQL"),
    "Java": ("Spring Boot", "Maven", "JUnit"),
    "Go": ("Docker", "Kubernetes", "Microservices"),
    "Rust": ("C++", "WebAssembly", "Go"),
    "SQL": ("PostgreSQL", "Data Analysis", "Query Optimization"),
    "Git": ("GitHub", "Code Review", "CI/CD"),
    "pytest": ("Python", "Test Automation", "Code Coverage"),
    "Test Automation": ("CI/CD", "Selenium", "Playwright"),
    "Agile": ("Scrum", "Jira", "Kanban"),
}


#: Skills whose names are also ordinary English words. Matching them on the
#: bare token alone produces false positives ("go to the office", "the rust on
#: the gate"), so each occurrence must be corroborated by nearby technical
#: context before it is reported.
AMBIGUOUS_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "Go",
        "Rust",
        "R",
        "C",
        "Agile",
        "Chef",
        "Vim",
        "Fiber",
        "Gin",
        "Flux",
        "Less",
        "Dart",
        "Swift",
        "Julia",
        "Phoenix",
        "Linear",
        "Notion",
        "Sketch",
        "Canva",
        "Scheme",
        "Assembly",
        "Communication",
        "Collaboration",
        "Leadership",
        "Adaptability",
        "Statistics",
        "Algorithms",
        "Embeddings",
        "Transformers",
        "Mocking",
        "Refactoring",
        "Waterfall",
        "Kanban",
        "Excel",
        "Mercurial",
    }
)

#: Characters and cues that mark a line as a skills list rather than prose.
_LIST_SEPARATORS: Final[tuple[str, ...]] = (",", "|", "•", "·", "/", ";", "\t")

#: Words that establish an engineering context around an ambiguous token.
_CONTEXT_TERMS: Final[frozenset[str]] = frozenset(
    """
    programming language languages developer development engineer engineering
    software backend frontend fullstack stack framework frameworks library
    libraries tool tools technology technologies technical skills proficient
    proficiency experience expertise knowledge familiar using used build built
    building code coding wrote written implemented developed designed api apis
    application applications service services system systems platform server
    microservices database cloud devops docker kubernetes linux git testing
    deployment production scripting automation data analysis analytics model
    models pipeline pipelines certified certification project projects
    """.split()
)

#: How many characters either side of a match are inspected for context.
_CONTEXT_WINDOW: Final[int] = 90


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


def _has_technical_context(text: str, start: int, end: int) -> bool:
    """Decide whether a match sits in a technical context.

    An ambiguous token counts as a skill when it appears in a delimited list
    (``"Python, Go, Rust"``), in a short line typical of a skills section, or
    near explicit engineering vocabulary.
    """
    window = text[max(0, start - _CONTEXT_WINDOW) : end + _CONTEXT_WINDOW]

    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line = text[line_start : line_end if line_end != -1 else len(text)]

    if any(separator in line for separator in _LIST_SEPARATORS):
        return True
    # Short standalone lines are almost always list items or headings.
    if len(line.strip()) <= 40:
        return True
    return any(term in _CONTEXT_TERMS for term in _WORD_SPLIT_RE.findall(window.lower()))


def detect_skills(text: str, *, min_occurrences: int = 1) -> list[Skill]:
    """Detect every catalog skill present in ``text``.

    Skills whose names are ordinary English words (:data:`AMBIGUOUS_SKILLS`)
    are only reported when corroborated by surrounding technical context, which
    keeps prose such as *"I like to go to the office"* from registering as Go.

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
        matches = list(definition.pattern.finditer(text))
        if not matches:
            continue

        if definition.name in AMBIGUOUS_SKILLS:
            matches = [
                match
                for match in matches
                if _has_technical_context(text, match.start(), match.end())
            ]

        if len(matches) < min_occurrences:
            continue

        found.append(
            definition.to_skill(
                matched_alias=matches[0].group() or definition.name,
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

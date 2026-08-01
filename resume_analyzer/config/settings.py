"""Application configuration.

Configuration is read once, validated, and exposed as an immutable
:class:`Settings` object.  The environment variable names are exactly the ones
already used by the deployed application (``OPENAI_API_KEY``,
``OPENAI_BASE_URL`` and ``MODEL``) and must not be renamed.

Streamlit secrets are consulted as a fallback so the app keeps working on
Streamlit Community Cloud, where secrets are not exported as real environment
variables in every runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv

load_dotenv()

#: Repository root, resolved from this file so it works from any CWD.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: Directory holding the SQLite database and other runtime artefacts.
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"

ENV_API_KEY: Final[str] = "OPENAI_API_KEY"
ENV_BASE_URL: Final[str] = "OPENAI_BASE_URL"
ENV_MODEL: Final[str] = "MODEL"

DEFAULT_BASE_URL: Final[str] = "https://openrouter.ai/api/v1"
DEFAULT_MODEL: Final[str] = "nvidia/nemotron-3-ultra-550b-a55b:free"


def _from_streamlit_secrets(key: str) -> str | None:
    """Return ``key`` from ``st.secrets`` when available, else ``None``.

    Importing Streamlit is deliberately guarded: the configuration layer must
    stay usable from tests, scripts and CI where Streamlit may be absent or
    running outside of a script context.
    """
    try:  # pragma: no cover - depends on the runtime environment
        import streamlit as st

        value = st.secrets.get(key)  # type: ignore[attr-defined]
        return str(value) if value else None
    except Exception:
        return None


def _read(key: str, default: str = "") -> str:
    """Resolve a configuration value from the environment or Streamlit secrets."""
    return (os.getenv(key) or _from_streamlit_secrets(key) or default).strip()


@dataclass(frozen=True, slots=True)
class AISettings:
    """Configuration for the OpenAI-compatible chat completion provider."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = 0.25
    max_tokens: int = 1_600
    timeout_seconds: float = 60.0
    max_retries: int = 2

    @property
    def is_configured(self) -> bool:
        """``True`` when an API key is present and reviews can be requested."""
        return bool(self.api_key)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Configuration for the local SQLite analytics store."""

    path: Path = DATA_DIR / "resume_history.db"
    timeout_seconds: float = 15.0

    def ensure_parent(self) -> None:
        """Create the database directory if it does not exist yet."""
        self.path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class Settings:
    """Root configuration object for the whole application."""

    app_name: str = "AI Resume Analyzer"
    app_icon: str = "📄"
    tagline: str = "Recruiter-grade resume intelligence"
    version: str = "2.0.0"
    log_level: str = "INFO"
    ai: AISettings = field(default_factory=AISettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)

    def public_dict(self) -> dict[str, Any]:
        """Return a redacted view of the settings, safe to log or display."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "log_level": self.log_level,
            "model": self.ai.model,
            "base_url": self.ai.base_url,
            "ai_configured": self.ai.is_configured,
            "database": str(self.database.path),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build (once) and return the application settings singleton."""
    ai = AISettings(
        api_key=_read(ENV_API_KEY),
        base_url=_read(ENV_BASE_URL, DEFAULT_BASE_URL),
        model=_read(ENV_MODEL, DEFAULT_MODEL),
    )
    database = DatabaseSettings(
        path=Path(_read("RESUME_DB_PATH", str(DATA_DIR / "resume_history.db")))
    )
    settings = Settings(
        log_level=_read("LOG_LEVEL", "INFO").upper() or "INFO",
        ai=ai,
        database=database,
    )
    settings.database.ensure_parent()
    return settings

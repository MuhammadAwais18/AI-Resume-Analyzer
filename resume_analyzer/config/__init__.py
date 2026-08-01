"""Configuration, constants and logging for the AI Resume Analyzer."""

from __future__ import annotations

from resume_analyzer.config.logging_config import configure_logging, get_logger
from resume_analyzer.config.settings import (
    DATA_DIR,
    PROJECT_ROOT,
    AISettings,
    DatabaseSettings,
    Settings,
    get_settings,
)

__all__ = [
    "AISettings",
    "DATA_DIR",
    "DatabaseSettings",
    "PROJECT_ROOT",
    "Settings",
    "configure_logging",
    "get_logger",
    "get_settings",
]

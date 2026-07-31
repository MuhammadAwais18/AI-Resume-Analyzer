"""Structured, idempotent logging setup.

Streamlit re-executes the script on every interaction, so ``configure_logging``
must be safe to call repeatedly without stacking duplicate handlers.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

_LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
_ROOT_LOGGER_NAME: Final[str] = "resume_analyzer"
_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Attach a single stream handler to the package logger.

    Args:
        level: Any standard logging level name, e.g. ``"DEBUG"``.
    """
    global _configured
    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if _configured and logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.handlers = [handler]
    logger.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger.

    Args:
        name: Usually ``__name__`` of the calling module.
    """
    if name.startswith(_ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")

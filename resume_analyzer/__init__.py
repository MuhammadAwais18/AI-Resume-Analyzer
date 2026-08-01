"""AI Resume Analyzer — production-grade resume intelligence platform.

The package is organised in layers, from the inside out:

``resume_analyzer.config``
    Immutable settings, tunable constants and logging setup.
``resume_analyzer.domain``
    Framework-agnostic dataclasses that model the business objects.
``resume_analyzer.parsing`` / ``skills`` / ``scoring`` / ``ai``
    Pure services. They accept and return domain objects and never
    import Streamlit.
``resume_analyzer.persistence`` / ``analytics`` / ``reporting``
    Infrastructure adapters (SQLite, statistics, PDF rendering).
``resume_analyzer.ui``
    The only layer allowed to import Streamlit.

Nothing below the ``ui`` package depends on the web framework, which keeps
the core testable and reusable from a CLI, an API or a batch job.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2.0.0"

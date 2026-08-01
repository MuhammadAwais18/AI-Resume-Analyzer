"""Backwards-compatible facade over :mod:`resume_analyzer.ui.charts`.

``create_score_chart`` keeps its v1 signature and still returns a Plotly
figure, now styled for the premium dashboard.
"""

from __future__ import annotations

import plotly.graph_objects as go

from resume_analyzer.ui.charts import score_gauge

__all__ = ["create_score_chart"]


def create_score_chart(score: float) -> go.Figure:
    """Return the ATS score gauge figure.

    Args:
        score: Match score between 0 and 100.

    Returns:
        A Plotly figure ready for ``st.plotly_chart``.
    """
    return score_gauge(score)

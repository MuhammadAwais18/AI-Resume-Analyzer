"""Plotly visualisations styled for the dark dashboard.

Every figure shares :func:`_base_layout`, so spacing, typography and
transparency stay consistent. Figures are transparent-backed and inherit the
page gradient, which is what makes them feel embedded rather than pasted on.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import plotly.graph_objects as go

from resume_analyzer.domain.models import ATSResult, ResumeProfile, ScoreComponent
from resume_analyzer.ui.theme import CHART_SEQUENCE, FONT_STACK, PALETTE, score_color

#: Shared transparent paper/plot styling.
_TRANSPARENT = "rgba(0,0,0,0)"


def _base_layout(height: int, **overrides: Any) -> dict[str, Any]:
    """Return the shared layout dictionary for every figure."""
    layout: dict[str, Any] = {
        "height": height,
        "paper_bgcolor": _TRANSPARENT,
        "plot_bgcolor": _TRANSPARENT,
        "font": {
            "family": FONT_STACK,
            "color": PALETTE.text_secondary,
            "size": 12,
        },
        "margin": {"l": 30, "r": 30, "t": 40, "b": 30},
        "hoverlabel": {
            "bgcolor": PALETTE.bg_elevated,
            "bordercolor": PALETTE.border_strong,
            "font": {"family": FONT_STACK, "color": PALETTE.text_primary, "size": 12},
        },
        "showlegend": False,
    }
    layout.update(overrides)
    return layout


def score_gauge(score: float, title: str = "ATS Match Score") -> go.Figure:
    """Build the headline score gauge.

    Args:
        score: Overall score between 0 and 100.
        title: Caption shown under the number.

    Returns:
        A configured Plotly gauge figure.
    """
    colour = score_color(score)
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={
                "suffix": "<span style='font-size:.8rem;opacity:.5'>/100</span>",
                "font": {"size": 46, "color": colour, "family": FONT_STACK},
            },
            title={
                "text": f"<span style='font-size:.82rem;color:{PALETTE.text_muted};"
                f"letter-spacing:.08em'>{title.upper()}</span>"
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": PALETTE.text_muted,
                    "tickfont": {"size": 10, "color": PALETTE.text_muted},
                },
                "bar": {"color": colour, "thickness": 0.26},
                "bgcolor": _TRANSPARENT,
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40], "color": "rgba(248,113,113,.13)"},
                    {"range": [40, 60], "color": "rgba(251,191,36,.13)"},
                    {"range": [60, 80], "color": "rgba(34,211,238,.13)"},
                    {"range": [80, 100], "color": "rgba(52,211,153,.15)"},
                ],
                "threshold": {
                    "line": {"color": PALETTE.text_primary, "width": 2},
                    "thickness": 0.78,
                    "value": score,
                },
            },
        )
    )
    figure.update_layout(**_base_layout(300, margin={"l": 24, "r": 24, "t": 52, "b": 12}))
    return figure


def progress_ring(value: float, label: str, colour: str | None = None) -> go.Figure:
    """Build a compact circular progress ring.

    Args:
        value: Percentage between 0 and 100.
        label: Caption rendered in the centre.
        colour: Override colour; defaults to the score-based colour.

    Returns:
        A donut figure acting as a progress ring.
    """
    value = max(0.0, min(100.0, float(value)))
    ring_colour = colour or score_color(value)

    figure = go.Figure(
        go.Pie(
            values=[value, 100 - value],
            hole=0.76,
            marker={"colors": [ring_colour, "rgba(255,255,255,.06)"], "line": {"width": 0}},
            textinfo="none",
            hoverinfo="skip",
            sort=False,
            direction="clockwise",
            rotation=0,
        )
    )
    figure.add_annotation(
        text=(
            f"<span style='font-size:1.5rem;font-weight:800;color:{ring_colour}'>"
            f"{value:.0f}</span><br>"
            f"<span style='font-size:.66rem;color:{PALETTE.text_muted};"
            f"letter-spacing:.09em'>{label.upper()}</span>"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"family": FONT_STACK},
    )
    figure.update_layout(**_base_layout(190, margin={"l": 8, "r": 8, "t": 8, "b": 8}))
    return figure


def component_radar(components: Sequence[ScoreComponent]) -> go.Figure:
    """Plot the ATS score components on a radar chart."""
    if not components:
        return _empty_figure("No score components available")

    labels = [component.name for component in components]
    values = [component.score for component in components]
    # Close the polygon so the trace forms a complete shape.
    labels_closed = [*labels, labels[0]]
    values_closed = [*values, values[0]]

    figure = go.Figure(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(99,102,241,.24)",
            line={"color": PALETTE.primary_soft, "width": 2},
            marker={"size": 7, "color": PALETTE.accent},
            hovertemplate="<b>%{theta}</b><br>%{r:.0f}/100<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(360, margin={"l": 60, "r": 60, "t": 40, "b": 40}),
        polar={
            "bgcolor": _TRANSPARENT,
            "radialaxis": {
                "visible": True,
                "range": [0, 100],
                "gridcolor": "rgba(255,255,255,.09)",
                "linecolor": "rgba(255,255,255,.09)",
                "tickfont": {"size": 9, "color": PALETTE.text_muted},
            },
            "angularaxis": {
                "gridcolor": "rgba(255,255,255,.09)",
                "linecolor": "rgba(255,255,255,.12)",
                "tickfont": {"size": 10, "color": PALETTE.text_secondary},
            },
        },
    )
    return figure


def skills_donut(profile: ResumeProfile) -> go.Figure:
    """Show the distribution of detected skills across categories."""
    grouped = profile.skills_by_category()
    if not grouped:
        return _empty_figure("No skills detected")

    top = list(grouped.items())[:8]
    labels = [name for name, _skills in top]
    values = [len(skills) for _name, skills in top]

    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker={
                "colors": list(CHART_SEQUENCE[: len(labels)]),
                "line": {"color": PALETTE.bg_base, "width": 2},
            },
            textinfo="percent",
            textfont={"size": 11, "color": PALETTE.text_primary, "family": FONT_STACK},
            hovertemplate="<b>%{label}</b><br>%{value} skills<extra></extra>",
            sort=True,
        )
    )
    total = sum(values)
    figure.add_annotation(
        text=(
            f"<span style='font-size:1.6rem;font-weight:800;color:{PALETTE.text_primary}'>"
            f"{total}</span><br><span style='font-size:.64rem;color:{PALETTE.text_muted};"
            "letter-spacing:.09em'>SKILLS</span>"
        ),
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"family": FONT_STACK},
    )
    figure.update_layout(
        **_base_layout(
            330,
            margin={"l": 10, "r": 10, "t": 20, "b": 40},
            showlegend=True,
            legend={
                "orientation": "h",
                "y": -0.12,
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 10, "color": PALETTE.text_muted},
            },
        )
    )
    return figure


def component_bars(components: Sequence[ScoreComponent]) -> go.Figure:
    """Horizontal bars comparing each weighted score component."""
    if not components:
        return _empty_figure("No score components available")

    ordered = sorted(components, key=lambda component: component.score)
    names = [component.name for component in ordered]
    values = [component.score for component in ordered]
    colours = [score_color(value) for value in values]
    details = [component.detail for component in ordered]

    figure = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colours, "line": {"width": 0}},
            text=[f"{value:.0f}" for value in values],
            textposition="outside",
            textfont={"size": 11, "color": PALETTE.text_secondary, "family": FONT_STACK},
            customdata=details,
            hovertemplate="<b>%{y}</b><br>%{x:.0f}/100<br>%{customdata}<extra></extra>",
            width=0.62,
        )
    )
    figure.update_layout(
        **_base_layout(320, margin={"l": 10, "r": 40, "t": 20, "b": 30}),
        xaxis={
            "range": [0, 108],
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,.06)",
            "zeroline": False,
            "tickfont": {"size": 10, "color": PALETTE.text_muted},
        },
        yaxis={
            "showgrid": False,
            "tickfont": {"size": 11, "color": PALETTE.text_secondary},
        },
        bargap=0.32,
    )
    return figure


def skills_heatmap(matched: Sequence[str], missing: Sequence[str]) -> go.Figure:
    """Grid heatmap contrasting matched and missing skills."""
    entries = [(name, 1) for name in matched[:18]] + [(name, 0) for name in missing[:18]]
    if not entries:
        return _empty_figure("No skill data to compare")

    columns = 6
    rows = (len(entries) + columns - 1) // columns

    values: list[list[float | None]] = []
    labels: list[list[str]] = []
    for row in range(rows):
        chunk = entries[row * columns : (row + 1) * columns]
        padded = chunk + [("", None)] * (columns - len(chunk))
        values.append([status for _name, status in padded])
        labels.append([name for name, _status in padded])

    figure = go.Figure(
        go.Heatmap(
            z=values,
            text=labels,
            texttemplate="%{text}",
            textfont={"size": 9, "color": PALETTE.text_primary, "family": FONT_STACK},
            colorscale=[[0, "rgba(248,113,113,.34)"], [1, "rgba(52,211,153,.40)"]],
            showscale=False,
            xgap=5,
            ygap=5,
            hovertemplate="<b>%{text}</b><extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(max(180, rows * 52), margin={"l": 8, "r": 8, "t": 16, "b": 8}),
        xaxis={"showticklabels": False, "showgrid": False, "zeroline": False},
        yaxis={
            "showticklabels": False,
            "showgrid": False,
            "zeroline": False,
            "autorange": "reversed",
        },
    )
    return figure


def history_timeline(points: Iterable[tuple[str, int]]) -> go.Figure:
    """Plot score history over time as a filled area chart."""
    data = list(points)
    if len(data) < 2:
        return _empty_figure("Run more analyses to unlock trends")

    timestamps = [str(stamp)[:16] for stamp, _score in data]
    scores = [score for _stamp, score in data]

    figure = go.Figure(
        go.Scatter(
            x=timestamps,
            y=scores,
            mode="lines+markers",
            line={"color": PALETTE.primary_soft, "width": 2.5, "shape": "spline"},
            marker={
                "size": 7,
                "color": [score_color(score) for score in scores],
                "line": {"width": 1.5, "color": PALETTE.bg_base},
            },
            fill="tozeroy",
            fillcolor="rgba(99,102,241,.13)",
            hovertemplate="<b>%{y}/100</b><br>%{x}<extra></extra>",
        )
    )
    figure.update_layout(
        **_base_layout(260, margin={"l": 30, "r": 20, "t": 20, "b": 40}),
        xaxis={
            "showgrid": False,
            "tickfont": {"size": 9, "color": PALETTE.text_muted},
            "nticks": 6,
        },
        yaxis={
            "range": [0, 105],
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,.06)",
            "tickfont": {"size": 10, "color": PALETTE.text_muted},
        },
    )
    return figure


def experience_timeline(profile: ResumeProfile) -> go.Figure:
    """Render career history as a horizontal duration chart."""
    entries = [
        entry
        for entry in profile.experience
        if entry.duration_months and entry.duration_months > 0
    ]
    if not entries:
        return _empty_figure("No dated experience detected")

    labels = [
        (f"{entry.title} · {entry.company}" if entry.company else entry.title)[:42]
        for entry in entries
    ]
    durations = [round((entry.duration_months or 0) / 12, 1) for entry in entries]

    figure = go.Figure(
        go.Bar(
            x=durations,
            y=labels,
            orientation="h",
            marker={
                "color": list(CHART_SEQUENCE[: len(labels)]),
                "line": {"width": 0},
            },
            text=[f"{value:g} yr" for value in durations],
            textposition="outside",
            textfont={"size": 10, "color": PALETTE.text_secondary, "family": FONT_STACK},
            hovertemplate="<b>%{y}</b><br>%{x:g} years<extra></extra>",
            width=0.55,
        )
    )
    figure.update_layout(
        **_base_layout(max(180, len(labels) * 62), margin={"l": 10, "r": 50, "t": 20, "b": 30}),
        xaxis={
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,.06)",
            "zeroline": False,
            "tickfont": {"size": 10, "color": PALETTE.text_muted},
        },
        yaxis={"showgrid": False, "tickfont": {"size": 10, "color": PALETTE.text_secondary}},
        bargap=0.35,
    )
    return figure


def coverage_bars(ats: ATSResult) -> go.Figure:
    """Compare matched, missing and additional skill counts."""
    categories = ["Matched", "Missing", "Additional"]
    values = [
        len(ats.matched_skills),
        len(ats.missing_skills),
        len(ats.additional_skills),
    ]
    colours = [PALETTE.success, PALETTE.danger, PALETTE.accent]

    figure = go.Figure(
        go.Bar(
            x=categories,
            y=values,
            marker={"color": colours, "line": {"width": 0}},
            text=values,
            textposition="outside",
            textfont={"size": 12, "color": PALETTE.text_secondary, "family": FONT_STACK},
            hovertemplate="<b>%{x}</b><br>%{y} skills<extra></extra>",
            width=0.5,
        )
    )
    figure.update_layout(
        **_base_layout(240, margin={"l": 20, "r": 20, "t": 24, "b": 30}),
        xaxis={"showgrid": False, "tickfont": {"size": 11, "color": PALETTE.text_secondary}},
        yaxis={
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,.06)",
            "zeroline": False,
            "tickfont": {"size": 10, "color": PALETTE.text_muted},
        },
    )
    return figure


def _empty_figure(message: str) -> go.Figure:
    """Return a placeholder figure carrying an explanatory message."""
    figure = go.Figure()
    figure.add_annotation(
        text=f"<span style='color:{PALETTE.text_muted};font-size:.86rem'>{message}</span>",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"family": FONT_STACK},
    )
    figure.update_layout(
        **_base_layout(200),
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return figure

"""Reusable presentation components.

Each helper returns an HTML string rather than writing to Streamlit directly.
That keeps them pure, unit-testable and composable — callers decide where the
markup lands. Only :func:`render` touches Streamlit.

All user-supplied values are HTML-escaped: a resume is untrusted input and
must never be able to inject markup into the dashboard.
"""

from __future__ import annotations

from html import escape
from typing import Iterable, Literal

import streamlit as st

from resume_analyzer.ui.theme import score_color

ChipTone = Literal["default", "ok", "bad", "warn", "info"]
VerdictTone = Literal["default", "ok", "warn", "bad"]


def render(html: str) -> None:
    """Write raw HTML into the Streamlit page."""
    st.markdown(html, unsafe_allow_html=True)


def _safe(value: object) -> str:
    """Escape a value for safe HTML interpolation."""
    return escape(str(value), quote=True)


def hero(
    title: str,
    subtitle: str,
    badges: Iterable[tuple[str, str]] = (),
    *,
    live: bool = False,
) -> str:
    """Build the page hero banner.

    Args:
        title: Main headline.
        subtitle: Supporting sentence.
        badges: ``(icon, label)`` pairs rendered as pills.
        live: Show an animated status dot on the first badge.

    Returns:
        HTML markup for the hero section.
    """
    items: list[str] = []
    for index, (icon, label) in enumerate(badges):
        dot = '<span class="ra-badge-dot"></span>' if live and index == 0 else ""
        items.append(
            f'<span class="ra-badge">{dot}{_safe(icon)} {_safe(label)}</span>'
        )
    badge_html = f'<div class="ra-badges">{"".join(items)}</div>' if items else ""

    return (
        '<div class="ra-hero">'
        f'<h1 class="ra-hero-title">{_safe(title)}</h1>'
        f'<p class="ra-hero-sub">{_safe(subtitle)}</p>'
        f"{badge_html}"
        "</div>"
    )


def stat_card(
    label: str,
    value: str,
    *,
    icon: str = "",
    meta: str = "",
    delta: float | None = None,
    progress: float | None = None,
    gradient: bool = False,
    delay: int = 1,
) -> str:
    """Build a statistic card.

    Args:
        label: Small uppercase caption.
        value: The headline figure.
        icon: Optional leading emoji or glyph.
        meta: Secondary caption under the value.
        delta: Optional change indicator; sign selects colour and arrow.
        progress: Optional 0-100 value rendered as a progress bar.
        gradient: Render the value with the brand gradient.
        delay: Stagger index (1-6) for the entrance animation.

    Returns:
        HTML markup for the card.
    """
    parts = [
        f'<div class="ra-stat-label">{_safe(icon)} {_safe(label)}</div>',
        f'<div class="ra-stat-value{" grad" if gradient else ""}">{_safe(value)}</div>',
    ]

    if delta is not None:
        tone = "up" if delta > 0 else "down" if delta < 0 else "flat"
        arrow = "▲" if delta > 0 else "▼" if delta < 0 else "—"
        parts.append(
            f'<div class="ra-delta {tone}">{arrow} {abs(delta):.1f} vs recent average</div>'
        )

    if meta:
        parts.append(f'<div class="ra-stat-meta">{_safe(meta)}</div>')

    if progress is not None:
        width = max(0.0, min(100.0, float(progress)))
        parts.append(
            f'<div class="ra-bar"><div class="ra-bar-fill" style="width:{width:.1f}%"></div></div>'
        )

    return (
        f'<div class="ra-card ra-d{max(1, min(6, delay))}">'
        f'<div class="ra-stat">{"".join(parts)}</div>'
        "</div>"
    )


def card(title: str, body_html: str, *, icon: str = "", delay: int = 1) -> str:
    """Wrap arbitrary HTML in a titled glass card."""
    heading = (
        f'<div class="ra-card-title">{_safe(icon)} {_safe(title)}</div>' if title else ""
    )
    return (
        f'<div class="ra-card ra-d{max(1, min(6, delay))}">{heading}{body_html}</div>'
    )


def chips(labels: Iterable[str], tone: ChipTone = "default", *, limit: int = 0) -> str:
    """Render labels as pill chips.

    Args:
        labels: Text for each chip.
        tone: Visual tone.
        limit: When positive, cap the chips and append a "+N more" pill.

    Returns:
        HTML markup, or an empty-state message when there is nothing to show.
    """
    items = [str(label) for label in labels if str(label).strip()]
    if not items:
        return '<div class="ra-kv-value empty">Nothing detected.</div>'

    overflow = 0
    if limit and len(items) > limit:
        overflow = len(items) - limit
        items = items[:limit]

    css_tone = "" if tone == "default" else f" {tone}"
    html = "".join(f'<span class="ra-chip{css_tone}">{_safe(item)}</span>' for item in items)
    if overflow:
        html += f'<span class="ra-chip">+{overflow} more</span>'
    return f'<div class="ra-chips">{html}</div>'


def key_value(icon: str, label: str, value: str | None) -> str:
    """Render one labelled contact/detail row."""
    if value:
        body = f'<div class="ra-kv-value">{_safe(value)}</div>'
    else:
        body = '<div class="ra-kv-value empty">Not found</div>'
    return (
        '<div class="ra-kv">'
        f'<div class="ra-kv-icon">{_safe(icon)}</div>'
        f'<div class="ra-kv-body"><div class="ra-kv-label">{_safe(label)}</div>{body}</div>'
        "</div>"
    )


def verdict(text: str, tone: VerdictTone = "default") -> str:
    """Render a highlighted verdict or callout block."""
    css_tone = "" if tone == "default" else f" {tone}"
    return f'<div class="ra-verdict{css_tone}">{_safe(text)}</div>'


def verdict_for_score(text: str, score: float) -> str:
    """Render a verdict whose tone is derived from ``score``."""
    if score >= 80:
        tone: VerdictTone = "ok"
    elif score >= 60:
        tone = "default"
    elif score >= 40:
        tone = "warn"
    else:
        tone = "bad"
    return verdict(text, tone)


def timeline(entries: Iterable[tuple[str, str]]) -> str:
    """Render a vertical timeline.

    Args:
        entries: ``(title, meta)`` pairs in display order.

    Returns:
        HTML markup, or an empty-state message.
    """
    items = list(entries)
    if not items:
        return '<div class="ra-kv-value empty">No timeline data available.</div>'

    rows = "".join(
        f'<div class="ra-tl-item ra-d{min(6, index + 1)}">'
        f'<div class="ra-tl-title">{_safe(title)}</div>'
        f'<div class="ra-tl-meta">{_safe(meta)}</div>'
        "</div>"
        for index, (title, meta) in enumerate(items)
    )
    return f'<div class="ra-timeline">{rows}</div>'


def bullet_list(items: Iterable[str], icon: str = "•") -> str:
    """Render a list of insight bullets."""
    entries = [str(item) for item in items if str(item).strip()]
    if not entries:
        return '<div class="ra-kv-value empty">Nothing to show.</div>'
    return "".join(
        f'<div class="ra-kv"><div class="ra-kv-icon">{_safe(icon)}</div>'
        f'<div class="ra-kv-body"><div class="ra-kv-value">{_safe(entry)}</div></div></div>'
        for entry in entries
    )


def score_headline(score: float, level: str) -> str:
    """Render the large ATS score readout with a coloured level pill."""
    colour = score_color(score)
    return (
        '<div class="ra-card ra-d1" style="text-align:center;">'
        f'<div class="ra-stat-label" style="justify-content:center;">🎯 ATS Match Score</div>'
        f'<div style="font-size:3.6rem;font-weight:800;line-height:1;color:{colour};'
        'font-variant-numeric:tabular-nums;letter-spacing:-.04em;">'
        f"{score:.0f}<span style='font-size:1.4rem;opacity:.55;'>/100</span></div>"
        f'<div style="margin-top:.7rem;"><span class="ra-chip" '
        f'style="border-color:{colour}55;background:{colour}1A;color:{colour};">'
        f"{_safe(level)}</span></div>"
        "</div>"
    )


def skeleton(count: int = 3) -> str:
    """Render shimmering placeholders shown while analysis runs."""
    blocks = "".join('<div class="ra-skeleton"></div>' for _ in range(max(1, count)))
    return f'<div style="display:grid;gap:.9rem;">{blocks}</div>'


def section_heading(title: str, subtitle: str = "") -> str:
    """Render a section title with an optional supporting line."""
    sub = (
        f'<p style="margin:.2rem 0 0;font-size:.88rem;color:var(--text-muted);">'
        f"{_safe(subtitle)}</p>"
        if subtitle
        else ""
    )
    return (
        '<div style="margin:2.1rem 0 1rem;">'
        f'<h2 style="margin:0;font-size:1.32rem;font-weight:750;">{_safe(title)}</h2>'
        f"{sub}</div>"
    )

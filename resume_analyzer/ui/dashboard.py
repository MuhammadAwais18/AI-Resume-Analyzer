"""Dashboard views.

Each ``render_*`` function owns one region of the page and receives only the
domain objects it needs. Keeping them small and independent means the layout
can be rearranged without touching business logic.
"""

from __future__ import annotations

from typing import Any, Final

import streamlit as st

from resume_analyzer.config.constants import RESUME_PREVIEW_CHARS
from resume_analyzer.domain.models import AIReview, AnalysisResult, ResumeProfile
from resume_analyzer.persistence import repository
from resume_analyzer.skills.registry import related_skills
from resume_analyzer.ui import charts
from resume_analyzer.ui import components as ui

#: Plotly display config: hide the modebar for a cleaner, product-like feel.
PLOTLY_CONFIG: Final[dict[str, Any]] = {
    "displayModeBar": False,
    "staticPlot": False,
    "responsive": True,
}


def _chart(figure: Any, key: str) -> None:
    """Render a Plotly figure with the shared configuration."""
    st.plotly_chart(figure, use_container_width=True, config=PLOTLY_CONFIG, key=key)


def render_score_overview(result: AnalysisResult) -> None:
    """Render the headline gauge, rings and recruiter verdict."""
    ui.render(ui.section_heading(
        "Analysis Overview",
        f"{result.resume_name} · scored against "
        f"{result.requirements.title or 'the supplied role'}",
    ))

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        _chart(charts.score_gauge(result.score), "gauge")
        ui.render(ui.verdict_for_score(result.ats.recruiter_verdict, result.score))

    with right:
        ring_a, ring_b = st.columns(2)
        with ring_a:
            _chart(
                charts.progress_ring(result.health_score, "Resume Health"),
                "ring_health",
            )
        with ring_b:
            _chart(
                charts.progress_ring(result.recruiter_readiness, "Recruiter Ready"),
                "ring_ready",
            )

        coverage = (
            len(result.ats.matched_skills)
            / max(1, len(result.ats.matched_skills) + len(result.ats.missing_skills))
            * 100
        )
        ui.render(
            ui.stat_card(
                "Skill Coverage",
                f"{coverage:.0f}%",
                icon="🎯",
                meta=(
                    f"{len(result.ats.matched_skills)} matched · "
                    f"{len(result.ats.missing_skills)} missing"
                ),
                progress=coverage,
                delay=2,
            )
        )


def render_kpi_strip(result: AnalysisResult) -> None:
    """Render the four-up KPI cards."""
    statistics = result.statistics
    profile = result.profile

    cards = (
        ui.stat_card(
            "Experience",
            f"{profile.total_experience_years:g}",
            icon="💼",
            meta="years detected",
            delay=1,
        ),
        ui.stat_card(
            "Education",
            profile.education[0].degree if profile.education else "—",
            icon="🎓",
            meta=(
                profile.education[0].field_of_study or "Field not detected"
                if profile.education
                else "No degree detected"
            ),
            delay=2,
        ),
        ui.stat_card(
            "Skills Detected",
            str(len(profile.skills)),
            icon="🛠",
            meta=f"across {len(profile.skills_by_category())} categories",
            gradient=True,
            delay=3,
        ),
        ui.stat_card(
            "Quantified Impact",
            str(statistics.quantified_achievements),
            icon="📈",
            meta=f"{statistics.words} words · {statistics.bullet_points} bullets",
            delay=4,
        ),
    )

    for column, card in zip(st.columns(4, gap="medium"), cards, strict=True):
        with column:
            ui.render(card)


def render_score_breakdown(result: AnalysisResult) -> None:
    """Render the radar and bar breakdown of score components."""
    ui.render(ui.section_heading(
        "Score Breakdown",
        "How each weighted dimension contributed to the final ATS score",
    ))

    left, right = st.columns(2, gap="large")
    with left:
        _chart(charts.component_radar(result.ats.components), "radar")
    with right:
        _chart(charts.component_bars(result.ats.components), "bars")

    rows = "".join(
        ui.key_value(
            "•",
            f"{component.name} — {component.score:.0f}/100 "
            f"(weight {component.weight:.0%})",
            component.detail,
        )
        for component in result.ats.components
    )
    ui.render(ui.card("Component Detail", rows, icon="🧮", delay=2))


def render_skills(result: AnalysisResult) -> None:
    """Render skill matching, distribution and heatmap."""
    ats = result.ats
    ui.render(ui.section_heading(
        "Skill Intelligence",
        "Matched, missing and additional capabilities detected in the resume",
    ))

    left, right = st.columns(2, gap="large")
    with left:
        ui.render(
            ui.card(
                f"Matched Skills ({len(ats.matched_skills)})",
                ui.chips([skill.name for skill in ats.matched_skills], "ok", limit=28),
                icon="✅",
                delay=1,
            )
        )
        ui.render("<div style='height:.9rem'></div>")
        ui.render(
            ui.card(
                f"Additional Strengths ({len(ats.additional_skills)})",
                ui.chips(
                    [skill.name for skill in ats.additional_skills], "info", limit=22
                ),
                icon="💎",
                delay=3,
            )
        )
    with right:
        ui.render(
            ui.card(
                f"Missing Skills ({len(ats.missing_skills)})",
                ui.chips([skill.name for skill in ats.missing_skills], "bad", limit=28),
                icon="⚠️",
                delay=2,
            )
        )
        ui.render("<div style='height:.9rem'></div>")
        suggestions = related_skills(result.profile.skills, limit=10)
        ui.render(
            ui.card(
                "Adjacent Technologies",
                ui.chips(suggestions, "warn")
                if suggestions
                else "<div class='ra-kv-value empty'>No suggestions available.</div>",
                icon="🔗",
                delay=4,
            )
        )

    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        _chart(charts.skills_donut(result.profile), "donut")
    with chart_right:
        _chart(
            charts.skills_heatmap(
                [skill.name for skill in ats.matched_skills],
                [skill.name for skill in ats.missing_skills],
            ),
            "heatmap",
        )


def render_profile(profile: ResumeProfile) -> None:
    """Render the parsed candidate profile, experience and education."""
    ui.render(ui.section_heading(
        "Candidate Profile",
        "Structured data extracted from the uploaded resume",
    ))

    left, middle, right = st.columns(3, gap="large")

    with left:
        contact = profile.contact
        rows = "".join(
            [
                ui.key_value("👤", "Full Name", contact.full_name),
                ui.key_value("📧", "Email", contact.email),
                ui.key_value("📞", "Phone", contact.phone),
                ui.key_value("📍", "Location", contact.location),
                ui.key_value("💼", "LinkedIn", contact.linkedin),
                ui.key_value("🐙", "GitHub", contact.github),
                ui.key_value("🌐", "Portfolio", contact.portfolio),
            ]
        )
        ui.render(ui.card("Contact", rows, icon="📇", delay=1))

    with middle:
        if profile.experience:
            body = "".join(
                ui.key_value(
                    "▸",
                    entry.title,
                    " · ".join(
                        part
                        for part in (
                            entry.company,
                            f"{entry.start_date or '?'} – {entry.end_date or 'Present'}"
                            if entry.start_date or entry.end_date
                            else None,
                        )
                        if part
                    ),
                )
                for entry in profile.experience[:6]
            )
        else:
            body = "<div class='ra-kv-value empty'>No experience entries detected.</div>"
        ui.render(
            ui.card(
                f"Experience · {profile.total_experience_years:g} yrs",
                body,
                icon="💼",
                delay=2,
            )
        )

    with right:
        if profile.education:
            body = "".join(
                ui.key_value("🎓", entry.degree, str(entry).replace(entry.degree, "").strip(" —"))
                for entry in profile.education[:4]
            )
        else:
            body = "<div class='ra-kv-value empty'>No education detected.</div>"
        ui.render(ui.card("Education", body, icon="🎓", delay=3))

    extras = (
        ("📜", "Certifications", profile.certifications),
        ("🚀", "Projects", profile.projects),
        ("🏆", "Awards", profile.awards),
        ("🗣", "Languages", profile.languages),
    )
    visible = [(icon, title, items) for icon, title, items in extras if items]
    if visible:
        for column, (icon, title, items) in zip(
            st.columns(len(visible), gap="medium"), visible, strict=True
        ):
            with column:
                ui.render(
                    ui.card(
                        f"{title} ({len(items)})",
                        ui.chips(items, "info", limit=8),
                        icon=icon,
                        delay=4,
                    )
                )

    if profile.experience:
        _chart(charts.experience_timeline(profile), "exp_timeline")


def render_insights(result: AnalysisResult) -> None:
    """Render deterministic recommendations and parser warnings."""
    ui.render(ui.section_heading(
        "Insights & Recommendations",
        "Prioritised actions derived from the deterministic analysis",
    ))

    left, right = st.columns([1.4, 1], gap="large")
    with left:
        ui.render(
            ui.card(
                "Recommended Actions",
                ui.bullet_list(result.ats.recommendations, icon="→"),
                icon="🎯",
                delay=1,
            )
        )
    with right:
        statistics = result.statistics
        rows = "".join(
            ui.key_value("•", label, str(value))
            for label, value in statistics.as_dict().items()
        )
        ui.render(ui.card("Resume Statistics", rows, icon="📊", delay=2))

        if result.profile.warnings:
            ui.render("<div style='height:.9rem'></div>")
            ui.render(
                ui.card(
                    "Parser Notes",
                    ui.bullet_list(result.profile.warnings, icon="!"),
                    icon="⚠️",
                    delay=3,
                )
            )


def render_ai_review(review: AIReview | None) -> None:
    """Render the AI review across tabbed sections."""
    if review is None:
        return

    ui.render(ui.section_heading(
        "AI Resume Review",
        "Generated by a language model, grounded in the deterministic analysis",
    ))

    if review.is_fallback:
        st.info(
            f"{review.error_message} Showing a detailed review generated from the "
            "local analysis engine instead.",
            icon="ℹ️",
        )

    top_left, top_right = st.columns([2.2, 1], gap="large")
    with top_left:
        ui.render(
            ui.card(
                "Executive Summary",
                f"<div class='ra-kv-value'>{review.executive_summary}</div>",
                icon="📌",
                delay=1,
            )
        )
    with top_right:
        ui.render(
            ui.stat_card(
                "Resume Rating",
                f"{review.resume_rating:g}/10",
                icon="⭐",
                meta="AI assessment" if review.succeeded else "Deterministic estimate",
                progress=review.resume_rating * 10,
                gradient=True,
                delay=2,
            )
        )

    tabs = st.tabs(
        ["💪 Strengths", "⚠️ Weaknesses", "🔧 Improvements", "🧭 Career", "👔 Recruiter"]
    )
    with tabs[0]:
        ui.render(ui.bullet_list(review.strengths, icon="✓"))
    with tabs[1]:
        ui.render(ui.bullet_list(review.weaknesses, icon="!"))
    with tabs[2]:
        ui.render(ui.bullet_list(review.improvements, icon="→"))
    with tabs[3]:
        ui.render(ui.bullet_list(review.career_advice, icon="◆"))
    with tabs[4]:
        ui.render(ui.verdict(review.recruiter_impression or "No impression available."))
        if review.interview_readiness:
            ui.render("<div style='height:.7rem'></div>")
            ui.render(
                ui.card(
                    "Interview Readiness",
                    f"<div class='ra-kv-value'>{review.interview_readiness}</div>",
                    icon="🎤",
                    delay=1,
                )
            )

    if review.ats_review:
        with st.expander("📋 Full ATS commentary"):
            st.write(review.ats_review)


def render_history() -> None:
    """Render history analytics: KPIs, trend chart and recent runs."""
    summary = repository.summary_statistics()
    if not summary["total_analyses"]:
        return

    ui.render(ui.section_heading(
        "History Analytics",
        "Aggregate performance across every analysis on this deployment",
    ))

    cards = (
        ui.stat_card(
            "Total Analyses", str(summary["total_analyses"]), icon="📚", delay=1
        ),
        ui.stat_card(
            "Average Score",
            f"{summary['average_score']:.0f}",
            icon="📊",
            delta=summary["trend"],
            delay=2,
        ),
        ui.stat_card(
            "Best Score",
            str(summary["best_score"]),
            icon="🏆",
            gradient=True,
            delay=3,
        ),
        ui.stat_card(
            "Unique Resumes", str(summary["unique_resumes"]), icon="📄", delay=4
        ),
    )
    for column, card in zip(st.columns(4, gap="medium"), cards, strict=True):
        with column:
            ui.render(card)

    timeline_points = repository.score_timeline(limit=30)
    if len(timeline_points) >= 2:
        _chart(charts.history_timeline(timeline_points), "history")

    records = repository.fetch_history(limit=8)
    if records:
        entries = [
            (
                f"{record.resume_name} — {record.score}/100",
                " · ".join(
                    part
                    for part in (
                        record.match_level or None,
                        f"{record.matched_count} matched"
                        if record.matched_count
                        else None,
                        record.created_at.strftime("%d %b %Y, %H:%M")
                        if record.created_at
                        else None,
                    )
                    if part
                ),
            )
            for record in records
        ]
        ui.render(ui.card("Recent Analyses", ui.timeline(entries), icon="🕑", delay=2))


def render_resume_preview(profile: ResumeProfile) -> None:
    """Render the extracted resume text inside a collapsed expander."""
    with st.expander("📄 Extracted resume text"):
        st.text(profile.raw_text[:RESUME_PREVIEW_CHARS] or "No text extracted.")
        if len(profile.raw_text) > RESUME_PREVIEW_CHARS:
            st.caption(
                f"Showing the first {RESUME_PREVIEW_CHARS:,} of "
                f"{len(profile.raw_text):,} characters."
            )

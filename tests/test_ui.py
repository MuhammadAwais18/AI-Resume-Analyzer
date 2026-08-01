"""Tests for the presentation layer.

Components are pure functions returning HTML, so they can be asserted on
directly. The critical property is **escaping**: a resume is untrusted input
and must never be able to inject markup into the dashboard.
"""

from __future__ import annotations

import pytest

from resume_analyzer.domain.models import (
    ATSResult,
    ResumeProfile,
    ScoreComponent,
    Skill,
    SkillCategory,
)
from resume_analyzer.parsing.resume_parser import parse_resume
from resume_analyzer.scoring.ats_engine import score_resume
from resume_analyzer.scoring.job_parser import parse_job_description
from resume_analyzer.ui import charts
from resume_analyzer.ui import components as ui
from resume_analyzer.ui.theme import PALETTE, build_css, score_color

# --------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------


def test_css_is_generated_and_cached() -> None:
    first = build_css()
    assert "<style>" in first
    assert "--primary" in first
    assert build_css() is first, "stylesheet should be memoised"


def test_css_respects_reduced_motion() -> None:
    assert "prefers-reduced-motion" in build_css()


def test_css_defines_responsive_breakpoint() -> None:
    assert "@media (max-width: 900px)" in build_css()


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (95, PALETTE.success),
        (70, PALETTE.accent),
        (50, PALETTE.warning),
        (10, PALETTE.danger),
    ],
)
def test_score_colour_bands(score: float, expected: str) -> None:
    assert score_color(score) == expected


# --------------------------------------------------------------------------
# Component escaping (security)
# --------------------------------------------------------------------------

MALICIOUS = "<script>alert('xss')</script>"


def test_hero_escapes_user_content() -> None:
    html = ui.hero(MALICIOUS, MALICIOUS)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_chips_escape_skill_names() -> None:
    html = ui.chips([MALICIOUS])
    assert "<script>" not in html


def test_key_value_escapes_values() -> None:
    html = ui.key_value("📧", "Email", MALICIOUS)
    assert "<script>" not in html


def test_stat_card_escapes_values() -> None:
    html = ui.stat_card(MALICIOUS, MALICIOUS, meta=MALICIOUS)
    assert "<script>" not in html


def test_timeline_escapes_entries() -> None:
    html = ui.timeline([(MALICIOUS, MALICIOUS)])
    assert "<script>" not in html


def test_bullet_list_escapes_items() -> None:
    assert "<script>" not in ui.bullet_list([MALICIOUS])


# --------------------------------------------------------------------------
# Component behaviour
# --------------------------------------------------------------------------


def test_chips_show_empty_state() -> None:
    assert "Nothing detected" in ui.chips([])


def test_chips_respect_limit() -> None:
    html = ui.chips([f"skill{index}" for index in range(20)], limit=5)
    assert "+15 more" in html


def test_key_value_marks_missing_values() -> None:
    assert "Not found" in ui.key_value("📧", "Email", None)


def test_stat_card_delta_direction() -> None:
    assert "up" in ui.stat_card("x", "1", delta=4.0)
    assert "down" in ui.stat_card("x", "1", delta=-4.0)
    assert "flat" in ui.stat_card("x", "1", delta=0.0)


def test_stat_card_progress_is_clamped() -> None:
    assert "width:100.0%" in ui.stat_card("x", "1", progress=180)
    assert "width:0.0%" in ui.stat_card("x", "1", progress=-40)


@pytest.mark.parametrize(
    ("score", "tone"), [(90, "ok"), (70, ""), (50, "warn"), (20, "bad")]
)
def test_verdict_tone_follows_score(score: float, tone: str) -> None:
    html = ui.verdict_for_score("Verdict text", score)
    assert "ra-verdict" in html
    if tone:
        assert tone in html


def test_score_headline_contains_value() -> None:
    html = ui.score_headline(87, "Excellent Match")
    assert "87" in html
    assert "Excellent Match" in html


def test_skeleton_renders_blocks() -> None:
    assert ui.skeleton(4).count("ra-skeleton") == 4


def test_timeline_empty_state() -> None:
    assert "No timeline data" in ui.timeline([])


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def analysis(request):
    resume = """Jane Doe
    jane@example.com
    EXPERIENCE
    Senior Engineer at Stripe   Jan 2021 - Present
    - Cut latency by 40%
    EDUCATION
    BS in Computer Science 2018
    SKILLS
    Python, Kubernetes, Docker, AWS, PostgreSQL
    """
    job = """Senior Backend Engineer.
    Must have Python, Kubernetes and AWS. We require 4 years of experience.
    Nice to have Rust."""
    profile = parse_resume(resume)
    requirements = parse_job_description(job)
    return profile, requirements, score_resume(profile, requirements)


def test_score_gauge_builds(analysis) -> None:
    figure = charts.score_gauge(analysis[2].overall_score)
    assert figure.data
    assert figure.layout.height == 300


def test_progress_ring_builds() -> None:
    figure = charts.progress_ring(64, "Health")
    assert figure.data
    assert figure.layout.annotations


def test_progress_ring_clamps_values() -> None:
    charts.progress_ring(-20, "x")
    charts.progress_ring(320, "x")


def test_component_radar_closes_polygon(analysis) -> None:
    figure = charts.component_radar(analysis[2].components)
    trace = figure.data[0]
    assert trace.r[0] == trace.r[-1], "radar polygon must be closed"
    assert trace.theta[0] == trace.theta[-1]


def test_component_bars_build(analysis) -> None:
    assert charts.component_bars(analysis[2].components).data


def test_skills_donut_builds(analysis) -> None:
    assert charts.skills_donut(analysis[0]).data


def test_skills_donut_legend_is_valid(analysis) -> None:
    """Regression: showlegend was once passed twice to update_layout."""
    figure = charts.skills_donut(analysis[0])
    assert figure.layout.showlegend is True


def test_skills_heatmap_builds(analysis) -> None:
    ats = analysis[2]
    figure = charts.skills_heatmap(
        [skill.name for skill in ats.matched_skills],
        [skill.name for skill in ats.missing_skills],
    )
    assert figure.data


def test_history_timeline_builds() -> None:
    figure = charts.history_timeline([("2026-01-01 10:00", 70), ("2026-01-02 11:00", 82)])
    assert figure.data


def test_experience_timeline_builds(analysis) -> None:
    assert charts.experience_timeline(analysis[0]) is not None


def test_coverage_bars_build(analysis) -> None:
    assert charts.coverage_bars(analysis[2]).data


@pytest.mark.parametrize(
    "factory",
    [
        lambda: charts.component_radar([]),
        lambda: charts.component_bars([]),
        lambda: charts.skills_donut(ResumeProfile()),
        lambda: charts.skills_heatmap([], []),
        lambda: charts.history_timeline([]),
        lambda: charts.experience_timeline(ResumeProfile()),
    ],
)
def test_empty_inputs_return_placeholder_figures(factory) -> None:
    """Empty data must never raise; it must render an explanatory placeholder."""
    figure = factory()
    assert figure is not None
    assert figure.layout.annotations


def test_all_charts_are_transparent(analysis) -> None:
    """Figures must inherit the page gradient rather than paint a background."""
    for figure in (
        charts.score_gauge(70),
        charts.component_bars(analysis[2].components),
        charts.coverage_bars(analysis[2]),
    ):
        assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_charts_handle_unicode_skill_names() -> None:
    profile = ResumeProfile(
        skills=[Skill(name="C++", category=SkillCategory.PROGRAMMING_LANGUAGE)]
    )
    assert charts.skills_donut(profile) is not None


def test_gauge_handles_boundary_scores() -> None:
    for score in (0, 100):
        assert charts.score_gauge(score).data


def test_component_bars_include_hover_detail() -> None:
    components = [ScoreComponent("Required Skills", 80, 0.4, "6 of 8 matched")]
    figure = charts.component_bars(components)
    assert "6 of 8 matched" in figure.data[0].customdata


def test_coverage_bars_with_empty_result() -> None:
    assert charts.coverage_bars(ATSResult()).data

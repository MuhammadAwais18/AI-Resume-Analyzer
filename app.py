"""AI Resume Analyzer — Streamlit entry point.

This module is deliberately thin: it wires configuration, session state and
the presentation layer together, then delegates every unit of work to
:mod:`resume_analyzer`. All business logic lives in the package so it stays
testable and reusable outside Streamlit.

Run locally with::

    streamlit run app.py
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from resume_analyzer.config import configure_logging, get_logger, get_settings
from resume_analyzer.config.constants import SUPPORTED_EXTENSIONS
from resume_analyzer.domain.models import AnalysisResult
from resume_analyzer.exceptions import ReportGenerationError, ResumeAnalyzerError
from resume_analyzer.persistence import repository
from resume_analyzer.reporting import build_report
from resume_analyzer.services import analyze_upload
from resume_analyzer.skills.registry import catalog_size
from resume_analyzer.ui import components as ui, dashboard
from resume_analyzer.ui.theme import build_css

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

#: Session-state key holding the most recent analysis.
STATE_RESULT = "analysis_result"

st.set_page_config(
    page_title=f"{settings.app_name} — {settings.tagline}",
    page_icon=settings.app_icon,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"about": f"{settings.app_name} v{settings.version}"},
)


@st.cache_resource(show_spinner=False)
def bootstrap() -> int:
    """Initialise one-time resources and return the skill catalog size.

    Cached with ``st.cache_resource`` so the database migration and the
    compilation of ~570 skill patterns happen once per server process rather
    than on every rerun.
    """
    repository.initialize_database()
    size = catalog_size()
    logger.info("Application bootstrapped: %s", settings.public_dict())
    return size


@st.cache_data(show_spinner=False)
def cached_report(_result: AnalysisResult, cache_key: str) -> bytes:
    """Build the PDF once per analysis.

    Args:
        _result: The analysis to render. Prefixed with an underscore so
            Streamlit does not attempt to hash the dataclass.
        cache_key: Stable identity for the analysis, used as the cache key.

    Returns:
        The report as PDF bytes.
    """
    del cache_key  # Only used for cache identity.
    return build_report(_result)


def render_sidebar(skill_count: int) -> bool:
    """Render the sidebar and return whether AI review is enabled."""
    with st.sidebar:
        ui.render(
            "<div style='padding:.3rem 0 1.1rem;'>"
            "<div style='font-size:1.2rem;font-weight:800;letter-spacing:-.02em;"
            "background:linear-gradient(120deg,#fff,#818CF8);-webkit-background-clip:text;"
            "background-clip:text;-webkit-text-fill-color:transparent;'>"
            f"{settings.app_icon} {settings.app_name}</div>"
            f"<div style='font-size:.76rem;color:var(--text-muted);margin-top:.15rem;'>"
            f"v{settings.version} · {settings.tagline}</div></div>"
        )

        st.markdown("#### Analysis options")
        include_ai = st.toggle(
            "AI resume review",
            value=True,
            help=(
                "Generate a language-model review alongside the deterministic "
                "ATS analysis."
            ),
        )

        if not settings.ai.is_configured:
            st.caption(
                "⚠️ No API key detected — reviews fall back to the local "
                "analysis engine."
            )
        else:
            st.caption(f"🤖 Model: `{settings.ai.model}`")

        st.divider()

        summary = repository.summary_statistics()
        st.markdown("#### Deployment stats")
        left, right = st.columns(2)
        left.metric("Analyses", summary["total_analyses"])
        right.metric("Avg score", f"{summary['average_score']:.0f}")
        st.caption(f"🧠 {skill_count} skills in the detection catalog")

        st.divider()
        with st.expander("How scoring works"):
            st.markdown(
                """
                The ATS score is a weighted blend of six signals:

                | Component | Weight |
                |---|---|
                | Required skills | 40% |
                | Experience | 14% |
                | Semantic match | 15% |
                | Keyword relevance | 13% |
                | Preferred skills | 10% |
                | Education | 8% |

                Candidates missing most must-have skills are capped, mirroring
                how commercial ATS platforms filter hard capability gaps.
                """
            )

        if summary["total_analyses"]:
            st.divider()
            if st.button("Clear history", use_container_width=True):
                repository.clear_history()
                st.session_state.pop(STATE_RESULT, None)
                st.rerun()

    return include_ai


def render_intake() -> tuple[Any, str, bool]:
    """Render the upload and job-description inputs.

    Returns:
        Tuple of ``(uploaded_file, job_description, submitted)``.
    """
    left, right = st.columns([1, 1.35], gap="large")

    with left:
        ui.render(ui.section_heading("1 · Upload resume", "PDF or DOCX, up to 10 MB"))
        uploaded = st.file_uploader(
            "Resume file",
            type=[extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS],
            label_visibility="collapsed",
        )
        if uploaded is not None:
            size_kb = getattr(uploaded, "size", 0) / 1024
            ui.render(
                ui.card(
                    "Selected file",
                    ui.key_value("📄", uploaded.name, f"{size_kb:,.0f} KB"),
                    icon="📎",
                )
            )

    with right:
        ui.render(
            ui.section_heading(
                "2 · Paste job description",
                "The full posting yields the most accurate score",
            )
        )
        job_description = st.text_area(
            "Job description",
            height=230,
            label_visibility="collapsed",
            placeholder=(
                "Paste the complete job posting here — responsibilities, "
                "required skills, preferred skills and experience level…"
            ),
        )

    submitted = st.button("⚡ Analyze resume", type="primary", use_container_width=True)
    return uploaded, job_description, submitted


def run_analysis(uploaded: Any, job_description: str, include_ai: bool) -> None:
    """Execute the pipeline and store the result in session state."""
    placeholder = st.empty()
    with placeholder.container():
        ui.render(ui.skeleton(3))

    try:
        with st.spinner("Parsing resume and scoring against the role…"):
            result, document = analyze_upload(
                uploaded, job_description, include_ai_review=include_ai
            )
    except ResumeAnalyzerError as exc:
        placeholder.empty()
        st.error(exc.user_message, icon="🚫")
        logger.info("Analysis rejected: %s", exc)
        return
    except Exception as exc:  # pragma: no cover - last-resort guard
        placeholder.empty()
        logger.error("Unexpected analysis failure: %s", exc, exc_info=True)
        st.error(
            "Something went wrong while analysing this resume. "
            "Please try again with a different file.",
            icon="🚫",
        )
        return

    placeholder.empty()
    st.session_state[STATE_RESULT] = result

    for warning in document.warnings[:3]:
        st.warning(warning, icon="⚠️")


def render_results(result: AnalysisResult) -> None:
    """Render the full dashboard for a completed analysis."""
    dashboard.render_score_overview(result)
    dashboard.render_kpi_strip(result)
    dashboard.render_score_breakdown(result)
    dashboard.render_skills(result)
    dashboard.render_profile(result.profile)
    dashboard.render_insights(result)
    dashboard.render_ai_review(result.review)

    ui.render(ui.section_heading("Export", "Share a recruiter-ready PDF report"))
    try:
        pdf_bytes = cached_report(
            result, f"{result.resume_name}:{result.created_at.isoformat()}"
        )
        st.download_button(
            "📄 Download PDF report",
            data=pdf_bytes,
            file_name=f"ATS_Report_{result.resume_name.rsplit('.', 1)[0]}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except ReportGenerationError as exc:
        st.error(exc.user_message, icon="🚫")
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Report generation failed: %s", exc, exc_info=True)
        st.error("The PDF report could not be generated.", icon="🚫")

    dashboard.render_resume_preview(result.profile)


def main() -> None:
    """Compose and render the application."""
    ui.render(build_css())
    skill_count = bootstrap()

    include_ai = render_sidebar(skill_count)

    ui.render(
        ui.hero(
            "AI Resume Analyzer",
            "Upload a resume and a job description to receive a recruiter-grade "
            "ATS score, a full skill gap analysis and AI-powered guidance.",
            badges=(
                ("", "Live"),
                ("🧠", f"{skill_count}+ skills"),
                ("⚡", "Weighted ATS engine"),
                ("📄", "PDF export"),
                ("🔒", "Processed in memory"),
            ),
            live=True,
        )
    )

    uploaded, job_description, submitted = render_intake()

    if submitted:
        run_analysis(uploaded, job_description, include_ai)

    result: AnalysisResult | None = st.session_state.get(STATE_RESULT)
    if result is not None:
        render_results(result)
    else:
        dashboard.render_history()


main()

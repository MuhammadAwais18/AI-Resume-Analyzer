"""Professional PDF report generation.

The report is a recruiter-ready document with a branded cover page, an ATS
score breakdown, skill analysis, AI review sections and recommendations.

Design decisions:

* **Pure ReportLab platypus flowables.** No headless browser, no image
  toolchain — the report renders in-process in well under a second and adds
  no deployment dependencies.
* **Charts are drawn as native vector flowables** (:class:`_GaugeFlowable`,
  :class:`_BarChartFlowable`) rather than embedded raster images, so the PDF
  stays small, crisp at any zoom and free of a Kaleido/Chrome dependency.
* **Every user-supplied string is escaped** before it reaches ReportLab's
  mini-HTML parser, so a resume containing ``<b>`` or ``&`` cannot corrupt
  the document.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Final

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from resume_analyzer.config.logging_config import get_logger
from resume_analyzer.domain.models import AIReview, AnalysisResult, ScoreComponent
from resume_analyzer.exceptions import ReportGenerationError

logger = get_logger(__name__)

# --------------------------------------------------------------------------
# Brand palette (print-tuned: the dark UI theme is unreadable on paper)
# --------------------------------------------------------------------------

INK: Final = colors.HexColor("#0F172A")
MUTED: Final = colors.HexColor("#64748B")
LINE: Final = colors.HexColor("#E2E8F0")
PRIMARY: Final = colors.HexColor("#6366F1")
SECONDARY: Final = colors.HexColor("#A855F7")
ACCENT: Final = colors.HexColor("#06B6D4")
SUCCESS: Final = colors.HexColor("#10B981")
WARNING: Final = colors.HexColor("#F59E0B")
DANGER: Final = colors.HexColor("#EF4444")
SURFACE: Final = colors.HexColor("#F8FAFC")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN: Final = 18 * mm
CONTENT_WIDTH: Final = PAGE_WIDTH - 2 * MARGIN


def _score_colour(score: float) -> colors.Color:
    """Return the print colour representing ``score``."""
    if score >= 80:
        return SUCCESS
    if score >= 60:
        return ACCENT
    if score >= 40:
        return WARNING
    return DANGER


def _clean(text: object, limit: int = 2000) -> str:
    """Escape and truncate a value for safe use in a ReportLab paragraph."""
    raw = str(text or "").strip()
    if len(raw) > limit:
        raw = raw[:limit].rsplit(" ", 1)[0] + "…"
    return escape(raw, quote=False).replace("\n", "<br/>")


# --------------------------------------------------------------------------
# Custom vector flowables
# --------------------------------------------------------------------------


class _GaugeFlowable(Flowable):
    """A semicircular score gauge drawn with vector primitives."""

    def __init__(self, score: float, width: float, height: float = 62 * mm):
        super().__init__()
        self.score = max(0.0, min(100.0, float(score)))
        self.width = width
        self.height = height

    def draw(self) -> None:  # noqa: D102 - ReportLab hook
        canvas = self.canv
        centre_x = self.width / 2
        centre_y = 12 * mm
        radius = min(self.width / 2.6, 34 * mm)
        thickness = 9 * mm

        # Track.
        canvas.saveState()
        canvas.setLineWidth(thickness)
        canvas.setLineCap(1)
        canvas.setStrokeColor(colors.HexColor("#E9EDF5"))
        canvas.arc(
            centre_x - radius,
            centre_y - radius,
            centre_x + radius,
            centre_y + radius,
        )
        path = canvas.beginPath()
        path.arc(
            centre_x - radius,
            centre_y - radius,
            centre_x + radius,
            centre_y + radius,
            startAng=0,
            extent=180,
        )
        canvas.drawPath(path, stroke=1, fill=0)

        # Value arc. A zero-extent arc makes ReportLab divide by zero, so the
        # sweep is floored to a hairline for very low scores.
        extent = -180.0 * (self.score / 100.0)
        if abs(extent) >= 0.5:
            canvas.setStrokeColor(_score_colour(self.score))
            value_path = canvas.beginPath()
            value_path.arc(
                centre_x - radius,
                centre_y - radius,
                centre_x + radius,
                centre_y + radius,
                startAng=180,
                extent=extent,
            )
            canvas.drawPath(value_path, stroke=1, fill=0)
        canvas.restoreState()

        # Centre readout.
        canvas.setFillColor(_score_colour(self.score))
        canvas.setFont("Helvetica-Bold", 30)
        canvas.drawCentredString(centre_x, centre_y + 6 * mm, f"{self.score:.0f}")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(centre_x, centre_y + 1 * mm, "OUT OF 100")


class _BarChartFlowable(Flowable):
    """Horizontal bars visualising the weighted score components."""

    ROW_HEIGHT: Final[float] = 11 * mm
    LABEL_WIDTH: Final[float] = 44 * mm

    def __init__(self, components: Sequence[ScoreComponent], width: float):
        super().__init__()
        self.components = list(components)
        self.width = width
        self.height = max(self.ROW_HEIGHT, self.ROW_HEIGHT * len(self.components))

    def draw(self) -> None:  # noqa: D102 - ReportLab hook
        canvas = self.canv
        track_width = self.width - self.LABEL_WIDTH - 16 * mm

        for index, component in enumerate(self.components):
            y = self.height - (index + 1) * self.ROW_HEIGHT + 3 * mm

            canvas.setFillColor(INK)
            canvas.setFont("Helvetica", 8.5)
            canvas.drawString(0, y + 1.2 * mm, component.name[:30])

            canvas.setFillColor(colors.HexColor("#EEF1F7"))
            canvas.roundRect(
                self.LABEL_WIDTH, y, track_width, 5 * mm, 2.5 * mm, stroke=0, fill=1
            )

            filled = track_width * max(0.0, min(100.0, component.score)) / 100.0
            if filled > 0:
                canvas.setFillColor(_score_colour(component.score))
                canvas.roundRect(
                    self.LABEL_WIDTH, y, max(filled, 2 * mm), 5 * mm, 2.5 * mm,
                    stroke=0, fill=1,
                )

            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica-Bold", 8.5)
            canvas.drawRightString(
                self.width, y + 1.2 * mm, f"{component.score:.0f}"
            )


class _DividerFlowable(Flowable):
    """A thin gradient-style rule used between report sections."""

    def __init__(self, width: float, height: float = 2.2):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self) -> None:  # noqa: D102 - ReportLab hook
        segments = 60
        segment_width = self.width / segments
        for index in range(segments):
            ratio = index / segments
            self.canv.setFillColor(
                colors.linearlyInterpolatedColor(PRIMARY, ACCENT, 0, 1, ratio)
            )
            self.canv.rect(
                index * segment_width, 0, segment_width + 0.6, self.height,
                stroke=0, fill=1,
            )


# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the paragraph styles used throughout the report."""
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=30, leading=35, textColor=colors.white, alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontSize=11, leading=16,
            textColor=colors.HexColor("#C7CCFB"), alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16,
            leading=20, textColor=INK, spaceBefore=2, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
            leading=15, textColor=PRIMARY, spaceBefore=10, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=9.5, leading=14.5,
            textColor=INK, alignment=TA_LEFT, spaceAfter=4,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["BodyText"], fontSize=8.5, leading=12,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontSize=9.5, leading=14,
            textColor=INK, leftIndent=10, bulletIndent=2, spaceAfter=3,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=17, leading=20, alignment=TA_CENTER, textColor=INK,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"], fontSize=7, leading=9,
            alignment=TA_CENTER, textColor=MUTED,
        ),
    }


# --------------------------------------------------------------------------
# Page furniture
# --------------------------------------------------------------------------


def _draw_cover_background(canvas: Canvas, _doc: Any) -> None:
    """Paint the full-bleed gradient used on the cover page."""
    canvas.saveState()
    steps = 130
    band = PAGE_HEIGHT / steps
    top = colors.HexColor("#4F46E5")
    bottom = colors.HexColor("#0B1020")
    for index in range(steps):
        canvas.setFillColor(
            colors.linearlyInterpolatedColor(top, bottom, 0, 1, index / steps)
        )
        canvas.rect(0, PAGE_HEIGHT - (index + 1) * band, PAGE_WIDTH, band + 1,
                    stroke=0, fill=1)

    # Decorative translucent circles.
    canvas.setFillColor(colors.HexColor("#8B5CF6"))
    canvas.setFillAlpha(0.16)
    canvas.circle(PAGE_WIDTH * 0.86, PAGE_HEIGHT * 0.87, 52 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#22D3EE"))
    canvas.setFillAlpha(0.13)
    canvas.circle(PAGE_WIDTH * 0.12, PAGE_HEIGHT * 0.22, 40 * mm, stroke=0, fill=1)
    canvas.setFillAlpha(1)
    canvas.restoreState()


def _draw_page_furniture(canvas: Canvas, doc: Any) -> None:
    """Draw the header rule and footer on content pages."""
    canvas.saveState()

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, PAGE_HEIGHT - 13 * mm, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 13 * mm)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 11 * mm, "AI Resume Analyzer · Analysis Report")
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 11 * mm,
        datetime.now().strftime("%d %B %Y"),
    )

    canvas.line(MARGIN, 13 * mm, PAGE_WIDTH - MARGIN, 13 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(MARGIN, 9 * mm, "Generated by AI Resume Analyzer")
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 9 * mm, f"Page {doc.page - 1}")

    canvas.restoreState()


# --------------------------------------------------------------------------
# Section builders
# --------------------------------------------------------------------------


def _kpi_row(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> Table:
    """Build the four-up KPI strip shown under the gauge."""
    cells = [
        (f"{result.score}", "ATS SCORE", _score_colour(result.score)),
        (f"{result.health_score:.0f}", "RESUME HEALTH", _score_colour(result.health_score)),
        (
            f"{result.recruiter_readiness:.0f}",
            "RECRUITER READY",
            _score_colour(result.recruiter_readiness),
        ),
        (f"{len(result.ats.matched_skills)}", "SKILLS MATCHED", PRIMARY),
    ]

    row = []
    for value, label, colour in cells:
        value_style = ParagraphStyle(
            f"kpi_{label}", parent=styles["kpi_value"], textColor=colour
        )
        row.append(
            [Paragraph(value, value_style), Paragraph(label, styles["kpi_label"])]
        )

    table = Table(
        [[Table([cell], style=[("ALIGN", (0, 0), (-1, -1), "CENTER")]) for cell in row]],
        colWidths=[CONTENT_WIDTH / 4.0] * 4,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _skill_table(title: str, skills: Sequence[str], tone: colors.Color) -> Table:
    """Render a skill list as a compact three-column table."""
    if not skills:
        rows = [["—"]]
        widths = [CONTENT_WIDTH]
    else:
        columns = 3
        padded = list(skills) + [""] * ((columns - len(skills) % columns) % columns)
        rows = [padded[i : i + columns] for i in range(0, len(padded), columns)]
        widths = [CONTENT_WIDTH / columns] * columns

    header = Table([[title]], colWidths=[CONTENT_WIDTH])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), tone),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    body = Table(rows, colWidths=widths)
    body.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, SURFACE]),
            ]
        )
    )

    return Table([[header], [body]], colWidths=[CONTENT_WIDTH])


def _bullets(
    items: Iterable[str], styles: dict[str, ParagraphStyle], marker: str = "-"
) -> list[Any]:
    """Render an iterable of strings as bulleted paragraphs."""
    entries = [item for item in items if str(item).strip()]
    if not entries:
        return [Paragraph("None identified.", styles["muted"])]
    return [
        Paragraph(_clean(entry, 400), styles["bullet"], bulletText=marker)
        for entry in entries[:12]
    ]


def _cover_page(result: AnalysisResult, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Build the cover page flowables."""
    profile = result.profile
    candidate = profile.contact.full_name or "Candidate"
    role = result.requirements.title or "Target Role"

    info_rows = [
        ["Candidate", candidate],
        ["Target role", role],
        ["Resume file", result.resume_name],
        ["Generated", result.created_at.strftime("%d %B %Y, %H:%M")],
    ]
    info = Table(info_rows, colWidths=[36 * mm, CONTENT_WIDTH - 36 * mm - 30 * mm])
    info.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#A5B4FC")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#4C51BF")),
            ]
        )
    )

    score = result.score
    return [
        Spacer(1, 46 * mm),
        Paragraph("AI RESUME<br/>ANALYSIS REPORT", styles["cover_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "Recruiter-grade ATS evaluation, skill gap analysis and "
            "AI-generated career guidance",
            styles["cover_sub"],
        ),
        Spacer(1, 20 * mm),
        Paragraph(
            f"<font size='68' color='#FFFFFF'><b>{score}</b></font>"
            f"<font size='18' color='#C7CCFB'>/100</font>",
            ParagraphStyle("big", parent=styles["cover_sub"], alignment=TA_CENTER),
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            f"<b>{_clean(result.ats.match_level.value)}</b>", styles["cover_sub"]
        ),
        Spacer(1, 24 * mm),
        info,
        PageBreak(),
    ]


def _overview_section(
    result: AnalysisResult, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    """Build the score overview and component breakdown."""
    story: list[Any] = [
        Paragraph("Executive Overview", styles["h1"]),
        _DividerFlowable(CONTENT_WIDTH),
        Spacer(1, 6 * mm),
        _GaugeFlowable(result.score, CONTENT_WIDTH),
        Spacer(1, 4 * mm),
        _kpi_row(result, styles),
        Spacer(1, 7 * mm),
        Paragraph("Recruiter Verdict", styles["h2"]),
        Paragraph(_clean(result.ats.recruiter_verdict), styles["body"]),
        Spacer(1, 4 * mm),
        Paragraph("Score Breakdown", styles["h2"]),
        _BarChartFlowable(result.ats.components, CONTENT_WIDTH),
        Spacer(1, 3 * mm),
    ]

    for component in result.ats.components:
        story.append(
            Paragraph(
                f"<b>{_clean(component.name)}</b> "
                f"<font color='#64748B'>(weight {component.weight:.0%})</font> — "
                f"{_clean(component.detail, 220)}",
                styles["muted"],
            )
        )
    return story


def _candidate_section(
    result: AnalysisResult, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    """Build the candidate profile summary."""
    profile = result.profile
    contact = profile.contact
    statistics = result.statistics

    rows = [
        ["Name", contact.full_name or "Not found"],
        ["Email", contact.email or "Not found"],
        ["Phone", contact.phone or "Not found"],
        ["LinkedIn", contact.linkedin or "Not found"],
        ["GitHub", contact.github or "Not found"],
        ["Experience", f"{profile.total_experience_years:g} years"],
        [
            "Education",
            str(profile.education[0]) if profile.education else "Not found",
        ],
        ["Certifications", str(len(profile.certifications))],
        ["Word count", str(statistics.words)],
        ["Quantified achievements", str(statistics.quantified_achievements)],
    ]

    table = Table(
        [[label, _clean(value, 90)] for label, value in rows],
        colWidths=[46 * mm, CONTENT_WIDTH - 46 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                ("TEXTCOLOR", (1, 0), (1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, SURFACE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return [
        Paragraph("Candidate Profile", styles["h1"]),
        _DividerFlowable(CONTENT_WIDTH),
        Spacer(1, 5 * mm),
        table,
    ]


def _skills_section(
    result: AnalysisResult, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    """Build the matched/missing skill analysis."""
    ats = result.ats
    return [
        Paragraph("Skill Analysis", styles["h1"]),
        _DividerFlowable(CONTENT_WIDTH),
        Spacer(1, 5 * mm),
        _skill_table(
            f"MATCHED SKILLS ({len(ats.matched_skills)})",
            [skill.name for skill in ats.matched_skills][:24],
            SUCCESS,
        ),
        Spacer(1, 4 * mm),
        _skill_table(
            f"MISSING SKILLS ({len(ats.missing_skills)})",
            [skill.name for skill in ats.missing_skills][:24],
            DANGER,
        ),
        Spacer(1, 4 * mm),
        _skill_table(
            f"ADDITIONAL STRENGTHS ({len(ats.additional_skills)})",
            [skill.name for skill in ats.additional_skills][:18],
            ACCENT,
        ),
    ]


def _review_section(
    review: AIReview | None, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    """Build the AI review section."""
    if review is None:
        return []

    story: list[Any] = [
        Paragraph("AI Review", styles["h1"]),
        _DividerFlowable(CONTENT_WIDTH),
        Spacer(1, 5 * mm),
    ]

    if review.is_fallback:
        story.append(
            Paragraph(
                "<i>Generated from deterministic analysis — the AI service was "
                "unavailable for this run.</i>",
                styles["muted"],
            )
        )
        story.append(Spacer(1, 3 * mm))

    if review.executive_summary:
        story += [
            Paragraph("Executive Summary", styles["h2"]),
            Paragraph(_clean(review.executive_summary), styles["body"]),
        ]
    if review.ats_review:
        story += [
            Paragraph("ATS Review", styles["h2"]),
            Paragraph(_clean(review.ats_review), styles["body"]),
        ]

    for heading, items in (
        ("Strengths", review.strengths),
        ("Weaknesses", review.weaknesses),
        ("Improvement Suggestions", review.improvements),
    ):
        if items:
            story.append(Paragraph(heading, styles["h2"]))
            story.extend(_bullets(items, styles))

    if review.recruiter_impression:
        story += [
            Paragraph("Recruiter Impression", styles["h2"]),
            Paragraph(_clean(review.recruiter_impression), styles["body"]),
        ]
    if review.interview_readiness:
        story += [
            Paragraph("Interview Readiness", styles["h2"]),
            Paragraph(_clean(review.interview_readiness), styles["body"]),
        ]
    if review.resume_rating:
        story += [
            Paragraph("Resume Rating", styles["h2"]),
            Paragraph(
                f"<font size='15'><b>{review.resume_rating:g}</b></font>"
                "<font color='#64748B'> / 10</font>",
                styles["body"],
            ),
        ]
    if review.career_advice:
        story.append(Paragraph("Career Advice", styles["h2"]))
        story.extend(_bullets(review.career_advice, styles, marker="–"))

    return story


def _recommendations_section(
    result: AnalysisResult, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    """Build the prioritised action list."""
    return [
        Paragraph("Recommended Actions", styles["h1"]),
        _DividerFlowable(CONTENT_WIDTH),
        Spacer(1, 5 * mm),
        *_bullets(result.ats.recommendations, styles, marker="–"),
    ]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def build_report(result: AnalysisResult) -> bytes:
    """Render a full analysis report as PDF bytes.

    Args:
        result: The completed analysis to serialise.

    Returns:
        The PDF document as bytes.

    Raises:
        ReportGenerationError: The document could not be produced.
    """
    buffer = BytesIO()
    styles = _build_styles()

    try:
        document = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title="AI Resume Analysis Report",
            author="AI Resume Analyzer",
            subject=f"ATS analysis for {result.resume_name}",
        )

        cover_frame = Frame(
            MARGIN, MARGIN, CONTENT_WIDTH, PAGE_HEIGHT - 2 * MARGIN, id="cover"
        )
        content_frame = Frame(
            MARGIN,
            MARGIN + 6 * mm,
            CONTENT_WIDTH,
            PAGE_HEIGHT - 2 * MARGIN - 12 * mm,
            id="content",
        )
        document.addPageTemplates(
            [
                PageTemplate(id="Cover", frames=[cover_frame],
                             onPage=_draw_cover_background),
                PageTemplate(id="Content", frames=[content_frame],
                             onPage=_draw_page_furniture),
            ]
        )

        story: list[Any] = [*_cover_page(result, styles)]
        story += _overview_section(result, styles)
        story.append(PageBreak())
        story += _candidate_section(result, styles)
        story.append(Spacer(1, 7 * mm))
        story += _skills_section(result, styles)
        story.append(PageBreak())

        review_flowables = _review_section(result.review, styles)
        if review_flowables:
            story += review_flowables
            story.append(Spacer(1, 6 * mm))

        if result.ats.recommendations:
            story.append(KeepTogether(_recommendations_section(result, styles)))

        document.build(story)

    except Exception as exc:
        logger.error("PDF generation failed: %s", exc, exc_info=True)
        raise ReportGenerationError(f"pdf build failed: {exc}") from exc

    pdf_bytes = buffer.getvalue()
    buffer.close()
    logger.info("Generated PDF report (%s bytes).", len(pdf_bytes))
    return pdf_bytes

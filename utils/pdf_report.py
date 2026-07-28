import re
from io import BytesIO
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph


def generate_pdf(score, stats, matched, missing, feedback):
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("<b>AI Resume Analysis Report</b>", styles["Title"]))
    story.append(Paragraph(f"<b>ATS Score:</b> {score}%", styles["BodyText"]))
    story.append(Paragraph("<br/>", styles["BodyText"]))

    story.append(Paragraph("<b>Resume Statistics</b>", styles["Heading2"]))
    for key, value in stats.items():
        story.append(Paragraph(f"{key}: {value}", styles["BodyText"]))

    story.append(Paragraph("<br/>", styles["BodyText"]))

    story.append(Paragraph("<b>Matched Skills</b>", styles["Heading2"]))
    if matched:
        for skill in matched:
            story.append(Paragraph(f"• {skill}", styles["BodyText"]))
    else:
        story.append(Paragraph("None", styles["BodyText"]))

    story.append(Paragraph("<br/>", styles["BodyText"]))

    story.append(Paragraph("<b>Missing Skills</b>", styles["Heading2"]))
    if missing:
        for skill in missing:
            story.append(Paragraph(f"• {skill}", styles["BodyText"]))
    else:
        story.append(Paragraph("None", styles["BodyText"]))

    story.append(Paragraph("<br/>", styles["BodyText"]))

    story.append(Paragraph("<b>AI Feedback</b>", styles["Heading2"]))
    clean_feedback = re.sub(r"<[^>]+>", "", feedback)
    clean_feedback = clean_feedback.replace("&", "&amp;")
    clean_feedback = clean_feedback.replace("<", "&lt;")
    clean_feedback = clean_feedback.replace(">", "&gt;")

    for line in clean_feedback.split("\n"):
        if line.strip():
            story.append(Paragraph(line, styles["BodyText"]))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf
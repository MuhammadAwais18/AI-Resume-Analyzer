import streamlit as st
from utils.ai import analyze_resume
from utils.pdf_report import generate_pdf

from utils.parser import extract_text

from utils.scorer import (
    calculate_score,
    matched_skills,
    missing_skills
)

from utils.charts import create_score_chart
from utils.stats import resume_statistics

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="AI Resume Analyzer",
    page_icon="📄",
    layout="wide"
)

# ----------------------------
# Header
# ----------------------------
st.title("📄 AI Resume Analyzer")
st.write("Upload your resume and compare it with a job description.")

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("About")
    st.info(
        "AI Resume Analyzer helps compare your resume "
        "against a job description and provides a matching score."
    )

# ----------------------------
# Upload Resume
# ----------------------------
uploaded_resume = st.file_uploader(
    "Upload Resume",
    type=["pdf", "docx"]
)

# ----------------------------
# Job Description
# ----------------------------
job_description = st.text_area(
    "Paste Job Description",
    height=250
)

# ----------------------------
# Analyze Button
# ----------------------------
if st.button("Analyze Resume", use_container_width=True):

    if uploaded_resume is None:
        st.warning("Please upload a resume.")
        st.stop()

    if not job_description.strip():
        st.warning("Please paste a job description.")
        st.stop()

    with st.spinner("Analyzing Resume..."):

        resume_text = extract_text(uploaded_resume)

        stats = resume_statistics(resume_text)

        matched = matched_skills(
            resume_text,
            job_description
        )

        missing = missing_skills(
            resume_text,
            job_description
        )

        score = calculate_score(
            resume_text,
            job_description
        )

    st.success("Analysis Complete!")

    st.metric(
        label="Resume Match Score",
        value=f"{score}%"
    )

    chart = create_score_chart(score)

    st.plotly_chart(
        chart,
        use_container_width=True
    )

    st.subheader("📊 Resume Statistics")

    col1, col2, col3 = st.columns(3)

    col1.metric("Words", stats["Words"])
    col2.metric("Characters", stats["Characters"])
    col3.metric("Sentences", stats["Sentences"])

    st.subheader("🛠 Skills Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.write("### ✅ Matched Skills")

        if matched:
            for skill in matched:
                st.success(skill)
        else:
            st.info("No matched skills found.")

    with col2:
        st.write("### ❌ Missing Skills")

        if missing:
            for skill in missing:
                st.error(skill)
        else:
            st.success("No missing skills found.")

    if score >= 80:
        st.success("Excellent Match ✅")

    elif score >= 60:
        st.warning("Good Match ⚠️")

    else:
        st.error("Low Match ❌")

    with st.expander("Resume Text Preview"):
        st.write(resume_text[:2500])

    st.divider()

    st.subheader("🤖 AI Resume Review")

    with st.spinner("Generating AI feedback..."):
        feedback = analyze_resume(
            resume_text,
            job_description
        )

    st.markdown(feedback)

    pdf = generate_pdf(
        score,
        stats,
        matched,
        missing,
        feedback
    )

    st.download_button(
        label="📄 Download PDF Report",
        data=pdf,
        file_name="AI_Resume_Report.pdf",
        mime="application/pdf",
        use_container_width=True
    )
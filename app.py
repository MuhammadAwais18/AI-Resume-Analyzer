import streamlit as st
from utils.ai import analyze_resume
from utils.parser import extract_text
from utils.scorer import calculate_score

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

        score = calculate_score(
            resume_text,
            job_description
        )

    st.success("Analysis Complete!")

    st.metric(
        label="Resume Match Score",
        value=f"{score}%"
    )

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
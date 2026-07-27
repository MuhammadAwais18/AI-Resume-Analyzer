import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("MODEL")


def analyze_resume(resume_text, job_description):

    prompt = f"""
You are an ATS Resume Expert.

Resume:

{resume_text}

Job Description:

{job_description}

Return your answer in Markdown.

Include:

1. Overall ATS Review
2. Strengths
3. Weaknesses
4. Missing Skills
5. Resume Improvement Suggestions
6. Final Verdict
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3
    )

    return response.choices[0].message.content
import re
import spacy

nlp = spacy.load("en_core_web_sm")


def extract_resume_info(text):
    doc = nlp(text)

    email = ""
    phone = ""

    email_match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    if email_match:
        email = email_match.group()

    phone_match = re.search(
        r"(\+?\d[\d\s\-]{8,}\d)",
        text
    )

    if phone_match:
        phone = phone_match.group()

    skills = []

    skill_list = [
        "Python",
        "SQL",
        "Excel",
        "Power BI",
        "Git",
        "Java",
        "C++",
        "HTML",
        "CSS",
        "JavaScript"
    ]

    text_lower = text.lower()

    for skill in skill_list:
        if skill.lower() in text_lower:
            skills.append(skill)
    
    education = "Not Found"

    education_keywords = [
        "Bachelor",
        "Master",
        "BS",
        "MS",
        "BSc",
        "MSc",
        "Computer Science",
        "Engineering",
        "Matric",
        "Intermediate"
    ]

    for keyword in education_keywords:
        if keyword.lower() in text_lower:
            education = keyword
            break

    experience = "Not Found"

    experience_match = re.search(
        r"(\d+)\+?\s*(years?|yrs?)",
        text,
        re.IGNORECASE
    )

    if experience_match:
        experience = experience_match.group()

    return {
        "email": email,
        "phone": phone,
        "skills": skills,
        "education": education,
        "experience": experience
    }
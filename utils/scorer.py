from utils.nlp_parser import extract_resume_info


def calculate_score(resume_text, job_description):

    resume_skills = set(
        skill.lower()
        for skill in extract_resume_info(resume_text)["skills"]
    )

    job_skills = set(
        skill.lower()
        for skill in extract_resume_info(job_description)["skills"]
    )

    if not job_skills:
        return 0

    matched = resume_skills.intersection(job_skills)

    score = (len(matched) / len(job_skills)) * 100

    return round(score)


def matched_skills(resume_text, job_description):

    resume_skills = set(
        extract_resume_info(resume_text)["skills"]
    )

    job_skills = set(
        extract_resume_info(job_description)["skills"]
    )

    return sorted(resume_skills.intersection(job_skills))


def missing_skills(resume_text, job_description):

    resume_skills = set(
        extract_resume_info(resume_text)["skills"]
    )

    job_skills = set(
        extract_resume_info(job_description)["skills"]
    )

    return sorted(job_skills - resume_skills)
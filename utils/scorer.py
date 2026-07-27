import re


def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text


def tokenize(text):
    return set(clean_text(text).split())


def calculate_score(resume_text, job_description):

    resume_words = tokenize(resume_text)
    job_words = tokenize(job_description)

    if len(job_words) == 0:
        return 0

    matched_words = resume_words.intersection(job_words)

    score = (len(matched_words) / len(job_words)) * 100

    return round(score)


def missing_skills(resume_text, job_description):

    resume_words = tokenize(resume_text)
    job_words = tokenize(job_description)

    missing = sorted(job_words - resume_words)

    return missing[:25]


def matched_skills(resume_text, job_description):

    resume_words = tokenize(resume_text)
    job_words = tokenize(job_description)

    matched = sorted(resume_words.intersection(job_words))

    return matched[:25]
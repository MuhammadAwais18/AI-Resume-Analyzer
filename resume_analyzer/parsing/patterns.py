"""Compiled regular expressions and vocabularies used by the resume parser.

Every pattern is compiled once at import time; the parser is a hot path that
runs on every rerun, so per-call compilation is avoided.
"""

from __future__ import annotations

import re
from typing import Final

# --------------------------------------------------------------------------
# Contact details
# --------------------------------------------------------------------------

EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

#: Deliberately strict so that dates and identifiers are not read as phones.
PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:(?<=^)|(?<=[^\d]))"
    r"(\+?\d{1,3}[\s.\-]?)?"
    r"(\(?\d{2,4}\)?[\s.\-]?)"
    r"\d{3}[\s.\-]?\d{3,4}"
    r"(?:(?=$)|(?=[^\d]))"
)

LINKEDIN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|pub|profile)/[A-Za-z0-9_\-%.]+",
    re.IGNORECASE,
)

GITHUB_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-.]+", re.IGNORECASE
)

URL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:https?://|www\.)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE
)

#: Hosts excluded when looking for a personal portfolio link.
NON_PORTFOLIO_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "linkedin.com",
        "github.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "mailto",
        "youtube.com",
        "stackoverflow.com",
        "medium.com",
        "leetcode.com",
        "kaggle.com",
    }
)

# --------------------------------------------------------------------------
# Experience
# --------------------------------------------------------------------------

YEARS_EXPERIENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(\d{1,2})(?:\s*\+)?\s*(?:\+\s*)?(?:years?|yrs?)"
    r"(?:\s+(?:of\s+)?(?:professional\s+|relevant\s+|hands[- ]on\s+)?experience)?",
    re.IGNORECASE,
)

MONTHS: Final[str] = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?"
    r"|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

DATE_RANGE_RE: Final[re.Pattern[str]] = re.compile(
    rf"((?:{MONTHS})?\.?\s*\d{{4}})"
    r"\s*(?:-|–|—|to|until|through)\s*"
    rf"((?:{MONTHS})?\.?\s*\d{{4}}|present|current|now|ongoing)",
    re.IGNORECASE,
)

YEAR_RE: Final[re.Pattern[str]] = re.compile(r"(19|20)\d{2}")

# --------------------------------------------------------------------------
# Education
# --------------------------------------------------------------------------

#: Degree keyword -> (display label, seniority rank).
DEGREE_LEVELS: Final[dict[str, tuple[str, int]]] = {
    "phd": ("PhD", 5),
    "ph.d": ("PhD", 5),
    "doctorate": ("Doctorate", 5),
    "doctor of philosophy": ("PhD", 5),
    "mba": ("MBA", 4),
    "master": ("Master's Degree", 4),
    "masters": ("Master's Degree", 4),
    "m.sc": ("MSc", 4),
    "msc": ("MSc", 4),
    "m.s.": ("MS", 4),
    "m.tech": ("M.Tech", 4),
    "mtech": ("M.Tech", 4),
    "m.eng": ("M.Eng", 4),
    "bachelor": ("Bachelor's Degree", 3),
    "bachelors": ("Bachelor's Degree", 3),
    "b.sc": ("BSc", 3),
    "bsc": ("BSc", 3),
    "b.s.": ("BS", 3),
    "b.tech": ("B.Tech", 3),
    "btech": ("B.Tech", 3),
    "b.e.": ("B.E.", 3),
    "b.eng": ("B.Eng", 3),
    "bca": ("BCA", 3),
    "mca": ("MCA", 4),
    "associate degree": ("Associate Degree", 2),
    "diploma": ("Diploma", 2),
    "intermediate": ("Intermediate", 1),
    "fsc": ("FSc", 1),
    "matric": ("Matriculation", 1),
    "high school": ("High School", 1),
}

FIELD_OF_STUDY_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:in|of)\s+([A-Za-z][A-Za-z&\s]{2,40}?)"
    r"(?=\s*(?:,|\||–|-|\(|\d{4}|$|\n))",
)

#: Degree qualifiers that precede the real field of study, e.g.
#: "Master *of Science* in Computer Science".
DEGREE_QUALIFIERS: Final[tuple[str, ...]] = (
    "science",
    "arts",
    "engineering",
    "technology",
    "business administration",
    "philosophy",
    "commerce",
    "education",
)

INSTITUTION_RE: Final[re.Pattern[str]] = re.compile(
    r"\b([A-Z][A-Za-z.&'\-]*(?:\s+[A-Z][A-Za-z.&'\-]*)*\s+"
    r"(?:University|College|Institute|Institute of Technology|School|Academy|Polytechnic))\b"
)

# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

#: Canonical section name -> heading synonyms found in real resumes.
SECTION_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "summary": (
        "summary",
        "professional summary",
        "profile",
        "about me",
        "about",
        "objective",
        "career objective",
        "professional profile",
        "executive summary",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "employment",
        "work history",
        "career history",
        "relevant experience",
        "industry experience",
    ),
    "education": (
        "education",
        "academic background",
        "academics",
        "educational qualifications",
        "qualifications",
        "academic qualifications",
        "education and training",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "areas of expertise",
        "expertise",
        "technologies",
        "tech stack",
        "technical proficiencies",
        "skill set",
    ),
    "projects": (
        "projects",
        "personal projects",
        "key projects",
        "selected projects",
        "academic projects",
        "portfolio",
        "side projects",
    ),
    "certifications": (
        "certifications",
        "certification",
        "certificates",
        "licenses",
        "licenses and certifications",
        "professional certifications",
        "courses",
        "training",
    ),
    "awards": (
        "awards",
        "honors",
        "honours",
        "awards and honors",
        "recognition",
        "accolades",
    ),
    "achievements": (
        "achievements",
        "key achievements",
        "accomplishments",
        "highlights",
        "career highlights",
    ),
    "languages": ("languages", "language proficiency", "spoken languages"),
    "publications": ("publications", "papers", "research"),
    "interests": ("interests", "hobbies", "activities"),
    "references": ("references", "referees"),
    "contact": ("contact", "contact information", "personal details", "personal information"),
    "volunteer": ("volunteer", "volunteering", "community service"),
}

#: Flat lookup of every heading synonym to its canonical section.
HEADING_LOOKUP: Final[dict[str, str]] = {
    alias: canonical
    for canonical, aliases in SECTION_ALIASES.items()
    for alias in aliases
}

BULLET_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^\s*[•▪◦‣∙*\-–—]\s*")

# --------------------------------------------------------------------------
# Certifications, awards, languages
# --------------------------------------------------------------------------

CERTIFICATION_HINTS: Final[tuple[str, ...]] = (
    "certified",
    "certificate",
    "certification",
    "aws certified",
    "azure",
    "google cloud certified",
    "pmp",
    "scrum master",
    "cissp",
    "ccna",
    "comptia",
    "oracle certified",
    "nanodegree",
    "specialization",
    "bootcamp",
    "coursera",
    "udacity",
    "udemy",
    "datacamp",
)

AWARD_HINTS: Final[tuple[str, ...]] = (
    "award",
    "winner",
    "won ",
    "1st place",
    "first place",
    "2nd place",
    "runner-up",
    "medal",
    "scholarship",
    "dean's list",
    "honor roll",
    "hackathon",
    "recognition",
    "top performer",
    "employee of the",
)

#: Spoken languages recognised in the Languages section.
KNOWN_LANGUAGES: Final[tuple[str, ...]] = (
    "English",
    "Spanish",
    "French",
    "German",
    "Chinese",
    "Mandarin",
    "Cantonese",
    "Japanese",
    "Korean",
    "Arabic",
    "Urdu",
    "Hindi",
    "Punjabi",
    "Bengali",
    "Portuguese",
    "Russian",
    "Italian",
    "Dutch",
    "Turkish",
    "Persian",
    "Farsi",
    "Pashto",
    "Sindhi",
    "Swedish",
    "Norwegian",
    "Danish",
    "Polish",
    "Ukrainian",
    "Vietnamese",
    "Thai",
    "Indonesian",
    "Malay",
    "Tagalog",
    "Filipino",
    "Hebrew",
    "Greek",
    "Czech",
    "Romanian",
    "Hungarian",
    "Swahili",
    "Tamil",
    "Telugu",
    "Marathi",
    "Gujarati",
)

#: Tokens that disqualify a line from being a candidate's name.
NAME_STOP_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "resume",
        "curriculum",
        "vitae",
        "cv",
        "profile",
        "contact",
        "phone",
        "email",
        "address",
        "linkedin",
        "github",
        "portfolio",
        "summary",
        "objective",
        "engineer",
        "developer",
        "manager",
        "analyst",
        "designer",
        "consultant",
        "intern",
        "student",
    }
)

JOB_TITLE_HINTS: Final[tuple[str, ...]] = (
    "engineer",
    "developer",
    "manager",
    "analyst",
    "scientist",
    "designer",
    "architect",
    "consultant",
    "specialist",
    "administrator",
    "lead",
    "director",
    "intern",
    "associate",
    "officer",
    "coordinator",
    "researcher",
    "programmer",
    "technician",
    "head of",
    "vp of",
    "president",
)

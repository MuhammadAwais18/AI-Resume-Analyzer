"""Tests for document extraction and structured resume parsing."""

from __future__ import annotations

import io

import pytest

from resume_analyzer.exceptions import (
    CorruptDocumentError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedFileTypeError,
)
from resume_analyzer.parsing.document import extract_document, validate_upload
from resume_analyzer.parsing.resume_parser import (
    education_level,
    extract_email,
    extract_phone,
    parse_resume,
    split_sections,
    total_experience_years,
)


class FakeUpload(io.BytesIO):
    """Minimal stand-in for a Streamlit ``UploadedFile``."""

    def __init__(self, name: str, payload: bytes = b"data"):
        super().__init__(payload)
        self.name = name
        self.size = len(payload)


# --------------------------------------------------------------------------
# Contact extraction
# --------------------------------------------------------------------------


def test_extracts_email(resume_text: str) -> None:
    assert extract_email(resume_text) == "jane.doe@example.com"


def test_extracts_phone(resume_text: str) -> None:
    phone = extract_phone(resume_text)
    assert phone is not None
    assert "555" in phone


def test_phone_does_not_match_year_range() -> None:
    assert extract_phone("Worked there 2019 - 2022 on backend systems") is None


def test_extracts_all_contact_fields(resume_text: str) -> None:
    contact = parse_resume(resume_text).contact
    assert contact.full_name == "Jane Alexandra Doe"
    assert contact.email == "jane.doe@example.com"
    assert contact.linkedin and "linkedin.com/in/janedoe" in contact.linkedin
    assert contact.github and "github.com/janedoe" in contact.github


# --------------------------------------------------------------------------
# Sections and structured fields
# --------------------------------------------------------------------------


def test_splits_known_sections(resume_text: str) -> None:
    sections = split_sections(resume_text)
    assert {"experience", "education", "skills", "certifications"} <= set(sections)


def test_extracts_education_entries(resume_text: str) -> None:
    education = parse_resume(resume_text).education
    assert education
    assert education[0].degree == "Master's Degree"
    assert education[0].field_of_study == "Computer Science"


def test_extracts_experience_entries(resume_text: str) -> None:
    experience = parse_resume(resume_text).experience
    assert experience
    assert experience[0].title == "Senior Software Engineer"
    assert experience[0].company == "Stripe"


def test_computes_experience_years(resume_text: str) -> None:
    years = total_experience_years(resume_text, split_sections(resume_text))
    assert 5 <= years <= 12


def test_education_level_ranking() -> None:
    assert education_level("PhD in Physics")[1] > education_level("BSc in Maths")[1]
    assert education_level("no degree here")[1] == 0


def test_extracts_lists(resume_text: str) -> None:
    profile = parse_resume(resume_text)
    assert profile.certifications
    assert profile.awards
    assert "Spanish" in profile.languages
    assert profile.achievements


def test_parse_empty_text_is_safe() -> None:
    profile = parse_resume("")
    assert profile.skills == []
    assert profile.warnings


def test_malformed_resume_degrades_gracefully() -> None:
    profile = parse_resume("!!!___###   \n\n   @@@@")
    assert profile.contact.email is None
    assert isinstance(profile.warnings, list)


# --------------------------------------------------------------------------
# Upload validation
# --------------------------------------------------------------------------


def test_rejects_unsupported_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(FakeUpload("resume.txt"))


def test_rejects_oversized_upload() -> None:
    upload = FakeUpload("resume.pdf")
    upload.size = 50 * 1024 * 1024
    with pytest.raises(FileTooLargeError):
        validate_upload(upload)


def test_accepts_supported_extensions() -> None:
    validate_upload(FakeUpload("resume.pdf"))
    validate_upload(FakeUpload("resume.docx"))


def test_corrupt_pdf_raises_typed_error() -> None:
    with pytest.raises((CorruptDocumentError, EmptyDocumentError)):
        extract_document(FakeUpload("broken.pdf", b"not a real pdf"))


def test_empty_upload_raises() -> None:
    with pytest.raises(EmptyDocumentError):
        extract_document(FakeUpload("empty.pdf", b""))


def test_user_messages_are_friendly() -> None:
    try:
        validate_upload(FakeUpload("resume.txt"))
    except UnsupportedFileTypeError as exc:
        assert "PDF" in exc.user_message
        assert "Traceback" not in exc.user_message

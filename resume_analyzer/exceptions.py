"""Application exception hierarchy.

Every error raised on purpose by the core carries a ``user_message``: a short,
non-technical sentence that is safe to render in the UI.  Stack traces and
provider payloads stay in the logs, never on screen.
"""

from __future__ import annotations


class ResumeAnalyzerError(Exception):
    """Base class for all expected application errors."""

    default_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None, *, user_message: str | None = None):
        super().__init__(message or self.default_message)
        self.user_message = user_message or self.default_message


class DocumentError(ResumeAnalyzerError):
    """Base class for problems with an uploaded document."""

    default_message = "The uploaded document could not be processed."


class UnsupportedFileTypeError(DocumentError):
    """Raised when the upload is neither a PDF nor a DOCX file."""

    default_message = "Unsupported file type. Please upload a PDF or DOCX resume."


class FileTooLargeError(DocumentError):
    """Raised when the upload exceeds the configured size limit."""

    default_message = "This file is too large. Please upload a resume under 10 MB."


class CorruptDocumentError(DocumentError):
    """Raised when the document exists but cannot be opened or decoded."""

    default_message = (
        "This file appears to be corrupted or password protected. "
        "Please re-export it and try again."
    )


class EmptyDocumentError(DocumentError):
    """Raised when a document yields no extractable text (typically scanned)."""

    default_message = (
        "No readable text was found. The resume looks like a scanned image — "
        "please upload a text-based PDF or DOCX."
    )


class ValidationError(ResumeAnalyzerError):
    """Raised when user-supplied input fails validation."""

    default_message = "Please check the information you provided and try again."


class AIServiceError(ResumeAnalyzerError):
    """Base class for language-model provider failures."""

    default_message = "The AI reviewer is unavailable right now."


class AIConfigurationError(AIServiceError):
    """Raised when no API credentials are configured."""

    default_message = (
        "AI review is not configured. Add your API key to enable AI feedback — "
        "all other analysis features continue to work."
    )


class AITimeoutError(AIServiceError):
    """Raised when the provider does not answer within the timeout."""

    default_message = "The AI reviewer took too long to respond. Please try again."


class AIRateLimitError(AIServiceError):
    """Raised when the provider rejects the request due to rate limiting."""

    default_message = (
        "The AI reviewer is rate limited at the moment. Please retry in a minute."
    )


class AIResponseError(AIServiceError):
    """Raised when the provider returns an empty or malformed payload."""

    default_message = "The AI reviewer returned an unexpected response."


class StorageError(ResumeAnalyzerError):
    """Raised when the analytics database cannot be read or written."""

    default_message = "Analysis history is temporarily unavailable."


class ReportGenerationError(ResumeAnalyzerError):
    """Raised when the PDF report cannot be produced."""

    default_message = "The PDF report could not be generated."

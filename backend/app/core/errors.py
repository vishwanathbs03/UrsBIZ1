"""Centralized Exception Hierarchy for UrsBiz (Phase 5 Platform Resilience).

Defines structured, retry-aware domain exceptions that map cleanly to
standardized HTTP error envelopes without exposing internal infrastructure details.
"""

from __future__ import annotations

from typing import Any, Optional


class AppResilienceError(Exception):
    """Base class for all structured application resilience exceptions."""

    def __init__(
        self,
        safe_message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        retryable: bool = False,
        service_name: str = "fastapi",
        hint: Optional[str] = None,
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable
        self.service_name = service_name
        self.hint = hint
        self.extra_details = extra_details or {}


class DatabaseUnavailableError(AppResilienceError):
    """Database connectivity failure or connection pool exhaustion."""

    def __init__(
        self,
        safe_message: str = "Database service is temporarily unavailable. Please retry in a few moments.",
        hint: str = "Wait a few seconds and refresh.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="DATABASE_UNAVAILABLE",
            status_code=503,
            retryable=True,
            service_name="database",
            hint=hint,
            extra_details=extra_details,
        )


class DatabaseTransactionError(AppResilienceError):
    """Transaction failure, integrity conflict, or aborted query safely rolled back."""

    def __init__(
        self,
        safe_message: str = "A database transaction error occurred. Changes were safely rolled back.",
        hint: str = "Verify input parameters and retry.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="DATABASE_TRANSACTION_ERROR",
            status_code=500,
            retryable=True,
            service_name="database",
            hint=hint,
            extra_details=extra_details,
        )


class ConcurrentModificationError(AppResilienceError):
    """Concurrent edit conflict detected on a stateful resource."""

    def __init__(
        self,
        safe_message: str = "Resource was modified concurrently by another operation.",
        hint: str = "Refresh latest status and reapply changes.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="CONCURRENT_MODIFICATION_CONFLICT",
            status_code=409,
            retryable=True,
            service_name="database",
            hint=hint,
            extra_details=extra_details,
        )


class AIServiceUnavailableError(AppResilienceError):
    """Gemini API outage, 503, or connection drop."""

    def __init__(
        self,
        safe_message: str = "AI reasoning service is temporarily unavailable. Deterministic business analytics remain fully active.",
        hint: str = "Deterministic features continue to operate normally. AI explanations will resume shortly.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="AI_SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
            service_name="gemini",
            hint=hint,
            extra_details=extra_details,
        )


class AIRateLimitError(AppResilienceError):
    """Gemini HTTP 429 quota exhaustion or rate limit."""

    def __init__(
        self,
        safe_message: str = "AI request quota limit reached. Request was queued or switched to deterministic fallback.",
        retry_after_seconds: Optional[int] = None,
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        details = extra_details or {}
        if retry_after_seconds:
            details["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            safe_message=safe_message,
            error_code="AI_RATE_LIMIT_EXCEEDED",
            status_code=429,
            retryable=True,
            service_name="gemini",
            hint=f"Please wait {retry_after_seconds or 30} seconds before asking another AI question.",
            extra_details=details,
        )


class AITimeoutError(AppResilienceError):
    """Gemini request timed out after maximum allowable budget."""

    def __init__(
        self,
        safe_message: str = "AI response timed out. A deterministic fallback response has been generated.",
        hint: str = "Try asking a more specific question or retry shortly.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="AI_REQUEST_TIMEOUT",
            status_code=504,
            retryable=True,
            service_name="gemini",
            hint=hint,
            extra_details=extra_details,
        )


class IdempotencyConflictError(AppResilienceError):
    """Duplicate or in-progress request detected for the same idempotency key."""

    def __init__(
        self,
        safe_message: str = "An identical operation is currently being processed or has already been submitted.",
        hint: str = "Please wait for the current operation to complete before re-submitting.",
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="IDEMPOTENCY_CONFLICT",
            status_code=409,
            retryable=False,
            service_name="idempotency",
            hint=hint,
            extra_details=extra_details,
        )


class UploadProcessingError(AppResilienceError):
    """File validation, size, format, or parsing error during sales ingestion."""

    def __init__(
        self,
        safe_message: str,
        hint: str = "Ensure the file is a valid CSV or Excel file under 10MB with required columns.",
        status_code: int = 422,
        extra_details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            safe_message=safe_message,
            error_code="UPLOAD_PROCESSING_ERROR",
            status_code=status_code,
            retryable=False,
            service_name="sales_ingestion",
            hint=hint,
            extra_details=extra_details,
        )

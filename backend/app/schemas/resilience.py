"""Resilience and Error Schemas — Sprint Phase 5 Operational Reliability.

Standardized error response envelope and operational telemetry schemas.
Guarantees consistent, safe error reporting across all UrsBiz services without
leaking database schemas, stack traces, or credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class StandardErrorEnvelope(BaseModel):
    """Consistent, safe error envelope returned for all client-facing errors."""

    error_code: str = Field(
        ...,
        description="Machine-readable canonical error code (e.g. DATABASE_UNAVAILABLE, AI_TIMEOUT, VALIDATION_ERROR)",
    )
    safe_message: str = Field(
        ...,
        description="Sanitized, human-readable message safe for display to business owners.",
    )
    request_id: str = Field(
        ...,
        description="Correlation ID for request tracing and log alignment.",
    )
    retryable: bool = Field(
        False,
        description="Whether the client or user can retry the operation.",
    )
    service_name: str = Field(
        ...,
        description="Originating subsystem (e.g. 'gemini', 'database', 'sales_ingestion', 'smart_recommendations').",
    )
    detail: str = Field(
        ...,
        description="Backward-compatible duplicate of safe_message for standard FastAPI clients.",
    )
    hint: Optional[str] = Field(
        None,
        description="Actionable suggestion for the user (e.g. 'Check file format' or 'Try again in 30s').",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of error occurrence.",
    )
    extra_details: Optional[dict[str, Any]] = Field(
        None,
        description="Non-sensitive domain metadata (e.g. valid row count or required columns).",
    )


class OperationalLogRecord(BaseModel):
    """Structured audit record for operational monitoring."""

    request_id: str
    endpoint: str
    method: str
    duration_ms: float
    service_status: str
    error_category: Optional[str] = None
    retry_count: int = 0
    fallback_used: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

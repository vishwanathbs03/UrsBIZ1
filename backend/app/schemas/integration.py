"""Pydantic schemas for Integration Readiness and Connector Framework (Phase 6.27).

Strictly excludes decrypted credentials, tokens, and raw secrets from API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConfigFieldOut(BaseModel):
    """Schema descriptor for a connector configuration field."""
    key: str
    label: str
    field_type: str
    required: bool
    description: str = ""
    default_value: Any = None
    options: list[str] | None = None
    is_secret: bool = False


class ConnectorCatalogueItemOut(BaseModel):
    """Metadata describing an available connector in the catalog."""
    connector_id: str
    name: str
    provider: str
    version: str
    description: str
    capabilities: list[str]
    auth_method: str
    sync_direction: str
    operational_status: str
    known_limitations: list[str]
    config_fields: list[ConfigFieldOut]


class ConnectionCreateReq(BaseModel):
    """Request payload to create a new connection."""
    connector_id: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    configuration: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)


class ConnectionConfigUpdateReq(BaseModel):
    """Request payload to update non-sensitive connection configuration."""
    configuration: dict[str, Any]


class CredentialRotateReq(BaseModel):
    """Request payload to rotate or update connection credentials."""
    credentials: dict[str, Any]


class ConnectionOut(BaseModel):
    """External representation of a configured data source connection."""
    id: int
    business_id: int
    connector_id: str
    name: str
    status: str
    configuration: dict[str, Any]
    has_credentials: bool
    masked_credentials: dict[str, str]
    credential_fingerprint: str | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_error_category: str | None = None
    last_error_message: str | None = None
    sync_cursor: str | None = None
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectionTestResultOut(BaseModel):
    """Response payload for testing connection authentication and reachability."""
    success: bool
    status: str
    message: str
    tested_at: datetime


class SyncTriggerReq(BaseModel):
    """Request payload to trigger a manual synchronization."""
    trigger_type: str = "MANUAL"
    batch_limit: int = 100


class SyncExecutionOut(BaseModel):
    """Representation of an individual synchronization run."""
    id: int
    business_id: int
    connection_id: int
    connector_id: str
    execution_id: str
    trigger_type: str
    status: str
    records_discovered: int
    records_imported: int
    records_skipped: int
    duplicate_count: int
    validation_failure_count: int
    error_category: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    sync_cursor_before: str | None = None
    sync_cursor_after: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncExecutionListResponse(BaseModel):
    """Paginated list of synchronization executions."""
    items: list[SyncExecutionOut]
    total: int
    page: int
    page_size: int


class IntegrationAuditOut(BaseModel):
    """Audit log entry for an integration lifecycle event."""
    id: int
    business_id: int
    connection_id: int | None = None
    connector_id: str | None = None
    actor_user_id: int | None = None
    event_type: str
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationAuditListResponse(BaseModel):
    """Paginated list of integration audit records."""
    items: list[IntegrationAuditOut]
    total: int
    page: int
    page_size: int

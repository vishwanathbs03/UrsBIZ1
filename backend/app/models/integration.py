"""ORM models for Integration Readiness & Connector Framework (Phase 6.27).

Stores:
  - IntegrationConnection: Tenant-scoped data source connection configurations & encrypted credentials.
  - IntegrationSyncExecution: Auditable sync execution runs, records discovered/imported/skipped.
  - IntegrationAudit: Append-only audit log for connection and sync lifecycle events.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class ConnectionStatus(str, Enum):
    """Lifecycle states for an external data source connection."""
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"
    DISCONNECTED = "DISCONNECTED"
    DISABLED = "DISABLED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"


class SyncExecutionStatus(str, Enum):
    """Lifecycle states for a synchronization run."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SyncTriggerType(str, Enum):
    """Trigger source for synchronization."""
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    WEBHOOK = "WEBHOOK"


class ErrorCategory(str, Enum):
    """Standardized error categories for connector operations."""
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    DATA_MAPPING_FAILURE = "DATA_MAPPING_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class IntegrationConnection(Base):
    """Configured connection between a business digital twin and an external data source."""

    __tablename__ = "integration_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ConnectionStatus.NOT_CONFIGURED.value,
        index=True,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    business: Mapped["Business"] = relationship(back_populates="integration_connections")
    created_by: Mapped["User | None"] = relationship()
    sync_executions: Mapped[list["IntegrationSyncExecution"]] = relationship(
        back_populates="connection",
        cascade="all, delete-orphan",
        order_by="desc(IntegrationSyncExecution.created_at)",
    )

    __table_args__ = (
        UniqueConstraint("business_id", "connector_id", "name", name="uq_integration_connection_name"),
    )


class IntegrationSyncExecution(Base):
    """An individual synchronization batch run from an external data source."""

    __tablename__ = "integration_sync_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SyncTriggerType.MANUAL.value
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SyncExecutionStatus.QUEUED.value, index=True
    )
    records_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sync_cursor_before: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_cursor_after: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    connection: Mapped["IntegrationConnection"] = relationship(back_populates="sync_executions")


class IntegrationAudit(Base):
    """Append-only audit trail for integration connection and synchronization lifecycle events."""

    __tablename__ = "integration_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    connector_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    business: Mapped["Business"] = relationship()
    actor: Mapped["User | None"] = relationship()


@event.listens_for(IntegrationAudit, "before_update")
def _prevent_integration_audit_update(mapper: Any, connection: Any, target: IntegrationAudit) -> None:
    raise ValueError(
        "IntegrationAudit records are strictly append-only and immutable. UPDATE operations are forbidden."
    )


@event.listens_for(IntegrationAudit, "before_delete")
def _prevent_integration_audit_delete(mapper: Any, connection: Any, target: IntegrationAudit) -> None:
    raise ValueError(
        "IntegrationAudit records are strictly append-only and immutable. DELETE operations are forbidden."
    )

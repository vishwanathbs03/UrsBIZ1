"""ORM models for Reports and Evidence Export Centre (Phase 6.25).

Stores generated business intelligence reports, export artifacts, and append-only audit logs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    DDL,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class BusinessReport(Base):
    """A generated, downloadable business report or evidence export."""

    __tablename__ = "business_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Catalog report type: e.g. executive_summary, sales_revenue_performance, etc.
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reporting_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Format: PDF, CSV, XLSX
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    
    # Status: QUEUED, GENERATING, COMPLETED, FAILED, EXPIRED
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="COMPLETED", index=True
    )

    # Storage details
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Configurations, summary findings, and evidence provenance
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    summary_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    provenance_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Archival / soft-delete
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Tracking & Retention
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    business: Mapped[Business] = relationship(back_populates="reports")
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    audits: Mapped[list[BusinessReportAudit]] = relationship(
        back_populates="report"
    )


class BusinessReportAudit(Base):
    """Append-only audit trail for report generations, previews, and downloads.

    Guarantees full accountability and historical provenance. Ordinary users
    cannot alter or delete audit history.
    """

    __tablename__ = "business_report_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action: PREVIEWED, GENERATED, DOWNLOADED, ARCHIVED, FAILED
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships
    report: Mapped[BusinessReport | None] = relationship(back_populates="audits")
    business: Mapped[Business] = relationship()
    user: Mapped[User | None] = relationship()


# --- Append-Only Immutability Protections for BusinessReportAudit ---

@event.listens_for(BusinessReportAudit, "before_update")
def _prevent_business_report_audit_update(mapper: Any, connection: Any, target: Any) -> None:
    raise ValueError("BusinessReportAudit records are append-only and cannot be updated.")


@event.listens_for(BusinessReportAudit, "before_delete")
def _prevent_business_report_audit_delete(mapper: Any, connection: Any, target: Any) -> None:
    raise ValueError("BusinessReportAudit records are append-only and cannot be deleted.")


# SQLite DB Triggers
_sqlite_report_audit_update_trg = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_business_report_audits_update
BEFORE UPDATE ON business_report_audits
BEGIN
    SELECT RAISE(ABORT, 'BusinessReportAudit records are append-only and cannot be updated.');
END;
""")

_sqlite_report_audit_delete_trg = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_prevent_business_report_audits_delete
BEFORE DELETE ON business_report_audits
BEGIN
    SELECT RAISE(ABORT, 'BusinessReportAudit records are append-only and cannot be deleted.');
END;
""")

event.listen(
    BusinessReportAudit.__table__,
    "after_create",
    _sqlite_report_audit_update_trg.execute_if(dialect="sqlite"),
)
event.listen(
    BusinessReportAudit.__table__,
    "after_create",
    _sqlite_report_audit_delete_trg.execute_if(dialect="sqlite"),
)

# PostgreSQL DB Triggers
_pg_report_audit_trg_func = DDL("""
CREATE OR REPLACE FUNCTION trg_prevent_business_report_audits_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'BusinessReportAudit records are append-only and cannot be modified or deleted.';
END;
$$ LANGUAGE plpgsql;
""")

_pg_report_audit_update_trg = DDL("""
CREATE TRIGGER trg_no_update_business_report_audits
BEFORE UPDATE ON business_report_audits
FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_report_audits_modification();
""")

_pg_report_audit_delete_trg = DDL("""
CREATE TRIGGER trg_no_delete_business_report_audits
BEFORE DELETE ON business_report_audits
FOR EACH ROW EXECUTE FUNCTION trg_prevent_business_report_audits_modification();
""")

event.listen(
    BusinessReportAudit.__table__,
    "after_create",
    _pg_report_audit_trg_func.execute_if(dialect="postgresql"),
)
event.listen(
    BusinessReportAudit.__table__,
    "after_create",
    _pg_report_audit_update_trg.execute_if(dialect="postgresql"),
)
event.listen(
    BusinessReportAudit.__table__,
    "after_create",
    _pg_report_audit_delete_trg.execute_if(dialect="postgresql"),
)

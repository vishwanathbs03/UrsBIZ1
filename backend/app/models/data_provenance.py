"""ORM models for Business Data Provenance and Quality Audits (Phase 5).

Stores persistent provenance lineage and automated data-quality audit reports
for each business digital twin.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class BusinessDataProvenance(Base):
    """Verifiable provenance tracking record for an individual business metric."""

    __tablename__ = "business_data_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_record_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measurement_period: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="INR")
    calculation_methodology: Mapped[str] = mapped_column(Text, nullable=False)
    data_quality_status: Mapped[str] = mapped_column(String(30), nullable=False, default="VERIFIED")
    nature: Mapped[str] = mapped_column(String(30), nullable=False, default="actual")
    freshness_status: Mapped[str] = mapped_column(String(30), nullable=False, default="FRESH")
    freshness_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    business: Mapped["Business"] = relationship()


class BusinessDataQualityAudit(Base):
    """Audit report log tracking data quality, anomalies, and freshness evaluations."""

    __tablename__ = "business_data_quality_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False, default="comprehensive")
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    overall_quality_status: Mapped[str] = mapped_column(String(30), nullable=False, default="VERIFIED")
    anomalies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    cross_module_discrepancies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    freshness_summary: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    unconfirmed_gaps_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    business: Mapped["Business"] = relationship()

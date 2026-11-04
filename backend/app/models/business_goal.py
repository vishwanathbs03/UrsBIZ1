"""Business goal and audit history ORM models (Prompt 6.24).

Child models of Business:
  - BusinessGoal: Measurable target linked to authoritative business metrics.
  - BusinessGoalAudit: Append-only historical log of goal lifecycle and progress evaluations.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
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
    from app.models.user import User


class BusinessGoal(Base):
    """A measurable business goal defined by an authorized business owner."""

    __tablename__ = "business_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "30d", "90d", "1y"
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")

    # Authoritative metric connection
    metric_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    measurement_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AUTOMATED_METRIC"
    )  # AUTOMATED_METRIC, MANUAL_REPORTED, ESTIMATE

    # Quantified targets & baseline
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="INR")  # INR, %, count, days

    # Period boundaries
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Lifecycle status: ACTIVE, PAUSED, COMPLETED, INCOMPLETE, EXPIRED, ARCHIVED
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", index=True
    )
    status_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data availability & freshness tracking
    data_availability: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AVAILABLE"
    )  # AVAILABLE, MISSING_DATA, STALE_DATA, PENDING_PERIOD
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Attribution & Soft-delete
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    business: Mapped["Business"] = relationship(back_populates="goals")
    audits: Mapped[list["BusinessGoalAudit"]] = relationship(
        back_populates="goal",
        order_by="desc(BusinessGoalAudit.created_at)",
        lazy="selectin",
    )


class BusinessGoalAudit(Base):
    """Append-only audit trail and progress snapshots for a business goal.

    Preserves historical progress snapshots so owners can review trajectories
    over time. Retains evidence even if parent goal is archived.
    """

    __tablename__ = "business_goal_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("business_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action type: CREATED, UPDATED, STATUS_CHANGED, PROGRESS_EVALUATED, MANUAL_PROGRESS_LOGGED, ARCHIVED
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    measured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships
    goal: Mapped[BusinessGoal | None] = relationship(back_populates="audits")

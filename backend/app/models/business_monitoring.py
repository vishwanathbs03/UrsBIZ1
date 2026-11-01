"""ORM models for Proactive AI Business Monitoring & Event-Driven Recommendation Intelligence (Phase 5).

Persists:
  - BusinessSignalEvent: Detected business changes, emerging risks, and verified opportunities.
  - BusinessMonitoringPreferences: Configurable owner monitoring settings (with critical risk protection).
  - RecommendationRefreshRecord: Audit trail of recommendation re-evaluations and priority shifts.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import (
    Boolean,
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


class BusinessSignalEvent(Base):
    """Event-driven record of a detected business change, risk, or opportunity."""

    __tablename__ = "business_signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    relevant_entity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    data_period: Mapped[str] = mapped_column(String(64), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Suppression and Escalation
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suppression_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Lifecycle & Recommendation Linkage
    linked_recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    what_changed: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship()


class BusinessMonitoringPreferences(Base):
    """Business owner preferences for proactive monitoring and notification rules."""

    __tablename__ = "business_monitoring_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    monitored_metrics: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [
            "revenue",
            "customer_concentration",
            "repeat_rate",
            "product_margins",
            "forecast_trends",
            "health_score",
            "cash_flow",
        ],
    )
    areas_of_interest: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: [
            "Revenue Growth",
            "Customer Retention",
            "Demand Planning",
            "Cash Flow",
            "Risk Mitigation",
        ],
    )
    alert_frequency: Mapped[str] = mapped_column(String(32), default="REALTIME", nullable=False)
    preferred_notification_types: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["in_app"],
    )
    min_severity: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False)
    cooldown_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship()


class RecommendationRefreshRecord(Base):
    """Audit record when recommendation status or priority is refreshed due to data changes."""

    __tablename__ = "recommendation_refresh_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    refresh_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    old_priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    new_priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    old_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    business: Mapped["Business"] = relationship()

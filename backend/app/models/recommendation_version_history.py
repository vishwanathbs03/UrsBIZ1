"""ORM model for tracking recommendation version and decision audit history (Phase 5).

Maintains an immutable historical record:
  - Original recommendation metadata and priority at creation
  - Subsequent priority changes and evidence adjustments
  - Owner decisions (Viewed, Accepted, In Progress, Completed, Dismissed, Snoozed, Outcome Recorded)
  - Snapshot of underlying business metrics at event time
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from sqlalchemy import (
    DateTime,
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


class RecommendationVersionHistory(Base):
    """Immutable audit trail for recommendation versions, owner decisions, and metric changes."""

    __tablename__ = "recommendation_version_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Audit Event Metadata
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CREATED, VIEWED, ACCEPTED, IN_PROGRESS, COMPLETED, DISMISSED, SNOOZED, OUTCOME_RECORDED
    event_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    business: Mapped["Business"] = relationship()

"""ORM model for tracking recommendation implementation outcomes and business measurements (Phase 5).

Persists verified owner implementation records:
  - Started, Completed, Abandoned status and dates
  - Actual effort required (Low, Medium, High)
  - Owner utility rating (1-5) and qualitative feedback
  - Non-completion reasons (Lack of time, capital, supplier dependencies)
  - Empirical baseline and post-completion measurement snapshots
  - Causal disclaimer and observational correlation status
"""

from __future__ import annotations

from datetime import datetime
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class RecommendationOutcome(Base):
    """Persistent implementation outcome and empirical business measurement for a recommendation."""

    __tablename__ = "recommendation_outcomes"

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
    
    # Implementation Lifecycle Status
    is_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_abandoned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Owner Implementation Feedback
    actual_effort: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Low, Medium, High, or days
    owner_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 to 5 stars
    qualitative_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    perceived_utility: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Very Useful, Useful, Neutral, Not Useful
    
    # Reasons for Non-Completion (if not completed or abandoned)
    non_completion_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    still_relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Measured Outcome Snapshots
    measured_outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    post_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    observed_changes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship()

    __table_args__ = (
        UniqueConstraint("business_id", "recommendation_id", name="uq_business_recommendation_outcome"),
    )

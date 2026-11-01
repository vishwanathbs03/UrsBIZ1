"""ORM model for tracking recommendation feedback (Phase 5 Advanced Intelligence).

Persists owner feedback for recommendations:
  Useful, Not relevant, Already implemented, Not feasible, Need more explanation
Supports suppression flags and audit notes.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class RecommendationFeedback(Base):
    """Owner feedback and suppression state for a business recommendation."""

    __tablename__ = "recommendation_feedback"

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
    feedback_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    suppress_recommendation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
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

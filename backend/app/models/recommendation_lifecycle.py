"""ORM model for tracking recommendation lifecycle state (Phase 5 & 6.26).

Persists the auditable state of each recommendation for a business:
  New -> Viewed -> Accepted -> In Progress -> Completed -> Dismissed

Includes auditable user_id tracking for MSME collaboration (Prompt 6.26).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class RecommendationLifecycleState(Base):
    """Auditable persistent lifecycle state for a business recommendation."""

    __tablename__ = "recommendation_lifecycle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="New",
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship()
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("business_id", "recommendation_id", name="uq_business_recommendation"),
    )

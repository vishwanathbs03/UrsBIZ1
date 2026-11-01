"""ORM model for business recommendation personalization preferences and constraints (Phase 5).

Persists business-specific:
  - Business goals (e.g. Increase Revenue, Retain Customers, Expand Markets)
  - Known resource constraints (e.g. Limited Budget, Small Workforce, Limited Digital Capability)
  - Effort and investment level preferences (Low, Medium, High)
  - Strategic focus areas
  - Source tracking (OWNER_DECLARED, ONBOARDING, SYSTEM_INFERRED)
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base

if TYPE_CHECKING:
    from app.models.business import Business


class BusinessPersonalizationSettings(Base):
    """Business owner recommendation personalization settings and constraints."""

    __tablename__ = "business_personalization_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # JSON-encoded string lists
    goals: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    constraints: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    focus_areas: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Preference levers
    preferred_effort_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Medium"
    )
    preferred_investment_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Low"
    )

    # Metadata & Provenance
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="OWNER_DECLARED"
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

    business: Mapped["Business"] = relationship(back_populates="personalization_settings")

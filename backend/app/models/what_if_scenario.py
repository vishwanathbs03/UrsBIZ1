"""What-If Scenario Simulator ORM model (Phase 6.19 Extension).

Stores saved business scenario projections for interactive testing,
side-by-side case comparisons (Base, Worst, Best), and sensitivity analysis.

Strict tenant isolation:
  - Scoped by business_id (foreign key -> businesses.id)
  - Scoped by owner_id (foreign key -> users.id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import Base


class WhatIfScenario(Base):
    """A saved what-if scenario projection with multi-case outcomes."""

    __tablename__ = "what_if_scenarios"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    scenario_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Historical and baseline numbers captured at simulation time
    baseline_metrics: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON,
        nullable=False,
        default=dict,
    )

    # Hypothetical levers and parameter adjustments
    parameters: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON,
        nullable=False,
        default=dict,
    )

    # Full deterministic simulation results: cases (Base, Worst, Best),
    # break-even impact, runway impact, assumptions applied, disclosures, and AI summary
    projection_result: Mapped[dict[str, Any]] = mapped_column(
        sa.JSON,
        nullable=False,
        default=dict,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        sa.JSON,
        nullable=True,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    business = relationship("Business", backref="what_if_scenarios")
    owner = relationship("User", backref="what_if_scenarios")

    def __repr__(self) -> str:
        return (
            f"<WhatIfScenario id={self.id} business_id={self.business_id} "
            f"type={self.scenario_type!r} title={self.title!r}>"
        )

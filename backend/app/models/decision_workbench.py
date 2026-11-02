"""ORM model for Business Decision Workbench (Phase 6.18 Extension).

Persists business owner decisions, evaluated multi-option comparisons,
supporting evidence snapshots, assumptions, estimated impacts, and
post-decision review states.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import (
    Boolean,
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
    from app.models.user import User
    from app.models.recommendation_outcome import RecommendationOutcome


class BusinessDecision(Base):
    """A business decision evaluation and resolution record."""

    __tablename__ = "business_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Decision Category / Predefined Template
    # e.g.: 'offer_discount', 'increase_price', 'customer_focus', 'expand_product_range', 'reduce_expenses', 'test_sales_channel', 'custom'
    decision_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)

    # Lifecycle Status: Draft -> Evaluating -> Decided -> Implemented -> Reviewed
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="Draft",
        index=True,
    )

    # Deterministic snapshots stored at evaluation time
    # baseline_snapshot: { revenue, aov, gross_margin, order_count, customer_concentration, observation_period, data_freshness }
    baseline_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    # options_payload: list of evaluated options (evidence, assumptions, missing info, benefits, risks, estimated impact, confidence, limitations)
    options_payload: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Owner Decision Selection & Rationale
    selected_option_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    selected_option_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Post-Decision Review & Empirical Outcome Connection
    # review_status: 'Pending', 'Outcome_Observed', 'Abandoned'
    review_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="Pending",
        index=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendation_outcomes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Soft Delete & Audit History
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    deleted_by: Mapped[Optional["User"]] = relationship(foreign_keys=[deleted_by_id])
    outcome: Mapped[Optional["RecommendationOutcome"]] = relationship()

    def __repr__(self) -> str:
        return f"<BusinessDecision id={self.id} business_id={self.business_id} type={self.decision_type} status={self.status}>"

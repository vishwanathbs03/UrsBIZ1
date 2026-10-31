"""Repository for recommendation owner feedback persistence (Phase 5).

Enforces tenant isolation and provides persistent feedback tracking:
  - Useful, Not relevant, Already implemented, Not feasible, Need more explanation
  - Automatic recommendation suppression for dismissed/completed suggestions
"""

from __future__ import annotations

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_feedback import RecommendationFeedback


class RecommendationFeedbackRepository:
    """Encapsulates data access and persistence for recommendation owner feedback."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_feedback_for_business(
        self, business_id: int
    ) -> list[RecommendationFeedback]:
        """Fetch all feedback entries for a business, ordered by newest first."""
        stmt = (
            select(RecommendationFeedback)
            .where(RecommendationFeedback.business_id == business_id)
            .order_by(RecommendationFeedback.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_feedback_by_recommendation(
        self, business_id: int, recommendation_id: str
    ) -> list[RecommendationFeedback]:
        """Fetch feedback entries for a specific business recommendation."""
        stmt = (
            select(RecommendationFeedback)
            .where(
                RecommendationFeedback.business_id == business_id,
                RecommendationFeedback.recommendation_id == recommendation_id,
            )
            .order_by(RecommendationFeedback.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_suppressed_recommendation_ids(self, business_id: int) -> set[str]:
        """Return the set of recommendation IDs currently marked as suppressed for the business."""
        stmt = select(RecommendationFeedback.recommendation_id).where(
            RecommendationFeedback.business_id == business_id,
            RecommendationFeedback.suppress_recommendation.is_(True),
        )
        return set(self.db.scalars(stmt).all())

    def record_feedback(
        self,
        business_id: int,
        recommendation_id: str,
        feedback_type: str,
        outcome_notes: Optional[str] = None,
        suppress: Optional[bool] = None,
    ) -> RecommendationFeedback:
        """Record or update feedback for a recommendation.
        
        If suppress is not explicitly provided:
          - Automatically True for 'Already implemented' or 'Not relevant'
          - False otherwise
        """
        if suppress is None:
            suppress = feedback_type in ("Already implemented", "Not relevant")

        feedback = RecommendationFeedback(
            business_id=business_id,
            recommendation_id=recommendation_id,
            feedback_type=feedback_type,
            outcome_notes=outcome_notes,
            suppress_recommendation=suppress,
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

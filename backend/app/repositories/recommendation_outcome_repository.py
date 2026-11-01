"""Repository for recommendation outcome tracking and version history audit persistence (Phase 5).

Enforces business isolation and provides persistent outcome records and audit history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_outcome import RecommendationOutcome
from app.models.recommendation_version_history import RecommendationVersionHistory


class RecommendationOutcomeRepository:
    """Encapsulates data access and persistence for recommendation outcomes and audit history."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_outcome(
        self, business_id: int, recommendation_id: str
    ) -> Optional[RecommendationOutcome]:
        """Fetch persistent outcome record for a specific business and recommendation."""
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.business_id == business_id,
            RecommendationOutcome.recommendation_id == recommendation_id,
        )
        return self.db.scalars(stmt).first()

    def get_all_outcomes(self, business_id: int) -> list[RecommendationOutcome]:
        """Fetch all outcome records for a business, ordered by newest update."""
        stmt = (
            select(RecommendationOutcome)
            .where(RecommendationOutcome.business_id == business_id)
            .order_by(RecommendationOutcome.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def record_outcome(
        self,
        business_id: int,
        recommendation_id: str,
        is_started: Optional[bool] = None,
        is_completed: Optional[bool] = None,
        is_abandoned: Optional[bool] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        actual_effort: Optional[str] = None,
        owner_rating: Optional[int] = None,
        qualitative_feedback: Optional[str] = None,
        perceived_utility: Optional[str] = None,
        non_completion_reason: Optional[str] = None,
        still_relevant: Optional[bool] = None,
        measured_outcome_summary: Optional[str] = None,
        baseline_metrics: Optional[dict[str, Any]] = None,
        post_metrics: Optional[dict[str, Any]] = None,
        observed_changes: Optional[dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> RecommendationOutcome:
        """Record or update outcome state, sync with lifecycle state, and record audit event."""
        now = datetime.now(timezone.utc)
        record = self.get_outcome(business_id, recommendation_id)

        if record is None:
            record = RecommendationOutcome(
                business_id=business_id,
                recommendation_id=recommendation_id,
                is_started=bool(is_started),
                is_completed=bool(is_completed),
                is_abandoned=bool(is_abandoned),
                started_at=started_at or (now if is_started else None),
                completed_at=completed_at or (now if is_completed else None),
                actual_effort=actual_effort,
                owner_rating=owner_rating,
                qualitative_feedback=qualitative_feedback,
                perceived_utility=perceived_utility,
                non_completion_reason=non_completion_reason,
                still_relevant=True if still_relevant is None else still_relevant,
                measured_outcome_summary=measured_outcome_summary,
                baseline_metrics=baseline_metrics,
                post_metrics=post_metrics,
                observed_changes=observed_changes,
            )
            self.db.add(record)
        else:
            if is_started is not None:
                record.is_started = is_started
                if is_started and record.started_at is None:
                    record.started_at = started_at or now
            if is_completed is not None:
                record.is_completed = is_completed
                if is_completed and record.completed_at is None:
                    record.completed_at = completed_at or now
            if is_abandoned is not None:
                record.is_abandoned = is_abandoned
            if actual_effort is not None:
                record.actual_effort = actual_effort
            if owner_rating is not None:
                record.owner_rating = owner_rating
            if qualitative_feedback is not None:
                record.qualitative_feedback = qualitative_feedback
            if perceived_utility is not None:
                record.perceived_utility = perceived_utility
            if non_completion_reason is not None:
                record.non_completion_reason = non_completion_reason
            if still_relevant is not None:
                record.still_relevant = still_relevant
            if measured_outcome_summary is not None:
                record.measured_outcome_summary = measured_outcome_summary
            if baseline_metrics is not None:
                record.baseline_metrics = baseline_metrics
            if post_metrics is not None:
                record.post_metrics = post_metrics
            if observed_changes is not None:
                record.observed_changes = observed_changes

        # Synchronize corresponding RecommendationLifecycleState
        lifecycle_stmt = select(RecommendationLifecycleState).where(
            RecommendationLifecycleState.business_id == business_id,
            RecommendationLifecycleState.recommendation_id == recommendation_id,
        )
        lifecycle = self.db.scalars(lifecycle_stmt).first()

        new_lifecycle_status: Optional[str] = None
        if record.is_completed:
            new_lifecycle_status = "Completed"
        elif record.is_abandoned:
            new_lifecycle_status = "Dismissed"
        elif record.is_started:
            new_lifecycle_status = "In Progress"

        if new_lifecycle_status:
            if lifecycle is None:
                lifecycle = RecommendationLifecycleState(
                    business_id=business_id,
                    recommendation_id=recommendation_id,
                    status=new_lifecycle_status,
                    notes=notes or qualitative_feedback,
                    status_updated_at=now,
                )
                self.db.add(lifecycle)
            else:
                lifecycle.status = new_lifecycle_status
                lifecycle.status_updated_at = now
                if notes or qualitative_feedback:
                    lifecycle.notes = notes or qualitative_feedback

        self.db.commit()
        self.db.refresh(record)
        return record

    def record_audit_event(
        self,
        business_id: int,
        recommendation_id: str,
        title: str,
        category: str,
        priority: str,
        priority_score: int,
        event_type: str,
        event_notes: Optional[str] = None,
        metrics_snapshot: Optional[dict[str, Any]] = None,
        evidence_summary: Optional[str] = None,
        evidence_version: Optional[str] = None,
    ) -> RecommendationVersionHistory:
        """Append an immutable audit entry to version history."""
        # Calculate next version number for this recommendation
        count_stmt = select(func.count(RecommendationVersionHistory.id)).where(
            RecommendationVersionHistory.business_id == business_id,
            RecommendationVersionHistory.recommendation_id == recommendation_id,
        )
        current_count = self.db.scalar(count_stmt) or 0
        version = current_count + 1

        history_item = RecommendationVersionHistory(
            business_id=business_id,
            recommendation_id=recommendation_id,
            version=version,
            title=title,
            category=category,
            priority=priority,
            priority_score=priority_score,
            evidence_version=evidence_version,
            evidence_summary=evidence_summary,
            event_type=event_type,
            event_notes=event_notes,
            metrics_snapshot=metrics_snapshot,
        )
        self.db.add(history_item)
        self.db.commit()
        self.db.refresh(history_item)
        return history_item

    def get_history_for_recommendation(
        self, business_id: int, recommendation_id: str
    ) -> list[RecommendationVersionHistory]:
        """Fetch complete immutable audit events for a recommendation in chronological order."""
        stmt = (
            select(RecommendationVersionHistory)
            .where(
                RecommendationVersionHistory.business_id == business_id,
                RecommendationVersionHistory.recommendation_id == recommendation_id,
            )
            .order_by(RecommendationVersionHistory.version.asc(), RecommendationVersionHistory.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_complete_history(
        self, business_id: int, limit: int = 100
    ) -> list[RecommendationVersionHistory]:
        """Fetch recent immutable audit events across all recommendations for a business."""
        stmt = (
            select(RecommendationVersionHistory)
            .where(RecommendationVersionHistory.business_id == business_id)
            .order_by(RecommendationVersionHistory.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

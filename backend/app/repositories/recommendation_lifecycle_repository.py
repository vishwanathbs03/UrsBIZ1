"""Repository for recommendation lifecycle state persistence (Phase 5).

Enforces business isolation and provides auditable state management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.recommendation_lifecycle import RecommendationLifecycleState


class RecommendationLifecycleRepository:
    """Encapsulates data access and persistence for recommendation lifecycle states."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_states_for_business(
        self, business_id: int
    ) -> dict[str, RecommendationLifecycleState]:
        """Fetch all persistent recommendation states for a business, keyed by recommendation_id."""
        stmt = select(RecommendationLifecycleState).where(
            RecommendationLifecycleState.business_id == business_id
        )
        records = self.db.scalars(stmt).all()
        return {r.recommendation_id: r for r in records}

    def get_state(
        self, business_id: int, recommendation_id: str
    ) -> Optional[RecommendationLifecycleState]:
        """Fetch persistent state for a specific business and recommendation."""
        stmt = select(RecommendationLifecycleState).where(
            RecommendationLifecycleState.business_id == business_id,
            RecommendationLifecycleState.recommendation_id == recommendation_id,
        )
        return self.db.scalars(stmt).first()

    def update_status(
        self,
        business_id: int,
        recommendation_id: str,
        status: str,
        notes: str | None = None,
    ) -> RecommendationLifecycleState:
        """Update or create a recommendation state transition with concurrency protection and idempotency."""
        now = datetime.now(timezone.utc)
        record = self.get_state(business_id, recommendation_id)

        # Idempotent check — if already in desired state with identical notes, skip redundant DB write
        if record is not None and record.status == status and (notes is None or record.notes == notes):
            return record

        try:
            if record is None:
                record = RecommendationLifecycleState(
                    business_id=business_id,
                    recommendation_id=recommendation_id,
                    status=status,
                    notes=notes,
                    first_viewed_at=now if status == "Viewed" else None,
                    status_updated_at=now,
                )
                self.db.add(record)
                self.db.commit()
            else:
                record.status = status
                record.status_updated_at = now
                if notes is not None:
                    record.notes = notes
                if status == "Viewed" and record.first_viewed_at is None:
                    record.first_viewed_at = now
                self.db.commit()

            self.db.refresh(record)
            return record
        except IntegrityError:
            # Concurrent insert race condition: reload existing record and update
            self.db.rollback()
            existing = self.get_state(business_id, recommendation_id)
            if existing is not None:
                existing.status = status
                existing.status_updated_at = now
                if notes is not None:
                    existing.notes = notes
                self.db.commit()
                self.db.refresh(existing)
                return existing
            raise
        except Exception:
            self.db.rollback()
            raise

    def record_first_views(
        self, business_id: int, recommendation_ids: list[str]
    ) -> None:
        """Record view event for any newly surfaced recommendations without overriding in-progress or accepted states."""
        now = datetime.now(timezone.utc)
        existing = self.get_states_for_business(business_id)
        changed = False

        for rec_id in recommendation_ids:
            if rec_id not in existing:
                new_state = RecommendationLifecycleState(
                    business_id=business_id,
                    recommendation_id=rec_id,
                    status="New",
                    first_viewed_at=now,
                    status_updated_at=now,
                )
                self.db.add(new_state)
                changed = True

        if changed:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()

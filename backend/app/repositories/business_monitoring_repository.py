"""Repository for Proactive AI Business Monitoring & Event-Driven Intelligence (Phase 5).

Handles database persistence and queries for:
  - BusinessSignalEvent (active signals, deduplication lookups, cooldown checks)
  - BusinessMonitoringPreferences (settings retrieval, safe updates)
  - RecommendationRefreshRecord (re-evaluation audit trail)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.business_monitoring import (
    BusinessMonitoringPreferences,
    BusinessSignalEvent,
    RecommendationRefreshRecord,
)
from app.schemas.business_monitoring import MonitoringPreferencesUpdate


class BusinessMonitoringRepository:
    """Database repository for business monitoring signals, preferences, and refresh history."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------------------------------------------------- #
    # Preferences Management                                                  #
    # ----------------------------------------------------------------------- #

    def get_or_create_preferences(self, business_id: int) -> BusinessMonitoringPreferences:
        """Fetch business monitoring preferences or create defaults if not found."""
        stmt = select(BusinessMonitoringPreferences).where(
            BusinessMonitoringPreferences.business_id == business_id
        )
        prefs = self.db.scalars(stmt).first()
        if prefs is None:
            prefs = BusinessMonitoringPreferences(
                business_id=business_id,
                monitored_metrics=[
                    "revenue",
                    "customer_concentration",
                    "repeat_rate",
                    "product_margins",
                    "forecast_trends",
                    "health_score",
                    "cash_flow",
                ],
                areas_of_interest=[
                    "Revenue Growth",
                    "Customer Retention",
                    "Demand Planning",
                    "Cash Flow",
                    "Risk Mitigation",
                ],
                alert_frequency="REALTIME",
                preferred_notification_types=["in_app"],
                min_severity="LOW",
                cooldown_days=7,
            )
            self.db.add(prefs)
            self.db.commit()
            self.db.refresh(prefs)
        return prefs

    def update_preferences(
        self, business_id: int, payload: MonitoringPreferencesUpdate
    ) -> BusinessMonitoringPreferences:
        """Update owner preferences with critical risk protection rules."""
        prefs = self.get_or_create_preferences(business_id)

        if payload.monitored_metrics is not None:
            prefs.monitored_metrics = payload.monitored_metrics
        if payload.areas_of_interest is not None:
            prefs.areas_of_interest = payload.areas_of_interest
        if payload.alert_frequency is not None:
            prefs.alert_frequency = payload.alert_frequency
        if payload.preferred_notification_types is not None:
            prefs.preferred_notification_types = payload.preferred_notification_types
        if payload.min_severity is not None:
            prefs.min_severity = payload.min_severity
        if payload.cooldown_days is not None:
            prefs.cooldown_days = payload.cooldown_days

        prefs.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(prefs)
        return prefs

    # ----------------------------------------------------------------------- #
    # Signal Events Persistence & Queries                                     #
    # ----------------------------------------------------------------------- #

    def get_signal_by_event_id(self, business_id: int, event_id: str) -> Optional[BusinessSignalEvent]:
        """Lookup a specific signal event by event_id for a business."""
        stmt = select(BusinessSignalEvent).where(
            BusinessSignalEvent.business_id == business_id,
            BusinessSignalEvent.event_id == event_id,
        )
        return self.db.scalars(stmt).first()

    def find_recent_event_by_fingerprint(
        self, business_id: int, fingerprint: str, within_days: int = 7
    ) -> Optional[BusinessSignalEvent]:
        """Find recent event matching fingerprint within cooldown window."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
        stmt = (
            select(BusinessSignalEvent)
            .where(
                BusinessSignalEvent.business_id == business_id,
                BusinessSignalEvent.fingerprint == fingerprint,
                BusinessSignalEvent.detected_at >= cutoff,
            )
            .order_by(desc(BusinessSignalEvent.detected_at))
        )
        return self.db.scalars(stmt).first()

    def record_signal_event(self, event: BusinessSignalEvent) -> BusinessSignalEvent:
        """Save a new business signal event."""
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_signals(
        self,
        business_id: int,
        include_suppressed: bool = False,
        min_severity: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusinessSignalEvent]:
        """List signals for the business dashboard feed."""
        stmt = select(BusinessSignalEvent).where(
            BusinessSignalEvent.business_id == business_id
        )
        if not include_suppressed:
            stmt = stmt.where(BusinessSignalEvent.is_suppressed.is_(False))

        # Severity filter ordering
        severity_order = {
            "INFORMATIONAL": ["INFORMATIONAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "LOW": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "MEDIUM": ["MEDIUM", "HIGH", "CRITICAL"],
            "HIGH": ["HIGH", "CRITICAL"],
            "CRITICAL": ["CRITICAL"],
        }
        if min_severity and min_severity in severity_order:
            allowed = severity_order[min_severity]
            stmt = stmt.where(BusinessSignalEvent.severity.in_(allowed))

        stmt = stmt.order_by(
            desc(BusinessSignalEvent.detected_at),
            desc(BusinessSignalEvent.id),
        ).limit(limit)

        return list(self.db.scalars(stmt).all())

    def dismiss_signal(self, business_id: int, event_id: str) -> Optional[BusinessSignalEvent]:
        """Mark a signal as acknowledged/dismissed."""
        event = self.get_signal_by_event_id(business_id, event_id)
        if event:
            event.status = "ACKNOWLEDGED"
            event.resolved_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(event)
        return event

    # ----------------------------------------------------------------------- #
    # Recommendation Refresh Audit                                            #
    # ----------------------------------------------------------------------- #

    def record_refresh(self, record: RecommendationRefreshRecord) -> RecommendationRefreshRecord:
        """Record a recommendation refresh event."""
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_recent_refreshes(
        self, business_id: int, limit: int = 50
    ) -> list[RecommendationRefreshRecord]:
        """List recent recommendation refreshes for a business."""
        stmt = (
            select(RecommendationRefreshRecord)
            .where(RecommendationRefreshRecord.business_id == business_id)
            .order_by(desc(RecommendationRefreshRecord.refreshed_at))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

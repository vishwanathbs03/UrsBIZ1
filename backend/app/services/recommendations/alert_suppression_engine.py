"""Duplicate Alert and Notification Suppression Engine (Phase 5).

Prevents alert fatigue while ensuring critical risks are never lost:
  - Generates stable event fingerprints (hash of business_id, event_type, relevant_entity).
  - Evaluates configurable cooldown windows (from BusinessMonitoringPreferences).
  - Detects material escalation (condition worsens by >= 15% delta) and bypasses cooldown.
  - Suppresses duplicate generic alerts when an equivalent recommendation is already active.
  - Strictly preserves CRITICAL risks: critical safety & solvency risks are NEVER permanently suppressed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business_monitoring import (
    BusinessMonitoringPreferences,
    BusinessSignalEvent,
)
from app.repositories.business_monitoring_repository import BusinessMonitoringRepository
from app.repositories.recommendation_lifecycle_repository import RecommendationLifecycleRepository
from app.schemas.business_monitoring import EventSeverity


class AlertSuppressionEngine:
    """Manages event deduplication, cooldowns, active recommendation suppression, and escalation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.monitoring_repo = BusinessMonitoringRepository(db)
        self.lifecycle_repo = RecommendationLifecycleRepository(db)

    def compute_fingerprint(
        self, business_id: int, event_type: str, relevant_entity: Optional[str] = None
    ) -> str:
        """Deterministic fingerprint for duplicate identification."""
        raw = f"{business_id}:{event_type}:{relevant_entity or 'general'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def evaluate_event_suppression(
        self,
        business_id: int,
        event_dict: dict[str, Any],
        prefs: BusinessMonitoringPreferences,
    ) -> dict[str, Any]:
        """Determine whether an event should be surfaced, escalated, or suppressed."""
        event_type = event_dict.get("event_type", "")
        relevant_entity = event_dict.get("relevant_entity")
        severity = event_dict.get("severity", EventSeverity.MEDIUM.value)
        evidence = event_dict.get("evidence", {})

        fingerprint = self.compute_fingerprint(business_id, event_type, relevant_entity)
        event_dict["fingerprint"] = fingerprint

        # ------------------------------------------------------------------- #
        # Rule 1: CRITICAL risks are NEVER permanently suppressed             #
        # ------------------------------------------------------------------- #
        is_critical = severity == EventSeverity.CRITICAL.value

        # ------------------------------------------------------------------- #
        # Rule 2: Active Recommendation Collision Check                       #
        # ------------------------------------------------------------------- #
        # Map event types to candidate recommendation IDs
        rec_id_mapping = {
            "CUSTOMER_CONCENTRATION_INCREASED": "cust_concentration_defense",
            "REVENUE_DECLINE_DETECTED": "rev_decline_stabilization",
            "CRITICAL_READINESS_GAP_DETECTED": "digital_gstin_onboarding",
            "PRODUCT_PERFORMANCE_DETERIORATED": "prod_portfolio_expansion",
        }
        candidate_rec_id = rec_id_mapping.get(event_type)
        if candidate_rec_id:
            lc = self.lifecycle_repo.get_state(business_id, candidate_rec_id)
            if lc and lc.status in ["Accepted", "In Progress"]:
                event_dict["linked_recommendation_id"] = candidate_rec_id
                # If not critical, suppress generic alert as action is already in-flight
                if not is_critical:
                    event_dict["is_suppressed"] = True
                    event_dict["suppression_reason"] = f"ACTIVE_RECOMMENDATION_EXISTS: {candidate_rec_id}"
                    return event_dict

        # ------------------------------------------------------------------- #
        # Rule 3: Cooldown and Material Escalation Detection                  #
        # ------------------------------------------------------------------- #
        cooldown_days = prefs.cooldown_days or 7
        recent_event = self.monitoring_repo.find_recent_event_by_fingerprint(
            business_id=business_id,
            fingerprint=fingerprint,
            within_days=cooldown_days,
        )

        if recent_event is not None:
            # Check for material escalation (worsening >= 15% delta)
            is_escalated, escalation_reason = self._check_material_escalation(
                recent_event=recent_event, current_evidence=evidence, event_type=event_type
            )

            if is_escalated:
                # Bypass cooldown and escalate
                event_dict["is_suppressed"] = False
                event_dict["escalation_level"] = recent_event.escalation_level + 1
                event_dict["suppression_reason"] = None
                event_dict["title"] = f"[ESCALATED] {event_dict['title']}"
                event_dict["why_it_matters"] += f" Condition has worsened: {escalation_reason}"
                return event_dict

            # If not escalated and within cooldown:
            if not is_critical:
                event_dict["is_suppressed"] = True
                event_dict["suppression_reason"] = f"COOLDOWN_ACTIVE: {cooldown_days}d cooldown window"
                event_dict["escalation_level"] = recent_event.escalation_level
                return event_dict
            else:
                # Critical severity bypasses cooldown if status was previously resolved or 3 days elapsed
                if recent_event.status in ["RESOLVED", "ACKNOWLEDGED"]:
                    event_dict["is_suppressed"] = False
                    event_dict["suppression_reason"] = None
                    return event_dict

        # Default: Not suppressed
        event_dict["is_suppressed"] = False
        event_dict["suppression_reason"] = None
        event_dict["escalation_level"] = 0
        return event_dict

    def _check_material_escalation(
        self,
        recent_event: BusinessSignalEvent,
        current_evidence: dict[str, Any],
        event_type: str,
    ) -> tuple[bool, str]:
        """Check if metric has deteriorated by >= 15% compared to the prior alert."""
        prev_evidence = recent_event.evidence or {}

        # Revenue decline escalation: drop deepened by >= 15 percentage points
        if event_type == "REVENUE_DECLINE_DETECTED":
            prev_drop = abs(prev_evidence.get("change_pct", 0.0))
            curr_drop = abs(current_evidence.get("change_pct", 0.0))
            if curr_drop - prev_drop >= 15.0:
                return True, f"Revenue decline widened from -{prev_drop:.1f}% to -{curr_drop:.1f}%."

        # Customer concentration escalation: share increased by >= 15 percentage points
        if event_type == "CUSTOMER_CONCENTRATION_INCREASED":
            prev_share = prev_evidence.get("top_customer_share_pct", 0.0)
            curr_share = current_evidence.get("top_customer_share_pct", 0.0)
            if curr_share - prev_share >= 15.0:
                return True, f"Top client share jumped from {prev_share:.1f}% to {curr_share:.1f}%."

        return False, ""

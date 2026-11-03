"""Business Alerts / Event Centre Orchestration Service (Prompt 6.22).

Provides authoritative business alert and event management:
  - Scoped strictly to the authenticated user's active business
  - Filterable by severity, status, and event_nature
  - Deterministic evaluation and duplicate suppression
  - Enforced status lifecycle state machine with immutable audit logging
  - Grounded AI explanations with deterministic fallback (non-mutating)
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_monitoring import (
    BusinessSignalEvent,
    BusinessSignalEventAudit,
)
from app.schemas.business_monitoring import (
    AlertAuditHistoryItem,
    AlertExplainResponse,
    AlertSummaryResponse,
    BusinessSignalItem,
    MonitoringEvaluationResponse,
)
from app.services.ai.resilient_client import ResilientGeminiClient
from app.services.recommendations.proactive_monitoring_service import (
    ProactiveMonitoringService,
)

logger = logging.getLogger(__name__)


# Valid state machine transitions
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "NEW": ["ACKNOWLEDGED", "DISMISSED"],
    "ACKNOWLEDGED": ["RESOLVED", "DISMISSED"],
    "RESOLVED": [],  # Terminal
    "DISMISSED": [],  # Terminal
}


class BusinessAlertsService:
    """Service handling business alert feeds, state transitions, audits, and explanations."""

    def __init__(
        self,
        db: Session,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ) -> None:
        self.db = db
        self.gemini_client = gemini_client or ResilientGeminiClient()
        self.monitoring_service = ProactiveMonitoringService(db, self.gemini_client)

    # ----------------------------------------------------------------------- #
    # 1. Alert Retrieval & Filtering                                          #
    # ----------------------------------------------------------------------- #

    def list_alerts(
        self,
        business_id: int,
        severity: Optional[str] = None,
        alert_status: Optional[str] = None,
        event_nature: Optional[str] = None,
        include_suppressed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BusinessSignalItem], int]:
        """Fetch tenant-isolated alert records matching query criteria."""
        stmt = select(BusinessSignalEvent).where(
            BusinessSignalEvent.business_id == business_id
        )

        if not include_suppressed:
            stmt = stmt.where(BusinessSignalEvent.is_suppressed.is_(False))

        if severity:
            stmt = stmt.where(
                func.upper(BusinessSignalEvent.severity) == severity.upper()
            )

        if alert_status:
            stmt = stmt.where(
                func.upper(BusinessSignalEvent.status) == alert_status.upper()
            )

        if event_nature:
            stmt = stmt.where(
                func.upper(BusinessSignalEvent.event_nature) == event_nature.upper()
            )

        # Count matching
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = self.db.scalar(count_stmt) or 0

        # Fetch page
        stmt = (
            stmt.order_by(desc(BusinessSignalEvent.detected_at))
            .offset(offset)
            .limit(limit)
        )
        records = self.db.scalars(stmt).all()

        items = [self._to_schema_item(r) for r in records]
        return items, total_count

    def get_alert(self, business_id: int, event_id: str) -> BusinessSignalEvent:
        """Fetch single alert verifying business tenant isolation."""
        stmt = select(BusinessSignalEvent).where(
            BusinessSignalEvent.business_id == business_id,
            BusinessSignalEvent.event_id == event_id,
        )
        record = self.db.scalars(stmt).first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert '{event_id}' not found for the active business.",
            )
        return record

    # ----------------------------------------------------------------------- #
    # 2. Aggregated Summary Counters                                          #
    # ----------------------------------------------------------------------- #

    def get_summary(self, business_id: int) -> AlertSummaryResponse:
        """Calculate authoritative counters for the Event Centre dashboard."""
        stmt = select(BusinessSignalEvent).where(
            BusinessSignalEvent.business_id == business_id,
            BusinessSignalEvent.is_suppressed.is_(False),
        )
        records = self.db.scalars(stmt).all()

        total = len(records)
        new_cnt = sum(1 for r in records if r.status == "NEW")
        ack_cnt = sum(1 for r in records if r.status == "ACKNOWLEDGED")
        res_cnt = sum(1 for r in records if r.status == "RESOLVED")
        dis_cnt = sum(1 for r in records if r.status == "DISMISSED")

        crit_cnt = sum(1 for r in records if r.severity.upper() == "CRITICAL")
        high_cnt = sum(1 for r in records if r.severity.upper() == "HIGH")
        med_cnt = sum(1 for r in records if r.severity.upper() == "MEDIUM")
        low_info_cnt = sum(
            1 for r in records if r.severity.upper() in ["LOW", "INFORMATIONAL"]
        )

        conf_cnt = sum(1 for r in records if r.event_nature == "CONFIRMED_EVENT")
        warn_cnt = sum(1 for r in records if r.event_nature == "WARNING")
        est_cnt = sum(1 for r in records if r.event_nature == "ESTIMATE")
        assump_cnt = sum(1 for r in records if r.event_nature == "ASSUMPTION")

        latest_dt = max((r.detected_at for r in records), default=None)

        return AlertSummaryResponse(
            business_id=business_id,
            total_alerts=total,
            new_count=new_cnt,
            acknowledged_count=ack_cnt,
            resolved_count=res_cnt,
            dismissed_count=dis_cnt,
            critical_count=crit_cnt,
            high_count=high_cnt,
            medium_count=med_cnt,
            low_and_info_count=low_info_cnt,
            confirmed_events_count=conf_cnt,
            warnings_count=warn_cnt,
            estimates_count=est_cnt,
            assumptions_count=assump_cnt,
            last_evaluated_at=latest_dt.isoformat() if latest_dt else None,
        )

    # ----------------------------------------------------------------------- #
    # 3. Deterministic Evaluation Scan                                        #
    # ----------------------------------------------------------------------- #

    def evaluate_business(self, business: Business) -> MonitoringEvaluationResponse:
        """Trigger incremental proactive change detection scan."""
        return self.monitoring_service.evaluate_business_changes(business)

    # ----------------------------------------------------------------------- #
    # 4. Status Transition Lifecycle & Audit Logging                          #
    # ----------------------------------------------------------------------- #

    def update_alert_status(
        self,
        business: Business,
        event_id: str,
        new_status: str,
        reason: Optional[str],
        user_id: int,
    ) -> BusinessSignalItem:
        """Enforces state machine transitions and logs immutable audit trail."""
        event = self.get_alert(business.id, event_id)
        current_status = event.status

        # If already at target status, return idempotently
        if current_status == new_status:
            return self._to_schema_item(event)

        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition from '{current_status}' to '{new_status}'. "
                    f"Allowed transitions: {allowed}."
                ),
            )

        # Update record
        event.status = new_status
        if new_status == "RESOLVED":
            event.resolved_at = datetime.now(timezone.utc)

        # Log audit entry
        audit_entry = BusinessSignalEventAudit(
            event_id=event.event_id,
            business_id=business.id,
            previous_status=current_status,
            new_status=new_status,
            changed_by_user_id=user_id,
            reason=reason,
        )
        self.db.add(audit_entry)
        self.db.commit()
        self.db.refresh(event)

        return self._to_schema_item(event)

    def get_alert_history(
        self, business_id: int, event_id: str
    ) -> list[AlertAuditHistoryItem]:
        """Retrieve complete immutable status transition history."""
        # Ensure alert exists and belongs to business
        self.get_alert(business_id, event_id)

        stmt = (
            select(BusinessSignalEventAudit)
            .where(
                BusinessSignalEventAudit.business_id == business_id,
                BusinessSignalEventAudit.event_id == event_id,
            )
            .order_by(desc(BusinessSignalEventAudit.id))
        )
        audits = self.db.scalars(stmt).all()

        return [
            AlertAuditHistoryItem(
                id=a.id,
                event_id=a.event_id,
                business_id=a.business_id,
                previous_status=a.previous_status,
                new_status=a.new_status,
                changed_by_user_id=a.changed_by_user_id,
                changed_at=a.changed_at.isoformat(),
                reason=a.reason,
            )
            for a in audits
        ]

    # ----------------------------------------------------------------------- #
    # 5. Grounded AI Explanation (Strictly Non-Mutating)                      #
    # ----------------------------------------------------------------------- #

    def explain_alert(
        self,
        business_id: int,
        event_id: str,
        language: str = "en",
    ) -> AlertExplainResponse:
        """Generate plain-language explanation without altering underlying alert evidence."""
        event = self.get_alert(business_id, event_id)

        system_prompt = (
            "You are the UrsBiz AI Business Advisor. Explain business alerts clearly and practically for an MSME owner."
        )
        user_content = (
            f"Explain the following business alert clearly for an MSME owner.\n"
            f"Title: {event.title}\n"
            f"Severity: {event.severity}\n"
            f"Event Nature: {event.event_nature}\n"
            f"What Changed: {event.what_changed}\n"
            f"Why It Matters: {event.why_it_matters}\n"
            f"Supporting Evidence: {json.dumps(event.evidence, indent=2)}\n"
            f"Suggested Action: {event.suggested_action}\n\n"
            f"Provide a 2-3 paragraph plain-language explanation in {'Kannada (ಕನ್ನಡ)' if language == 'kn' else 'English'}.\n"
            f"Explain what the evidence means, why the business owner should take action now, and practical first steps."
        )

        is_fallback = False
        provider_used = "gemini-2.0-flash"
        explanation_text = ""

        try:
            if hasattr(self.gemini_client, "execute_chat_completion"):
                content = self.gemini_client.execute_chat_completion(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    max_tokens=500,
                )
                if content and content.strip():
                    explanation_text = content.strip()
                else:
                    is_fallback = True
            elif hasattr(self.gemini_client, "generate"):
                resp = self.gemini_client.generate(f"{system_prompt}\n\n{user_content}")
                if resp and getattr(resp, "text", None):
                    explanation_text = resp.text.strip()
                else:
                    is_fallback = True
            else:
                is_fallback = True
        except Exception as exc:
            logger.warning(f"AI explanation call failed for alert {event_id}: {exc}")
            is_fallback = True

        if is_fallback or not explanation_text:
            provider_used = "deterministic_fallback"
            if language == "kn":
                explanation_text = (
                    f"ವ್ಯವಹಾರ ಎಚ್ಚರಿಕೆ ವಿವರಣೆ:\n\n"
                    f"ಸೂಚನೆ: {event.title}\n"
                    f"ವರ್ಗ: {event.event_nature} ({event.severity} ತೀವ್ರತೆ)\n\n"
                    f"ಏನು ಬದಲಾಗಿದೆ: {event.what_changed}\n\n"
                    f"ಪ್ರಾಮುಖ್ಯತೆ: {event.why_it_matters}\n\n"
                    f"ಸೂಚಿಸಿದ ಕ್ರಮ: {event.suggested_action}"
                )
            else:
                explanation_text = (
                    f"Authoritative Alert Summary:\n\n"
                    f"{event.title} is classified as a {event.event_nature} with {event.severity} severity.\n\n"
                    f"Observation: {event.what_changed}\n\n"
                    f"Business Impact: {event.why_it_matters}\n\n"
                    f"Recommended Action: {event.suggested_action}\n\n"
                    f"Supporting Evidence Data: {json.dumps(event.evidence, indent=2)}"
                )

        return AlertExplainResponse(
            event_id=event.event_id,
            title=event.title,
            severity=event.severity,
            event_nature=event.event_nature,
            explanation=explanation_text,
            language=language,
            provider_used=provider_used,
            is_fallback=is_fallback,
        )

    # ----------------------------------------------------------------------- #
    # Helper Serialization                                                    #
    # ----------------------------------------------------------------------- #

    def _to_schema_item(self, event: BusinessSignalEvent) -> BusinessSignalItem:
        sev = event.severity.upper()
        if sev == "CRITICAL":
            score = 95
        elif sev == "HIGH":
            score = 75
        elif sev == "MEDIUM":
            score = 55
        else:
            score = 30

        return BusinessSignalItem(
            event_id=event.event_id,
            business_id=event.business_id,
            event_type=event.event_type,
            event_nature=event.event_nature,
            source=event.source,
            relevant_entity=event.relevant_entity,
            detected_at=event.detected_at.isoformat() if event.detected_at else datetime.now(timezone.utc).isoformat(),
            evidence=event.evidence or {},
            severity=event.severity,
            priority_score=score,
            data_period=event.data_period,
            event_version=event.event_version,
            title=event.title,
            what_changed=event.what_changed,
            why_it_matters=event.why_it_matters,
            suggested_action=event.suggested_action,
            confidence=event.confidence,
            is_suppressed=event.is_suppressed,
            suppression_reason=event.suppression_reason,
            escalation_level=event.escalation_level,
            linked_recommendation_id=event.linked_recommendation_id,
            status=event.status,
            resolved_at=event.resolved_at.isoformat() if event.resolved_at else None,
        )

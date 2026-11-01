"""Proactive Business Monitoring Service (Phase 5).

Master orchestrator for event-driven proactive business intelligence:
  - Incremental change detection across 10 business dimensions
  - Duplicate alert suppression, cooldown tracking, and escalation
  - Continuous recommendation re-evaluation and lifecycle refresh
  - Proactive business signals & opportunities feed for dashboard
  - Grounded natural-language proactive Q&A
  - Business-specific monitoring preferences with critical safety preservation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import uuid
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_monitoring import (
    BusinessMonitoringPreferences,
    BusinessSignalEvent,
)
from app.repositories.business_monitoring_repository import BusinessMonitoringRepository
from app.schemas.business_monitoring import (
    BusinessSignalItem,
    BusinessSignalsFeedResponse,
    MonitoringEvaluationResponse,
    MonitoringPreferencesSchema,
    MonitoringPreferencesUpdate,
    RecommendationRefreshDetail,
)
from app.services.ai.resilient_client import ResilientGeminiClient
from app.services.recommendations.alert_suppression_engine import AlertSuppressionEngine
from app.services.recommendations.change_detection_engine import ChangeDetectionEngine
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.recommendation_refresh_engine import RecommendationRefreshEngine

logger = logging.getLogger(__name__)


class ProactiveMonitoringService:
    """End-to-end service for proactive monitoring, event triggers, and signals feed."""

    def __init__(
        self,
        db: Session,
        gemini_client: Optional[ResilientGeminiClient] = None,
    ) -> None:
        self.db = db
        self.gemini_client = gemini_client or ResilientGeminiClient()
        self.monitoring_repo = BusinessMonitoringRepository(db)
        self.context_service = RecommendationContextService(db)
        self.change_engine = ChangeDetectionEngine(db)
        self.suppression_engine = AlertSuppressionEngine(db)
        self.refresh_engine = RecommendationRefreshEngine(db)

    # ----------------------------------------------------------------------- #
    # 1. Incremental Business Change Evaluation                               #
    # ----------------------------------------------------------------------- #

    def evaluate_business_changes(
        self, business: Business, now: Optional[datetime] = None
    ) -> MonitoringEvaluationResponse:
        """Run bounded change detection, alert suppression, and recommendation refresh."""
        if now is None:
            now = datetime.now(timezone.utc)

        # 1. Build unified context
        ctx = self.context_service.build_context(business)

        # 2. Retrieve owner preferences
        prefs = self.monitoring_repo.get_or_create_preferences(business.id)

        # 3. Detect raw change events
        raw_events = self.change_engine.scan_all_changes(business, ctx, now)

        # 4. Filter through duplicate suppression & escalation
        evaluated_events: list[dict[str, Any]] = []
        new_events_count = 0
        suppressed_count = 0

        for raw_evt in raw_events:
            processed = self.suppression_engine.evaluate_event_suppression(
                business_id=business.id,
                event_dict=raw_evt,
                prefs=prefs,
            )
            evaluated_events.append(processed)

            # Persist if not in active cooldown or if escalated
            if not processed.get("is_suppressed", False):
                new_events_count += 1
                evt_id = f"evt_{uuid.uuid4().hex[:12]}"
                event_model = BusinessSignalEvent(
                    event_id=evt_id,
                    business_id=business.id,
                    event_type=processed["event_type"],
                    source=processed["source"],
                    relevant_entity=processed.get("relevant_entity"),
                    detected_at=now,
                    evidence=processed.get("evidence", {}),
                    severity=processed["severity"],
                    data_period=processed.get("data_period", "current"),
                    event_version=1,
                    fingerprint=processed["fingerprint"],
                    is_suppressed=False,
                    suppression_reason=None,
                    escalation_level=processed.get("escalation_level", 0),
                    linked_recommendation_id=processed.get("linked_recommendation_id"),
                    status="NEW",
                    title=processed["title"],
                    what_changed=processed["what_changed"],
                    why_it_matters=processed["why_it_matters"],
                    suggested_action=processed["suggested_action"],
                    confidence=processed.get("confidence", 0.85),
                )
                self.monitoring_repo.record_signal_event(event_model)
                processed["event_id"] = evt_id
            else:
                suppressed_count += 1
                processed["event_id"] = f"suppressed_{uuid.uuid4().hex[:8]}"

        # 5. Continuous Recommendation Refresh
        refreshes = self.refresh_engine.refresh_recommendations_for_events(
            business=business,
            ctx=ctx,
            detected_events=evaluated_events,
        )

        # 6. Format signals for response
        signal_items: list[BusinessSignalItem] = []
        for e in evaluated_events:
            signal_items.append(
                BusinessSignalItem(
                    event_id=e.get("event_id", ""),
                    business_id=business.id,
                    event_type=e["event_type"],
                    source=e["source"],
                    relevant_entity=e.get("relevant_entity"),
                    detected_at=now.isoformat(),
                    evidence=e.get("evidence", {}),
                    severity=e["severity"],
                    priority_score=e.get("priority_score", 50),
                    data_period=e.get("data_period", "current"),
                    event_version=1,
                    title=e["title"],
                    what_changed=e["what_changed"],
                    why_it_matters=e["why_it_matters"],
                    suggested_action=e["suggested_action"],
                    confidence=e.get("confidence", 0.85),
                    is_suppressed=e.get("is_suppressed", False),
                    suppression_reason=e.get("suppression_reason"),
                    escalation_level=e.get("escalation_level", 0),
                    linked_recommendation_id=e.get("linked_recommendation_id"),
                    status="NEW",
                )
            )

        return MonitoringEvaluationResponse(
            business_id=business.id,
            evaluated_at=now.isoformat(),
            new_events_detected=new_events_count,
            suppressed_events=suppressed_count,
            refreshed_recommendations=len(refreshes),
            signals=signal_items,
            recommendation_refreshes=refreshes,
        )

    # ----------------------------------------------------------------------- #
    # 2. Proactive Business Signals Feed                                      #
    # ----------------------------------------------------------------------- #

    def get_signals_feed(
        self,
        business: Business,
        min_severity: Optional[str] = None,
        limit: int = 50,
    ) -> BusinessSignalsFeedResponse:
        """Fetch unsuppressed active business signals for the owner dashboard feed."""
        # Auto-evaluate if no signals exist yet
        stored_signals = self.monitoring_repo.list_signals(
            business_id=business.id,
            include_suppressed=False,
            min_severity=min_severity,
            limit=limit,
        )
        if not stored_signals:
            eval_res = self.evaluate_business_changes(business)
            stored_signals = self.monitoring_repo.list_signals(
                business_id=business.id,
                include_suppressed=False,
                min_severity=min_severity,
                limit=limit,
            )

        items: list[BusinessSignalItem] = []
        crit_count = 0
        high_count = 0
        med_count = 0
        low_count = 0

        for s in stored_signals:
            sev = s.severity.upper()
            if sev == "CRITICAL":
                crit_count += 1
                score = 95
            elif sev == "HIGH":
                high_count += 1
                score = 75
            elif sev == "MEDIUM":
                med_count += 1
                score = 55
            else:
                low_count += 1
                score = 30

            items.append(
                BusinessSignalItem(
                    event_id=s.event_id,
                    business_id=s.business_id,
                    event_type=s.event_type,
                    source=s.source,
                    relevant_entity=s.relevant_entity,
                    detected_at=s.detected_at.isoformat() if s.detected_at else datetime.now(timezone.utc).isoformat(),
                    evidence=s.evidence or {},
                    severity=s.severity,
                    priority_score=score,
                    data_period=s.data_period,
                    event_version=s.event_version,
                    title=s.title,
                    what_changed=s.what_changed,
                    why_it_matters=s.why_it_matters,
                    suggested_action=s.suggested_action,
                    confidence=s.confidence,
                    is_suppressed=s.is_suppressed,
                    suppression_reason=s.suppression_reason,
                    escalation_level=s.escalation_level,
                    linked_recommendation_id=s.linked_recommendation_id,
                    status=s.status,
                )
            )

        return BusinessSignalsFeedResponse(
            business_id=business.id,
            total_signals=len(items),
            active_signals_count=len([i for i in items if i.status == "NEW"]),
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_and_info_count=low_count,
            signals=items,
            last_evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ----------------------------------------------------------------------- #
    # 3. Preferences Management (with Critical Risk Protection)                #
    # ----------------------------------------------------------------------- #

    def get_monitoring_preferences(self, business: Business) -> MonitoringPreferencesSchema:
        """Fetch monitoring configuration."""
        prefs = self.monitoring_repo.get_or_create_preferences(business.id)
        return MonitoringPreferencesSchema(
            business_id=business.id,
            monitored_metrics=prefs.monitored_metrics or [],
            areas_of_interest=prefs.areas_of_interest or [],
            alert_frequency=prefs.alert_frequency,
            preferred_notification_types=prefs.preferred_notification_types or ["in_app"],
            min_severity=prefs.min_severity,
            cooldown_days=prefs.cooldown_days,
            updated_at=prefs.updated_at.isoformat() if prefs.updated_at else None,
        )

    def update_monitoring_preferences(
        self, business: Business, payload: MonitoringPreferencesUpdate
    ) -> MonitoringPreferencesSchema:
        """Update preferences with critical safety preservation."""
        # Safety rule: min_severity cannot be set to exceed HIGH (CRITICAL risks must never be silenced)
        if payload.min_severity and payload.min_severity.upper() == "CRITICAL":
            payload.min_severity = "HIGH"

        prefs = self.monitoring_repo.update_preferences(business.id, payload)
        return self.get_monitoring_preferences(business)

    def dismiss_signal(self, business: Business, event_id: str) -> dict[str, Any]:
        """Acknowledge or dismiss a signal."""
        updated = self.monitoring_repo.dismiss_signal(business.id, event_id)
        if not updated:
            return {"status": "not_found", "event_id": event_id}
        return {"status": "acknowledged", "event_id": event_id, "resolved_at": updated.resolved_at.isoformat() if updated.resolved_at else None}

    # ----------------------------------------------------------------------- #
    # 4. Natural-Language Proactive Intelligence Q&A                          #
    # ----------------------------------------------------------------------- #

    def answer_proactive_question(
        self, business: Business, question: str
    ) -> dict[str, Any]:
        """Provide verified answers to proactive monitoring questions."""
        q_lower = question.lower()
        signals = self.monitoring_repo.list_signals(business.id, include_suppressed=False, limit=20)
        refreshes = self.monitoring_repo.list_recent_refreshes(business.id, limit=10)

        # Question Intent 1: "What changed in my business this week?" / "What changed recently?"
        if any(w in q_lower for w in ["what changed", "changes this week", "business changes", "what's new"]):
            if signals:
                bullets = [f"- **{s.title}** ({s.severity}): {s.what_changed}" for s in signals[:4]]
                answer = (
                    f"Here are the recent developments detected in your business data:\n\n"
                    + "\n".join(bullets)
                    + f"\n\n**Immediate Priority:** {signals[0].suggested_action}"
                )
            else:
                answer = "No significant fluctuations or negative deviations were detected in your business metrics recently. Operations and revenue remain stable."

            return {
                "question": question,
                "intent": "recent_business_changes",
                "direct_answer": answer,
                "relevant_signals": [s.event_id for s in signals[:4]],
                "time_period": "recent_7_to_30_days",
            }

        # Question Intent 2: "Are there any new risks?"
        elif any(w in q_lower for w in ["new risks", "any risks", "emerging risks", "threats"]):
            risks = [s for s in signals if s.severity in ["CRITICAL", "HIGH"]]
            if risks:
                bullets = [f"- **{r.title}**: {r.what_changed} *Why it matters:* {r.why_it_matters}" for r in risks[:3]]
                answer = (
                    f"Yes, **{len(risks)} priority risk(s)** require your attention:\n\n"
                    + "\n".join(bullets)
                    + f"\n\n**Recommended Step:** {risks[0].suggested_action}"
                )
            else:
                answer = "No critical or high-severity risks have been detected. Your client concentration and cash flow indicators are currently within acceptable thresholds."

            return {
                "question": question,
                "intent": "emerging_risks_check",
                "direct_answer": answer,
                "relevant_signals": [r.event_id for r in risks[:3]],
                "time_period": "current",
            }

        # Question Intent 3: "Have any new growth opportunities appeared?"
        elif any(w in q_lower for w in ["growth opportunities", "new opportunities", "growth signals", "opportunities"]):
            opps = [s for s in signals if "GROWTH" in s.event_type or "IMPROVED" in s.event_type or "SURGE" in s.event_type]
            if opps:
                bullets = [f"- **{o.title}**: {o.what_changed}" for o in opps[:3]]
                answer = (
                    f"We have identified **{len(opps)} positive momentum signal(s)**:\n\n"
                    + "\n".join(bullets)
                    + f"\n\n**Capitalize on this:** {opps[0].suggested_action}"
                )
            else:
                answer = "No new demand surges or sudden volume accelerations have appeared in this cycle. Focus on maintaining steady repeat customer orders."

            return {
                "question": question,
                "intent": "proactive_opportunities_check",
                "direct_answer": answer,
                "relevant_signals": [o.event_id for o in opps[:3]],
                "time_period": "current",
            }

        # Question Intent 4: "Why did this recommendation become more urgent?"
        elif any(w in q_lower for w in ["more urgent", "priority change", "why is this urgent", "recommendation become"]):
            if refreshes:
                r = refreshes[0]
                answer = (
                    f"Recommendation **{r.recommendation_id}** had its priority score updated from **{r.old_priority_score}** to **{r.new_priority_score}** "
                    f"due to *{r.refresh_reason}*.\n\n**Reasoning:** {r.explanation}"
                )
            else:
                answer = "No automated priority escalations have occurred recently. Active recommendations remain at their baseline calculated priority."

            return {
                "question": question,
                "intent": "recommendation_urgency_explanation",
                "direct_answer": answer,
                "relevant_signals": [],
                "time_period": "recent_refresh",
            }

        # Question Intent 5: "Which business signals should I pay attention to?"
        elif any(w in q_lower for w in ["pay attention to", "which signals", "important signals", "what should i watch"]):
            top_signals = signals[:3]
            if top_signals:
                bullets = [f"- **{s.title}** ({s.severity}): {s.suggested_action}" for s in top_signals]
                answer = (
                    "Based on verified data, you should focus on these top signals:\n\n"
                    + "\n".join(bullets)
                )
            else:
                answer = "All key monitoring metrics (revenue trends, customer concentration, and health scores) are operating normally. Continue standard weekly bookkeeping."

            return {
                "question": question,
                "intent": "top_signals_advisory",
                "direct_answer": answer,
                "relevant_signals": [s.event_id for s in top_signals],
                "time_period": "current",
            }

        # Default Fallback
        bullets = [f"- **{s.title}**: {s.what_changed}" for s in signals[:2]]
        fallback_msg = (
            "Here is the latest proactive monitoring summary for your business:\n\n"
            + ("\n".join(bullets) if bullets else "All monitored parameters are stable.")
        )
        return {
            "question": question,
            "intent": "general_monitoring_overview",
            "direct_answer": fallback_msg,
            "relevant_signals": [s.event_id for s in signals[:2]],
            "time_period": "current",
        }

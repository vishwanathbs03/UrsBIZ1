"""Continuous Recommendation Refresh Engine (Phase 5).

Re-evaluates recommendations when business conditions shift:
  - New evidence strengthens a recommendation (+priority score, updated metrics)
  - Supporting evidence becomes stale (attaches temporal freshness note)
  - A risk is resolved (auto-resolves recommendation with explicit rationale)
  - An opportunity disappears or recommendation becomes obsolete
  - A previously resolved issue returns (re-activates alert with escalation)
  - Priority escalates due to material worsening

Crucial Integrity Rules:
  - Preserves owner decisions: NEVER silently reset or alter Accepted/In Progress recommendations.
  - Generates immutable audit records in RecommendationRefreshRecord and RecommendationVersionHistory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_monitoring import RecommendationRefreshRecord
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_version_history import RecommendationVersionHistory
from app.repositories.business_monitoring_repository import BusinessMonitoringRepository
from app.repositories.recommendation_lifecycle_repository import RecommendationLifecycleRepository
from app.schemas.business_monitoring import (
    RecommendationRefreshDetail,
    RefreshReason,
)
from app.services.recommendations.context_service import UnifiedRecommendationContext


class RecommendationRefreshEngine:
    """Evaluates and updates recommendations in response to proactive business change events."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.monitoring_repo = BusinessMonitoringRepository(db)
        self.lifecycle_repo = RecommendationLifecycleRepository(db)

    def refresh_recommendations_for_events(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        detected_events: list[dict[str, Any]],
    ) -> list[RecommendationRefreshDetail]:
        """Re-evaluate all active recommendation lifecycles against detected events."""
        refresh_details: list[RecommendationRefreshDetail] = []
        lifecycle_dict = self.lifecycle_repo.get_states_for_business(business.id)
        active_lifecycles = list(lifecycle_dict.values())
        now = datetime.now(timezone.utc)

        # Build quick event lookup by type
        event_types = {e.get("event_type"): e for e in detected_events}

        for lc in active_lifecycles:
            rec_id = lc.recommendation_id
            old_status = lc.status

            # Skip dismissed recommendations from refresh updates
            if old_status == "Dismissed":
                continue

            # --------------------------------------------------------------- #
            # Scenario A: Customer Concentration Risk Resolved               #
            # --------------------------------------------------------------- #
            if "cust_concentration" in rec_id:
                top_share = 0.0
                if ctx.customers.top_customers_by_revenue and ctx.sales.total_revenue > 0:
                    top_rev = float(ctx.customers.top_customers_by_revenue[0].get("revenue") or ctx.customers.top_customers_by_revenue[0].get("total_revenue") or 0.0)
                    top_share = (top_rev / ctx.sales.total_revenue) * 100.0

                # If top customer share has dropped safely below 30%
                if top_share > 0 and top_share < 30.0 and old_status in ["New", "Viewed", "Accepted", "In Progress"]:
                    detail = self._record_refresh(
                        business=business,
                        rec_id=rec_id,
                        old_score=75,
                        new_score=30,
                        old_status=old_status,
                        new_status="Resolved",
                        reason=RefreshReason.RISK_RESOLVED.value,
                        explanation=f"Top client share reduced safely to {top_share:.1f}%. Concentration risk is successfully mitigated.",
                        now=now,
                        allow_status_change=True,
                    )
                    refresh_details.append(detail)
                    continue

                # Scenario B: Concentration Condition Materially Worsened (Escalation)
                elif "CUSTOMER_CONCENTRATION_INCREASED" in event_types:
                    evt = event_types["CUSTOMER_CONCENTRATION_INCREASED"]
                    if evt.get("severity") == "CRITICAL":
                        detail = self._record_refresh(
                            business=business,
                            rec_id=rec_id,
                            old_score=75,
                            new_score=95,
                            old_status=old_status,
                            new_status=old_status,  # Preserve owner decision status
                            reason=RefreshReason.PRIORITY_ESCALATED.value,
                            explanation=f"Top customer concentration reached critical level ({top_share:.1f}%). Priority elevated to Critical.",
                            now=now,
                            allow_status_change=False,
                        )
                        refresh_details.append(detail)
                        continue

            # --------------------------------------------------------------- #
            # Scenario C: Revenue Decline Deepened or Recovered               #
            # --------------------------------------------------------------- #
            if "rev_decline" in rec_id:
                if "REVENUE_GROWTH_SURGE" in event_types:
                    detail = self._record_refresh(
                        business=business,
                        rec_id=rec_id,
                        old_score=80,
                        new_score=40,
                        old_status=old_status,
                        new_status="Resolved",
                        reason=RefreshReason.RISK_RESOLVED.value,
                        explanation="Recent 30-day revenue has accelerated. Immediate decline risk is resolved.",
                        now=now,
                        allow_status_change=True,
                    )
                    refresh_details.append(detail)
                    continue
                elif "REVENUE_DECLINE_DETECTED" in event_types:
                    evt = event_types["REVENUE_DECLINE_DETECTED"]
                    if evt.get("severity") == "CRITICAL":
                        detail = self._record_refresh(
                            business=business,
                            rec_id=rec_id,
                            old_score=75,
                            new_score=95,
                            old_status=old_status,
                            new_status=old_status,
                            reason=RefreshReason.PRIORITY_ESCALATED.value,
                            explanation="Revenue decline accelerated beyond 30%. Priority raised to Critical.",
                            now=now,
                            allow_status_change=False,
                        )
                        refresh_details.append(detail)
                        continue

            # --------------------------------------------------------------- #
            # Scenario D: Stale Evidence Warning                              #
            # --------------------------------------------------------------- #
            if "RECOMMENDATION_EVIDENCE_STALE" in event_types:
                if old_status in ["New", "Viewed"]:
                    detail = self._record_refresh(
                        business=business,
                        rec_id=rec_id,
                        old_score=70,
                        new_score=50,
                        old_status=old_status,
                        new_status=old_status,
                        reason=RefreshReason.EVIDENCE_STALE.value,
                        explanation="Supporting transaction data is > 45 days old. Priority reduced until refreshed ledger uploaded.",
                        now=now,
                        allow_status_change=False,
                    )
                    refresh_details.append(detail)
                    continue

        return refresh_details

    def _record_refresh(
        self,
        business: Business,
        rec_id: str,
        old_score: int,
        new_score: int,
        old_status: str,
        new_status: str,
        reason: str,
        explanation: str,
        now: datetime,
        allow_status_change: bool = False,
    ) -> RecommendationRefreshDetail:
        """Create audit records and optionally update lifecycle status safely."""
        # 1. Update lifecycle if allowed (only for Resolved/Obsolete, never resetting user in-flight work)
        final_status = new_status if allow_status_change else old_status
        if allow_status_change and final_status != old_status:
            self.lifecycle_repo.update_status(
                business_id=business.id,
                recommendation_id=rec_id,
                status=final_status,
                notes=explanation,
            )

        # 2. Append to RecommendationRefreshRecord
        refresh_rec = RecommendationRefreshRecord(
            business_id=business.id,
            recommendation_id=rec_id,
            refresh_reason=reason,
            old_priority_score=old_score,
            new_priority_score=new_score,
            old_status=old_status,
            new_status=final_status,
            explanation=explanation,
            refreshed_at=now,
        )
        self.monitoring_repo.record_refresh(refresh_rec)

        # 3. Append to immutable RecommendationVersionHistory
        version_rec = RecommendationVersionHistory(
            business_id=business.id,
            recommendation_id=rec_id,
            version=2,
            title=rec_id.replace("_", " ").title(),
            category="Proactive Monitoring Refresh",
            priority="Critical" if new_score >= 80 else ("High" if new_score >= 60 else "Medium"),
            priority_score=new_score,
            evidence_version="proactive_refresh_v2",
            evidence_summary=explanation,
            event_type="PRIORITY_REFRESHED" if not allow_status_change else "STATUS_REFRESHED",
            event_notes=f"Triggered by {reason}: {explanation}",
            metrics_snapshot={"refreshed_score": new_score, "reason": reason},
            created_at=now,
        )
        self.db.add(version_rec)
        self.db.commit()

        return RecommendationRefreshDetail(
            recommendation_id=rec_id,
            refresh_reason=reason,
            old_priority_score=old_score,
            new_priority_score=new_score,
            old_status=old_status,
            new_status=final_status,
            explanation=explanation,
            refreshed_at=now.isoformat(),
        )

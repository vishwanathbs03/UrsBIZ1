"""Context-Aware Business Recommendation Engine (Phase 5).

Orchestrates the 4-tier recommendation architecture:
  Tier 1: Verified Business Data via RecommendationContextService
  Tier 2: Deterministic Rules & Prioritization via RecommendationRuleRegistry & RecommendationPrioritizationService
  Tier 3: Explainability & Action Plans via ExplanationService
  Tier 4: Lifecycle Tracking & Persistence via RecommendationLifecycleRepository

Enforces strict inventory and revenue boundaries:
  - Phase 3 has no inventory balances, supplier lead times, or stockout dates:
    recommends operational review of demand trends only; never calculates reorder
    quantities, safety stock, or liquidation targets.
  - Historical inactive-customer spend is historical evidence only:
    never claimed as guaranteed or calculated recoverable revenue.
  - Composite ID schema: rec_{rule_id}_{business_id}_{entity_id}_v{version}
    ensuring idempotent lifecycle tracking across data refreshes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
    SmartRecommendationsResponse,
)
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.prioritization_service import (
    RecommendationPrioritizationService,
)
from app.services.recommendations.rule_registry import RecommendationRuleRegistry

logger = logging.getLogger(__name__)


class SmartRecommendationEngine:
    """Core recommendation generation and deterministic prioritization orchestrator."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.context_service = RecommendationContextService(db)
        self.rule_registry = RecommendationRuleRegistry()
        self.prioritizer = RecommendationPrioritizationService()
        self.lifecycle_repo = RecommendationLifecycleRepository(db)

    def generate_recommendations(
        self,
        business: Business,
        category_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> SmartRecommendationsResponse:
        """Generate context-grounded recommendations for a business with lifecycle state tracking."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Tier 1: Aggregate verified context from all subsystems
        ctx = self.context_service.build_context(business)

        # Tier 2: Evaluate modular rules against verified context
        raw_candidates = self.rule_registry.evaluate_all(ctx)

        # Tier 4: Fetch persisted lifecycle states and record first views
        persisted_states = self.lifecycle_repo.get_states_for_business(business.id)
        candidate_ids = [c["id"] for c in raw_candidates]
        self.lifecycle_repo.record_first_views(business.id, candidate_ids)

        # Tier 2: Deterministic Prioritization Scoring
        scored_items: list[SmartRecommendationItem] = []
        for cand in raw_candidates:
            u = cand.get("urgency", 50)
            imp = cand.get("impact", 50)
            ev = cand.get("evidence_strength", 50)
            conf = cand.get("confidence", 70.0)
            feas = cand.get("feasibility", 60)

            p_score, p_level = self.prioritizer.calculate_score(
                urgency=u,
                impact=imp,
                evidence_strength=ev,
                confidence=conf,
                feasibility=feas,
            )

            state_record = persisted_states.get(cand["id"])
            if state_record:
                curr_status = RecommendationStatus(state_record.status)
                status_updated = (
                    state_record.status_updated_at.isoformat()
                    if state_record.status_updated_at
                    else None
                )
                rec_notes = state_record.notes
            else:
                curr_status = RecommendationStatus.NEW
                status_updated = now_iso
                rec_notes = None

            item = SmartRecommendationItem(
                id=cand["id"],
                title=cand["title"],
                category=cand["category"],
                priority=p_level,
                priority_score=p_score,
                description=cand["description"],
                business_context=cand["business_context"],
                evidence=cand.get("evidence", []),
                reasoning=cand["reasoning"],
                recommended_actions=cand.get("recommended_actions", []),
                action_plan=cand.get("action_plan"),
                expected_benefit=cand["expected_benefit"],
                estimated_impact=cand.get("estimated_impact"),
                impact_unit=cand.get("impact_unit"),
                confidence=float(conf),
                data_quality=cand.get("data_quality", "Moderate"),
                limitations=cand.get("limitations", []),
                source_modules=cand.get("source_modules", []),
                source_module_link=cand.get("source_module_link"),
                created_at=now_iso,
                status=curr_status,
                status_updated_at=status_updated,
                notes=rec_notes,
            )
            scored_items.append(item)

        scored_items.sort(key=lambda r: r.priority_score, reverse=True)

        # Apply Filters
        filtered_items = scored_items

        if category_filter and category_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.category.value.lower() == category_filter.lower()
            ]

        if priority_filter and priority_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.priority.value.lower() == priority_filter.lower()
            ]

        if status_filter and status_filter != "all":
            filtered_items = [
                i
                for i in filtered_items
                if i.status.value.lower() == status_filter.lower()
            ]
        elif not status_filter:
            filtered_items = [
                i for i in filtered_items if i.status != RecommendationStatus.DISMISSED
            ]

        crit_count = sum(
            1 for i in scored_items if i.priority == RecommendationPriority.CRITICAL
        )
        high_count = sum(
            1 for i in scored_items if i.priority == RecommendationPriority.HIGH
        )
        med_count = sum(
            1 for i in scored_items if i.priority == RecommendationPriority.MEDIUM
        )
        low_count = sum(
            1 for i in scored_items if i.priority == RecommendationPriority.LOW
        )

        status_counts: dict[str, int] = {}
        for i in scored_items:
            status_counts[i.status.value] = status_counts.get(i.status.value, 0) + 1

        category_counts: dict[str, int] = {}
        for i in scored_items:
            category_counts[i.category.value] = (
                category_counts.get(i.category.value, 0) + 1
            )

        return SmartRecommendationsResponse(
            generated_at=now_iso,
            business_id=business.id,
            business_name=business.legal_name,
            total_count=len(filtered_items),
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            status_counts=status_counts,
            category_counts=category_counts,
            recommendations=filtered_items,
        )

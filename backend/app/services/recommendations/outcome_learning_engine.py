"""Recommendation Effectiveness and Outcome Learning Engine (Phase 5).

Analyzes historical implementation outcomes and owner feedback to:
  1. Measure portfolio-wide and category-level recommendation effectiveness.
  2. Enforce statistical small-sample safeguards (N < 3 requires provisional disclaimer).
  3. Identify structural non-completion bottlenecks (Lack of time, capital, complexity).
  4. Provide deterministic learning adjustments to personalize future ranking.
  5. Strictly safeguard critical risk recommendations from suppression.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation_feedback import RecommendationFeedback
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_outcome import RecommendationOutcome
from app.models.recommendation_version_history import RecommendationVersionHistory
from app.schemas.recommendation_outcomes import (
    CategoryEffectivenessItem,
    RecommendationEffectivenessResponse,
)
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    SmartRecommendationItem,
)

logger = logging.getLogger("atlas.recommendations.outcome_learning")


class RecommendationOutcomeLearningEngine:
    """Analyzes closed-loop recommendation outcomes and computes deterministic learning adjustments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def compute_effectiveness_intelligence(
        self, business_id: int
    ) -> RecommendationEffectivenessResponse:
        """Compute portfolio-wide and per-category implementation effectiveness analytics."""
        # 1. Fetch all lifecycle states, feedback, and outcomes for this business
        lifecycle_stmt = select(RecommendationLifecycleState).where(
            RecommendationLifecycleState.business_id == business_id
        )
        lifecycles = list(self.db.scalars(lifecycle_stmt).all())

        outcome_stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.business_id == business_id
        )
        outcomes = list(self.db.scalars(outcome_stmt).all())

        feedback_stmt = select(RecommendationFeedback).where(
            RecommendationFeedback.business_id == business_id
        )
        feedbacks = list(self.db.scalars(feedback_stmt).all())

        # Map outcomes by recommendation_id
        outcome_by_rec = {o.recommendation_id: o for o in outcomes}

        # 2. Portfolio-wide counts
        total_recs = len(lifecycles)
        total_accepted = sum(1 for l in lifecycles if l.status in ("Accepted", "In Progress", "Completed"))
        total_completed = sum(1 for l in lifecycles if l.status == "Completed" or (outcome_by_rec.get(l.recommendation_id) and outcome_by_rec[l.recommendation_id].is_completed))
        total_dismissed = sum(1 for l in lifecycles if l.status == "Dismissed")
        total_abandoned = sum(1 for o in outcomes if o.is_abandoned)

        acceptance_rate = (total_accepted / total_recs * 100.0) if total_recs > 0 else 0.0
        completion_rate = (total_completed / total_accepted * 100.0) if total_accepted > 0 else 0.0

        # Non-completion reasons breakdown
        abandon_reasons: Counter[str] = Counter()
        for o in outcomes:
            if o.is_abandoned or (o.is_started and not o.is_completed):
                reason = o.non_completion_reason or "UNSPECIFIED"
                abandon_reasons[reason] += 1

        # 3. Category-level analysis
        # Group by category inferred from recommendation_id or historical audit records
        category_recs: dict[str, list[str]] = {cat.value: [] for cat in RecommendationCategory}
        
        # Pull category mappings from version history if available
        history_stmt = select(RecommendationVersionHistory).where(
            RecommendationVersionHistory.business_id == business_id
        )
        histories = list(self.db.scalars(history_stmt).all())
        rec_to_cat: dict[str, str] = {h.recommendation_id: h.category for h in histories}

        # Fallback category mapping by slug keyword
        for l in lifecycles:
            rec_id = l.recommendation_id
            cat_name = rec_to_cat.get(rec_id)
            if not cat_name:
                rec_id_l = rec_id.lower()
                if "customer" in rec_id_l or "retention" in rec_id_l or "churn" in rec_id_l:
                    cat_name = RecommendationCategory.CUSTOMER_RETENTION.value
                elif "digital" in rec_id_l or "catalog" in rec_id_l or "storefront" in rec_id_l or "presence" in rec_id_l:
                    cat_name = RecommendationCategory.DIGITAL_TRANSFORMATION.value
                elif "revenue" in rec_id_l or "sales" in rec_id_l or "pricing" in rec_id_l:
                    cat_name = RecommendationCategory.REVENUE_GROWTH.value
                elif "cost" in rec_id_l or "expense" in rec_id_l:
                    cat_name = RecommendationCategory.COST_OPTIMIZATION.value
                elif "scheme" in rec_id_l or "grant" in rec_id_l or "pmegp" in rec_id_l or "cgtmse" in rec_id_l:
                    cat_name = RecommendationCategory.GOVERNMENT_SCHEMES.value
                elif "forecast" in rec_id_l or "demand" in rec_id_l:
                    cat_name = RecommendationCategory.DEMAND_PLANNING.value
                elif "product" in rec_id_l or "sku" in rec_id_l:
                    cat_name = RecommendationCategory.PRODUCT_PERFORMANCE.value
                elif "risk" in rec_id_l or "concentration" in rec_id_l:
                    cat_name = RecommendationCategory.RISK_REDUCTION.value
                elif "operation" in rec_id_l or "workflow" in rec_id_l:
                    cat_name = RecommendationCategory.OPERATIONAL_EFFICIENCY.value
                else:
                    cat_name = RecommendationCategory.FINANCIAL_MANAGEMENT.value

            if cat_name in category_recs:
                category_recs[cat_name].append(rec_id)

        category_items: list[CategoryEffectivenessItem] = []
        top_cats: list[str] = []
        insufficient_cats: list[str] = []
        small_sample_safeguard_triggered = False

        for cat_name, rec_ids in category_recs.items():
            if not rec_ids:
                continue

            c_suggested = len(rec_ids)
            c_accepted = 0
            c_completed = 0
            c_abandoned = 0
            ratings: list[int] = []
            positive_outcomes = 0

            for r_id in rec_ids:
                l_state = next((l for l in lifecycles if l.recommendation_id == r_id), None)
                o_state = outcome_by_rec.get(r_id)

                if l_state and l_state.status in ("Accepted", "In Progress", "Completed"):
                    c_accepted += 1
                if (l_state and l_state.status == "Completed") or (o_state and o_state.is_completed):
                    c_completed += 1
                if o_state and o_state.is_abandoned:
                    c_abandoned += 1
                if o_state and o_state.owner_rating:
                    ratings.append(o_state.owner_rating)
                    if o_state.owner_rating >= 4:
                        positive_outcomes += 1
                elif o_state and o_state.is_completed:
                    positive_outcomes += 1

            c_accept_rate = (c_accepted / c_suggested * 100.0) if c_suggested > 0 else 0.0
            c_comp_rate = (c_completed / c_accepted * 100.0) if c_accepted > 0 else 0.0
            avg_rating = (sum(ratings) / len(ratings)) if ratings else None

            # Small-Sample Safeguard: Require at least N >= 3 completed instances
            if c_completed < 3:
                reliability = "Insufficient Sample Size"
                warning = (
                    f"Fewer than 3 completed actions recorded in this category ({c_completed} completed). "
                    f"Effectiveness score is provisional and requires further historical implementation data before statistical conclusions can be drawn."
                )
                insufficient_cats.append(cat_name)
                small_sample_safeguard_triggered = True
            elif c_completed < 6:
                reliability = "Moderate"
                warning = None
                if c_comp_rate >= 60.0 or (avg_rating and avg_rating >= 4.0):
                    top_cats.append(cat_name)
            else:
                reliability = "Reliable"
                warning = None
                if c_comp_rate >= 50.0 or (avg_rating and avg_rating >= 3.5):
                    top_cats.append(cat_name)

            category_items.append(
                CategoryEffectivenessItem(
                    category=cat_name,
                    total_suggested=c_suggested,
                    total_accepted=c_accepted,
                    total_completed=c_completed,
                    total_abandoned=c_abandoned,
                    acceptance_rate_pct=round(c_accept_rate, 1),
                    completion_rate_pct=round(c_comp_rate, 1),
                    average_rating=round(avg_rating, 2) if avg_rating is not None else None,
                    positive_outcomes_count=positive_outcomes,
                    statistical_reliability=reliability,
                    small_sample_warning=warning,
                )
            )

        methodology_notes = [
            "Effectiveness rates represent empirical action progression (New -> Accepted -> Completed).",
            "Small-Sample Safeguard: Categories with fewer than 3 completed instances are flagged as Insufficient Sample Size.",
            "Causation Boundary: Observed business changes are correlations across symmetric windows, not counterfactual proof of causal impact.",
            "Critical Risk Invariant: Critical risks (Urgency >= 80) are exempt from dismissal-based suppression.",
        ]

        return RecommendationEffectivenessResponse(
            business_id=business_id,
            total_recommendations=total_recs,
            total_accepted=total_accepted,
            total_completed=total_completed,
            total_dismissed=total_dismissed,
            total_abandoned=total_abandoned,
            overall_acceptance_rate_pct=round(acceptance_rate, 1),
            overall_completion_rate_pct=round(completion_rate, 1),
            abandonment_reasons_breakdown=dict(abandon_reasons),
            category_effectiveness=category_items,
            top_performing_categories=top_cats,
            insufficient_evidence_categories=insufficient_cats,
            small_sample_safeguard_applied=small_sample_safeguard_triggered,
            methodology_notes=methodology_notes,
        )

    def get_closed_loop_learning_adjustments(
        self, business_id: int
    ) -> dict[str, Any]:
        """Compute deterministic personalization adjustments derived from verified outcomes and feedback."""
        # 1. Fetch outcomes and feedback
        outcome_stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.business_id == business_id
        )
        outcomes = list(self.db.scalars(outcome_stmt).all())

        feedback_stmt = select(RecommendationFeedback).where(
            RecommendationFeedback.business_id == business_id
        )
        feedbacks = list(self.db.scalars(feedback_stmt).all())

        # 2. Count dismissals by recommendation_id
        dismissal_counts: Counter[str] = Counter()
        for f in feedbacks:
            ft = f.feedback_type.lower()
            if "not relevant" in ft or "too expensive" in ft or "not feasible" in ft or f.suppress_recommendation:
                dismissal_counts[f.recommendation_id] += 1

        # 3. Repeated Dismissal Suppression: Dismissed >= 2 times
        # Note: Critical risks are filtered out during application
        repeatedly_dismissed_ids = {
            rec_id for rec_id, count in dismissal_counts.items() if count >= 2
        }

        # 4. Effort and Constraint Patterns from Non-Completion
        time_bottleneck_count = sum(
            1 for o in outcomes if o.non_completion_reason in ("LACK_OF_TIME", "Time constraints", "Time Constraints")
        )
        capital_bottleneck_count = sum(
            1 for o in outcomes if o.non_completion_reason in ("LACK_OF_CAPITAL", "Limited budget", "Lack of capital")
        )
        complexity_bottleneck_count = sum(
            1 for o in outcomes if o.non_completion_reason in ("TOO_COMPLEX", "Technical difficulty", "Too complex")
        )

        # Successful categories with positive ratings or completed status
        completed_recs = [o for o in outcomes if o.is_completed]
        preferred_effort_bias = "Low" if time_bottleneck_count >= 2 else None

        return {
            "repeatedly_dismissed_ids": repeatedly_dismissed_ids,
            "time_bottleneck_active": time_bottleneck_count >= 2,
            "capital_bottleneck_active": capital_bottleneck_count >= 2,
            "complexity_bottleneck_active": complexity_bottleneck_count >= 2,
            "completed_count": len(completed_recs),
            "preferred_effort_bias": preferred_effort_bias,
        }

    def apply_learning_to_recommendations(
        self,
        recommendations: list[SmartRecommendationItem],
        business_id: int,
    ) -> list[SmartRecommendationItem]:
        """Apply deterministic feedback-driven adjustments while strictly protecting critical risks."""
        adjustments = self.get_closed_loop_learning_adjustments(business_id)
        repeatedly_dismissed = adjustments["repeatedly_dismissed_ids"]
        time_bottleneck = adjustments["time_bottleneck_active"]
        capital_bottleneck = adjustments["capital_bottleneck_active"]

        filtered_and_adjusted: list[SmartRecommendationItem] = []

        for rec in recommendations:
            is_critical_risk = (
                rec.priority == RecommendationPriority.CRITICAL
                or rec.priority_score >= 80
                or "concentration" in rec.id.lower()
                or "solvency" in rec.id.lower()
            )

            # Rule 1: Repeated Dismissal Suppression with Strict Critical Risk Protection
            if rec.id in repeatedly_dismissed:
                if is_critical_risk:
                    # STRICT CRITICAL RISK PROTECTION: Never suppress critical risks!
                    logger.info(
                        f"Preserving critical risk recommendation '{rec.id}' despite repeated dismissals."
                    )
                    rec.limitations.append(
                        "Critical Risk Notice: Maintained in recommendations despite previous dismissal due to acute operational/financial exposure."
                    )
                else:
                    # Suppress non-critical repeatedly dismissed recommendation
                    logger.info(
                        f"Suppressing non-critical recommendation '{rec.id}' due to repeated owner dismissals (>=2)."
                    )
                    continue

            # Rule 2: Time Bottleneck Feasibility Adaptation
            if time_bottleneck:
                desc_lower = (rec.description + " " + rec.title).lower()
                if rec.implementation_difficulty == "Strategic" or "30-90 days" in desc_lower or "complex" in desc_lower:
                    # Penalize feasibility for complex actions when time is a known bottleneck
                    if rec.constraint_adjusted_feasibility is not None:
                        rec.constraint_adjusted_feasibility = max(10.0, rec.constraint_adjusted_feasibility - 15.0)
                    rec.limitations.append(
                        "Adapted for past time constraints: implementation difficulty factored into lower feasibility."
                    )
                elif rec.implementation_difficulty == "Quick Win" or "quick win" in desc_lower:
                    # Boost quick wins
                    rec.priority_score = min(100, rec.priority_score + 5)

            # Rule 3: Capital Bottleneck Adaptation
            if capital_bottleneck:
                desc_lower = (rec.description + " " + rec.title).lower()
                if "capex" in desc_lower or "purchase" in desc_lower or "invest" in desc_lower:
                    if not any(w in desc_lower for w in ["grant", "subsidy", "zero", "free"]):
                        if rec.constraint_adjusted_feasibility is not None:
                            rec.constraint_adjusted_feasibility = max(10.0, rec.constraint_adjusted_feasibility - 20.0)
                        rec.limitations.append(
                            "Adapted for past capital constraints: capital expenditure requirement factored into feasibility penalty."
                        )

            filtered_and_adjusted.append(rec)

        # Re-sort recommendations by priority_score descending
        filtered_and_adjusted.sort(key=lambda r: r.priority_score, reverse=True)
        return filtered_and_adjusted

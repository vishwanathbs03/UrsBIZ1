"""Next Best Business Action Engine (Phase 5).

Ranks, tiers, and enriches recommendations with:
  1. Top Priority Action (#1 highest-leverage immediate action)
  2. Cost of Delay (Consequences of postponement)
  3. Effort Level (Low, Medium, High)
  4. Time-to-Value (Time until initial business impact)
  5. Next 3 Sequential Actions
  6. Long-Term Strategic Initiatives
"""

from __future__ import annotations

import logging
from typing import Optional

from app.schemas.advanced_recommendations import (
    NextBestAction,
    NextBestActionResponse,
)
from app.schemas.smart_recommendations import SmartRecommendationItem

logger = logging.getLogger(__name__)


class NextBestActionEngine:
    """Selects and structures the Top Priority Action and Next-in-Line initiatives."""

    def rank_actions(
        self,
        recommendations: list[SmartRecommendationItem],
        suppressed_ids: Optional[set[str]] = None,
    ) -> NextBestActionResponse:
        """Rank and tier active recommendations into Top Action, Next 3, and Long-Term."""
        suppressed = suppressed_ids or set()
        active = [r for r in recommendations if r.id not in suppressed]

        if not active:
            return NextBestActionResponse()

        # Sort by deterministic priority score descending
        sorted_recs = sorted(active, key=lambda r: r.priority_score, reverse=True)

        # Build enriched NextBestAction items
        enriched_actions = [self._enrich_action(r, index=i) for i, r in enumerate(sorted_recs)]

        top_action = enriched_actions[0] if enriched_actions else None
        next_three = enriched_actions[1:4] if len(enriched_actions) > 1 else []
        long_term = enriched_actions[4:8] if len(enriched_actions) > 4 else []

        return NextBestActionResponse(
            top_priority_action=top_action,
            next_three_actions=next_three,
            long_term_initiatives=long_term,
        )

    def _enrich_action(self, rec: SmartRecommendationItem, index: int) -> NextBestAction:
        effort = self._infer_effort(rec)
        time_to_val = self._infer_time_to_value(rec)
        cost_of_delay = self._synthesize_cost_of_delay(rec)
        first_step = (
            rec.recommended_actions[0]
            if rec.recommended_actions
            else "Review detailed action plan and assign responsible team member."
        )

        why_now = (
            f"Ranked #{index + 1} with priority score of {rec.priority_score}/100. "
            f"Directly impacts {rec.category.value} with {rec.data_quality.lower()} data confidence."
        )

        return NextBestAction(
            recommendation_id=rec.id,
            title=rec.title,
            category=rec.category.value,
            priority_score=rec.priority_score,
            priority=rec.priority.value,
            why_now=why_now,
            cost_of_delay=cost_of_delay,
            effort_level=effort,
            time_to_value=time_to_val,
            first_immediate_step=first_step,
            source_modules=rec.source_modules,
        )

    def _infer_effort(self, rec: SmartRecommendationItem) -> str:
        cat = rec.category.value.lower()
        if "government" in cat or "digital" in cat or "risk" in cat:
            return "Medium"
        if "customer" in cat or "product" in cat:
            return "Low"
        if "financial" in cat or "operational" in cat:
            return "Medium"
        return "Medium"

    def _infer_time_to_value(self, rec: SmartRecommendationItem) -> str:
        if rec.action_plan and rec.action_plan.suggested_timeframe:
            return rec.action_plan.suggested_timeframe
        cat = rec.category.value.lower()
        if "customer" in cat:
            return "7-14 days"
        if "product" in cat:
            return "14-21 days"
        if "government" in cat:
            return "30-60 days"
        return "15-30 days"

    def _synthesize_cost_of_delay(self, rec: SmartRecommendationItem) -> str:
        cat = rec.category.value.lower()
        if "customer retention" in cat or "concentration" in rec.title.lower():
            return (
                "Delaying action increases the probability of permanent client churn. "
                "Lapsed commercial relationships become exponentially more difficult and expensive to re-establish after 30 days."
            )
        if "demand" in cat or "product" in cat:
            return (
                "Postponing operational alignment risks unfulfilled orders during peak demand spikes, "
                "surrendering market share to competitors and resulting in emergency procurement price premiums."
            )
        if "government" in cat:
            return (
                "Statutory scheme windows and annual fiscal budget allocations operate on strict cutoffs. "
                "Delays forfeit non-dilutive capital and interest subvention opportunities for the current fiscal cycle."
            )
        if "cost" in cat or "financial" in cat:
            return (
                "Unaddressed overhead and margin leakages compound month-over-month, "
                "unnecessarily draining cash reserves and reducing operational flexibility."
            )
        return (
            "Every month of delayed execution defers compound operational improvements "
            "and prolongs exposure to unhedged business volatility."
        )

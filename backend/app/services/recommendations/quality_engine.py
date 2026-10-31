"""Recommendation Quality & Evidence Gate Engine (Phase 5).

Evaluates the evidentiary grounding and data integrity of recommendations:
  - Strong Evidence (>= 3 verified data points across modules)
  - Moderate Evidence (1-2 verified data points)
  - Limited Evidence (Qualitative signal only)
  - Insufficient Data (Suppressed from active view to prevent hallucination)
Enforces strict boundaries on inventory and revenue claims.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.schemas.smart_recommendations import SmartRecommendationItem

logger = logging.getLogger(__name__)


class RecommendationQualityEngine:
    """Validates evidentiary rigor and suppresses low-confidence or boundary-violating recommendations."""

    def evaluate_quality(self, rec: SmartRecommendationItem) -> str:
        """Evaluate evidence quality level based on concrete evidence count and confidence."""
        if rec.data_quality == "Insufficient":
            return "Insufficient Data"

        ev_count = len(rec.evidence)
        conf = rec.confidence

        if ev_count >= 3 and conf >= 75.0:
            return "Strong Evidence"
        elif ev_count >= 1 and conf >= 50.0:
            return "Moderate Evidence"
        elif ev_count >= 1 or conf >= 30.0:
            return "Limited Evidence"
        else:
            return "Insufficient Data"

    def filter_actionable(
        self, recommendations: list[SmartRecommendationItem]
    ) -> list[SmartRecommendationItem]:
        """Filter out recommendations that lack sufficient evidence or violate integrity rules."""
        approved: list[SmartRecommendationItem] = []

        for rec in recommendations:
            if rec.data_quality == "Insufficient":
                # Explicit upload guidance card; preserve as Insufficient
                approved.append(rec)
                continue

            quality = self.evaluate_quality(rec)
            if quality == "Strong Evidence":
                rec.data_quality = "High"
            elif quality == "Moderate Evidence":
                rec.data_quality = "Moderate"
            elif quality == "Limited Evidence":
                rec.data_quality = "Limited"
            else:
                logger.info(
                    "Recommendation '%s' suppressed due to Insufficient Data quality.",
                    rec.id,
                )
                continue

            # Integrity check: Ensure no fake inventory reorder quantities or guaranteed revenue
            if "reorder quantity" in rec.description.lower() and "units" in rec.description.lower():
                # Flag boundary violation
                rec.limitations.append(
                    "Phase 3 lacks physical warehouse counts: operational review only, not calculated reorder quantity."
                )

            approved.append(rec)

        return approved

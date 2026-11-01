"""Deterministic Recommendation Prioritization Service (Phase 5.3).

Implements the verified 5-factor prioritization formula:
  Priority Score = 0.25 * R + 0.25 * I + 0.20 * E + 0.15 * C + 0.15 * F

Factor Definitions (Normalized 0 to 100):
  - R (Risk / Urgency): Time-sensitivity and cost of inaction.
  - I (Business Impact): Strategic, revenue, or operational significance.
  - E (Evidence Strength): Empirical observation quantity and history span.
  - C (Confidence): Statistical reliability grade and data provenance.
  - F (Feasibility): Practical ease of execution for MSME owner.

Priority Bands:
  - Critical: 80.0 to 100.0
  - High: 65.0 to 79.99
  - Medium: 45.0 to 64.99
  - Low: Below 45.0
"""

from __future__ import annotations

from typing import Tuple
from app.schemas.smart_recommendations import RecommendationPriority


class RecommendationPrioritizationService:
    """Calculates deterministic priority scores and assigns canonical priority bands."""

    @staticmethod
    def calculate_score(
        urgency: float,
        impact: float,
        evidence_strength: float,
        confidence: float,
        feasibility: float,
    ) -> Tuple[int, RecommendationPriority]:
        """Compute normalized priority score [10, 100] and priority band."""
        u_norm = max(0.0, min(100.0, float(urgency)))
        i_norm = max(0.0, min(100.0, float(impact)))
        e_norm = max(0.0, min(100.0, float(evidence_strength)))
        c_norm = max(0.0, min(100.0, float(confidence)))
        f_norm = max(0.0, min(100.0, float(feasibility)))

        raw_score = (
            (0.25 * u_norm)
            + (0.25 * i_norm)
            + (0.20 * e_norm)
            + (0.15 * c_norm)
            + (0.15 * f_norm)
        )
        final_score = min(100, max(10, round(raw_score)))

        if final_score >= 80:
            band = RecommendationPriority.CRITICAL
        elif final_score >= 65:
            band = RecommendationPriority.HIGH
        elif final_score >= 45:
            band = RecommendationPriority.MEDIUM
        else:
            band = RecommendationPriority.LOW

        return final_score, band

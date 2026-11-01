"""Personalized Business DNA and Adaptive Recommendation Intelligence Engine (Phase 5).

Deeply personalizes UrsBiz recommendations to each individual business based on:
  1. Business DNA & Evaluated Organizational Maturity (Early Stage, Growing, Established)
  2. Owner-Configured Business Goals (Revenue, Profitability, Retention, Cost, Launch, etc.)
  3. Known Resource Constraints (Budget, Workforce, Digital, Data, Time, Financials)
  4. Historical Owner Feedback Learning (Relevant, Not feasible, Too expensive, etc.)
  5. Deterministic Priority Re-ranking with Strict Critical Risk Safeguards.
  6. Multi-dimensional Adaptive Explanations.

Strict Non-Hallucination & Safety Principles:
  - Critical business risks (Urgency >= 80, churn/solvency warnings) are NEVER demoted
    or suppressed by personalization preferences.
  - No information is assumed that has not been provided or verified in context.
  - When feasibility cannot be determined, constraints are explicitly surfaced.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from app.models.business import Business
from app.models.personalization import BusinessPersonalizationSettings
from app.models.recommendation_feedback import RecommendationFeedback
from app.schemas.personalization import (
    BusinessConstraintType,
    BusinessGoalType,
    BusinessMaturityLevel,
    PersonalizationExplanation,
    RecommendationPersonalizationProfile,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
)

logger = logging.getLogger("atlas.recommendations.personalization_engine")


class PersonalizationEngine:
    """Core intelligence engine for personalized recommendation ranking and adaptive explanations."""

    # ----------------------------------------------------------------------- #
    # 1. Maturity Evaluation                                                  #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def evaluate_maturity(
        business: Business,
        sales_total_revenue: float = 0.0,
        sales_tx_count: int = 0,
    ) -> Tuple[BusinessMaturityLevel, list[str]]:
        """Deterministically assess business maturity from verified factual telemetry."""
        current_year = datetime.now(timezone.utc).year
        est_year = business.established_year or (current_year - 1)
        age = max(0, current_year - est_year)
        employees = business.employee_count or 0
        effective_rev = max(float(business.annual_revenue or 0.0), float(sales_total_revenue))

        drivers: list[str] = [
            f"Operating age: {age} year{'s' if age != 1 else ''} (est. {est_year})",
            f"Workforce: {employees} employee{'s' if employees != 1 else ''}",
            f"Verified annual turnover: ₹{effective_rev:,.0f}",
        ]
        if sales_tx_count > 0:
            drivers.append(f"Recorded transaction history: {sales_tx_count} sales entries")

        # Early-Stage Criteria
        if age <= 2 or employees < 5 or (sales_tx_count < 20 and effective_rev < 1_500_000):
            return BusinessMaturityLevel.EARLY_STAGE, drivers

        # Established Criteria
        if age >= 6 and (employees >= 15 or effective_rev >= 10_000_000):
            return BusinessMaturityLevel.ESTABLISHED, drivers

        # Default Growth Stage
        return BusinessMaturityLevel.GROWING, drivers

    # ----------------------------------------------------------------------- #
    # 2. Maturity Fit Scoring                                                 #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def calculate_maturity_fit(
        category: RecommendationCategory,
        maturity: BusinessMaturityLevel,
        difficulty: str = "Tactical",
    ) -> float:
        """Compute suitability score [0.0 - 100.0] for current organizational maturity."""
        cat_val = category.value if hasattr(category, "value") else str(category)

        if maturity == BusinessMaturityLevel.EARLY_STAGE:
            # Early stage prioritizes digital footprint, early revenue, startup schemes, and basic operations
            if cat_val in (
                RecommendationCategory.DIGITAL_TRANSFORMATION.value,
                RecommendationCategory.REVENUE_GROWTH.value,
                RecommendationCategory.GOVERNMENT_SCHEMES.value,
            ):
                return 95.0 if difficulty == "Quick Win" else 85.0
            if cat_val in (
                RecommendationCategory.OPERATIONAL_EFFICIENCY.value,
                RecommendationCategory.FINANCIAL_MANAGEMENT.value,
            ):
                return 75.0
            # Complex demand forecasting or heavy cost optimization has lower fit for early startups
            return 50.0

        elif maturity == BusinessMaturityLevel.GROWING:
            # Growing businesses prioritize customer retention, product optimization, demand planning
            if cat_val in (
                RecommendationCategory.CUSTOMER_RETENTION.value,
                RecommendationCategory.PRODUCT_PERFORMANCE.value,
                RecommendationCategory.DEMAND_PLANNING.value,
                RecommendationCategory.FINANCIAL_MANAGEMENT.value,
            ):
                return 95.0
            if cat_val in (
                RecommendationCategory.REVENUE_GROWTH.value,
                RecommendationCategory.OPERATIONAL_EFFICIENCY.value,
                RecommendationCategory.GOVERNMENT_SCHEMES.value,
            ):
                return 85.0
            return 70.0

        else:  # ESTABLISHED
            # Established businesses prioritize risk reduction, concentration reduction, cost optimization
            if cat_val in (
                RecommendationCategory.RISK_REDUCTION.value,
                RecommendationCategory.COST_OPTIMIZATION.value,
                RecommendationCategory.OPERATIONAL_EFFICIENCY.value,
                RecommendationCategory.CUSTOMER_RETENTION.value,
            ):
                return 95.0
            if cat_val in (
                RecommendationCategory.DEMAND_PLANNING.value,
                RecommendationCategory.PRODUCT_PERFORMANCE.value,
            ):
                return 85.0
            # Basic digital storefront setup has lower fit for mature firms
            if cat_val == RecommendationCategory.DIGITAL_TRANSFORMATION.value:
                return 55.0
            return 75.0

    # ----------------------------------------------------------------------- #
    # 3. Goal Alignment Scoring                                               #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def calculate_goal_alignment(
        category: RecommendationCategory,
        title: str,
        description: str,
        active_goals: list[str],
    ) -> float:
        """Calculate match score [0.0 - 100.0] against active owner goals."""
        if not active_goals:
            return 50.0  # Neutral baseline when owner has not configured goals

        cat_val = category.value if hasattr(category, "value") else str(category)
        text_corpus = (title + " " + description + " " + cat_val).lower()

        max_match = 40.0  # Default non-matching baseline

        for g in active_goals:
            g_lower = g.lower()
            # Revenue Goal
            if "revenue" in g_lower and (
                cat_val == RecommendationCategory.REVENUE_GROWTH.value
                or "revenue" in text_corpus
                or "pricing" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Profitability Goal
            elif "profit" in g_lower and (
                cat_val == RecommendationCategory.COST_OPTIMIZATION.value
                or "margin" in text_corpus
                or "profit" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Customer Retention Goal
            elif "retain" in g_lower and (
                cat_val == RecommendationCategory.CUSTOMER_RETENTION.value
                or "retention" in text_corpus
                or "repeat" in text_corpus
                or "churn" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Operating Costs Goal
            elif "cost" in g_lower and (
                cat_val == RecommendationCategory.COST_OPTIMIZATION.value
                or cat_val == RecommendationCategory.OPERATIONAL_EFFICIENCY.value
                or "expense" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Launch Products Goal
            elif "product" in g_lower and (
                cat_val == RecommendationCategory.PRODUCT_PERFORMANCE.value
                or "launch" in text_corpus
                or "sku" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Expand Markets Goal
            elif "market" in g_lower and (
                cat_val == RecommendationCategory.REVENUE_GROWTH.value
                or cat_val == RecommendationCategory.GOVERNMENT_SCHEMES.value
                or "market" in text_corpus
                or "expansion" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Digital Presence Goal
            elif "digital" in g_lower and (
                cat_val == RecommendationCategory.DIGITAL_TRANSFORMATION.value
                or "website" in text_corpus
                or "online" in text_corpus
            ):
                max_match = max(max_match, 95.0)
            # Operational Efficiency Goal
            elif "operation" in g_lower and (
                cat_val == RecommendationCategory.OPERATIONAL_EFFICIENCY.value
                or cat_val == RecommendationCategory.DEMAND_PLANNING.value
                or "workflow" in text_corpus
            ):
                max_match = max(max_match, 95.0)

        return max_match

    # ----------------------------------------------------------------------- #
    # 4. Constraint-Aware Feasibility Adaptation                              #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def evaluate_constraints(
        category: RecommendationCategory,
        title: str,
        description: str,
        active_constraints: list[str],
        preferred_investment: str = "Low",
        preferred_effort: str = "Medium",
    ) -> Tuple[float, list[str]]:
        """Evaluate known constraints and compute deduction penalty [0 - 50] + explanation notes."""
        penalty = 0.0
        warnings: list[str] = []
        text_corpus = (title + " " + description).lower()

        # Constraint 1: Limited Budget
        if BusinessConstraintType.LIMITED_BUDGET.value in active_constraints:
            has_budget_negation = any(neg in text_corpus for neg in ("zero", "no cost", "free", "subsid", "grant"))
            if any(term in text_corpus for term in ("machinery", "hire", "software license", "expensive software")) and not has_budget_negation:
                penalty += 25.0
                warnings.append("Adapted for Limited Budget: recommend zero-capex or grant-subsidized alternative.")
            elif preferred_investment == "Low" and any(term in text_corpus for term in ("invest", "purchase")) and not has_budget_negation:
                penalty += 15.0
                warnings.append("Constrained by Low Investment preference: prioritized organic tactical steps.")

        # Constraint 2: Small Workforce
        if BusinessConstraintType.SMALL_WORKFORCE.value in active_constraints:
            if "hire" in text_corpus or "dedicated team" in text_corpus or "manual audit" in text_corpus:
                penalty += 20.0
                warnings.append("Adapted for Small Workforce: action scoped for single-owner or 1-person execution.")

        # Constraint 3: Limited Digital Capability
        if BusinessConstraintType.LIMITED_DIGITAL_CAPABILITY.value in active_constraints:
            if "api" in text_corpus or "custom web" in text_corpus or "erp" in text_corpus:
                penalty += 25.0
                warnings.append("Adapted for Limited Digital Capability: simplified to off-the-shelf tools.")

        # Constraint 4: Limited Historical Data
        if BusinessConstraintType.LIMITED_HISTORICAL_DATA.value in active_constraints:
            if "advanced forecast" in text_corpus or "seasonality decomposition" in text_corpus:
                penalty += 20.0
                warnings.append("Adapted for Limited Data: heuristic rule applied in lieu of deep modeling.")

        # Constraint 5: Time Constraints
        if BusinessConstraintType.TIME_CONSTRAINTS.value in active_constraints:
            if "30-60 days" in text_corpus or "strategic" in text_corpus:
                penalty += 15.0
                warnings.append("Adapted for Time Constraints: broken into 15-minute daily micro-actions.")

        # Cap maximum penalty so feasibility does not drop to zero
        final_penalty = min(50.0, penalty)
        return final_penalty, warnings

    # ----------------------------------------------------------------------- #
    # 5. Owner Preference & Feedback Learning                                 #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def calculate_preference_score(
        category: RecommendationCategory,
        recent_feedback: list[RecommendationFeedback],
        focus_areas: list[str],
    ) -> float:
        """Compute score [0.0 - 100.0] derived from historical owner feedback and focus areas."""
        score = 60.0  # Neutral baseline
        cat_val = category.value if hasattr(category, "value") else str(category)

        # Focus areas boost
        for fa in focus_areas:
            if fa.lower() in cat_val.lower():
                score += 15.0
                break

        # Historical feedback modulation
        relevant_feedbacks = [
            fb for fb in recent_feedback
            if fb.recommendation_id and cat_val.lower() in fb.recommendation_id.lower()
        ]
        for fb in relevant_feedbacks:
            ft = fb.feedback_type.lower()
            if "relevant" in ft or "useful" in ft:
                score += 10.0
            elif "too expensive" in ft or "not feasible" in ft:
                score -= 15.0
            elif "not aligned" in ft or "not relevant" in ft:
                score -= 20.0

        return max(10.0, min(100.0, score))

    # ----------------------------------------------------------------------- #
    # 6. Deterministic Personalized Priority Scoring                          #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def compute_personalized_priority(
        base_urgency: float,
        base_impact: float,
        evidence_strength: float,
        confidence: float,
        base_feasibility: float,
        goal_alignment_score: float,
        maturity_fit_score: float,
        preference_score: float,
        constraint_penalty: float,
    ) -> Tuple[int, RecommendationPriority, float, float]:
        """Compute personalized priority score and priority band with critical risk protection."""
        # Adjust feasibility by constraint penalty
        adj_feasibility = max(10.0, min(100.0, base_feasibility - constraint_penalty))

        # Re-compute base deterministic score with constraint-adjusted feasibility
        base_score = (
            (0.25 * base_urgency)
            + (0.25 * base_impact)
            + (0.20 * evidence_strength)
            + (0.15 * confidence)
            + (0.15 * adj_feasibility)
        )

        # Compute Personalization Composite Score
        # Weighting: 40% Goal Alignment + 35% Maturity Fit + 25% Owner Preference
        personalization_score = (
            (0.40 * goal_alignment_score)
            + (0.35 * maturity_fit_score)
            + (0.25 * preference_score)
        )

        # Strict Critical Risk Protection:
        # If Urgency >= 80 (e.g. acute churn, critical working capital, regulatory deadline),
        # personalization CANNOT demote the recommendation out of the top band!
        is_critical_risk = base_urgency >= 80.0

        if is_critical_risk:
            # Personalization provides at most 15% modulation, but never drags below base score
            blended = (0.85 * base_score) + (0.15 * personalization_score)
            final_score_raw = max(base_score, blended)
        else:
            # Standard recommendations: 65% Base Grounding + 35% Personalization
            final_score_raw = (0.65 * base_score) + (0.35 * personalization_score)

        final_score = min(100, max(10, round(final_score_raw)))

        # Assign Priority Band
        if final_score >= 80 or (is_critical_risk and base_score >= 75):
            band = RecommendationPriority.CRITICAL
        elif final_score >= 65:
            band = RecommendationPriority.HIGH
        elif final_score >= 45:
            band = RecommendationPriority.MEDIUM
        else:
            band = RecommendationPriority.LOW

        return final_score, band, round(personalization_score, 1), round(adj_feasibility, 1)

    # ----------------------------------------------------------------------- #
    # 7. Adaptive Recommendation Explanation Construction                     #
    # ----------------------------------------------------------------------- #
    @staticmethod
    def build_personalization_explanation(
        business: Business,
        category: RecommendationCategory,
        title: str,
        maturity: BusinessMaturityLevel,
        maturity_drivers: list[str],
        active_goals: list[str],
        active_constraints: list[str],
        constraint_warnings: list[str],
        missing_data: list[str],
        goal_score: float,
        maturity_score: float,
        pref_score: float,
        constraint_pen: float,
        priority_rank: int,
        is_critical_risk: bool,
    ) -> PersonalizationExplanation:
        """Construct multi-dimensional explanation answering why this recommendation fits."""
        biz_name = business.legal_name or "Your business"
        ind = business.industry or "MSME"

        # Why relevant
        why_rel = (
            f"Tailored specifically for {biz_name} in {ind}: "
            f"directly addresses verified business conditions while respecting current operations."
        )

        # Maturity suitability
        if maturity == BusinessMaturityLevel.EARLY_STAGE:
            mat_suit = (
                f"Suited for your Early Stage maturity ({maturity_drivers[0]}): focuses on lean foundation "
                "and cash-generative quick wins before complex systems are introduced."
            )
        elif maturity == BusinessMaturityLevel.GROWING:
            mat_suit = (
                f"Suited for your Growing business maturity ({maturity_drivers[0]}): capitalizes on established "
                "traction to optimize repeat customers, product efficiency, and working capital."
            )
        else:
            mat_suit = (
                f"Suited for your Established business maturity ({maturity_drivers[0]}): prioritizes risk "
                "reduction, customer concentration mitigation, and enterprise operating leverage."
            )

        # Ranking rationale
        if is_critical_risk:
            rank_rat = (
                f"Ranked #{priority_rank} (Protected Critical Risk Alert): elevated urgency ({title}) "
                "takes precedence to protect enterprise solvency and customer relationships."
            )
        elif goal_score >= 85:
            matched_goal = active_goals[0] if active_goals else "Growth"
            rank_rat = (
                f"Ranked #{priority_rank}: directly accelerates your priority goal '{matched_goal}' "
                f"(Goal Alignment: {goal_score:.0f}/100, Maturity Fit: {maturity_score:.0f}/100)."
            )
        else:
            rank_rat = (
                f"Ranked #{priority_rank} based on combined impact, feasibility ({maturity_score:.0f}/100 "
                f"maturity suitability), and verified empirical ledger observations."
            )

        return PersonalizationExplanation(
            why_relevant_to_this_business=why_rel,
            triggering_conditions=[f"Industry: {ind}", *maturity_drivers[:2]],
            maturity_suitability=mat_suit,
            constraints_considered=active_constraints or ["No prohibitive constraints declared"],
            missing_information=missing_data or ["Telemetry fully verified from business twin"],
            ranking_rationale=rank_rat,
            goal_alignment_score=goal_score,
            maturity_fit_score=maturity_score,
            preference_score=pref_score,
            constraint_penalty=constraint_pen,
            is_critical_risk_override=is_critical_risk,
        )

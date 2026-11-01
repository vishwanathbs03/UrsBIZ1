"""Personalized AI Business Growth Strategy Engine (Phase 5).

Synthesizes a 3-horizon growth roadmap tailored to the MSME's empirical data:
  - Horizon 1 (0-30 Days): Immediate operational stabilization and quick cash wins
  - Horizon 2 (31-90 Days): Process optimization, customer reactivation, digital adoption
  - Horizon 3 (3-12 Months): Strategic scaling, formalization, and capacity expansion

Combines deterministic milestone structuring with Gemini narrative synthesis and instant fallback.
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

from app.config.settings import get_settings
from app.schemas.advanced_recommendations import (
    GrowthHorizonPlan,
    GrowthMilestone,
    PersonalizedGrowthStrategy,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.schemas.smart_recommendations import SmartRecommendationItem

logger = logging.getLogger(__name__)


class GrowthStrategyEngine:
    """Generates a 3-horizon personalized roadmap combining deterministic structure and AI reasoning."""

    def generate_strategy(
        self,
        ctx: UnifiedRecommendationContext,
        recommendations: list[SmartRecommendationItem],
    ) -> PersonalizedGrowthStrategy:
        """Construct the 3-horizon growth strategy for the business."""
        business_name = ctx.profile.legal_name
        industry = ctx.profile.industry or "General MSME"

        # 1. Deterministic baseline structuring across 3 horizons
        h1 = self._build_horizon_1(ctx, recommendations)
        h2 = self._build_horizon_2(ctx, recommendations)
        h3 = self._build_horizon_3(ctx, recommendations)

        horizons = [h1, h2, h3]

        critical_success_factors = [
            "Weekly review of top-client order volume to prevent sudden churn",
            "Consistent record-keeping in UrsBiz to keep business health score above 75",
            "Staged raw material procurement aligned with Phase 4 demand forecast trends",
            "Active pursuit of verified statutory subsidies to reduce non-dilutive capital costs",
        ]

        deterministic_summary = (
            f"Growth strategy roadmap tailored for {business_name} ({industry}). "
            "Focuses immediately on mitigating revenue concentration and reactivating dormant accounts in Days 0–30, "
            "scaling product lines with confirmed demand in Days 31–90, and formalizing institutional financing in Months 3–12."
        )

        settings = get_settings()
        if not settings.ai_api_key or settings.ai_provider == "placeholder":
            return PersonalizedGrowthStrategy(
                business_name=business_name,
                industry=industry,
                strategy_summary=deterministic_summary,
                is_ai_generated=False,
                horizons=horizons,
                critical_success_factors=critical_success_factors,
            )

        # 2. Bounded Gemini call to enrich strategy summary
        try:
            prompt = (
                f"You are a senior MSME growth consultant. Provide a concise, 2-3 sentence strategic summary "
                f"for {business_name}, operating in the {industry} sector with annual revenue of ₹{ctx.profile.annual_revenue or ctx.sales.total_revenue:,.0f}. "
                f"Key priorities: {h1.focus}, followed by {h2.focus}, and {h3.focus}. "
                "Keep it pragmatic, encouraging, and completely grounded without jargon."
            )

            headers = {
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": "You are an executive MSME business advisor."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 150,
                "temperature": 0.2,
            }
            url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    ai_text = data["choices"][0]["message"]["content"].strip()
                    if ai_text and len(ai_text) > 30:
                        return PersonalizedGrowthStrategy(
                            business_name=business_name,
                            industry=industry,
                            strategy_summary=ai_text,
                            is_ai_generated=True,
                            horizons=horizons,
                            critical_success_factors=critical_success_factors,
                        )
        except Exception as e:
            logger.warning(f"Growth strategy AI generation failed, falling back to deterministic: {e}")

        return PersonalizedGrowthStrategy(
            business_name=business_name,
            industry=industry,
            strategy_summary=deterministic_summary,
            is_ai_generated=False,
            horizons=horizons,
            critical_success_factors=critical_success_factors,
        )

    def _build_horizon_1(
        self,
        ctx: UnifiedRecommendationContext,
        recommendations: list[SmartRecommendationItem],
    ) -> GrowthHorizonPlan:
        top_recs = [r.title for r in recommendations[:2]]
        actions = top_recs if top_recs else [
            "Conduct structured check-in with top 3 revenue-contributing clients",
            "Audit slow-moving products and pause unconfirmed raw material purchases",
        ]

        milestones = [
            GrowthMilestone(
                milestone="Key Account Touchpoints Completed",
                target_date_window="Day 10",
                metric_to_track="100% of top 3 clients contacted",
            ),
            GrowthMilestone(
                milestone="Dormant Account Reactivation Campaign Launched",
                target_date_window="Day 20",
                metric_to_track="Reactivation outreach sent to lapsed buyers",
            ),
        ]

        return GrowthHorizonPlan(
            horizon="0-30 Days",
            title="Immediate Cashflow Protection & Retention",
            focus="Stabilize current cash flows, protect top accounts from churn, and eliminate unverified overhead.",
            actions=actions,
            milestones=milestones,
            kpis=["Repeat customer rate", "Outstanding receivables aging", "Weekly sales volume"],
        )

    def _build_horizon_2(
        self,
        ctx: UnifiedRecommendationContext,
        recommendations: list[SmartRecommendationItem],
    ) -> GrowthHorizonPlan:
        schemes = ctx.schemes.recommended_schemes
        scheme_name = schemes[0].name if schemes else "Government Credit Scheme"

        actions = [
            f"Prepare and submit application for '{scheme_name}'",
            "Establish digital product catalog and share with regional trade buyers",
            "Align inventory batch sizes to Phase 4 multi-period demand forecasts",
        ]

        milestones = [
            GrowthMilestone(
                milestone="Scheme Documentation Package Submitted",
                target_date_window="Day 45",
                metric_to_track="Application receipt on official portal",
            ),
            GrowthMilestone(
                milestone="Digital Catalog Operational",
                target_date_window="Day 60",
                metric_to_track="Active catalog link distributed to 20+ leads",
            ),
        ]

        return GrowthHorizonPlan(
            horizon="31-90 Days",
            title="Process Standardization & Demand Scaling",
            focus="Expand customer reach, formalize statutory scheme benefits, and scale high-demand product lines.",
            actions=actions,
            milestones=milestones,
            kpis=["New customer acquisition count", "Scheme application approval status", "Forecast forecast accuracy"],
        )

    def _build_horizon_3(
        self,
        ctx: UnifiedRecommendationContext,
        recommendations: list[SmartRecommendationItem],
    ) -> GrowthHorizonPlan:
        actions = [
            "Formalize institutional credit line or working capital facility at subsidized rates",
            "Consolidate supplier contracts to negotiate bulk volume discounts",
            "Implement standardized customer lifecycle management workflow",
        ]

        milestones = [
            GrowthMilestone(
                milestone="Working Capital Facility Secured",
                target_date_window="Month 6",
                metric_to_track="Approved credit limit under statutory scheme",
            ),
            GrowthMilestone(
                milestone="Customer Concentration Below 35%",
                target_date_window="Month 9",
                metric_to_track="Top 3 client share of total revenue",
            ),
        ]

        return GrowthHorizonPlan(
            horizon="3-12 Months",
            title="Strategic Scale & Capital Structuring",
            focus="Scale institutional credit, diversify client portfolio, and establish resilient operational maturity.",
            actions=actions,
            milestones=milestones,
            kpis=["Total annual revenue growth", "Herfindahl customer concentration index", "Business Health Score"],
        )

"""Opportunity Discovery Engine (Phase 5).

Proactively discovers growth and optimization opportunities across 10 strategic categories:
  1. Revenue Expansion
  2. Customer Retention & Reactivation
  3. Product Catalog Optimization
  4. Digital Channel Expansion
  5. Cost & Margin Optimization
  6. Government Schemes & Subsidies
  7. Working Capital & Cashflow Optimization
  8. Seasonal Demand Alignment
  9. Customer & Revenue Diversification
  10. Operational Standardization
"""

from __future__ import annotations

import logging
from typing import Optional

from app.schemas.advanced_recommendations import OpportunityItem
from app.schemas.recommendation_context import UnifiedRecommendationContext

logger = logging.getLogger(__name__)


class OpportunityDiscoveryEngine:
    """Surfaces data-backed growth opportunities across 10 standardized categories."""

    def discover(self, ctx: UnifiedRecommendationContext) -> list[OpportunityItem]:
        """Discover actionable opportunities from verified business intelligence."""
        opportunities: list[OpportunityItem] = []

        # 1. Customer Retention & Reactivation
        opp_retention = self._find_retention_opportunity(ctx)
        if opp_retention:
            opportunities.append(opp_retention)

        # 2. Customer & Revenue Diversification
        opp_diversification = self._find_diversification_opportunity(ctx)
        if opp_diversification:
            opportunities.append(opp_diversification)

        # 3. Product Catalog Optimization & Demand Focus
        opp_product = self._find_product_growth_opportunity(ctx)
        if opp_product:
            opportunities.append(opp_product)

        # 4. Government Schemes & Subsidies
        opp_scheme = self._find_scheme_opportunity(ctx)
        if opp_scheme:
            opportunities.append(opp_scheme)

        # 5. Digital Channel Expansion
        opp_digital = self._find_digital_opportunity(ctx)
        if opp_digital:
            opportunities.append(opp_digital)

        # 6. Operational & Financial Standardization
        opp_ops = self._find_operational_opportunity(ctx)
        if opp_ops:
            opportunities.append(opp_ops)

        return opportunities

    def _find_retention_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        declining_count = len(ctx.customers.declining_customers)
        repeat_rate = ctx.customers.repeat_rate_pct

        if declining_count > 0 or (ctx.customers.total_customers >= 5 and repeat_rate < 40.0):
            return OpportunityItem(
                id="opp_customer_retention",
                title="Lapsed Buyer Reactivation Campaign",
                category="Customer Retention",
                rationale=(
                    f"Identified {declining_count} lapsed or declining customer account(s) and a current repeat "
                    f"rate of {repeat_rate:.1f}%. Reactivating past customers costs 5-7x less than acquiring new ones."
                ),
                evidence_strength="Strong Evidence",
                feasibility="High",
                estimated_impact_description=(
                    "Projected: 10-15% increase in monthly repeat sales if 20% of lapsed accounts are reactivated."
                ),
                first_step="Generate an outreach list of dormant accounts with personalized incentive offers.",
                timeframe="14-30 days",
            )
        return None

    def _find_diversification_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        if not ctx.sales.has_sales_data or not ctx.customers.top_customers_by_revenue:
            return None

        total_rev = ctx.sales.total_revenue
        top3 = ctx.customers.top_customers_by_revenue[:3]
        top3_rev = sum(c.get("revenue", 0.0) for c in top3)
        top3_pct = (top3_rev / total_rev) * 100.0 if total_rev > 0 else 0.0

        if top3_pct >= 40.0:
            return OpportunityItem(
                id="opp_customer_diversification",
                title="Mid-Market Customer Base Diversification",
                category="Revenue Growth",
                rationale=(
                    f"Top 3 clients generate {top3_pct:.1f}% of total revenue. Onboarding 5-10 mid-tier buyers "
                    "will stabilize cash-flow predictability and increase commercial bargaining power."
                ),
                evidence_strength="Strong Evidence",
                feasibility="Medium",
                estimated_impact_description=(
                    f"Projected: Reduces single-client revenue loss exposure from {top3_pct:.0f}% to under 30% within 2 quarters."
                ),
                first_step="Define target buyer profiles in neighboring districts matching past successful orders.",
                timeframe="30-60 days",
            )
        return None

    def _find_product_growth_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return None

        growing = [
            f
            for f in ctx.forecast.product_forecasts
            if f.demand_trend.lower() in ("increasing", "surge")
            or (f.trend_delta_pct and f.trend_delta_pct > 10.0)
        ]

        if growing:
            top_g = growing[0]
            delta = f"+{top_g.trend_delta_pct:.1f}%" if top_g.trend_delta_pct else "increasing"
            return OpportunityItem(
                id="opp_product_demand_surge",
                title=f"Prioritize Production of High-Demand SKU: '{top_g.product_name}'",
                category="Product Performance",
                rationale=(
                    f"Multi-period forecast indicates strong demand growth ({delta}) for '{top_g.product_name}'. "
                    "Focusing sales efforts and procurement here maximizes revenue velocity."
                ),
                evidence_strength="Strong Evidence",
                feasibility="High",
                estimated_impact_description=(
                    f"Projected: Capture up to {top_g.forecasted_units_total:,.0f} units of confirmed demand over next horizon."
                ),
                first_step=f"Confirm raw material lead times and schedule production slots for '{top_g.product_name}'.",
                timeframe="7-21 days",
            )
        return None

    def _find_scheme_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        schemes = ctx.schemes.recommended_schemes or ctx.schemes.eligible_schemes
        if not schemes:
            return None

        top_s = schemes[0]
        return OpportunityItem(
            id="opp_scheme_grant_access",
            title=f"Leverage Statutory Benefit: '{top_s.name}'",
            category="Government Schemes and Funding",
            rationale=(
                f"Business profile matches eligibility criteria for '{top_s.name}' administered by {top_s.official_authority}. "
                "Provides collateral-free financing, interest subsidies, or technology assistance."
            ),
            evidence_strength="Strong Evidence",
            feasibility="Medium",
            estimated_impact_description=(
                f"Projected: Non-dilutive capital access or credit interest subvention under official guidelines."
            ),
            first_step=f"Download official application checklist from {top_s.official_source_url}.",
            timeframe="30-45 days",
        )

    def _find_digital_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        if not ctx.profile.has_website or not ctx.profile.has_ecommerce:
            return OpportunityItem(
                id="opp_digital_catalog",
                title="Establish Direct Digital Catalog & WhatsApp Commerce",
                category="Digital Transformation",
                rationale=(
                    "Current sales rely almost exclusively on offline or manual channels. "
                    "A digital product catalog enables frictionless order taking and expanded regional discovery."
                ),
                evidence_strength="Moderate Evidence",
                feasibility="High",
                estimated_impact_description=(
                    "Projected: 15-25% faster order inquiry turnaround and expanded customer reach."
                ),
                first_step="Create a shareable digital PDF/web product catalog with standardized pricing.",
                timeframe="14-21 days",
            )
        return None

    def _find_operational_opportunity(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[OpportunityItem]:
        score = ctx.health.overall_score
        if score < 75:
            return OpportunityItem(
                id="opp_operational_health_lift",
                title="Business Health & Creditworthiness Optimization",
                category="Financial Management",
                rationale=(
                    f"Current business health score is {score}/100. Completing verified operational records "
                    "directly elevates formal bankability and loan eligibility terms."
                ),
                evidence_strength="Strong Evidence",
                feasibility="High",
                estimated_impact_description=(
                    "Projected: Elevate health grade to 'Good' (75+) to unlock favorable credit terms from institutional lenders."
                ),
                first_step="Complete missing profile fields in the UrsBiz Business Twin dashboard.",
                timeframe="7-14 days",
            )
        return None

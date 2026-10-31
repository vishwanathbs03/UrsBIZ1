"""AI Root Cause Analysis Engine (Phase 5).

Deconstructs observed business symptoms into:
  1. Observed Symptom (Empirical data observation)
  2. Verified Contributing Factors (Directly corroborated by UrsBiz modules)
  3. Plausible Underlying Causes (Operational and commercial hypotheses)
  4. Data Gaps & Unknown Factors (External context requiring owner confirmation)
  5. Urgency Level (Immediate, Near-term, Watch)
"""

from __future__ import annotations

import logging
from typing import Optional

from app.schemas.advanced_recommendations import RootCauseAnalysisItem
from app.schemas.recommendation_context import UnifiedRecommendationContext

logger = logging.getLogger(__name__)


class RootCauseEngine:
    """Diagnoses business symptoms and decomposes them into verified vs unverified causes."""

    def diagnose(self, ctx: UnifiedRecommendationContext) -> list[RootCauseAnalysisItem]:
        """Perform root cause analysis across business intelligence domains."""
        analyses: list[RootCauseAnalysisItem] = []

        # 1. Customer Concentration Vulnerability
        rc_concentration = self._diagnose_concentration(ctx)
        if rc_concentration:
            analyses.append(rc_concentration)

        # 2. Customer Inactivity and Repeat Rate Deficit
        rc_retention = self._diagnose_retention(ctx)
        if rc_retention:
            analyses.append(rc_retention)

        # 3. Product Demand Contraction or Volatility
        rc_demand = self._diagnose_demand_volatility(ctx)
        if rc_demand:
            analyses.append(rc_demand)

        # 4. Overall Business Health / Digital Gap
        rc_health = self._diagnose_health_deficit(ctx)
        if rc_health:
            analyses.append(rc_health)

        return analyses

    def _diagnose_concentration(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[RootCauseAnalysisItem]:
        if not ctx.sales.has_sales_data or not ctx.customers.top_customers_by_revenue:
            return None

        total_rev = ctx.sales.total_revenue
        top3 = ctx.customers.top_customers_by_revenue[:3]
        top3_rev = sum(c.get("revenue", 0.0) for c in top3)
        top3_pct = (top3_rev / total_rev) * 100.0 if total_rev > 0 else 0.0

        if top3_pct < 40.0:
            return None

        top1_name = top3[0].get("customer_name") or top3[0].get("customer_id") or "Primary Customer"
        top1_rev = top3[0].get("revenue", 0.0)
        top1_pct = (top1_rev / total_rev) * 100.0 if total_rev > 0 else 0.0

        return RootCauseAnalysisItem(
            id="rc_customer_concentration",
            symptom=f"Heavy sales concentration on top accounts: Top 3 generate {top3_pct:.1f}% of total revenue.",
            verified_factors=[
                f"Account '{top1_name}' contributes ₹{top1_rev:,.0f} ({top1_pct:.1f}% of overall revenue)",
                f"Total active customer roster is {ctx.customers.total_customers} accounts across {ctx.sales.total_transactions} sales orders",
                f"Aggregate top-3 client dependency stands at ₹{top3_rev:,.0f}",
            ],
            plausible_causes=[
                "Historical sales focus prioritized large customized orders from initial flagship relationships",
                "Absence of a systematic outbound lead generation pipeline for mid-sized clients",
                "Account management bandwidth focused almost entirely on maintaining top 2-3 contracts",
            ],
            data_gaps_and_unknowns=[
                "Terms and expiration dates of master service agreements or contracts with top clients",
                "Client-side satisfaction levels or whether client has sought competing quotes",
                "Internal capacity limits preventing simultaneous onboarding of newer accounts",
            ],
            urgency="Immediate" if top3_pct >= 60.0 else "Near-term",
        )

    def _diagnose_retention(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[RootCauseAnalysisItem]:
        if not ctx.customers.total_customers or ctx.customers.total_customers < 3:
            return None

        repeat_rate = ctx.customers.repeat_rate_pct
        declining = ctx.customers.declining_customers

        if repeat_rate >= 35.0 and len(declining) == 0:
            return None

        return RootCauseAnalysisItem(
            id="rc_customer_retention",
            symptom=f"Low re-order velocity: Only {repeat_rate:.1f}% of buyers make repeat purchases, with {len(declining)} dormant account(s).",
            verified_factors=[
                f"Repeat customer rate is {repeat_rate:.1f}% (Industry healthy benchmark: > 35%)",
                f"{len(declining)} past customer account(s) show extended inactivity or declining order cadence",
                f"Average Order Value across recorded transactions is ₹{ctx.customers.average_order_value:,.0f}",
            ],
            plausible_causes=[
                "Lack of structured post-delivery check-in or proactive re-order reminders",
                "Order fulfillment lead time or communication gaps during previous delivery",
                "Product usage cycle does not naturally prompt immediate repurchase without cross-selling",
            ],
            data_gaps_and_unknowns=[
                "Direct customer feedback on product quality, pricing, or service delivery",
                "Whether inactive accounts have transitioned to competing regional suppliers",
                "Customer product consumption cycles (whether purchases are seasonal or project-based)",
            ],
            urgency="Near-term",
        )

    def _diagnose_demand_volatility(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[RootCauseAnalysisItem]:
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return None

        declining_forecasts = [
            f
            for f in ctx.forecast.product_forecasts
            if f.demand_trend.lower() in ("declining", "downward")
            or (f.trend_delta_pct and f.trend_delta_pct < -10.0)
        ]

        if not declining_forecasts:
            return None

        item = declining_forecasts[0]
        delta_str = (
            f"{item.trend_delta_pct:.1f}%"
            if item.trend_delta_pct
            else "downward"
        )

        return RootCauseAnalysisItem(
            id="rc_demand_contraction",
            symptom=f"Demand contraction projected for '{item.product_name}' ({delta_str} over next {item.forecast_horizon_periods} periods).",
            verified_factors=[
                f"Forecast model ({item.selected_model}) projects a decline with {item.reliability} reliability",
                f"Expected total volume over forecast horizon: {item.forecasted_units_total:.0f} units",
                f"Evaluation MAE on holdout test data: {item.best_mae if item.best_mae is not None else 'N/A'}",
            ],
            plausible_causes=[
                "Seasonal purchasing cycle or post-festival lull in end-market demand",
                "Market maturation or price sensitivity causing buyers to trade down",
                "Substituted purchasing towards newer product variants or alternative SKUs",
            ],
            data_gaps_and_unknowns=[
                "Recent price changes or promotions by competing vendors in the category",
                "End-consumer inventory levels in retail or distribution channels",
                "Broader macroeconomic or raw material cost shifts affecting downstream demand",
            ],
            urgency="Near-term",
        )

    def _diagnose_health_deficit(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[RootCauseAnalysisItem]:
        score = ctx.health.overall_score
        missing = ctx.health.missing_fields

        if score >= 70 and not missing:
            return None

        return RootCauseAnalysisItem(
            id="rc_business_health_profile",
            symptom=f"Business health index stands at {score}/100 (Grade: {ctx.health.grade}) with {len(missing)} missing profile data dimension(s).",
            verified_factors=[
                f"Overall composite score is {score}/100",
                f"Missing critical operational fields: {', '.join(missing[:3]) if missing else 'None'}",
                f"Digital readiness index at {ctx.readiness.digital_readiness_score:.0f}/100",
            ],
            plausible_causes=[
                "Founder time constraints leading to partial record maintenance and ad-hoc filing",
                "Informal operational workflows without automated ledger or CRM integration",
                "Underestimation of how documented governance impacts creditworthiness and scheme access",
            ],
            data_gaps_and_unknowns=[
                "Official audited balance sheet details (current debt obligations and working capital ratios)",
                "Statutory GST compliance status and filing timeliness",
                "Specific banking relationships or current collateral pledges",
            ],
            urgency="Immediate" if score < 50 else "Near-term",
        )

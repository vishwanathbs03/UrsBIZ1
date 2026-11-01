"""Multi-Signal Business Intelligence Reasoning Engine (Phase 5).

Evaluates cross-signal correlations across disparate business dimensions:
  1. Customer Concentration + Inactivity/Declining Spend -> Severe Revenue Vulnerability
  2. Demand Surge + Operational/Capacity Limits -> Growth Bottleneck
  3. Revenue Growth + Low Financial Health/Margin -> Margin Erosion / Profitless Growth
  4. Intermittent Demand + High Volatility -> Working Capital Lockup
  5. Scheme Match + Low Digital/Formal Adoption -> Untapped Subsidy / Formalization Unlock
  6. Low Repeat Purchase Rate + Customer Inactivity -> Customer Retention Leakage
"""

from __future__ import annotations

import logging
from typing import Optional

from app.schemas.advanced_recommendations import CrossSignalInsight
from app.schemas.recommendation_context import UnifiedRecommendationContext

logger = logging.getLogger(__name__)


class MultiSignalEngine:
    """Detects multi-signal cross-correlations across verified business context."""

    def analyze(self, ctx: UnifiedRecommendationContext) -> list[CrossSignalInsight]:
        """Analyze unified context and synthesize cross-signal insights."""
        insights: list[CrossSignalInsight] = []

        # 1. Customer Concentration + Declining Customers / Inactivity
        insight_concentration = self._eval_concentration_risk(ctx)
        if insight_concentration:
            insights.append(insight_concentration)

        # 2. Demand Surge + Operational/Fulfillment Constraints
        insight_capacity = self._eval_demand_capacity_bottleneck(ctx)
        if insight_capacity:
            insights.append(insight_capacity)

        # 3. Revenue Volume vs Financial Health / Margin Compression
        insight_margin = self._eval_margin_divergence(ctx)
        if insight_margin:
            insights.append(insight_margin)

        # 4. Intermittent Demand + Forecast Volatility
        insight_intermittent = self._eval_intermittent_volatility(ctx)
        if insight_intermittent:
            insights.append(insight_intermittent)

        # 5. High-Value Scheme Match + Digital/Compliance Deficit
        insight_scheme = self._eval_scheme_formalization_unlock(ctx)
        if insight_scheme:
            insights.append(insight_scheme)

        # 6. Customer Inactivity + Low Repeat Rate
        insight_leakage = self._eval_retention_leakage(ctx)
        if insight_leakage:
            insights.append(insight_leakage)

        return insights

    def _eval_concentration_risk(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        if not ctx.sales.has_sales_data or not ctx.customers.top_customers_by_revenue:
            return None

        total_rev = ctx.sales.total_revenue
        if total_rev <= 0:
            return None

        top3 = ctx.customers.top_customers_by_revenue[:3]
        top3_rev = sum(c.get("revenue", 0.0) for c in top3)
        top3_pct = (top3_rev / total_rev) * 100.0 if total_rev > 0 else 0.0

        declining_count = len(ctx.customers.declining_customers)

        if top3_pct >= 40.0:
            severity = "Critical" if top3_pct >= 60.0 or declining_count > 0 else "High"
            signals = [
                f"Top 3 customers account for {top3_pct:.1f}% of total sales (₹{top3_rev:,.0f})",
                f"Customer base has {declining_count} account(s) with declining purchase activity",
                f"Total customer pool is {ctx.customers.total_customers} clients",
            ]
            return CrossSignalInsight(
                id="cs_concentration_churn_risk",
                title="Severe Revenue Vulnerability: High Concentration & Account Churn Risk",
                severity=severity,
                pattern_type="concentration_churn_risk",
                signals_combined=signals,
                business_implication=(
                    f"Over {top3_pct:.0f}% of total business turnover depends on just 3 accounts. "
                    "If a single key client reduces order volume or switches to a competitor, "
                    "monthly cash flow will face an immediate, potentially crippling deficit."
                ),
                recommended_action=(
                    "Implement a proactive Key Account Retention Protocol with personal relationship reviews, "
                    "while systematically broadening lead acquisition to dilute top-client exposure."
                ),
                evidence_strength="Strong Evidence",
                linked_recommendation_id=f"rec_cust_conc_{ctx.business_id}_top3_v1",
            )
        return None

    def _eval_demand_capacity_bottleneck(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return None

        surging_products = [
            f
            for f in ctx.forecast.product_forecasts
            if f.demand_trend.lower() in ("increasing", "surge")
            or (f.trend_delta_pct and f.trend_delta_pct > 15.0)
        ]

        if not surging_products:
            return None

        top_surging = surging_products[0]
        delta_str = (
            f"+{top_surging.trend_delta_pct:.1f}%"
            if top_surging.trend_delta_pct
            else "Upward"
        )
        readiness_score = ctx.readiness.operational_completeness_pct

        signals = [
            f"Forecasted demand for '{top_surging.product_name}' trending {delta_str} over next {top_surging.forecast_horizon_periods} periods",
            f"Expected units: {top_surging.forecasted_units_total:,.0f} units (Model: {top_surging.selected_model})",
            f"Operational completeness index is at {readiness_score:.0f}%",
        ]

        return CrossSignalInsight(
            id="cs_capacity_surge_bottleneck",
            title="Growth Bottleneck: Surging Product Demand vs Fulfillment Constraints",
            severity="High",
            pattern_type="capacity_bottleneck",
            signals_combined=signals,
            business_implication=(
                f"Demand for '{top_surging.product_name}' is projected to expand significantly. "
                "Without staged raw material procurement and production bandwidth alignment, "
                "the business risks delivery delays, customer dissatisfaction, and forfeited market share."
            ),
            recommended_action=(
                f"Verify supplier lead times and stage procurement batches for '{top_surging.product_name}' "
                "to match the multi-period forecast trajectory before seasonal spikes materialize."
            ),
            evidence_strength="Strong Evidence",
            linked_recommendation_id=f"rec_prod_focus_{ctx.business_id}_perf_v1",
        )

    def _eval_margin_divergence(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        if not ctx.sales.has_sales_data or ctx.sales.total_transactions < 10:
            return None

        health_score = ctx.health.overall_score
        financial_facet = ctx.health.facet_scores.get("financial", 100.0)

        if health_score < 60 or financial_facet < 55.0:
            signals = [
                f"Recorded revenue of ₹{ctx.sales.total_revenue:,.0f} across {ctx.sales.total_transactions} transactions",
                f"Overall business health score is {health_score}/100 (Grade: {ctx.health.grade})",
                f"Financial health facet score is {financial_facet:.0f}/100",
            ]
            return CrossSignalInsight(
                id="cs_margin_erosion_risk",
                title="Profitless Growth Risk: Volume Expansion vs Margin Compression",
                severity="High",
                pattern_type="margin_erosion",
                signals_combined=signals,
                business_implication=(
                    "Transaction activity is active, yet business financial health indicates "
                    "thin profit margins or excessive working overhead. Increasing sales volume "
                    "without protecting unit gross margins increases cash-flow stress rather than net worth."
                ),
                recommended_action=(
                    "Conduct a per-SKU contribution margin review. Eliminate unprofitable discounting "
                    "and review payment collection terms with delayed-paying customers."
                ),
                evidence_strength="Moderate Evidence",
                linked_recommendation_id=f"rec_fin_margin_{ctx.business_id}_health_v1",
            )
        return None

    def _eval_intermittent_volatility(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        if not ctx.forecast.has_forecast_data:
            return None

        intermittent_items = [
            f
            for f in ctx.forecast.product_forecasts
            if "croston" in f.selected_model.lower()
            or "intermittent" in f.selected_model.lower()
            or "intermittent" in f.demand_trend.lower()
        ]

        if not intermittent_items:
            return None

        sample = intermittent_items[0]
        signals = [
            f"Intermittent demand pattern detected on '{sample.product_name}' (Model: {sample.selected_model})",
            f"Forecasted volume: {sample.forecasted_units_total:.0f} units with {sample.reliability} reliability",
            f"Historical demand exhibits sporadic, zero-demand intervals",
        ]

        return CrossSignalInsight(
            id="cs_intermittent_capital_lockup",
            title="Working Capital Risk: Intermittent Demand & Inventory Lockup",
            severity="Medium",
            pattern_type="intermittent_demand_volatility",
            signals_combined=signals,
            business_implication=(
                f"Demand for '{sample.product_name}' arrives in sporadic bursts rather than steady flows. "
                "Speculative bulk manufacturing or purchasing based on simple averages will lock up "
                "scarce working capital in slow-moving stock."
            ),
            recommended_action=(
                "Adopt a staged, order-triggered procurement model for intermittent lines. "
                "Avoid speculative inventory holding without confirmed customer purchase orders."
            ),
            evidence_strength="Strong Evidence",
            linked_recommendation_id=f"rec_demand_intermittent_{ctx.business_id}_{sample.product_name[:12]}_v1",
        )

    def _eval_scheme_formalization_unlock(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        schemes = ctx.schemes.recommended_schemes or ctx.schemes.eligible_schemes
        if not schemes:
            return None

        digital_score = ctx.readiness.digital_readiness_score
        has_web = ctx.profile.has_website
        has_ecom = ctx.profile.has_ecommerce

        if digital_score < 50.0 or not has_web or not has_ecom:
            top_scheme = schemes[0]
            signals = [
                f"{len(schemes)} matched government scheme(s) including '{top_scheme.name}'",
                f"Authority: {top_scheme.official_authority}",
                f"Digital readiness score is {digital_score:.0f}/100 (E-commerce active: {has_ecom})",
            ]
            return CrossSignalInsight(
                id="cs_scheme_formalization_unlock",
                title="Untapped Funding Unlock: Available Government Subsidies vs Digital Gaps",
                severity="Medium",
                pattern_type="scheme_unlock",
                signals_combined=signals,
                business_implication=(
                    f"The business is eligible for major statutory benefits under '{top_scheme.name}', "
                    "yet low digital readiness and documentation gaps delay application readiness, "
                    "leaving non-dilutive capital and interest subvention unclaimed."
                ),
                recommended_action=(
                    f"Assemble required documentation for '{top_scheme.name}' ({', '.join(top_scheme.documents_required[:2]) if top_scheme.documents_required else 'Udyam, Bank Statement'}) "
                    "and submit official portal application."
                ),
                evidence_strength="Strong Evidence",
                linked_recommendation_id=f"rec_scheme_{ctx.business_id}_{top_scheme.id[:10]}_v1",
            )
        return None

    def _eval_retention_leakage(
        self, ctx: UnifiedRecommendationContext
    ) -> Optional[CrossSignalInsight]:
        if not ctx.customers.total_customers or ctx.customers.total_customers < 5:
            return None

        repeat_rate = ctx.customers.repeat_rate_pct
        declining_count = len(ctx.customers.declining_customers)

        if repeat_rate < 30.0 or declining_count >= 2:
            signals = [
                f"Customer repeat purchase rate is {repeat_rate:.1f}% across {ctx.customers.total_customers} clients",
                f"{declining_count} customer account(s) have zero recent repeat transactions",
                f"Average Order Value: ₹{ctx.customers.average_order_value:,.0f}",
            ]
            return CrossSignalInsight(
                id="cs_retention_leakage",
                title="Customer Retention Leakage: Low Re-order Velocity",
                severity="High",
                pattern_type="retention_leakage",
                signals_combined=signals,
                business_implication=(
                    "Customer acquisition costs are currently consumed on single transactions. "
                    "Without systematic re-engagement, past buyers lapse into dormancy, requiring "
                    "continuous, expensive marketing to replace lost transaction volume."
                ),
                recommended_action=(
                    "Launch a 30-day post-purchase check-in sequence with an exclusive re-order incentive "
                    "to reactivate lapsed accounts before they are permanently lost."
                ),
                evidence_strength="Strong Evidence",
                linked_recommendation_id=f"rec_cust_ret_{ctx.business_id}_repeat_v1",
            )
        return None

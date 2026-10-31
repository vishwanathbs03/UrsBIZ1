"""Deterministic Scenario Simulation Engine (Phase 5).

Allows MSME owners to run What-If simulations grounded in their empirical baseline:
  - Sales Growth impact (+5%, +10%, +20%)
  - Customer Retention improvement impact
  - Operating Expense reduction impact
  - Top-Customer Concentration dilution impact

All formulas are transparent, deterministic, and strictly labeled as hypothetical projections.
"""

from __future__ import annotations

import logging
from app.schemas.advanced_recommendations import (
    ScenarioMetricResult,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext

logger = logging.getLogger(__name__)


class ScenarioSimulationEngine:
    """Calculates deterministic hypothetical projections based on verified business baselines."""

    def simulate(
        self,
        ctx: UnifiedRecommendationContext,
        req: ScenarioSimulationRequest,
    ) -> ScenarioSimulationResponse:
        """Run scenario simulation for the business."""
        # 1. Establish baseline figures
        if ctx.sales.has_sales_data and ctx.sales.total_revenue > 0:
            # Estimate monthly baseline from ledger
            days = max(ctx.sales.date_range_days, 30)
            baseline_monthly_revenue = (ctx.sales.total_revenue / days) * 30.0
        elif ctx.profile.annual_revenue and ctx.profile.annual_revenue > 0:
            baseline_monthly_revenue = ctx.profile.annual_revenue / 12.0
        else:
            baseline_monthly_revenue = 100000.0  # Fallback benchmark for zero-ledger businesses

        # Baseline repeat revenue share
        repeat_pct = ctx.customers.repeat_rate_pct if ctx.customers.repeat_rate_pct > 0 else 20.0
        baseline_repeat_revenue = baseline_monthly_revenue * (repeat_pct / 100.0)

        # Baseline operating expense estimation (industry average 75% of revenue if not ledgered)
        baseline_monthly_expense = baseline_monthly_revenue * 0.75
        baseline_gross_margin_pct = 25.0

        # Baseline concentration
        if ctx.customers.top_customers_by_revenue and ctx.sales.total_revenue > 0:
            top3 = ctx.customers.top_customers_by_revenue[:3]
            top3_rev = sum(c.get("revenue", 0.0) for c in top3)
            baseline_concentration_pct = (top3_rev / ctx.sales.total_revenue) * 100.0
        else:
            baseline_concentration_pct = 50.0

        # 2. Compute Projected Figures
        # Revenue projection
        sales_growth_factor = 1.0 + (req.sales_growth_pct / 100.0)
        projected_monthly_revenue = baseline_monthly_revenue * sales_growth_factor
        revenue_delta = projected_monthly_revenue - baseline_monthly_revenue

        # Repeat customer revenue projection
        repeat_growth_factor = 1.0 + (req.repeat_customer_rate_improvement_pct / 100.0)
        projected_repeat_revenue = baseline_repeat_revenue * repeat_growth_factor
        repeat_delta = projected_repeat_revenue - baseline_repeat_revenue

        # Expense reduction projection
        expense_savings = baseline_monthly_expense * (req.expense_reduction_pct / 100.0)
        projected_monthly_expense = baseline_monthly_expense - expense_savings

        # Gross profit change = (revenue delta * margin%) + expense savings
        gross_profit_change = (revenue_delta * (baseline_gross_margin_pct / 100.0)) + expense_savings

        # Concentration projection
        concentration_reduction_factor = 1.0 - (req.concentration_reduction_pct / 100.0)
        projected_concentration_pct = max(0.0, baseline_concentration_pct * concentration_reduction_factor)
        concentration_delta = projected_concentration_pct - baseline_concentration_pct

        # 3. Build Detailed Metric Explanations
        metrics: list[ScenarioMetricResult] = [
            ScenarioMetricResult(
                metric_name="Monthly Revenue",
                baseline_value=round(baseline_monthly_revenue, 2),
                projected_value=round(projected_monthly_revenue, 2),
                delta_value=round(revenue_delta, 2),
                unit="₹",
                formula_explanation=f"Baseline (₹{baseline_monthly_revenue:,.0f}) × (1 + {req.sales_growth_pct}% sales growth)",
            ),
            ScenarioMetricResult(
                metric_name="Repeat Customer Monthly Revenue",
                baseline_value=round(baseline_repeat_revenue, 2),
                projected_value=round(projected_repeat_revenue, 2),
                delta_value=round(repeat_delta, 2),
                unit="₹",
                formula_explanation=f"Baseline repeat sales (₹{baseline_repeat_revenue:,.0f}) × (1 + {req.repeat_customer_rate_improvement_pct}% retention lift)",
            ),
            ScenarioMetricResult(
                metric_name="Monthly Operating Expenses",
                baseline_value=round(baseline_monthly_expense, 2),
                projected_value=round(projected_monthly_expense, 2),
                delta_value=round(-expense_savings, 2),
                unit="₹",
                formula_explanation=f"Baseline expenses (₹{baseline_monthly_expense:,.0f}) - {req.expense_reduction_pct}% cost optimization",
            ),
            ScenarioMetricResult(
                metric_name="Top-3 Customer Dependency",
                baseline_value=round(baseline_concentration_pct, 1),
                projected_value=round(projected_concentration_pct, 1),
                delta_value=round(concentration_delta, 1),
                unit="%",
                formula_explanation=f"Baseline concentration ({baseline_concentration_pct:.1f}%) reduced by {req.concentration_reduction_pct}% through client diversification",
            ),
        ]

        # 4. Generate Key Takeaways
        takeaways: list[str] = []
        if req.sales_growth_pct > 0:
            takeaways.append(
                f"A {req.sales_growth_pct:.0f}% lift in sales generates an estimated ₹{revenue_delta:,.0f}/month in additional turnover."
            )
        if req.expense_reduction_pct > 0:
            takeaways.append(
                f"A {req.expense_reduction_pct:.0f}% expense discipline directly preserves ₹{expense_savings:,.0f}/month in liquid cash reserves."
            )
        if req.concentration_reduction_pct > 0:
            takeaways.append(
                f"Diversifying client acquisition dilutes top-customer exposure to {projected_concentration_pct:.1f}%, materially lowering sudden churn vulnerability."
            )
        if not takeaways:
            takeaways.append("Adjust the scenario parameters above to simulate potential financial outcomes.")

        return ScenarioSimulationResponse(
            baseline_revenue=round(baseline_monthly_revenue, 2),
            projected_revenue=round(projected_monthly_revenue, 2),
            estimated_gross_profit_change=round(gross_profit_change, 2),
            metrics=metrics,
            key_takeaways=takeaways,
        )

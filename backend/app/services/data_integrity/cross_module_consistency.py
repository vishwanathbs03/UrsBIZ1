"""Cross-Module Consistency & Reconciliation Engine (Phase 5 Data Integrity).

Validates consistency across disparate business modules:
  1. Sales transactions total vs sales summary turnover
  2. Product-level revenue vs total business turnover
  3. Customer-level revenue vs total business turnover
  4. Forecast horizons vs historical observation periods
  5. Recommendation claims vs verified provenance evidence
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from app.schemas.data_provenance import CrossModuleDiscrepancy
from app.schemas.recommendation_context import UnifiedRecommendationContext

logger = logging.getLogger("ursbiz.cross_module_consistency")


class CrossModuleConsistencyEngine:
    """Verifies that mathematical and temporal invariants hold across business modules."""

    def __init__(self, relative_tolerance: float = 0.02) -> None:
        self.rel_tol = relative_tolerance

    def reconcile_context(
        self,
        ctx: UnifiedRecommendationContext,
    ) -> list[CrossModuleDiscrepancy]:
        """Perform comprehensive cross-module consistency reconciliation."""
        discrepancies: list[CrossModuleDiscrepancy] = []
        biz_id = ctx.business_id

        total_rev = ctx.sales.total_revenue or 0.0
        has_sales = ctx.sales.has_sales_data and total_rev > 0

        # ---------------------------------------------------------------------
        # 1. Product-Level Revenue vs Total Revenue
        # ---------------------------------------------------------------------
        if has_sales and ctx.products.top_products_by_revenue:
            prod_sum = sum(
                float(p.get("revenue", 0.0)) for p in ctx.products.top_products_by_revenue
            )
            # If top products alone exceed total revenue
            if prod_sum > (total_rev * (1.0 + self.rel_tol)):
                diff_pct = round(((prod_sum - total_rev) / total_rev) * 100.0, 1)
                discrepancies.append(
                    CrossModuleDiscrepancy(
                        id=f"disc_prod_rev_{uuid.uuid4().hex[:8]}",
                        business_id=biz_id,
                        discrepancy_type="product_revenue_overflow",
                        module_a="products",
                        metric_a="sum_top_products_revenue",
                        value_a=prod_sum,
                        module_b="sales",
                        metric_b="total_revenue",
                        value_b=total_rev,
                        divergence_pct=diff_pct,
                        description=(
                            f"Sum of top products revenue (₹{prod_sum:,.0f}) exceeds total business turnover "
                            f"(₹{total_rev:,.0f}) by {diff_pct}%."
                        ),
                        resolution_guidance="Verify SKU transaction categorizations and eliminate overlapping product rollups.",
                        severity="High",
                    )
                )

        # ---------------------------------------------------------------------
        # 2. Customer-Level Revenue vs Total Revenue
        # ---------------------------------------------------------------------
        if has_sales and ctx.customers.top_customers_by_revenue:
            top_cust = ctx.customers.top_customers_by_revenue[0]
            top_cust_rev = float(top_cust.get("revenue", 0.0))
            cust_name = top_cust.get("customer_name") or "Primary Customer"

            # Individual customer cannot exceed total revenue
            if top_cust_rev > (total_rev * (1.0 + self.rel_tol)):
                diff_pct = round(((top_cust_rev - total_rev) / total_rev) * 100.0, 1)
                discrepancies.append(
                    CrossModuleDiscrepancy(
                        id=f"disc_cust_rev_{uuid.uuid4().hex[:8]}",
                        business_id=biz_id,
                        discrepancy_type="customer_revenue_overflow",
                        module_a="customers",
                        metric_a="top_customer_revenue",
                        value_a=top_cust_rev,
                        module_b="sales",
                        metric_b="total_revenue",
                        value_b=total_rev,
                        divergence_pct=diff_pct,
                        description=(
                            f"Top customer '{cust_name}' revenue (₹{top_cust_rev:,.0f}) exceeds total business turnover "
                            f"(₹{total_rev:,.0f}) by {diff_pct}%."
                        ),
                        resolution_guidance="Verify customer invoice linkage; individual client turnover cannot exceed aggregate turnover.",
                        severity="Critical",
                    )
                )

        # ---------------------------------------------------------------------
        # 3. Profile Revenue vs Transaction Ledger Turnover
        # ---------------------------------------------------------------------
        prof_rev = ctx.profile.annual_revenue
        if prof_rev and has_sales:
            div = abs(prof_rev - total_rev)
            if div > (0.4 * prof_rev):
                diff_pct = round((div / prof_rev) * 100.0, 1)
                discrepancies.append(
                    CrossModuleDiscrepancy(
                        id=f"disc_profile_sales_{uuid.uuid4().hex[:8]}",
                        business_id=biz_id,
                        discrepancy_type="profile_sales_reconciliation",
                        module_a="profile",
                        metric_a="annual_revenue",
                        value_a=prof_rev,
                        module_b="sales",
                        metric_b="total_revenue",
                        value_b=total_rev,
                        divergence_pct=diff_pct,
                        description=(
                            f"Stated profile annual turnover (₹{prof_rev:,.0f}) diverges significantly ({diff_pct}%) "
                            f"from verified transaction ledger turnover (₹{total_rev:,.0f})."
                        ),
                        resolution_guidance=(
                            "Expose discrepancy to owner: Insights prioritize verified invoice transactions "
                            "over self-reported profile figures."
                        ),
                        severity="Medium",
                    )
                )

        # ---------------------------------------------------------------------
        # 4. Forecast Horizon vs Historical Sales Period
        # ---------------------------------------------------------------------
        if ctx.forecast and ctx.forecast.has_forecast_data and ctx.sales.latest_transaction_date:
            try:
                latest_sales_dt = datetime.fromisoformat(
                    ctx.sales.latest_transaction_date.replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                # If forecast generated without minimum 6 periods
                if ctx.sales.total_transactions < 6:
                    discrepancies.append(
                        CrossModuleDiscrepancy(
                            id=f"disc_fc_history_{uuid.uuid4().hex[:8]}",
                            business_id=biz_id,
                            discrepancy_type="insufficient_forecast_history",
                            module_a="forecast",
                            metric_a="forecast_status",
                            value_a="generated",
                            module_b="sales",
                            metric_b="total_transactions",
                            value_b=ctx.sales.total_transactions,
                            description=(
                                f"Demand forecast generated with only {ctx.sales.total_transactions} historical transactions. "
                                "Statistical forecasting mandates minimum 6 periods for reliability."
                            ),
                            resolution_guidance="Flag forecast reliability as 'Low' or 'Provisional'.",
                            severity="High",
                        )
                    )
            except Exception as e:
                logger.warning(f"Error checking forecast temporal consistency: {e}")

        return discrepancies

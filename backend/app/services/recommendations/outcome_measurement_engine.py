"""Before-and-After Business Measurement Engine (Phase 5 Closed-Loop Intelligence).

Measures empirical business changes across symmetric time windows before and after
recommendation implementation with strict scientific honesty and zero false causal claims.

Core Principles:
  1. Symmetric Measurement Windows (14, 30, or 60 days before vs after completion).
  2. Baseline Preservation: Pre-period transactions establish frozen baselines.
  3. Gap Detection: Explicitly flags insufficient post-period elapsed days or missing baseline data.
  4. Mandatory Causal Disclaimer: Explicitly communicates that observed changes reflect
     empirical correlation in observational business data, NOT counterfactual proof of causation.
  5. Learning Quality Tier: Categorizes all observations as OBSERVED_CORRELATION.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sales import SalesTransaction
from app.schemas.recommendation_outcomes import (
    BeforeAfterMeasurementResponse,
    MetricComparison,
)

logger = logging.getLogger("atlas.recommendations.outcome_measurement")


class BeforeAfterMeasurementEngine:
    """Computes deterministic before-and-after business metrics across symmetric time windows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def measure_outcome(
        self,
        business_id: int,
        recommendation_id: str,
        recommendation_title: str,
        completed_at: Optional[datetime],
        window_days: int = 30,
    ) -> BeforeAfterMeasurementResponse:
        """Measure sales and customer changes across symmetric time windows before and after completion."""
        now = datetime.now(timezone.utc)
        data_gaps: list[str] = []

        if completed_at is None:
            return BeforeAfterMeasurementResponse(
                recommendation_id=recommendation_id,
                title=recommendation_title,
                completed_at=None,
                measurement_window_days=window_days,
                window_status="INSUFFICIENT_POST_PERIOD_DATA",
                elapsed_days_since_completion=0,
                comparison_methodology=f"symmetric_time_window_{window_days}d",
                data_gaps=["Recommendation has not been marked as completed. A completion date is required to establish measurement windows."],
                metrics=[],
                causal_disclaimer="Action is not yet completed. Before-and-after business measurement requires a verified completion timestamp.",
                learning_quality_tier="ACTION_COMPLETION",
            )

        # Ensure completed_at is timezone-aware
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        # Calculate time windows
        pre_period_start = completed_at - timedelta(days=window_days)
        pre_period_end = completed_at
        post_period_start = completed_at
        post_period_end = completed_at + timedelta(days=window_days)

        elapsed_days = max(0, (now - completed_at).days)

        # Check post-window completion
        window_status = "COMPLETED_WINDOW"
        effective_post_end = post_period_end

        if elapsed_days < window_days:
            window_status = "PARTIAL_WINDOW_IN_PROGRESS"
            effective_post_end = now
            remaining_days = window_days - elapsed_days
            data_gaps.append(
                f"Only {elapsed_days} day{'s' if elapsed_days != 1 else ''} have elapsed since completion. "
                f"A complete {window_days}-day post-window evaluation requires {remaining_days} additional day{'s' if remaining_days != 1 else ''} of recorded business activity."
            )

        # Retrieve Pre-period Sales Transactions
        pre_stmt = (
            select(SalesTransaction)
            .where(
                SalesTransaction.business_id == business_id,
                SalesTransaction.is_duplicate.is_(False),
                SalesTransaction.transaction_date >= pre_period_start,
                SalesTransaction.transaction_date < pre_period_end,
            )
            .order_by(SalesTransaction.transaction_date.asc())
        )
        pre_txs = list(self.db.scalars(pre_stmt).all())

        # Retrieve Post-period Sales Transactions
        post_stmt = (
            select(SalesTransaction)
            .where(
                SalesTransaction.business_id == business_id,
                SalesTransaction.is_duplicate.is_(False),
                SalesTransaction.transaction_date >= post_period_start,
                SalesTransaction.transaction_date <= effective_post_end,
            )
            .order_by(SalesTransaction.transaction_date.asc())
        )
        post_txs = list(self.db.scalars(post_stmt).all())

        # Check baseline availability
        if len(pre_txs) == 0:
            window_status = "INSUFFICIENT_BASELINE_DATA"
            data_gaps.append(
                f"No sales transactions were recorded during the baseline pre-period "
                f"({pre_period_start.strftime('%Y-%m-%d')} to {pre_period_end.strftime('%Y-%m-%d')}). "
                f"Baseline performance could not be established."
            )

        # Deterministic Metric Calculations
        metrics: list[MetricComparison] = []

        # 1. Revenue Comparison
        pre_rev = sum(float(t.total_amount or 0.0) for t in pre_txs)
        post_rev = sum(float(t.total_amount or 0.0) for t in post_txs)
        rev_delta_abs = post_rev - pre_rev
        rev_delta_pct = ((post_rev - pre_rev) / pre_rev * 100.0) if pre_rev > 0 else 0.0
        rev_direction = "INCREASED" if rev_delta_abs > 0.01 else ("DECREASED" if rev_delta_abs < -0.01 else "UNCHANGED")

        metrics.append(
            MetricComparison(
                metric_name="Total Revenue",
                unit="INR",
                baseline_value=round(pre_rev, 2),
                post_value=round(post_rev, 2),
                delta_absolute=round(rev_delta_abs, 2),
                delta_percentage=round(rev_delta_pct, 1),
                direction=rev_direction,
                observation_statement=(
                    f"Revenue moved from ₹{pre_rev:,.0f} to ₹{post_rev:,.0f} "
                    f"({rev_delta_pct:+.1f}%) during the {window_days}-day symmetric measurement window."
                ),
            )
        )

        # 2. Daily Run-Rate Revenue (especially useful for partial windows)
        pre_days_denom = max(1, window_days)
        post_days_denom = max(1, min(window_days, max(1, elapsed_days)))
        pre_daily_rev = pre_rev / pre_days_denom
        post_daily_rev = post_rev / post_days_denom
        daily_delta_abs = post_daily_rev - pre_daily_rev
        daily_delta_pct = ((post_daily_rev - pre_daily_rev) / pre_daily_rev * 100.0) if pre_daily_rev > 0 else 0.0
        daily_direction = "INCREASED" if daily_delta_abs > 0.01 else ("DECREASED" if daily_delta_abs < -0.01 else "UNCHANGED")

        metrics.append(
            MetricComparison(
                metric_name="Daily Revenue Run-Rate",
                unit="INR/day",
                baseline_value=round(pre_daily_rev, 2),
                post_value=round(post_daily_rev, 2),
                delta_absolute=round(daily_delta_abs, 2),
                delta_percentage=round(daily_delta_pct, 1),
                direction=daily_direction,
                observation_statement=(
                    f"Daily run-rate averaged ₹{pre_daily_rev:,.0f}/day before vs "
                    f"₹{post_daily_rev:,.0f}/day after completion ({daily_delta_pct:+.1f}%)."
                ),
            )
        )

        # 3. Transaction Count
        pre_count = float(len(pre_txs))
        post_count = float(len(post_txs))
        count_delta_abs = post_count - pre_count
        count_delta_pct = ((post_count - pre_count) / pre_count * 100.0) if pre_count > 0 else 0.0
        count_direction = "INCREASED" if count_delta_abs > 0 else ("DECREASED" if count_delta_abs < 0 else "UNCHANGED")

        metrics.append(
            MetricComparison(
                metric_name="Transaction Count",
                unit="Orders",
                baseline_value=pre_count,
                post_value=post_count,
                delta_absolute=count_delta_abs,
                delta_percentage=round(count_delta_pct, 1),
                direction=count_direction,
                observation_statement=(
                    f"Recorded transactions shifted from {int(pre_count)} to {int(post_count)} "
                    f"({count_delta_pct:+.1f}%)."
                ),
            )
        )

        # 4. Unique Active Customers
        pre_customers = {t.customer_name for t in pre_txs if t.customer_name}
        post_customers = {t.customer_name for t in post_txs if t.customer_name}
        pre_cust_count = float(len(pre_customers))
        post_cust_count = float(len(post_customers))
        cust_delta_abs = post_cust_count - pre_cust_count
        cust_delta_pct = ((post_cust_count - pre_cust_count) / pre_cust_count * 100.0) if pre_cust_count > 0 else 0.0
        cust_direction = "INCREASED" if cust_delta_abs > 0 else ("DECREASED" if cust_delta_abs < 0 else "UNCHANGED")

        metrics.append(
            MetricComparison(
                metric_name="Active Customers",
                unit="Customers",
                baseline_value=pre_cust_count,
                post_value=post_cust_count,
                delta_absolute=cust_delta_abs,
                delta_percentage=round(cust_delta_pct, 1),
                direction=cust_direction,
                observation_statement=(
                    f"Active buying customers changed from {int(pre_cust_count)} to {int(post_cust_count)} "
                    f"({cust_delta_pct:+.1f}%)."
                ),
            )
        )

        # 5. Average Order Value (AOV)
        pre_aov = (pre_rev / pre_count) if pre_count > 0 else 0.0
        post_aov = (post_rev / post_count) if post_count > 0 else 0.0
        aov_delta_abs = post_aov - pre_aov
        aov_delta_pct = ((post_aov - pre_aov) / pre_aov * 100.0) if pre_aov > 0 else 0.0
        aov_direction = "INCREASED" if aov_delta_abs > 0.01 else ("DECREASED" if aov_delta_abs < -0.01 else "UNCHANGED")

        metrics.append(
            MetricComparison(
                metric_name="Average Order Value",
                unit="INR/order",
                baseline_value=round(pre_aov, 2),
                post_value=round(post_aov, 2),
                delta_absolute=round(aov_delta_abs, 2),
                delta_percentage=round(aov_delta_pct, 1),
                direction=aov_direction,
                observation_statement=(
                    f"Average order value was ₹{pre_aov:,.0f} pre-completion vs "
                    f"₹{post_aov:,.0f} post-completion ({aov_delta_pct:+.1f}%)."
                ),
            )
        )

        # Mandatory Standardized Causal Disclaimer
        if rev_delta_pct >= 0:
            verb = "increased"
        else:
            verb = "decreased"

        causal_disclaimer = (
            f"Revenue {verb} by {abs(rev_delta_pct):.1f}% during the measurement period "
            f"after this action was completed. This is an observed change, not proof that the action alone caused the {verb}."
        )

        return BeforeAfterMeasurementResponse(
            recommendation_id=recommendation_id,
            title=recommendation_title,
            completed_at=completed_at.isoformat(),
            measurement_window_days=window_days,
            window_status=window_status,
            elapsed_days_since_completion=elapsed_days,
            pre_period_start=pre_period_start.isoformat(),
            pre_period_end=pre_period_end.isoformat(),
            post_period_start=post_period_start.isoformat(),
            post_period_end=post_period_end.isoformat(),
            comparison_methodology=f"symmetric_time_window_{window_days}d",
            data_gaps=data_gaps,
            metrics=metrics,
            causal_disclaimer=causal_disclaimer,
            learning_quality_tier="OBSERVED_CORRELATION",
        )

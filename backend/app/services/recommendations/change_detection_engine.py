"""Business Change Detection Engine (Phase 5 & 6 Proactive Monitoring).

Monitors meaningful shifts across available business data:
  - Statistical revenue anomalies (> 2 standard deviations) & period declines
  - Key customer inactivity (> 30 days beyond normal purchase cycle) & concentration
  - Product velocity deceleration (>= 30% drop in unit run-rate)
  - Demand forecast shifts & forecast staleness
  - Failed or invalid CSV upload detection
  - Health score and digital readiness gaps
  - Stale evidence and returning resolved risks

Applies:
  - Minimum data requirements (filters sparse/new data noise; handles zero variance)
  - Insignificant fluctuation suppression (ignores < 5% normal variance)
  - Transparent deterministic threshold evaluation with explicit event_nature classifications
  - Empty data disclosures (never fabricates false alerts on empty ledgers)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import math
from typing import Any, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.sales import SalesTransaction, SalesUpload
from app.schemas.business_monitoring import (
    EventNature,
    EventSeverity,
    MonitoringEventType,
)
from app.services.recommendations.context_service import UnifiedRecommendationContext


class ChangeDetectionEngine:
    """Detects meaningful changes across verified business metrics."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    def compute_fingerprint(
        self, business_id: int, event_type: str, relevant_entity: Optional[str] = None
    ) -> str:
        """Generate stable deterministic fingerprint for event deduplication."""
        raw = f"{business_id}:{event_type}:{relevant_entity or 'general'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def detect_changes(
        self,
        business: Business,
        now: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Convenience method that builds unified context and scans all changes."""
        from app.services.recommendations.context_service import (
            RecommendationContextService,
        )

        if not self.db:
            return []
        ctx_service = RecommendationContextService(self.db)
        ctx = ctx_service.build_context(business)
        return self.scan_all_changes(business, ctx, now)

    def scan_all_changes(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Run all change detection routines across unified context and recent transactions."""
        if now is None:
            now = datetime.now(timezone.utc)

        detected_events: list[dict[str, Any]] = []

        # 0. Empty Data Guard: Disclose missing ledger without fabricating trend alerts
        if not ctx.sales.has_sales_data:
            detected_events.extend(self._analyze_empty_data(business, ctx))
            # Health and digital readiness can still be evaluated on profile
            detected_events.extend(self._analyze_health_and_readiness(business, ctx))
            detected_events.extend(self._analyze_failed_uploads(business, now))
            return detected_events

        # 1. Historical Transaction Window & Statistical 2-Sigma Analysis
        tx_events = self._analyze_transaction_periods(business, ctx, now)
        detected_events.extend(tx_events)

        # 2. Customer Concentration & Inactivity Shifts (> normal cycle + 30d)
        customer_events = self._analyze_customer_dynamics(business, ctx, now)
        detected_events.extend(customer_events)

        # 3. Product Performance, Momentum & Velocity Deceleration
        product_events = self._analyze_product_performance(business, ctx, now)
        detected_events.extend(product_events)

        # 4. Demand Forecast Changes & Staleness
        forecast_events = self._analyze_demand_forecast(business, ctx, now)
        detected_events.extend(forecast_events)

        # 5. Failed CSV Upload Detection
        upload_events = self._analyze_failed_uploads(business, now)
        detected_events.extend(upload_events)

        # 6. Health Score and Digital Readiness
        health_events = self._analyze_health_and_readiness(business, ctx)
        detected_events.extend(health_events)

        # 7. Recommendation Evidence Freshness & Returning Risks
        lifecycle_events = self._analyze_recommendation_lifecycle_events(business, ctx, now)
        detected_events.extend(lifecycle_events)

        return detected_events

    # ----------------------------------------------------------------------- #
    # 0. Empty Data Guard                                                     #
    # ----------------------------------------------------------------------- #

    def _analyze_empty_data(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
    ) -> list[dict[str, Any]]:
        """Surfaces honest missing data disclosure when transaction ledger is empty."""
        return [
            {
                "event_type": MonitoringEventType.SALES_DATA_MISSING.value,
                "event_nature": EventNature.ASSUMPTION.value,
                "source": "sales_monitoring",
                "relevant_entity": "sales_ledger",
                "severity": EventSeverity.INFORMATIONAL.value,
                "priority_score": 15,
                "data_period": "all_time",
                "evidence": {
                    "total_transactions": 0,
                    "has_sales_data": False,
                    "disclosure": "Proactive revenue anomaly detection, customer dormancy alerts, and velocity tracking require verified transaction data.",
                },
                "title": "Sales Ledger Required to Activate Proactive Alerts",
                "what_changed": "No sales transactions have been uploaded for this business.",
                "why_it_matters": "The platform cannot detect revenue shifts, dormant buyers, or SKU deceleration without transaction history.",
                "suggested_action": "Upload historical sales CSV or connect invoice ledger in the Data Confidence Centre.",
                "confidence": 1.0,
            }
        ]

    # ----------------------------------------------------------------------- #
    # 1. Sales & Revenue Window Analysis (Statistical 2-Sigma + Period Delta)  #
    # ----------------------------------------------------------------------- #

    def _analyze_transaction_periods(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not self.db or not ctx.sales.has_sales_data:
            return events

        # Fetch transactions within last 90 days for statistical baseline
        cutoff_90d = now - timedelta(days=90)
        cutoff_60d = now - timedelta(days=60)
        cutoff_30d = now - timedelta(days=30)

        transactions = (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.transaction_date >= cutoff_90d,
            )
            .order_by(SalesTransaction.transaction_date.asc())
            .all()
        )

        # Minimum data requirement: at least 3 transactions to establish any trend
        if len(transactions) < 3:
            return events

        recent_txs = [
            t
            for t in transactions
            if t.transaction_date
            and (
                t.transaction_date.replace(tzinfo=timezone.utc)
                if t.transaction_date.tzinfo is None
                else t.transaction_date
            )
            >= cutoff_30d
        ]
        prior_txs = [
            t
            for t in transactions
            if t.transaction_date
            and cutoff_60d
            <= (
                t.transaction_date.replace(tzinfo=timezone.utc)
                if t.transaction_date.tzinfo is None
                else t.transaction_date
            )
            < cutoff_30d
        ]

        recent_revenue = sum(float(t.total_amount or 0.0) for t in recent_txs)
        prior_revenue = sum(float(t.total_amount or 0.0) for t in prior_txs)

        # --- A. Statistical Revenue Anomaly (> 2 Standard Deviations) ---
        # Partition 90-day history into 7-day observation buckets prior to recent 30d
        weekly_buckets: list[float] = []
        historical_txs = [
            t
            for t in transactions
            if t.transaction_date
            and (
                t.transaction_date.replace(tzinfo=timezone.utc)
                if t.transaction_date.tzinfo is None
                else t.transaction_date
            )
            < cutoff_30d
        ]

        if historical_txs:
            # Group historical into 7-day buckets starting from earliest tx
            start_date = min(
                t.transaction_date.replace(tzinfo=timezone.utc)
                if t.transaction_date.tzinfo is None
                else t.transaction_date
                for t in historical_txs
            )
            bucket_duration = timedelta(days=7)
            current_bucket_start = start_date

            while current_bucket_start < cutoff_30d:
                bucket_end = current_bucket_start + bucket_duration
                b_txs = [
                    t
                    for t in historical_txs
                    if current_bucket_start
                    <= (
                        t.transaction_date.replace(tzinfo=timezone.utc)
                        if t.transaction_date.tzinfo is None
                        else t.transaction_date
                    )
                    < bucket_end
                ]
                # Only include buckets with confirmed ledger records (do not treat unconfirmed gaps as 0)
                if b_txs:
                    b_rev = sum(float(t.total_amount or 0.0) for t in b_txs)
                    weekly_buckets.append(b_rev)
                current_bucket_start = bucket_end

        # Minimum history for statistical 2-sigma: at least 6 confirmed observation buckets
        if len(weekly_buckets) >= 6:
            mean_bucket_rev = sum(weekly_buckets) / len(weekly_buckets)
            # Sample variance
            variance = sum((x - mean_bucket_rev) ** 2 for x in weekly_buckets) / (
                len(weekly_buckets) - 1
            )
            std_dev = math.sqrt(variance)

            # Convert recent 30-day revenue to average 7-day equivalent for direct scale comparison
            recent_weekly_equiv = recent_revenue / (30.0 / 7.0)

            # Check for zero variance
            if std_dev > 0.0:
                two_sigma_threshold = mean_bucket_rev - (2.0 * std_dev)
                z_score = (recent_weekly_equiv - mean_bucket_rev) / std_dev

                if recent_weekly_equiv < two_sigma_threshold:
                    is_critical = z_score <= -3.0 or recent_revenue <= 0.0
                    sev = EventSeverity.CRITICAL.value if is_critical else EventSeverity.HIGH.value
                    events.append(
                        {
                            "event_type": MonitoringEventType.STATISTICAL_REVENUE_DROP.value,
                            "event_nature": EventNature.ESTIMATE.value,
                            "source": "statistical_anomaly_engine",
                            "relevant_entity": "total_revenue",
                            "severity": sev,
                            "priority_score": 95 if is_critical else 85,
                            "data_period": "recent_30d_vs_6_bucket_baseline",
                            "evidence": {
                                "recent_30d_revenue": round(recent_revenue, 2),
                                "recent_weekly_equivalent": round(recent_weekly_equiv, 2),
                                "baseline_weekly_mean": round(mean_bucket_rev, 2),
                                "baseline_std_dev": round(std_dev, 2),
                                "z_score": round(z_score, 2),
                                "two_sigma_threshold": round(two_sigma_threshold, 2),
                                "historical_bucket_count": len(weekly_buckets),
                            },
                            "title": f"Statistical Revenue Anomaly: {abs(round(z_score, 1))}σ Below Mean",
                            "what_changed": f"Recent weekly-equivalent run-rate (₹{recent_weekly_equiv:,.0f}) has plunged below the 2-standard-deviation threshold (₹{two_sigma_threshold:,.0f}).",
                            "why_it_matters": "A drop exceeding 2 standard deviations signifies a statistically abnormal contraction, not routine business fluctuation.",
                            "suggested_action": "Initiate emergency cash conservation and inspect active buyer pipelines immediately.",
                            "confidence": 0.95,
                        }
                    )

        # --- B. Standard Period-over-Period Revenue Decline / Growth ---
        if prior_revenue > 0.0:
            change_pct = ((recent_revenue - prior_revenue) / prior_revenue) * 100.0

            # Suppress insignificant fluctuation between -5% and +5%
            if abs(change_pct) >= 5.0:
                if change_pct <= -15.0:
                    is_critical = change_pct <= -30.0
                    sev = EventSeverity.CRITICAL.value if is_critical else EventSeverity.HIGH.value
                    events.append(
                        {
                            "event_type": MonitoringEventType.REVENUE_DECLINE_DETECTED.value,
                            "event_nature": EventNature.WARNING.value,
                            "source": "sales_monitoring",
                            "relevant_entity": "total_revenue",
                            "severity": sev,
                            "priority_score": 90 if is_critical else 75,
                            "data_period": "recent_30d_vs_prior_30d",
                            "evidence": {
                                "recent_revenue": round(recent_revenue, 2),
                                "prior_revenue": round(prior_revenue, 2),
                                "change_pct": round(change_pct, 1),
                                "recent_tx_count": len(recent_txs),
                                "prior_tx_count": len(prior_txs),
                            },
                            "title": f"Revenue Decline of {abs(round(change_pct, 1))}% Detected",
                            "what_changed": f"30-day revenue decreased from ₹{prior_revenue:,.2f} to ₹{recent_revenue:,.2f} ({change_pct:.1f}%).",
                            "why_it_matters": "A sustained drop in sales volume directly impairs cash flow and fixed cost coverage.",
                            "suggested_action": "Review top client reorder status and inspect pricing across top volume SKUs.",
                            "confidence": 0.95,
                        }
                    )
                elif change_pct >= 20.0:
                    events.append(
                        {
                            "event_type": MonitoringEventType.REVENUE_GROWTH_SURGE.value,
                            "event_nature": EventNature.CONFIRMED_EVENT.value,
                            "source": "sales_monitoring",
                            "relevant_entity": "total_revenue",
                            "severity": EventSeverity.INFORMATIONAL.value,
                            "priority_score": 30,
                            "data_period": "recent_30d_vs_prior_30d",
                            "evidence": {
                                "recent_revenue": round(recent_revenue, 2),
                                "prior_revenue": round(prior_revenue, 2),
                                "change_pct": round(change_pct, 1),
                            },
                            "title": f"Revenue Accelerated by {round(change_pct, 1)}%",
                            "what_changed": f"Revenue grew from ₹{prior_revenue:,.2f} to ₹{recent_revenue:,.2f} in the past 30 days.",
                            "why_it_matters": "Accelerating revenue presents an opportunity to capture repeat volume and improve gross margins.",
                            "suggested_action": "Secure long-term contracts and maintain working capital buffer for higher fulfillment volume.",
                            "confidence": 0.90,
                        }
                    )

        return events

    # ----------------------------------------------------------------------- #
    # 2. Customer Concentration & Inactivity Dynamics                         #
    # ----------------------------------------------------------------------- #

    def _analyze_customer_dynamics(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.customers.total_customers or not ctx.customers.top_customers_by_revenue:
            return events

        # Customer Concentration Detection
        top_cust_dict = ctx.customers.top_customers_by_revenue[0]
        top_client = top_cust_dict.get("customer_name") or "Primary Customer"
        top_cust_rev = float(
            top_cust_dict.get("revenue") or top_cust_dict.get("total_revenue") or 0.0
        )
        tot_rev = ctx.sales.total_revenue or 1.0
        top_share = (top_cust_rev / tot_rev) * 100.0

        if top_share >= 40.0 and top_client:
            is_critical = top_share >= 50.0
            sev = EventSeverity.CRITICAL.value if is_critical else EventSeverity.HIGH.value
            events.append(
                {
                    "event_type": MonitoringEventType.CUSTOMER_CONCENTRATION_INCREASED.value,
                    "event_nature": EventNature.WARNING.value,
                    "source": "customer_analytics",
                    "relevant_entity": top_client,
                    "severity": sev,
                    "priority_score": 95 if is_critical else 75,
                    "data_period": "historical_sales_aggregate",
                    "evidence": {
                        "top_customer": top_client,
                        "top_customer_share_pct": round(top_share, 1),
                        "total_customers": ctx.customers.total_customers,
                    },
                    "title": f"High Customer Concentration: {round(top_share, 1)}% in {top_client}",
                    "what_changed": f"{top_client} accounts for {top_share:.1f}% of total business revenue.",
                    "why_it_matters": "A loss or delay in payment from this single buyer would severely disrupt business solvency.",
                    "suggested_action": "Diversify client base into adjacent industrial or B2B buyer segments immediately.",
                    "confidence": 0.95,
                }
            )

        # Key Customer Inactivity (> normal purchase cycle + 30 days)
        if self.db:
            all_txs = (
                self.db.query(SalesTransaction)
                .filter(SalesTransaction.business_id == business.id)
                .order_by(SalesTransaction.transaction_date.asc())
                .all()
            )
            # Group by customer name
            cust_txs: dict[str, list[SalesTransaction]] = {}
            for t in all_txs:
                cname = (t.customer_name or "").strip()
                if cname:
                    cust_txs.setdefault(cname, []).append(t)

            for cname, tx_list in cust_txs.items():
                # Minimum history requirement: at least 3 transactions to establish cycle
                if len(tx_list) >= 3:
                    dates = [
                        (
                            t.transaction_date.replace(tzinfo=timezone.utc)
                            if t.transaction_date.tzinfo is None
                            else t.transaction_date
                        )
                        for t in tx_list
                        if t.transaction_date
                    ]
                    dates.sort()
                    first_dt, last_dt = dates[0], dates[-1]
                    span_days = max(1, (last_dt - first_dt).days)
                    # Average gap between orders
                    normal_cycle_days = max(1, int(span_days / (len(dates) - 1)))

                    days_since_last = (now - last_dt).days
                    inactivity_threshold = normal_cycle_days + 30

                    if days_since_last > inactivity_threshold:
                        cust_total_rev = sum(float(t.total_amount or 0.0) for t in tx_list)
                        cust_share = (
                            (cust_total_rev / tot_rev) * 100.0 if tot_rev > 0 else 0.0
                        )

                        is_critical = cust_share >= 25.0
                        sev = (
                            EventSeverity.CRITICAL.value
                            if is_critical
                            else EventSeverity.HIGH.value
                        )

                        events.append(
                            {
                                "event_type": MonitoringEventType.CUSTOMER_INACTIVITY_DETECTED.value,
                                "event_nature": EventNature.CONFIRMED_EVENT.value,
                                "source": "customer_inactivity_tracker",
                                "relevant_entity": cname,
                                "severity": sev,
                                "priority_score": 90 if is_critical else 75,
                                "data_period": f"{days_since_last}d_since_last_order",
                                "evidence": {
                                    "customer_name": cname,
                                    "normal_cycle_days": normal_cycle_days,
                                    "days_since_last_order": days_since_last,
                                    "inactivity_threshold_days": inactivity_threshold,
                                    "historical_orders_count": len(tx_list),
                                    "total_customer_spend": round(cust_total_rev, 2),
                                    "revenue_share_pct": round(cust_share, 1),
                                },
                                "title": f"Key Customer Inactive: {cname} ({days_since_last} Days Silent)",
                                "what_changed": f"{cname} normally re-orders every {normal_cycle_days} days, but has been silent for {days_since_last} days (> normal cycle + 30 days).",
                                "why_it_matters": "Prolonged inactivity from an established purchasing account indicates churn risk or defection to competitors.",
                                "suggested_action": "Reach out directly with a personalized relationship check and review recent delivery quality.",
                                "confidence": 0.95,
                            }
                        )

        # Repeat Purchase Behavior
        repeat_rate = ctx.customers.repeat_rate_pct or 0.0
        if repeat_rate >= 50.0:
            events.append(
                {
                    "event_type": MonitoringEventType.REPEAT_PURCHASE_IMPROVED.value,
                    "event_nature": EventNature.CONFIRMED_EVENT.value,
                    "source": "customer_analytics",
                    "relevant_entity": "repeat_customers",
                    "severity": EventSeverity.LOW.value,
                    "priority_score": 25,
                    "data_period": "historical_sales_aggregate",
                    "evidence": {
                        "repeat_rate": round(repeat_rate, 1),
                        "repeat_customer_count": ctx.customers.repeat_customers,
                    },
                    "title": f"Strong Repeat Customer Retention ({round(repeat_rate, 1)}%)",
                    "what_changed": f"Repeat customers represent {repeat_rate:.1f}% of active purchasing accounts.",
                    "why_it_matters": "High customer retention lowers customer acquisition costs and stabilizes baseline cash flows.",
                    "suggested_action": "Introduce structured loyalty incentives or recurring supply agreements.",
                    "confidence": 0.88,
                }
            )

        return events

    # ----------------------------------------------------------------------- #
    # 3. Product Performance, Momentum & Velocity Deceleration               #
    # ----------------------------------------------------------------------- #

    def _analyze_product_performance(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.products.top_products_by_revenue or not ctx.sales.total_revenue:
            return events

        # Top product revenue concentration
        top_prod = ctx.products.top_products_by_revenue[0]
        prod_name = top_prod.get("product_name", "Top Product")
        prod_rev = float(
            top_prod.get("revenue") or top_prod.get("total_revenue") or 0.0
        )
        tot_rev = ctx.sales.total_revenue or 1.0
        prod_share = (prod_rev / tot_rev) * 100.0

        if prod_share >= 45.0:
            events.append(
                {
                    "event_type": MonitoringEventType.PRODUCT_MOMENTUM_SURGE.value,
                    "event_nature": EventNature.WARNING.value,
                    "source": "product_analytics",
                    "relevant_entity": prod_name,
                    "severity": EventSeverity.MEDIUM.value,
                    "priority_score": 50,
                    "data_period": "portfolio_overview",
                    "evidence": {
                        "product_name": prod_name,
                        "revenue_share_pct": round(prod_share, 1),
                        "total_revenue": prod_rev,
                    },
                    "title": f"Portfolio Dependency on {prod_name} ({round(prod_share, 1)}%)",
                    "what_changed": f"{prod_name} contributes {prod_share:.1f}% of all product sales revenue.",
                    "why_it_matters": "High reliance on a single SKU exposes the business to component cost or supplier disruptions.",
                    "suggested_action": "Promote complementary catalog products and expand secondary product offerings.",
                    "confidence": 0.85,
                }
            )

        # Product Velocity Deceleration (Units Sold: Recent 30d vs Prior 30d)
        if self.db:
            cutoff_60d = now - timedelta(days=60)
            cutoff_30d = now - timedelta(days=30)

            txs_60d = (
                self.db.query(SalesTransaction)
                .filter(
                    SalesTransaction.business_id == business.id,
                    SalesTransaction.transaction_date >= cutoff_60d,
                )
                .all()
            )

            # Group unit volumes by product
            product_units_prior: dict[str, float] = {}
            product_units_recent: dict[str, float] = {}

            for t in txs_60d:
                pname = (t.product_name or "").strip()
                if not pname:
                    continue
                dt = (
                    t.transaction_date.replace(tzinfo=timezone.utc)
                    if t.transaction_date and t.transaction_date.tzinfo is None
                    else t.transaction_date
                )
                qty = float(t.quantity or 0.0)

                if dt and dt >= cutoff_30d:
                    product_units_recent[pname] = product_units_recent.get(pname, 0.0) + qty
                elif dt and dt < cutoff_30d:
                    product_units_prior[pname] = product_units_prior.get(pname, 0.0) + qty

            for pname, prior_qty in product_units_prior.items():
                # Minimum baseline requirement: at least 5 units sold in prior period
                if prior_qty >= 5.0:
                    recent_qty = product_units_recent.get(pname, 0.0)
                    velocity_delta_pct = ((recent_qty - prior_qty) / prior_qty) * 100.0

                    if velocity_delta_pct <= -30.0:
                        is_critical = velocity_delta_pct <= -50.0
                        sev = (
                            EventSeverity.HIGH.value
                            if is_critical
                            else EventSeverity.MEDIUM.value
                        )

                        events.append(
                            {
                                "event_type": MonitoringEventType.PRODUCT_VELOCITY_DECELERATION.value,
                                "event_nature": EventNature.CONFIRMED_EVENT.value,
                                "source": "product_velocity_engine",
                                "relevant_entity": pname,
                                "severity": sev,
                                "priority_score": 80 if is_critical else 65,
                                "data_period": "recent_30d_vs_prior_30d",
                                "evidence": {
                                    "product_name": pname,
                                    "prior_30d_units": round(prior_qty, 1),
                                    "recent_30d_units": round(recent_qty, 1),
                                    "velocity_delta_pct": round(velocity_delta_pct, 1),
                                    "units_dropped": round(prior_qty - recent_qty, 1),
                                    "inventory_disclosure": "UrsBiz does not track warehouse inventory balances, safety stock, or lead times; deceleration reflects recorded sales volume only.",
                                },
                                "title": f"Product Velocity Deceleration: {pname} ({round(velocity_delta_pct, 1)}%)",
                                "what_changed": f"Unit sales velocity for {pname} declined by {abs(round(velocity_delta_pct, 1))}% ({prior_qty:.0f} to {recent_qty:.0f} units).",
                                "why_it_matters": "Sharp velocity drop indicates potential market share loss, seasonal slump, or buyer fatigue.",
                                "suggested_action": "Evaluate SKU pricing competitiveness and run targeted outreach to past buyers of this product.",
                                "confidence": 0.90,
                            }
                        )

        return events

    # ----------------------------------------------------------------------- #
    # 4. Demand Forecast Changes & Staleness                                  #
    # ----------------------------------------------------------------------- #

    def _analyze_demand_forecast(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return events

        # Check for Forecast Staleness (> 30 days since latest transaction date used in forecast)
        if ctx.sales.has_sales_data and ctx.sales.latest_transaction_date:
            try:
                raw_dt = ctx.sales.latest_transaction_date.replace("Z", "+00:00")
                latest_tx_dt = datetime.fromisoformat(raw_dt)
                if latest_tx_dt.tzinfo is None:
                    latest_tx_dt = latest_tx_dt.replace(tzinfo=timezone.utc)
                now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
                forecast_age_days = (now_utc - latest_tx_dt).days

                if forecast_age_days > 30:
                    events.append(
                        {
                            "event_type": MonitoringEventType.STALE_FORECAST.value,
                            "event_nature": EventNature.WARNING.value,
                            "source": "demand_forecasting",
                            "relevant_entity": "demand_models",
                            "severity": EventSeverity.MEDIUM.value,
                            "priority_score": 60,
                            "data_period": f"{forecast_age_days}d_since_refresh",
                            "evidence": {
                                "latest_transaction_date": ctx.sales.latest_transaction_date,
                                "forecast_age_days": forecast_age_days,
                                "stale_threshold_days": 30,
                            },
                            "title": f"Demand Forecast Requires Refresh ({forecast_age_days} Days Old)",
                            "what_changed": f"Current demand forecasting models are based on sales data that is {forecast_age_days} days old.",
                            "why_it_matters": "Forward demand projections become unreliable when recent transaction shifts are not incorporated.",
                            "suggested_action": "Upload fresh sales transactions in the Data Confidence Centre to trigger automated model re-training.",
                            "confidence": 0.95,
                        }
                    )
            except Exception:
                pass

        # Existing trend alerts
        for pf in ctx.forecast.product_forecasts:
            trend = pf.demand_trend.lower()
            prod_name = pf.product_name
            if "growth" in trend or "upward" in trend:
                events.append(
                    {
                        "event_type": MonitoringEventType.DEMAND_FORECAST_CHANGED.value,
                        "event_nature": EventNature.ESTIMATE.value,
                        "source": "demand_forecasting",
                        "relevant_entity": prod_name,
                        "severity": EventSeverity.INFORMATIONAL.value,
                        "priority_score": 35,
                        "data_period": "next_30_to_90_days",
                        "evidence": {
                            "product_name": prod_name,
                            "projected_trend": pf.demand_trend,
                            "trend_delta_pct": pf.trend_delta_pct,
                            "reliability": pf.reliability,
                            "inventory_disclosure": "UrsBiz does not track warehouse inventory balances, safety stock, or lead times; alerts reflect forward demand run-rates only.",
                        },
                        "title": f"Demand Growth Alert: {prod_name} ({pf.demand_trend})",
                        "what_changed": f"Statistical forecast indicates an upward demand trajectory for {prod_name}.",
                        "why_it_matters": "Anticipating demand increases enables advance production scheduling without overextending capital.",
                        "suggested_action": "Review forward planning and scheduling for projected demand; note that inventory balances are not tracked.",
                        "confidence": 0.85,
                    }
                )
            elif "decline" in trend or "downward" in trend:
                events.append(
                    {
                        "event_type": MonitoringEventType.DEMAND_FORECAST_CHANGED.value,
                        "event_nature": EventNature.ESTIMATE.value,
                        "source": "demand_forecasting",
                        "relevant_entity": prod_name,
                        "severity": EventSeverity.HIGH.value,
                        "priority_score": 70,
                        "data_period": "next_30_to_90_days",
                        "evidence": {
                            "product_name": prod_name,
                            "projected_trend": pf.demand_trend,
                            "trend_delta_pct": pf.trend_delta_pct,
                            "reliability": pf.reliability,
                            "inventory_disclosure": "UrsBiz does not track warehouse inventory balances, safety stock, or lead times; alerts reflect forward demand run-rates only.",
                        },
                        "title": f"Projected Demand Contraction: {prod_name} ({pf.demand_trend})",
                        "what_changed": f"Statistical projection anticipates downward demand for {prod_name}.",
                        "why_it_matters": "Lower forward demand requires lean operating expenses and tight working capital controls.",
                        "suggested_action": "Review operational planning commitments and align forward schedules with projected run-rate.",
                        "confidence": 0.85,
                    }
                )

        return events

    # ----------------------------------------------------------------------- #
    # 5. Failed CSV Upload Detection                                          #
    # ----------------------------------------------------------------------- #

    def _analyze_failed_uploads(
        self,
        business: Business,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not self.db:
            return events

        recent_uploads = (
            self.db.query(SalesUpload)
            .filter(
                SalesUpload.business_id == business.id,
            )
            .order_by(desc(SalesUpload.created_at))
            .limit(20)
            .all()
        )

        now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        for up in recent_uploads:
            if up.created_at:
                created_dt = (
                    up.created_at.replace(tzinfo=timezone.utc)
                    if up.created_at.tzinfo is None
                    else up.created_at
                )
                if (now_utc - created_dt).days > 30:
                    continue

            # Check for failed status or completely invalid row imports
            is_failed = (
                up.status in ["failed", "error"]
                or (up.invalid_row_count > 0 and up.valid_row_count == 0)
                or (up.error_message is not None and up.status != "confirmed")
            )

            if is_failed:
                sev = (
                    EventSeverity.HIGH.value
                    if up.valid_row_count == 0
                    else EventSeverity.MEDIUM.value
                )
                events.append(
                    {
                        "event_type": MonitoringEventType.CSV_UPLOAD_FAILED.value,
                        "event_nature": EventNature.CONFIRMED_EVENT.value,
                        "source": "upload_system",
                        "relevant_entity": up.filename,
                        "severity": sev,
                        "priority_score": 85 if sev == EventSeverity.HIGH.value else 65,
                        "data_period": "recent_upload",
                        "evidence": {
                            "upload_id": up.id,
                            "filename": up.filename,
                            "status": up.status,
                            "row_count": up.row_count,
                            "invalid_row_count": up.invalid_row_count,
                            "error_message": up.error_message,
                            "uploaded_at": up.created_at.isoformat()
                            if up.created_at
                            else None,
                        },
                        "title": f"Sales Data Upload Failed: {up.filename}",
                        "what_changed": f"File '{up.filename}' encountered errors during upload: {up.error_message or 'Invalid row formatting'}.",
                        "why_it_matters": "Failed data uploads prevent business intelligence models from reflecting recent transactions.",
                        "suggested_action": "Inspect column mappings and correct formatting errors in the Data Confidence Centre.",
                        "confidence": 1.0,
                    }
                )

        return events

    # ----------------------------------------------------------------------- #
    # 6. Health Score and Readiness                                           #
    # ----------------------------------------------------------------------- #

    def _analyze_health_and_readiness(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # Health score evaluation
        health_score = ctx.health.overall_score
        if health_score is not None:
            if health_score < 50:
                events.append(
                    {
                        "event_type": MonitoringEventType.HEALTH_SCORE_DECLINED.value,
                        "event_nature": EventNature.WARNING.value,
                        "source": "health_engine",
                        "relevant_entity": "business_health_score",
                        "severity": EventSeverity.HIGH.value,
                        "priority_score": 80,
                        "data_period": "current_evaluation",
                        "evidence": {
                            "health_score": health_score,
                            "grade": ctx.health.grade,
                        },
                        "title": f"Business Health Index Alert (Score: {health_score}/100, Grade: {ctx.health.grade})",
                        "what_changed": f"Current overall health score is {health_score}/100 (Grade {ctx.health.grade}).",
                        "why_it_matters": "A composite score below 50 indicates multiple operational, financial, or data vulnerabilities.",
                        "suggested_action": "Address foundational data completeness and resolve core cash flow bottlenecks.",
                        "confidence": 0.90,
                    }
                )
            elif health_score >= 80:
                events.append(
                    {
                        "event_type": MonitoringEventType.HEALTH_SCORE_IMPROVED.value,
                        "event_nature": EventNature.CONFIRMED_EVENT.value,
                        "source": "health_engine",
                        "relevant_entity": "business_health_score",
                        "severity": EventSeverity.INFORMATIONAL.value,
                        "priority_score": 20,
                        "data_period": "current_evaluation",
                        "evidence": {
                            "health_score": health_score,
                            "grade": ctx.health.grade,
                        },
                        "title": f"Healthy Business Operations (Score: {health_score}/100)",
                        "what_changed": f"Composite business health is strong at {health_score}/100 (Grade {ctx.health.grade}).",
                        "why_it_matters": "High operational health qualifies the business for expansion schemes and credit access.",
                        "suggested_action": "Explore government capital subsidy schemes (e.g. CGTMSE / PMEGP) to accelerate scale.",
                        "confidence": 0.90,
                    }
                )

        # Critical Readiness Gaps (Digital Presence)
        if not ctx.profile.has_website and not ctx.profile.has_ecommerce:
            events.append(
                {
                    "event_type": MonitoringEventType.CRITICAL_READINESS_GAP_DETECTED.value,
                    "event_nature": EventNature.WARNING.value,
                    "source": "compliance_monitoring",
                    "relevant_entity": "digital_presence",
                    "severity": EventSeverity.MEDIUM.value,
                    "priority_score": 60,
                    "data_period": "profile_assessment",
                    "evidence": {"has_website": False, "has_ecommerce": False},
                    "title": "Digital Market Channels Not Established",
                    "what_changed": "Business does not have an active website or e-commerce channel.",
                    "why_it_matters": "Lack of digital discoverability limits customer acquisition beyond local geography.",
                    "suggested_action": "Set up a lightweight verified digital presence to expand client reach.",
                    "confidence": 1.0,
                }
            )

        return events

    # ----------------------------------------------------------------------- #
    # 7. Recommendation Evidence Freshness & Returning Risks                  #
    # ----------------------------------------------------------------------- #

    def _analyze_recommendation_lifecycle_events(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # Check evidence freshness
        if ctx.sales.has_sales_data and ctx.sales.latest_transaction_date:
            try:
                raw_dt = ctx.sales.latest_transaction_date.replace("Z", "+00:00")
                latest_dt = datetime.fromisoformat(raw_dt)
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                now_utc = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
                days_old = (now_utc - latest_dt).days
                if days_old >= 30:
                    events.append(
                        {
                            "event_type": MonitoringEventType.RECOMMENDATION_EVIDENCE_STALE.value,
                            "event_nature": EventNature.ASSUMPTION.value,
                            "source": "provenance_engine",
                            "relevant_entity": "sales_ledger",
                            "severity": EventSeverity.MEDIUM.value,
                            "priority_score": 55,
                            "data_period": "latest_sales_date",
                            "evidence": {
                                "latest_transaction_date": ctx.sales.latest_transaction_date,
                                "days_since_update": days_old,
                            },
                            "title": f"Sales Data Requires Refresh ({days_old} Days Old)",
                            "what_changed": f"The most recent transaction recorded was {days_old} days ago.",
                            "why_it_matters": "Recommendations relying on sales figures may not reflect recent market dynamics.",
                            "suggested_action": "Upload an updated monthly sales ledger to ensure verified recommendations.",
                            "confidence": 1.0,
                        }
                    )
            except Exception:
                pass

        # Check completed recommendations: Has a resolved risk reappeared?
        completed_recs = getattr(ctx, "completed_recommendations", [])
        top_share = 0.0
        if ctx.customers.top_customers_by_revenue and ctx.sales.total_revenue > 0:
            top_rev = float(
                ctx.customers.top_customers_by_revenue[0].get("revenue")
                or ctx.customers.top_customers_by_revenue[0].get("total_revenue")
                or 0.0
            )
            top_share = (top_rev / ctx.sales.total_revenue) * 100.0

        for rec in completed_recs:
            rec_id = rec.get("recommendation_id", "")
            # If a customer concentration recommendation was completed, but concentration is now >= 45%
            if "cust_concentration" in rec_id and top_share >= 45.0:
                events.append(
                    {
                        "event_type": MonitoringEventType.RESOLVED_RISK_REAPPEARED.value,
                        "event_nature": EventNature.WARNING.value,
                        "source": "closed_loop_monitor",
                        "relevant_entity": rec_id,
                        "severity": EventSeverity.HIGH.value,
                        "priority_score": 85,
                        "data_period": "continuous_monitoring",
                        "evidence": {
                            "recommendation_id": rec_id,
                            "current_top_share": round(top_share, 1),
                            "status_previously": "Completed",
                        },
                        "title": f"Previously Resolved Risk Reappeared: Customer Concentration ({round(top_share, 1)}%)",
                        "what_changed": f"Customer concentration was resolved previously, but has climbed back to {top_share:.1f}%.",
                        "why_it_matters": "Re-emergence of high client concentration re-introduces revenue volatility risk.",
                        "suggested_action": "Re-activate diversification efforts with target accounts in new sectors.",
                        "confidence": 0.95,
                    }
                )

        return events

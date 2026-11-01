"""Business Change Detection Engine (Phase 5 Proactive Monitoring).

Monitors meaningful shifts across available business data:
  - Revenue trends and sales velocity (Period A vs Period B)
  - Customer concentration, churn risk, and purchase frequency
  - Product performance and SKU momentum
  - Demand forecast shifts
  - Health score and digital readiness gaps
  - Stale evidence and returning resolved risks

Applies:
  - Minimum data requirements (filters sparse/new data noise)
  - Insignificant fluctuation suppression (ignores < 5% normal variance)
  - Transparent deterministic threshold evaluation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.schemas.business_monitoring import (
    BusinessSignalItem,
    EventSeverity,
    MonitoringEventType,
)
from app.services.recommendations.context_service import UnifiedRecommendationContext


class ChangeDetectionEngine:
    """Detects meaningful changes across verified business metrics."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    def compute_fingerprint(self, business_id: int, event_type: str, relevant_entity: Optional[str] = None) -> str:
        """Generate stable deterministic fingerprint for event deduplication."""
        raw = f"{business_id}:{event_type}:{relevant_entity or 'general'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

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

        # 1. Historical Transaction Window Analysis (Recent 30d vs Prior 30d)
        tx_events = self._analyze_transaction_periods(business, ctx, now)
        detected_events.extend(tx_events)

        # 2. Customer Concentration & Inactivity Shifts
        customer_events = self._analyze_customer_dynamics(business, ctx)
        detected_events.extend(customer_events)

        # 3. Product Performance & Momentum
        product_events = self._analyze_product_performance(business, ctx)
        detected_events.extend(product_events)

        # 4. Demand Forecast Changes
        forecast_events = self._analyze_demand_forecast(business, ctx)
        detected_events.extend(forecast_events)

        # 5. Health Score and Readiness
        health_events = self._analyze_health_and_readiness(business, ctx)
        detected_events.extend(health_events)

        # 6. Recommendation Evidence Freshness & Returning Risks
        lifecycle_events = self._analyze_recommendation_lifecycle_events(business, ctx, now)
        detected_events.extend(lifecycle_events)

        return detected_events

    # ----------------------------------------------------------------------- #
    # 1. Sales & Revenue Window Analysis                                      #
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

        # Fetch transactions within last 60 days
        cutoff_60d = now - timedelta(days=60)
        cutoff_30d = now - timedelta(days=30)

        transactions = (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.transaction_date >= cutoff_60d,
            )
            .all()
        )

        # Minimum data requirement: at least 3 transactions to establish trend
        if len(transactions) < 3:
            return events

        recent_txs = [t for t in transactions if t.transaction_date and (t.transaction_date.replace(tzinfo=timezone.utc) if t.transaction_date.tzinfo is None else t.transaction_date) >= cutoff_30d]
        prior_txs = [t for t in transactions if t.transaction_date and (t.transaction_date.replace(tzinfo=timezone.utc) if t.transaction_date.tzinfo is None else t.transaction_date) < cutoff_30d]

        # Require prior period baseline to detect change
        if not prior_txs or not recent_txs:
            return events

        recent_revenue = sum(float(t.total_amount or 0.0) for t in recent_txs)
        prior_revenue = sum(float(t.total_amount or 0.0) for t in prior_txs)

        if prior_revenue <= 0.0:
            return events

        change_pct = ((recent_revenue - prior_revenue) / prior_revenue) * 100.0

        # Insignificant fluctuation suppression: Ignore changes between -5% and +5%
        if abs(change_pct) < 5.0:
            return events

        # Significant Revenue Decline
        if change_pct <= -15.0:
            is_critical = change_pct <= -30.0
            sev = EventSeverity.CRITICAL.value if is_critical else EventSeverity.HIGH.value
            priority = 90 if is_critical else 75

            events.append({
                "event_type": MonitoringEventType.REVENUE_DECLINE_DETECTED.value,
                "source": "sales_monitoring",
                "relevant_entity": "total_revenue",
                "severity": sev,
                "priority_score": priority,
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
            })

        # Significant Revenue Growth Surge
        elif change_pct >= 20.0:
            events.append({
                "event_type": MonitoringEventType.REVENUE_GROWTH_SURGE.value,
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
            })

        return events

    # ----------------------------------------------------------------------- #
    # 2. Customer Concentration & Inactivity Dynamics                         #
    # ----------------------------------------------------------------------- #

    def _analyze_customer_dynamics(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.customers.total_customers or not ctx.customers.top_customers_by_revenue:
            return events

        # Customer Concentration Detection
        top_cust_dict = ctx.customers.top_customers_by_revenue[0]
        top_client = top_cust_dict.get("customer_name") or "Primary Customer"
        top_cust_rev = float(top_cust_dict.get("revenue") or top_cust_dict.get("total_revenue") or 0.0)
        tot_rev = ctx.sales.total_revenue or 1.0
        top_share = (top_cust_rev / tot_rev) * 100.0

        if top_share >= 40.0 and top_client:
            is_critical = top_share >= 50.0
            sev = EventSeverity.CRITICAL.value if is_critical else EventSeverity.HIGH.value
            priority = 95 if is_critical else 75

            events.append({
                "event_type": MonitoringEventType.CUSTOMER_CONCENTRATION_INCREASED.value,
                "source": "customer_analytics",
                "relevant_entity": top_client,
                "severity": sev,
                "priority_score": priority,
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
            })

        # Repeat Purchase Behavior
        repeat_rate = ctx.customers.repeat_rate_pct or 0.0
        if repeat_rate >= 50.0:
            events.append({
                "event_type": MonitoringEventType.REPEAT_PURCHASE_IMPROVED.value,
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
            })

        return events

    # ----------------------------------------------------------------------- #
    # 3. Product Performance & Momentum                                       #
    # ----------------------------------------------------------------------- #

    def _analyze_product_performance(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.products.top_products_by_revenue or not ctx.sales.total_revenue:
            return events

        top_prod = ctx.products.top_products_by_revenue[0]
        prod_name = top_prod.get("product_name", "Top Product")
        prod_rev = float(top_prod.get("revenue") or top_prod.get("total_revenue") or 0.0)
        tot_rev = ctx.sales.total_revenue or 1.0
        prod_share = (prod_rev / tot_rev) * 100.0

        # Top product revenue concentration / dominance
        if prod_share >= 45.0:
            events.append({
                "event_type": MonitoringEventType.PRODUCT_MOMENTUM_SURGE.value,
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
            })

        return events

    # ----------------------------------------------------------------------- #
    # 4. Demand Forecast Changes                                              #
    # ----------------------------------------------------------------------- #

    def _analyze_demand_forecast(
        self,
        business: Business,
        ctx: UnifiedRecommendationContext,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return events

        for pf in ctx.forecast.product_forecasts:
            trend = pf.demand_trend.lower()
            prod_name = pf.product_name
            if "growth" in trend or "upward" in trend:
                events.append({
                    "event_type": MonitoringEventType.DEMAND_FORECAST_CHANGED.value,
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
                    },
                    "title": f"Positive Demand Forecast Trend: {prod_name} ({pf.demand_trend})",
                    "what_changed": f"Statistical forecast indicates an upward demand trajectory for {prod_name}.",
                    "why_it_matters": "Anticipating demand increases enables advance production scheduling without overextending capital.",
                    "suggested_action": "Align raw material supplier lead times to projected order volumes.",
                    "confidence": 0.85,
                })
            elif "decline" in trend or "downward" in trend:
                events.append({
                    "event_type": MonitoringEventType.DEMAND_FORECAST_CHANGED.value,
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
                    },
                    "title": f"Projected Demand Contraction: {prod_name} ({pf.demand_trend})",
                    "what_changed": f"Statistical projection anticipates downward demand for {prod_name}.",
                    "why_it_matters": "Lower forward demand requires lean operating expenses and tight working capital controls.",
                    "suggested_action": "Review procurement commitments and avoid excess raw material accumulation.",
                    "confidence": 0.85,
                })

        return events

    # ----------------------------------------------------------------------- #
    # 5. Health Score and Readiness                                           #
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
                events.append({
                    "event_type": MonitoringEventType.HEALTH_SCORE_DECLINED.value,
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
                })
            elif health_score >= 80:
                events.append({
                    "event_type": MonitoringEventType.HEALTH_SCORE_IMPROVED.value,
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
                })

        # Critical Readiness Gaps (Digital Presence)
        if not ctx.profile.has_website and not ctx.profile.has_ecommerce:
            events.append({
                "event_type": MonitoringEventType.CRITICAL_READINESS_GAP_DETECTED.value,
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
            })

        return events

    # ----------------------------------------------------------------------- #
    # 6. Recommendation Evidence Freshness & Returning Risks                  #
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
                if days_old >= 45:
                    events.append({
                        "event_type": MonitoringEventType.RECOMMENDATION_EVIDENCE_STALE.value,
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
                    })
            except Exception:
                pass

        # Check completed recommendations: Has a resolved risk reappeared?
        completed_recs = getattr(ctx, "completed_recommendations", [])
        top_share = 0.0
        if ctx.customers.top_customers_by_revenue and ctx.sales.total_revenue > 0:
            top_rev = float(ctx.customers.top_customers_by_revenue[0].get("revenue") or ctx.customers.top_customers_by_revenue[0].get("total_revenue") or 0.0)
            top_share = (top_rev / ctx.sales.total_revenue) * 100.0

        for rec in completed_recs:
            rec_id = rec.get("recommendation_id", "")
            # If a customer concentration recommendation was completed, but concentration is now >= 45%
            if "cust_concentration" in rec_id and top_share >= 45.0:
                events.append({
                    "event_type": MonitoringEventType.RESOLVED_RISK_REAPPEARED.value,
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
                })

        return events

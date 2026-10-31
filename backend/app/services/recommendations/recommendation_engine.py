"""Context-Aware Business Recommendation Engine (Phase 5).

Consolidates verified business context from:
  1. Business Digital Twin & Profile
  2. Health Score Engine
  3. Sales Intelligence (Transactions, Customers, Products, Trends)
  4. Demand Forecasting & Predictive Intelligence
  5. Government Schemes Catalog

Applies a deterministic multi-factor prioritization formula across 10 official categories.
Persists and tracks recommendation lifecycle states.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.repositories.business_repository import BusinessRepository
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.repositories.sales_repository import SalesRepository
from app.schemas.forecasting import ForecastIntervalEnum
from app.schemas.smart_recommendations import (
    ActionPlan,
    ActionStep,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
    SmartRecommendationsResponse,
)
from app.services.forecasting.forecast_engine import generate_demand_overview
from app.services.health_score_service import HealthScoreService
from app.services.schemes_sprint16_service import SchemeRecommendationEngine

logger = logging.getLogger(__name__)


class SmartRecommendationEngine:
    """Core recommendation generation and deterministic prioritization engine."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales_repo = SalesRepository(db)
        self.lifecycle_repo = RecommendationLifecycleRepository(db)
        self.schemes_service = SchemeRecommendationEngine(BusinessRepository(db))

    def generate_recommendations(
        self,
        business: Business,
        category_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> SmartRecommendationsResponse:
        """Generate context-grounded recommendations for a business with lifecycle state tracking."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # ---------------------------------------------------------------------
        # 1. Gather Verified Subsystem Context
        # ---------------------------------------------------------------------
        # Health Score
        try:
            health_report = HealthScoreService.compute(business)
            health_score = health_report.score
            missing_fields = health_report.missing_fields or []
        except Exception as e:
            logger.warning(f"Error computing health score: {e}")
            health_score = 50
            missing_fields = []

        # Sales Intelligence
        sales_summary = None
        customer_insights = None
        product_insights = None
        has_sales_data = False
        try:
            sales_summary = self.sales_repo.get_sales_summary(business.id)
            if sales_summary and sales_summary.get("total_transactions", 0) > 0:
                has_sales_data = True
                customer_insights = self.sales_repo.get_customer_insights(business.id)
                product_insights = self.sales_repo.get_product_insights(business.id)
        except Exception as e:
            logger.warning(f"Error fetching sales intelligence: {e}")

        # Demand Forecasting
        forecast_overview = None
        has_forecast_data = False
        if has_sales_data:
            try:
                txns = (
                    self.db.query(SalesTransaction)
                    .filter(
                        SalesTransaction.business_id == business.id,
                        SalesTransaction.is_duplicate.is_(False),
                    )
                    .order_by(SalesTransaction.transaction_date.asc())
                    .all()
                )
                if txns:
                    forecast_overview = generate_demand_overview(
                        txns, interval=ForecastIntervalEnum.MONTHLY, horizon=3
                    )
                    if forecast_overview and forecast_overview.product_summaries:
                        has_forecast_data = True
            except Exception as e:
                logger.warning(f"Error generating forecast overview: {e}")

        # Government Schemes
        matching_schemes = []
        try:
            schemes_res = self.schemes_service.recommend_schemes(business)
            matching_schemes = (schemes_res.recommended or []) + (schemes_res.eligible or [])
        except Exception as e:
            logger.warning(f"Error fetching government schemes: {e}")

        # ---------------------------------------------------------------------
        # 2. Rule Evaluation Across 10 Categories
        # ---------------------------------------------------------------------
        raw_candidates: list[dict[str, Any]] = []

        # Category 1: Revenue Growth
        if has_sales_data and customer_insights and sales_summary:
            top_by_rev = customer_insights.get("top_customers_by_revenue", [])
            tot_rev = sales_summary.get("total_revenue", 0.0)
            tot_tx = sales_summary.get("total_transactions", 0)
            tot_cust = customer_insights.get("total_customers", 0)
            if top_by_rev and tot_rev > 0:
                top_3_rev = sum(c.get("total_revenue", 0) for c in top_by_rev[:3])
                top_3_pct = round((top_3_rev / tot_rev) * 100, 1)
                if top_3_pct >= 50:
                    raw_candidates.append({
                        "id": f"rec_rev_diversify_{business.id}",
                        "title": "Diversify Customer Acquisition to Expand Revenue Base",
                        "category": RecommendationCategory.REVENUE_GROWTH,
                        "description": (
                            f"Top 3 customers currently generate {top_3_pct}% of total sales. "
                            "Developing new mid-tier customer channels will insulate your revenue from single-buyer volatility."
                        ),
                        "business_context": f"Business operating in {business.industry} with {tot_cust} tracked customer(s).",
                        "evidence": [
                            f"Top 3 customers contribute {top_3_pct}% of all recorded revenue.",
                            f"Total active customer accounts: {tot_cust}.",
                            f"Total revenue recorded: ₹{tot_rev:,.2f} across {tot_tx} orders.",
                        ],
                        "reasoning": "High revenue concentration creates acute vulnerability if a primary client reduces purchase volume.",
                        "recommended_actions": [
                            "Identify customer profiles and common purchasing drivers of your top 3 clients.",
                            "Launch a structured referral incentive for existing accounts.",
                            "Direct outbound sales efforts to acquire at least 2 new corporate/commercial buyers this quarter.",
                        ],
                        "action_plan": ActionPlan(
                            objective="Expand customer portfolio and reduce top-3 revenue share below 45%",
                            suggested_timeframe="60-90 Days",
                            success_metric="Acquire 2 new active accounts generating at least 15% of monthly revenue",
                            steps=[
                                ActionStep(
                                    step_number=1,
                                    title="Analyze Top Customer Buyer Profiles",
                                    description="Audit order history, product bundles, and payment timelines of leading clients.",
                                    timeframe="Days 1-15",
                                    resources_required="Sales transactions ledger",
                                ),
                                ActionStep(
                                    step_number=2,
                                    title="Targeted Prospect Outreach",
                                    description="Contact 15-20 comparable businesses in your region with tailored product proposals.",
                                    timeframe="Days 16-45",
                                    resources_required="Sales team / Owner outreach, digital product catalog",
                                ),
                                ActionStep(
                                    step_number=3,
                                    title="Review Revenue Distribution",
                                    description="Check monthly concentration metrics to confirm healthy customer spread.",
                                    timeframe="Days 46-60",
                                    resources_required="UrsBiz Sales Intelligence Dashboard",
                                ),
                            ],
                        ),
                        "expected_benefit": "More resilient revenue baseline with reduced dependence on primary accounts.",
                        "estimated_impact": round(tot_rev * 0.10, 2),
                        "impact_unit": "INR potential incremental turnover",
                        "urgency": 80,
                        "impact": 85,
                        "evidence_strength": 90,
                        "confidence": 88.0,
                        "feasibility": 70,
                        "data_quality": "High",
                        "limitations": ["Assumes market capacity exists for comparable customer acquisition."],
                        "source_modules": ["Sales Intelligence", "Customer Insights"],
                        "source_module_link": "/sales?tab=customers",
                    })

        if has_sales_data and product_insights and sales_summary:
            top_prods = product_insights.get("top_products_by_revenue", [])
            tot_rev = sales_summary.get("total_revenue", 0.0)
            aov = customer_insights.get("average_order_value", 0.0) if customer_insights else 0.0
            if top_prods and tot_rev > 0:
                top_p = top_prods[0]
                p_share = round((top_p.get("total_revenue", 0) / tot_rev) * 100, 1)
                p_name = top_p.get("product_name", "Flagship Product")
                p_id = top_p.get("product_id") or "sku"
                p_rev = top_p.get("total_revenue", 0.0)
                p_qty = top_p.get("total_quantity_sold", 0.0)
                p_price = top_p.get("average_unit_price", 0.0)
                if p_share >= 35:
                    raw_candidates.append({
                        "id": f"rec_rev_flagship_bundle_{business.id}_{p_id}",
                        "title": f"Leverage Flagship Product '{p_name}' for Cross-Selling",
                        "category": RecommendationCategory.REVENUE_GROWTH,
                        "description": (
                            f"'{p_name}' is your primary revenue engine ({p_share}% of sales). "
                            "Create complementary product bundles or bulk purchasing tiers to increase average order value."
                        ),
                        "business_context": f"Product portfolio comprises {product_insights.get('total_products', 1)} distinct item(s).",
                        "evidence": [
                            f"'{p_name}' generated ₹{p_rev:,.2f} ({p_share}% of revenue).",
                            f"Total units sold: {p_qty:,.0f} units at average price ₹{p_price:,.2f}.",
                            f"Overall business average order value is ₹{aov:,.2f}.",
                        ],
                        "reasoning": "High-demand flagship items provide an ideal anchor for cross-selling lower-velocity complementary products.",
                        "recommended_actions": [
                            f"Bundle '{p_name}' with secondary accessories or consumables.",
                            "Offer volume-based discount tiers (e.g. 5% off orders of 10+ units) to incentivize larger basket sizes.",
                        ],
                        "action_plan": ActionPlan(
                            objective="Increase average order value by bundling around leading SKU",
                            suggested_timeframe="30-45 Days",
                            success_metric=f"Lift average order value above current ₹{aov:,.2f} baseline",
                            steps=[
                                ActionStep(
                                    step_number=1,
                                    title="Identify Frequently Co-Purchased Items",
                                    description="Determine which secondary products complement the flagship SKU.",
                                    timeframe="Week 1",
                                    resources_required="Sales order records",
                                ),
                                ActionStep(
                                    step_number=2,
                                    title="Design Bundle Packages",
                                    description="Package flagship + complementary SKU with clear value pricing.",
                                    timeframe="Weeks 2-3",
                                    resources_required="Pricing schedule, marketing flyer",
                                ),
                            ],
                        ),
                        "expected_benefit": "Higher average transaction value and faster turnover for secondary products.",
                        "estimated_impact": round(aov * 0.12, 2) if aov > 0 else None,
                        "impact_unit": "INR lift per order" if aov > 0 else None,
                        "urgency": 65,
                        "impact": 75,
                        "evidence_strength": 92,
                        "confidence": 90.0,
                        "feasibility": 85,
                        "data_quality": "High",
                        "limitations": ["Customer willingness to adopt bundle packages may vary by channel."],
                        "source_modules": ["Sales Intelligence", "Product Insights"],
                        "source_module_link": "/sales?tab=products",
                    })

        # Category 2: Cost Optimization
        if has_sales_data and product_insights:
            top_by_vol = product_insights.get("fast_moving_products_by_volume", [])
            tot_vol = product_insights.get("total_quantity_sold", 0.0)
            tot_prods = product_insights.get("total_products", 0)
            low_skus = [p for p in reversed(top_by_vol) if tot_vol > 0 and (p.get("total_quantity_sold", 0) / tot_vol) < 0.05][:3]
            if low_skus and tot_prods >= 2:
                low_names = ", ".join(f"'{s.get('product_name')}'" for s in low_skus)
                raw_candidates.append({
                    "id": f"rec_cost_sku_rationalization_{business.id}",
                    "title": "Rationalize Slow-Moving SKUs to Release Working Capital",
                    "category": RecommendationCategory.COST_OPTIMIZATION,
                    "description": (
                        f"Identified slow-moving product(s) ({low_names}) "
                        "contributing negligibly to sales volume. Liquidate or rationalize these SKUs to minimize inventory holding costs."
                    ),
                    "business_context": f"Business currently holds {tot_prods} active SKUs.",
                    "evidence": [
                        f"{len(low_skus)} SKU(s) identified with less than 5% volume contribution.",
                        f"Target SKUs: {low_names}.",
                    ],
                    "reasoning": "Holding sluggish inventory ties up liquid cash flow and occupies physical warehouse space.",
                    "recommended_actions": [
                        "Conduct physical inventory count of identified slow-moving products.",
                        "Run clearance promotion or bundle with fast-moving items to clear remaining stock.",
                        "Pause future purchase orders for these SKUs until demand signals strengthen.",
                    ],
                    "action_plan": ActionPlan(
                        objective="Clear slow inventory and redirect working capital to high-margin SKUs",
                        suggested_timeframe="30 Days",
                        success_metric="Liquidate at least 60% of identified slow SKU inventory",
                        steps=[
                            ActionStep(
                                step_number=1,
                                title="Audit Stock on Hand",
                                description="Tally physical units and capital tied up in low-performing SKUs.",
                                timeframe="Day 1-7",
                                resources_required="Inventory count ledger",
                            ),
                            ActionStep(
                                step_number=2,
                                title="Execute Clearance Promo",
                                description="Apply a 15-25% markdown or distributor clearance discount.",
                                timeframe="Day 8-25",
                                resources_required="Promotional communications",
                            ),
                        ],
                    ),
                    "expected_benefit": "Immediate recovery of tied-up working capital and reduced warehousing overhead.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 70,
                    "impact": 65,
                    "evidence_strength": 88,
                    "confidence": 85.0,
                    "feasibility": 80,
                    "data_quality": "High",
                    "limitations": ["Liquidation speed depends on customer price sensitivity."],
                    "source_modules": ["Sales Intelligence", "Product Insights"],
                    "source_module_link": "/sales?tab=products",
                })

        # Category 3: Customer Retention
        if has_sales_data and customer_insights:
            declining = customer_insights.get("declining_customers", [])
            rep_cust = customer_insights.get("repeat_customers", 0)
            tot_cust = customer_insights.get("total_customers", 0)
            rep_rate = customer_insights.get("repeat_rate_pct", 0.0)
            if declining:
                inact_count = len(declining)
                inact_sample = ", ".join(f"'{c.get('customer_name')}'" for c in declining[:3])
                hist_val = sum(c.get("total_revenue", 0.0) for c in declining)
                raw_candidates.append({
                    "id": f"rec_retention_inactive_reengagement_{business.id}",
                    "title": f"Re-Engage {inact_count} Lapsed Repeat Customer(s)",
                    "category": RecommendationCategory.CUSTOMER_RETENTION,
                    "description": (
                        f"{inact_count} customer(s) with previous repeat purchase history ({inact_sample}) "
                        "have not placed an order in over 60 days. Immediate proactive outreach can prevent permanent churn."
                    ),
                    "business_context": f"Customer base includes {rep_cust} repeat buyers out of {tot_cust} total.",
                    "evidence": [
                        f"{inact_count} repeat customer(s) inactive for >60 days.",
                        f"Combined historical purchase value from these accounts: ₹{hist_val:,.2f}.",
                        f"Repeat customer share: {rep_rate}%.",
                    ],
                    "reasoning": "Re-activating an existing customer who already trusts your business is significantly cheaper than acquiring a new one.",
                    "recommended_actions": [
                        f"Conduct direct check-in calls with key lapsed accounts ({inact_sample}).",
                        "Offer customized restocking discounts or inquire about recent service/product satisfaction.",
                        "Set up a 45-day automated follow-up reminder after every completed delivery.",
                    ],
                    "action_plan": ActionPlan(
                        objective="Reactivate lapsed buyers and establish recurring repurchase cadence",
                        suggested_timeframe="21 Days",
                        success_metric="Reactivate at least 25% of lapsed customers within 3 weeks",
                        steps=[
                            ActionStep(
                                step_number=1,
                                title="Review Prior Orders & Preferences",
                                description="Look up specific items previously ordered by each inactive customer.",
                                timeframe="Days 1-3",
                                resources_required="Sales Intelligence Customer Ledger",
                            ),
                            ActionStep(
                                step_number=2,
                                title="Direct Relationship Outreach",
                                description="Call or message business owner/purchaser directly with restock support.",
                                timeframe="Days 4-14",
                                resources_required="Direct contact channel",
                            ),
                        ],
                    ),
                    "expected_benefit": "Re-establishment of recurring cash flow from proven historical buyers.",
                    "estimated_impact": round(hist_val * 0.25, 2),
                    "impact_unit": "INR estimated recoverable order volume",
                    "urgency": 85,
                    "impact": 80,
                    "evidence_strength": 95,
                    "confidence": 92.0,
                    "feasibility": 85,
                    "data_quality": "High",
                    "limitations": ["Some customers may have relocated, paused operations, or fulfilled needs elsewhere."],
                    "source_modules": ["Sales Intelligence", "Customer Insights"],
                    "source_module_link": "/sales?tab=customers",
                })

        # Category 4: Product Performance
        if has_sales_data and product_insights and sales_summary:
            top_prods = product_insights.get("top_products_by_revenue", [])
            tot_rev = sales_summary.get("total_revenue", 0.0)
            tot_prods = product_insights.get("total_products", 0)
            if top_prods and tot_rev > 0 and tot_prods > 1:
                top_pct = round((top_prods[0].get("total_revenue", 0) / tot_rev) * 100, 1)
                if top_pct >= 60:
                    raw_candidates.append({
                        "id": f"rec_prod_concentration_rebalance_{business.id}",
                        "title": "Balance Product Portfolio to Reduce Single-SKU Reliance",
                        "category": RecommendationCategory.PRODUCT_PERFORMANCE,
                        "description": (
                            f"A single product generates {top_pct}% of total sales revenue. "
                            "Actively promote secondary SKUs to establish a diversified, balanced product portfolio."
                        ),
                        "business_context": f"Business currently offers {tot_prods} product SKU(s).",
                        "evidence": [
                            f"Single product concentration: {top_pct}% of total revenue.",
                            f"Catalog breadth: {tot_prods} total SKUs.",
                        ],
                        "reasoning": "Supplier shortages or price competition on your primary SKU could disproportionately disrupt total cash flow.",
                        "recommended_actions": [
                            "Review gross margins of tier-2 products and adjust merchandising priority.",
                            "Feature high-margin secondary products prominently in customer quotes and catalogs.",
                        ],
                        "expected_benefit": "Resilient product sales mix with reduced single-point supply vulnerability.",
                        "estimated_impact": None,
                        "impact_unit": None,
                        "urgency": 70,
                        "impact": 70,
                        "evidence_strength": 88,
                        "confidence": 85.0,
                        "feasibility": 75,
                        "data_quality": "High",
                        "limitations": ["Market demand for secondary SKUs must be verified through small-scale promotion."],
                        "source_modules": ["Sales Intelligence", "Product Insights"],
                        "source_module_link": "/sales?tab=products",
                    })

        # Category 5: Demand and Sales Planning
        if has_forecast_data and forecast_overview:
            increasing_prods = [p for p in forecast_overview.product_summaries if p.demand_trend == "Increasing"]
            if increasing_prods:
                lead_grower = increasing_prods[0]
                lead_id = lead_grower.product_id or "sku"
                p_units = round(lead_grower.forecasted_units_total, 1)
                p_horizon = lead_grower.forecast_horizon_periods
                p_model = lead_grower.selected_model
                p_rel = str(lead_grower.reliability.value if hasattr(lead_grower.reliability, "value") else lead_grower.reliability)
                p_mae = lead_grower.best_mae
                delta_str = f" ({lead_grower.trend_delta_pct:+.1f}%)" if lead_grower.trend_delta_pct is not None else ""
                raw_candidates.append({
                    "id": f"rec_demand_scale_inventory_{business.id}_{lead_id}",
                    "title": f"Pre-Stock Inventory for Projected Demand Surge in '{lead_grower.product_name}'",
                    "category": RecommendationCategory.DEMAND_PLANNING,
                    "description": (
                        f"Demand forecasting ({p_model}) projects {p_units} units for '{lead_grower.product_name}' "
                        f"over the coming {p_horizon} periods ({lead_grower.demand_trend}{delta_str}). Advance procurement to avoid stockouts."
                    ),
                    "business_context": f"Evaluated with {p_rel} reliability grade based on historical sales transactions.",
                    "evidence": [
                        f"Forecasted demand: {p_units} units across next {p_horizon} periods.",
                        f"Selected forecast model: {p_model} (Backtest MAE: {p_mae}).",
                        f"Trend direction: {lead_grower.demand_trend}{delta_str}.",
                        f"Reliability grade: {p_rel}.",
                    ],
                    "reasoning": "Rising demand trajectory without proactive inventory buffering causes stockouts, lost sales, and customer attrition.",
                    "recommended_actions": [
                        f"Coordinate supplier orders for at least {p_units} units of '{lead_grower.product_name}'.",
                        "Confirm vendor lead times to ensure delivery before projected peak periods.",
                        "Track weekly sales against forecast pace.",
                    ],
                    "action_plan": ActionPlan(
                        objective=f"Secure stock coverage for projected {p_units} unit demand surge",
                        suggested_timeframe="2-4 Weeks",
                        success_metric="Zero stock-out days during the upcoming forecast period",
                        steps=[
                            ActionStep(
                                step_number=1,
                                title="Check Existing Warehouse Quantities",
                                description="Calculate current stock on hand plus pipeline orders.",
                                timeframe="Days 1-3",
                                resources_required="Warehouse stock register",
                            ),
                            ActionStep(
                                step_number=2,
                                title="Place Confirmed Purchase Orders",
                                description=f"Order remaining units to cover {p_units} target.",
                                timeframe="Days 4-10",
                                resources_required="Supplier agreement / purchase order",
                            ),
                        ],
                    ),
                    "expected_benefit": "Uninterrupted order fulfillment and capture of peak seasonal demand.",
                    "estimated_impact": float(p_units),
                    "impact_unit": "units forecasted demand",
                    "urgency": 85 if p_rel == "High" else 75,
                    "impact": 85,
                    "evidence_strength": 92 if p_rel == "High" else 78,
                    "confidence": 90.0 if p_rel == "High" else 75.0,
                    "feasibility": 80,
                    "data_quality": "High" if p_rel == "High" else "Moderate",
                    "limitations": lead_grower.limitation_notes or ["Demand estimates reflect historical purchase patterns and may vary with external market shifts."],
                    "source_modules": ["Demand Forecasting"],
                    "source_module_link": "/sales?tab=forecast",
                })

            declining_prods = [p for p in forecast_overview.product_summaries if p.demand_trend == "Decreasing"]
            if declining_prods:
                lead_decliner = declining_prods[0]
                p_units = round(lead_decliner.forecasted_units_total, 1)
                p_horizon = lead_decliner.forecast_horizon_periods
                p_model = lead_decliner.selected_model
                p_rel = str(lead_decliner.reliability.value if hasattr(lead_decliner.reliability, "value") else lead_decliner.reliability)
                raw_candidates.append({
                    "id": f"rec_demand_taper_reorders_{business.id}_{lead_decliner.product_id or 'sku'}",
                    "title": f"Taper Re-Orders for Declining SKU '{lead_decliner.product_name}'",
                    "category": RecommendationCategory.DEMAND_PLANNING,
                    "description": (
                        f"Demand for '{lead_decliner.product_name}' is trending downward with {p_units} units "
                        f"projected across the next {p_horizon} periods. Moderate reorder batch sizes to avoid surplus accumulation."
                    ),
                    "business_context": f"Identified via backtesting with {p_rel} reliability grade.",
                    "evidence": [
                        f"Projected demand: {p_units} units ({lead_decliner.demand_trend} trend).",
                        f"Selected forecasting model: {p_model}.",
                        f"Backtest error: MAE {lead_decliner.best_mae}.",
                    ],
                    "reasoning": "Continuing regular production or replenishment runs during demand contraction leads to dead inventory and write-downs.",
                    "recommended_actions": [
                        f"Reduce upcoming purchase batch size for '{lead_decliner.product_name}'.",
                        "Audit reasons for demand decline (pricing, substitute products, competitor actions).",
                    ],
                    "expected_benefit": "Avoidance of excess inventory holding and write-down losses.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 75,
                    "impact": 70,
                    "evidence_strength": 85,
                    "confidence": 80.0,
                    "feasibility": 85,
                    "data_quality": "Moderate",
                    "limitations": lead_decliner.limitation_notes or ["External promotional events could reverse decline."],
                    "source_modules": ["Demand Forecasting"],
                    "source_module_link": "/sales?tab=forecast",
                })

        # Category 6: Digital Transformation
        dp = getattr(business, "digital_presence", None)
        has_web = bool(dp and getattr(dp, "website_url", None) and len(dp.website_url.strip()) > 3)
        has_ecom = bool(dp and getattr(dp, "has_ecommerce", False))
        if not has_web or not has_ecom:
            raw_candidates.append({
                "id": f"rec_digital_storefront_{business.id}",
                "title": "Establish Official Online Presence and Digital Order Channel",
                "category": RecommendationCategory.DIGITAL_TRANSFORMATION,
                "description": (
                    f"Your business currently lacks an active web presence or digital order channel in {business.industry}. "
                    "Launching a digital storefront enables inbound buyer discovery beyond local geographic boundaries."
                ),
                "business_context": f"Business stage: {getattr(business, 'business_stage', 'Growth') or 'Growth'}, Location: {business.city or 'Domestic market'}.",
                "evidence": [
                    "No verified website URL recorded in business profile.",
                    "No e-commerce order intake integration configured.",
                    f"Digital health facet score: {round(health_score * 0.10, 1)}/10 points.",
                ],
                "reasoning": "Modern B2B and consumer buyers evaluate vendor credibility and product catalogs online before issuing purchase orders.",
                "recommended_actions": [
                    "Register a dedicated business domain matching your trade name.",
                    "Publish a responsive digital catalog featuring your primary products and specifications.",
                    "Set up official WhatsApp Business channel for direct order inquiries.",
                ],
                "action_plan": ActionPlan(
                    objective="Launch verified online catalog and digital communication channel",
                    suggested_timeframe="30 Days",
                    success_metric="Live business website with product catalog and inquiry integration",
                    steps=[
                        ActionStep(
                            step_number=1,
                            title="Register Domain & Web Presence",
                            description="Acquire company domain and configure essential company profile.",
                            timeframe="Days 1-7",
                            resources_required="Domain registrar, branding assets",
                        ),
                        ActionStep(
                            step_number=2,
                            title="Publish Core Product Catalog",
                            description="List primary SKUs with high-resolution photos, descriptions, and pricing.",
                            timeframe="Days 8-20",
                            resources_required="Product specification sheets",
                        ),
                        ActionStep(
                            step_number=3,
                            title="Configure Inbound Lead Flow",
                            description="Add instant message inquiry buttons and contact forms.",
                            timeframe="Days 21-30",
                            resources_required="Communication channels",
                        ),
                    ],
                ),
                "expected_benefit": "Expanded customer reach, higher brand credibility, and 24/7 product catalog visibility.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 75,
                "impact": 80,
                "evidence_strength": 95,
                "confidence": 95.0,
                "feasibility": 85,
                "data_quality": "High",
                "limitations": ["Requires periodic maintenance to keep product availability up to date."],
                "source_modules": ["Business Profile", "Digital Health"],
                "source_module_link": "/business",
            })

        # Category 7: Financial Management
        if not business.annual_revenue or business.annual_revenue <= 0 or "annual_revenue" in missing_fields:
            raw_candidates.append({
                "id": f"rec_fin_recordkeeping_{business.id}",
                "title": "Formalize Financial Invoicing & Accounting Records",
                "category": RecommendationCategory.FINANCIAL_MANAGEMENT,
                "description": (
                    "Annual turnover or formal financial indicators are missing from your business profile. "
                    "Maintaining standardized cloud accounting records is mandatory for institutional credit evaluation and tax compliance."
                ),
                "business_context": f"Business entity: {business.business_type or 'MSME'} established in {business.established_year or 'recent years'}.",
                "evidence": [
                    "Annual revenue baseline unrecorded in digital twin profile.",
                    "Financial readiness component requires verification for credit matching.",
                ],
                "reasoning": "Unstructured financial recordkeeping inhibits accurate tax filing, prevents loan approvals, and obscures true net margins.",
                "recommended_actions": [
                    "Adopt a certified MSME accounting software (Tally, Zoho Books, or Marg).",
                    "Maintain distinct, separated business bank accounts away from personal finances.",
                    "Update recorded annual revenue in UrsBiz Business Profile.",
                ],
                "expected_benefit": "Audit-ready financial books, clear margin tracking, and bankability for credit schemes.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 80,
                "impact": 75,
                "evidence_strength": 90,
                "confidence": 90.0,
                "feasibility": 80,
                "data_quality": "Limited",
                "limitations": ["Software implementation requires initial ledger setup time."],
                "source_modules": ["Business Profile", "Health Score"],
                "source_module_link": "/business",
            })

        # Category 8: Operational Efficiency
        if not has_sales_data:
            raw_candidates.append({
                "id": f"rec_ops_upload_sales_data_{business.id}",
                "title": "Upload Historical Sales Data to Unlock Predictive Intelligence",
                "category": RecommendationCategory.OPERATIONAL_EFFICIENCY,
                "description": (
                    "No historical sales records have been uploaded for your business. "
                    "Ingesting transaction CSV or Excel spreadsheets activates automatic customer churn tracking, product Pareto analysis, and demand forecasting."
                ),
                "business_context": f"Profile health score is {health_score}/100. Sales Intelligence module is currently inactive.",
                "evidence": [
                    "Zero sales transaction records currently stored.",
                    "Demand forecasting and customer retention engines waiting for baseline data.",
                ],
                "reasoning": "Automated data-grounded intelligence requires real historical transactions to compute accurate projections and risk alerts.",
                "recommended_actions": [
                    "Export past 6 to 12 months of sales invoices or ledger entries from your billing system.",
                    "Upload the CSV or Excel file in the Sales Intelligence portal.",
                    "Confirm column mapping for transaction date, product name, quantity, and unit price.",
                ],
                "action_plan": ActionPlan(
                    objective="Activate full predictive sales and customer intelligence capabilities",
                    suggested_timeframe="Immediate (1 Day)",
                    success_metric="Successful ingestion of at least 50 historical sales rows",
                    steps=[
                        ActionStep(
                            step_number=1,
                            title="Export Sales Ledger",
                            description="Export transaction file (CSV/XLSX) from billing software.",
                            timeframe="30 minutes",
                            resources_required="Billing software / spreadsheet",
                        ),
                        ActionStep(
                            step_number=2,
                            title="Upload to UrsBiz",
                            description="Navigate to Sales tab, upload file, and confirm column mappings.",
                            timeframe="15 minutes",
                            resources_required="UrsBiz Sales Portal",
                        ),
                    ],
                ),
                "expected_benefit": "Instant access to customer retention metrics, SKU performance, and automated demand forecasts.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 90,
                "impact": 90,
                "evidence_strength": 100,
                "confidence": 95.0,
                "feasibility": 95,
                "data_quality": "Insufficient",
                "limitations": ["Supported formats: CSV, XLSX up to 10MB."],
                "source_modules": ["Sales Intelligence", "System Audit"],
                "source_module_link": "/sales?tab=upload",
            })
        elif missing_fields and len(missing_fields) > 2:
            missing_clean = ", ".join(f.replace("_", " ").title() for f in missing_fields[:4])
            raw_candidates.append({
                "id": f"rec_ops_profile_completeness_{business.id}",
                "title": "Complete Digital Twin Profile to Sharpen Recommendation Accuracy",
                "category": RecommendationCategory.OPERATIONAL_EFFICIENCY,
                "description": (
                    f"Your Business Digital Twin profile is missing key fields: {missing_clean}. "
                    "Completing these operational details improves government scheme eligibility matching and AI advisor precision."
                ),
                "business_context": f"Health score is currently {health_score}/100 with {len(missing_fields)} unpopulated field(s).",
                "evidence": [
                    f"Overall health score: {health_score}/100.",
                    f"Missing operational attributes: {missing_clean}.",
                ],
                "reasoning": "Incomplete profile data reduces the confidence and specificity of matching algorithms.",
                "recommended_actions": [
                    "Navigate to Business Profile and fill in missing operational, product, and facility details.",
                    "Record employee count, certifications, and target markets.",
                ],
                "expected_benefit": "Maximized health score and highly targeted scheme and risk recommendations.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 65,
                "impact": 60,
                "evidence_strength": 90,
                "confidence": 95.0,
                "feasibility": 90,
                "data_quality": "Moderate",
                "limitations": ["Self-reported profile data."],
                "source_modules": ["Business Profile", "Health Score"],
                "source_module_link": "/business",
            })

        # Category 9: Government Schemes and Funding
        if matching_schemes:
            lead_scheme = matching_schemes[0]
            raw_candidates.append({
                "id": f"rec_scheme_apply_{business.id}_{lead_scheme.id}",
                "title": f"Explore Matching Government Scheme: {lead_scheme.name}",
                "category": RecommendationCategory.GOVERNMENT_SCHEMES,
                "description": (
                    f"Your business profile matches the published parameters for '{lead_scheme.name}' "
                    f"administered by the {lead_scheme.official_authority}. {lead_scheme.description}"
                ),
                "business_context": f"Matches based on industry '{business.industry}', employee count ({business.employee_count or 'N/A'}), and location '{business.city or 'India'}'.",
                "evidence": [
                    f"Official Administering Authority: {lead_scheme.official_authority}.",
                    f"Official Verification Portal: {lead_scheme.official_source_url}.",
                    f"Key Benefits: {', '.join(lead_scheme.benefits or [])}.",
                ],
                "reasoning": "Government-backed schemes provide subsidized credit, collateral relief, and technology upgrade grants for qualifying MSMEs.",
                "recommended_actions": [
                    f"Review full eligibility criteria and mandatory checklists on the official {lead_scheme.official_authority} portal.",
                    "Assemble prerequisite documentation (Udyam registration, audited financial statements, project report).",
                    f"Submit application directly via verified official URL: {lead_scheme.official_source_url}.",
                ],
                "action_plan": ActionPlan(
                    objective=f"Prepare and submit verified application for {lead_scheme.name}",
                    suggested_timeframe="3-4 Weeks",
                    success_metric="Application acknowledgment generated by official authority",
                    steps=[
                        ActionStep(
                            step_number=1,
                            title="Verify Official Guidelines",
                            description=f"Inspect official documentation at {lead_scheme.official_source_url}.",
                            timeframe="Days 1-5",
                            resources_required="Internet access, browser",
                        ),
                        ActionStep(
                            step_number=2,
                            title="Compile Documentation",
                            description="Assemble Udyam certificate, GST returns, and financial statements.",
                            timeframe="Days 6-18",
                            resources_required="Company documents, chartered accountant assistance",
                        ),
                        ActionStep(
                            step_number=3,
                            title="Submit to Official Authority",
                            description="Apply directly through authorized government portal or designated partner bank.",
                            timeframe="Days 19-25",
                            resources_required="Digital signature / portal login",
                        ),
                    ],
                ),
                "expected_benefit": f"Potential access to {', '.join(lead_scheme.benefits or [])} as governed by official authority rules.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 70,
                "impact": 85,
                "evidence_strength": 92,
                "confidence": 88.0,
                "feasibility": 75,
                "data_quality": "High",
                "limitations": [
                    "UrsBiz computes match similarity based on published criteria; official eligibility and approval rests exclusively with the administering government authority.",
                ],
                "source_modules": ["Government Schemes"],
                "source_module_link": "/schemes",
            })

        # Category 10: Risk Reduction
        has_export = bool(getattr(business, "has_export_experience", False) or (getattr(business, "export_history", None) and len(business.export_history) > 0))
        if not has_export and business.annual_revenue and business.annual_revenue > 500000:
            raw_candidates.append({
                "id": f"rec_risk_export_diversification_{business.id}",
                "title": "Evaluate Cross-Border Export Readiness to Hedge Domestic Market Cycles",
                "category": RecommendationCategory.RISK_REDUCTION,
                "description": (
                    f"Your business generates healthy domestic turnover in {business.industry} but operates with 100% domestic market dependence. "
                    "Obtaining an Importer-Exporter Code (IEC) and exploring export markets mitigates regional economic downturns."
                ),
                "business_context": f"Domestic revenue scale: ₹{business.annual_revenue:,.2f}.",
                "evidence": [
                    "100% revenue generated in domestic market.",
                    "No export registration code (IEC) on record.",
                ],
                "reasoning": "Relying purely on one geographical market exposes operations to local regulatory shifts and regional liquidity contractions.",
                "recommended_actions": [
                    "Register for DGFT Importer-Exporter Code (IEC) online.",
                    "Identify export demand and tariff advantages for your products in neighboring trade corridors.",
                ],
                "expected_benefit": "Geographic revenue diversification and foreign exchange market access.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 60,
                "impact": 75,
                "evidence_strength": 85,
                "confidence": 82.0,
                "feasibility": 70,
                "data_quality": "Moderate",
                "limitations": ["Exporting involves cross-border logistics, customs documentation, and compliance obligations."],
                "source_modules": ["Business Profile", "SWOT Analysis"],
                "source_module_link": "/business",
            })

        # ---------------------------------------------------------------------
        # 3. Deterministic Prioritization Scoring
        # ---------------------------------------------------------------------
        persisted_states = self.lifecycle_repo.get_states_for_business(business.id)
        candidate_ids = [c["id"] for c in raw_candidates]
        self.lifecycle_repo.record_first_views(business.id, candidate_ids)

        scored_items: list[SmartRecommendationItem] = []
        for cand in raw_candidates:
            u = cand.get("urgency", 50)
            imp = cand.get("impact", 50)
            ev = cand.get("evidence_strength", 50)
            conf = cand.get("confidence", 70.0)
            feas = cand.get("feasibility", 60)

            raw_score = (0.25 * u) + (0.25 * imp) + (0.20 * ev) + (0.15 * conf) + (0.15 * feas)
            p_score = min(100, max(10, round(raw_score)))

            if p_score >= 80:
                p_level = RecommendationPriority.CRITICAL
            elif p_score >= 65:
                p_level = RecommendationPriority.HIGH
            elif p_score >= 45:
                p_level = RecommendationPriority.MEDIUM
            else:
                p_level = RecommendationPriority.LOW

            state_record = persisted_states.get(cand["id"])
            if state_record:
                curr_status = RecommendationStatus(state_record.status)
                status_updated = state_record.status_updated_at.isoformat() if state_record.status_updated_at else None
                rec_notes = state_record.notes
            else:
                curr_status = RecommendationStatus.NEW
                status_updated = now_iso
                rec_notes = None

            item = SmartRecommendationItem(
                id=cand["id"],
                title=cand["title"],
                category=cand["category"],
                priority=p_level,
                priority_score=p_score,
                description=cand["description"],
                business_context=cand["business_context"],
                evidence=cand.get("evidence", []),
                reasoning=cand["reasoning"],
                recommended_actions=cand.get("recommended_actions", []),
                action_plan=cand.get("action_plan"),
                expected_benefit=cand["expected_benefit"],
                estimated_impact=cand.get("estimated_impact"),
                impact_unit=cand.get("impact_unit"),
                confidence=float(conf),
                data_quality=cand.get("data_quality", "Moderate"),
                limitations=cand.get("limitations", []),
                source_modules=cand.get("source_modules", []),
                source_module_link=cand.get("source_module_link"),
                created_at=now_iso,
                status=curr_status,
                status_updated_at=status_updated,
                notes=rec_notes,
            )
            scored_items.append(item)

        scored_items.sort(key=lambda r: r.priority_score, reverse=True)

        # ---------------------------------------------------------------------
        # 4. Apply Filters
        # ---------------------------------------------------------------------
        filtered_items = scored_items

        if category_filter and category_filter != "all":
            filtered_items = [i for i in filtered_items if i.category.value.lower() == category_filter.lower()]

        if priority_filter and priority_filter != "all":
            filtered_items = [i for i in filtered_items if i.priority.value.lower() == priority_filter.lower()]

        if status_filter and status_filter != "all":
            filtered_items = [i for i in filtered_items if i.status.value.lower() == status_filter.lower()]
        elif not status_filter:
            filtered_items = [i for i in filtered_items if i.status != RecommendationStatus.DISMISSED]

        crit_count = sum(1 for i in scored_items if i.priority == RecommendationPriority.CRITICAL)
        high_count = sum(1 for i in scored_items if i.priority == RecommendationPriority.HIGH)
        med_count = sum(1 for i in scored_items if i.priority == RecommendationPriority.MEDIUM)
        low_count = sum(1 for i in scored_items if i.priority == RecommendationPriority.LOW)

        status_counts: dict[str, int] = {}
        for i in scored_items:
            status_counts[i.status.value] = status_counts.get(i.status.value, 0) + 1

        category_counts: dict[str, int] = {}
        for i in scored_items:
            category_counts[i.category.value] = category_counts.get(i.category.value, 0) + 1

        return SmartRecommendationsResponse(
            generated_at=now_iso,
            business_id=business.id,
            business_name=business.legal_name,
            total_count=len(filtered_items),
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            status_counts=status_counts,
            category_counts=category_counts,
            recommendations=filtered_items,
        )

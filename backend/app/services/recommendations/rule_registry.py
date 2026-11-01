"""Modular Recommendation Rule Registry (Phase 5.2).

Houses modular, evidence-based recommendation rules across the 10 official categories:
  1. Revenue Growth
  2. Cost Optimization
  3. Customer Retention
  4. Product Performance
  5. Demand and Sales Planning
  6. Digital Transformation
  7. Financial Management
  8. Operational Efficiency
  9. Government Schemes and Funding
  10. Risk Reduction

Strict Boundaries:
  - Phase 3 has no inventory balances, supplier lead times, or stockout dates:
    Demand rules advise reviewing demand trajectories and supplier check-ins;
    they NEVER calculate reorder quantities, safety stock, or stockouts.
  - Historical customer purchase value is past evidence only; never recoverable revenue.
"""

from __future__ import annotations

from typing import Any
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.schemas.smart_recommendations import (
    ActionPlan,
    ActionStep,
    RecommendationCategory,
)


class RecommendationRuleRegistry:
    """Evaluates modular recommendation rules against a UnifiedRecommendationContext."""

    @staticmethod
    def evaluate_all(ctx: UnifiedRecommendationContext) -> list[dict[str, Any]]:
        """Run all registered rules and return structured recommendation candidates."""
        candidates: list[dict[str, Any]] = []
        biz_id = ctx.business_id
        profile = ctx.profile
        health = ctx.health
        sales = ctx.sales
        cust = ctx.customers
        prod = ctx.products
        forecast = ctx.forecast
        schemes = ctx.schemes

        # Decoupled Evidence Strength calculation for sales-derived rules
        sales_ev_strength = 50
        if sales.has_sales_data:
            sales_ev_strength = min(
                100,
                50 + min(30, int(sales.total_transactions * 0.5)) + min(20, int(sales.date_range_days / 15)),
            )

        # ---------------------------------------------------------------------
        # Category 1: Revenue Growth
        # ---------------------------------------------------------------------
        # Rule 1.1: Customer Concentration Diversification
        if sales.has_sales_data and cust.top_customers_by_revenue and sales.total_revenue > 0:
            top_3_rev = sum(c.get("total_revenue", 0) for c in cust.top_customers_by_revenue[:3])
            top_3_pct = round((top_3_rev / sales.total_revenue) * 100, 1)
            if top_3_pct >= 50:
                candidates.append({
                    "id": f"rec_RULE_REV_CONCENTRATION_DIVERSIFICATION_{biz_id}_GLOBAL_v1",
                    "title": "Diversify Customer Acquisition to Expand Revenue Base",
                    "category": RecommendationCategory.REVENUE_GROWTH,
                    "description": (
                        f"Top 3 customers currently generate {top_3_pct}% of total sales. "
                        "Developing new mid-tier customer channels will insulate your revenue from single-buyer volatility."
                    ),
                    "business_context": f"Business operating in {profile.industry} with {cust.total_customers} tracked customer(s).",
                    "evidence": [
                        f"Top 3 customers contribute {top_3_pct}% of all recorded revenue.",
                        f"Total active customer accounts: {cust.total_customers}.",
                        f"Total revenue recorded: ₹{sales.total_revenue:,.2f} across {sales.total_transactions} orders.",
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
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 80,
                    "impact": 85,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 95.0,
                    "feasibility": 70,
                    "data_quality": "High",
                    "limitations": ["Reflects recorded transaction data only; does not observe off-ledger sales or contractual multi-year commitments."],
                    "source_modules": ["Sales Intelligence", "Customer Insights"],
                    "source_module_link": "/sales?tab=customers",
                    "what_is_happening": f"Top 3 customers currently generate {top_3_pct}% of total sales.",
                    "why_it_matters": "If any primary client delays orders or switches suppliers, operational cash flow faces immediate shock.",
                    "root_cause": "Historical reliance on early anchor accounts without systematic outreach to mid-tier B2B accounts.",
                    "missed_opportunity": "Unlocking consistent recurring orders from underserved regional businesses.",
                    "action_scenario": "Acquiring 2-3 mid-tier accounts diversifies turnover and reduces top-3 share below 45%.",
                    "cost_of_inaction": f"Vulnerability to a {top_3_pct}% revenue wipeout if major accounts pause procurement.",
                    "measurement_kpis": ["Top 3 revenue concentration %", "New active accounts acquired", "Monthly revenue stability"],
                    "implementation_difficulty": "Strategic",
                    "prerequisites_and_tradeoffs": ["Requires dedicated outreach time by owner/sales lead; temporary ramp-up time."],
                })

        # Rule 1.2: Flagship Product Cross-Selling
        if sales.has_sales_data and prod.top_products_by_revenue and sales.total_revenue > 0:
            top_p = prod.top_products_by_revenue[0]
            p_share = round((top_p.get("total_revenue", 0) / sales.total_revenue) * 100, 1)
            p_name = top_p.get("product_name", "Flagship Product")
            p_id = top_p.get("product_id") or "sku"
            p_rev = top_p.get("total_revenue", 0.0)
            p_qty = top_p.get("total_quantity_sold", 0.0)
            p_price = top_p.get("average_unit_price", 0.0)
            if p_share >= 35:
                candidates.append({
                    "id": f"rec_RULE_REV_FLAGSHIP_BUNDLE_EXPANSION_{biz_id}_{p_id}_v1",
                    "title": f"Leverage Flagship Product '{p_name}' for Cross-Selling",
                    "category": RecommendationCategory.REVENUE_GROWTH,
                    "description": (
                        f"'{p_name}' is your primary revenue engine ({p_share}% of sales). "
                        "Create complementary product bundles or volume pricing tiers to increase average order value."
                    ),
                    "business_context": f"Product portfolio comprises {prod.total_products} distinct item(s).",
                    "evidence": [
                        f"'{p_name}' generated ₹{p_rev:,.2f} ({p_share}% of revenue).",
                        f"Total units sold: {p_qty:,.0f} units at average price ₹{p_price:,.2f}.",
                        f"Overall business average order value is ₹{cust.average_order_value:,.2f}.",
                    ],
                    "reasoning": "High-demand flagship items provide an ideal anchor for cross-selling lower-velocity complementary products.",
                    "recommended_actions": [
                        f"Bundle '{p_name}' with secondary accessories or consumables.",
                        "Offer volume-based discount tiers to incentivize larger basket sizes.",
                    ],
                    "action_plan": ActionPlan(
                        objective="Increase average order value by bundling around leading SKU",
                        suggested_timeframe="30-45 Days",
                        success_metric=f"Lift average order value above current ₹{cust.average_order_value:,.2f} baseline",
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
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 65,
                    "impact": 80,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 95.0,
                    "feasibility": 85,
                    "data_quality": "High",
                    "limitations": ["Bundle adoption depends on customer purchasing preferences and price elasticity."],
                    "source_modules": ["Sales Intelligence", "Product Insights"],
                    "source_module_link": "/sales?tab=products",
                    "what_is_happening": f"'{p_name}' accounts for {p_share}% of total sales revenue.",
                    "why_it_matters": "Single-product over-concentration leaves business exposed if that SKU slows down.",
                    "root_cause": "Customers primarily know the business for one hero item and lack awareness of catalog depth.",
                    "missed_opportunity": "Higher basket size and increased AOV through bundled accessories and consumables.",
                    "action_scenario": f"Bundling lifts Average Order Value above the ₹{cust.average_order_value:,.2f} baseline.",
                    "cost_of_inaction": "Slow inventory turnover on secondary items and missed margin on accessory attachments.",
                    "measurement_kpis": ["Average Order Value (AOV)", "Multi-item order %", "Secondary SKU sales volume"],
                    "implementation_difficulty": "Quick Win",
                    "prerequisites_and_tradeoffs": ["Requires setting package pricing tiers without eroding standalone margins."],
                })

        # Rule 1.3: Average Order Value Expansion via Volume Tiering
        if sales.has_sales_data and cust.average_order_value and cust.average_order_value > 0 and cust.repeat_customers >= 1:
            aov = cust.average_order_value
            candidates.append({
                "id": f"rec_RULE_REV_AOV_VOLUME_TIERING_{biz_id}_GLOBAL_v1",
                "title": f"Introduce Volume Pricing Tiers to Lift Average Order Value (₹{aov:,.2f})",
                "category": RecommendationCategory.REVENUE_GROWTH,
                "description": (
                    f"Your current Average Order Value (AOV) across repeat customers is ₹{aov:,.2f}. "
                    "Introducing structured 2x and 3x volume brackets with modest percentage incentives encourages commercial buyers to consolidate orders."
                ),
                "business_context": f"Active customer base of {cust.total_customers} with {cust.repeat_customers} repeat buyers.",
                "evidence": [
                    f"Baseline Average Order Value: ₹{aov:,.2f}.",
                    f"Repeat customer count: {cust.repeat_customers} accounts ({cust.repeat_rate_pct}% repeat rate).",
                    f"Total recorded orders: {sales.total_transactions}.",
                ],
                "reasoning": "Tiered quantity discounts lower per-order fulfillment, packaging, and dispatch overhead while boosting gross revenue.",
                "recommended_actions": [
                    "Define volume brackets: Tier 1 (standard), Tier 2 (1.5x AOV with 3% incentive), Tier 3 (2.5x AOV with 6% incentive).",
                    "Communicate tiered pricing on digital quotes and WhatsApp order confirmations.",
                    "Test volume pricing with your top 5 most frequent purchasers.",
                ],
                "action_plan": ActionPlan(
                    objective=f"Lift baseline AOV from ₹{aov:,.2f} by at least 15% through order consolidation",
                    suggested_timeframe="30 Days",
                    success_metric=f"Achieve AOV above ₹{aov * 1.15:,.2f} over next 30 days",
                    steps=[
                        ActionStep(
                            step_number=1,
                            title="Structure Volume Price Brackets",
                            description="Calculate contribution margins to ensure volume discounts maintain healthy net profit.",
                            timeframe="Days 1-5",
                            resources_required="Product margin sheet",
                        ),
                        ActionStep(
                            step_number=2,
                            title="Roll Out to Frequent Buyers",
                            description="Present tiered options during next purchase inquiries.",
                            timeframe="Days 6-20",
                            resources_required="Sales quotation template",
                        ),
                    ],
                ),
                "expected_benefit": "Larger order sizes, lower per-transaction packaging/logistics overhead, and higher monthly revenue velocity.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 70,
                "impact": 75,
                "evidence_strength": sales_ev_strength,
                "confidence": 92.0,
                "feasibility": 85,
                "data_quality": "High",
                "limitations": ["Incentives must be calibrated to protect gross margin contribution."],
                "source_modules": ["Sales Intelligence", "Customer Insights"],
                "source_module_link": "/sales?tab=customers",
                "what_is_happening": f"Average order size across repeat buyers stands at ₹{aov:,.2f}.",
                "why_it_matters": "Frequent small orders multiply logistics, billing, and packaging costs compared to consolidated orders.",
                "root_cause": "Absence of structured incentives that reward clients for ordering in larger economic batches.",
                "missed_opportunity": "15-25% increase in order values without requiring new customer acquisition.",
                "action_scenario": "Consolidated order batches increase cash flow predictability and reduce administrative overhead.",
                "cost_of_inaction": "Continued high packaging and handling costs for small, piecemeal orders.",
                "measurement_kpis": ["Average Order Value (AOV)", "Repeat order interval", "Net contribution margin %"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires verifying unit margins to ensure volume discounts remain accretive."],
            })

        # ---------------------------------------------------------------------
        # Category 2: Cost Optimization
        # ---------------------------------------------------------------------
        # Rule 2.1: Low Volume SKU Review
        if sales.has_sales_data and prod.fast_moving_products_by_volume and prod.total_products >= 2:
            tot_vol = sales.total_quantity
            low_skus = [p for p in reversed(prod.fast_moving_products_by_volume) if tot_vol > 0 and (p.get("total_quantity_sold", 0) / tot_vol) < 0.05][:3]
            if low_skus:
                low_names = ", ".join(f"'{s.get('product_name')}'" for s in low_skus)
                candidates.append({
                    "id": f"rec_RULE_COST_SLOW_SKU_REVIEW_{biz_id}_GLOBAL_v1",
                    "title": "Review Sales Performance of Low-Volume SKUs",
                    "category": RecommendationCategory.COST_OPTIMIZATION,
                    "description": (
                        f"Identified low-volume product(s) ({low_names}) "
                        "contributing less than 5% of sales volume. Review product turnover and customer purchasing frequency to inform future production and merchandising decisions."
                    ),
                    "business_context": f"Business currently offers {prod.total_products} active SKUs.",
                    "evidence": [
                        f"{len(low_skus)} SKU(s) identified with less than 5% volume contribution.",
                        f"Target SKUs: {low_names}.",
                    ],
                    "reasoning": "Reviewing low-velocity lines prevents unneeded capital allocation and operational distraction.",
                    "recommended_actions": [
                        "Review sales order frequency and customer reorder rates for identified low-volume SKUs.",
                        "Assess whether these SKUs are seasonal or complementary to core products before adjusting sourcing.",
                        "Consider promotional bundling with fast-moving items if looking to stimulate demand.",
                    ],
                    "action_plan": ActionPlan(
                        objective="Review low-velocity SKUs and redirect resources to high-performing product lines",
                        suggested_timeframe="30 Days",
                        success_metric="Complete sales and customer demand review for all low-volume SKUs",
                        steps=[
                            ActionStep(
                                step_number=1,
                                title="Audit Sales Records",
                                description="Review monthly sales trends and buyer feedback for low-volume SKUs.",
                                timeframe="Day 1-7",
                                resources_required="Sales order records",
                            ),
                            ActionStep(
                                step_number=2,
                                title="Assess Merchandising Strategy",
                                description="Decide whether to bundle, discount, or phase out low-volume products.",
                                timeframe="Day 8-20",
                                resources_required="Product catalog, pricing guidelines",
                            ),
                        ],
                    ),
                    "expected_benefit": "Closer alignment between customer demand and operational focus.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 65,
                    "impact": 65,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 95.0,
                    "feasibility": 80,
                    "data_quality": "High",
                    "limitations": ["UrsBiz does not track inventory balances, carrying costs, or warehouse space. Recommendations are limited to sales volume review; do not take liquidation or restocking actions without physical count."],
                    "source_modules": ["Sales Intelligence", "Product Insights"],
                    "source_module_link": "/sales?tab=products",
                    "what_is_happening": f"Identified low-volume product(s) ({low_names}) contributing under 5% of unit turnover.",
                    "why_it_matters": "Tying up working capital and warehouse attention in non-moving items.",
                    "root_cause": "Catalog expansion without active lifecycle rationalization.",
                    "missed_opportunity": "Reallocating operating cash to faster-turning, high-demand SKUs.",
                    "action_scenario": "Leaner product portfolio with faster inventory rotation.",
                    "cost_of_inaction": "Continued storage overhead, obsolescence risk, and wasted marketing effort.",
                    "measurement_kpis": ["Slow SKU volume contribution %", "Active catalog velocity"],
                    "implementation_difficulty": "Tactical",
                    "prerequisites_and_tradeoffs": ["Audit customer demand before deciding to phase out or bundle."],
                })

        # ---------------------------------------------------------------------
        # Category 3: Customer Retention
        # ---------------------------------------------------------------------
        # Rule 3.1: Inactive Repeat Customer Re-engagement
        if sales.has_sales_data and cust.declining_customers:
            inact_count = len(cust.declining_customers)
            inact_sample = ", ".join(f"'{c.get('customer_name')}'" for c in cust.declining_customers[:3])
            hist_val = sum(c.get("total_revenue", 0.0) for c in cust.declining_customers)
            candidates.append({
                "id": f"rec_RULE_RETENTION_INACTIVE_BUYER_REENGAGEMENT_{biz_id}_GLOBAL_v1",
                "title": f"Re-Engage {inact_count} Inactive Repeat Customer(s)",
                "category": RecommendationCategory.CUSTOMER_RETENTION,
                "description": (
                    f"{inact_count} customer(s) with previous repeat purchase history ({inact_sample}) "
                    "have not placed an order in over 60 days. Proactive relationship outreach can help uncover customer needs and prevent churn."
                ),
                "business_context": f"Customer base includes {cust.repeat_customers} repeat buyers out of {cust.total_customers} total.",
                "evidence": [
                    f"{inact_count} repeat customer(s) inactive for >60 days.",
                    f"Combined historical purchase value from these accounts: ₹{hist_val:,.2f} (historical context only).",
                    f"Repeat customer share: {cust.repeat_rate_pct}%.",
                ],
                "reasoning": "Re-engaging proven customers who already know your business is more efficient than cold customer acquisition.",
                "recommended_actions": [
                    f"Conduct direct relationship check-ins with key lapsed accounts ({inact_sample}).",
                    "Gather feedback on product satisfaction, delivery timelines, or changing operational requirements.",
                    "Establish a structured 30-to-45 day follow-up cadence after major order fulfillments.",
                ],
                "action_plan": ActionPlan(
                    objective="Reactivate lapsed buyers and establish recurring repurchase cadence",
                    suggested_timeframe="21 Days",
                    success_metric="Conduct outreach to 100% of inactive repeat customers",
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
                "expected_benefit": "Re-engagement of proven buyers and qualitative insight into customer drop-off drivers.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 85,
                "impact": 85,
                "evidence_strength": sales_ev_strength,
                "confidence": 95.0,
                "feasibility": 85,
                "data_quality": "High",
                "limitations": ["Historical spend represents past turnover only and is not guaranteed recoverable revenue."],
                "source_modules": ["Sales Intelligence", "Customer Insights"],
                "source_module_link": "/sales?tab=customers",
                "what_is_happening": f"{inact_count} repeat accounts have placed zero orders in over 60 days.",
                "why_it_matters": "Losing repeat accounts forces high acquisition expenses for replacement buyers.",
                "root_cause": "Post-purchase contact drop-off; lack of recurring follow-up touchpoint.",
                "missed_opportunity": "Reclaiming stable recurring purchase cycles from known accounts.",
                "action_scenario": "Reactivating 20-30% of lapsed buyers stabilizes monthly baseline.",
                "cost_of_inaction": "Permanent buyer defection to competitors and escalating customer acquisition spend.",
                "measurement_kpis": ["Lapsed customer reactivation rate %", "Customer repurchase interval (days)"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires phone/WhatsApp outreach; ensure adequate staff capacity to fulfill reorders."],
            })

        # Rule 3.2: Top-Tier Account VIP Retention Protocol
        if sales.has_sales_data and cust.top_customers_by_revenue and cust.repeat_customers >= 1:
            top_client = cust.top_customers_by_revenue[0]
            top_name = top_client.get("customer_name") or "Primary Client"
            top_rev = top_client.get("total_revenue", 0.0)
            candidates.append({
                "id": f"rec_RULE_RETENTION_TOP_TIER_VIP_SERVICE_{biz_id}_GLOBAL_v1",
                "title": f"Establish Priority Service & Review Protocol for Top Account '{top_name}'",
                "category": RecommendationCategory.CUSTOMER_RETENTION,
                "description": (
                    f"'{top_name}' is your largest individual revenue contributor (₹{top_rev:,.2f}). "
                    "Institute a monthly executive check-in, priority order processing, and customized terms to lock in relationship loyalty."
                ),
                "business_context": f"Top account contributes significant share of recorded revenue ₹{sales.total_revenue:,.2f}.",
                "evidence": [
                    f"Top customer revenue: ₹{top_rev:,.2f} (historical context only).",
                    f"Total recorded business revenue: ₹{sales.total_revenue:,.2f}.",
                    f"Account relationship: Top-ranked revenue contributor.",
                ],
                "reasoning": "Retaining anchor clients is the single highest ROI retention activity for growing MSMEs.",
                "recommended_actions": [
                    f"Schedule a bi-monthly operational review with the purchasing lead at '{top_name}'.",
                    "Offer guaranteed 48-hour order dispatch and flexible credit terms within credit limits.",
                    "Anticipate their quarterly procurement calendar to reserve production capacity.",
                ],
                "expected_benefit": "Zero churn risk on flagship revenue stream and multi-quarter order visibility.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 75,
                "impact": 90,
                "evidence_strength": sales_ev_strength,
                "confidence": 95.0,
                "feasibility": 90,
                "data_quality": "High",
                "limitations": [
                    "Requires senior management or owner time to personally nurture the relationship.",
                    "Past client turnover represents historical spend only; retention is not guaranteed without active service agreements.",
                ],
                "source_modules": ["Sales Intelligence", "Customer Insights"],
                "source_module_link": "/sales?tab=customers",
                "what_is_happening": f"'{top_name}' represents a major revenue pillar for your enterprise.",
                "why_it_matters": "Losing this relationship would directly threaten ongoing payroll and vendor commitments.",
                "root_cause": "Transactional interactions without formalized executive relationship management.",
                "missed_opportunity": "Deepening share-of-wallet with your largest customer.",
                "action_scenario": "Guarantees contract renewal and preferred supplier status for upcoming financial cycles.",
                "cost_of_inaction": "Competitor inroads through targeted discounts or aggressive sales poaching.",
                "measurement_kpis": ["Anchor client retention %", "On-time delivery fulfillment rate", "Client satisfaction score"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires executive time investment from owner."],
            })

        # ---------------------------------------------------------------------
        # Category 4: Product Performance
        # ---------------------------------------------------------------------
        # Rule 4.1: Product Concentration Rebalance
        if sales.has_sales_data and prod.top_products_by_revenue and sales.total_revenue > 0 and prod.total_products > 1:
            top_pct = round((prod.top_products_by_revenue[0].get("total_revenue", 0) / sales.total_revenue) * 100, 1)
            if top_pct >= 60:
                candidates.append({
                    "id": f"rec_RULE_PROD_PORTFOLIO_CONCENTRATION_REBALANCE_{biz_id}_GLOBAL_v1",
                    "title": "Balance Product Portfolio to Reduce Single-SKU Reliance",
                    "category": RecommendationCategory.PRODUCT_PERFORMANCE,
                    "description": (
                        f"A single product generates {top_pct}% of total sales revenue. "
                        "Actively promote secondary SKUs to establish a diversified, balanced product portfolio."
                    ),
                    "business_context": f"Business currently offers {prod.total_products} product SKU(s).",
                    "evidence": [
                        f"Single product concentration: {top_pct}% of total revenue.",
                        f"Catalog breadth: {prod.total_products} total SKUs.",
                    ],
                    "reasoning": "Over-reliance on one product leaves operations vulnerable to competitor moves or supply disruptions.",
                    "recommended_actions": [
                        "Review gross margins of tier-2 products and adjust merchandising priority.",
                        "Feature high-margin secondary products prominently in customer quotes and catalogs.",
                    ],
                    "expected_benefit": "Resilient product sales mix with reduced single-point supply vulnerability.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 70,
                    "impact": 70,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 95.0,
                    "feasibility": 75,
                    "data_quality": "High",
                    "limitations": ["Market demand for secondary SKUs must be verified through small-scale promotion."],
                    "source_modules": ["Sales Intelligence", "Product Insights"],
                    "source_module_link": "/sales?tab=products",
                    "what_is_happening": f"Leading single SKU represents {top_pct}% of all product turnover.",
                    "why_it_matters": "Any supply bottleneck or competitor discount in this category threatens company solvency.",
                    "root_cause": "Historical marketing focused exclusively on the fastest seller without cross-promoting catalog depth.",
                    "missed_opportunity": "Building a balanced portfolio with 2-3 reliable revenue engines.",
                    "action_scenario": "Diversifies product turnover and cushions margins against single-category demand swings.",
                    "cost_of_inaction": "Acute enterprise risk if substitute products enter the market.",
                    "measurement_kpis": ["Single-SKU revenue share %", "Secondary SKU monthly growth %"],
                    "implementation_difficulty": "Tactical",
                    "prerequisites_and_tradeoffs": ["Requires small marketing budget or sales rep reorientation toward secondary lines."],
                })

        # ---------------------------------------------------------------------
        # Category 5: Demand and Sales Planning
        # ---------------------------------------------------------------------
        if forecast.has_forecast_data and forecast.product_forecasts:
            # Rule 5.1: Demand Surge Preparation
            surging = [p for p in forecast.product_forecasts if p.demand_trend == "Increasing"]
            if surging:
                lead_grower = surging[0]
                lead_id = lead_grower.product_id or "sku"
                p_units = round(lead_grower.forecasted_units_total, 1)
                p_horizon = lead_grower.forecast_horizon_periods
                p_model = lead_grower.selected_model
                p_rel = lead_grower.reliability
                p_mae = lead_grower.best_mae
                delta_str = f" ({lead_grower.trend_delta_pct:+.1f}%)" if lead_grower.trend_delta_pct is not None else ""
                candidates.append({
                    "id": f"rec_RULE_DEMAND_SURGE_PREPARATION_{biz_id}_{lead_id}_v1",
                    "title": f"Review Supply Capacity for Projected Demand Increase in '{lead_grower.product_name}'",
                    "category": RecommendationCategory.DEMAND_PLANNING,
                    "description": (
                        f"Demand forecasting ({p_model}) projects {p_units} units for '{lead_grower.product_name}' "
                        f"over the coming {p_horizon} periods ({lead_grower.demand_trend}{delta_str}). Review supplier ordering schedules and delivery lead times to prepare for projected volume changes."
                    ),
                    "business_context": f"Evaluated with {p_rel} reliability grade based on historical sales transactions.",
                    "evidence": [
                        f"Forecasted demand: {p_units} units across next {p_horizon} periods.",
                        f"Selected forecast model: {p_model} (Backtest MAE: {p_mae}).",
                        f"Trend direction: {lead_grower.demand_trend}{delta_str}.",
                        f"Reliability grade: {p_rel}.",
                    ],
                    "reasoning": "Proactively assessing supply arrangements prevents fulfillment bottlenecks when demand expands.",
                    "recommended_actions": [
                        f"Review upcoming sales trajectory and verify historical supplier delivery times for '{lead_grower.product_name}'.",
                        "Engage key suppliers to confirm material availability for projected demand growth.",
                        "Monitor weekly sales orders to confirm whether actual demand aligns with projected trajectory.",
                    ],
                    "action_plan": ActionPlan(
                        objective=f"Align operational capacity with projected {p_units} unit demand trend",
                        suggested_timeframe="2-4 Weeks",
                        success_metric="Supplier capacity confirmed for upcoming forecast periods",
                        steps=[
                            ActionStep(
                                step_number=1,
                                title="Review Demand Forecast Details",
                                description="Inspect monthly projected run-rate and model reliability in Sales Forecast dashboard.",
                                timeframe="Days 1-3",
                                resources_required="Sales Forecast Dashboard",
                            ),
                            ActionStep(
                                step_number=2,
                                title="Supplier Capacity Check-In",
                                description="Contact raw material or finished goods suppliers to verify lead-time flexibility.",
                                timeframe="Days 4-10",
                                resources_required="Supplier agreement / communications",
                            ),
                        ],
                    ),
                    "expected_benefit": "Smooth fulfillment of upcoming customer orders without supply bottlenecks.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 80 if p_rel == "High" else 70,
                    "impact": 85,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 90.0 if p_rel == "High" else (75.0 if p_rel == "Moderate" else 60.0),
                    "feasibility": 80,
                    "data_quality": "High" if p_rel == "High" else "Moderate",
                    "limitations": (lead_grower.limitation_notes or []) + ["UrsBiz does not observe warehouse inventory, reorder quantities, or stockout dates; recommendations are limited to demand trend review."],
                    "source_modules": ["Demand Forecasting"],
                    "source_module_link": "/sales?tab=forecast",
                    "what_is_happening": f"Demand for '{lead_grower.product_name}' is projected to increase ({p_units} units over next {p_horizon} periods).",
                    "why_it_matters": "Failing to verify supplier capacity ahead of time results in stockouts and delayed customer fulfillment.",
                    "root_cause": "Positive seasonal or market trajectory identified by backtested forecasting models.",
                    "missed_opportunity": "Fulfilling surge demand fully and capturing market share from slower competitors.",
                    "action_scenario": "Synchronizing supply schedules guarantees on-time order fulfillment without rush freight charges.",
                    "cost_of_inaction": "Missed sales orders, dissatisfied buyers, and negative word-of-mouth.",
                    "measurement_kpis": ["Order fill rate %", "Supplier lead-time adherence", "Forecast vs actual sales tracking"],
                    "implementation_difficulty": "Tactical",
                    "prerequisites_and_tradeoffs": ["Review supplier minimum order quantities and terms."],
                })

            # Rule 5.2: Demand Decline Monitoring
            declining = [p for p in forecast.product_forecasts if p.demand_trend == "Decreasing"]
            if declining:
                lead_decliner = declining[0]
                p_units = round(lead_decliner.forecasted_units_total, 1)
                p_horizon = lead_decliner.forecast_horizon_periods
                p_model = lead_decliner.selected_model
                p_rel = lead_decliner.reliability
                candidates.append({
                    "id": f"rec_RULE_DEMAND_DECLINE_MONITORING_{biz_id}_{lead_decliner.product_id or 'sku'}_v1",
                    "title": f"Monitor Sales Pace for Declining Demand in '{lead_decliner.product_name}'",
                    "category": RecommendationCategory.DEMAND_PLANNING,
                    "description": (
                        f"Demand for '{lead_decliner.product_name}' is trending downward with {p_units} units "
                        f"projected across the next {p_horizon} periods. Assess market, pricing, and competitive factors behind the contraction."
                    ),
                    "business_context": f"Identified via backtesting with {p_rel} reliability grade.",
                    "evidence": [
                        f"Projected demand: {p_units} units ({lead_decliner.demand_trend} trend).",
                        f"Selected forecasting model: {p_model}.",
                        f"Backtest error: MAE {lead_decliner.best_mae}.",
                    ],
                    "reasoning": "Understanding contraction drivers early helps adjust marketing focus and prevent unnecessary production commitments.",
                    "recommended_actions": [
                        f"Assess market and competitive factors behind demand contraction for '{lead_decliner.product_name}'.",
                        "Review pricing elasticity and customer feedback regarding this SKU.",
                    ],
                    "expected_benefit": "Avoidance of surplus procurement and strategic reallocation of sales attention.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 75,
                    "impact": 70,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 85.0 if p_rel == "High" else 75.0,
                    "feasibility": 85,
                    "data_quality": "Moderate",
                    "limitations": (lead_decliner.limitation_notes or []) + ["UrsBiz does not calculate inventory write-downs or order cancellations. Recommends reviewing sales performance and customer demand drivers."],
                    "source_modules": ["Demand Forecasting"],
                    "source_module_link": "/sales?tab=forecast",
                    "what_is_happening": f"Demand for '{lead_decliner.product_name}' shows downward momentum ({p_units} units over next {p_horizon} periods).",
                    "why_it_matters": "Over-ordering materials for a contracting product line ties up critical working capital.",
                    "root_cause": "Shifting customer preferences or seasonal cyclicality detected by predictive analytics.",
                    "missed_opportunity": "Proactively redirecting promotional focus and purchasing capital to expanding product lines.",
                    "action_scenario": "Minimizes dead stock and aligns procurement with verified demand run-rates.",
                    "cost_of_inaction": "Excess inventory accumulation and margin erosion from distress discounting.",
                    "measurement_kpis": ["Product unit run-rate", "Customer reorder frequency", "Gross margin contribution %"],
                    "implementation_difficulty": "Tactical",
                    "prerequisites_and_tradeoffs": ["Verify whether contraction is temporary or structural before modifying agreements."],
                })

            # Rule 5.3: Intermittent Demand Review
            intermittent = [
                p for p in forecast.product_forecasts
                if p.demand_trend == "Intermittent" or "croston" in (p.selected_model or "").lower()
            ]
            if intermittent:
                lead_intermittent = intermittent[0]
                p_units = round(lead_intermittent.forecasted_units_total, 1)
                p_horizon = lead_intermittent.forecast_horizon_periods
                p_model = lead_intermittent.selected_model
                p_rel = lead_intermittent.reliability
                candidates.append({
                    "id": f"rec_RULE_DEMAND_INTERMITTENT_BUFFER_REVIEW_{biz_id}_{lead_intermittent.product_id or 'sku'}_v1",
                    "title": f"Evaluate Demand Frequency for Intermittent SKU '{lead_intermittent.product_name}'",
                    "category": RecommendationCategory.DEMAND_PLANNING,
                    "description": (
                        f"Demand for '{lead_intermittent.product_name}' is intermittent ({p_model}). "
                        "Focus on buyer order intervals and batching patterns rather than relying on uniform monthly run-rates."
                    ),
                    "business_context": f"Evaluated under intermittent baseline with {p_rel} reliability.",
                    "evidence": [
                        f"Selected forecasting model: {p_model} (Intermittent demand rate).",
                        f"Projected demand: {p_units} units over {p_horizon} periods.",
                        f"Reliability grade: {p_rel}.",
                    ],
                    "reasoning": "Intermittent demand items experience sporadic orders separated by multiple zero-sales periods; applying linear replenishment leads to misallocated resources.",
                    "recommended_actions": [
                        "Engage key institutional or wholesale buyers for advance order indications.",
                        "Review historical order gap intervals to estimate irregular purchasing cycles.",
                    ],
                    "expected_benefit": "Prudent operational planning aligned with irregular purchasing cycles.",
                    "estimated_impact": None,
                    "impact_unit": None,
                    "urgency": 65,
                    "impact": 65,
                    "evidence_strength": sales_ev_strength,
                    "confidence": 75.0,
                    "feasibility": 80,
                    "data_quality": "Moderate",
                    "limitations": (lead_intermittent.limitation_notes or []) + ["Intermittent demand exhibits irregular order timing; point forecasts reflect average period demand rather than guaranteed order dates. UrsBiz does not calculate reorder points or safety stock."],
                    "source_modules": ["Demand Forecasting"],
                    "source_module_link": "/sales?tab=forecast",
                    "what_is_happening": f"'{lead_intermittent.product_name}' displays sporadic, irregular demand patterns.",
                    "why_it_matters": "Linear periodic ordering creates either chronic overstocking or sudden unfulfillable stockouts.",
                    "root_cause": "Institutional or batch-purchasing clients ordering large quantities separated by prolonged quiet periods.",
                    "missed_opportunity": "Establishing advance order commitments or reservation deposits with irregular buyers.",
                    "action_scenario": "Flexible, order-driven procurement protects cash flow while servicing sporadic demand profitably.",
                    "cost_of_inaction": "Capital trapped in stagnant stock during quiet intervals.",
                    "measurement_kpis": ["Intermittent order frequency", "Average batch size", "Order lead time"],
                    "implementation_difficulty": "Tactical",
                    "prerequisites_and_tradeoffs": ["Requires direct communication with bulk institutional purchasers."],
                })

        # ---------------------------------------------------------------------
        # Category 6: Digital Transformation
        # ---------------------------------------------------------------------
        # Rule 6.1: Digital Storefront Presence
        if not profile.has_website or not profile.has_ecommerce:
            candidates.append({
                "id": f"rec_RULE_DIGITAL_STOREFRONT_PRESENCE_{biz_id}_GLOBAL_v1",
                "title": "Establish Official Online Presence and Digital Order Channel",
                "category": RecommendationCategory.DIGITAL_TRANSFORMATION,
                "description": (
                    f"Your business currently lacks an active web presence or digital order channel in {profile.industry}. "
                    "Launching a digital storefront enables inbound buyer discovery beyond local geographic boundaries."
                ),
                "business_context": f"Business stage: {profile.business_stage}, Location: {profile.city or 'Domestic market'}.",
                "evidence": [
                    "No verified website URL recorded in business profile.",
                    "No e-commerce order intake integration configured.",
                    f"Digital health facet score: {round(health.overall_score * 0.10, 1)}/10 points.",
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
                "evidence_strength": 80,
                "confidence": 95.0,
                "feasibility": 85,
                "data_quality": "High",
                "limitations": ["Requires periodic maintenance to keep product availability up to date."],
                "source_modules": ["Business Profile", "Digital Health"],
                "source_module_link": "/business",
                "what_is_happening": "Business currently has no verified digital storefront or e-commerce ordering channel.",
                "why_it_matters": "B2B and retail buyers verify credibility online; absence limits reach to local physical contacts.",
                "root_cause": "Traditional reliance on offline foot-traffic and word-of-mouth.",
                "missed_opportunity": "Inbound discovery from buyers searching online across regional and national markets.",
                "action_scenario": "A 24/7 digital product showcase and instant inquiry channel expands inbound customer acquisition.",
                "cost_of_inaction": "Steady loss of emerging buyers who discover and order from digitally enabled competitors.",
                "measurement_kpis": ["Website visitor inquiries", "Digital lead conversions", "Digital Twin Health Score"],
                "implementation_difficulty": "Tactical",
                "prerequisites_and_tradeoffs": ["Initial setup investment in domain, photography, and catalog copywriting."],
            })

        # ---------------------------------------------------------------------
        # Category 7: Financial Management
        # ---------------------------------------------------------------------
        # Rule 7.1: Financial Recordkeeping Formalization
        if not profile.annual_revenue or profile.annual_revenue <= 0 or "annual_revenue" in health.missing_fields:
            candidates.append({
                "id": f"rec_RULE_FIN_RECORDKEEPING_FORMALIZATION_{biz_id}_GLOBAL_v1",
                "title": "Formalize Financial Invoicing & Accounting Records",
                "category": RecommendationCategory.FINANCIAL_MANAGEMENT,
                "description": (
                    "Annual turnover or formal financial indicators are missing from your business profile. "
                    "Maintaining standardized cloud accounting records is mandatory for institutional credit evaluation and tax compliance."
                ),
                "business_context": f"Business entity operating in {profile.industry} established in {profile.established_year or 'recent years'}.",
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
                "evidence_strength": 80,
                "confidence": 90.0,
                "feasibility": 80,
                "data_quality": "Limited",
                "limitations": ["Software implementation requires initial ledger setup time."],
                "source_modules": ["Business Profile", "Health Score"],
                "source_module_link": "/business",
                "what_is_happening": "Business profile does not have verified annual turnover or formalized accounting records.",
                "why_it_matters": "Inability to present formal financial records blocks bank credit, subsidies, and investor confidence.",
                "root_cause": "Ad-hoc paper billing and informal transaction tracking.",
                "missed_opportunity": "Securing low-interest bank working capital lines and statutory tax deductions.",
                "action_scenario": "Formalized books enable instant credit appraisal and accurate gross margin tracking.",
                "cost_of_inaction": "Severe credit rationing, tax audit penalties, and blind operational spending.",
                "measurement_kpis": ["Financial readiness score", "Accounting software adoption", "Monthly reconciliation cadence"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires small monthly software subscription and basic staff training."],
            })
        elif sales.has_sales_data and sales.total_revenue > 0:
            # Rule 7.2: Working Capital Acceleration via Payment Terms & Early Settlement Incentives
            candidates.append({
                "id": f"rec_RULE_FIN_PAYMENT_TERMS_ACCELERATION_{biz_id}_GLOBAL_v1",
                "title": "Establish Standardized Payment Terms (Net-30) & 2% Quick-Pay Incentive",
                "category": RecommendationCategory.FINANCIAL_MANAGEMENT,
                "description": (
                    "Managing commercial cash flow requires strict credit terms. "
                    "Institute formal Net-30 payment milestones with a 2% early settlement discount (2/10 Net 30) to accelerate accounts receivable collection."
                ),
                "business_context": f"Total sales throughput: ₹{sales.total_revenue:,.2f} across {sales.total_transactions} orders.",
                "evidence": [
                    f"Recorded transactions: {sales.total_transactions} orders.",
                    f"Total sales volume: ₹{sales.total_revenue:,.2f}.",
                    f"Customer concentration: {cust.total_customers} tracked accounts.",
                ],
                "reasoning": "Unstructured payment terms lead to creeping receivable days (DSO), forcing business owners to borrow expensive emergency capital.",
                "recommended_actions": [
                    "Specify payment milestones (50% deposit, balance Net-30) on all written quotes and invoices.",
                    "Offer 2% cash discount for invoice settlement within 10 days of delivery.",
                    "Set up automated WhatsApp/email invoice reminders on Day 21 and Day 28.",
                ],
                "expected_benefit": "Faster cash conversion cycle, reduced debtor aging, and lower reliance on overdraft facilities.",
                "estimated_impact": None,
                "impact_unit": None,
                "urgency": 75,
                "impact": 80,
                "evidence_strength": sales_ev_strength,
                "confidence": 92.0,
                "feasibility": 85,
                "data_quality": "High",
                "limitations": ["Requires buyer agreement; larger enterprise buyers may mandate their standard 60-90 day procurement cycles."],
                "source_modules": ["Sales Intelligence", "Financial Health"],
                "source_module_link": "/sales",
                "what_is_happening": "Sales orders are fulfilled without standardized payment milestones or automated collection reminders.",
                "why_it_matters": "Delayed buyer payments choke working capital and prevent timely restocking and payroll.",
                "root_cause": "Informal credit granted without clear written milestone terms or early payment incentives.",
                "missed_opportunity": "Accelerating cash conversion cycle by 15-25 days without bank financing costs.",
                "action_scenario": "Predictable weekly cash inflows and reduced bad debt risk.",
                "cost_of_inaction": "Working capital crunch forcing emergency high-interest borrowing or supplier payment defaults.",
                "measurement_kpis": ["Days Sales Outstanding (DSO)", "On-time invoice payment %", "Cash conversion cycle (days)"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires updating invoice templates and communicating terms clearly before order acceptance."],
            })

        # ---------------------------------------------------------------------
        # Category 8: Operational Efficiency
        # ---------------------------------------------------------------------
        # Rule 8.1: Sales Ingestion Prompt
        if not sales.has_sales_data:
            candidates.append({
                "id": f"rec_RULE_OPS_SALES_DATA_INGESTION_{biz_id}_GLOBAL_v1",
                "title": "Upload Historical Sales Data to Unlock Predictive Intelligence",
                "category": RecommendationCategory.OPERATIONAL_EFFICIENCY,
                "description": (
                    "No historical sales records have been uploaded for your business. "
                    "Ingesting transaction CSV or Excel spreadsheets activates automatic customer churn tracking, product Pareto analysis, and demand forecasting."
                ),
                "business_context": f"Profile health score is {health.overall_score}/100. Sales Intelligence module is currently inactive.",
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
                "evidence_strength": 50,
                "confidence": 95.0,
                "feasibility": 95,
                "data_quality": "Insufficient",
                "limitations": ["Supported formats: CSV, XLSX up to 10MB."],
                "source_modules": ["Sales Intelligence", "System Audit"],
                "source_module_link": "/sales?tab=upload",
                "what_is_happening": "UrsBiz has zero recorded sales transactions for this business profile.",
                "why_it_matters": "All predictive algorithms, churn detectors, and inventory demand planning modules remain locked.",
                "root_cause": "Sales ledger has not been exported or uploaded into the UrsBiz ingestion pipeline.",
                "missed_opportunity": "Automated detection of customer drop-offs, bestsellers, and predictive growth trajectories.",
                "action_scenario": "Unlocks complete predictive analytics, AI explanation briefs, and What-If scenario simulations.",
                "cost_of_inaction": "Operating business decisions on intuition rather than verified sales intelligence.",
                "measurement_kpis": ["Ingested transaction records", "Coverage date range (days)", "Sales Intelligence status"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["Requires exporting invoice CSV/Excel from current billing system."],
            })
        elif health.missing_fields and len(health.missing_fields) > 2:
            # Rule 8.2: Profile Completion
            missing_clean = ", ".join(f.replace("_", " ").title() for f in health.missing_fields[:4])
            candidates.append({
                "id": f"rec_RULE_OPS_PROFILE_COMPLETION_{biz_id}_GLOBAL_v1",
                "title": "Complete Digital Twin Profile to Sharpen Recommendation Accuracy",
                "category": RecommendationCategory.OPERATIONAL_EFFICIENCY,
                "description": (
                    f"Your Business Digital Twin profile is missing key fields: {missing_clean}. "
                    "Completing these operational details improves government scheme eligibility matching and AI advisor precision."
                ),
                "business_context": f"Health score is currently {health.overall_score}/100 with {len(health.missing_fields)} unpopulated field(s).",
                "evidence": [
                    f"Overall health score: {health.overall_score}/100.",
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
                "evidence_strength": 80,
                "confidence": 95.0,
                "feasibility": 90,
                "data_quality": "Moderate",
                "limitations": ["Self-reported profile data."],
                "source_modules": ["Business Profile", "Health Score"],
                "source_module_link": "/business",
                "what_is_happening": f"Digital Twin profile is missing key operational attributes ({missing_clean}).",
                "why_it_matters": "Incomplete data restricts accurate government subsidy matching and strategic AI reasoning.",
                "root_cause": "Initial onboarding completed with only basic registration fields.",
                "missed_opportunity": "Unlocking high-matching public grants and targeted sector recommendations.",
                "action_scenario": "Reaching 90%+ completeness activates tailored compliance and subsidy opportunities.",
                "cost_of_inaction": "Missing out on eligible government schemes and lower accuracy in automated health diagnostics.",
                "measurement_kpis": ["Digital Twin Completeness %", "Health Score", "Scheme match count"],
                "implementation_difficulty": "Quick Win",
                "prerequisites_and_tradeoffs": ["10-15 minutes of administrative time to input operating details."],
            })

        # ---------------------------------------------------------------------
        # Category 9: Government Schemes and Funding
        # ---------------------------------------------------------------------
        # Rule 9.1: Criteria Match
        all_schemes = schemes.recommended_schemes + schemes.eligible_schemes
        if all_schemes:
            lead_scheme = all_schemes[0]
            candidates.append({
                "id": f"rec_RULE_SCHEME_CRITERIA_MATCH_{biz_id}_{lead_scheme.id}_v1",
                "title": f"Explore Matching Government Scheme: {lead_scheme.name}",
                "category": RecommendationCategory.GOVERNMENT_SCHEMES,
                "description": (
                    f"Your business profile matches the published parameters for '{lead_scheme.name}' "
                    f"administered by the {lead_scheme.official_authority}."
                ),
                "business_context": f"Matches based on industry '{profile.industry}', employee count ({profile.employee_count or 'N/A'}), and location '{profile.city or 'India'}'.",
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
                "what_is_happening": f"Profile matches eligibility parameters for {lead_scheme.name}.",
                "why_it_matters": "Subsidized government backing dramatically lowers the cost of capital and technology adoption.",
                "root_cause": "Public policies created specifically to foster MSME competitiveness in {profile.industry}.",
                "missed_opportunity": f"Benefiting from {', '.join(lead_scheme.benefits or ['subsidized financing'])} without commercial loan rates.",
                "action_scenario": "Approved application grants access to designated state benefits and concessionary finance.",
                "cost_of_inaction": "Paying unnecessary high commercial interest or bearing 100% of modernization costs out of pocket.",
                "measurement_kpis": ["Application submission acknowledgment", "Sanction letter turnaround", "Subsidy benefit received"],
                "implementation_difficulty": "Tactical",
                "prerequisites_and_tradeoffs": ["Requires active Udyam registration and clean GST filing compliance."],
            })

        # ---------------------------------------------------------------------
        # Category 10: Risk Reduction
        # ---------------------------------------------------------------------
        # Rule 10.1: Domestic Market Dependence
        if not profile.has_export_experience and profile.annual_revenue and profile.annual_revenue > 500000:
            candidates.append({
                "id": f"rec_RULE_RISK_DOMESTIC_DEPENDENCE_{biz_id}_GLOBAL_v1",
                "title": "Evaluate Cross-Border Export Readiness to Hedge Domestic Market Cycles",
                "category": RecommendationCategory.RISK_REDUCTION,
                "description": (
                    f"Your business generates healthy domestic turnover in {profile.industry} but operates with 100% domestic market dependence. "
                    "Obtaining an Importer-Exporter Code (IEC) and exploring export markets mitigates regional economic downturns."
                ),
                "business_context": f"Domestic revenue scale: ₹{profile.annual_revenue:,.2f}.",
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
                "what_is_happening": "Business is 100% reliant on local domestic demand without international market exposure.",
                "why_it_matters": "Domestic economic slowdowns or local tax changes directly impact total revenue with no geographic hedge.",
                "root_cause": "Perceived regulatory complexity of cross-border trade.",
                "missed_opportunity": "Higher export margins and foreign currency earnings across regional markets.",
                "action_scenario": "Securing export credentials allows bidding on international buyer requests and trade fairs.",
                "cost_of_inaction": "Complete exposure to domestic economic cycles and localized price wars.",
                "measurement_kpis": ["Export readiness score", "IEC registration status", "International buyer inquiries"],
                "implementation_difficulty": "Strategic",
                "prerequisites_and_tradeoffs": ["Requires IEC registration, GST LUT filing, and international shipping partner."],
            })

        # Freshness Enforcement (Phase 5 Data Integrity):
        # Stale sales data must NEVER silently support high-confidence recommendations.
        is_sales_stale = any(
            "Temporal Caution" in lim or "stale" in lim.lower() or "expired" in lim.lower()
            for lim in ctx.data_limitations
        )
        if is_sales_stale:
            for cand in candidates:
                sources = cand.get("source_modules", [])
                if "Sales Intelligence" in sources or "Customer Insights" in sources:
                    cand["confidence"] = min(65.0, float(cand.get("confidence", 70.0)))
                    cand["evidence_strength"] = min(45.0, float(cand.get("evidence_strength", 50.0)))
                    cand["data_quality"] = "Stale / Aging"
                    limits = cand.get("limitations", [])
                    stale_notice = "Temporal Caution: Sales data is aging (>30 days old); priority and confidence are downgraded until updated sales records are ingested."
                    if stale_notice not in limits:
                        limits.append(stale_notice)
                    cand["limitations"] = limits

        return candidates

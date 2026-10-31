"""Advanced Autonomous Business Opportunity Discovery Engine (Phase 5).

Upgrades UrsBiz from static predefined rules to an autonomous, evidence-backed
opportunity discovery engine that continuously analyzes the verified business context,
identifies meaningful multi-signal patterns, generates structured hypotheses, and validates
them against ground truth data.

Core Capabilities:
  1. Dynamic Multi-Signal Discovery: Analyzes revenue, products, customers, forecasts,
     health, digital readiness, and financial indicators across 12+ dimensions.
  2. Opportunity Hypothesis Generation: Produces structured hypotheses separating observed
     facts from inferred explanations, stating alternative explanations, and disclaiming
     that correlation does not prove causation.
  3. Strict Validation Pipeline: Verifies supporting data, checks freshness, confirms
     signal meaningfulness (suppresses noise), detects conflicting evidence, and checks
     whether already addressed/completed.
  4. Novelty & Stable Identity: Deterministic composite ID convention
     (rec_OPP_{category}_{biz}_{entity}_{issue}_v{version}) with evidence signature versioning.
  5. Discovery Beyond Existing Rules: Combines resilient Gemini-powered hypothesis synthesis
     with deterministic multi-signal pattern mining and backend numerical grounding.
  6. 5-Tier Quality Classification:
       - VERIFIED_OPPORTUNITY (Confidence >= 0.75, fresh data, no conflicts)
       - PROMISING_OPPORTUNITY (Confidence >= 0.55, solid evidence, minor gaps)
       - NEEDS_INVESTIGATION (Multi-signal ambiguity or partial conflict)
       - INSUFFICIENT_EVIDENCE (Below sample size / significance threshold -> suppressed)
       - NOT_ACTIONABLE (Stale data, already completed, or no lever -> suppressed)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional, Set

from app.schemas.advanced_recommendations import (
    OpportunityHypothesis,
    OpportunityItem,
    OpportunityQualityStatus,
    OpportunitySupportingSignal,
)
from app.schemas.recommendation_context import UnifiedRecommendationContext
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
)
from app.services.ai.resilient_client import ResilientGeminiClient

logger = logging.getLogger("atlas.recommendations.opportunity_discovery")


# --------------------------------------------------------------------------- #
# 1. Validation Engine
# --------------------------------------------------------------------------- #

class OpportunityValidationEngine:
    """Rigorous gatekeeper validating opportunity hypotheses against empirical business context."""

    def validate(
        self,
        hypothesis: OpportunityHypothesis,
        ctx: UnifiedRecommendationContext,
        active_rec_ids: Optional[Set[str]] = None,
        completed_rec_ids: Optional[Set[str]] = None,
    ) -> OpportunityHypothesis:
        """Execute the 7-step validation pipeline on a candidate hypothesis."""
        active_ids = active_rec_ids or set()
        completed_ids = completed_rec_ids or set()

        # Step 1: Check whether the opportunity has already been addressed or dismissed
        if hypothesis.id in completed_ids:
            hypothesis.quality_status = OpportunityQualityStatus.NOT_ACTIONABLE
            hypothesis.validation_status = "SUPPRESSED"
            hypothesis.limitations.append("Opportunity was already completed or addressed by the business owner.")
            return hypothesis

        # Step 2: Check whether duplicate already exists in active recommendation set
        if hypothesis.id in active_ids:
            hypothesis.validation_status = "DUPLICATE_ACTIVE"

        # Step 3: Check data freshness
        if not self._check_data_freshness(hypothesis, ctx):
            hypothesis.quality_status = OpportunityQualityStatus.NOT_ACTIONABLE
            hypothesis.validation_status = "SUPPRESSED"
            hypothesis.limitations.append("Supporting sales data is stale or expired; refresh ledger before acting.")
            return hypothesis

        # Step 4: Check signal meaningfulness (sample size, nonzero revenue, meaningful delta)
        is_meaningful, reason = self._check_signal_meaningfulness(hypothesis, ctx)
        if not is_meaningful:
            hypothesis.quality_status = OpportunityQualityStatus.INSUFFICIENT_EVIDENCE
            hypothesis.validation_status = "SUPPRESSED"
            hypothesis.limitations.append(f"Insufficient signal volume: {reason}")
            hypothesis.confidence = min(hypothesis.confidence, 0.40)
            return hypothesis

        # Step 5: Verify supporting empirical data
        data_verified, missing_data = self._verify_supporting_data(hypothesis, ctx)
        if not data_verified:
            hypothesis.missing_information.extend(missing_data)
            hypothesis.confidence = max(0.20, hypothesis.confidence - 0.25)

        # Step 6: Identify conflicting evidence / counter-signals
        conflicts = self._identify_conflicting_evidence(hypothesis, ctx)
        if conflicts:
            hypothesis.conflicting_signals.extend(conflicts)
            hypothesis.confidence = max(0.25, hypothesis.confidence - (0.20 * len(conflicts)))
            hypothesis.quality_status = OpportunityQualityStatus.NEEDS_INVESTIGATION
            hypothesis.validation_status = "FLAGGED"

        # Step 7: Final quality status assignment
        if hypothesis.quality_status not in (
            OpportunityQualityStatus.NOT_ACTIONABLE,
            OpportunityQualityStatus.INSUFFICIENT_EVIDENCE,
            OpportunityQualityStatus.NEEDS_INVESTIGATION,
        ):
            if hypothesis.confidence >= 0.75 and data_verified:
                hypothesis.quality_status = OpportunityQualityStatus.VERIFIED_OPPORTUNITY
                hypothesis.validation_status = "VALIDATED"
            elif hypothesis.confidence >= 0.55:
                hypothesis.quality_status = OpportunityQualityStatus.PROMISING_OPPORTUNITY
                hypothesis.validation_status = "VALIDATED"
            else:
                hypothesis.quality_status = OpportunityQualityStatus.NEEDS_INVESTIGATION
                hypothesis.validation_status = "FLAGGED"

        return hypothesis

    def _check_data_freshness(
        self, hypothesis: OpportunityHypothesis, ctx: UnifiedRecommendationContext
    ) -> bool:
        """Reject opportunities built on explicitly stale/expired transactional data."""
        # Only check sales freshness if the opportunity relies on sales or customer transactions
        relies_on_sales = any(
            "sales" in s.source_module.lower() or "customer" in s.source_module.lower()
            for s in hypothesis.supporting_signals
        ) or hypothesis.category.lower() in (
            "product portfolio optimization",
            "customer retention",
            "demand planning",
        )

        if not relies_on_sales:
            return True

        for lim in ctx.data_limitations:
            if "expired" in lim.lower() or "stale data" in lim.lower():
                return False
        return True

    def _check_signal_meaningfulness(
        self, hypothesis: OpportunityHypothesis, ctx: UnifiedRecommendationContext
    ) -> tuple[bool, str]:
        """Ensure signals exceed minimum threshold to avoid recommending on noise."""
        cat = hypothesis.category.lower()

        # Customer / retention opportunities require at least 2 customers
        if "customer" in cat or "retention" in cat or "diversification" in cat:
            if ctx.customers.total_customers < 2:
                return False, f"Total customer count ({ctx.customers.total_customers}) is too low for segmentation."

        # Product / revenue opportunities require nonzero sales and at least 1 product
        if "product" in cat or "revenue" in cat:
            if not ctx.sales.has_sales_data or ctx.sales.total_revenue <= 0:
                return False, "No verified revenue history to ground product or revenue opportunities."
            if ctx.products.total_products < 1:
                return False, "Product catalog contains zero recorded items."

        # Demand forecasting opportunities require forecast intelligence
        if "demand" in cat or "forecast" in cat:
            if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
                return False, "No forecast trajectory data available for demand alignment."

        return True, "Signal volume satisfies baseline criteria."

    def _verify_supporting_data(
        self, hypothesis: OpportunityHypothesis, ctx: UnifiedRecommendationContext
    ) -> tuple[bool, list[str]]:
        """Verify that cited metrics correspond to empirical ground truth in context."""
        missing: list[str] = []

        for sig in hypothesis.supporting_signals:
            mod = sig.source_module.lower()
            if "sales" in mod and not ctx.sales.has_sales_data:
                missing.append("Sales ledger records are not present.")
            elif "customer" in mod and ctx.customers.total_customers == 0:
                missing.append("Customer records are empty.")
            elif "forecast" in mod and not ctx.forecast.has_forecast_data:
                missing.append("Demand forecasting models have not run.")
            elif "schemes" in mod and not ctx.schemes.recommended_schemes:
                missing.append("No government scheme matches found.")

        return len(missing) == 0, missing

    def _identify_conflicting_evidence(
        self, hypothesis: OpportunityHypothesis, ctx: UnifiedRecommendationContext
    ) -> list[str]:
        """Detect counter-signals that weaken the opportunity hypothesis."""
        conflicts: list[str] = []
        prob = hypothesis.business_problem_or_opportunity.lower()
        title = hypothesis.title.lower()

        # 1. Product decline vs Forecast surge conflict
        if "underperforming" in prob or "declining" in title:
            entity = (hypothesis.relevant_entity or "").lower()
            for pf in ctx.forecast.product_forecasts:
                if pf.product_name.lower() in entity or entity in pf.product_name.lower():
                    if pf.demand_trend.lower() in ("increasing", "surge") or (pf.trend_delta_pct and pf.trend_delta_pct > 15.0):
                        conflicts.append(
                            f"Product '{pf.product_name}' has surging forecast demand (+{pf.trend_delta_pct or 0:.1f}%), "
                            "conflicting with underperformance diagnosis."
                        )

        # 2. Churn alarm vs Strong repeat rate conflict
        if "churn" in prob or "lapsed" in prob or "retention" in title:
            if ctx.customers.repeat_rate_pct >= 60.0 and ctx.customers.repeat_customers >= 3:
                conflicts.append(
                    f"Business possesses high repeat customer rate ({ctx.customers.repeat_rate_pct:.1f}%), "
                    "conflicting with widespread customer attrition diagnosis."
                )

        # 3. Revenue diversification vs low top-client concentration
        if "diversification" in prob or "dependence" in prob:
            if ctx.sales.has_sales_data and ctx.customers.top_customers_by_revenue:
                top1_rev = ctx.customers.top_customers_by_revenue[0].get("revenue", 0.0)
                tot_rev = ctx.sales.total_revenue
                share = (top1_rev / tot_rev) * 100.0 if tot_rev > 0 else 0.0
                if share < 25.0:
                    conflicts.append(
                        f"Top client accounts for only {share:.1f}% of total revenue, "
                        "conflicting with high concentration exposure hypothesis."
                    )

        return conflicts


# --------------------------------------------------------------------------- #
# 2. Autonomous Multi-Signal Opportunity Scanner (Pattern Mining)
# --------------------------------------------------------------------------- #

class AutonomousOpportunityScanner:
    """Examines combinatorial business data across 12+ dimensions to discover novel opportunities."""

    def __init__(self) -> None:
        self._evidence_history: dict[str, str] = {}  # (biz_id, issue_key) -> signature

    def scan_all_dimensions(self, ctx: UnifiedRecommendationContext) -> list[OpportunityHypothesis]:
        """Run deep combinatorial pattern mining across the unified business twin context."""
        hypotheses: list[OpportunityHypothesis] = []
        biz_id = ctx.business_id

        # Dimension 1: High-Volume Low-Revenue SKU Pricing/Packaging Opportunity
        opp_sku_margin = self._scan_sku_pricing_volume_gap(ctx, biz_id)
        if opp_sku_margin:
            hypotheses.append(opp_sku_margin)

        # Dimension 2: Hero Product Demand Surge Production Prioritization
        opp_demand_surge = self._scan_forecast_demand_surge(ctx, biz_id)
        if opp_demand_surge:
            hypotheses.append(opp_demand_surge)

        # Dimension 3: Pre-Churn Lapsing Account Inter-Purchase Interval Expansion
        opp_lapsing = self._scan_lapsing_frequency(ctx, biz_id)
        if opp_lapsing:
            hypotheses.append(opp_lapsing)

        # Dimension 4: High-Repeat Buyer Loyalty & Standing Order Expansion
        opp_loyalty = self._scan_repeat_loyalty_expansion(ctx, biz_id)
        if opp_loyalty:
            hypotheses.append(opp_loyalty)

        # Dimension 5: Single/Top-Client Revenue Concentration Diversification
        opp_concentration = self._scan_concentration_diversification(ctx, biz_id)
        if opp_concentration:
            hypotheses.append(opp_concentration)

        # Dimension 6: Working Capital Acceleration via Quick-Pay Cash Discounts
        opp_cashflow = self._scan_payment_terms_cashflow(ctx, biz_id)
        if opp_cashflow:
            hypotheses.append(opp_cashflow)

        # Dimension 7: Digital Catalog & WhatsApp Commerce Expansion
        opp_digital = self._scan_digital_readiness_gap(ctx, biz_id)
        if opp_digital:
            hypotheses.append(opp_digital)

        # Dimension 8: Business Health & Institutional Credit Readiness
        opp_health = self._scan_business_health_lift(ctx, biz_id)
        if opp_health:
            hypotheses.append(opp_health)

        # Dimension 9: Cross-Signal Expansion: Surging Demand + Low Concentration
        opp_cross = self._scan_cross_signal_growth_wedge(ctx, biz_id)
        if opp_cross:
            hypotheses.append(opp_cross)

        # Dimension 10: Non-Dilutive Government Scheme Capital Access
        opp_scheme = self._scan_scheme_capital_access(ctx, biz_id)
        if opp_scheme:
            hypotheses.append(opp_scheme)

        return hypotheses

    def _compute_evidence_signature(self, *values: Any) -> str:
        """Create deterministic 8-character signature of underlying metrics."""
        raw = ":".join(str(v) for v in values)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]

    def _resolve_identity_and_version(
        self,
        category_code: str,
        biz_id: int,
        entity_code: str,
        issue_slug: str,
        current_sig: str,
        current_summary: str,
    ) -> tuple[str, int, Optional[str]]:
        """Produce stable composite ID and detect material changes requiring version bumps."""
        history_key = f"{biz_id}:{category_code}:{entity_code}:{issue_slug}"
        prev_sig = self._evidence_history.get(history_key)

        version = 1
        version_notes: Optional[str] = None

        if prev_sig is not None and prev_sig != current_sig:
            version = 2
            version_notes = f"Updated from v1: Underlying evidence signature changed ({current_summary})."

        self._evidence_history[history_key] = current_sig
        stable_id = f"rec_OPP_{category_code}_{biz_id}_{entity_code}_{issue_slug}_v{version}"
        return stable_id, version, version_notes

    # --- Dimension Scanners ---

    def _scan_sku_pricing_volume_gap(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect SKUs with high order quantity but low relative revenue share."""
        if not ctx.sales.has_sales_data or not ctx.products.top_products_by_revenue:
            return None

        tot_rev = ctx.sales.total_revenue
        tot_qty = ctx.sales.total_quantity
        if tot_rev <= 0 or tot_qty <= 0 or len(ctx.products.top_products_by_revenue) < 2:
            return None

        # Check fast moving volume vs revenue
        fast_items = ctx.products.fast_moving_products_by_volume
        if not fast_items:
            return None

        top_vol = fast_items[0]
        qty = float(top_vol.get("quantity", 0))
        vol_share = (qty / tot_qty) * 100.0 if tot_qty > 0 else 0.0

        p_name = top_vol.get("product_name", "Primary Volume SKU")
        matching_rev = next(
            (p for p in ctx.products.top_products_by_revenue if p.get("product_name") == p_name),
            None,
        )
        rev = float(matching_rev.get("revenue", 0.0)) if matching_rev else 0.0
        rev_share = (rev / tot_rev) * 100.0 if tot_rev > 0 else 0.0

        # If volume share significantly exceeds revenue share (e.g. 35% vol vs <15% rev)
        if vol_share >= 30.0 and rev_share < 20.0:
            sig = self._compute_evidence_signature(tot_rev, qty, rev, vol_share)
            summary = f"Volume share {vol_share:.1f}% vs Revenue share {rev_share:.1f}%"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "PROD", biz_id, "HIGH_VOL_SKU", "pricing_tier_gap", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title=f"Value-Capture Pricing & Tiering on High-Volume SKU: '{p_name}'",
                category="Product Portfolio Optimization",
                business_problem_or_opportunity=(
                    f"Product '{p_name}' drives {vol_share:.1f}% of total physical units sold but yields only "
                    f"{rev_share:.1f}% of total business revenue. A modest price realignment or minimum order quantity "
                    "tier could expand gross contribution without suppressing order velocity."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="volume_share_pct",
                        observed_value=round(vol_share, 1),
                        baseline_value=20.0,
                        source_module="sales_intelligence",
                        interpretation=f"Drives {vol_share:.1f}% of unit sales volume.",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="revenue_share_pct",
                        observed_value=round(rev_share, 1),
                        baseline_value=30.0,
                        source_module="product_performance",
                        interpretation=f"Yields only {rev_share:.1f}% of total gross revenue.",
                    ),
                ],
                evidence_references=[
                    f"Total units sold for '{p_name}': {qty:,.0f} units ({vol_share:.1f}% volume share).",
                    f"Total revenue contribution: ₹{rev:,.2f} ({rev_share:.1f}% revenue share).",
                    f"Total company sales: ₹{tot_rev:,.2f} across {ctx.sales.total_transactions} transactions.",
                ],
                relevant_time_period="Last 90-180 days (historical sales ledger)",
                possible_explanation=(
                    "The product is priced below optimal market value or treated as an unmonetized loss-leader, "
                    "causing operational overhead disproportionate to financial contribution."
                ),
                alternative_explanations=[
                    "Low unit price may be an intentional gateway product to acquire clients who buy higher-margin lines.",
                    "Input raw material costs may have shifted faster than contract pricing terms were revised.",
                ],
                confidence=0.82,
                missing_information=[
                    "Exact bill-of-materials (BOM) cost and gross margin percentages per unit.",
                    "Price sensitivity elasticity of repeat purchasers of this specific SKU.",
                ],
                recommended_investigation=(
                    f"Audit unit cost and benchmark competitor pricing for '{p_name}'. "
                    "Test a 5-8% price or minimum order adjustment on upcoming wholesale quotes."
                ),
                potential_business_benefit=(
                    f"A 5% realized price adjustment on {qty:,.0f} units yields approximately "
                    f"₹{rev * 0.05:,.2f} in pure incremental operating margin."
                ),
                cost_of_inaction=(
                    "Ongoing margin erosion as operational processing and fulfillment costs outpace low unit contribution."
                ),
                limitations=[
                    "Inventory holding costs and supplier lead times are not recorded in Phase 5.",
                    "Customer price elasticity cannot be guaranteed from past sales data alone.",
                ],
                observed_facts=[
                    f"SKU '{p_name}' total volume: {qty:,.0f} units.",
                    f"SKU '{p_name}' total revenue: ₹{rev:,.2f}.",
                    f"Volume-to-revenue ratio gap: {vol_share:.1f}% volume vs {rev_share:.1f}% revenue.",
                ],
                inferred_explanations=[
                    f"Hypothesis: Buyer willingness-to-pay for '{p_name}' supports a higher price tier or volume bundle.",
                ],
                relevant_entity="HIGH_VOL_SKU",
                underlying_issue="pricing_tier_gap",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_forecast_demand_surge(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect product demand surge in multi-period forecasting tournament."""
        if not ctx.forecast.has_forecast_data or not ctx.forecast.product_forecasts:
            return None

        growing = [
            f for f in ctx.forecast.product_forecasts
            if f.demand_trend.lower() in ("increasing", "surge")
            or (f.trend_delta_pct and f.trend_delta_pct > 12.0)
        ]
        if not growing:
            return None

        top_f = growing[0]
        delta_str = f"+{top_f.trend_delta_pct:.1f}%" if top_f.trend_delta_pct else "increasing trend"
        sig = self._compute_evidence_signature(top_f.product_name, top_f.forecasted_units_total, top_f.trend_delta_pct)
        summary = f"Demand trajectory {delta_str} across {top_f.forecast_horizon_periods} horizons"
        hyp_id, ver, v_notes = self._resolve_identity_and_version(
            "DEMAND", biz_id, "SURGING_SKU", "production_capacity_alignment", sig, summary
        )

        return OpportunityHypothesis(
            id=hyp_id,
            title=f"Capacity & Procurement Focus for Surging Product: '{top_f.product_name}'",
            category="Product Performance",
            business_problem_or_opportunity=(
                f"Multi-period statistical forecasting identifies a strong growth trajectory ({delta_str}) for "
                f"'{top_f.product_name}' over the next {top_f.forecast_horizon_periods} periods. Aligning operational "
                "procurement and sales prioritization here captures rising market demand before bottlenecks occur."
            ),
            quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
            supporting_signals=[
                OpportunitySupportingSignal(
                    signal_name="forecast_demand_trend",
                    observed_value=top_f.demand_trend,
                    baseline_value="neutral",
                    source_module="demand_forecasting",
                    interpretation=f"Selected model '{top_f.selected_model}' projects trajectory: {delta_str}.",
                ),
                OpportunitySupportingSignal(
                    signal_name="forecasted_units",
                    observed_value=round(top_f.forecasted_units_total, 1),
                    baseline_value=None,
                    source_module="demand_forecasting",
                    interpretation=f"Projected demand of {top_f.forecasted_units_total:,.0f} units over horizon.",
                ),
            ],
            evidence_references=[
                f"Top forecast model: '{top_f.selected_model}' with reliability grade '{top_f.reliability}'.",
                f"Projected horizon units: {top_f.forecasted_units_total:,.0f} units.",
            ],
            relevant_time_period=f"Next {top_f.forecast_horizon_periods} forecast periods",
            possible_explanation=(
                f"Underlying market adoption or repeat re-orders for '{top_f.product_name}' are accelerating."
            ),
            alternative_explanations=[
                "Temporary spike caused by one-off bulk orders from a single buyer rather than systemic market demand.",
                "Seasonal purchasing cycle peak that may normalize after the forecasted horizon.",
            ],
            confidence=0.85 if top_f.reliability.lower() == "high" else 0.70,
            missing_information=[
                "Supplier material lead times and machine capacity constraints (Phase 6 boundary).",
            ],
            recommended_investigation=(
                f"Confirm upcoming order pipeline with commercial buyers for '{top_f.product_name}' "
                "and verify raw material supplier readiness."
            ),
            potential_business_benefit=(
                f"Prevents unfulfilled demand and captures up to {top_f.forecasted_units_total:,.0f} units "
                "in sales velocity."
            ),
            cost_of_inaction=(
                "Stockouts or delivery delays, pushing impatient commercial buyers toward competing suppliers."
            ),
            limitations=[
                "Phase 5 models demand trends only; does NOT compute inventory safety stock or reorder points.",
                "Demand forecast reflects algorithmic projections based on past patterns.",
            ],
            observed_facts=[
                f"Forecast model: {top_f.selected_model}.",
                f"Forecast trend: {top_f.demand_trend} ({delta_str}).",
                f"Forecasted volume: {top_f.forecasted_units_total:,.0f} units.",
            ],
            inferred_explanations=[
                f"Hypothesis: Sustained customer pull justifies prioritizing production slots for '{top_f.product_name}'.",
            ],
            relevant_entity="SURGING_SKU",
            underlying_issue="production_capacity_alignment",
            version=ver,
            version_notes=v_notes,
        )

    def _scan_lapsing_frequency(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect customer accounts with expanding order intervals indicating churn risk."""
        declining = ctx.customers.declining_customers
        if not declining:
            return None

        count = len(declining)
        tot_cust = ctx.customers.total_customers
        if tot_cust < 2:
            return None

        # Sample customer names
        names = [c.get("customer_name") or c.get("customer_id") or "Client" for c in declining[:3]]
        sig = self._compute_evidence_signature(count, tot_cust, ":".join(names))
        summary = f"{count} lapsed accounts among {tot_cust} total customers"
        hyp_id, ver, v_notes = self._resolve_identity_and_version(
            "CUST", biz_id, "DECLINING_ACCOUNTS", "lapsing_frequency_retention", sig, summary
        )

        return OpportunityHypothesis(
            id=hyp_id,
            title=f"Pre-Churn Account Reactivation Protocol ({count} Dormant Accounts)",
            category="Customer Retention",
            business_problem_or_opportunity=(
                f"Detected {count} commercial customer account(s) ({', '.join(names)}) with significantly "
                "lengthened order intervals or zero purchases in recent months. Engaging past buyers proactively "
                "preserves customer acquisition ROI."
            ),
            quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
            supporting_signals=[
                OpportunitySupportingSignal(
                    signal_name="declining_customers_count",
                    observed_value=count,
                    baseline_value=0,
                    source_module="customer_analytics",
                    interpretation=f"{count} previously active customers have not reordered in recent periods.",
                ),
                OpportunitySupportingSignal(
                    signal_name="total_customers",
                    observed_value=tot_cust,
                    baseline_value=None,
                    source_module="customer_analytics",
                    interpretation=f"Represents {(count / tot_cust) * 100:.1f}% of total customer relationships.",
                ),
            ],
            evidence_references=[
                f"Dormant/declining accounts identified: {', '.join(names)} (historical context only).",
                f"Total customer database size: {tot_cust} registered clients.",
            ],
            relevant_time_period="Past 60-120 days since last recorded purchase",
            possible_explanation=(
                "Clients have shifted purchasing to alternatives, completed their project cycles, or experienced "
                "unaddressed service/pricing friction."
            ),
            alternative_explanations=[
                "Client order seasonality: purchasing may occur semi-annually rather than monthly.",
                "Client completed a major capital expenditure and does not require immediate replenishments.",
            ],
            confidence=0.80,
            missing_information=[
                "Reason for last order pause (requires direct telephone or commercial relationship check).",
            ],
            recommended_investigation=(
                f"Conduct direct relationship outreach to {names[0]} to review feedback on past deliveries and share updated offerings."
            ),
            potential_business_benefit=(
                "Reactivating even 20-30% of dormant accounts restores recurring order cadence at near-zero acquisition cost."
            ),
            cost_of_inaction=(
                "Permanent loss of acquired customer accounts and forfeiture of customer lifetime value to competitors."
            ),
            limitations=[
                "Past spend is historical context only; no portion is guaranteed as recoverable revenue.",
                "Actual customer status requires human confirmation before commercial outreach.",
            ],
            observed_facts=[
                f"{count} accounts have zero orders in the latest observation period.",
                f"Accounts were verified repeat or active buyers historically.",
            ],
            inferred_explanations=[
                "Hypothesis: Timely personalized outreach can restore recurring transaction frequency.",
            ],
            relevant_entity="DECLINING_ACCOUNTS",
            underlying_issue="lapsing_frequency_retention",
            version=ver,
            version_notes=v_notes,
        )

    def _scan_repeat_loyalty_expansion(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect strong repeat buyer base that warrants formal VIP / standing order structures."""
        repeat_count = ctx.customers.repeat_customers
        tot_cust = ctx.customers.total_customers
        repeat_pct = ctx.customers.repeat_rate_pct

        if tot_cust >= 2 and (repeat_count >= 1 or repeat_pct >= 25.0):
            sig = self._compute_evidence_signature(repeat_count, tot_cust, repeat_pct)
            summary = f"{repeat_count} repeat buyers ({repeat_pct:.1f}% repeat rate)"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "REV", biz_id, "REPEAT_COHORT", "loyalty_standing_agreements", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title="Institutionalize Standing Orders & Volume Loyalty with Core Repeat Buyers",
                category="Revenue Growth",
                business_problem_or_opportunity=(
                    f"The business has {repeat_count} repeat buyer accounts representing a {repeat_pct:.1f}% repeat "
                    "rate. Transitioning ad-hoc re-orders into formal standing agreements, scheduled monthly shipments, "
                    "or loyalty rebates secures recurring revenue predictability."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="repeat_customers_count",
                        observed_value=repeat_count,
                        baseline_value=1,
                        source_module="customer_analytics",
                        interpretation=f"{repeat_count} accounts demonstrate validated multi-order retention.",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="repeat_rate_pct",
                        observed_value=round(repeat_pct, 1),
                        baseline_value=20.0,
                        source_module="customer_analytics",
                        interpretation=f"Repeat rate stands at {repeat_pct:.1f}%.",
                    ),
                ],
                evidence_references=[
                    f"Verified repeat accounts: {repeat_count} out of {tot_cust} total customers.",
                    f"Average order value (AOV): ₹{ctx.customers.average_order_value:,.2f}.",
                ],
                relevant_time_period="Full recorded sales ledger period",
                possible_explanation=(
                    "Customers are satisfied with product quality and lead times, creating an opening to "
                    "lock in long-term supply relationships."
                ),
                alternative_explanations=[
                    "Repeat orders may be short-term project-specific needs rather than ongoing operational requirements.",
                ],
                confidence=0.85,
                missing_information=[
                    "Client contract renewal dates and formal procurement calendar cycles.",
                ],
                recommended_investigation=(
                    "Review top repeat buyers' order frequency and propose scheduled quarterly standing orders."
                ),
                potential_business_benefit=(
                    "Locks in 15-25% more predictable monthly revenue and eliminates renegotiation overhead."
                ),
                cost_of_inaction=(
                    "Core repeat accounts remain susceptible to poaching by aggressive competitors offering formal SLA terms."
                ),
                limitations=[
                    "Past order patterns do not constitute binding commitments.",
                ],
                observed_facts=[
                    f"Repeat customer count: {repeat_count}.",
                    f"Repeat purchase rate: {repeat_pct:.1f}%.",
                ],
                inferred_explanations=[
                    "Hypothesis: Clients value continuity and will accept standing replenishment schedules in exchange for tiered perks.",
                ],
                relevant_entity="REPEAT_COHORT",
                underlying_issue="loyalty_standing_agreements",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_concentration_diversification(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect high customer revenue concentration and surface diversification opportunity."""
        if not ctx.sales.has_sales_data or not ctx.customers.top_customers_by_revenue:
            return None

        tot_rev = ctx.sales.total_revenue
        if tot_rev <= 0 or ctx.customers.total_customers < 2:
            return None

        top3 = ctx.customers.top_customers_by_revenue[:3]
        top3_rev = sum(float(c.get("revenue", 0.0)) for c in top3)
        top3_pct = (top3_rev / tot_rev) * 100.0

        top1 = top3[0]
        top1_rev = float(top1.get("revenue", 0.0))
        top1_pct = (top1_rev / tot_rev) * 100.0
        top1_name = top1.get("customer_name") or top1.get("customer_id") or "Anchor Client"

        if top1_pct >= 35.0 or top3_pct >= 55.0:
            sig = self._compute_evidence_signature(tot_rev, top1_pct, top3_pct, top1_name)
            summary = f"Top client generates {top1_pct:.1f}%, top 3 generate {top3_pct:.1f}%"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "CUST", biz_id, "TOP_CLIENTS", "concentration_diversification", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title=f"Mid-Market Client Acquisition to De-Risk {top1_pct:.0f}% Anchor Client Concentration",
                category="Revenue Growth",
                business_problem_or_opportunity=(
                    f"The top client '{top1_name}' represents {top1_pct:.1f}% of total business revenue, and the "
                    f"top 3 clients drive {top3_pct:.1f}%. While valuable, this concentration creates severe vulnerability "
                    "if purchasing slows. Onboarding 5-10 mid-market buyers in adjacent sectors diversifies cashflow."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="top1_revenue_share_pct",
                        observed_value=round(top1_pct, 1),
                        baseline_value=25.0,
                        source_module="customer_analytics",
                        interpretation=f"Single client '{top1_name}' generates {top1_pct:.1f}% of total sales.",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="top3_revenue_share_pct",
                        observed_value=round(top3_pct, 1),
                        baseline_value=50.0,
                        source_module="customer_analytics",
                        interpretation=f"Top 3 accounts generate {top3_pct:.1f}% of aggregate revenue.",
                    ),
                ],
                evidence_references=[
                    f"Top client '{top1_name}': ₹{top1_rev:,.2f} ({top1_pct:.1f}% share, historical context only).",
                    f"Top 3 revenue: ₹{top3_rev:,.2f} ({top3_pct:.1f}% share).",
                    f"Total company revenue: ₹{tot_rev:,.2f}.",
                ],
                relevant_time_period="Historical recorded sales ledger",
                possible_explanation=(
                    "Commercial focus has prioritized servicing the largest incoming accounts at the expense of "
                    "systematic inbound marketing or outbound diversification."
                ),
                alternative_explanations=[
                    "The business may operate in a specialized OEM industry with structurally few domestic buyers.",
                ],
                confidence=0.88,
                missing_information=[
                    "Customer acquisition cost (CAC) and lead times in adjacent market segments.",
                ],
                recommended_investigation=(
                    "Identify 10 mid-market companies in adjacent regional industrial clusters that utilize similar components."
                ),
                potential_business_benefit=(
                    f"Reduces revenue loss risk and brings single-client exposure below 25% within 6-9 months."
                ),
                cost_of_inaction=(
                    "Catastrophic cashflow disruption if the anchor account postpones capital allocations or renegotiates rates."
                ),
                limitations=[
                    "Past spend is past evidence only; no claim guarantees customer retention or loss.",
                ],
                observed_facts=[
                    f"Top client revenue: ₹{top1_rev:,.2f} ({top1_pct:.1f}%).",
                    f"Top 3 clients total: ₹{top3_rev:,.2f} ({top3_pct:.1f}%).",
                ],
                inferred_explanations=[
                    "Hypothesis: Proven execution for anchor client validates capability to win mid-market peers.",
                ],
                relevant_entity="TOP_CLIENTS",
                underlying_issue="concentration_diversification",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_payment_terms_cashflow(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect opportunities to compress working capital cash conversion cycles."""
        tot_rev = ctx.sales.total_revenue
        avg_order = ctx.customers.average_order_value

        # For B2B/Wholesale with significant order sizes
        if tot_rev > 200000.0 and avg_order > 5000.0:
            sig = self._compute_evidence_signature(tot_rev, avg_order, ctx.sales.total_transactions)
            summary = f"Total revenue ₹{tot_rev:,.0f}, AOV ₹{avg_order:,.0f}"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "FIN", biz_id, "RECEIVABLES", "cashflow_acceleration", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title="Working Capital Acceleration via 2% Net-10 Early Settlement Incentive",
                category="Financial Management",
                business_problem_or_opportunity=(
                    f"With average transaction values of ₹{avg_order:,.2f}, standard Net-30/60 day terms tie up "
                    "substantial liquidity in accounts receivable. Introducing a 2% discount for payments settled within "
                    "10 days accelerates cash conversion by 15-20 days."
                ),
                quality_status=OpportunityQualityStatus.PROMISING_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="average_order_value",
                        observed_value=round(avg_order, 2),
                        baseline_value=5000.0,
                        source_module="customer_analytics",
                        interpretation=f"Substantial transaction scale (₹{avg_order:,.2f}) makes cash terms impactful.",
                    ),
                ],
                evidence_references=[
                    f"Average order value: ₹{avg_order:,.2f}.",
                    f"Total sales ledger volume: ₹{tot_rev:,.2f}.",
                ],
                relevant_time_period="Ongoing operational invoicing cycle",
                possible_explanation=(
                    "MSME commercial customers delay payment until invoices mature, using supplier credit as working capital."
                ),
                alternative_explanations=[
                    "Corporate enterprise buyers often have rigid payment batch schedules that cannot adopt discount terms.",
                ],
                confidence=0.76,
                missing_information=[
                    "Current Days Sales Outstanding (DSO) breakdown per customer.",
                ],
                recommended_investigation=(
                    "Test 2% Net-10 terms with 3 trusted repeat clients on upcoming bulk orders to gauge payment acceleration."
                ),
                potential_business_benefit=(
                    "Compresses cash conversion cycle by 15-20 days, reducing working capital borrowing costs."
                ),
                cost_of_inaction=(
                    "Ongoing cashflow tightness during peak production cycles requiring expensive short-term overdrafts."
                ),
                limitations=[
                    "Requires verification that 2% discount does not unduly compromise gross operating margin.",
                ],
                observed_facts=[
                    f"Average order value is ₹{avg_order:,.2f}.",
                    f"Total sales ledger volume is ₹{tot_rev:,.2f}.",
                ],
                inferred_explanations=[
                    "Hypothesis: Commercial buyers with excess liquidity will gladly take a 2% discount for quick settlement.",
                ],
                relevant_entity="RECEIVABLES",
                underlying_issue="cashflow_acceleration",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_digital_readiness_gap(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect offline sales model and surface digital catalog / WhatsApp commerce expansion."""
        if not ctx.profile.has_website or not ctx.profile.has_ecommerce:
            sig = self._compute_evidence_signature(ctx.profile.has_website, ctx.profile.has_ecommerce, ctx.sales.total_revenue)
            summary = f"Website: {ctx.profile.has_website}, eCommerce: {ctx.profile.has_ecommerce}"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "DIG", biz_id, "CHANNELS", "whatsapp_digital_catalog", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title="Deploy Digital Product Showcase & WhatsApp Business Order Capture",
                category="Digital Transformation",
                business_problem_or_opportunity=(
                    "The business currently relies almost exclusively on manual or offline communication. Establishing "
                    "a shareable digital catalog and automated WhatsApp order-taking allows rapid regional discovery and "
                    "streamlines inquiry turnaround."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="has_website",
                        observed_value=ctx.profile.has_website,
                        baseline_value=True,
                        source_module="business_profile",
                        interpretation="Website absence restricts automated inbound inquiries.",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="digital_readiness_score",
                        observed_value=ctx.readiness.digital_readiness_score,
                        baseline_value=60.0,
                        source_module="operational_readiness",
                        interpretation="Digital maturity index indicates manual ordering processes.",
                    ),
                ],
                evidence_references=[
                    f"Online web presence: {'Present' if ctx.profile.has_website else 'Absent'}.",
                    f"Digital commerce channel: {'Present' if ctx.profile.has_ecommerce else 'Absent'}.",
                ],
                relevant_time_period="Current operational baseline",
                possible_explanation=(
                    "Traditional MSME operations prioritize local physical relationships over digital lead funnels."
                ),
                alternative_explanations=[
                    "Highly custom bespoke manufacturing where digital catalogs cannot replace technical engineering quotes.",
                ],
                confidence=0.82,
                missing_information=[
                    "Percentage of current incoming orders initiated via WhatsApp or phone calls.",
                ],
                recommended_investigation=(
                    "Consolidate current top 10 products into a standardized PDF/linkable catalog for customer WhatsApp sharing."
                ),
                potential_business_benefit=(
                    "Expands regional discovery and shortens quote turnaround time by 30-40%."
                ),
                cost_of_inaction=(
                    "Gradual loss of emerging younger procurement officers who favor instant digital catalogs over phone inquiries."
                ),
                limitations=[
                    "Does not require building full e-commerce software; lightweight digital catalog is recommended first.",
                ],
                observed_facts=[
                    f"Website active: {ctx.profile.has_website}.",
                    f"E-commerce active: {ctx.profile.has_ecommerce}.",
                ],
                inferred_explanations=[
                    "Hypothesis: Standardizing product specifications digitally increases buyer conversion velocity.",
                ],
                relevant_entity="CHANNELS",
                underlying_issue="whatsapp_digital_catalog",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_business_health_lift(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect business health score gaps that restrict creditworthiness."""
        score = ctx.health.overall_score
        missing = ctx.health.missing_fields

        if score < 75 and missing:
            sig = self._compute_evidence_signature(score, len(missing), ":".join(missing[:3]))
            summary = f"Health score {score}/100 with {len(missing)} missing profile attributes"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "OPS", biz_id, "CREDIT_TWIN", "health_score_lift", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title=f"Elevate Health Score from {score} to 80+ to Unlock Tier-1 Bank Loan Terms",
                category="Operational Standardization",
                business_problem_or_opportunity=(
                    f"The verified business health score stands at {score}/100, constrained by missing profile attributes "
                    f"({', '.join(missing[:3])}). Completing verified records elevates institutional creditworthiness and "
                    "unlocks preferential working capital interest subventions."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="overall_health_score",
                        observed_value=score,
                        baseline_value=75,
                        source_module="health_score",
                        interpretation=f"Current health rating is {ctx.health.grade} ({score}/100).",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="missing_fields_count",
                        observed_value=len(missing),
                        baseline_value=0,
                        source_module="health_score",
                        interpretation=f"{len(missing)} verifiable business data fields remain unrecorded.",
                    ),
                ],
                evidence_references=[
                    f"Verified health score: {score}/100 (Grade {ctx.health.grade}).",
                    f"Missing fields: {', '.join(missing[:4])}.",
                ],
                relevant_time_period="Current verified business twin state",
                possible_explanation=(
                    "Business owner has not completed secondary operational and governance profile information."
                ),
                alternative_explanations=[
                    "Certain data fields (e.g. export certifications) may not be applicable to the current domestic scale.",
                ],
                confidence=0.90,
                missing_information=[
                    f"Pending business twin fields: {', '.join(missing[:3])}.",
                ],
                recommended_investigation=(
                    "Complete missing twin profile fields in the UrsBiz Business Twin dashboard."
                ),
                potential_business_benefit=(
                    "Elevates health rating to 'Good' (75+) and unlocks preferential interest rates from institutional lenders."
                ),
                cost_of_inaction=(
                    "Ongoing classification in lower credit bands, resulting in 1-2% higher commercial borrowing rates."
                ),
                limitations=[
                    "Health score reflects recorded data completeness and operational signals; actual bank approval requires underwriter review.",
                ],
                observed_facts=[
                    f"Current health score is {score}/100.",
                    f"Pending profile fields: {', '.join(missing[:3])}.",
                ],
                inferred_explanations=[
                    "Hypothesis: Complete governance documentation accelerates institutional bank credit underwriting.",
                ],
                relevant_entity="CREDIT_TWIN",
                underlying_issue="health_score_lift",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_cross_signal_growth_wedge(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Cross-signal: Surging product demand + High client concentration -> Diversification wedge."""
        if not ctx.forecast.has_forecast_data or not ctx.customers.top_customers_by_revenue:
            return None

        # Check for surging SKU
        surging_skus = [
            f for f in ctx.forecast.product_forecasts
            if f.demand_trend.lower() in ("increasing", "surge")
        ]
        if not surging_skus:
            return None

        surging_name = surging_skus[0].product_name
        tot_rev = ctx.sales.total_revenue
        top1_rev = float(ctx.customers.top_customers_by_revenue[0].get("revenue", 0.0))
        top1_pct = (top1_rev / tot_rev) * 100.0 if tot_rev > 0 else 0.0

        if top1_pct >= 35.0:
            sig = self._compute_evidence_signature(surging_name, top1_pct, tot_rev)
            summary = f"Surging SKU '{surging_name}' with anchor concentration {top1_pct:.1f}%"
            hyp_id, ver, v_notes = self._resolve_identity_and_version(
                "CROSS", biz_id, "GROWTH_WEDGE", "surging_sku_client_diversification", sig, summary
            )

            return OpportunityHypothesis(
                id=hyp_id,
                title=f"Deploy High-Demand '{surging_name}' as Commercial Wedge to Diversify Beyond Anchor Client",
                category="Revenue Growth",
                business_problem_or_opportunity=(
                    f"Multi-signal correlation: While client concentration is high ({top1_pct:.1f}% on top buyer), "
                    f"product '{surging_name}' demonstrates surging market demand. Using this proven hero product as "
                    "a commercial door-opener enables rapid acquisition of new corporate accounts without price concessions."
                ),
                quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                supporting_signals=[
                    OpportunitySupportingSignal(
                        signal_name="forecast_demand_surge",
                        observed_value=surging_name,
                        baseline_value=None,
                        source_module="demand_forecasting",
                        interpretation=f"Product '{surging_name}' is accelerating in forecast trajectory.",
                    ),
                    OpportunitySupportingSignal(
                        signal_name="customer_concentration_pct",
                        observed_value=round(top1_pct, 1),
                        baseline_value=25.0,
                        source_module="customer_analytics",
                        interpretation=f"Top buyer accounts for {top1_pct:.1f}% of total revenue.",
                    ),
                ],
                evidence_references=[
                    f"Surging product: '{surging_name}' (model '{surging_skus[0].selected_model}').",
                    f"Top client revenue share: {top1_pct:.1f}%.",
                ],
                relevant_time_period="Current cross-signal window",
                possible_explanation=(
                    f"Market appetite for '{surging_name}' is expanding beyond existing buyer relationships."
                ),
                alternative_explanations=[
                    "The surging demand may be driven entirely by the existing anchor client's own expansion.",
                ],
                confidence=0.84,
                missing_information=[
                    "Proportion of surging demand coming from existing anchor vs potential new accounts.",
                ],
                recommended_investigation=(
                    f"Reach out to 5 prospective buyers in neighboring districts offering immediate sample deliveries of '{surging_name}'."
                ),
                potential_business_benefit=(
                    "Simultaneously captures rising market demand and establishes 3-5 non-anchor revenue streams."
                ),
                cost_of_inaction=(
                    "Allowing competitors to capture market demand for a product category where the business has demonstrated manufacturing capability."
                ),
                limitations=[
                    "Requires ensuring production capacity can service both anchor orders and trial runs for new buyers.",
                ],
                observed_facts=[
                    f"Demand for '{surging_name}' is trending upward.",
                    f"Top client currently accounts for {top1_pct:.1f}% of sales.",
                ],
                inferred_explanations=[
                    f"Hypothesis: Demonstrated excellence in '{surging_name}' makes it the lowest-friction acquisition hook.",
                ],
                relevant_entity="GROWTH_WEDGE",
                underlying_issue="surging_sku_client_diversification",
                version=ver,
                version_notes=v_notes,
            )
        return None

    def _scan_scheme_capital_access(
        self, ctx: UnifiedRecommendationContext, biz_id: int
    ) -> Optional[OpportunityHypothesis]:
        """Detect eligible government schemes providing non-dilutive subsidies."""
        schemes = ctx.schemes.recommended_schemes or ctx.schemes.eligible_schemes
        if not schemes:
            return None

        top_s = schemes[0]
        sig = self._compute_evidence_signature(top_s.id, top_s.name, top_s.official_authority)
        summary = f"Scheme: {top_s.name} from {top_s.official_authority}"
        hyp_id, ver, v_notes = self._resolve_identity_and_version(
            "SCHEME", biz_id, top_s.id, "subsidized_capital_access", sig, summary
        )

        return OpportunityHypothesis(
            id=hyp_id,
            title=f"Access Subsidized Financing & Grants via '{top_s.name}'",
            category="Government Schemes and Funding",
            business_problem_or_opportunity=(
                f"Business profile matches eligibility criteria for '{top_s.name}' administered by "
                f"{top_s.official_authority}. This statutory program offers collateral-free credit, interest "
                "subventions, or technology upgrades that lower expansion capital costs."
            ),
            quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
            supporting_signals=[
                OpportunitySupportingSignal(
                    signal_name="scheme_eligibility",
                    observed_value=top_s.name,
                    baseline_value=None,
                    source_module="government_schemes",
                    interpretation=f"Matched on verified industry '{ctx.profile.industry}' and business stage.",
                ),
            ],
            evidence_references=[
                f"Statutory authority: {top_s.official_authority}.",
                f"Official application portal: {top_s.official_source_url}.",
                f"Key benefits: {', '.join(top_s.benefits[:3]) if top_s.benefits else 'Interest subvention & credit support'}.",
            ],
            relevant_time_period="Current statutory fiscal year",
            possible_explanation=(
                "Government ministry allocations prioritize MSME growth in this specific manufacturing/services sector."
            ),
            alternative_explanations=[
                "Scheme funding windows may be subject to quarterly budgetary exhaustion.",
            ],
            confidence=0.88,
            missing_information=[
                "Internal readiness of required statutory audit documents (Udyam, GST returns, ITR).",
            ],
            recommended_investigation=(
                f"Download application checklist from {top_s.official_source_url} and verify document readiness with company accountant."
            ),
            potential_business_benefit=(
                "Substantially reduces cost of capital for planned machinery or working capital expansion."
            ),
            cost_of_inaction=(
                "Paying standard commercial borrowing rates (12-15%) when 3-5% interest subsidies are available by statute."
            ),
            limitations=[
                "Official eligibility guidelines and statutory discretion govern scheme approval; matching confirms criteria match, not disbursement.",
            ],
            observed_facts=[
                f"Scheme matched: {top_s.name}.",
                f"Official authority: {top_s.official_authority}.",
                f"Verified official URL: {top_s.official_source_url}.",
            ],
            inferred_explanations=[
                "Hypothesis: Capital investment subsidization accelerates technology modernization without equity dilution.",
            ],
            relevant_entity=top_s.id,
            underlying_issue="subsidized_capital_access",
            version=ver,
            version_notes=v_notes,
        )


# --------------------------------------------------------------------------- #
# 3. Dynamic Gemini Opportunity Discoverer (Beyond Existing Rules)
# --------------------------------------------------------------------------- #

class DynamicGeminiOpportunityDiscoverer:
    """Uses Gemini to identify non-obvious cross-signal opportunities from business data."""

    def __init__(self, client: Optional[ResilientGeminiClient] = None) -> None:
        self.client = client or ResilientGeminiClient(timeout_seconds=7.0, max_retries=1)

    def discover_novel_opportunities(
        self, ctx: UnifiedRecommendationContext
    ) -> list[OpportunityHypothesis]:
        """Prompt Gemini to synthesize non-predefined opportunity hypotheses from verified data."""
        prompt_system = (
            "You are the UrsBiz Autonomous Opportunity Discovery Engine for Indian MSMEs.\n"
            "Analyze the verified business data provided and discover 1-2 NON-OBVIOUS, HIGH-VALUE business opportunities "
            "that are NOT generic advice. Every opportunity must be grounded in the provided numbers.\n"
            "CRITICAL AUDIT RULES:\n"
            "1. NO inventory reorder quantities, safety stock, or stockout dates (Phase 6 boundary).\n"
            "2. Past customer spend is historical evidence only; NEVER claim it as guaranteed recoverable revenue.\n"
            "3. Separate observed facts from inferred explanations. Explicitly state that correlation != causation.\n"
            "4. Return strict JSON array matching the schema: "
            "[{'title': str, 'category': str, 'problem': str, 'signals': [{'name': str, 'value': str, 'module': str, 'interp': str}], "
            "'explanation': str, 'alternatives': [str], 'confidence': float, 'investigation': str, 'benefit': str, "
            "'observed_facts': [str], 'inferred_explanations': [str], 'entity': str, 'issue': str}]"
        )

        user_content = json.dumps({
            "business_id": ctx.business_id,
            "industry": ctx.profile.industry,
            "annual_revenue": ctx.profile.annual_revenue,
            "employee_count": ctx.profile.employee_count,
            "health_score": ctx.health.overall_score,
            "sales_transactions": ctx.sales.total_transactions,
            "total_revenue": ctx.sales.total_revenue,
            "total_customers": ctx.customers.total_customers,
            "repeat_customers": ctx.customers.repeat_customers,
            "repeat_rate_pct": ctx.customers.repeat_rate_pct,
            "average_order_value": ctx.customers.average_order_value,
            "top_products": [p.get("product_name") for p in ctx.products.top_products_by_revenue[:3]],
            "forecast_trends": [
                {"sku": f.product_name, "trend": f.demand_trend, "units": f.forecasted_units_total}
                for f in ctx.forecast.product_forecasts[:3]
            ],
            "digital_readiness": ctx.readiness.digital_readiness_score,
        })

        try:
            raw_response = self.client.execute_chat_completion(
                system_prompt=prompt_system,
                user_content=user_content,
                max_tokens=600,
                temperature=0.2,
                require_json=True,
            )
            if not raw_response:
                return []

            parsed = self.client.extract_and_validate_json(raw_response)
            if not parsed or not isinstance(parsed, list):
                return []

            hypotheses: list[OpportunityHypothesis] = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue

                entity = item.get("entity", "GENERAL")
                issue = item.get("issue", "dynamic_opportunity")
                hyp_id = f"rec_OPP_AI_{ctx.business_id}_{entity}_{issue}_v1"

                signals = [
                    OpportunitySupportingSignal(
                        signal_name=s.get("name", "signal"),
                        observed_value=s.get("value", ""),
                        source_module=s.get("module", "sales_intelligence"),
                        interpretation=s.get("interp", ""),
                    )
                    for s in item.get("signals", [])
                    if isinstance(s, dict)
                ]

                hyp = OpportunityHypothesis(
                    id=hyp_id,
                    title=item.get("title", "Autonomous Business Opportunity"),
                    category=item.get("category", "Revenue Growth"),
                    business_problem_or_opportunity=item.get("problem", ""),
                    quality_status=OpportunityQualityStatus.PROMISING_OPPORTUNITY,
                    supporting_signals=signals,
                    evidence_references=[f"Synthesized from verified {s.source_module} metrics." for s in signals],
                    relevant_time_period="Recent operational business context",
                    possible_explanation=item.get("explanation", "Data patterns indicate an emerging growth vector."),
                    alternative_explanations=item.get("alternatives", ["External market dynamics may account for the observation."]),
                    confidence=float(min(0.85, max(0.50, item.get("confidence", 0.70)))),
                    missing_information=["Requires commercial validation by operational leadership."],
                    recommended_investigation=item.get("investigation", "Audit order records to verify operational readiness."),
                    potential_business_benefit=item.get("benefit", "Accelerates revenue and improves operating leverage."),
                    limitations=[
                        "Generated through multi-signal AI reasoning; correlation does not establish causation.",
                        "No inventory reorder quantities or stockout projections computed.",
                    ],
                    observed_facts=item.get("observed_facts", [f"Analyzed {ctx.sales.total_transactions} transactions."]),
                    inferred_explanations=item.get("inferred_explanations", [item.get("explanation", "")]),
                    relevant_entity=entity,
                    underlying_issue=issue,
                    version=1,
                )
                hypotheses.append(hyp)

            return hypotheses

        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[opportunity_discovery] Gemini dynamic discovery error: {exc}. Using deterministic scanner.")
            return []


# --------------------------------------------------------------------------- #
# 4. Main Opportunity Discovery Orchestrator
# --------------------------------------------------------------------------- #

class OpportunityDiscoveryEngine:
    """Master orchestrator combining dynamic AI discovery, deterministic pattern mining, and strict validation."""

    def __init__(
        self,
        scanner: Optional[AutonomousOpportunityScanner] = None,
        validator: Optional[OpportunityValidationEngine] = None,
        gemini_discoverer: Optional[DynamicGeminiOpportunityDiscoverer] = None,
    ) -> None:
        self.scanner = scanner or AutonomousOpportunityScanner()
        self.validator = validator or OpportunityValidationEngine()
        self.gemini_discoverer = gemini_discoverer or DynamicGeminiOpportunityDiscoverer()

    def discover_hypotheses(
        self,
        ctx: UnifiedRecommendationContext,
        active_rec_ids: Optional[Set[str]] = None,
        completed_rec_ids: Optional[Set[str]] = None,
    ) -> list[OpportunityHypothesis]:
        """Discover, synthesize, and validate opportunity hypotheses across all dimensions."""
        # 1. Deterministic Multi-Signal Scanners
        raw_hypotheses = self.scanner.scan_all_dimensions(ctx)

        # 2. Dynamic Gemini Synthesis (Beyond Predefined Rules)
        gemini_hypotheses = self.gemini_discoverer.discover_novel_opportunities(ctx)
        raw_hypotheses.extend(gemini_hypotheses)

        # 3. Validation Pipeline & Quality Classification
        validated_hypotheses: list[OpportunityHypothesis] = []
        for h in raw_hypotheses:
            val_h = self.validator.validate(
                hypothesis=h,
                ctx=ctx,
                active_rec_ids=active_rec_ids,
                completed_rec_ids=completed_rec_ids,
            )
            validated_hypotheses.append(val_h)

        return validated_hypotheses

    def discover(
        self,
        ctx: UnifiedRecommendationContext,
        active_rec_ids: Optional[Set[str]] = None,
        completed_rec_ids: Optional[Set[str]] = None,
    ) -> list[OpportunityItem]:
        """Surface validated opportunities formatted as OpportunityItem for the dashboard."""
        hypotheses = self.discover_hypotheses(
            ctx=ctx,
            active_rec_ids=active_rec_ids,
            completed_rec_ids=completed_rec_ids,
        )
        return self.hypotheses_to_opportunity_items(hypotheses)

    def hypotheses_to_opportunity_items(
        self, hypotheses: list[OpportunityHypothesis]
    ) -> list[OpportunityItem]:
        """Transform validated hypotheses into OpportunityItem instances."""
        items: list[OpportunityItem] = []

        for h in hypotheses:
            # Suppress non-actionable or insufficient evidence from dashboard
            if h.quality_status in (
                OpportunityQualityStatus.INSUFFICIENT_EVIDENCE,
                OpportunityQualityStatus.NOT_ACTIONABLE,
            ):
                continue

            strength_label = (
                "Strong Evidence"
                if h.confidence >= 0.80
                else ("Moderate Evidence" if h.confidence >= 0.60 else "Limited Evidence")
            )
            feasibility_label = "High" if h.confidence >= 0.75 else "Medium"

            items.append(
                OpportunityItem(
                    id=h.id,
                    title=h.title,
                    category=h.category,
                    rationale=h.business_problem_or_opportunity,
                    evidence_strength=strength_label,
                    feasibility=feasibility_label,
                    estimated_impact_description=h.potential_business_benefit,
                    first_step=h.recommended_investigation,
                    timeframe="14-30 days",
                    quality_status=h.quality_status,
                    hypothesis_id=h.id,
                    cost_of_inaction=h.cost_of_inaction,
                    observed_facts=h.observed_facts,
                    inferred_explanations=h.inferred_explanations,
                    alternative_explanations=h.alternative_explanations,
                    recommended_investigation=h.recommended_investigation,
                    confidence=h.confidence,
                    version=h.version,
                    version_notes=h.version_notes,
                )
            )

        return items

    def generate_opportunity_recommendation_candidates(
        self,
        ctx: UnifiedRecommendationContext,
        active_rec_ids: Optional[Set[str]] = None,
        completed_rec_ids: Optional[Set[str]] = None,
    ) -> list[dict[str, Any]]:
        """Convert verified/promising opportunities into full 9-pillar recommendation candidate dicts."""
        hypotheses = self.discover_hypotheses(
            ctx=ctx,
            active_rec_ids=active_rec_ids,
            completed_rec_ids=completed_rec_ids,
        )

        candidates: list[dict[str, Any]] = []

        for h in hypotheses:
            # Only VERIFIED and PROMISING opportunities enter the primary recommendation stream
            if h.quality_status not in (
                OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
                OpportunityQualityStatus.PROMISING_OPPORTUNITY,
            ):
                continue

            # Map category string to RecommendationCategory
            cat_lower = h.category.lower()
            if "retention" in cat_lower or "lapsed" in cat_lower:
                category = RecommendationCategory.CUSTOMER_RETENTION
            elif "demand" in cat_lower or "forecast" in cat_lower:
                category = RecommendationCategory.DEMAND_PLANNING
            elif "product" in cat_lower or "catalog" in cat_lower:
                category = RecommendationCategory.PRODUCT_PERFORMANCE
            elif "digital" in cat_lower:
                category = RecommendationCategory.DIGITAL_TRANSFORMATION
            elif "scheme" in cat_lower or "funding" in cat_lower:
                category = RecommendationCategory.GOVERNMENT_SCHEMES
            elif "finance" in cat_lower or "cashflow" in cat_lower or "receivable" in cat_lower:
                category = RecommendationCategory.FINANCIAL_MANAGEMENT
            elif "operational" in cat_lower or "health" in cat_lower:
                category = RecommendationCategory.OPERATIONAL_EFFICIENCY
            elif "cost" in cat_lower:
                category = RecommendationCategory.COST_OPTIMIZATION
            elif "risk" in cat_lower:
                category = RecommendationCategory.RISK_REDUCTION
            else:
                category = RecommendationCategory.REVENUE_GROWTH

            urgency_score = int(h.confidence * 75)
            impact_score = int(h.confidence * 85)
            evidence_score = int(h.confidence * 100)

            cand = {
                "id": h.id,
                "title": h.title,
                "category": category,
                "urgency": urgency_score,
                "impact": impact_score,
                "evidence_strength": evidence_score,
                "confidence": round(h.confidence * 100.0, 1),
                "feasibility": 80 if h.confidence >= 0.80 else 65,
                "description": h.business_problem_or_opportunity,
                "business_context": f"Empirical observation period: {h.relevant_time_period}.",
                "evidence": h.evidence_references,
                "reasoning": (
                    f"Discovered by Autonomous Opportunity Engine: {h.possible_explanation} "
                    f"Alternative explanations evaluated: {'; '.join(h.alternative_explanations[:2])}."
                ),
                "recommended_actions": [
                    h.recommended_investigation,
                    f"Evaluate financial feasibility: {h.potential_business_benefit}.",
                    "Establish milestone tracking over the next 30 days.",
                ],
                "expected_benefit": h.potential_business_benefit,
                "estimated_impact": None,
                "impact_unit": None,
                "data_quality": "High" if h.confidence >= 0.80 else "Moderate",
                "limitations": h.limitations,
                "source_modules": list(set(s.source_module for s in h.supporting_signals)) or ["sales_intelligence"],
                "source_module_link": (
                    "/schemes" if category == RecommendationCategory.GOVERNMENT_SCHEMES
                    else ("/predictive-analytics" if category == RecommendationCategory.DEMAND_PLANNING else "/analytics")
                ),
                "what_is_happening": (
                    f"Autonomous data discovery: {h.business_problem_or_opportunity}"
                ),
                "why_it_matters": (
                    f"Core strategic lever: Capitalizing on this pattern secures {h.potential_business_benefit}."
                ),
                "root_cause": h.possible_explanation,
                "missed_opportunity": h.potential_business_benefit,
                "action_scenario": (
                    f"Implementing recommended actions unlocks {h.potential_business_benefit} within 30-60 days."
                ),
                "cost_of_inaction": (
                    h.cost_of_inaction or "Forfeiture of commercial upside and exposure to competitor displacement."
                ),
                "measurement_kpis": [
                    "Target opportunity conversion velocity",
                    "Incremental order volume or cashflow compression",
                    "Customer retention or product margin lift",
                ],
                "implementation_difficulty": "Quick Win" if h.confidence >= 0.85 else "Tactical",
                "prerequisites_and_tradeoffs": [
                    "Review commercial terms and operational capacity before rollout.",
                    "Verify correlation findings with direct operational reality.",
                ],
                "is_autonomous_opportunity": True,
                "opportunity_quality_status": h.quality_status.value,
                "opportunity_hypothesis_id": h.id,
            }
            candidates.append(cand)

        return candidates

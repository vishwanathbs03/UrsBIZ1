"""What-If Scenario Simulator Service (Phase 6.19 Extension).

Delivers deterministic financial simulation for hypothetical business shocks and opportunities:
  - Sales volume dips and revenue shocks
  - Supplier cost increases and COGS inflation
  - Key customer churn and concentration risks
  - Hiring expansions and OpEx increases
  - Price elasticity of demand testing
  - Collection cycle / DSO stretch impact on cash runway

Engineering Principles:
  1. Deterministic Financial Math: calculations are strictly formula-driven, never hallucinated.
  2. Grounded Baseline: captures live sales data, AOV, customer concentration, and product margins.
  3. Transparent Disclosures: explicitly declares when benchmarks (COGS, OpEx, Cash) are used due to unconfirmed data.
  4. Mandatory Disclaimer: every output stamps "Illustrative scenario estimate — not a guaranteed prediction."
  5. Strict Tenant Isolation: every query is scoped to business_id and owner_id.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.what_if_scenario import WhatIfScenario
from app.schemas.what_if_scenario import (
    MANDATORY_SCENARIO_DISCLAIMER,
    AssumptionItem,
    MitigationAction,
    ScenarioCaseResult,
    ScenarioComparisonItem,
    ScenarioCompareResponse,
    ScenarioParameterIn,
    ScenarioSaveRequest,
    ScenarioUpdateRequest,
    SimulationResult,
)
from app.services.sales_service import SalesService

logger = logging.getLogger(__name__)


class WhatIfScenarioService:
    """Deterministic simulation and persistence engine for what-if scenarios."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales_service = SalesService(db)

    # -------------------------------------------------------------------------
    # Baseline Assembly & Missing Data Disclosure
    # -------------------------------------------------------------------------

    def _assemble_baseline(
        self,
        business: Business,
        overrides: dict[str, float] | None = None,
    ) -> tuple[dict[str, Any], list[AssumptionItem], list[str]]:
        """Extracts observed baseline figures from live sales data and business digital twin.

        Identifies missing values and transparently substitutes benchmark assumptions.
        """
        overrides = overrides or {}
        assumptions: list[AssumptionItem] = []
        disclosures: list[str] = []

        # 1. Revenue
        sales_summary = self.sales_service.get_summary(business.id)
        has_sales = bool(getattr(sales_summary, "has_sales_data", False)) and getattr(sales_summary, "total_transactions", 0) > 0

        if has_sales and getattr(sales_summary, "total_revenue", 0) > 0:
            annual_rev = float(sales_summary.total_revenue)
            rev_source = "Observed Fact"
            rev_note = f"Observed from {sales_summary.total_transactions} ingested sales transactions."
        elif business.annual_revenue and business.annual_revenue > 0:
            annual_rev = float(business.annual_revenue)
            rev_source = "Observed Fact"
            rev_note = "Derived from verified Business Profile declaration."
        else:
            annual_rev = 1_200_000.0  # ₹12 Lakh MSME benchmark fallback
            rev_source = "Industry Benchmark"
            rev_note = "Standard micro-enterprise revenue benchmark applied because sales data is absent."
            disclosures.append(
                "Missing: Verified sales transactions. Using micro-enterprise benchmark annual revenue of ₹12,00,000 for simulation."
            )

        monthly_rev = annual_rev / 12.0
        assumptions.append(
            AssumptionItem(
                name="Monthly Revenue",
                value=round(monthly_rev, 2),
                unit="INR",
                source=rev_source,  # type: ignore
                note=rev_note,
            )
        )

        # 2. Customer Insights & Concentration
        customer_insights = self.sales_service.get_customer_insights(business.id)
        top_customers = getattr(customer_insights, "top_customers_by_revenue", [])
        if top_customers:
            top_cust = top_customers[0]
            top_cust_name = top_cust.customer_name
            top_cust_spend = float(top_cust.total_revenue)
            top_cust_share = (top_cust_spend / annual_rev * 100.0) if annual_rev > 0 else 25.0
        else:
            top_cust_name = "Key Account"
            top_cust_spend = monthly_rev * 0.25
            top_cust_share = 25.0
            disclosures.append(
                "Missing: Individual customer ledger. Top customer concentration benchmarked at 25% of monthly revenue."
            )

        # 3. Cost of Goods Sold & Gross Margin
        industry = (business.industry or "").lower()
        if "gross_margin_pct" in overrides:
            gross_margin_pct = float(overrides["gross_margin_pct"])
            margin_source = "User Override"
            margin_note = "Explicitly customized by user in scenario parameter overrides."
        else:
            # Standard industry benchmark margins
            if "manufactur" in industry:
                gross_margin_pct = 35.0
            elif "retail" in industry or "trade" in industry:
                gross_margin_pct = 28.0
            elif "service" in industry or "tech" in industry:
                gross_margin_pct = 65.0
            elif "food" in industry or "restaurant" in industry:
                gross_margin_pct = 40.0
            else:
                gross_margin_pct = 32.0

            margin_source = "Industry Benchmark"
            margin_note = f"Standard {business.industry or 'MSME'} gross margin benchmark applied."
            disclosures.append(
                f"Missing: Exact Cost of Goods Sold (COGS). Using standard {business.industry or 'general'} benchmark gross margin of {gross_margin_pct}% — edit this assumption below."
            )

        monthly_cogs = monthly_rev * (1.0 - (gross_margin_pct / 100.0))
        monthly_gross_profit = monthly_rev - monthly_cogs

        assumptions.append(
            AssumptionItem(
                name="Gross Margin",
                value=gross_margin_pct,
                unit="%",
                source=margin_source,  # type: ignore
                note=margin_note,
            )
        )

        # 4. Operating Expenses (OpEx)
        if "monthly_opex_inr" in overrides:
            monthly_opex = float(overrides["monthly_opex_inr"])
            opex_source = "User Override"
            opex_note = "User-entered monthly operating expenses."
        else:
            emp_count = business.employee_count or 4
            # Estimate salary + rent/admin: ₹22,000 per employee + fixed overhead
            estimated_payroll = emp_count * 22_000.0
            estimated_overhead = monthly_rev * 0.12
            monthly_opex = min(monthly_gross_profit * 0.85, estimated_payroll + estimated_overhead)
            opex_source = "Industry Benchmark"
            opex_note = f"Calculated from declared {emp_count} employees plus estimated 12% overhead."
            disclosures.append(
                f"Missing: Expense ledger. Monthly OpEx estimated at ₹{monthly_opex:,.0f} based on {emp_count} employees and baseline overhead."
            )

        monthly_operating_profit = monthly_gross_profit - monthly_opex

        assumptions.append(
            AssumptionItem(
                name="Monthly OpEx",
                value=round(monthly_opex, 2),
                unit="INR",
                source=opex_source,  # type: ignore
                note=opex_note,
            )
        )

        # 5. Cash Balance & Working Capital
        if "cash_balance_inr" in overrides:
            cash_balance = float(overrides["cash_balance_inr"])
            cash_source = "User Override"
            cash_note = "User-entered cash balance."
        else:
            # Benchmark 1.5 months operating expenses as liquidity cushion
            cash_balance = max(100_000.0, monthly_opex * 1.5)
            cash_source = "Industry Benchmark"
            cash_note = "Benchmarked at 1.5 months of operating expenses."
            disclosures.append(
                f"Missing: Live bank/cash balance. Benchmarked at 1.5 months OpEx (₹{cash_balance:,.0f}) — adjust in parameters if known."
            )

        # 6. Credit Sales Ratio Assumption for Receivables Lockup
        if "credit_sales_ratio" in overrides:
            credit_ratio_val = float(overrides["credit_sales_ratio"]) * 100.0
            credit_ratio_src = "User Override"
            credit_ratio_note = "User-specified credit-versus-cash sales percentage."
        else:
            credit_ratio_val = 70.0
            credit_ratio_src = "Planning Assumption (Editable)"
            credit_ratio_note = "Assumes 70% of transactions are on credit terms; cash sales are unaffected by collection delay shocks. This is an editable planning assumption, not a measured ledger value."
            disclosures.append(
                "Planning Assumption: 70% credit sales ratio applied to receivables lockup modeling. Adjust in parameter overrides if your cash-vs-credit split differs."
            )

        assumptions.append(
            AssumptionItem(
                name="Credit Sales Ratio (Planning Assumption)",
                value=round(credit_ratio_val, 1),
                unit="%",
                source=credit_ratio_src,  # type: ignore
                note=credit_ratio_note,
            )
        )

        # Baseline runway in days
        if monthly_operating_profit < 0:
            baseline_runway_days = int((cash_balance / abs(monthly_operating_profit)) * 30)
        else:
            baseline_runway_days = 365  # profitable / self-sustaining

        baseline_metrics = {
            "has_sales_data": has_sales,
            "annual_revenue_inr": round(annual_rev, 2),
            "monthly_revenue_inr": round(monthly_rev, 2),
            "monthly_cogs_inr": round(monthly_cogs, 2),
            "monthly_gross_profit_inr": round(monthly_gross_profit, 2),
            "gross_margin_pct": round(gross_margin_pct, 2),
            "monthly_opex_inr": round(monthly_opex, 2),
            "monthly_operating_profit_inr": round(monthly_operating_profit, 2),
            "cash_balance_inr": round(cash_balance, 2),
            "baseline_runway_days": baseline_runway_days,
            "top_customer_name": top_cust_name,
            "top_customer_spend_inr": round(top_cust_spend, 2),
            "top_customer_share_pct": round(top_cust_share, 2),
            "baseline_dso_days": 35,
        }

        return baseline_metrics, assumptions, disclosures

    # -------------------------------------------------------------------------
    # Deterministic Multi-Case Calculation Engine
    # -------------------------------------------------------------------------

    def _calculate_case(
        self,
        case_label: str,
        baseline: dict[str, Any],
        params: ScenarioParameterIn,
        severity_multiplier: float,
    ) -> ScenarioCaseResult:
        """Calculates exact deterministic metrics for a given severity branch."""
        base_rev = baseline["monthly_revenue_inr"]
        base_cogs = baseline["monthly_cogs_inr"]
        base_opex = baseline["monthly_opex_inr"]
        base_cash = baseline["cash_balance_inr"]
        base_op_profit = baseline["monthly_operating_profit_inr"]
        base_runway = baseline["baseline_runway_days"]

        # 1. Volume & Price Impact
        price_pct = params.price_delta_pct
        if params.price_elasticity_coefficient is not None and params.price_delta_pct != 0.0 and params.sales_volume_delta_pct == 0.0:
            # Model volume response from explicit price elasticity coefficient
            vol_pct = params.price_delta_pct * params.price_elasticity_coefficient * severity_multiplier
        else:
            vol_pct = params.sales_volume_delta_pct * severity_multiplier

        # If customer churn scenario, deduct lost customer monthly revenue
        lost_cust_rev = 0.0
        if params.scenario_type == "customer_churn":
            if params.lost_customer_revenue_inr is not None:
                lost_cust_rev = params.lost_customer_revenue_inr / (12.0 if params.lost_customer_revenue_inr > base_rev else 1.0)
            else:
                lost_cust_rev = baseline["top_customer_spend_inr"] / 12.0
            lost_cust_rev *= severity_multiplier

        vol_multiplier = max(0.0, 1.0 + (vol_pct / 100.0))
        price_multiplier = max(0.0, 1.0 + (price_pct / 100.0))

        projected_rev = max(0.0, (base_rev * vol_multiplier * price_multiplier) - lost_cust_rev)
        rev_delta = projected_rev - base_rev
        rev_delta_pct = (rev_delta / base_rev * 100.0) if base_rev > 0 else 0.0

        # 2. COGS Impact (Supplier price increases)
        cogs_pct = params.cogs_delta_pct * severity_multiplier
        cogs_multiplier = max(0.0, 1.0 + (cogs_pct / 100.0))
        # COGS scales with physical volume sold + supplier price shock
        projected_cogs = max(0.0, base_cogs * vol_multiplier * cogs_multiplier)

        projected_gross_profit = projected_rev - projected_cogs
        gross_profit_delta = projected_gross_profit - baseline["monthly_gross_profit_inr"]
        projected_gross_margin = (
            (projected_gross_profit / projected_rev * 100.0) if projected_rev > 0 else 0.0
        )

        # 3. OpEx Impact (Hiring, operational expansion, or emergency cost containment)
        opex_adj = params.opex_delta_inr
        if case_label == "Optimistic / Best Case" and opex_adj > 0:
            opex_adj *= 0.9  # 10% operational efficiency
        elif case_label == "Conservative / Worst Case" and opex_adj > 0:
            opex_adj *= 1.15  # 15% overrun risk

        projected_opex = max(0.0, base_opex + opex_adj)
        projected_op_profit = projected_gross_profit - projected_opex
        op_profit_delta = projected_op_profit - base_op_profit

        # 4. Working Capital / Cash Runway Impact
        # Delayed customer collections (DSO stretch) locks up receivables strictly on CREDIT sales
        credit_ratio = max(0.0, min(1.0, getattr(params, "credit_sales_ratio", 0.70)))
        dso_stretch = int(params.dso_stretch_days * severity_multiplier)
        credit_projected_rev = projected_rev * credit_ratio
        receivables_locked = (credit_projected_rev / 30.0) * dso_stretch if dso_stretch > 0 else 0.0

        # Effective monthly cash burn
        effective_monthly_burn = max(0.0, -projected_op_profit) + (receivables_locked / 3.0)

        if effective_monthly_burn > 0:
            projected_runway_days: int | None = max(1, int((base_cash / effective_monthly_burn) * 30))
            runway_delta: int | None = projected_runway_days - base_runway
        else:
            projected_runway_days = None  # Profitable, self-funding
            runway_delta = None

        # 5. Break-Even Analysis
        if projected_gross_margin > 0:
            break_even_rev: float | None = round(projected_opex / (projected_gross_margin / 100.0), 2)
        else:
            break_even_rev = None

        return ScenarioCaseResult(
            case_label=case_label,  # type: ignore
            projected_revenue_inr=round(projected_rev, 2),
            revenue_delta_inr=round(rev_delta, 2),
            revenue_delta_pct=round(rev_delta_pct, 2),
            projected_cogs_inr=round(projected_cogs, 2),
            projected_gross_profit_inr=round(projected_gross_profit, 2),
            gross_profit_delta_inr=round(gross_profit_delta, 2),
            gross_margin_pct=round(projected_gross_margin, 2),
            projected_opex_inr=round(projected_opex, 2),
            projected_operating_profit_inr=round(projected_op_profit, 2),
            operating_profit_delta_inr=round(op_profit_delta, 2),
            cash_runway_days_estimated=projected_runway_days,
            cash_runway_days_delta=runway_delta,
            break_even_revenue_inr=break_even_rev,
        )

    # -------------------------------------------------------------------------
    # AI Explanation & Grounded Mitigations
    # -------------------------------------------------------------------------

    def _generate_explanation_and_mitigations(
        self,
        scenario_type: str,
        baseline: dict[str, Any],
        base_case: ScenarioCaseResult,
        worst_case: ScenarioCaseResult,
    ) -> tuple[str, list[str], list[MitigationAction]]:
        """Synthesizes structured business interpretation, risks, and mitigations."""
        vulnerabilities: list[str] = []
        mitigations: list[MitigationAction] = []

        # Analyze vulnerability triggers
        if base_case.operating_profit_delta_inr < 0:
            if base_case.projected_operating_profit_inr < 0:
                vulnerabilities.append(
                    f"Operating deficit: Business becomes cash flow negative, losing ₹{abs(base_case.projected_operating_profit_inr):,.0f} per month under Base Case."
                )
            else:
                vulnerabilities.append(
                    f"Margin compression: Operating profit contracts by ₹{abs(base_case.operating_profit_delta_inr):,.0f} per month ({abs(base_case.revenue_delta_pct):.1f}% impact)."
                )

        if base_case.cash_runway_days_estimated and base_case.cash_runway_days_estimated < 90:
            vulnerabilities.append(
                f"Liquidity vulnerability: Cash runway drops to {base_case.cash_runway_days_estimated} days (less than 3 months of operational cushion)."
            )

        if scenario_type == "customer_churn":
            vulnerabilities.append(
                f"Revenue concentration risk: Top account '{baseline.get('top_customer_name')}' accounts for {baseline.get('top_customer_share_pct')}% of total sales."
            )
            mitigations.append(
                MitigationAction(
                    title="Account Diversification Campaign",
                    impact="Targets 3 secondary accounts to replace 50% of concentrated revenue within 60 days.",
                    timeframe="30–60 days",
                    feasibility="High",
                )
            )
            mitigations.append(
                MitigationAction(
                    title="Customer Retention Contract Lock-in",
                    impact="Offers a 3% volume rebate in exchange for a 6-month minimum supply commitment.",
                    timeframe="14 days",
                    feasibility="High",
                )
            )

        elif scenario_type == "supplier_cost_increase":
            vulnerabilities.append(
                f"Input cost pass-through vulnerability: Gross margin drops from {baseline['gross_margin_pct']}% to {base_case.gross_margin_pct}%."
            )
            mitigations.append(
                MitigationAction(
                    title="Dual-Sourcing Vendor Negotiation",
                    impact="Identify secondary supplier quotes to cap raw material inflation below 4%.",
                    timeframe="21 days",
                    feasibility="Medium",
                )
            )
            mitigations.append(
                MitigationAction(
                    title="Selective Surcharge Pass-Through",
                    impact="Pass a 3.5% energy/raw material surcharge to end-buyers on top products.",
                    timeframe="7–14 days",
                    feasibility="High",
                )
            )

        elif scenario_type == "collection_delay":
            vulnerabilities.append(
                "Working capital lockup: Stretched debtor days tie up liquidity in uncollected invoices."
            )
            mitigations.append(
                MitigationAction(
                    title="Early Payment Cash Discount (2/10 Net 30)",
                    impact="Offer a 2% discount for payments within 10 days to pull collections forward.",
                    timeframe="Immediate",
                    feasibility="High",
                )
            )
            mitigations.append(
                MitigationAction(
                    title="TReDS / Invoice Discounting Facility",
                    impact="Discount accepted MSME invoices on TReDS at prime repo rates for instant cash.",
                    timeframe="15 days",
                    feasibility="Medium",
                )
            )

        else:
            # General volume / pricing / hiring mitigations
            mitigations.append(
                MitigationAction(
                    title="Variable Cost Restructuring",
                    impact="Tie sales bonuses directly to collected gross contribution margin rather than gross sales.",
                    timeframe="30 days",
                    feasibility="High",
                )
            )
            mitigations.append(
                MitigationAction(
                    title="High-Margin Product Focus",
                    impact="Prioritize production scheduling for the top 2 highest gross margin SKUs.",
                    timeframe="7 days",
                    feasibility="High",
                )
            )

        if not vulnerabilities:
            vulnerabilities.append("Resilient baseline: Business maintains positive operating cushion under Base Case conditions.")

        # Executive Summary
        summary = (
            f"Under the {scenario_type.replace('_', ' ').title()} scenario, projected monthly revenue shifts to "
            f"₹{base_case.projected_revenue_inr:,.0f} ({base_case.revenue_delta_pct:+.1f}%), resulting in monthly operating profit of "
            f"₹{base_case.projected_operating_profit_inr:,.0f}. "
            f"Worst-case stress tests indicate an operational downside of ₹{worst_case.operating_profit_delta_inr:,.0f}/mo. "
            f"Recommended priorities focus on {mitigations[0].title.lower()} and preserving liquidity cushion."
        )

        return summary, vulnerabilities, mitigations

    # -------------------------------------------------------------------------
    # Public Simulation API
    # -------------------------------------------------------------------------

    def simulate(
        self,
        business_id: int,
        owner_id: int,
        title: str,
        params: ScenarioParameterIn,
    ) -> SimulationResult:
        """Runs the deterministic multi-case simulation without mutating database state."""
        business = self.db.execute(
            select(Business).where(
                Business.id == business_id,
                Business.owner_id == owner_id,
            )
        ).scalar_one_or_none()

        if not business:
            raise ValueError(f"Business {business_id} not found or not owned by user {owner_id}")

        # 1. Assemble verified baseline and benchmark assumptions
        baseline, assumptions, disclosures = self._assemble_baseline(
            business, overrides=params.assumptions_overrides
        )

        # 2. Compute the 3 Cases (Base: 1.0x, Worst: 1.5x stress, Best: 0.6x mitigated)
        base_case = self._calculate_case("Base Case", baseline, params, severity_multiplier=1.0)
        worst_case = self._calculate_case(
            "Conservative / Worst Case", baseline, params, severity_multiplier=1.4
        )
        best_case = self._calculate_case(
            "Optimistic / Best Case", baseline, params, severity_multiplier=0.65
        )

        # 3. AI Explanation & Mitigations
        summary, vulnerabilities, mitigations = self._generate_explanation_and_mitigations(
            params.scenario_type, baseline, base_case, worst_case
        )

        return SimulationResult(
            scenario_type=params.scenario_type,
            title=title,
            baseline_metrics=baseline,
            assumptions_applied=assumptions,
            missing_data_disclosures=disclosures,
            cases=[base_case, worst_case, best_case],
            ai_executive_summary=summary,
            vulnerabilities_exposed=vulnerabilities,
            mitigation_actions=mitigations,
            disclaimer=MANDATORY_SCENARIO_DISCLAIMER,
        )

    # -------------------------------------------------------------------------
    # Scenario Persistence & Management (CRUD)
    # -------------------------------------------------------------------------

    def save_scenario(
        self,
        business_id: int,
        owner_id: int,
        request: ScenarioSaveRequest,
    ) -> WhatIfScenario:
        """Persists a simulated scenario with its parameters and projection results."""
        simulation = self.simulate(
            business_id=business_id,
            owner_id=owner_id,
            title=request.title,
            params=request.parameters,
        )

        scenario = WhatIfScenario(
            business_id=business_id,
            owner_id=owner_id,
            title=request.title,
            scenario_type=request.scenario_type,
            description=request.description,
            baseline_metrics=simulation.baseline_metrics,
            parameters=request.parameters.model_dump(),
            projection_result=simulation.model_dump(),
            tags=request.tags or [],
        )
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def list_scenarios(
        self,
        business_id: int,
        owner_id: int,
    ) -> list[WhatIfScenario]:
        """Lists all saved scenarios for the active business."""
        stmt = (
            select(WhatIfScenario)
            .where(
                WhatIfScenario.business_id == business_id,
                WhatIfScenario.owner_id == owner_id,
            )
            .order_by(WhatIfScenario.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_scenario(
        self,
        business_id: int,
        owner_id: int,
        scenario_id: int,
    ) -> WhatIfScenario | None:
        """Fetches a single scenario with strict tenant validation."""
        stmt = select(WhatIfScenario).where(
            WhatIfScenario.id == scenario_id,
            WhatIfScenario.business_id == business_id,
            WhatIfScenario.owner_id == owner_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_scenario(
        self,
        business_id: int,
        owner_id: int,
        scenario_id: int,
        request: ScenarioUpdateRequest,
    ) -> WhatIfScenario | None:
        """Updates scenario metadata or re-runs projection with updated parameters."""
        scenario = self.get_scenario(business_id, owner_id, scenario_id)
        if not scenario:
            return None

        if request.title is not None:
            scenario.title = request.title
        if request.description is not None:
            scenario.description = request.description
        if request.tags is not None:
            scenario.tags = request.tags

        if request.parameters is not None:
            scenario.parameters = request.parameters.model_dump()
            # Re-simulate with updated parameters
            sim = self.simulate(
                business_id=business_id,
                owner_id=owner_id,
                title=scenario.title,
                params=request.parameters,
            )
            scenario.baseline_metrics = sim.baseline_metrics
            scenario.projection_result = sim.model_dump()

        self.db.commit()
        self.db.refresh(scenario)
        return scenario

    def delete_scenario(
        self,
        business_id: int,
        owner_id: int,
        scenario_id: int,
    ) -> bool:
        """Deletes a saved scenario with strict tenant verification."""
        scenario = self.get_scenario(business_id, owner_id, scenario_id)
        if not scenario:
            return False

        self.db.delete(scenario)
        self.db.commit()
        return True

    def compare_scenarios(
        self,
        business_id: int,
        owner_id: int,
        scenario_ids: list[int],
    ) -> ScenarioCompareResponse:
        """Performs side-by-side comparison across 2 or 3 saved scenarios."""
        stmt = select(WhatIfScenario).where(
            WhatIfScenario.id.in_(scenario_ids),
            WhatIfScenario.business_id == business_id,
            WhatIfScenario.owner_id == owner_id,
        )
        saved = list(self.db.execute(stmt).scalars().all())
        if len(saved) < 2:
            raise ValueError("At least 2 valid scenarios belonging to your business are required for comparison.")

        items: list[ScenarioComparisonItem] = []
        for s in saved:
            proj = s.projection_result
            cases = proj.get("cases", [])
            base = next((c for c in cases if c.get("case_label") == "Base Case"), cases[0] if cases else {})
            vulns = proj.get("vulnerabilities_exposed", ["Standard scenario risk"])

            items.append(
                ScenarioComparisonItem(
                    id=s.id,
                    title=s.title,
                    scenario_type=s.scenario_type,
                    base_case_revenue_delta_inr=base.get("revenue_delta_inr", 0.0),
                    base_case_revenue_delta_pct=base.get("revenue_delta_pct", 0.0),
                    base_case_profit_delta_inr=base.get("operating_profit_delta_inr", 0.0),
                    base_case_runway_delta_days=base.get("cash_runway_days_delta"),
                    top_vulnerability=vulns[0] if vulns else "Operational exposure",
                    created_at=s.created_at,
                )
            )

        # Sort from highest profit drop to lowest
        items.sort(key=lambda x: x.base_case_profit_delta_inr)
        worst = items[0]
        summary = (
            f"Comparison of {len(items)} scenarios reveals that '{worst.title}' ({worst.scenario_type.replace('_', ' ')}) "
            f"presents the greatest financial downside, with a projected monthly operating profit shift of "
            f"₹{worst.base_case_profit_delta_inr:,.0f}."
        )

        return ScenarioCompareResponse(
            scenarios=items,
            comparison_summary=summary,
            disclaimer=MANDATORY_SCENARIO_DISCLAIMER,
        )

"""ScenarioSimulator — Sprint H8.4 / AI-5 Business Scenario Simulator Engine.

H8.4 — 5 hard-coded deterministic branches producing a
:class:`ScenarioSimulationResult` across 8 dimensions.

AI-5 — extended with 3 new branches (``price_change``,
``supplier_concentration``, ``inventory_change``) so the chat
path can produce scenario envelopes for the 8 mandatory test
cases from the brief. Dispatcher pattern: ``simulate()``
classifies the prompt into one of 8 scenario types and
delegates to a branch method.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScenarioSimulationResult:
    """Outcome of a Business Scenario Simulation across 8 dimensions."""

    scenario_title: str
    scenario_type: str
    # one of:
    #   "hiring", "export_growth", "funding", "commodity_cost",
    #   "facility_expansion", "equipment_capex",            (H8.4)
    #   "price_change", "supplier_concentration", "inventory_change"  (AI-5)
    revenue_impact: str
    cashflow_impact: str
    risks_identified: tuple[str, ...] = field(default_factory=tuple)
    capacity_impact: str = ""
    export_impact: str = ""
    hiring_impact: str = ""
    profitability_impact: str = ""
    timeline_horizon: str = "6-12 months"
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = "Illustrative scenario estimate — not a prediction"

    def to_markdown(self) -> str:
        """Format simulation result as clean Markdown card."""
        lines: list[str] = []
        lines.append(f"### SCENARIO SIMULATION: {self.scenario_title.upper()}")
        lines.append(f"*{self.disclaimer}*")
        lines.append("")
        lines.append(f"- **Revenue Impact**: {self.revenue_impact}")
        lines.append(f"- **Cashflow Impact**: {self.cashflow_impact}")
        if self.profitability_impact:
            lines.append(f"- **Profitability & Margins**: {self.profitability_impact}")
        if self.capacity_impact:
            lines.append(f"- **Capacity & Utilization**: {self.capacity_impact}")
        if self.export_impact:
            lines.append(f"- **Export Expansion**: {self.export_impact}")
        if self.hiring_impact:
            lines.append(f"- **Hiring & Payroll Overhead**: {self.hiring_impact}")
        lines.append(f"- **Timeline Horizon**: {self.timeline_horizon}")
        if self.risks_identified:
            lines.append("- **Risks & Vulnerabilities**:")
            for r in self.risks_identified:
                lines.append(f"  * {r}")
        if self.assumptions:
            lines.append("- **Key Scenario Assumptions**:")
            for a in self.assumptions:
                lines.append(f"  * {a}")
        return "\n".join(lines)


# AI-5 — canonical disclaimer used by the scenario envelope.
SCENARIO_DISCLAIMER = "Illustrative scenario — not a prediction."


class ScenarioSimulator:
    """Deterministic MSME Business Scenario Simulator.

    H8.4 — 5 branches: ``equipment_capex``, ``hiring``,
    ``export_growth``, ``funding``, ``commodity_cost`` /
    ``facility_expansion`` (default).

    AI-5 — 3 new branches: ``price_change``,
    ``supplier_concentration``, ``inventory_change``.
    """

    def is_simulation_query(self, prompt: str) -> bool:
        """Check if user prompt is asking a 'What if' scenario question."""
        p_low = (prompt or "").lower()
        keywords = ("what if", "scenario", "simulate", "if i hire", "if funding", "if exports", "if prices", "if i open", "buy", "machine", "reach")
        return any(kw in p_low for kw in keywords)

    # ------------------------------------------------------------------
    # AI-5 — Branch dispatcher
    # ------------------------------------------------------------------

    def classify_prompt(self, prompt: str) -> str:
        """Return one of the 8 scenario types based on prompt keywords.

        Order matters: more specific patterns first.
        """
        p_low = (prompt or "").lower()

        # 1. Supplier concentration — only when supplier is mentioned
        if "supplier" in p_low:
            return "supplier_concentration"

        # 2. Inventory / stock change
        if "inventory" in p_low or "stock" in p_low:
            return "inventory_change"

        # 3. Commodity / raw material cost — checked BEFORE price_change
        # so "cotton prices rise" stays in commodity_cost, not price_change.
        if (
            "cotton" in p_low
            or "raw material" in p_low
            or ("cost" in p_low and "if" in p_low)
        ):
            return "commodity_cost"

        # 4. Price change — explicit pct with price keyword.
        # Requires "price[s]" + "+/-" OR a "%" token.  Plain "price +"
        # without "%" falls through.
        if re.search(r"price[s]?\s*[+\-−]\s*\d+\s*%", p_low) or (
            "prices" in p_low and re.search(r"\d+\s*%", p_low)
        ):
            return "price_change"

        # 5. Hiring / employees
        if "hire" in p_low or "employee" in p_low:
            return "hiring"

        # 6. Export expansion (before funding, because "export" + "%")
        if "export" in p_low or "international" in p_low or "europe" in p_low:
            return "export_growth"

        # 7. Funding / capital / lakh
        if (
            "fund" in p_low
            or "lakh" in p_low
            or "crore" in p_low
            or "capital" in p_low
            or "invest" in p_low
        ):
            return "funding"

        # 8. Equipment / machine capex
        if "machine" in p_low or "equipment" in p_low:
            return "equipment_capex"

        # 9. Default — facility expansion
        return "facility_expansion"

    def simulate(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        """Run deterministic financial & operational simulation.

        AI-5: dispatches by ``classify_prompt`` so all 8 branches
        are covered. Returns a single :class:`ScenarioSimulationResult`.
        """
        scenario_type = self.classify_prompt(prompt)
        if scenario_type == "price_change":
            return self._branch_price_change(prompt, context)
        if scenario_type == "supplier_concentration":
            return self._branch_supplier_concentration(prompt, context)
        if scenario_type == "inventory_change":
            return self._branch_inventory_change(prompt, context)
        # Legacy H8.4 branches — keep their original behavior verbatim.
        if scenario_type == "equipment_capex":
            return self._branch_equipment_capex(prompt, context)
        if scenario_type == "hiring":
            return self._branch_hiring(prompt, context)
        if scenario_type == "export_growth":
            return self._branch_export_growth(prompt, context)
        if scenario_type == "funding":
            return self._branch_funding(prompt, context)
        if scenario_type == "commodity_cost":
            return self._branch_commodity_cost(prompt, context)
        return self._branch_facility_expansion(prompt, context)

    # ------------------------------------------------------------------
    # H8.4 — original 5 branches (kept verbatim to preserve tests)
    # ------------------------------------------------------------------

    def _branch_equipment_capex(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        return ScenarioSimulationResult(
            scenario_title="Automated Machinery Capex Procurement",
            scenario_type="equipment_capex",
            revenue_impact=f"Estimated top-line expansion of +₹{base_revenue * 0.25 / 100000:.1f} Lakh (+25% Output)",
            cashflow_impact="Initial Capex outlay of ₹12 Lakh with 10-month payback horizon",
            profitability_impact="Net profit margin increases by +3.2% due to lower per-unit labor COGS",
            capacity_impact="Daily manufacturing unit output increases from 1,200 to 1,600 units",
            export_impact="Meets international buyer quality precision specifications",
            hiring_impact="Requires 2 trained CNC machine technicians",
            timeline_horizon="4-6 months procurement, installation & calibration",
            risks_identified=(
                "Short-term cashflow pressure during 60-day installation phase",
                "Technician learning curve impact during initial 30 days",
            ),
            assumptions=(
                "Equipment financed via 70% bank term loan under CGTMSE scheme at 8.5% interest",
                "Maintenance contract included under 3-year OEM warranty",
            ),
        )

    def _branch_hiring(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        p_low = (prompt or "").lower()
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        match = re.search(r"(\d+)", p_low)
        count = int(match.group(1)) if match else 10
        payroll_cost = count * 35000 * 12
        rev_gain = base_revenue * 0.18
        return ScenarioSimulationResult(
            scenario_title=f"Hiring {count} Employees",
            scenario_type="hiring",
            revenue_impact=f"Estimated revenue boost of +₹{rev_gain / 100000:.1f} Lakh (+18% capacity)",
            cashflow_impact=f"Annual payroll expenditure increase of ₹{payroll_cost / 100000:.1f} Lakh",
            profitability_impact="Initial net margin dip of ~2.5% during 60-day onboarding, recovering after month 4",
            capacity_impact=f"Production throughput increases by ~22%",
            export_impact="Enables fulfillment of pending international orders",
            hiring_impact=f"Add {count} staff to operations and quality assurance",
            timeline_horizon="3-6 months onboarding & productivity ramp",
            risks_identified=(
                f"Payroll overhead increase of ₹{payroll_cost / 1200000:.1f}L/month prior to revenue realization",
                "Initial drop in worker productivity during training",
            ),
            assumptions=(
                f"Average monthly salary of ₹35,000 per employee",
                "Existing factory space accommodates additional headcount",
            ),
        )

    def _branch_export_growth(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        p_low = (prompt or "").lower()
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        match = re.search(r"(\d+)%", p_low)
        pct = int(match.group(1)) if match else 20
        rev_gain = base_revenue * (pct / 100.0)
        return ScenarioSimulationResult(
            scenario_title=f"Export Increase of {pct}%",
            scenario_type="export_growth",
            revenue_impact=f"Projected revenue addition of +₹{rev_gain / 100000:.1f} Lakh",
            cashflow_impact="Working capital cycle extends by 30-45 days due to international shipping credit terms",
            profitability_impact=f"Gross margin expands by +3.5% due to higher export realization rates",
            capacity_impact="Factory operating capacity rises from 70% to 88%",
            export_impact=f"Export revenue share increases by +{pct}%",
            hiring_impact="Requires 2 export documentation & logistics specialists",
            timeline_horizon="6-12 months export shipping & payment cycle",
            risks_identified=(
                "Currency exchange rate fluctuation risk",
                "Working capital stretch due to longer 90-day L/C credit cycles",
            ),
            assumptions=(
                f"Export orders realize {pct}% higher price realization than domestic sales",
                "ECGC export credit insurance coverage obtained",
            ),
        )

    def _branch_funding(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        p_low = (prompt or "").lower()
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        match = re.search(r"(\d+)", p_low)
        amount = int(match.group(1)) if match else 50
        return ScenarioSimulationResult(
            scenario_title=f"Capital Injection of ₹{amount} Lakh",
            scenario_type="funding",
            revenue_impact=f"Enables ₹{base_revenue * 0.25 / 100000:.1f} Lakh revenue expansion via machinery upgrade",
            cashflow_impact=f"Liquidity buffer increases by ₹{amount} Lakh",
            profitability_impact="Operating margin improves by +4.0% through bulk raw material purchases",
            capacity_impact="Automated machinery increases daily unit output by 35%",
            export_impact="Meets quality audit criteria for European buyers",
            hiring_impact="Add 3 skilled machine operators",
            timeline_horizon="6-9 months machinery procurement & commissioning",
            risks_identified=(
                "Debt servicing obligation if capital includes term loan component",
                "Depreciation & interest expense impact on net profit",
            ),
            assumptions=(
                f"₹{amount} Lakh allocated: 60% capex equipment, 40% working capital",
                "Interest rate assumption of 8.5% p.a. if funded via collateralized debt",
            ),
        )

    def _branch_commodity_cost(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        return ScenarioSimulationResult(
            scenario_title="Raw Material Cost Increase (Commodity Volatility)",
            scenario_type="commodity_cost",
            revenue_impact="Flat revenue unless product prices are revised upwards by 5-8%",
            cashflow_impact="Cash outlays for raw material inventory rise by ~12%",
            profitability_impact="Gross profit margin compresses by -4.2% if cost increase cannot be passed to buyers",
            capacity_impact="Production volume maintained but inventory holding cost increases",
            export_impact="Export competitiveness impacted against foreign suppliers",
            hiring_impact="Freeze non-essential hiring to preserve cash",
            timeline_horizon="Immediate (1-3 months inventory cycle)",
            risks_identified=(
                "Margin squeeze from rigid buyer price contracts",
                "Working capital shortfall due to higher upfront procurement costs",
            ),
            assumptions=(
                "Raw material constitutes 55% of total Cost of Goods Sold (COGS)",
                "Partial cost pass-through of 50% achieved with domestic buyers",
            ),
        )

    def _branch_facility_expansion(self, prompt: str, context: Any) -> ScenarioSimulationResult:
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        return ScenarioSimulationResult(
            scenario_title="Second Factory Facility Expansion",
            scenario_type="facility_expansion",
            revenue_impact=f"Doubles maximum production capacity, enabling +₹{base_revenue * 0.6 / 100000:.1f} Lakh revenue over 18 months",
            cashflow_impact="High capex cash outflow during initial 6 months construction phase",
            profitability_impact="Break-even expected at month 10 following operational commencement",
            capacity_impact="Total manufacturing footprint expands by +100%",
            export_impact="Dedicated export manufacturing line established",
            hiring_impact="Requires 15 additional factory floor workers and 1 plant manager",
            timeline_horizon="12-18 months greenfield/brownfield expansion",
            risks_identified=(
                "Fixed overhead cost burden during initial low-utilization months",
                "Construction & statutory compliance approval delays",
            ),
            assumptions=(
                "Industrial land leased in MSME manufacturing cluster",
                "Phase 1 utilization reaches 50% within 4 months of commissioning",
            ),
        )

    # ------------------------------------------------------------------
    # AI-5 — new branches
    # ------------------------------------------------------------------

    def _branch_price_change(
        self, prompt: str, context: Any
    ) -> ScenarioSimulationResult:
        """``What if I raise prices 5%?`` style questions.

        Math:
            rev_delta = base_revenue × (pct / 100) × elasticity

        where elasticity defaults to -1.5 for a price raise (volume
        drops 1.5× more than price rises — staple-product heuristic)
        and +1.2 for a price cut.
        """
        p_low = (prompt or "").lower()
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000

        # Extract pct — supports "raise prices 5%", "increase price by 7%",
        # "prices +5%", "lower prices 10%", "cut price 3%"
        pct_match = re.search(r"(\d+)\s*%", p_low)
        pct = int(pct_match.group(1)) if pct_match else 5

        is_raise = bool(
            re.search(r"\b(raise|increase|hike|up|go\s*up|more|higher)\b", p_low)
        ) or bool(re.search(r"price[s]?\s*\+\s*\d+", p_low))
        is_lower = bool(
            re.search(r"\b(lower|cut|reduce|drop|down|less|cheaper|discount)\b", p_low)
        ) or bool(re.search(r"price[s]?\s*[−-]\s*\d+", p_low))

        if is_lower and not is_raise:
            elasticity = 1.2  # cut prices → volume rises 1.2× the cut
            direction = "lower"
        else:
            elasticity = -1.5  # default raise
            direction = "raise"

        rev_delta = base_revenue * (pct / 100.0) * elasticity
        sign = "+" if rev_delta >= 0 else ""
        rev_pct = (rev_delta / base_revenue) * 100.0

        return ScenarioSimulationResult(
            scenario_title=f"Price {direction} of {pct}%",
            scenario_type="price_change",
            revenue_impact=(
                f"Estimated revenue {sign}₹{abs(rev_delta) / 100000:.1f} Lakh "
                f"(≈{rev_pct:+.1f}% net of demand elasticity)"
            ),
            cashflow_impact=(
                "Operating cashflow shifts "
                + ("upward" if rev_delta >= 0 else "downward")
                + f" by ≈₹{abs(rev_delta) / 100000:.1f} Lakh/year before cost changes"
            ),
            profitability_impact=(
                "Gross margin expands by ~"
                + f"{pct * 0.6:.1f}%" if is_raise else
                "Gross margin compresses by ~"
                + f"{pct * 0.4:.1f}% on lower volume"
            ),
            capacity_impact=(
                "Production throughput unchanged; only pricing altered"
            ),
            export_impact=(
                "Export competitiveness "
                + ("rises" if is_raise else "falls")
                + " on per-unit realization"
            ),
            hiring_impact="No hiring change required for a pricing change",
            timeline_horizon="Immediate (1-3 months for customer renegotiation)",
            risks_identified=(
                "Volume may fall more than the elasticity assumption suggests",
                "Competitor response (price war, customer churn) not modeled",
                "Customer retention risk during the transition quarter",
            ),
            assumptions=(
                f"Demand elasticity = {elasticity} (raise) / {1.2 if is_raise else -1.5} (lower)",
                "Cost base (raw material, payroll) held constant",
                "No product-mix shift in the scenario window",
            ),
        )

    def _branch_supplier_concentration(
        self, prompt: str, context: Any
    ) -> ScenarioSimulationResult:
        """``What if supplier concentration falls from 75% to 40%?``.

        Heuristic:
            * If the user gives two percentages, use them.
            * Otherwise default to current share = 75%, target = 40%.
            * Downside revenue impact = base_revenue × top_share × 0.6
              (60% disruption if the dominant supplier fails).
        """
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000
        suppliers = list(getattr(context, "supplier_dependencies", []) or [])

        pcts = re.findall(r"(\d+)\s*%", prompt or "")
        current_share = (int(pcts[0]) / 100.0) if len(pcts) >= 1 else 0.75
        target_share = (int(pcts[1]) / 100.0) if len(pcts) >= 2 else 0.40

        downside_revenue = base_revenue * current_share * 0.6

        # Diversification scenario: spreading to N suppliers where
        # target_share = 1/N; benefit measured as downside reduction.
        downside_at_target = base_revenue * target_share * 0.6
        downside_avoided = downside_revenue - downside_at_target

        return ScenarioSimulationResult(
            scenario_title=(
                f"Supplier concentration reduction from "
                f"{int(current_share * 100)}% to {int(target_share * 100)}%"
            ),
            scenario_type="supplier_concentration",
            revenue_impact=(
                f"Downside-revenue-at-risk drops from "
                f"₹{downside_revenue / 100000:.1f} Lakh → "
                f"₹{downside_at_target / 100000:.1f} Lakh "
                f"(≈₹{downside_avoided / 100000:.1f} Lakh of disruption avoided)"
            ),
            cashflow_impact=(
                "Working capital may rise temporarily as new supplier "
                "credit terms are negotiated"
            ),
            profitability_impact=(
                "Margins stable; small per-unit cost variance expected "
                "across the new supplier base"
            ),
            capacity_impact=(
                "Production capacity unchanged; only the supply-side "
                "risk profile shifts"
            ),
            export_impact=(
                "Lower single-supplier risk improves buyer audit scores"
            ),
            hiring_impact=(
                "May require 1 procurement specialist during transition"
            ),
            timeline_horizon="3-9 months supplier onboarding & qualification",
            risks_identified=(
                "New-supplier quality variance during ramp-up",
                "Lost volume during the transition overlap period",
                "Per-unit cost variance vs the previous dominant supplier",
            ),
            assumptions=(
                f"Current top supplier share assumed at {int(current_share * 100)}%",
                "60% disruption severity used as the worst-case scenario",
                f"Identified supplier dependencies: {len(suppliers)}",
            ),
        )

    def _branch_inventory_change(
        self, prompt: str, context: Any
    ) -> ScenarioSimulationResult:
        """``What if I reduce inventory by 30 days?`` style.

        Math:
            working_capital_delta = base_revenue × 0.15 × (pct_days / 365)
            pct_days is days-reduction parsed from prompt (default 30).
        """
        p_low = (prompt or "").lower()
        base_revenue = getattr(context, "annual_revenue_inr", 18000000) or 18000000

        day_match = re.search(r"(\d+)\s*days?", p_low)
        pct_match = re.search(r"(\d+)\s*%", p_low)
        if day_match:
            days = int(day_match.group(1))
        elif pct_match:
            days = int(int(pct_match.group(1)) * 3.65)  # 100% ≈ 365 days
        else:
            days = 30

        # working_capital_delta is positive when inventory shrinks
        # (cash freed), negative when inventory grows (cash tied up).
        is_reduction = bool(
            re.search(r"\b(reduce|cut|lower|shrink|drop|down)\b", p_low)
        )
        sign = -1 if is_reduction else 1
        wc_delta = sign * base_revenue * 0.15 * (days / 365.0)

        return ScenarioSimulationResult(
            scenario_title=(
                f"Inventory {['increase', 'reduction'][is_reduction]} "
                f"of {days} days"
            ),
            scenario_type="inventory_change",
            revenue_impact=(
                "Revenue impact depends on demand-served-rate; cannot be "
                "inferred from the working-capital shift alone"
            ),
            cashflow_impact=(
                f"Working-capital shift of "
                + ("+" if wc_delta >= 0 else "")
                + f"₹{wc_delta / 100000:.1f} Lakh freed-up"
                if is_reduction
                else f"Working-capital shift of ₹{abs(wc_delta) / 100000:.1f} Lakh tied-up"
            ),
            profitability_impact=(
                "Margin effect negligible (holding-cost & obsolescence "
                "impact estimated but small at this scale)"
            ),
            capacity_impact="Production throughput unchanged",
            export_impact=(
                "Export delivery SLAs may be tighter; current inventory "
                "buffer may not be sufficient for export lead times"
            ),
            hiring_impact="No hiring change required",
            timeline_horizon="Immediate to 3 months depending on SKU cycle",
            risks_identified=(
                "Stock-out risk if demand spikes above the leaner buffer",
                "Demand pattern is not knowable from this prompt alone",
            ),
            assumptions=(
                "Inventory carrying cost approximated at 15% of revenue",
                "Demand variability not modeled",
                "Per-SKU mix held constant",
            ),
        )

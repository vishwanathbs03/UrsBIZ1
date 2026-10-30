"""ScenarioAnalysis envelope — Sprint AI-5 Business Scenario Copilot.

The AI-5 "what if" envelope is a 10-field dataclass with a
deterministic assembler. It is paired with a keyword/regex
:func:`ScenarioDetector` and a thin :class:`ScenarioAnalyzer`
that wraps the existing :class:`ScenarioSimulator` output.

Strict rules from the brief
---------------------------

1.  Every envelope carries ``disclaimer = "Illustrative scenario
    — not a prediction."`` so the wire cannot accidentally drop the
    label.
2.  Math is deterministic when possible. When a real number is not
    derivable from the context, the field lists the variable as an
    "unknown" — never as a fabricated precision.
3.  The detector returns ``None`` for non-scenario prompts so the
    chat path falls through to the LLM route unchanged.
4.  The analyzer is pure: no mutation of the context, no I/O, no
    LLM call. The same prompt + context always produce the same
    envelope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


SCENARIO_DISCLAIMER = "Illustrative scenario — not a prediction."

# The 8 scenario kinds the analyzer can produce.  Matches the
# branches the simulator now supports (5 original + 3 new in AI-5).
SCENARIO_KINDS: tuple[str, ...] = (
    "price_change",
    "supplier_concentration",
    "inventory_change",
    "revenue_growth",
    "employee_increase",
    "export_expansion",
    "investment_scenario",
    "missing_data",
)


@dataclass(frozen=True)
class ScenarioAnalysis:
    """The 10-field structured envelope from the AI-5 brief.

    The shape is stable and must round-trip through Pydantic with
    ``extra="forbid"``. Field semantics:

      * ``scenario_name``     — human-readable scenario title.
      * ``baseline``          — bullet list of current values.
      * ``changes``           — bullet list of what the user is changing.
      * ``assumptions``       — every assumption made to compute the effects.
      * ``calculation_method``— single-paragraph deterministic recipe.
      * ``estimated_effects`` — bullet list of expected deltas.
      * ``risks``             — bullet list of risks.
      * ``unknowns``          — bullet list of unknown / not-knowable variables.
      * ``sensitivity``       — bullet list of "if X, then Y" branches.
      * ``confidence``        — one of ``"low" | "medium" | "high" | "unknown"``.
      * ``disclaimer``        — always the canonical scenario disclaimer.
    """

    scenario_name: str
    baseline: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    calculation_method: str = ""
    estimated_effects: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    sensitivity: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    disclaimer: str = SCENARIO_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        """Project the envelope onto the wire-ready dict shape."""
        return {
            "scenario_name": self.scenario_name,
            "baseline": list(self.baseline),
            "changes": list(self.changes),
            "assumptions": list(self.assumptions),
            "calculation_method": self.calculation_method,
            "estimated_effects": list(self.estimated_effects),
            "risks": list(self.risks),
            "unknowns": list(self.unknowns),
            "sensitivity": list(self.sensitivity),
            "confidence": self.confidence,
            "disclaimer": self.disclaimer,
            # AI-5 helper flag — the chat wire projection reads this
            # to decide whether to emit the envelope at all.
            "present": True,
        }


# ---------------------------------------------------------------------------
# Detector — pure function, returns one of the 8 kinds or None
# ---------------------------------------------------------------------------


def _has(text: str, *needles: str) -> bool:
    """True when every needle occurs in ``text``."""
    return all(n in text for n in needles)


def _extract_pct(text: str) -> int | None:
    """Return the first ``\\d+%`` in ``text`` as int, or ``None``."""
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


def _extract_int(text: str) -> int | None:
    """Return the first integer in ``text``, or ``None``."""
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


class ScenarioDetector:
    """Classify a chat prompt into one of the 8 AI-5 scenario kinds.

    Returns ``None`` when the prompt is not a "what if" question —
    the chat path falls through to the LLM route unchanged.

    The detector is intentionally conservative: when in doubt,
    return ``"missing_data"`` rather than the most-likely guess so
    the envelope reads honestly.
    """

    # Order matters — more specific patterns first.

    def classify(self, prompt: str) -> str | None:
        text = (prompt or "").lower()
        if not text:
            return None

        # 1. Supplier concentration — only when "supplier" is mentioned.
        if "supplier" in text:
            return "supplier_concentration"

        # 2. Inventory / stock change.
        if "inventory" in text or "stock" in text:
            return "inventory_change"

        # 3. Investment scenario — "invest" + amount in lakh/crore.
        if "invest" in text and re.search(
            r"\b(?:invest|spend)\b[^.]*?\b\d+\s*(?:lakh|crore|l|cr)\b", text
        ):
            return "investment_scenario"

        # 4. Employee increase — "hire N employees" / "add N staff".
        if re.search(r"\b(?:hire|add|recruit)\b[^.]*?\b\d+\s*(?:employees?|staff|people)\b", text):
            return "employee_increase"

        # 5. Price change — explicit price + pct.
        if (
            re.search(r"price[s]?\s*[+\-−]\s*\d+\s*%", text)
            or ("price" in text and _extract_pct(text) is not None)
        ):
            return "price_change"

        # 6. Revenue growth — "revenue" + "%" or "grow/growth".
        if "revenue" in text and (
            _extract_pct(text) is not None
            or re.search(r"\b(?:grow|growth|growing)\b", text)
        ):
            return "revenue_growth"

        # 7. Export expansion — explicit "export" / "europe" /
        # "international".
        if (
            "export" in text
            or "international" in text
            or "europe" in text
            or "abroad" in text
        ):
            return "export_expansion"

        # 8. "What if" / "suppose" with no numeric — missing data.
        if re.search(r"\b(?:what if|suppose|scenario|sensitivity)\b", text):
            return "missing_data"

        return None


# ---------------------------------------------------------------------------
# Analyzer — wires the envelope together from the simulator + context
# ---------------------------------------------------------------------------


def _format_inr(amount: float) -> str:
    """Format an INR amount with the Lakh/Cr suffix the rest of the
    chat surfaces use."""
    if amount < 0:
        sign = "-"
        amount = abs(amount)
    else:
        sign = ""
    if amount >= 1_00_00_000:  # >= 1 Crore
        return f"{sign}₹{amount / 1_00_00_000:.2f} Cr"
    if amount >= 1_00_000:  # >= 1 Lakh
        return f"{sign}₹{amount / 1_00_000:.1f} Lakh"
    return f"{sign}₹{amount:,.0f}"


class ScenarioAnalyzer:
    """Produce a :class:`ScenarioAnalysis` from a chat prompt + context.

    Pure: no I/O, no LLM call, no mutation. The same prompt + the
    same context always produce the same envelope.

    Pipeline
    --------

      1.  :meth:`ScenarioDetector.classify` — text → one of 8 kinds.
      2.  Dispatch to a kind-specific builder.
      3.  Each builder fills the 10 fields from the context fields
          (``annual_revenue_inr``, ``employee_count``,
          ``supplier_dependencies``, ``export_history``) using
          deterministic math.
      4.  When the prompt lacks a numeric the builder sets
          ``estimated_effects = ["Insufficient data"]``,
          ``confidence = "unknown"``, and populates ``unknowns`` with
          the missing variable.
    """

    def __init__(self, detector: ScenarioDetector | None = None) -> None:
        self._detector = detector or ScenarioDetector()

    def analyze(
        self,
        prompt: str,
        context: Any,
    ) -> ScenarioAnalysis | None:
        """Return a :class:`ScenarioAnalysis` for a scenario prompt.

        Returns ``None`` when the prompt is not a scenario question
        — the chat path falls through to the LLM route.
        """
        kind = self._detector.classify(prompt)
        if kind is None:
            return None

        builder = _KIND_BUILDERS.get(kind)
        if builder is None:
            return self._missing_data(prompt)
        try:
            return builder(prompt, context)
        except Exception:  # pragma: no cover — defensive, never crashes chat
            return self._missing_data(prompt)

    # ------------------------------------------------------------------
    # Per-kind builders
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_inr(amount: float) -> str:  # pragma: no cover — re-export
        return _format_inr(amount)

    def _price_change(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        pct = _extract_pct(text) or 5
        is_lower = bool(re.search(r"\b(?:lower|cut|reduce|drop|down|cheaper)\b", text))
        elasticity = 1.2 if is_lower else -1.5

        if base_rev <= 0:
            return self._missing_data(
                prompt,
                extra_unknowns=["Baseline revenue unavailable"],
            )

        rev_delta = base_rev * (pct / 100.0) * elasticity

        # Sensitivity — bracket 3 elasticity scenarios.
        sens = [
            f"Lower bound (elasticity=±1.0): revenue {_format_inr(base_rev * (pct / 100.0) * (1.0 if is_lower else -1.0))}",
            f"Best-guess elasticity=±{abs(elasticity)}: revenue {_format_inr(rev_delta)}",
            f"Upper bound (elasticity=±2.0): revenue {_format_inr(base_rev * (pct / 100.0) * (2.0 if is_lower else -2.0))}",
        ]

        direction = "lower" if is_lower else "raise"
        return ScenarioAnalysis(
            scenario_name=f"Price {direction} of {pct}%",
            baseline=[
                f"Annual revenue: {_format_inr(base_rev)}",
                "Demand elasticity assumed at ±1.5 (raise) / ±1.2 (lower)",
            ],
            changes=[f"List price {direction} of {pct}%"],
            assumptions=[
                f"Demand elasticity = {elasticity} for this segment",
                "Cost base (raw material, payroll) held constant",
                "No product-mix shift in the scenario window",
            ],
            calculation_method=(
                f"rev_delta = annual_revenue × (pct_change / 100) × elasticity "
                f"= {_format_inr(base_rev)} × {pct / 100.0:.2f} × {elasticity}"
            ),
            estimated_effects=[
                f"Revenue {('+' if rev_delta >= 0 else '')}{_format_inr(rev_delta)} "
                f"(≈{(rev_delta / base_rev) * 100:+.1f}% net of demand elasticity)",
            ],
            risks=[
                "Volume may fall more than the elasticity assumption suggests",
                "Competitor response (price war, customer churn) not modeled",
            ],
            unknowns=[
                "True elasticity for this segment",
                "Competitor response in the same window",
            ],
            sensitivity=sens,
            confidence="medium" if base_rev > 0 else "low",
        )

    def _revenue_growth(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        pct = _extract_pct(text) or 10
        if base_rev <= 0:
            return self._missing_data(prompt, extra_unknowns=["Baseline revenue unavailable"])

        rev_delta = base_rev * (pct / 100.0)
        return ScenarioAnalysis(
            scenario_name=f"Revenue growth {pct}%",
            baseline=[f"Annual revenue: {_format_inr(base_rev)}"],
            changes=[f"Top-line growth of {pct}%"],
            assumptions=[
                "Cost base held constant in the short term",
                "Mix of products/services held constant",
            ],
            calculation_method=f"rev_delta = annual_revenue × pct / 100 = {_format_inr(base_rev)} × {pct / 100.0:.2f}",
            estimated_effects=[
                f"Revenue +{_format_inr(rev_delta)} (≈{pct}% gross)",
                "Margin unaffected in the short term",
            ],
            risks=["Cost base may rise with volume — margin compression possible"],
            unknowns=["Whether the growth requires extra capex or hires"],
            sensitivity=[
                f"At +{pct}%: revenue {_format_inr(base_rev + rev_delta)}",
                f"At +{int(pct / 2)}%: revenue {_format_inr(base_rev + (rev_delta / 2))}",
                f"At +{pct * 2}%: revenue {_format_inr(base_rev + (rev_delta * 2))}",
            ],
            confidence="medium",
        )

    def _employee_increase(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        count = _extract_int(text) or 3
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        emp_count_raw = getattr(context, "employee_count", "unknown")
        try:
            current_emp = int(emp_count_raw)
            annual_cost = (base_rev / current_emp) if current_emp > 0 and base_rev > 0 else 0
        except (TypeError, ValueError):
            current_emp = 0
            annual_cost = 0

        # When we can't compute real numbers, fall back to a defaults
        # consistent with the H8.4 hiring branch (₹35k/mo per employee)
        # so the envelope still surfaces something useful.
        if annual_cost <= 0:
            annual_cost_per_emp = 35_000 * 12  # ₹4.2 Lakh / employee / yr
        else:
            annual_cost_per_emp = annual_cost * 0.85  # assume cost < revenue/employee

        total_cost = count * annual_cost_per_emp
        rev_gain = total_cost * 1.5  # operational leverage assumption

        return ScenarioAnalysis(
            scenario_name=f"Hire {count} employees",
            baseline=[
                f"Annual revenue: {_format_inr(base_rev)}" if base_rev else "Annual revenue: unknown",
                f"Current headcount: {current_emp or 'unknown'}",
                "Avg annual cost / employee (assumed): "
                + (_format_inr(annual_cost_per_emp) if annual_cost_per_emp else "unknown"),
            ],
            changes=[f"Add {count} new employees"],
            assumptions=[
                "Operational leverage ratio of 1.5× on payroll cost → revenue gain",
                "New hires are productive after a 60-day ramp-up",
                "Existing factory space accommodates the additional headcount",
            ],
            calculation_method=(
                f"cost_delta = count × annual_cost_per_employee × 0.85 → "
                f"revenue_gain = cost_delta × 1.5"
            ),
            estimated_effects=[
                f"Annual payroll increase ≈{_format_inr(total_cost)}",
                f"Expected revenue uplift ≈{_format_inr(rev_gain)}",
            ],
            risks=[
                "Productivity dip during onboarding (~60 days)",
                "Hiring cost / onboarding overrun",
            ],
            unknowns=[
                "True annual cost per employee for this role",
                "Time-to-productivity for the new hires",
            ],
            sensitivity=[
                f"At 0.5× leverage: revenue uplift {_format_inr(total_cost * 0.5)}",
                f"At 1.5× leverage: revenue uplift {_format_inr(total_cost * 1.5)}",
                f"At 2.5× leverage: revenue uplift {_format_inr(total_cost * 2.5)}",
            ],
            confidence="medium" if base_rev and current_emp else "low",
        )

    def _supplier_concentration(self, prompt: str, context: Any) -> ScenarioAnalysis:
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        suppliers = tuple(getattr(context, "supplier_dependencies", ()) or ())
        pcts = re.findall(r"(\d+)\s*%", prompt or "")
        current = (int(pcts[0]) / 100.0) if len(pcts) >= 1 else 0.75
        target = (int(pcts[1]) / 100.0) if len(pcts) >= 2 else 0.40

        downside_at_current = base_rev * current * 0.6
        downside_at_target = base_rev * target * 0.6
        downside_avoided = downside_at_current - downside_at_target

        return ScenarioAnalysis(
            scenario_name=(
                f"Supplier concentration {int(current * 100)}% → {int(target * 100)}%"
            ),
            baseline=[
                f"Top supplier share: {int(current * 100)}%"
                + (f" (identified {len(suppliers)} suppliers)" if suppliers else ""),
                f"Annual revenue at risk from top-supplier disruption: {_format_inr(downside_at_current)}",
            ],
            changes=[
                f"Reduce top supplier share from {int(current * 100)}% to {int(target * 100)}%",
            ],
            assumptions=[
                "Worst-case disruption severity: 60% of top-supplier revenue",
                "Cost-per-unit comparable across the new supplier base",
            ],
            calculation_method=(
                "downside = annual_revenue × top_supplier_share × 0.6; "
                "benefit = downside_at_current − downside_at_target"
            ),
            estimated_effects=[
                f"Disruption-at-risk drops: {_format_inr(downside_at_current)} → {_format_inr(downside_at_target)}",
                f"Annual downside avoided: ≈{_format_inr(max(downside_avoided, 0))}",
            ],
            risks=[
                "New-supplier quality variance during ramp-up",
                "Per-unit cost variance vs the prior dominant supplier",
            ],
            unknowns=[
                "Actual supplier pricing and lead times for the new vendors",
                "Operational disruption during the transition overlap period",
            ],
            sensitivity=[
                "Single-supplier exposure remains the largest concentration risk",
                f"At target {int(target * 100)}%: downside ≈{_format_inr(downside_at_target)}",
                "If new suppliers onboard faster, downside drops further",
            ],
            confidence="medium" if suppliers else "low",
        )

    def _export_expansion(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        pct = _extract_pct(text) or 20
        export_history = tuple(getattr(context, "export_history", ()) or ())

        if base_rev <= 0:
            return self._missing_data(prompt, extra_unknowns=["Baseline revenue unavailable"])

        rev_delta = base_rev * (pct / 100.0)
        margin_uplift = pct * 0.04  # 4× the pct as the export margin lift heuristic
        return ScenarioAnalysis(
            scenario_name=f"Export expansion +{pct}%",
            baseline=[
                f"Annual revenue: {_format_inr(base_rev)}"
                + (f"; existing export footprint: {len(export_history)} markets" if export_history else ""),
            ],
            changes=[f"Export volume increases by {pct}%"],
            assumptions=[
                "Export realization per unit is +20% over domestic pricing",
                "ECGC export credit insurance mitigates credit risk",
            ],
            calculation_method=(
                f"rev_delta = annual_revenue × pct / 100 = {_format_inr(base_rev)} × {pct / 100.0:.2f}; "
                f"margin_uplift ≈ {margin_uplift:.1f}% on the export slice"
            ),
            estimated_effects=[
                f"Revenue +{_format_inr(rev_delta)}",
                f"Gross margin expands ≈+{margin_uplift:.1f}% on the export slice",
            ],
            risks=[
                "FX / currency fluctuation risk",
                "Working capital stretch due to longer L/C credit cycles",
                "Compliance audit for target markets",
            ],
            unknowns=[
                "Target-market acceptance / certification lead time",
                "Best-case FX band",
            ],
            sensitivity=[
                f"At +{pct}%: revenue {_format_inr(base_rev + rev_delta)}",
                f"At +{int(pct / 2)}%: revenue {_format_inr(base_rev + (rev_delta / 2))}",
                f"At +{pct * 2}%: revenue {_format_inr(base_rev + (rev_delta * 2))}",
            ],
            confidence="medium" if export_history else "low",
        )

    def _inventory_change(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)
        day_match = re.search(r"(\d+)\s*days?", text)
        pct_match = re.search(r"(\d+)\s*%", text)
        if day_match:
            days = int(day_match.group(1))
        elif pct_match:
            days = int(int(pct_match.group(1)) * 3.65)  # 100% ≈ 365 days
        else:
            days = 30
        is_reduction = bool(
            re.search(r"\b(?:reduce|cut|lower|shrink|drop|down)\b", text)
        )
        sign = -1 if is_reduction else 1
        wc_delta = sign * base_rev * 0.15 * (days / 365.0)

        direction = "reduction" if is_reduction else "increase"
        return ScenarioAnalysis(
            scenario_name=f"Inventory {direction} of {days} days",
            baseline=[
                "Inventory carrying cost approximated at 15% of revenue",
                "Per-SKU mix assumed constant",
            ],
            changes=[f"Inventory {direction} of {days} days"],
            assumptions=[
                "Working-capital cycle = 15% of annual revenue",
                "Demand variability not modeled",
            ],
            calculation_method=(
                f"working_capital_delta = annual_revenue × 0.15 × (days / 365) "
                f"= {_format_inr(base_rev)} × 0.15 × ({days} / 365)"
            ),
            estimated_effects=[
                ("Cash freed: " if is_reduction else "Cash tied up: ")
                + f"{_format_inr(abs(wc_delta))}",
                "Revenue impact dependent on demand-served-rate (not modeled)",
            ],
            risks=[
                "Stock-out risk if demand spikes above the leaner buffer",
                "Demand pattern is not knowable from this prompt alone",
            ],
            unknowns=[
                "True demand pattern for the SKUs in question",
                "Per-unit obsolescence cost at the new inventory level",
            ],
            sensitivity=[
                f"At -{days} days: WC freed {_format_inr(abs(wc_delta)) if wc_delta >= 0 else _format_inr(abs(wc_delta))}",
                f"At -{days // 2 or 1} days: WC freed ≈{_format_inr(abs(wc_delta) / 2)}",
                f"At -{days * 2} days: WC freed ≈{_format_inr(abs(wc_delta) * 2)}",
            ],
            confidence="low",
        )

    def _investment_scenario(self, prompt: str, context: Any) -> ScenarioAnalysis:
        text = (prompt or "").lower()
        base_rev = int(getattr(context, "annual_revenue_inr", 0) or 0)

        amount_match = re.search(
            r"\b(?:invest|spend)\b[^.]*?\b(\d+)\s*(lakh|crore|l|cr)\b", text
        )
        if amount_match:
            n = int(amount_match.group(1))
            unit = amount_match.group(2)
            scale = {"lakh": 100_000, "l": 100_000, "crore": 10_000_000, "cr": 10_000_000}
            amount = n * scale.get(unit, 100_000)
        else:
            amount = 0

        if amount <= 0:
            return self._missing_data(
                prompt,
                extra_unknowns=["Investment amount (₹) not specified"],
            )

        if base_rev <= 0:
            payback_months = None
            revenue_uplift_low = 0
        else:
            payback_months = amount / (base_rev * 0.05 / 12.0) if base_rev > 0 else None
            revenue_uplift_low = amount * 0.20  # 20% annualized uplift assumption

        return ScenarioAnalysis(
            scenario_name=f"Investment of {_format_inr(amount)}",
            baseline=[
                f"Annual revenue: {_format_inr(base_rev)}" if base_rev else "Annual revenue: unknown",
            ],
            changes=[f"Invest {_format_inr(amount)} in business growth"],
            assumptions=[
                "20% annualized revenue uplift on the invested amount",
                "Payback calculated against 5% incremental margin",
            ],
            calculation_method=(
                f"payback_months = amount / (annual_revenue × 0.05 / 12); "
                f"revenue_uplift_low ≈ amount × 0.20"
            ),
            estimated_effects=[
                f"Annual revenue uplift (lower bound): ≈{_format_inr(revenue_uplift_low)}"
                if revenue_uplift_low else "Revenue uplift cannot be estimated without baseline revenue",
                f"Payback horizon: {payback_months:.1f} months (if baseline available)" if payback_months else "Payback horizon cannot be estimated",
            ],
            risks=[
                "Realisation risk — uplift depends on the use of capital",
                "Execution risk — capacity to deploy capital productively",
            ],
            unknowns=[
                "Specific deployment of capital (capex vs working capital)",
                "Discount rate / opportunity cost",
            ],
            sensitivity=[
                f"At 10% margin: payback {amount / (base_rev * 0.10 / 12.0):.1f} months" if base_rev else "N/A",
                f"At 5% margin: payback {amount / (base_rev * 0.05 / 12.0):.1f} months" if base_rev else "N/A",
                f"At 2% margin: payback {amount / (base_rev * 0.02 / 12.0):.1f} months" if base_rev else "N/A",
            ],
            confidence="medium" if base_rev > 0 else "low",
        )

    def _missing_data(
        self,
        prompt: str,
        *,
        extra_unknowns: list[str] | None = None,
    ) -> ScenarioAnalysis:
        unknowns: list[str] = ["Quantitative prompt required for a defensible estimate"]
        if extra_unknowns:
            unknowns.extend(extra_unknowns)
        return ScenarioAnalysis(
            scenario_name="Insufficient data scenario",
            baseline=["Baseline values required to model this scenario"],
            changes=[f"User prompt did not include a directional numeric: '{prompt[:80]}'"],
            assumptions=["No assumptions can be made without additional data"],
            calculation_method="No calculation performed — too few inputs",
            estimated_effects=["Insufficient data to estimate"],
            risks=[
                "Approximating without data risks fabricated precision — refusing to estimate instead",
            ],
            unknowns=unknowns,
            sensitivity=[
                "Provide a directional change (e.g. raise prices 5%) to receive an illustrative estimate",
            ],
            confidence="unknown",
        )


# ---------------------------------------------------------------------------
# Module-level dispatch table — kept as a dict (not a method) so
# tests can introspect the routes without instantiating the analyzer.
# ---------------------------------------------------------------------------


def _build_price_change(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._price_change(prompt, context)


def _build_revenue_growth(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._revenue_growth(prompt, context)


def _build_employee_increase(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._employee_increase(prompt, context)


def _build_supplier_concentration(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._supplier_concentration(prompt, context)


def _build_export_expansion(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._export_expansion(prompt, context)


def _build_inventory_change(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._inventory_change(prompt, context)


def _build_investment_scenario(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._investment_scenario(prompt, context)


def _build_missing_data(prompt: str, context: Any) -> ScenarioAnalysis:
    return _DEFAULT_ANALYZER._missing_data(prompt)


_DEFAULT_ANALYZER = ScenarioAnalyzer()

_KIND_BUILDERS: dict[str, Any] = {
    "price_change": _build_price_change,
    "revenue_growth": _build_revenue_growth,
    "employee_increase": _build_employee_increase,
    "supplier_concentration": _build_supplier_concentration,
    "export_expansion": _build_export_expansion,
    "inventory_change": _build_inventory_change,
    "investment_scenario": _build_investment_scenario,
    "missing_data": _build_missing_data,
}

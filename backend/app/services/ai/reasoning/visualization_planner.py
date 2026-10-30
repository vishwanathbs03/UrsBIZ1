"""Sprint AI-15 — Intelligent Visualization + Trust-First Answer UX.

``visualization_planner`` decides **when** a chart materially
improves comprehension. It is **deterministic, pure, and
provenance-first**: every plan carries the source evidence IDs +
calculation IDs the chart will read from. The LLM has no path
into this decision.

The planner returns 0..N :class:`VisualizationPlan` entries. The
renderer picks one (or zero) per prompt based on the AI-14
section selector; viz never counts against the
``MAX_SUPPORTING_SECTIONS = 3`` cap — when the planner emits
exactly one plan, the renderer slots it in as one of the three
supports.

Chart kinds (the brief)
-----------------------

The AI-15 brief specifies a **small controlled vocabulary**
("Do not allow arbitrary LLM-defined chart types"). The seven
canonical kinds are:

* ``revenue_progress``    — current vs target (revenue gap).
* ``revenue_trend``       — time-series (revenue over time).
* ``supplier_composition`` — supplier concentration donut.
* ``strategy_comparison``  — side-by-side options (hire vs
  contract).
* ``forecast_scenario``    — baseline + changed input + estimated
  effect. Always labelled "Scenario estimate" — never a
  guaranteed prediction.
* ``readiness_radar``      — multidimensional readiness radar
  (export / finance / ops / etc.).
* ``risk_distribution``    — risk severity buckets.

The :class:`ChartKind` enum exposes the brief's seven names as
canonical values. Two additional supporting kinds (``kpi`` and
``legacy_progress`` / ``legacy_trend`` / ``legacy_comparison`` /
``legacy_scenario`` / ``legacy_risk`` / ``legacy_composition`` /
``legacy_readiness``) exist for backward-compat with the
AI-15 internal renderer routing — every ``legacy_*`` value maps
to its brief-canonical counterpart via
:func:`canonical_chart_kind`.

The LLM cannot introduce a new chart kind: every entry must
round-trip through :func:`canonical_chart_kind` and any
unrecognised string raises ``ValueError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING


# --------------------------------------------------------------------------- #
# Controlled vocabulary
# --------------------------------------------------------------------------- #
#
# The brief is explicit: the controlled vocabulary is the seven
# names listed in section "CHART KINDS". ``_ALIAS_TO_CANONICAL``
# maps every legacy / supporting name back to the brief's name so
# the wire envelope speaks the brief's vocabulary while the
# renderer can keep using the legacy names internally.
#
# Adding a new kind is non-breaking only when the new name is
# added to BOTH the enum AND the alias map. The LLM has no path
# to either table — the planner writes the value, the renderer
# reads it.

_CANONICAL_VALUES: frozenset[str] = frozenset({
    "revenue_progress",
    "revenue_trend",
    "supplier_composition",
    "strategy_comparison",
    "forecast_scenario",
    "readiness_radar",
    "risk_distribution",
})

_ALIAS_TO_CANONICAL: dict[str, str] = {
    # Legacy AI-15 internal renderer routes → brief canonical name.
    "progress": "revenue_progress",
    "trend": "revenue_trend",
    "composition": "supplier_composition",
    "comparison": "strategy_comparison",
    "scenario": "forecast_scenario",
    "readiness": "readiness_radar",
    "risk": "risk_distribution",
    # Explicit aliases so the brief's name and the legacy name
    # both round-trip cleanly through the enum.
    "revenue_progress": "revenue_progress",
    "revenue_trend": "revenue_trend",
    "supplier_composition": "supplier_composition",
    "strategy_comparison": "strategy_comparison",
    "forecast_scenario": "forecast_scenario",
    "readiness_radar": "readiness_radar",
    "risk_distribution": "risk_distribution",
    # Supporting fallback kind — the brief permits a single
    # headline KPI card when no richer chart qualifies.
    "kpi": "kpi",
}


class ChartKind(str, Enum):
    """The seven canonical chart kinds the AI-15 brief mandates,
    plus the supporting ``kpi`` fallback.

    The enum values are JSON-clean strings — both the brief's
    vocabulary ("revenue_progress", "supplier_composition",
    …) and the legacy AI-15 renderer routes ("progress",
    "composition", …) are accepted by ``ChartKind(value)`` so
    no existing wire payload breaks.

    String-valued so the enum serialises JSON-clean across the
    wire without bespoke converters.
    """

    # Brief canonical vocabulary.
    REVENUE_PROGRESS = "revenue_progress"
    REVENUE_TREND = "revenue_trend"
    SUPPLIER_COMPOSITION = "supplier_composition"
    STRATEGY_COMPARISON = "strategy_comparison"
    FORECAST_SCENARIO = "forecast_scenario"
    READINESS_RADAR = "readiness_radar"
    RISK_DISTRIBUTION = "risk_distribution"
    # Supporting fallback (single-value headline tile).
    KPI = "kpi"
    # Legacy AI-15 internal renderer routes — kept as full enum
    # members (not underscore-prefixed) so pre-AI-15-final tests
    # can still reference them by attribute name. The canonical
    # brief vocabulary above is the wire-facing value; the
    # legacy names are aliases that :func:`canonical_chart_kind`
    # maps to the canonical value.
    PROGRESS = "progress"
    TREND = "trend"
    COMPOSITION = "composition"
    COMPARISON = "comparison"
    SCENARIO = "scenario"
    RISK = "risk"
    READINESS = "readiness"


def canonical_chart_kind(value: Any) -> ChartKind:
    """Return the brief-canonical :class:`ChartKind` for ``value``.

    Accepts the brief's vocabulary (``revenue_progress``,
    ``supplier_composition``, …), the legacy AI-15 internal
    names (``progress``, ``composition``, …), any :class:`ChartKind`
    enum member (legacy or canonical), or any string that maps
    through :data:`_ALIAS_TO_CANONICAL`. Always returns the
    brief-canonical :class:`ChartKind` enum member — the
    function collapses both vocabularies to one.

    Raises :class:`ValueError` when the value is not part of
    the controlled vocabulary. This is the gate the brief
    mandates ("Do not allow arbitrary LLM-defined chart
    types"). Any LLM-authored chart string that did not come
    from the planner's decision table will fail this check.
    """
    raw: str
    if isinstance(value, ChartKind):
        raw = value.value
    else:
        raw = str(value or "").strip().lower()
    if raw not in _ALIAS_TO_CANONICAL:
        raise ValueError(
            f"unknown ChartKind {value!r}; controlled vocabulary is "
            f"{sorted(_CANONICAL_VALUES)}"
        )
    canonical = _ALIAS_TO_CANONICAL[raw]
    # The canonical value is always a valid enum member.
    return ChartKind(canonical)


def is_brief_canonical(value: Any) -> bool:
    """True iff ``value`` is one of the seven brief-canonical names."""
    if isinstance(value, ChartKind):
        return value.value in _CANONICAL_VALUES
    return str(value or "").strip().lower() in _CANONICAL_VALUES


def brief_vocabulary() -> tuple[str, ...]:
    """Return the seven brief-canonical chart-kind strings (frozen)."""
    return tuple(sorted(_CANONICAL_VALUES))


@dataclass(frozen=True)
class VisualizationPlan:
    """Server-owned plan describing one chart.

    Attributes
    ----------
    chart_kind
        One of :class:`ChartKind`.
    title
        Short headline the renderer shows above the chart.
    purpose
        One-line statement of what the chart is for.
    recommended_display
        Hint to the renderer: ``"card"``, ``"table"``,
        ``"bar"``, ``"sparkline"``, ``"stacked_bar"``,
        ``"donut"``, ``"radar"``. The renderer may override
        but rarely needs to.
    explanation
        Plain-English one-line "why this helps the user
        understand the answer". NEVER chain-of-thought.
    source_evidence_ids
        EvidenceNode IDs the chart reads from.
    calculation_ids
        CalculationNode IDs the chart reads from (numeric
        lineage — server-owned).
    assumptions
        Scenario / forecast assumptions the chart relies on.
    limitations
        Known limitations the chart should surface.
    confidence
        0..1 — server-owned. ``min`` over source confidences;
        never bumped above source.
    """

    chart_kind: ChartKind
    title: str
    purpose: str
    recommended_display: str = "card"
    explanation: str = ""
    source_evidence_ids: tuple[str, ...] = ()
    calculation_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self) -> dict:
        """JSON-safe wire representation.

        ``chart_kind`` is the canonical brief-vocabulary value
        (``revenue_progress``, ``supplier_composition``, …).
        Legacy consumers reading the short forms
        (``progress``, ``composition``, …) can use
        :func:`canonical_chart_kind` to coerce the value.
        """
        return {
            "chart_kind": self.chart_kind.value
            if isinstance(self.chart_kind, ChartKind)
            else str(self.chart_kind),
            "title": str(self.title),
            "purpose": str(self.purpose),
            "recommended_display": str(self.recommended_display),
            "explanation": str(self.explanation),
            "source_evidence_ids": list(self.source_evidence_ids),
            "calculation_ids": list(self.calculation_ids),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "confidence": float(self.confidence),
        }


# ---------------------------------------------------------------------------
# Planner result wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VisualizationPlannerResult:
    """Return shape for :func:`plan`.

    The AI-15 brief mandates the planner expose four fields:

    * ``requested_charts``  — the brief-canonical chart kinds
      the planner picked, in emit order, deduped. The wire
      envelope (``AnswerRequirements.requested_charts``) is
      derived from this.
    * ``rationale``         — one short sentence explaining
      *why* a chart materially improves comprehension for this
      prompt, or an empty string when the planner emits nothing.
    * ``data_sources``      — union of every plan's
      ``source_evidence_ids`` and ``calculation_ids``. The
      renderer uses this to attribute the charts.
    * ``materially_useful`` — ``True`` iff the planner emitted
      at least one plan AND the rationale defends at least one
      plan. The renderer hides the slot when ``False``.

    ``plans`` is preserved for callers that need to iterate
    the raw :class:`VisualizationPlan` entries (chart-data
    builder, trust summary, regression tests).
    """

    requested_charts: tuple[ChartKind, ...]
    rationale: str
    data_sources: tuple[str, ...]
    materially_useful: bool
    plans: tuple[VisualizationPlan, ...] = ()

    def __iter__(self):  # pragma: no cover — convenience
        """Iterate the raw plans tuple.

        Convenience shim so existing callers that treated
        ``plan()`` as a tuple of :class:`VisualizationPlan`
        continue to work — every ``for p in plan(...)``
        pattern keeps functioning. New code should read
        ``result.plans`` explicitly.
        """
        return iter(self.plans)

    def __len__(self) -> int:  # pragma: no cover — convenience
        return len(self.plans)

    def __getitem__(self, idx: int) -> VisualizationPlan:  # pragma: no cover
        return self.plans[idx]

    def to_dict(self) -> dict:
        """JSON-safe wire representation."""
        return {
            "requested_charts": [
                k.value if isinstance(k, ChartKind) else str(k)
                for k in self.requested_charts
            ],
            "rationale": str(self.rationale),
            "data_sources": list(self.data_sources),
            "materially_useful": bool(self.materially_useful),
            "plans": [p.to_dict() for p in self.plans],
        }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Safe attribute access for stub-shaped QU / context objects."""
    return getattr(obj, name, default) if obj is not None else default


def _envelope_tool(envelope: Any) -> str:
    return str(_get_attr(envelope, "tool_name", "") or "")


def _envelope_metric(envelope: Any) -> str:
    return str(_get_attr(envelope, "metric", "") or "")


def _envelope_calc_id(envelope: Any) -> str:
    return str(_get_attr(envelope, "calculation_id", "") or "")


def _envelope_input_ids(envelope: Any) -> tuple[str, ...]:
    ids = _get_attr(envelope, "input_evidence_ids", ()) or ()
    return tuple(str(i) for i in ids)


def _envelope_assumptions(envelope: Any) -> tuple[str, ...]:
    a = _get_attr(envelope, "assumptions", ()) or ()
    return tuple(str(x) for x in a)


def _envelope_limitations(envelope: Any) -> tuple[str, ...]:
    a = _get_attr(envelope, "limitations", ()) or ()
    return tuple(str(x) for x in a)


def _envelope_confidence(envelope: Any) -> float:
    try:
        c = float(_get_attr(envelope, "confidence", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c


def _has_time_series(envelope: Any) -> bool:
    """True iff the envelope's value is a list of ≥2 points."""
    value = _get_attr(envelope, "value", None)
    if not isinstance(value, dict):
        return False
    series = value.get("series") or value.get("points") or value.get("forecast")
    if not isinstance(series, (list, tuple)):
        return False
    return len(series) >= 2


def _plan(
    kind: ChartKind,
    title: str,
    purpose: str,
    *,
    display: str = "card",
    explanation: str = "",
    source_evidence_ids: tuple[str, ...] = (),
    calculation_ids: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
    confidence: float = 1.0,
) -> VisualizationPlan:
    """Internal builder that validates confidence bounds."""
    if confidence < 0.0:
        confidence = 0.0
    if confidence > 1.0:
        confidence = 1.0
    return VisualizationPlan(
        chart_kind=kind,
        title=title,
        purpose=purpose,
        recommended_display=display,
        explanation=explanation,
        source_evidence_ids=tuple(source_evidence_ids),
        calculation_ids=tuple(calculation_ids),
        assumptions=tuple(assumptions),
        limitations=tuple(limitations),
        confidence=float(confidence),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def plan(
    *,
    question_understanding: Any,
    answer_requirements: Any | None = None,
    envelopes: tuple = (),
    evidence_graph: Any | None = None,
    contradiction_report: Any | None = None,
) -> VisualizationPlannerResult:
    """Return a :class:`VisualizationPlannerResult` for this prompt.

    Pure function. Same inputs always return the same
    :class:`VisualizationPlannerResult`. The planner **never
    invents** a chart that has no envelope / context source.

    The return shape carries:

    * ``requested_charts``  — brief-canonical chart kinds in
      emit order, deduped.
    * ``rationale``         — short sentence defending the
      chosen charts (empty when the planner emits nothing).
    * ``data_sources``      — union of every plan's
      ``source_evidence_ids`` and ``calculation_ids``.
    * ``materially_useful`` — ``True`` iff at least one plan
      was emitted with a non-empty rationale.
    * ``plans``             — the raw :class:`VisualizationPlan`
      entries (kept for the chart-data builder + trust
      summary).

    The plan order is deterministic (KPI / progress / readiness
    first; trend / scenario when present; risk / composition
    last). The renderer picks one (or zero).
    """
    plans: list[VisualizationPlan] = []

    capability = tuple(_get_attr(question_understanding, "capability", ()) or ())
    requires_calc = bool(
        _get_attr(question_understanding, "requires_calculation", False)
    )
    requires_scenario = bool(
        _get_attr(question_understanding, "requires_scenario_analysis", False)
    )
    requires_external = bool(
        _get_attr(question_understanding, "requires_external_information", False)
    )
    requires_forecast = bool(
        _get_attr(question_understanding, "requires_forecast", False)
    )
    business_dep = str(
        _get_attr(question_understanding, "business_dependency", "none") or "none"
    )

    # If the QU is purely educational / general knowledge, the
    # brief says no chart. We detect this by capability = ()
    # AND business_dependency = "none" AND requires_* all False.
    is_pure_educational = (
        not capability
        and business_dep == "none"
        and not requires_calc
        and not requires_scenario
        and not requires_external
        and not requires_forecast
    )
    if is_pure_educational:
        return VisualizationPlannerResult(
            requested_charts=(),
            rationale="",
            data_sources=(),
            materially_useful=False,
            plans=(),
        )

    # Index envelopes once by metric for O(1) lookups.
    by_metric: dict[str, tuple] = {}
    for env in envelopes or ():
        m = _envelope_metric(env)
        if not m:
            continue
        by_metric.setdefault(m, ())
        # We keep order but track the FIRST envelope per metric
        # for the plan — the builder re-reads all envelopes.
        if m not in by_metric:
            by_metric[m] = (env,)
        else:
            by_metric[m] = by_metric[m] + (env,)

    def _first(metric: str):
        items = by_metric.get(metric, ())
        return items[0] if items else None

    contradictions_high = (
        contradiction_report is not None
        and str(_get_attr(contradiction_report, "severity", "none")) == "high"
    )

    # -- REVENUE_PROGRESS --------------------------------------------------
    # Brief: revenue target → progress/scenario visualization.
    # Source: growth envelope (calc engine) OR profile targets.
    growth_env = _first("growth") or _first("scenario")
    if growth_env is not None:
        src_ids = _envelope_input_ids(growth_env)
        calc_ids = tuple(filter(None, (_envelope_calc_id(growth_env),)))
        plans.append(
            _plan(
                ChartKind.REVENUE_PROGRESS,
                title="Revenue progress",
                purpose="Current revenue vs target.",
                display="progress",
                explanation=(
                    "Shows the gap between current revenue and "
                    "your target so the recommendation is "
                    "grounded in the same numbers the engine "
                    "computed."
                ),
                source_evidence_ids=src_ids,
                calculation_ids=calc_ids,
                limitations=("Target is set by the user profile.",),
                confidence=_envelope_confidence(growth_env),
            )
        )

    # -- FORECAST_SCENARIO -------------------------------------------------
    # Brief: scenario must show baseline / changed input / estimated
    # effect / assumptions / unknowns / risks. Never labelled
    # "Predicted result".
    scenario_env = _first("scenario") or _first("scenario_delta")
    if requires_scenario or scenario_env is not None:
        if scenario_env is not None:
            assumptions = _envelope_assumptions(scenario_env)
            limitations = _envelope_limitations(scenario_env)
            src_ids = _envelope_input_ids(scenario_env)
            calc_ids = tuple(filter(None, (_envelope_calc_id(scenario_env),)))
            conf = _envelope_confidence(scenario_env)
            # Scenarios are inherently less certain — cap confidence.
            conf = min(conf, 0.7)
            plans.append(
                _plan(
                    ChartKind.FORECAST_SCENARIO,
                    title="Scenario estimate",
                    purpose=(
                        "Baseline, changed input, and estimated "
                        "effect under declared assumptions."
                    ),
                    display="stacked_bar",
                    explanation=(
                        "Scenario estimate — what the changed "
                        "input implies under the listed "
                        "assumptions, not a guaranteed "
                        "prediction."
                    ),
                    source_evidence_ids=src_ids,
                    calculation_ids=calc_ids,
                    assumptions=assumptions,
                    limitations=(
                        *limitations,
                        "Treated as a scenario, not a forecast.",
                    ),
                    confidence=conf,
                )
            )
        elif requires_scenario and not scenario_env:
            # Scenario requested but no envelope — the planner
            # surfaces the absence via a "missing data" plan the
            # renderer can hide. We do not invent data.
            plans.append(
                _plan(
                    ChartKind.FORECAST_SCENARIO,
                    title="Scenario estimate (data unavailable)",
                    purpose="Baseline + changed input + estimated effect.",
                    display="stacked_bar",
                    explanation=(
                        "The engine has no deterministic inputs "
                        "to compute the scenario; this is "
                        "explicitly a placeholder."
                    ),
                    limitations=(
                        "No scenario envelope was produced; the "
                        "chart is intentionally not rendered.",
                    ),
                    confidence=0.0,
                )
            )

    # -- STRATEGY_COMPARISON -----------------------------------------------
    # Brief: strategy comparison → comparison chart/table.
    compare_env = _first("compare")
    if compare_env is not None:
        plans.append(
            _plan(
                ChartKind.STRATEGY_COMPARISON,
                title="Strategy comparison",
                purpose="Side-by-side recommendation comparison.",
                display="table",
                explanation=(
                    "Lets you weigh the two options on the same "
                    "axes without re-reading the prose."
                ),
                source_evidence_ids=_envelope_input_ids(compare_env),
                calculation_ids=tuple(
                    filter(None, (_envelope_calc_id(compare_env),))
                ),
                confidence=_envelope_confidence(compare_env),
            )
        )

    # -- REVENUE_TREND -----------------------------------------------------
    # Brief: revenue trend → line chart only if genuine
    # time-series data exists. NEVER without ≥2 points.
    forecast_env = _first("forecast")
    if forecast_env is not None and _has_time_series(forecast_env):
        plans.append(
            _plan(
                ChartKind.REVENUE_TREND,
                title="Revenue trend",
                purpose="Deterministic time-series view.",
                display="sparkline",
                explanation=(
                    "Plotted only when the engine has ≥2 "
                    "time-series points; we never invent trend "
                    "points."
                ),
                source_evidence_ids=_envelope_input_ids(forecast_env),
                calculation_ids=tuple(
                    filter(None, (_envelope_calc_id(forecast_env),))
                ),
                assumptions=_envelope_assumptions(forecast_env),
                confidence=_envelope_confidence(forecast_env),
            )
        )

    # -- RISK_DISTRIBUTION -------------------------------------------------
    # Brief: risk analysis → risk distribution chart.
    risk_env = _first("risks")
    if risk_env is not None and "RISK" in capability:
        plans.append(
            _plan(
                ChartKind.RISK_DISTRIBUTION,
                title="Risk distribution",
                purpose="Severity-weighted risk breakdown.",
                display="bar",
                explanation=(
                    "Buckets risks by severity so the user can "
                    "spot the heavy ones at a glance."
                ),
                source_evidence_ids=_envelope_input_ids(risk_env),
                confidence=_envelope_confidence(risk_env),
            )
        )

    # -- SUPPLIER_COMPOSITION ----------------------------------------------
    # Brief: supplier concentration → composition chart.
    # We treat any risks envelope with a "concentration" sub-
    # field, OR the context.supplier_dependencies list, as a
    # composition source. We never invent suppliers.
    composition_env = _first("risks") if risk_env is not None else None
    if composition_env is not None:
        value = _get_attr(composition_env, "value", None)
        if isinstance(value, dict) and (
            value.get("concentration") or value.get("supplier_share")
        ):
            plans.append(
                _plan(
                    ChartKind.SUPPLIER_COMPOSITION,
                    title="Supplier concentration",
                    purpose="Share of spend by supplier.",
                    display="donut",
                    explanation=(
                        "Shows how concentrated your spend is "
                        "across suppliers — high concentration "
                        "is a known supply-chain risk."
                    ),
                    source_evidence_ids=_envelope_input_ids(composition_env),
                    confidence=_envelope_confidence(composition_env),
                )
            )

    # -- READINESS_RADAR ---------------------------------------------------
    # Brief: readiness → multidimensional comparison.
    health_env = _first("score")  # get_health_score uses metric="score"
    readiness_env = _first("overall_score")  # get_readiness uses overall_score
    if health_env is not None or readiness_env is not None:
        src_env = readiness_env or health_env
        plans.append(
            _plan(
                ChartKind.READINESS_RADAR,
                title="Readiness",
                purpose="Multidimensional readiness snapshot.",
                display="radar",
                explanation=(
                    "Plots the readiness sub-axes on a single "
                    "radar so strengths and gaps show up at "
                    "once."
                ),
                source_evidence_ids=_envelope_input_ids(src_env),
                calculation_ids=tuple(
                    filter(None, (_envelope_calc_id(src_env),))
                ),
                confidence=_envelope_confidence(src_env),
            )
        )

    # -- KPI ---------------------------------------------------------------
    # Brief: deterministic KPI from envelopes + profile. We emit
    # this last so it never preempts a more specific chart.
    kpi_env = None
    for candidate_metric in ("amount", "score", "value"):
        e = _first(candidate_metric)
        if e is not None:
            kpi_env = e
            break
    if (
        kpi_env is not None
        and requires_calc
        and not any(p.chart_kind == ChartKind.READINESS_RADAR for p in plans)
    ):
        plans.append(
            _plan(
                ChartKind.KPI,
                title="Key metric",
                purpose="Single-value headline.",
                display="card",
                explanation=(
                    "A single number the rest of the answer "
                    "is anchored to."
                ),
                source_evidence_ids=_envelope_input_ids(kpi_env),
                calculation_ids=tuple(
                    filter(None, (_envelope_calc_id(kpi_env),))
                ),
                confidence=_envelope_confidence(kpi_env),
            )
        )

    # If a contradiction was high, demote confidence on every
    # plan so the renderer can surface the disclosure.
    if contradictions_high:
        plans = [
            _plan(
                p.chart_kind,
                title=p.title,
                purpose=p.purpose,
                display=p.recommended_display,
                explanation=p.explanation,
                source_evidence_ids=p.source_evidence_ids,
                calculation_ids=p.calculation_ids,
                assumptions=p.assumptions,
                limitations=(
                    *p.limitations,
                    "Confidence reduced: source contradiction "
                    "detected.",
                ),
                confidence=min(p.confidence, 0.5),
            )
            for p in plans
        ]

    return _wrap(plans, question_understanding)


def _wrap(
    plans: list[VisualizationPlan],
    question_understanding: Any,
) -> VisualizationPlannerResult:
    """Build the brief-mandated 4-tuple wrapper around ``plans``.

    Computes:

    * ``requested_charts``  — brief-canonical chart kinds,
      deduped, in emit order. The first emission wins so the
      renderer can rank by priority.
    * ``rationale``         — one short sentence assembled
      from the QU's ``answer_mode`` and ``requires_*`` flags
      plus the first emitted plan's ``purpose``. Falls back
      to the first plan's ``explanation`` when ``answer_mode``
      is missing. Empty when no plan was emitted.
    * ``data_sources``      — ordered, deduped union of every
      plan's ``source_evidence_ids`` and ``calculation_ids``.
    * ``materially_useful`` — ``True`` iff at least one plan
      was emitted AND the rationale defends at least one plan.
    """
    plans_tuple: tuple[VisualizationPlan, ...] = tuple(plans)

    # Deduped, emit-order brief-canonical kinds.
    seen: set[ChartKind] = set()
    requested: list[ChartKind] = []
    for p in plans_tuple:
        canonical = canonical_chart_kind(p.chart_kind)
        if canonical not in seen:
            seen.add(canonical)
            requested.append(canonical)
    requested_charts: tuple[ChartKind, ...] = tuple(requested)

    # Rationale — short sentence from QU + first plan purpose.
    rationale = ""
    if plans_tuple:
        mode = str(
            _get_attr(question_understanding, "answer_mode", "") or ""
        )
        flags: list[str] = []
        if _get_attr(question_understanding, "requires_calculation", False):
            flags.append("calculation")
        if _get_attr(question_understanding, "requires_scenario_analysis", False):
            flags.append("scenario analysis")
        if _get_attr(question_understanding, "requires_forecast", False):
            flags.append("forecast")
        if _get_attr(question_understanding, "requires_external_information", False):
            flags.append("external sources")
        flag_phrase = ", ".join(flags) if flags else ""
        purpose = plans_tuple[0].purpose or plans_tuple[0].explanation
        if mode and flag_phrase:
            rationale = (
                f"{mode.replace('_', ' ').capitalize()} prompt "
                f"with {flag_phrase}; {purpose.lower()}"
            )
        elif mode:
            rationale = (
                f"{mode.replace('_', ' ').capitalize()} prompt; "
                f"{purpose.lower()}"
            )
        else:
            rationale = purpose or ""

    # Ordered, deduped union of evidence + calculation IDs.
    seen_src: set[str] = set()
    sources: list[str] = []
    for p in plans_tuple:
        for sid in (*p.source_evidence_ids, *p.calculation_ids):
            s = str(sid)
            if s and s not in seen_src:
                seen_src.add(s)
                sources.append(s)
    data_sources: tuple[str, ...] = tuple(sources)

    materially_useful = bool(plans_tuple) and bool(rationale.strip())

    return VisualizationPlannerResult(
        requested_charts=requested_charts,
        rationale=rationale,
        data_sources=data_sources,
        materially_useful=materially_useful,
        plans=plans_tuple,
    )


__all__ = [
    "ChartKind",
    "VisualizationPlan",
    "VisualizationPlannerResult",
    "brief_vocabulary",
    "canonical_chart_kind",
    "is_brief_canonical",
    "plan",
]

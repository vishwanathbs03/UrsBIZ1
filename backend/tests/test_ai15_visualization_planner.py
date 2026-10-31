"""Sprint AI-15 — unit tests for ``visualization_planner``.

12 tests covering the deterministic decision table + safe
defaults + pure-function invariance.

All inputs are stub-shaped objects so the planner is decoupled
from the production dataclasses.
"""

from __future__ import annotations

from app.services.ai.reasoning.visualization_planner import (
    ChartKind,
    VisualizationPlan,
    VisualizationPlannerResult,
    canonical_chart_kind,
    plan,
)


def _has(plans, kind: ChartKind | str) -> bool:
    """True iff any emitted plan canonicalises to ``kind``.

    SPRINT AI-15 FINAL HARDENING — the planner emits the
    brief-canonical enum members (``REVENUE_PROGRESS``, …).
    Existing tests reference the legacy short names
    (``PROGRESS``, …). This helper bridges both vocabularies via
    :func:`canonical_chart_kind`.
    """
    target = canonical_chart_kind(kind)
    return any(canonical_chart_kind(p.chart_kind) == target for p in plans)


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #


class _StubQU:
    def __init__(self, **kw):
        self.literal_question = kw.get("literal_question", "")
        self.capability = kw.get("capability", ())
        self.business_dependency = kw.get("business_dependency", "none")
        self.requires_calculation = kw.get("requires_calculation", False)
        self.requires_scenario_analysis = kw.get(
            "requires_scenario_analysis", False
        )
        self.requires_forecast = kw.get("requires_forecast", False)
        self.requires_external_information = kw.get(
            "requires_external_information", False
        )
        self.unknowns = kw.get("unknowns", ())
        self.answer_mode = kw.get("answer_mode", "general_knowledge")


class _StubEnv:
    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "finance")
        self.metric = kw.get("metric", "amount")
        self.value = kw.get("value", None)
        self.unit = kw.get("unit", "INR")
        self.formula = kw.get("formula", "value")
        self.input_evidence_ids = kw.get("input_evidence_ids", ())
        self.calculation_id = kw.get("calculation_id", "")
        self.assumptions = kw.get("assumptions", ())
        self.limitations = kw.get("limitations", ())
        self.confidence = kw.get("confidence", 1.0)


# --------------------------------------------------------------------------- #
# 1 — enum has the 8 chart kinds
# --------------------------------------------------------------------------- #


def test_chart_kind_enum_has_eight_kinds():
    # SPRINT AI-15 FINAL HARDENING — the controlled vocabulary
    # is the brief's seven canonical names plus the supporting
    # ``kpi`` fallback. The legacy AI-15 internal names are also
    # exposed as enum members for renderer routing.
    expected = {
        "kpi",
        "revenue_progress",
        "revenue_trend",
        "supplier_composition",
        "strategy_comparison",
        "forecast_scenario",
        "readiness_radar",
        "risk_distribution",
        "progress",
        "trend",
        "composition",
        "comparison",
        "scenario",
        "risk",
        "readiness",
    }
    assert {k.value for k in ChartKind} == expected


# --------------------------------------------------------------------------- #
# 2 — empty inputs return empty plans
# --------------------------------------------------------------------------- #


def test_empty_inputs_returns_no_plans():
    plans = plan(question_understanding=_StubQU())
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 3 — educational/general-knowledge prompts return no plans
# --------------------------------------------------------------------------- #


def test_educational_qu_returns_no_plans():
    qu = _StubQU(literal_question="What is EBITDA?")
    plans = plan(question_understanding=qu, envelopes=())
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 4 — growth envelope ⇒ PROGRESS plan
# --------------------------------------------------------------------------- #


def test_growth_envelope_emits_progress():
    qu = _StubQU(requires_calculation=True, business_dependency="required")
    env = _StubEnv(metric="growth", value={"current": 1.0e7, "target": 3.0e7})
    plans = plan(question_understanding=qu, envelopes=(env,))
    assert _has(plans, ChartKind.PROGRESS)


# --------------------------------------------------------------------------- #
# 5 — scenario QU ⇒ SCENARIO plan with assumptions
# --------------------------------------------------------------------------- #


def test_scenario_qu_emits_scenario_plan():
    qu = _StubQU(requires_scenario_analysis=True)
    env = _StubEnv(
        metric="scenario",
        value={"baseline": 1.0e7, "changed_input": 0.15, "estimated_effect": -1.5e6},
        assumptions=("cotton prices stable",),
    )
    plans = plan(question_understanding=qu, envelopes=(env,))
    target = canonical_chart_kind(ChartKind.SCENARIO)
    scen = next(
        p for p in plans if canonical_chart_kind(p.chart_kind) == target
    )
    assert scen.assumptions == ("cotton prices stable",)
    # The scenario is capped at 0.7 confidence (it's not a prediction).
    assert scen.confidence <= 0.7


# --------------------------------------------------------------------------- #
# 6 — compare envelope ⇒ COMPARISON plan
# --------------------------------------------------------------------------- #


def test_compare_envelope_emits_comparison():
    qu = _StubQU(requires_calculation=True)
    env = _StubEnv(metric="compare", value={"left": {}, "right": {}})
    plans = plan(question_understanding=qu, envelopes=(env,))
    assert _has(plans, ChartKind.COMPARISON)


# --------------------------------------------------------------------------- #
# 7 — forecast with ≥2 points ⇒ TREND plan
# --------------------------------------------------------------------------- #


def test_forecast_envelope_with_two_points_emits_trend():
    qu = _StubQU(requires_forecast=True)
    env = _StubEnv(
        metric="forecast",
        value={
            "series": [
                {"x": "Q1", "y": 1.0e7},
                {"x": "Q2", "y": 1.2e7},
                {"x": "Q3", "y": 1.5e7},
            ]
        },
    )
    plans = plan(question_understanding=qu, envelopes=(env,))
    assert _has(plans, ChartKind.TREND)


# --------------------------------------------------------------------------- #
# 8 — forecast with only 1 point ⇒ NO TREND plan (deterministic guard)
# --------------------------------------------------------------------------- #


def test_forecast_envelope_with_one_point_no_trend():
    qu = _StubQU(requires_forecast=True)
    env = _StubEnv(
        metric="forecast",
        value={"series": [{"x": "Q1", "y": 1.0e7}]},
    )
    plans = plan(question_understanding=qu, envelopes=(env,))
    kinds = [p.chart_kind for p in plans]
    # Negative case — no canonical TREND plan emitted.
    assert not _has(plans, ChartKind.TREND)


# --------------------------------------------------------------------------- #
# 9 — risks envelope ⇒ RISK plan; concentration subset ⇒ COMPOSITION
# --------------------------------------------------------------------------- #


def test_risks_envelope_emits_risk_and_composition():
    qu = _StubQU(capability=("RISK",))
    env = _StubEnv(
        metric="risks",
        value={
            "items": [
                {"label": "Concentration", "severity": "high"},
                {"label": "FX", "severity": "low"},
            ],
            "concentration": [{"label": "Acme", "share": 0.7}],
        },
    )
    plans = plan(question_understanding=qu, envelopes=(env,))
    assert _has(plans, ChartKind.RISK)
    assert _has(plans, ChartKind.COMPOSITION)


# --------------------------------------------------------------------------- #
# 10 — readiness envelope ⇒ READINESS plan
# --------------------------------------------------------------------------- #


def test_readiness_envelope_emits_readiness():
    qu = _StubQU(requires_calculation=True, business_dependency="required")
    env = _StubEnv(metric="overall_score", value={"axes": [{"label": "x", "value": 50, "max": 100}]})
    plans = plan(question_understanding=qu, envelopes=(env,))
    assert _has(plans, ChartKind.READINESS)


# --------------------------------------------------------------------------- #
# 11 — KPI metric envelope + profile ⇒ KPI plan (when no richer chart qualifies)
# --------------------------------------------------------------------------- #


def test_kpi_envelope_emits_kpi():
    qu = _StubQU(requires_calculation=True, business_dependency="required")
    env = _StubEnv(metric="amount", value=1.0e7, unit="INR")
    plans = plan(question_understanding=qu, envelopes=(env,))
    kinds = [p.chart_kind for p in plans]
    assert ChartKind.KPI in kinds


# --------------------------------------------------------------------------- #
# 12 — pure-function invariance
# --------------------------------------------------------------------------- #


def test_planner_is_pure():
    qu = _StubQU(requires_calculation=True, business_dependency="required")
    env = _StubEnv(metric="growth", value={"current": 1.0e7, "target": 3.0e7})
    a = plan(question_understanding=qu, envelopes=(env,))
    b = plan(question_understanding=qu, envelopes=(env,))
    assert a == b


# --------------------------------------------------------------------------- #
# Bonus — VisualizationPlan.to_dict round-trip preserves shape
# --------------------------------------------------------------------------- #


def test_plan_to_dict_shape():
    p = VisualizationPlan(
        chart_kind=ChartKind.KPI,
        title="Score",
        purpose="headline",
        source_evidence_ids=("p1",),
        calculation_ids=("c1",),
        assumptions=("a",),
        limitations=("l",),
        confidence=0.9,
    )
    out = p.to_dict()
    assert out["chart_kind"] == "kpi"
    assert out["title"] == "Score"
    assert out["source_evidence_ids"] == ["p1"]
    assert out["confidence"] == 0.9
    assert out["assumptions"] == ["a"]


# --------------------------------------------------------------------------- #
# AI-15 — VisualizationPlannerResult wrapper exposes the brief's 4 fields
# --------------------------------------------------------------------------- #


def test_plan_returns_planner_result_with_all_four_fields():
    """The brief mandates four return fields. The wrapper
    dataclass exposes them plus the raw plans tuple."""
    qu = _StubQU(
        requires_calculation=True, business_dependency="required"
    )
    env = _StubEnv(
        metric="growth", value={"current": 1.0e7, "target": 3.0e7}
    )
    result = plan(question_understanding=qu, envelopes=(env,))
    assert isinstance(result, VisualizationPlannerResult)
    # The four brief-mandated fields are present.
    assert hasattr(result, "requested_charts")
    assert hasattr(result, "rationale")
    assert hasattr(result, "data_sources")
    assert hasattr(result, "materially_useful")
    # Plus the convenience raw plans tuple for callers.
    assert hasattr(result, "plans")
    assert isinstance(result.requested_charts, tuple)
    assert isinstance(result.rationale, str)
    assert isinstance(result.data_sources, tuple)
    assert isinstance(result.materially_useful, bool)
    assert isinstance(result.plans, tuple)


def test_requested_charts_dedupes_to_brief_canonical_kinds():
    """A QU that would emit two REVENUE_PROGRESS plans must yield
    exactly one requested_charts entry — the brief-canonical
    enum member, deduped in emit order."""
    qu = _StubQU(
        requires_calculation=True, business_dependency="required"
    )
    env = _StubEnv(
        metric="growth",
        value={"current": 1.0e7, "target": 3.0e7},
        input_evidence_ids=("p1",),
    )
    result = plan(question_understanding=qu, envelopes=(env,))
    # Growth envelope yields REVENUE_PROGRESS + (because
    # requires_calc=True) KPI. Both dedupe to brief-canonical
    # values.
    kinds = result.requested_charts
    # All entries must be ChartKind enum members.
    for k in kinds:
        assert isinstance(k, ChartKind)
    # Brief-canonical names only — no legacy alias slipped through.
    brief_set = {
        "revenue_progress",
        "revenue_trend",
        "supplier_composition",
        "strategy_comparison",
        "forecast_scenario",
        "readiness_radar",
        "risk_distribution",
        "kpi",
    }
    for k in kinds:
        assert k.value in brief_set
    # No duplicates — set comparison must match length.
    assert len(set(kinds)) == len(kinds)


def test_materially_useful_false_when_no_plans():
    """An educational / general-knowledge prompt yields zero
    plans AND ``materially_useful is False``. The renderer's
    contract is: hide the chart slot when the planner says
    nothing materially helps."""
    qu = _StubQU(literal_question="What is EBITDA?")
    result = plan(question_understanding=qu, envelopes=())
    assert result.materially_useful is False
    assert result.requested_charts == ()
    assert result.rationale == ""
    assert result.data_sources == ()
    assert result.plans == ()


def test_data_sources_unions_evidence_and_calculation_ids():
    """``data_sources`` is the ordered, deduped union of every
    plan's source_evidence_ids and calculation_ids. Three
    plans with overlapping IDs must produce a deduplicated
    tuple preserving emit order."""
    qu = _StubQU(
        requires_calculation=True,
        requires_scenario_analysis=True,
        business_dependency="required",
    )
    env_growth = _StubEnv(
        metric="growth",
        value={"current": 1.0e7, "target": 3.0e7},
        input_evidence_ids=("e1", "e2"),
        calculation_id="c1",
    )
    env_scenario = _StubEnv(
        metric="scenario",
        value={
            "baseline": 1.0e7,
            "changed_input": 0.15,
            "estimated_effect": -1.5e6,
        },
        input_evidence_ids=("e2", "e3"),  # e2 is shared
        calculation_id="c2",
    )
    result = plan(
        question_understanding=qu,
        envelopes=(env_growth, env_scenario),
    )
    sources = result.data_sources
    # Must contain every distinct ID.
    assert "e1" in sources
    assert "e2" in sources
    assert "e3" in sources
    assert "c1" in sources
    assert "c2" in sources
    # Deduped — no duplicate e2.
    assert len(sources) == len(set(sources))
    # emit-order preserved: e1, e2 come from the first plan,
    # so e1 < e2 < e3 in the tuple.
    assert sources.index("e1") < sources.index("e2") < sources.index("e3")
    # Calculation IDs follow their plan's evidence IDs.
    assert sources.index("e2") < sources.index("c1")
    assert sources.index("e3") < sources.index("c2")


def test_planner_result_to_dict_round_trip():
    """``to_dict()`` exposes the four brief-mandated fields
    as JSON-safe values plus the raw plans list."""
    qu = _StubQU(
        requires_calculation=True, business_dependency="required"
    )
    env = _StubEnv(
        metric="growth", value={"current": 1.0e7, "target": 3.0e7}
    )
    result = plan(question_understanding=qu, envelopes=(env,))
    out = result.to_dict()
    assert "requested_charts" in out
    assert "rationale" in out
    assert "data_sources" in out
    assert "materially_useful" in out
    assert "plans" in out
    # JSON-safe values.
    assert all(isinstance(k, str) for k in out["requested_charts"])
    assert isinstance(out["rationale"], str)
    assert all(isinstance(s, str) for s in out["data_sources"])
    assert isinstance(out["materially_useful"], bool)
    assert isinstance(out["plans"], list)
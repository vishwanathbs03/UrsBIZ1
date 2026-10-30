"""Sprint AI-15 — unit tests for ``chart_data_builder``.

8 tests covering per-chart-kind data resolution + the
deterministic empty-state path.
"""

from __future__ import annotations

from app.services.ai.reasoning.chart_data_builder import (
    ChartPayload,
    build,
)
from app.services.ai.reasoning.visualization_planner import (
    ChartKind,
    VisualizationPlan,
)


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #


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


class _StubCtx:
    """Minimal AssistantContext stub exposing the fields the
    builder reads. Default values are empty so each test sets
    what it needs explicitly."""

    def __init__(self, **kw):
        self.target_revenue_inr = kw.get("target_revenue_inr", None)
        self.annual_revenue_inr = kw.get("annual_revenue_inr", None)
        self.supplier_dependencies = kw.get("supplier_dependencies", ())


def _plan(kind: ChartKind, **kw) -> VisualizationPlan:
    return VisualizationPlan(
        chart_kind=kind,
        title=kw.get("title", "T"),
        purpose=kw.get("purpose", "p"),
        recommended_display=kw.get("recommended_display", "card"),
        explanation=kw.get("explanation", "x"),
        source_evidence_ids=kw.get("source_evidence_ids", ()),
        calculation_ids=kw.get("calculation_ids", ()),
        assumptions=kw.get("assumptions", ()),
        limitations=kw.get("limitations", ()),
        confidence=kw.get("confidence", 1.0),
    )


# --------------------------------------------------------------------------- #
# 1 — KPI builder reads value from envelope
# --------------------------------------------------------------------------- #


def test_kpi_builder_reads_value():
    plan = _plan(ChartKind.KPI)
    env = _StubEnv(metric="amount", value=1.5e7, unit="INR")
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert isinstance(payload, ChartPayload)
    assert payload.data, "KPI data should be non-empty"
    assert payload.data.get("value") == 1.5e7
    assert payload.data.get("unit") == "INR"
    assert payload.empty_reason == ""
    assert payload.confidence > 0


# --------------------------------------------------------------------------- #
# 2 — Progress builder reads current / target
# --------------------------------------------------------------------------- #


def test_progress_builder_reads_current_and_target():
    plan = _plan(ChartKind.PROGRESS)
    env = _StubEnv(
        metric="growth",
        value={"current": 1.0e7, "target": 3.0e7},
        unit="INR",
    )
    ctx = _StubCtx(target_revenue_inr=3.0e7, annual_revenue_inr=1.0e7)
    payload = build(plan, envelopes=(env,), context=ctx)
    assert payload.data, "Progress data should be non-empty"
    assert payload.data.get("current") == 1.0e7
    assert payload.data.get("target") == 3.0e7
    assert payload.empty_reason == ""


# --------------------------------------------------------------------------- #
# 3 — Comparison builder reads compare envelope
# --------------------------------------------------------------------------- #


def test_comparison_builder_reads_compare_envelope():
    plan = _plan(ChartKind.COMPARISON)
    env = _StubEnv(
        metric="compare",
        value={"left": {"label": "A", "metrics": []}, "right": {"label": "B", "metrics": []}},
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data, "Comparison data should be non-empty"
    assert payload.data.get("left", {}).get("label") == "A"
    assert payload.data.get("right", {}).get("label") == "B"


# --------------------------------------------------------------------------- #
# 4 — Trend builder returns empty when <2 points
# --------------------------------------------------------------------------- #


def test_trend_builder_returns_empty_with_one_point():
    plan = _plan(ChartKind.TREND)
    env = _StubEnv(
        metric="forecast",
        value={"series": [{"x": "Q1", "y": 1.0e7}]},
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data == {}
    assert payload.empty_reason
    assert "Not enough" in payload.empty_reason


# --------------------------------------------------------------------------- #
# 5 — Scenario builder stamps assumptions
# --------------------------------------------------------------------------- #


def test_scenario_builder_stamps_assumptions():
    plan = _plan(
        ChartKind.SCENARIO,
        assumptions=("cotton prices stable",),
        confidence=0.6,
    )
    env = _StubEnv(
        metric="scenario",
        value={"baseline": 1.0e7, "changed_input": 0.15, "estimated_effect": -1.5e6},
        assumptions=("cotton prices stable",),
        confidence=0.6,
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data, "Scenario data should be non-empty"
    assert "cotton prices stable" in payload.assumptions
    assert payload.confidence <= 0.7


# --------------------------------------------------------------------------- #
# 6 — Risk builder buckets by severity
# --------------------------------------------------------------------------- #


def test_risk_builder_buckets_by_severity():
    plan = _plan(ChartKind.RISK)
    env = _StubEnv(
        metric="risks",
        value={
            "items": [
                {"label": "Concentration", "severity": "high"},
                {"label": "FX", "severity": "low"},
                {"label": "Compliance", "severity": "medium"},
            ]
        },
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data, "Risk data should be non-empty"
    assert payload.data.get("segments") or payload.data.get("items")
    assert payload.empty_reason == ""


# --------------------------------------------------------------------------- #
# 7 — Composition builder respects max 5 slices
# --------------------------------------------------------------------------- #


def test_composition_builder_caps_slices():
    plan = _plan(ChartKind.COMPOSITION)
    env = _StubEnv(
        metric="risks",
        value={
            "concentration": [
                {"label": "A", "share": 0.4},
                {"label": "B", "share": 0.2},
                {"label": "C", "share": 0.15},
                {"label": "D", "share": 0.1},
                {"label": "E", "share": 0.05},
                {"label": "F", "share": 0.05},
                {"label": "G", "share": 0.05},
            ]
        },
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data, "Composition data should be non-empty"
    slices = payload.data.get("slices") or payload.data.get("items") or []
    # Cap at 5 explicit + maybe one "Other" → at most 6
    assert len(slices) <= 6


# --------------------------------------------------------------------------- #
# 8 — Readiness builder maps axes from health_score envelope
# --------------------------------------------------------------------------- #


def test_readiness_builder_maps_axes():
    plan = _plan(ChartKind.READINESS)
    env = _StubEnv(
        metric="overall_score",
        value={"axes": [{"label": "Finance", "value": 70, "max": 100}]},
    )
    payload = build(plan, envelopes=(env,), context=_StubCtx())
    assert payload.data, "Readiness data should be non-empty"
    axes = payload.data.get("axes") or []
    assert any(a.get("label") == "Finance" for a in axes)


# --------------------------------------------------------------------------- #
# Bonus — empty builder surfaces "Not enough business data"
# --------------------------------------------------------------------------- #


def test_empty_chart_has_reason():
    plan = _plan(ChartKind.KPI)
    payload = build(plan, envelopes=(), context=_StubCtx())
    assert payload.data == {}
    assert payload.empty_reason
    assert "business data" in payload.empty_reason.lower()


# --------------------------------------------------------------------------- #
# Bonus — payload to_dict round-trip
# --------------------------------------------------------------------------- #


def test_payload_to_dict_round_trip():
    env = _StubEnv(metric="amount", value=1.5e7, unit="INR")
    payload = build(
        _plan(ChartKind.KPI),
        envelopes=(env,),
        context=_StubCtx(),
    )
    out = payload.to_dict()
    assert out["chart_kind"] == "kpi"
    assert isinstance(out["data"], dict)
    assert isinstance(out["confidence"], float)
    assert isinstance(out["source_evidence_ids"], list)

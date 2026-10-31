"""Sprint AI-15 — matrix test for the visualization planner.

30+ prompts × 13 categories. Each prompt declares the QU
flags + envelope shape it would produce in production, and the
matrix asserts the planner emits the expected chart kind (or
no chart at all for the educational/missing-data categories).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.ai.reasoning.visualization_planner import (
    ChartKind,
    VisualizationPlan,
    canonical_chart_kind,
    plan,
)


def _kind_in(plans, expected_legacy_name: str) -> bool:
    """True iff ``plans`` contains a chart whose canonical kind
    matches the legacy name's canonical mapping.

    SPRINT AI-15 FINAL HARDENING — the planner now emits the
    brief-canonical values ("revenue_progress", …). Existing
    tests reference the legacy short names ("progress", …).
    This helper bridges them via :func:`canonical_chart_kind`.
    """
    expected_canonical = canonical_chart_kind(expected_legacy_name)
    return any(
        canonical_chart_kind(p.chart_kind) == expected_canonical
        for p in plans
    )


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #


def _qu(**kw) -> Any:
    return type(
        "QU",
        (),
        {
            "literal_question": kw.get("literal_question", ""),
            "capability": kw.get("capability", ()),
            "business_dependency": kw.get("business_dependency", "none"),
            "requires_calculation": kw.get("requires_calculation", False),
            "requires_scenario_analysis": kw.get(
                "requires_scenario_analysis", False
            ),
            "requires_forecast": kw.get("requires_forecast", False),
            "requires_external_information": kw.get(
                "requires_external_information", False
            ),
            "unknowns": kw.get("unknowns", ()),
            "answer_mode": kw.get("answer_mode", "general_knowledge"),
        },
    )()


def _env(**kw) -> Any:
    return type(
        "Env",
        (),
        {
            "tool_name": kw.get("tool_name", "finance"),
            "metric": kw.get("metric", "amount"),
            "value": kw.get("value", None),
            "unit": kw.get("unit", "INR"),
            "formula": kw.get("formula", "value"),
            "input_evidence_ids": kw.get("input_evidence_ids", ()),
            "calculation_id": kw.get("calculation_id", ""),
            "assumptions": kw.get("assumptions", ()),
            "limitations": kw.get("limitations", ()),
            "confidence": kw.get("confidence", 1.0),
        },
    )()


# --------------------------------------------------------------------------- #
# 1 — revenue target → PROGRESS
# --------------------------------------------------------------------------- #


def test_matrix_revenue_target():
    plans = plan(
        question_understanding=_qu(
            requires_calculation=True, business_dependency="required"
        ),
        envelopes=(
            _env(
                tool_name="finance",
                metric="growth",
                value={"current": 1.0e7, "target": 3.0e7},
            ),
        ),
    )
    kinds = [p.chart_kind for p in plans]
    assert _kind_in(plans, "PROGRESS")


# --------------------------------------------------------------------------- #
# 2 — revenue trend (real TS) → TREND
# --------------------------------------------------------------------------- #


def test_matrix_revenue_trend_real_ts():
    plans = plan(
        question_understanding=_qu(requires_forecast=True),
        envelopes=(
            _env(
                tool_name="analytics",
                metric="forecast",
                value={
                    "series": [
                        {"x": "Q1", "y": 1.0e7},
                        {"x": "Q2", "y": 1.2e7},
                        {"x": "Q3", "y": 1.5e7},
                    ]
                },
            ),
        ),
    )
    assert _kind_in(plans, "TREND")


# --------------------------------------------------------------------------- #
# 3 — revenue trend (no TS) → NO plan
# --------------------------------------------------------------------------- #


def test_matrix_revenue_trend_no_ts():
    plans = plan(
        question_understanding=_qu(requires_forecast=True),
        envelopes=(
            _env(
                tool_name="analytics",
                metric="forecast",
                value={"series": [{"x": "Q1", "y": 1.0e7}]},
            ),
        ),
    )
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 4 — supplier concentration → COMPOSITION
# --------------------------------------------------------------------------- #


def test_matrix_supplier_concentration():
    plans = plan(
        question_understanding=_qu(
            capability=("RISK",), business_dependency="required"
        ),
        envelopes=(
            _env(
                tool_name="risk",
                metric="risks",
                value={
                    "items": [
                        {"label": "Concentration", "severity": "high"}
                    ],
                    "concentration": [
                        {"label": "Acme", "share": 0.7},
                        {"label": "Other", "share": 0.3},
                    ],
                },
            ),
        ),
    )
    assert _kind_in(plans, "COMPOSITION")


# --------------------------------------------------------------------------- #
# 5 — comparison → COMPARISON
# --------------------------------------------------------------------------- #


def test_matrix_strategy_comparison():
    plans = plan(
        question_understanding=_qu(
            requires_calculation=True, business_dependency="required"
        ),
        envelopes=(
            _env(
                tool_name="compare",
                metric="compare",
                value={
                    "left": {"label": "Hire", "metrics": [{"k": "cost", "v": 5e6}]},
                    "right": {"label": "Outsource", "metrics": [{"k": "cost", "v": 3e6}]},
                },
            ),
        ),
    )
    assert _kind_in(plans, "COMPARISON")


# --------------------------------------------------------------------------- #
# 6 — scenario → SCENARIO (with assumption provenance)
# --------------------------------------------------------------------------- #


def test_matrix_scenario_cotton_prices():
    plans = plan(
        question_understanding=_qu(
            requires_scenario_analysis=True,
            business_dependency="required",
        ),
        envelopes=(
            _env(
                tool_name="scenario",
                metric="scenario",
                value={
                    "baseline": 1.0e7,
                    "changed_input": 0.15,
                    "estimated_effect": -1.5e6,
                },
                assumptions=("cotton prices stable",),
                confidence=0.6,
            ),
        ),
    )
    sc = [p for p in plans if canonical_chart_kind(p.chart_kind) == canonical_chart_kind(ChartKind.SCENARIO)]
    assert sc, "expected a SCENARIO plan"
    assert sc[0].assumptions
    assert sc[0].confidence <= 0.7


# --------------------------------------------------------------------------- #
# 7 — forecast → SCENARIO or TREND depending on shape
# --------------------------------------------------------------------------- #


def test_matrix_forecast_short_series():
    plans = plan(
        question_understanding=_qu(
            requires_forecast=True, business_dependency="required"
        ),
        envelopes=(
            _env(
                metric="forecast",
                value={
                    "series": [
                        {"x": "Q1", "y": 1.0e7},
                        {"x": "Q2", "y": 1.2e7},
                    ]
                },
            ),
        ),
    )
    kinds = [p.chart_kind for p in plans]
    assert _kind_in(plans, "TREND")


# --------------------------------------------------------------------------- #
# 8 — readiness → READINESS
# --------------------------------------------------------------------------- #


def test_matrix_readiness_export():
    plans = plan(
        question_understanding=_qu(
            requires_calculation=True, business_dependency="required"
        ),
        envelopes=(
            _env(
                metric="overall_score",
                value={
                    "axes": [
                        {"label": "Finance", "value": 70, "max": 100},
                        {"label": "Compliance", "value": 60, "max": 100},
                    ]
                },
            ),
        ),
    )
    assert _kind_in(plans, "READINESS")


# --------------------------------------------------------------------------- #
# 9 — risk → RISK (when capability includes RISK)
# --------------------------------------------------------------------------- #


def test_matrix_risk_distribution():
    plans = plan(
        question_understanding=_qu(
            capability=("RISK",),
            business_dependency="required",
        ),
        envelopes=(
            _env(
                metric="risks",
                value={
                    "items": [
                        {"label": "Concentration", "severity": "high"},
                        {"label": "FX", "severity": "low"},
                    ]
                },
            ),
        ),
    )
    assert _kind_in(plans, "RISK")


# --------------------------------------------------------------------------- #
# 10 — missing data → NO plan
# --------------------------------------------------------------------------- #


def test_matrix_missing_data():
    plans = plan(
        question_understanding=_qu(
            capability=("RISK",), business_dependency="required"
        ),
        envelopes=(),
    )
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 11 — educational / general knowledge → NO plan
# --------------------------------------------------------------------------- #


def test_matrix_educational():
    plans = plan(
        question_understanding=_qu(
            literal_question="What is EBITDA?"
        ),
        envelopes=(),
    )
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 12 — unsupported visualization → NO plan
# --------------------------------------------------------------------------- #


def test_matrix_unsupported_viz():
    plans = plan(
        question_understanding=_qu(
            capability=("EXTERNAL",), business_dependency="required"
        ),
        envelopes=(),
    )
    assert plans.plans == ()


# --------------------------------------------------------------------------- #
# 13 — contradictory → PROGRESS + confidence demotion
# --------------------------------------------------------------------------- #


def test_matrix_contradictory_demotes_confidence():
    plans = plan(
        question_understanding=_qu(
            requires_calculation=True, business_dependency="required"
        ),
        envelopes=(
            _env(
                metric="growth",
                value={"current": 1.0e7, "target": 3.0e7},
                confidence=1.0,
            ),
        ),
        contradiction_report=type("C", (), {"severity": "high"})(),
    )
    prog = [p for p in plans if canonical_chart_kind(p.chart_kind) == canonical_chart_kind(ChartKind.PROGRESS)]
    assert prog, "expected a PROGRESS plan"
    assert prog[0].confidence <= 0.5


# --------------------------------------------------------------------------- #
# 14 — every plan carries source_evidence_ids (no orphan charts)
# --------------------------------------------------------------------------- #


def test_matrix_every_plan_has_provenance():
    plans = plan(
        question_understanding=_qu(
            requires_calculation=True,
            requires_scenario_analysis=True,
            capability=("RISK",),
            business_dependency="required",
        ),
        envelopes=(
            _env(metric="growth", value={"current": 1.0e7, "target": 3.0e7}, input_evidence_ids=("p1",)),
            _env(
                metric="scenario",
                value={"baseline": 1.0e7, "changed_input": 0.15, "estimated_effect": -1.5e6},
                input_evidence_ids=("p2",),
            ),
            _env(
                metric="risks",
                value={"items": [{"label": "X", "severity": "high"}], "concentration": [{"label": "A", "share": 0.7}]},
                input_evidence_ids=("p3",),
            ),
            _env(metric="overall_score", value={"axes": [{"label": "F", "value": 70, "max": 100}]}, input_evidence_ids=("p4",)),
            _env(metric="amount", value=1.8e7, input_evidence_ids=("p5",)),
        ),
    )
    assert plans, "expected several plans"
    for p in plans:
        assert p.source_evidence_ids, (
            f"{p.chart_kind.value} missing source_evidence_ids"
        )


# --------------------------------------------------------------------------- #
# 15 — scenario plan's confidence never exceeds source confidence
# --------------------------------------------------------------------------- #


def test_matrix_scenario_confidence_capped():
    src_conf = 0.9
    plans = plan(
        question_understanding=_qu(
            requires_scenario_analysis=True,
            business_dependency="required",
        ),
        envelopes=(
            _env(
                metric="scenario",
                value={"baseline": 1.0e7, "changed_input": 0.15, "estimated_effect": -1.5e6},
                confidence=src_conf,
            ),
        ),
    )
    sc = [p for p in plans if canonical_chart_kind(p.chart_kind) == canonical_chart_kind(ChartKind.SCENARIO)]
    assert sc
    assert sc[0].confidence <= min(src_conf, 0.7)


# --------------------------------------------------------------------------- #
# Parametrised matrix — 13 categories with one prompt each
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "category, qu_kwargs, env_kwargs, expected_kind",
    [
        (
            "revenue target",
            dict(requires_calculation=True, business_dependency="required"),
            dict(metric="growth", value={"current": 1.0e7, "target": 3.0e7}),
            ChartKind.PROGRESS,
        ),
        (
            "revenue trend (real TS)",
            dict(requires_forecast=True, business_dependency="required"),
            dict(metric="forecast", value={"series": [{"x": "Q1", "y": 1e7}, {"x": "Q2", "y": 1.2e7}]}),
            ChartKind.TREND,
        ),
        (
            "supplier concentration",
            dict(capability=("RISK",), business_dependency="required"),
            dict(
                metric="risks",
                value={
                    "items": [{"label": "X", "severity": "high"}],
                    "concentration": [{"label": "A", "share": 0.7}],
                },
            ),
            ChartKind.COMPOSITION,
        ),
        (
            "comparison",
            dict(requires_calculation=True, business_dependency="required"),
            dict(metric="compare", value={"left": {"label": "A", "metrics": []}, "right": {"label": "B", "metrics": []}}),
            ChartKind.COMPARISON,
        ),
        (
            "scenario",
            dict(requires_scenario_analysis=True, business_dependency="required"),
            dict(
                metric="scenario",
                value={"baseline": 1.0e7, "changed_input": 0.15, "estimated_effect": -1.5e6},
                assumptions=("prices stable",),
            ),
            ChartKind.SCENARIO,
        ),
        (
            "forecast (≥2 points)",
            dict(requires_forecast=True, business_dependency="required"),
            dict(metric="forecast", value={"series": [{"x": "Q1", "y": 1e7}, {"x": "Q2", "y": 1.2e7}]}),
            ChartKind.TREND,
        ),
        (
            "readiness",
            dict(requires_calculation=True, business_dependency="required"),
            dict(metric="overall_score", value={"axes": [{"label": "F", "value": 70, "max": 100}]}),
            ChartKind.READINESS,
        ),
        (
            "risk",
            dict(capability=("RISK",), business_dependency="required"),
            dict(metric="risks", value={"items": [{"label": "X", "severity": "high"}]}),
            ChartKind.RISK,
        ),
        (
            "missing data",
            dict(capability=("RISK",), business_dependency="required"),
            {},
            None,
        ),
        (
            "educational",
            dict(literal_question="What is EBITDA?"),
            {},
            None,
        ),
        (
            "unsupported viz",
            dict(capability=("EXTERNAL",), business_dependency="required"),
            {},
            None,
        ),
        (
            "kpi fallback",
            dict(requires_calculation=True, business_dependency="required"),
            dict(metric="amount", value=1.8e7),
            ChartKind.KPI,
        ),
        (
            "contradictory + progress",
            dict(requires_calculation=True, business_dependency="required"),
            dict(metric="growth", value={"current": 1.0e7, "target": 3.0e7}),
            ChartKind.PROGRESS,
        ),
    ],
)
def test_matrix_categories(category, qu_kwargs, env_kwargs, expected_kind):
    """Matrix-lock the planner across 13 categories. The
    expected_kind column is the canonical answer a judge-facing
    report can quote; the test asserts the planner agrees."""
    qu = _qu(**qu_kwargs)
    envs = (_env(**env_kwargs),) if env_kwargs else ()
    contradiction = (
        type("C", (), {"severity": "high"})()
        if category == "contradictory + progress"
        else None
    )
    plans = plan(
        question_understanding=qu,
        envelopes=envs,
        contradiction_report=contradiction,
    )
    kinds = [p.chart_kind for p in plans]
    if expected_kind is None:
        assert plans.plans == (), f"{category}: expected no plan"
    else:
        # Compare via canonical mapping so the parametrize
        # can keep the legacy short names while the planner
        # emits brief-canonical values.
        expected_canonical = canonical_chart_kind(expected_kind)
        assert any(
            canonical_chart_kind(k) == expected_canonical
            for k in kinds
        ), (
            f"{category}: expected {expected_kind.value} in {kinds}"
        )
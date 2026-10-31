"""Sprint AI-15 — unit tests for ``trust_summary``.

6 tests covering the disclosure payload shape, contradiction
demotion, quality-warning surfacing, and the chain-of-thought
scrub guard.
"""

from __future__ import annotations

from app.services.ai.reasoning.trust_summary import build_trust_summary
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
        self.value = kw.get("value", 1.0e7)
        self.unit = kw.get("unit", "INR")
        self.formula = kw.get("formula", "value")
        self.calculation_id = kw.get("calculation_id", "calc-1")
        self.assumptions = kw.get("assumptions", ())
        self.limitations = kw.get("limitations", ())


class _StubQuality:
    def __init__(self, **kw):
        self.needs_warning = kw.get("needs_warning", False)
        self.warning_message = kw.get("warning_message", "")


class _StubContradiction:
    def __init__(self, **kw):
        self.severity = kw.get("severity", "none")
        self.items = kw.get("items", ())


class _StubGraph:
    def __init__(self, **kw):
        self.unsupported_claim_count = kw.get("unsupported_claim_count", 0)
        self.fabricated_source_count = kw.get("fabricated_source_count", 0)


class _StubCtx:
    def __init__(self):
        self.legal_name = "Acme"
        self.industry = "Textiles"
        self.annual_revenue_inr = 1.8e7
        self.target_revenue_inr = 3.0e7
        self.employee_count = 42


def _plan(kind: ChartKind) -> VisualizationPlan:
    return VisualizationPlan(
        chart_kind=kind,
        title="T",
        purpose="p",
        recommended_display="card",
        explanation="x",
    )


# --------------------------------------------------------------------------- #
# 1 — disclosure includes 5 sections + tools + confidence_change
# --------------------------------------------------------------------------- #


def test_disclosure_has_required_sections():
    summary = build_trust_summary(
        assistant_context=_StubCtx(),
        envelopes=(_StubEnv(),),
    )
    for key in (
        "evidence",
        "calculations",
        "assumptions",
        "uncertainty",
        "alternatives",
        "tools_used",
        "tool_failures",
        "confidence_change",
        "quality_warning",
    ):
        assert key in summary, f"missing section: {key}"
    # All sections must be lists except confidence_change and quality_warning
    for key in (
        "evidence",
        "calculations",
        "assumptions",
        "uncertainty",
        "alternatives",
        "tools_used",
        "tool_failures",
    ):
        assert isinstance(summary[key], list), f"{key} should be a list"
    assert isinstance(summary["confidence_change"], str)


# --------------------------------------------------------------------------- #
# 2 — tool failures surface with reasons
# --------------------------------------------------------------------------- #


def test_tool_failures_surface_with_reasons():
    traces = (
        {"tool": "finance", "status": "ok"},
        {"tool": "compliance", "status": "error", "error": "no api key"},
        {"tool": "market", "status": "skipped", "reason": "no signal"},
    )
    summary = build_trust_summary(tool_traces=traces)
    assert "finance" in summary["tools_used"]
    failures = summary["tool_failures"]
    assert len(failures) == 2
    assert any(f["tool"] == "compliance" and f["status"] == "error" for f in failures)
    assert any(f["tool"] == "market" and f["status"] == "skipped" for f in failures)


# --------------------------------------------------------------------------- #
# 3 — contradiction reduces confidence_change label
# --------------------------------------------------------------------------- #


def test_contradiction_demotes_confidence_label():
    report = _StubContradiction(severity="high", items=({"label": "rev"},))
    summary = build_trust_summary(contradiction_report=report)
    assert "reduced" in summary["confidence_change"].lower() or "contradict" in summary["confidence_change"].lower()


# --------------------------------------------------------------------------- #
# 4 — quality warning surfaces when needs_warning
# --------------------------------------------------------------------------- #


def test_quality_warning_surfaces():
    q = _StubQuality(needs_warning=True, warning_message="Limited data")
    summary = build_trust_summary(answer_quality=q)
    assert summary["quality_warning"] == "Limited data"


def test_quality_warning_absent_when_not_needed():
    q = _StubQuality(needs_warning=False, warning_message="ignored")
    summary = build_trust_summary(answer_quality=q)
    assert summary["quality_warning"] is None


# --------------------------------------------------------------------------- #
# 5 — no chain-of-thought strings present (scrub guard)
# --------------------------------------------------------------------------- #


def test_no_chain_of_thought_strings():
    env = _StubEnv(
        assumptions=(
            "Step-by-step reasoning about revenues",
            "As an AI, I consider pricing",
            "Standard assumption about pricing",
        ),
        limitations=("Internal monologue about margins",),
    )
    summary = build_trust_summary(envelopes=(env,))
    blob = repr(summary).lower()
    assert "step-by-step reasoning" not in blob
    assert "as an ai" not in blob
    assert "internal monologue" not in blob


# --------------------------------------------------------------------------- #
# 6 — pure function invariance
# --------------------------------------------------------------------------- #


def test_pure_invariance():
    env = _StubEnv()
    a = build_trust_summary(
        assistant_context=_StubCtx(),
        envelopes=(env,),
        visualization_plans=(_plan(ChartKind.KPI),),
    )
    b = build_trust_summary(
        assistant_context=_StubCtx(),
        envelopes=(env,),
        visualization_plans=(_plan(ChartKind.KPI),),
    )
    assert a == b
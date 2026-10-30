"""SPRINT AI-5 — Business Scenario Copilot — tests.

Covers the brief's 8 mandatory scenario kinds, the 10-field
envelope shape, the wire projection, and the backward-compat
contract with the existing chat flow.
"""

from __future__ import annotations

import pytest

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    GenerationMeta,
)
from app.services.ai.simulation.analysis import (
    SCENARIO_DISCLAIMER,
    ScenarioAnalysis,
    ScenarioAnalyzer,
    ScenarioDetector,
)
from app.services.ai.simulation.simulator import ScenarioSimulator


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def sim_context() -> AssistantContext:
    """A populated business context with deterministic inputs."""
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
        employee_count="42",
        supplier_dependencies=("Mumbai Cotton Co", "Surat Logistics"),
        export_history=("Sri Lanka 2022", "Bangladesh 2021"),
    )


@pytest.fixture
def empty_context() -> AssistantContext:
    """An empty context (no revenue, no employees, no suppliers)."""
    return AssistantContext(
        business_id=2,
        legal_name="unknown",
        industry="unknown",
        annual_revenue_inr=0,
        overall_business_score=0,
        band="Foundation",
        dna=AssistantContextDna("foundation_builder", "Foundation Builder", 0),
    )


@pytest.fixture
def analyzer() -> ScenarioAnalyzer:
    return ScenarioAnalyzer()


# --------------------------------------------------------------------------- #
# 8 mandatory scenarios from the brief
# --------------------------------------------------------------------------- #


def test_scenario_01_price_change(sim_context, analyzer):
    """Brief: 'What if I increase prices 5%?'."""
    analysis = analyzer.analyze(
        "What if I increase prices 5%?", sim_context
    )
    assert analysis is not None
    assert "Price" in analysis.scenario_name and "5%" in analysis.scenario_name
    assert analysis.estimated_effects, "must have at least one effect"
    assert analysis.calculation_method, "must declare the calculation method"
    assert analysis.confidence in ("low", "medium", "high", "unknown")
    assert analysis.disclaimer == SCENARIO_DISCLAIMER


def test_scenario_02_revenue_growth(sim_context, analyzer):
    """Brief: 'What if revenue grows 10%?'."""
    analysis = analyzer.analyze("What if revenue grows 10%?", sim_context)
    assert analysis is not None
    assert "Revenue growth" in analysis.scenario_name or "10%" in analysis.scenario_name
    assert any("Revenue" in e for e in analysis.estimated_effects)
    assert any("10%" in s for s in analysis.sensitivity)


def test_scenario_03_employee_increase(sim_context, analyzer):
    """Brief: 'What if I hire 3 employees?'."""
    analysis = analyzer.analyze("What if I hire 3 employees?", sim_context)
    assert analysis is not None
    assert "3" in analysis.scenario_name
    assert any("payroll" in e.lower() or "headcount" in e.lower() for e in analysis.changes + analysis.estimated_effects)


def test_scenario_04_supplier_concentration(sim_context, analyzer):
    """Brief: 'What if supplier dependency falls from 75% to 40%?'."""
    analysis = analyzer.analyze(
        "What if supplier dependency falls from 75% to 40%?", sim_context
    )
    assert analysis is not None
    assert "75%" in analysis.scenario_name and "40%" in analysis.scenario_name
    assert any("supplier" in r.lower() for r in analysis.risks)
    assert any("disruption" in e.lower() or "downside" in e.lower() for e in analysis.estimated_effects)


def test_scenario_05_export_expansion(sim_context, analyzer):
    """Brief: 'What if I enter Europe?' / 'What if exports double?'."""
    analysis = analyzer.analyze("What if I enter Europe?", sim_context)
    assert analysis is not None
    assert "Export" in analysis.scenario_name
    # Export branch should mention FX risk and margin uplift
    assert any("FX" in r or "currency" in r.lower() for r in analysis.risks)
    assert any("revenue" in e.lower() for e in analysis.estimated_effects)


def test_scenario_06_inventory_change(sim_context, analyzer):
    """Brief: 'What if I reduce inventory?'."""
    analysis = analyzer.analyze("What if I reduce inventory by 30 days?", sim_context)
    assert analysis is not None
    assert "Inventory" in analysis.scenario_name
    assert any("Cash" in e or "Working" in e for e in analysis.estimated_effects)
    # Demand pattern is unknowable → must flag in unknowns
    assert any("demand" in u.lower() for u in analysis.unknowns)


def test_scenario_07_investment_scenario(sim_context, analyzer):
    """Brief: 'What if I invest ₹20 lakh?'."""
    analysis = analyzer.analyze("What if I invest ₹20 lakh?", sim_context)
    assert analysis is not None
    assert "Investment" in analysis.scenario_name or "20" in analysis.scenario_name
    assert analysis.calculation_method, "must declare payback calculation"
    assert analysis.confidence in ("low", "medium", "high", "unknown")


def test_scenario_08_missing_data(analyzer):
    """Brief: 'What if my business changes?' (no numeric)."""
    analysis = analyzer.analyze("What if my business changes?", None)
    assert analysis is not None
    assert analysis.confidence == "unknown"
    assert analysis.estimated_effects == ["Insufficient data to estimate"]
    assert any("Required" in u or "Quantitative" in u or "amount" in u.lower() for u in analysis.unknowns)


# --------------------------------------------------------------------------- #
# Envelope shape contract
# --------------------------------------------------------------------------- #


def test_envelope_has_all_10_fields(sim_context, analyzer):
    """The brief lists 10 fields; the envelope must carry all of them."""
    analysis = analyzer.analyze("What if I increase prices 5%?", sim_context)
    assert analysis is not None
    for field in (
        "scenario_name",
        "baseline",
        "changes",
        "assumptions",
        "calculation_method",
        "estimated_effects",
        "risks",
        "unknowns",
        "sensitivity",
        "confidence",
    ):
        assert hasattr(analysis, field), f"missing field: {field}"
    # disclaimer is the 11th canonical field.
    assert hasattr(analysis, "disclaimer")


def test_envelope_disclaimer_is_canonical(sim_context, analyzer):
    """ALL scenarios must carry the exact disclaimer string."""
    prompts = [
        "What if I increase prices 5%?",
        "What if revenue grows 10%?",
        "What if I hire 3 employees?",
        "What if supplier dependency falls from 75% to 40%?",
        "What if I enter Europe?",
        "What if I reduce inventory by 30 days?",
        "What if I invest ₹20 lakh?",
    ]
    for p in prompts:
        a = analyzer.analyze(p, sim_context)
        assert a is not None
        assert a.disclaimer == SCENARIO_DISCLAIMER, (
            f"disclaimer drift on prompt: {p}"
        )


def test_envelope_to_dict_round_trips(sim_context, analyzer):
    """to_dict() must produce the wire shape with all 10 fields + present."""
    analysis = analyzer.analyze("What if I increase prices 5%?", sim_context)
    d = analysis.to_dict()
    assert d["present"] is True
    for field in (
        "scenario_name",
        "baseline",
        "changes",
        "assumptions",
        "calculation_method",
        "estimated_effects",
        "risks",
        "unknowns",
        "sensitivity",
        "confidence",
        "disclaimer",
    ):
        assert field in d, f"to_dict() missing field: {field}"
    # Lists serialise as lists.
    assert isinstance(d["baseline"], list)
    assert isinstance(d["estimated_effects"], list)


def test_envelope_lists_are_lists(sim_context, analyzer):
    """All bullet-list fields must be list[str], never tuples or strings."""
    analysis = analyzer.analyze("What if revenue grows 10%?", sim_context)
    d = analysis.to_dict()
    for field in (
        "baseline",
        "changes",
        "assumptions",
        "estimated_effects",
        "risks",
        "unknowns",
        "sensitivity",
    ):
        assert isinstance(d[field], list), f"{field} is not a list"
        for item in d[field]:
            assert isinstance(item, str), f"{field} contains non-str: {item!r}"


def test_envelope_confidence_is_one_of_four(sim_context, analyzer):
    """Confidence must be one of low/medium/high/unknown — bounded vocabulary."""
    prompts = [
        "What if I increase prices 5%?",
        "What if revenue grows 10%?",
        "What if I hire 3 employees?",
        "What if I enter Europe?",
        "What if I reduce inventory by 30 days?",
        "What if I invest ₹20 lakh?",
        "What if something happens?",  # missing data
    ]
    for p in prompts:
        a = analyzer.analyze(p, sim_context)
        assert a is not None
        assert a.confidence in ("low", "medium", "high", "unknown"), (
            f"unexpected confidence: {a.confidence!r} for prompt={p!r}"
        )


def test_envelope_frozen(sim_context, analyzer):
    """ScenarioAnalysis is a frozen dataclass — no mutation allowed."""
    analysis = analyzer.analyze("What if I increase prices 5%?", sim_context)
    with pytest.raises(Exception):
        analysis.scenario_name = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Detector contract
# --------------------------------------------------------------------------- #


def test_detector_classifies_8_kinds(sim_context):
    """Every scenario prompt must map to one of the 8 kinds."""
    detector = ScenarioDetector()
    cases = [
        ("What if I raise prices 5%?", "price_change"),
        ("What if revenue grows 10%?", "revenue_growth"),
        ("What if I hire 3 employees?", "employee_increase"),
        ("What if supplier dependency falls?", "supplier_concentration"),
        ("What if I enter Europe?", "export_expansion"),
        ("What if I reduce inventory by 30 days?", "inventory_change"),
        ("What if I invest ₹20 lakh?", "investment_scenario"),
        ("What if something happens?", "missing_data"),
    ]
    for prompt, expected in cases:
        kind = detector.classify(prompt)
        assert kind == expected, f"kind={kind!r} expected={expected!r} for {prompt!r}"


def test_detector_returns_none_for_non_scenario():
    """Non-scenario prompts must NOT be force-classified."""
    detector = ScenarioDetector()
    non_scenarios = [
        "How healthy is my business?",
        "Show me my readiness scores.",
        "Recommend top 3 actions.",
        "Explain my business DNA.",
    ]
    for p in non_scenarios:
        assert detector.classify(p) is None, (
            f"non-scenario prompt was misclassified: {p!r}"
        )


def test_detector_handles_edge_cases():
    """Empty / whitespace / unicode inputs must not crash."""
    detector = ScenarioDetector()
    assert detector.classify("") is None
    assert detector.classify("   ") is None
    assert detector.classify("🤔") is None
    assert detector.classify("What if 🤖 raises prices 5%?") == "price_change"


# --------------------------------------------------------------------------- #
# Wire projection — GenerationMeta + chat payload
# --------------------------------------------------------------------------- #


def test_generation_meta_carries_scenario_analysis():
    """GenerationMeta.empty() must accept scenario_analysis kwarg."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic-fallback",
        model="deterministic-fallback",
        provider_latency_ms=42,
        fallback_used=True,
        scenario_analysis={"scenario_name": "test", "present": True},
    )
    assert meta.scenario_analysis == {"scenario_name": "test", "present": True}


def test_generation_meta_scenario_analysis_default_none():
    """Default for scenario_analysis is None — backward-compatible."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic-fallback",
        model="deterministic-fallback",
        provider_latency_ms=None,
        fallback_used=False,
    )
    assert meta.scenario_analysis is None


def test_generation_meta_scenario_analysis_round_trip():
    """from_dict must reconstruct the scenario_analysis field."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
        scenario_analysis={"disclaimer": SCENARIO_DISCLAIMER, "present": True},
    )
    d = meta.to_dict()
    meta2 = GenerationMeta.from_dict(d)
    assert meta2.scenario_analysis == {"disclaimer": SCENARIO_DISCLAIMER, "present": True}


def test_generation_meta_scenario_analysis_legacy_row():
    """Legacy rows that pre-date AI-5 must reconstruct with None."""
    legacy = GenerationMeta.empty(
        mode="grounded",
        provider_used="p",
        model="m",
        provider_latency_ms=None,
        fallback_used=False,
    )
    d = legacy.to_dict()
    # AI-5 not present in legacy dict — from_dict must still work.
    meta2 = GenerationMeta.from_dict(d)
    assert meta2.scenario_analysis is None


# --------------------------------------------------------------------------- #
# Backward-compat
# --------------------------------------------------------------------------- #


def test_analyzer_returns_none_for_legacy_prompts():
    """Non-scenario prompts must return None so the LLM route runs unchanged."""
    analyzer = ScenarioAnalyzer()
    ctx = AssistantContext(
        business_id=1,
        legal_name="Acme",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )
    assert analyzer.analyze("How healthy is my business?", ctx) is None
    assert analyzer.analyze("Explain my roadmap.", ctx) is None


def test_simulator_existing_branches_still_pass(sim_context):
    """AI-5 adds branches — original H8.4 branches must remain untouched."""
    sim = ScenarioSimulator()
    cases = [
        ("What if I buy a machine?", "equipment_capex"),
        ("What if I hire 10 employees?", "hiring"),
        ("What if exports increase 20%?", "export_growth"),
        ("What if I receive ₹50 lakh funding?", "funding"),
        ("What if cotton prices rise by 15%?", "commodity_cost"),
        ("What if I grow my business?", "facility_expansion"),
    ]
    for prompt, expected in cases:
        res = sim.simulate(prompt, sim_context)
        assert res.scenario_type == expected, (
            f"{prompt!r} → {res.scenario_type!r} (expected {expected!r})"
        )


def test_analyzer_does_not_mutate_context(sim_context, analyzer):
    """The analyzer is pure — must not mutate the input context."""
    snap_revenue = sim_context.annual_revenue_inr
    snap_emp = sim_context.employee_count
    snap_suppliers = sim_context.supplier_dependencies

    _ = analyzer.analyze("What if I increase prices 5%?", sim_context)
    _ = analyzer.analyze("What if I hire 3 employees?", sim_context)
    _ = analyzer.analyze("What if I reduce inventory by 30 days?", sim_context)

    assert sim_context.annual_revenue_inr == snap_revenue
    assert sim_context.employee_count == snap_emp
    assert sim_context.supplier_dependencies == snap_suppliers


def test_analyzer_with_empty_context_falls_back_to_missing_data(analyzer):
    """When the context has no revenue, the analyzer must not crash."""
    ctx = AssistantContext(
        business_id=2,
        legal_name="unknown",
        industry="unknown",
        annual_revenue_inr=0,
        overall_business_score=0,
        band="Foundation",
        dna=AssistantContextDna("foundation_builder", "Foundation Builder", 0),
    )
    a = analyzer.analyze("What if I increase prices 5%?", ctx)
    # Either a degraded envelope or missing_data — never None for a clear scenario prompt.
    assert a is not None
    assert a.disclaimer == SCENARIO_DISCLAIMER
    assert a.confidence in ("low", "medium", "high", "unknown")


def test_analyzer_does_not_raise_on_weird_inputs(analyzer, sim_context):
    """None context, empty string, unicode → must not crash."""
    # None context for an obvious scenario prompt falls back to missing_data.
    a = analyzer.analyze("What if revenue grows 10%?", None)
    assert a is None or a.disclaimer == SCENARIO_DISCLAIMER

    # Empty prompt — non-scenario.
    assert analyzer.analyze("", sim_context) is None
    assert analyzer.analyze("🤔", sim_context) is None
    assert analyzer.analyze("   ", sim_context) is None


# --------------------------------------------------------------------------- #
# Sensitivity + uncertainty contract
# --------------------------------------------------------------------------- #


def test_envelope_sensitivity_never_empty(sim_context, analyzer):
    """Sensitivity bounds must be populated for every computable scenario."""
    for p in [
        "What if I increase prices 5%?",
        "What if revenue grows 10%?",
        "What if I hire 3 employees?",
        "What if I enter Europe?",
        "What if I invest ₹20 lakh?",
    ]:
        a = analyzer.analyze(p, sim_context)
        assert a is not None
        assert a.sensitivity, f"empty sensitivity for {p!r}"


def test_envelope_unknowns_flag_for_missing_data(analyzer):
    """When the calculation cannot be completed, unknowns must be populated."""
    a = analyzer.analyze("What if something happens?", None)
    assert a is not None
    assert a.estimated_effects == ["Insufficient data to estimate"]
    assert a.confidence == "unknown"
    assert a.unknowns, "missing-data scenario must enumerate unknowns"

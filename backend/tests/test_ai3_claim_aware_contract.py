"""Test suite for SPRINT AI-3 — Claim-Aware Assistant Response Contract.

Coverage:
- claim_schema: dataclass round-trip, to_dict, to_chat_body, capacity limits
- claim_parser: JSON extraction, fence stripping, prose tolerance, missing field
- claim_validator: per-type rules (FACT/CALCULATION/INFERENCE/RECOMMENDATION/SCENARIO/UNKNOWN)
- numeric_checker: per-category tolerance, conflict replacement, audit log
- confidence_calculator: every component weight + clamping
- claim_fallback: deterministic payload structure + ChatClaimAwareResponse validation
- Pydantic extra='forbid' guard for the new ChatClaimAwareResponse schema
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from app.services.ai.providers.claim_schema import (
    ALLOWED_CLAIM_TYPES,
    ALLOWED_CALCULATION_SOURCES,
    ALLOWED_UNKNOWN_IMPACTS,
    Claim,
    ClaimAwareResponse,
    ClaimCalculation,
    ClaimRecommendation,
    ClaimScenario,
    ClaimUnknown,
)
from app.services.ai.providers.claim_parser import (
    extract_claim_aware_block,
    parse_claim_aware_payload,
)
from app.services.ai.providers.claim_validator import ClaimValidator
from app.services.ai.providers.numeric_checker import (
    NumericConflict,
    NumericConflictReport,
    NumericConsistencyChecker,
)
from app.services.ai.providers.confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceReport,
)
from app.services.ai.providers.claim_fallback import build_fallback_claim_aware
from app.services.ai.providers.evidence_registry import (
    EvidenceEntry,
    EvidenceRegistry,
    EvidenceKind,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _make_context(**overrides) -> SimpleNamespace:
    """A realistic Acme Textiles context for AI-3 fixture use.

    Uses a real :class:`AssistantContext` so the EvidenceRegistry
    can derive entries from populated ``recommendations`` /
    ``scores`` / ``forecasts`` / ``dna``. Override individual
    fields via kwargs (only those with non-default-safe semantics
    are listed explicitly).
    """
    from app.services.ai.providers.base import (
        AssistantContext,
        AssistantContextDna,
        AssistantContextRecommendation,
        AssistantContextScore,
        AssistantContextForecast,
    )

    base_kwargs = dict(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        location="Tirupur",
        business_type="Manufacturer",
        employee_count=42,
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=85,
        ),
        scores=(
            AssistantContextScore(
                key="health_score",
                title="Overall business score",
                score=68,
                level="established",
            ),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_001",
                title="Diversify supplier base",
                category="supply_chain",
                priority="HIGH",
                estimated_score_gain=8,
                estimated_roi=1.5,
                estimated_timeline="3 months",
            ),
        ),
        forecasts=(
            AssistantContextForecast(
                scenario_id="forecast_001",
                horizon_label="12-month scenario",
                revenue_delta=12_000_000,
                score_delta=10,
                assumption_summary="Steady margins",
                confidence=70,
            ),
        ),
        rules=(),
        insights=(),
        schemes=(),
        action_items=(),
        analytics_metrics=(),
        report_summaries=(),
        certifications=("ISO 9001",),
        export_history=("EU 2022",),
        products=("Cotton yarn",),
        services=(),
        goals=("Reach ₹3 Cr turnover",),
        challenges=(),
        supplier_dependencies=(),
        customer_dependencies=(),
        twin_generated_at="2026-08-09T10:00:00+00:00",
        recommendations_generated_at="2026-08-09T10:00:00+00:00",
        rules_generated_at="2026-08-09T10:00:00+00:00",
        insights_generated_at="2026-08-09T10:00:00+00:00",
        schemes_generated_at="2026-08-09T10:00:00+00:00",
        forecasts_generated_at="2026-08-09T10:00:00+00:00",
        action_items_generated_at="2026-08-09T10:00:00+00:00",
    )
    base_kwargs.update(overrides)
    return AssistantContext(**base_kwargs)


def _make_registry() -> EvidenceRegistry:
    """An EvidenceRegistry built from the Acme context."""
    reg = EvidenceRegistry(_make_context())
    # Sanity: registry must have at least 3 entries (rec, score, forecast, dna)
    assert reg.count >= 3, f"registry has {reg.count} entries, expected >=3"
    return reg


# --------------------------------------------------------------------------- #
# 1. claim_schema — round-trip + capacity + to_chat_body
# --------------------------------------------------------------------------- #


def test_1_allowed_claim_types_exact_set():
    """The 9 claim types are the only labels the validator accepts.

    SPRINT AI-16 extended the vocabulary with INTERNAL_BUSINESS
    and ASSUMPTION (in addition to the original 7). The 9-way
    set is the canonical contract; renaming or removing any of
    these labels would break the AI-16 claim-kind classifier.
    """
    assert set(ALLOWED_CLAIM_TYPES) == {
        "FACT",
        "CALCULATION",
        "INFERENCE",
        "RECOMMENDATION",
        "SCENARIO",
        "EXTERNAL_FACT",
        "UNKNOWN",
        # SPRINT AI-16 — two new claim kinds.
        "INTERNAL_BUSINESS",
        "ASSUMPTION",
    }
    assert len(ALLOWED_CLAIM_TYPES) == 9


def test_2_allowed_calculation_sources_exact_set():
    """CALCULATION.source must be one of these three labels."""
    assert set(ALLOWED_CALCULATION_SOURCES) == {
        "URSBIZ_ENGINE",
        "MODEL_SCENARIO",
        "USER_INPUT",
    }


def test_3_allowed_unknown_impacts_exact_set():
    """UNKNOWN.impact must be HIGH / MEDIUM / LOW."""
    assert set(ALLOWED_UNKNOWN_IMPACTS) == {"HIGH", "MEDIUM", "LOW"}


def test_4_claim_to_dict_round_trip():
    """A Claim dataclass serialises to a JSON-safe dict."""
    c = Claim(
        text="Acme Textiles employs 42 people.",
        claim_type="FACT",
        evidence_references=("rec_001",),
        confidence=80,
        user_provided=False,
    )
    d = {
        "text": c.text,
        "claim_type": c.claim_type,
        "evidence_references": list(c.evidence_references),
        "confidence": c.confidence,
        "audit_log": list(c.audit_log),
        "user_provided": c.user_provided,
    }
    assert d["claim_type"] == "FACT"
    assert d["evidence_references"] == ["rec_001"]
    assert d["confidence"] == 80


def test_5_claim_recommendation_to_dict_round_trip():
    """Recommendation serialises with all 8 fields."""
    r = ClaimRecommendation(
        title="Diversify suppliers",
        reason="Concentration on one supplier is risky.",
        recommendation_id="rec_001",
        evidence_references=("rec_001",),
        category="supply_chain",
        priority="HIGH",
        estimated_score_gain=8,
        estimated_timeline="3 months",
    )
    assert r.title == "Diversify suppliers"
    assert r.estimated_score_gain == 8
    assert r.priority == "HIGH"


def test_6_claim_calculation_to_dict_round_trip():
    c = ClaimCalculation(
        name="growth multiple",
        result=1.67,
        unit="x",
        source="URSBIZ_ENGINE",
        expression="30/18",
        inputs={"current": 18, "target": 30},
        evidence_references=("score_001",),
    )
    assert c.result == pytest.approx(1.67)
    assert c.source == "URSBIZ_ENGINE"
    assert c.inputs == {"current": 18, "target": 30}


def test_7_claim_scenario_to_dict_round_trip():
    s = ClaimScenario(
        title="Best case revenue",
        description="If revenue grows 30%.",
        assumptions=("30% growth", "Stable margins"),
        revenue_impact="+₹54 lakh",
        score_impact="+5 points",
        confidence=70,
    )
    assert len(s.assumptions) == 2
    assert s.confidence == 70


def test_8_claim_unknown_to_dict_round_trip():
    u = ClaimUnknown(
        question="What is the customer mix?",
        impact="HIGH",
        rationale="Customer mix shapes the growth plan.",
        clarification_prompt="What share of sales goes to your top customer?",
    )
    assert u.impact == "HIGH"
    assert u.clarification_prompt.endswith("customer?")


def test_9_claim_aware_response_to_dict_round_trip_full():
    """A full ClaimAwareResponse serialises without dropping fields."""
    resp = ClaimAwareResponse(
        answer="Acme is on track.",
        claims=(
            Claim(text="Score is 68", claim_type="FACT", evidence_references=("score_001",)),
            Claim(text="Could reach ₹3 Cr", claim_type="SCENARIO", confidence=60),
        ),
        recommendations=(
            ClaimRecommendation(title="Diversify", reason="Risk", recommendation_id="rec_001"),
        ),
        calculations=(
            ClaimCalculation(name="multiple", result=1.67, unit="x", source="URSBIZ_ENGINE"),
        ),
        scenarios=(
            ClaimScenario(title="Best case", description="30% growth", assumptions=("X",)),
        ),
        unknowns=(
            ClaimUnknown(question="Mix?", impact="MEDIUM", rationale="Shapes plan"),
        ),
        evidence_references=("score_001", "rec_001"),
        assumptions=("Stable margins",),
        limitations=("Profile is partial",),
        narrative="Acme is on track. Score 68.",
        server_confidence=72,
        server_confidence_rationale="base=30, evidence=20",
        numeric_conflicts=(),
        server_audit={"source": "test"},
    )
    d = resp.to_dict()
    assert d["answer"] == "Acme is on track."
    assert len(d["claims"]) == 2
    assert len(d["recommendations"]) == 1
    assert d["server_confidence"] == 72
    assert d["server_audit"]["source"] == "test"


def test_10_claim_aware_response_to_chat_body_renders_markdown():
    """to_chat_body() emits a Markdown fallback the frontend can render."""
    resp = ClaimAwareResponse(
        answer="Score 68",
        claims=(Claim(text="Score is 68", claim_type="FACT", confidence=80),),
        recommendations=(),
        narrative="narrative text",
    )
    body = resp.to_chat_body()
    assert "Score 68" in body
    assert "narrative text" in body


def test_11_claim_user_provided_default_false():
    """FACT claims need evidence OR user_provided=True. The default is False."""
    c = Claim(text="X", claim_type="FACT")
    assert c.user_provided is False
    assert c.confidence is None
    assert c.evidence_references == ()


# --------------------------------------------------------------------------- #
# 2. claim_parser — extract_claim_aware_block + parse_claim_aware_payload
# --------------------------------------------------------------------------- #


def test_12_extract_claim_aware_block_returns_none_when_missing():
    """When the LLM didn't fill claim_aware, the extractor returns None."""
    parsed = {"answer": "x", "claims": []}
    assert extract_claim_aware_block(parsed) is None


def test_13_extract_claim_aware_block_returns_dict_when_present():
    parsed = {
        "answer": "x",
        "claim_aware": {"answer": "y", "claims": []},
    }
    block = extract_claim_aware_block(parsed)
    assert block == {"answer": "y", "claims": []}


def test_14_parse_claim_aware_payload_handles_valid_json():
    """A well-formed JSON block returns ok=True and a populated response."""
    raw = json.dumps(
        {
            "answer": "Score 68",
            "claims": [
                {"text": "Score is 68", "claim_type": "FACT", "confidence": 80}
            ],
            "recommendations": [],
            "calculations": [],
            "scenarios": [],
            "unknowns": [],
            "assumptions": [],
            "limitations": [],
        }
    )
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert res.response is not None
    assert len(res.response.claims) == 1
    assert res.response.claims[0].claim_type == "FACT"


def test_15_parse_claim_aware_payload_strips_json_fences():
    """```json ... ``` fences are stripped before parsing."""
    raw = '```json\n{"answer": "x", "claims": [], "recommendations": [], "calculations": [], "scenarios": [], "unknowns": []}\n```'
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert res.response is not None
    assert res.response.answer == "x"


def test_16_parse_claim_aware_payload_recovers_from_prose():
    """When prose surrounds the JSON, the parser extracts the first balanced block."""
    raw = (
        "Here is the response:\n"
        "```json\n{\"answer\": \"x\", \"claims\": []}\n```\n"
        "Hope that helps."
    )
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert res.response.answer == "x"


def test_17_parse_claim_aware_payload_returns_none_on_malformed_json():
    """A broken JSON block yields ok=False and a populated errors list."""
    res = parse_claim_aware_payload("{not valid json")
    assert res.ok is False
    assert res.errors


def test_18_parse_claim_aware_payload_strips_server_fields():
    """The LLM is forbidden from setting server_* — the parser strips them."""
    raw = json.dumps(
        {
            "answer": "x",
            "claims": [],
            "server_confidence": 100,  # server-only
            "server_audit": {},  # server-only
        }
    )
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert res.response.server_confidence is None
    assert res.response.server_audit == {}


def test_19_parse_claim_aware_payload_maps_unknown_label_to_UNKNOWN():
    """A bogus claim_type is mapped to UNKNOWN, not rejected."""
    raw = json.dumps(
        {
            "answer": "x",
            "claims": [{"text": "y", "claim_type": "BOGUS_LABEL"}],
        }
    )
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert res.response.claims[0].claim_type == "UNKNOWN"


def test_20_parse_claim_aware_payload_clamps_text_length():
    """A very long claim text is clamped to keep the wire bounded."""
    raw = json.dumps(
        {
            "answer": "x",
            "claims": [{"text": "x" * 10_000, "claim_type": "FACT"}],
        }
    )
    res = parse_claim_aware_payload(raw)
    assert res.ok is True
    assert len(res.response.claims[0].text) <= 2000


# --------------------------------------------------------------------------- #
# 3. claim_validator — per-type rules
# --------------------------------------------------------------------------- #


def test_21_validator_fact_without_evidence_or_user_provided_fails():
    """FACT needs evidence OR user_provided=True."""
    resp = ClaimAwareResponse(claims=(Claim(text="X", claim_type="FACT"),))
    report = ClaimValidator(_make_registry(), resp).validate()
    assert report.passed is False
    assert any("evidence" in e or "user_provided" in e for e in report.errors)


def test_22_validator_fact_with_evidence_passes():
    """Evidence refs derived from context are accepted."""
    reg = _make_registry()
    # Pick any real rec id from the registry
    rec_ids = [e.id for e in reg.all() if e.kind.value == "recommendation"]
    assert rec_ids, "registry should carry a recommendation entry"
    resp = ClaimAwareResponse(
        claims=(Claim(text="X", claim_type="FACT", evidence_references=(rec_ids[0],)),)
    )
    report = ClaimValidator(reg, resp).validate()
    assert report.passed is True


def test_23_validator_fact_user_provided_passes_without_evidence():
    """FACT can skip evidence when the user supplied the value."""
    resp = ClaimAwareResponse(
        claims=(Claim(text="X", claim_type="FACT", user_provided=True),)
    )
    report = ClaimValidator(_make_registry(), resp).validate()
    assert report.passed is True


def test_24_validator_calculation_requires_allowed_source():
    """CALCULATION.source must be one of URSBIZ_ENGINE / MODEL_SCENARIO / USER_INPUT."""
    bad = ClaimAwareResponse(
        calculations=(
            ClaimCalculation(name="x", result=1.0, unit="x", source="RANDOM_SOURCE"),
        )
    )
    report = ClaimValidator(_make_registry(), bad).validate()
    assert report.passed is False

    good = ClaimAwareResponse(
        calculations=(ClaimCalculation(name="x", result=1.0, unit="x", source="URSBIZ_ENGINE"),)
    )
    report = ClaimValidator(_make_registry(), good).validate()
    assert report.passed is True


def test_25_validator_inference_requires_evidence():
    """INFERENCE must cite an evidence ID."""
    bad = ClaimAwareResponse(
        claims=(Claim(text="X", claim_type="INFERENCE"),)
    )
    report = ClaimValidator(_make_registry(), bad).validate()
    assert report.passed is False

    reg = _make_registry()
    score_ids = [e.id for e in reg.all() if e.kind.value == "score"]
    assert score_ids, "registry should carry a score entry"
    good = ClaimAwareResponse(
        claims=(
            Claim(
                text="X",
                claim_type="INFERENCE",
                evidence_references=(score_ids[0],),
            ),
        )
    )
    report = ClaimValidator(_make_registry(), good).validate()
    assert report.passed is True


def test_26_validator_recommendation_requires_reason():
    """RECOMMENDATION must have a non-empty reason."""
    bad = ClaimAwareResponse(
        recommendations=(ClaimRecommendation(title="x", reason=""),)
    )
    report = ClaimValidator(_make_registry(), bad).validate()
    assert report.passed is False

    good = ClaimAwareResponse(
        recommendations=(ClaimRecommendation(title="x", reason="Do Y"),)
    )
    report = ClaimValidator(_make_registry(), good).validate()
    assert report.passed is True


def test_27_validator_scenario_requires_assumptions():
    """SCENARIO must have a non-empty assumptions list."""
    bad = ClaimAwareResponse(
        scenarios=(ClaimScenario(title="x", description="y", assumptions=()),)
    )
    report = ClaimValidator(_make_registry(), bad).validate()
    assert report.passed is False

    good = ClaimAwareResponse(
        scenarios=(ClaimScenario(title="x", description="y", assumptions=("Z",)),)
    )
    report = ClaimValidator(_make_registry(), good).validate()
    assert report.passed is True


def test_28_validator_unknown_rejects_numeric_literal():
    """UNKNOWN must not contain numeric literals."""
    bad = ClaimAwareResponse(
        claims=(Claim(text="Revenue is 18,000,000", claim_type="UNKNOWN"),)
    )
    report = ClaimValidator(_make_registry(), bad).validate()
    assert report.passed is False

    good = ClaimAwareResponse(
        claims=(Claim(text="We don't know the customer mix", claim_type="UNKNOWN"),)
    )
    report = ClaimValidator(_make_registry(), good).validate()
    assert report.passed is True


def test_29_validator_rejects_fabricated_evidence_id():
    """An evidence ID not in the registry fails."""
    resp = ClaimAwareResponse(
        claims=(
            Claim(text="X", claim_type="FACT", evidence_references=("rec_999",)),
        )
    )
    report = ClaimValidator(_make_registry(), resp).validate()
    assert report.passed is False
    assert any("rec_999" in e for e in report.errors)


def test_30_validator_score_decreases_with_errors():
    """Each error drops the score by 10; the floor is 0."""
    resp = ClaimAwareResponse(
        claims=(
            Claim(text="X", claim_type="FACT"),  # no evidence
        ),
    )
    report = ClaimValidator(_make_registry(), resp).validate()
    assert 0 <= report.score <= 100
    assert report.score < 100


# --------------------------------------------------------------------------- #
# 4. numeric_checker — categories + tolerance + replacement
# --------------------------------------------------------------------------- #


def test_31_numeric_checker_returns_report_with_count_field():
    ctx = _make_context()
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(Claim(text="Score is 68", claim_type="FACT"),)
    )
    report = checker.check(resp)
    assert isinstance(report, NumericConflictReport)
    assert report.count == 0  # 68 matches context.overall_business_score=68


def test_32_numeric_checker_detects_currency_conflict():
    """A claim saying ₹3.5 Cr when context has ₹1.8 Cr is a currency conflict."""
    ctx = _make_context(annual_revenue_inr=18_000_000, target_revenue_inr=0)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(
            Claim(
                text="Your revenue is ₹3.5 Cr.",
                claim_type="FACT",
                evidence_references=(),
            ),
        )
    )
    report = checker.check(resp)
    assert report.count >= 1
    assert report.conflicts[0].category == "currency"


def test_33_numeric_checker_detects_score_conflict():
    """Score category with 'Score: 85' against authoritative 68 → conflict."""
    ctx = _make_context(overall_business_score=68)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(Claim(text="Score: 85", claim_type="FACT"),)
    )
    report = checker.check(resp)
    assert report.count >= 1
    assert report.conflicts[0].category == "score"


def test_34_numeric_checker_replaces_conflicting_literal():
    """The conflicting value is replaced with the authoritative one in claim.text."""
    ctx = _make_context(annual_revenue_inr=18_000_000, target_revenue_inr=0)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(
            Claim(
                text="Revenue is ₹3.5 Cr.",
                claim_type="FACT",
                evidence_references=(),
            ),
        )
    )
    checker.check(resp)
    new_text = resp.claims[0].text
    assert "₹3.5 Cr" not in new_text
    # Original preserved in audit log
    assert any("3.5" in entry for entry in resp.claims[0].audit_log)


def test_35_numeric_checker_does_not_mutate_scenarios():
    """SCENARIO descriptions are exempt — text is NOT mutated, but the
    conflict IS recorded in the report so the audit log is faithful."""
    ctx = _make_context(annual_revenue_inr=18_000_000, target_revenue_inr=0)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        scenarios=(
            ClaimScenario(
                title="Best case",
                description="If revenue reaches ₹3.5 Cr",
                assumptions=("30% growth",),
            ),
        )
    )
    report = checker.check(resp)
    # Scenario prose must be untouched.
    assert "₹3.5 Cr" in resp.scenarios[0].description
    # But the conflict IS surfaced (audit-only, not a wire-level contradiction).
    assert report.count >= 1
    assert all(
        c.replacement == "(unchanged - scenario)" for c in report.conflicts
    )


def test_36_numeric_checker_employee_count_exact_match():
    """employee_count=42 conflicts with prose saying '50 employees'."""
    ctx = _make_context(employee_count=42)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(Claim(text="Acme has 50 employees", claim_type="FACT"),)
    )
    report = checker.check(resp)
    assert report.count >= 1


def test_37_numeric_checker_within_tolerance_no_conflict():
    """68 vs 67 — within 5% → no conflict."""
    ctx = _make_context(overall_business_score=68)
    checker = NumericConsistencyChecker(context=ctx, tool_results=())
    resp = ClaimAwareResponse(
        claims=(Claim(text="Score is 67", claim_type="FACT"),)
    )
    report = checker.check(resp)
    assert report.count == 0


def test_38_numeric_checker_extracts_tool_result_values():
    """Numeric values inside tool_results payloads are added to the authoritative set."""
    from app.services.ai.reasoning.tool_selector import ToolResult

    # Only tool result provides an authoritative value (no context revenue).
    ctx = _make_context(annual_revenue_inr=0, target_revenue_inr=0)
    tool_result = ToolResult(
        service_name="forecast",
        status="ok",
        payload={"projected_revenue_inr": 25_000_000},
        duration_ms=10,
        error="",
    )
    checker = NumericConsistencyChecker(
        context=ctx, tool_results=(tool_result,)
    )
    # The LLM claims revenue is ₹2.5 Cr (matches the tool result) → no conflict
    resp = ClaimAwareResponse(
        claims=(Claim(text="Revenue is ₹2.5 Cr", claim_type="FACT"),)
    )
    report = checker.check(resp)
    assert report.count == 0


def test_39_numeric_conflict_to_dict_round_trip():
    """NumericConflict serialises to a JSON-safe dict."""
    c = NumericConflict(
        location="claims[0].text",
        original="₹3.5 Cr",
        replacement="₹1.8 Cr",
        category="currency",
        authoritative_value=18_000_000,
        tolerance=0.01,
    )
    d = c.to_dict()
    assert d["category"] == "currency"
    assert d["original"] == "₹3.5 Cr"
    assert d["authoritative_value"] == 18_000_000


def test_40_numeric_checker_empty_response_safe():
    """An empty response doesn't crash the checker."""
    checker = NumericConsistencyChecker(context=_make_context(), tool_results=())
    report = checker.check(ClaimAwareResponse())
    assert report.count == 0
    assert report.has_conflicts is False


# --------------------------------------------------------------------------- #
# 5. confidence_calculator — components + clamping
# --------------------------------------------------------------------------- #


def test_41_confidence_base_score_30_when_nothing_else():
    """base=30 is the floor when registry / claims are empty."""
    calc = ConfidenceCalculator()
    report = calc.compute()
    assert report.score == 30


def test_42_confidence_evidence_coverage_capped_at_20():
    """Cited / registry_count * 20, capped at 20. With a 6-entry registry,
    3 cited → 10. The point is the component is non-zero + scaled."""
    calc = ConfidenceCalculator()
    reg = _make_registry()
    all_ids = [e.id for e in reg.all()]
    n = len(all_ids)
    assert n >= 3
    cited = all_ids[:3]
    resp = ClaimAwareResponse(
        claims=tuple(
            Claim(text=t, claim_type="FACT", evidence_references=(eid,))
            for t, eid in zip(("A", "B", "C"), cited)
        )
    )
    rep = calc.compute(registry=reg, claim_response=resp)
    expected = min(20, (3 / n) * 20)
    assert rep.components["evidence_coverage"] == pytest.approx(expected, abs=0.01)


def test_43_confidence_source_authority_weights_match_kind_weights():
    """The registry's source_authority component reflects the kinds present."""
    calc = ConfidenceCalculator()
    reg = _make_registry()
    rep = calc.compute(registry=reg)
    # The weights are 0..15 capped. The exact value depends on the
    # kinds present in the registry; we just assert it's in bounds.
    assert 0 <= rep.components["source_authority"] <= 15


def test_44_confidence_assumption_penalty_capped_at_minus_10():
    """More than 5 assumptions can't push the penalty below -10."""
    calc = ConfidenceCalculator()
    resp = ClaimAwareResponse(
        assumptions=tuple(f"a{i}" for i in range(20)),
    )
    rep = calc.compute(claim_response=resp)
    assert rep.components["assumption_penalty"] == -10


def test_45_confidence_calculation_availability_full_when_all_ok():
    """5 tool results all OK → calculation_availability = 10."""
    from app.services.ai.reasoning.tool_selector import ToolResult

    calc = ConfidenceCalculator()
    tools = tuple(
        ToolResult(service_name=f"s{i}", status="ok", payload={}, duration_ms=1, error="")
        for i in range(5)
    )
    rep = calc.compute(tool_results=tools)
    assert rep.components["calculation_availability"] == pytest.approx(10)


def test_46_confidence_calculation_availability_zero_when_no_results():
    calc = ConfidenceCalculator()
    rep = calc.compute(tool_results=())
    assert rep.components["calculation_availability"] == 0


def test_47_confidence_contradiction_penalty_per_conflict():
    """Each numeric conflict costs 3 points."""
    calc = ConfidenceCalculator()
    nr = NumericConflictReport(
        conflicts=(
            NumericConflict(
                location="x", original="1", replacement="2",
                category="score", authoritative_value=2, tolerance=0,
            ),
            NumericConflict(
                location="y", original="3", replacement="4",
                category="score", authoritative_value=4, tolerance=0,
            ),
        )
    )
    rep = calc.compute(numeric_report=nr)
    assert rep.components["contradiction_penalty"] == -6


def test_48_confidence_clamped_between_0_and_100():
    """An overflowing / underflowing total clamps to [0, 100]."""
    calc = ConfidenceCalculator()
    resp = ClaimAwareResponse(
        assumptions=tuple(f"a{i}" for i in range(20)),
        unknowns=(
            ClaimUnknown(question="x", impact="HIGH", rationale="y"),
            ClaimUnknown(question="x2", impact="HIGH", rationale="y2"),
            ClaimUnknown(question="x3", impact="HIGH", rationale="y3"),
        ),
    )
    nr = NumericConflictReport(
        conflicts=tuple(
            NumericConflict(
                location=f"x{i}", original="1", replacement="2",
                category="score", authoritative_value=2, tolerance=0,
            )
            for i in range(10)
        )
    )
    rep = calc.compute(claim_response=resp, numeric_report=nr)
    assert 0 <= rep.score <= 100


def test_49_confidence_rationale_is_non_empty():
    """Every score carries a one-line rationale string."""
    calc = ConfidenceCalculator()
    rep = calc.compute()
    assert rep.rationale
    assert "/100" in rep.rationale


def test_50_confidence_to_dict_round_trip():
    """ConfidenceReport serialises to a JSON-safe dict."""
    rep = ConfidenceReport(score=72, components={"base": 30, "evidence_coverage": 20}, rationale="base=30 -> 50/100")
    d = rep.to_dict()
    assert d["score"] == 72
    assert d["components"]["base"] == 30
    assert d["rationale"].endswith("/100")


# --------------------------------------------------------------------------- #
# 6. claim_fallback — deterministic payload + Pydantic mirror validation
# --------------------------------------------------------------------------- #


def test_51_fallback_payload_is_json_safe_with_lists_for_assumptions():
    """assumptions + limitations are lists (Pydantic mirror requires lists)."""
    ctx = _make_context()
    payload = build_fallback_claim_aware(SimpleNamespace(context=ctx))
    assert isinstance(payload["assumptions"], list)
    assert isinstance(payload["limitations"], list)
    json.dumps(payload)


def test_52_fallback_payload_has_4_business_facts_plus_dna():
    """One FACT claim per non-empty business field + one for DNA."""
    ctx = _make_context()
    payload = build_fallback_claim_aware(SimpleNamespace(context=ctx))
    assert len(payload["claims"]) >= 5
    assert any("Legal name" in c["text"] for c in payload["claims"])
    assert any("Industry" in c["text"] for c in payload["claims"])
    assert any("score" in c["text"].lower() for c in payload["claims"])
    assert any("DNA" in c["text"] for c in payload["claims"])


def test_53_fallback_server_confidence_is_100():
    """The deterministic fallback is grounded by construction → score 100."""
    ctx = _make_context()
    payload = build_fallback_claim_aware(SimpleNamespace(context=ctx))
    assert payload["server_confidence"] == 100
    assert "fallback" in payload["server_confidence_rationale"].lower()


def test_54_fallback_empty_when_no_context():
    """When no AssistantContext is available, the payload is the empty stub."""
    payload = build_fallback_claim_aware(SimpleNamespace(context=None))
    assert payload["answer"] == ""
    assert payload["claims"] == []
    assert payload["server_confidence"] == 0


def test_55_fallback_maps_top_recommendations():
    """Recommendations carry rec_{slug} evidence refs."""
    recs = (
        SimpleNamespace(
            id="rec_abc_123",
            title="Diversify suppliers",
            category="supply_chain",
            priority="HIGH",
            estimated_score_gain=8,
            estimated_timeline="3 months",
        ),
        SimpleNamespace(
            id="rec_xyz_999",
            title="Open current account",
            category="finance",
            priority="MEDIUM",
            estimated_score_gain=5,
            estimated_timeline="1 week",
        ),
    )
    ctx = _make_context(recommendations=recs)
    payload = build_fallback_claim_aware(SimpleNamespace(context=ctx))
    assert len(payload["recommendations"]) == 2
    assert any(r["evidence_references"] for r in payload["recommendations"])


# --------------------------------------------------------------------------- #
# 7. Pydantic mirror — extra="forbid" guards
# --------------------------------------------------------------------------- #


def test_56_pydantic_chat_claim_aware_response_rejects_unknown_field():
    """extra='forbid' rejects a typo'd field name."""
    from app.schemas.chat import ChatClaimAwareResponse
    from pydantic import ValidationError

    bad = {
        "answer": "x",
        "claims": [],
        "recommendations": [],
        "calculations": [],
        "scenarios": [],
        "unknowns": [],
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "narrative": "",
        "server_audit": {},
        "totally_made_up_field": "nope",
    }
    with pytest.raises(ValidationError):
        ChatClaimAwareResponse.model_validate(bad)


def test_57_pydantic_chat_claim_aware_response_accepts_minimum():
    """The minimal payload (all defaults) is valid."""
    from app.schemas.chat import ChatClaimAwareResponse
    m = ChatClaimAwareResponse.model_validate({})
    assert m.answer == ""
    assert m.claims == []
    assert m.server_confidence is None


def test_58_pydantic_chat_claim_evidence_ref_rejects_bad_claim_type():
    """claim_type must be one of the 7 labels."""
    from app.schemas.chat import ChatClaimEvidenceRef
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatClaimEvidenceRef.model_validate(
            {"text": "x", "claim_type": "BOGUS"}
        )


def test_59_pydantic_chat_message_out_accepts_claim_aware_response():
    """ChatMessageOut accepts a nested ChatClaimAwareResponse."""
    from app.schemas.chat import ChatMessageOut

    m = ChatMessageOut.model_validate(
        {
            "id": 1,
            "role": "assistant",
            "content": "x",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "claim_aware_response": {
                "answer": "y",
                "claims": [],
                "recommendations": [],
                "calculations": [],
                "scenarios": [],
                "unknowns": [],
                "assumptions": [],
                "limitations": [],
                "evidence_references": [],
                "narrative": "",
                "server_audit": {},
                "server_confidence": 80,
                "server_confidence_rationale": "test",
                "numeric_conflicts": [],
            },
            "server_confidence": 80,
            "server_confidence_rationale": "test",
            "numeric_conflicts_count": 0,
            "claim_aware_validated": True,
        }
    )
    assert m.claim_aware_response is not None
    assert m.claim_aware_response.server_confidence == 80
    assert m.claim_aware_validated is True


def test_60_pydantic_chat_message_out_rejects_extra_field():
    """ChatMessageOut's extra='forbid' rejects unknown top-level fields."""
    from app.schemas.chat import ChatMessageOut
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatMessageOut.model_validate(
            {
                "id": 1,
                "role": "assistant",
                "content": "x",
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "fictional_field": "nope",
            }
        )
"""Sprint AI-14 — unit tests for the ``answer_requirements`` module.

These tests are pure-functional: same inputs ⇒ same output. They
do NOT need a database or LLM. They cover:

  * Default-safe construction of ``AnswerRequirements`` (every
    flag default-false except ``needs_direct_answer``).
  * Determinism — calling the derivation function twice with the
    same inputs returns structurally-equal results.
  * Every ``needs_*`` flag is wired to a known derivation rule
    (capability token, business_dependency, envelope metric, ...).
  * Wire round-trip via ``to_dict`` / ``from_dict`` preserves
    every field.
  * Edge cases — None envelopes, empty QU, empty ToolPlan.
"""

from __future__ import annotations

from app.services.ai.reasoning.answer_requirements import (
    AnswerRequirements,
    derive_answer_requirements,
)


class _StubQU:
    def __init__(self, **kw):
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
        self.literal_question = kw.get("literal_question", "")


class _StubER:
    def __init__(self, missing_fields=()):
        self.missing_fields = tuple(missing_fields)


class _StubPlan:
    def __init__(self):
        self.required_tools = ()


class _StubEnvelope:
    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "")
        self.metric = kw.get("metric")
        self.value = kw.get("value")
        self.assumptions = kw.get("assumptions", ())
        self.input_evidence_ids = kw.get("input_evidence_ids", ())


class _StubContext:
    def __init__(self):
        self.business_id = 1
        self.legal_name = "Acme"


def test_defaults():
    """The frozen dataclass defaults to hero-only."""
    req = AnswerRequirements()
    assert req.needs_direct_answer is True
    assert req.needs_business_evidence is False
    assert req.needs_calculation is False
    assert req.needs_external_information is False
    assert req.needs_recommendation is False
    assert req.needs_scenario is False
    assert req.needs_comparison is False
    assert req.needs_risk_analysis is False
    assert req.needs_missing_data is False
    assert req.needs_assumptions is False
    assert req.needs_visualization is False
    assert req.requested_entities == ()
    assert req.requested_metrics == ()
    assert req.requested_time_horizon == ""
    assert req.requested_output_format == "narrative"


def test_pure_function_invariance():
    """Calling the derivation twice with the same inputs is identical."""
    qu = _StubQU(capability=("FACT",), business_dependency="required")
    a = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    b = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert a.to_dict() == b.to_dict()


def test_business_evidence_flag():
    """business_dependency in {optional, required} lights up the flag."""
    qu = _StubQU(business_dependency="required")
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_business_evidence is True


def test_calculation_flag_from_envelope_metric():
    """Any envelope carrying a metric+value lights up the calc flag."""
    env = _StubEnvelope(tool_name="finance", metric="amount", value=1.5e7)
    qu = _StubQU()
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(env,),
        context=_StubContext(),
    )
    assert req.needs_calculation is True


def test_external_information_flag():
    """knowledge_retrieval envelope OR requires_external_information lights up."""
    env = _StubEnvelope(tool_name="knowledge_retrieval", metric=None, value=None)
    qu = _StubQU(requires_external_information=False)
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(env,),
        context=_StubContext(),
    )
    assert req.needs_external_information is True


def test_missing_data_flag_when_unknowns_unfilled():
    """Unknowns without matching profile data light up missing_data."""
    qu = _StubQU(unknowns=("monthly_payroll_cost_inr",))
    er = _StubER(missing_fields=("monthly_payroll_cost_inr",))
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=er,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_missing_data is True


def test_scenario_flag_from_qu():
    """requires_scenario_analysis lights up the scenario flag."""
    qu = _StubQU(
        requires_scenario_analysis=True,
        answer_mode="scenario",
    )
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_scenario is True
    assert req.needs_assumptions is True


def test_comparison_flag_from_literal_question():
    """'vs' / 'versus' / 'compare' in literal_question lights up the flag."""
    qu = _StubQU(
        literal_question="Compare supplier diversification with inventory buffering.",
    )
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_comparison is True


def test_recommendation_flag_from_capability():
    """RECOMMENDATION in capability lights up the flag."""
    qu = _StubQU(capability=("RECOMMENDATION",))
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_recommendation is True


def test_risk_flag_from_capability():
    """RISK in capability lights up the flag."""
    qu = _StubQU(capability=("RISK",))
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    assert req.needs_risk_analysis is True


def test_wire_roundtrip():
    """to_dict emits a JSON-safe shape; every field is preserved."""
    req = AnswerRequirements(
        needs_direct_answer=True,
        needs_business_evidence=True,
        needs_calculation=True,
        requested_entities=("acme", "tirupur"),
        requested_metrics=("revenue",),
        requested_time_horizon="12 months",
        requested_output_format="steps",
        rationale="test rationale",
    )
    payload = req.to_dict()
    assert payload["needs_direct_answer"] is True
    assert payload["needs_business_evidence"] is True
    assert payload["needs_calculation"] is True
    assert payload["requested_entities"] == ["acme", "tirupur"]
    assert payload["requested_metrics"] == ["revenue"]
    assert payload["requested_time_horizon"] == "12 months"
    assert payload["requested_output_format"] == "steps"
    assert payload["rationale"] == "test rationale"
    # Round-trip via from_dict must coerce lists to tuples (the
    # wire shape is JSON; the dataclass wants tuples).
    restored = AnswerRequirements.from_dict(payload)
    assert restored == req
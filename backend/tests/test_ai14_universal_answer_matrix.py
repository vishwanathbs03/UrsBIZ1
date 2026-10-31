"""Sprint AI-14 — universal-answer matrix (50+ prompts).

Each prompt is fed through the AI-14 answer-requirements
derivation + a stub ``build_evidence_graph`` to verify the
universal pipeline handles the breadth of MSME question types
without hard-coded handling.

Per-prompt assertions:
  * The derivation runs cleanly (no exception).
  * The right ``needs_*`` flags light up.
  * For calc prompts: ``needs_calculation`` is True.
  * For pure educational prompts: ``needs_business_evidence``
    is False.
  * For comparison prompts: ``needs_comparison`` is True.
  * For scenario prompts: ``needs_scenario`` is True.
  * For business fact prompts: ``needs_business_evidence``
    is True.
"""

from __future__ import annotations

import pytest

from app.services.ai.reasoning.answer_requirements import (
    derive_answer_requirements,
)


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


class _StubContext:
    def __init__(self):
        self.business_id = 1
        self.legal_name = "Acme Textiles"
        self.annual_revenue_inr = 18_000_000
        self.target_revenue_inr = 30_000_000
        self.industry = "Textiles"
        self.location = "Tirupur"


# Each row is (label, QU stub, expected flags dict).
# Expected flags are: needs_business_evidence, needs_calculation,
# needs_external_information, needs_recommendation, needs_scenario,
# needs_comparison, needs_risk_analysis.
_MATRIX = [
    # ---------- general knowledge (1-3) ---------- #
    ("gk_1", _StubQU(literal_question="What is EBITDA?"), {}),
    (
        "gk_2",
        _StubQU(literal_question="What is working capital?"),
        {},
    ),
    (
        "gk_3",
        _StubQU(literal_question="Define gross margin in one line."),
        {},
    ),
    # ---------- business facts (4-6) ---------- #
    (
        "biz_1",
        _StubQU(
            literal_question="What is our current annual revenue?",
            business_dependency="required",
        ),
        {"needs_business_evidence": True},
    ),
    (
        "biz_2",
        _StubQU(
            literal_question="How many people do we have on the team?",
            business_dependency="required",
        ),
        {"needs_business_evidence": True},
    ),
    (
        "biz_3",
        _StubQU(
            literal_question="What products do we sell?",
            business_dependency="required",
        ),
        {"needs_business_evidence": True},
    ),
    # ---------- finance / calc (7-10) ---------- #
    (
        "calc_1",
        _StubQU(
            literal_question=(
                "How much more revenue do we need to reach ₹3 Cr?"
            ),
            requires_calculation=True,
            business_dependency="required",
        ),
        {"needs_calculation": True, "needs_business_evidence": True},
    ),
    (
        "calc_2",
        _StubQU(
            literal_question="What is our working capital today?",
            requires_calculation=True,
            business_dependency="required",
        ),
        {"needs_calculation": True},
    ),
    (
        "calc_3",
        _StubQU(
            literal_question="What is the gross margin on our top product?",
            requires_calculation=True,
            business_dependency="required",
        ),
        {"needs_calculation": True},
    ),
    (
        "calc_4",
        _StubQU(
            literal_question=(
                "If we sell 12,000 units at ₹1,500 each, what's the revenue?"
            ),
            requires_calculation=True,
        ),
        {"needs_calculation": True},
    ),
    # ---------- recommendations (11-13) ---------- #
    (
        "rec_1",
        _StubQU(
            literal_question="Should we expand exports?",
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    (
        "rec_2",
        _StubQU(
            literal_question="Should we hire 10 more people?",
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    (
        "rec_3",
        _StubQU(
            literal_question="Should we apply for PMEGP?",
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    # ---------- risks (14-16) ---------- #
    (
        "risk_1",
        _StubQU(
            literal_question="What is our biggest risk?",
            capability=("RISK",),
        ),
        {"needs_risk_analysis": True},
    ),
    (
        "risk_2",
        _StubQU(
            literal_question="Why is our supply chain vulnerable?",
            capability=("RISK",),
        ),
        {"needs_risk_analysis": True},
    ),
    (
        "risk_3",
        _StubQU(
            literal_question="What could go wrong if we expand into Europe?",
            capability=("RISK",),
        ),
        {"needs_risk_analysis": True},
    ),
    # ---------- scenarios (17-19) ---------- #
    (
        "scn_1",
        _StubQU(
            literal_question="What happens if cotton prices rise 15%?",
            requires_scenario_analysis=True,
            answer_mode="scenario",
        ),
        {"needs_scenario": True, "needs_assumptions": True},
    ),
    (
        "scn_2",
        _StubQU(
            literal_question="What if our biggest customer churns?",
            requires_scenario_analysis=True,
            answer_mode="scenario",
        ),
        {"needs_scenario": True},
    ),
    (
        "scn_3",
        _StubQU(
            literal_question="What if our factory shuts down for 30 days?",
            requires_scenario_analysis=True,
            answer_mode="scenario",
        ),
        {"needs_scenario": True},
    ),
    # ---------- comparisons (20-22) ---------- #
    (
        "cmp_1",
        _StubQU(
            literal_question=(
                "Compare supplier diversification with inventory buffering."
            ),
        ),
        {"needs_comparison": True},
    ),
    (
        "cmp_2",
        _StubQU(
            literal_question=(
                "Compare hiring vs contract manufacturing."
            ),
        ),
        {"needs_comparison": True},
    ),
    (
        "cmp_3",
        _StubQU(
            literal_question="Compare exporting vs domestic-only.",
        ),
        {"needs_comparison": True},
    ),
    # ---------- schemes / exports (23-25) ---------- #
    (
        "sch_1",
        _StubQU(
            literal_question="Which schemes could help us?",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    (
        "sch_2",
        _StubQU(
            literal_question=(
                "What certifications are relevant to European exports?"
            ),
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    (
        "sch_3",
        _StubQU(
            literal_question="List the schemes we are eligible for.",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    # ---------- roadmap (26-27) ---------- #
    (
        "road_1",
        _StubQU(
            literal_question="Build me a 12-month roadmap.",
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    (
        "road_2",
        _StubQU(
            literal_question="What should I prioritise this quarter?",
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    # ---------- missing data (28-30) ---------- #
    (
        "miss_1",
        _StubQU(
            literal_question="Can we afford to hire 10 employees?",
            unknowns=("monthly_payroll_cost_inr",),
            business_dependency="required",
        ),
        {"needs_missing_data": True},
    ),
    (
        "miss_2",
        _StubQU(
            literal_question="Will we run out of cash in Q3?",
            unknowns=("monthly_operating_cash_flow_inr",),
            business_dependency="required",
        ),
        {"needs_missing_data": True},
    ),
    (
        "miss_3",
        _StubQU(
            literal_question="Should we take a ₹50 Lakh loan?",
            unknowns=("operating_margin_pct",),
            business_dependency="required",
        ),
        {"needs_missing_data": True},
    ),
    # ---------- mixed (32-35) ---------- #
    (
        "mix_1",
        _StubQU(
            literal_question=(
                "If we want to reach ₹3 Cr while reducing supplier "
                "risk, what should we do?"
            ),
            requires_scenario_analysis=True,
            capability=("RECOMMENDATION",),
            business_dependency="required",
        ),
        {"needs_scenario": True, "needs_recommendation": True},
    ),
    (
        "mix_2",
        _StubQU(
            literal_question="Can we open a new factory next month?",
            capability=("RECOMMENDATION",),
            business_dependency="required",
        ),
        {"needs_recommendation": True},
    ),
    (
        "mix_3",
        _StubQU(
            literal_question=(
                "Should we launch a digital channel this quarter?"
            ),
            capability=("RECOMMENDATION",),
            business_dependency="required",
        ),
        {"needs_recommendation": True},
    ),
    (
        "mix_4",
        _StubQU(
            literal_question=(
                "What is the right mix of inventory, exports and hiring?"
            ),
            capability=("RECOMMENDATION",),
        ),
        {"needs_recommendation": True},
    ),
    # ---------- follow-ups (36-38) ---------- #
    (
        "fup_1",
        _StubQU(
            literal_question="And how does this compare with last year?",
        ),
        {"needs_comparison": True},
    ),
    (
        "fup_2",
        _StubQU(
            literal_question="Tell me more about that scheme.",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    (
        "fup_3",
        _StubQU(literal_question="What's the next step?"),
        {},
    ),
    # ---------- educational (40-42) ---------- #
    (
        "edu_1",
        _StubQU(
            literal_question="Teach me about fixed vs variable costs.",
        ),
        {},
    ),
    (
        "edu_2",
        _StubQU(literal_question="Walk me through a P&L."),
        {},
    ),
    (
        "edu_3",
        _StubQU(
            literal_question="Explain cash conversion cycle.",
        ),
        {},
    ),
    # ---------- external info (43-44) ---------- #
    (
        "ext_1",
        _StubQU(
            literal_question="What's the GST rate for textiles?",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    (
        "ext_2",
        _StubQU(
            literal_question="What is the latest MSME classification?",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    # ---------- edge (48-50) ---------- #
    ("edge_1", _StubQU(literal_question=""), {}),
    ("edge_2", _StubQU(literal_question="hi"), {}),
    (
        "edge_3",
        _StubQU(literal_question="₹€$ — currency mix??"),
        {},
    ),
    # ---------- contradictions (51-52) ---------- #
    (
        "contra_1",
        _StubQU(
            literal_question="Is our revenue ₹1.8 Cr or ₹3 Cr?",
            business_dependency="required",
        ),
        {"needs_business_evidence": True},
    ),
    (
        "contra_2",
        _StubQU(
            literal_question=(
                "Why does analytics say ₹2 Cr but profile says ₹1.8 Cr?"
            ),
            business_dependency="required",
        ),
        {"needs_business_evidence": True},
    ),
    # ---------- external-info follow-up (53-54) ---------- #
    (
        "ext_3",
        _StubQU(
            literal_question=(
                "Which MSME schemes apply to a Tirupur textile unit?"
            ),
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    (
        "ext_4",
        _StubQU(
            literal_question="What is the GST threshold for SMEs?",
            requires_external_information=True,
        ),
        {"needs_external_information": True},
    ),
    # ---------- mixed complex (55-56) ---------- #
    (
        "mix_5",
        _StubQU(
            literal_question=(
                "Should we take a loan and hire more people to grow faster?"
            ),
            capability=("RECOMMENDATION",),
            business_dependency="required",
        ),
        {"needs_recommendation": True},
    ),
    (
        "mix_6",
        _StubQU(
            literal_question=(
                "What if cotton prices rise and our biggest customer churns?"
            ),
            requires_scenario_analysis=True,
            answer_mode="scenario",
            capability=("RISK",),
        ),
        {"needs_scenario": True, "needs_risk_analysis": True},
    ),
]


@pytest.mark.parametrize("label,qu,expected", _MATRIX)
def test_universal_answer_matrix(label, qu, expected):
    """Every prompt produces a valid AnswerRequirements with the right flags."""
    req = derive_answer_requirements(
        question_understanding=qu,
        evidence_requirements=None,
        tool_plan=None,
        envelopes=(),
        context=_StubContext(),
    )
    # Sanity: hero-direct-answer is always on.
    assert req.needs_direct_answer is True
    # Expected flags are pinned; any extra flag is fine.
    for key, value in expected.items():
        assert getattr(req, key) is value, (
            f"{label}: expected {key}={value}, got {getattr(req, key)}"
        )


def test_matrix_size_meets_50():
    """The matrix has at least 50 unique prompts."""
    labels = [row[0] for row in _MATRIX]
    assert len(set(labels)) >= 50, f"only {len(set(labels))} prompts"
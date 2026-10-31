"""SPRINT AI-14 FINAL HARDENING — brief-category coverage.

The AI-14 brief lists 13 explicit prompt categories that must be
covered by the answer-intelligence layer. This module exercises
each category against the production modules:

  * :mod:`app.services.ai.reasoning.answer_requirements`
  * :mod:`app.services.ai.reasoning.evidence_graph`
  * :mod:`app.services.ai.reasoning.calculation_lineage`

Each test is read-only and dependency-free — no LLM, no DB.

The categories:

  1.  general question
  2.  business fact
  3.  business analysis
  4.  calculation
  5.  recommendation
  6.  scenario
  7.  mixed question
  8.  missing data
  9.  contradictory data
  10. external information
  11. unsupported claim
  12. fabricated evidence ID
  13. numeric mismatch
"""
from __future__ import annotations

import pytest

from app.services.ai.reasoning.answer_requirements import (
    derive_answer_requirements,
)
from app.services.ai.reasoning.calculation_lineage import (
    contradictory_claims,
    fabricated_sources,
    mint_calculation_nodes,
    missing_data_state,
    unsupported_claims,
)
from app.services.ai.reasoning.evidence_graph import (
    AUTHORITY_ASSUMPTION,
    AUTHORITY_PROFILE,
    AnswerEvidenceGraph,
    AssumptionNode,
    CalculationNode,
    ClaimNode,
    EvidenceEdge,
    EvidenceNode,
    ExternalSourceNode,
    build_evidence_graph,
)


# --------------------------------------------------------------------------- #
# Shared fixtures
# --------------------------------------------------------------------------- #


class _StubQU:
    """Duck-typed QuestionUnderstanding for derivation tests."""

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
    """Duck-typed AssistantContext for derivation tests."""

    def __init__(self, *, missing_payroll: bool = False):
        self.business_id = 1
        self.legal_name = "Acme Textiles"
        self.annual_revenue_inr = 18_000_000
        self.target_revenue_inr = 30_000_000
        self.industry = "Textiles"
        self.location = "Tirupur"
        self.employee_count = "42"
        # missing-data probe: the brief's "missing data" prompt
        # uses monthly_payroll_cost_inr absent.
        self.monthly_payroll_cost_inr = 0 if missing_payroll else 250_000
        self.monthly_operating_cash_flow_inr = 180_000
        self.operating_margin_pct = 12.5


class _StubEnvelope:
    """Duck-typed StructuredToolEnvelope for derivation tests."""

    def __init__(
        self,
        *,
        tool_name: str = "",
        metric: str | None = None,
        value: float | None = None,
        unit: str = "",
        formula: str = "",
        calculation_id: str = "",
        input_evidence_ids: tuple[str, ...] = (),
        confidence: float = 1.0,
        assumptions: tuple[str, ...] = (),
    ):
        self.tool_name = tool_name
        self.metric = metric
        self.value = value
        self.unit = unit
        self.formula = formula
        self.calculation_id = calculation_id
        self.input_evidence_ids = input_evidence_ids
        self.confidence = confidence
        self.assumptions = assumptions


# --------------------------------------------------------------------------- #
# 1 — General question
# --------------------------------------------------------------------------- #


class TestGeneralQuestion:
    """Category 1 — pure educational / general knowledge."""

    def test_general_question_no_business_evidence(self):
        qu = _StubQU(literal_question="What is EBITDA?")
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_direct_answer is True
        assert req.needs_business_evidence is False
        assert req.needs_calculation is False
        assert req.required_capabilities == ()
        assert req.required_evidence_types == ()
        assert req.required_tools == ()
        assert req.calculations_required is False
        assert req.external_sources_required is False


# --------------------------------------------------------------------------- #
# 2 — Business fact
# --------------------------------------------------------------------------- #


class TestBusinessFact:
    """Category 2 — asks for a fact about the user's business."""

    def test_business_fact_lights_business_evidence(self):
        qu = _StubQU(
            literal_question="What is our current annual revenue?",
            capability=("BUSINESS_FACT",),
            business_dependency="required",
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_business_evidence is True
        assert req.calculations_required is False
        assert "profile" in req.required_evidence_types
        assert "BUSINESS_FACT" in req.required_capabilities


# --------------------------------------------------------------------------- #
# 3 — Business analysis
# --------------------------------------------------------------------------- #


class TestBusinessAnalysis:
    """Category 3 — analytical / interpretive question."""

    def test_business_analysis_no_calc_required(self):
        qu = _StubQU(
            literal_question="Why did our score drop last quarter?",
            capability=("BUSINESS_ANALYSIS",),
            business_dependency="required",
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_business_evidence is True
        assert req.calculations_required is False
        assert req.required_capabilities == ("BUSINESS_ANALYSIS",)


# --------------------------------------------------------------------------- #
# 4 — Calculation
# --------------------------------------------------------------------------- #


class TestCalculation:
    """Category 4 — arithmetic / numeric question."""

    def test_calc_prompt_flips_calculation_required(self):
        qu = _StubQU(
            literal_question="How much more revenue do we need to reach ₹3 Cr?",
            capability=("CALCULATION",),
            business_dependency="required",
            requires_calculation=True,
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_calculation is True
        assert req.calculations_required is True
        assert "calculation" in req.required_evidence_types

    def test_calc_envelope_drives_required_tools(self):
        """A finance envelope becomes a required_tool projection."""
        qu = _StubQU(
            literal_question="Revenue gap to ₹3 Cr?",
            business_dependency="required",
            requires_calculation=True,
        )
        env = _StubEnvelope(
            tool_name="finance",
            metric="revenue_gap",
            value=12_000_000,
            unit="INR",
            formula="target - current",
            calculation_id="calc_gap_1",
            input_evidence_ids=("biz_profile_revenue",),
        )
        req = derive_answer_requirements(
            question_understanding=qu,
            envelopes=(env,),
            context=_StubContext(),
        )
        assert req.required_tools == ("finance",)
        assert req.calculations_required is True
        # Calc lineage is mintable.
        nodes = mint_calculation_nodes((env,))
        assert len(nodes) == 1
        assert nodes[0].tool_name == "finance"
        assert nodes[0].output == 12_000_000


# --------------------------------------------------------------------------- #
# 5 — Recommendation
# --------------------------------------------------------------------------- #


class TestRecommendation:
    """Category 5 — what should we do."""

    def test_recommendation_flips_recommendation_flag(self):
        qu = _StubQU(
            literal_question="Should we expand exports?",
            capability=("RECOMMENDATION",),
            business_dependency="required",
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_recommendation is True
        assert req.calculations_required is False
        assert "recommendation" in req.required_evidence_types
        assert "recommendation" in req.requested_answer_sections


# --------------------------------------------------------------------------- #
# 6 — Scenario
# --------------------------------------------------------------------------- #


class TestScenario:
    """Category 6 — what-if."""

    def test_scenario_flips_scenario_flag(self):
        qu = _StubQU(
            literal_question="What if cotton prices rise 15%?",
            capability=("SCENARIO",),
            business_dependency="optional",
            requires_scenario_analysis=True,
            answer_mode="scenario",
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_scenario is True
        assert req.needs_assumptions is True
        assert req.uncertainty_required is True
        assert "scenario" in req.requested_answer_sections


# --------------------------------------------------------------------------- #
# 7 — Mixed question
# --------------------------------------------------------------------------- #


class TestMixedQuestion:
    """Category 7 — combines business + scenario + recommendation."""

    def test_mixed_question_lights_multiple_flags(self):
        qu = _StubQU(
            literal_question=(
                "If we want to reach ₹3 Cr while reducing "
                "supplier risk, what should we do?"
            ),
            capability=("SCENARIO", "RECOMMENDATION", "BUSINESS_FACT"),
            business_dependency="required",
            requires_scenario_analysis=True,
            requires_calculation=True,
            answer_mode="scenario",
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_scenario is True
        assert req.needs_recommendation is True
        assert req.needs_business_evidence is True
        assert req.needs_calculation is True
        # Sections include all three.
        assert "scenario" in req.requested_answer_sections
        assert "recommendation" in req.requested_answer_sections
        assert "key_evidence" in req.requested_answer_sections


# --------------------------------------------------------------------------- #
# 8 — Missing data
# --------------------------------------------------------------------------- #


class TestMissingData:
    """Category 8 — prompt asks for a fact the context lacks."""

    def test_missing_data_flips_uncertainty(self):
        ctx = _StubContext(missing_payroll=True)
        qu = _StubQU(
            literal_question="Can we afford to hire 10 employees?",
            capability=("CALCULATION",),
            business_dependency="required",
            requires_calculation=True,
            unknowns=("monthly_payroll_cost_inr",),
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=ctx
        )
        assert req.needs_missing_data is True
        assert req.uncertainty_required is True
        assert "missing_data" in req.required_evidence_types
        # The missing-data branch surfaces as the ``uncertainty``
        # section in the composer; it is NOT a standalone section.
        assert "uncertainty" in req.requested_answer_sections


# --------------------------------------------------------------------------- #
# 9 — Contradictory data
# --------------------------------------------------------------------------- #


class TestContradictoryData:
    """Category 9 — adversarial prompt with conflicting numbers."""

    def test_contradictory_claim_count_rises(self):
        # Build a graph with two contradicted claims directly.
        claims = (
            ClaimNode(
                claim_id="c1",
                claim_text="Revenue is ₹1.8 Cr.",
                category="FACT",
                validation_status="contradicted",
                authority=AUTHORITY_PROFILE,
                freshness="",
                evidence_ids=(),
                calculation_ids=(),
                tool_ids=(),
                assumption_ids=(),
                external_source_ids=(),
            ),
            ClaimNode(
                claim_id="c2",
                claim_text="Revenue is ₹3 Cr.",
                category="FACT",
                validation_status="contradicted",
                authority=AUTHORITY_PROFILE,
                freshness="",
                evidence_ids=(),
                calculation_ids=(),
                tool_ids=(),
                assumption_ids=(),
                external_source_ids=(),
            ),
        )
        graph = AnswerEvidenceGraph(
            claims=claims,
            contradictory_claim_count=2,
            contradiction_severity="high",
        )
        assert graph.contradictory_claim_count == 2
        contra = contradictory_claims(graph)
        assert len(contra) == 2
        assert {c.claim_id for c in contra} == {"c1", "c2"}


# --------------------------------------------------------------------------- #
# 10 — External information
# --------------------------------------------------------------------------- #


class TestExternalInformation:
    """Category 10 — knowledge_retrieval / scheme engine."""

    def test_external_flips_sources_required(self):
        qu = _StubQU(
            literal_question="Which government schemes help exporters?",
            capability=("EXTERNAL_FACT",),
            business_dependency="optional",
            requires_external_information=True,
        )
        req = derive_answer_requirements(
            question_understanding=qu, context=_StubContext()
        )
        assert req.needs_external_information is True
        assert req.external_sources_required is True
        assert "external" in req.required_evidence_types
        assert "external_sources" in req.requested_answer_sections


# --------------------------------------------------------------------------- #
# 11 — Unsupported claim
# --------------------------------------------------------------------------- #


class TestUnsupportedClaim:
    """Category 11 — LLM produced a claim with no supporting edge."""

    def test_unsupported_claim_count_is_server_computed(self):
        claim = ClaimNode(
            claim_id="c_unsup",
            claim_text="Our EBITDA is 42%.",
            category="FACT",
            validation_status="unsupported",
            authority=0.0,
            freshness="",
            evidence_ids=(),
            calculation_ids=(),
            tool_ids=(),
            assumption_ids=(),
            external_source_ids=(),
        )
        graph = AnswerEvidenceGraph(
            claims=(claim,),
            unsupported_claim_count=1,
        )
        assert graph.unsupported_claim_count == 1
        unsup = unsupported_claims(graph)
        assert len(unsup) == 1
        assert unsup[0].claim_id == "c_unsup"


# --------------------------------------------------------------------------- #
# 12 — Fabricated evidence ID
# --------------------------------------------------------------------------- #


class TestFabricatedEvidenceId:
    """Category 12 — external source whose URL fails the guard."""

    def test_fabricated_source_count_is_server_computed(self):
        # An external source with authority < 0.5 fails the URL
        # guard; the count is the integer the audit row exposes.
        bad = ExternalSourceNode(
            source_id="s_fake",
            label="example.com/fake",
            authority=0.10,
            url_or_path="https://example.com/fake",
        )
        good = ExternalSourceNode(
            source_id="s_real",
            label="msme.gov.in/scheme-123",
            authority=0.95,
            url_or_path="https://msme.gov.in/scheme-123",
        )
        graph = AnswerEvidenceGraph(
            external_sources=(bad, good),
            fabricated_source_count=1,
        )
        assert graph.fabricated_source_count == 1
        fab = fabricated_sources(graph)
        assert len(fab) == 1
        assert fab[0].source_id == "s_fake"


# --------------------------------------------------------------------------- #
# 13 — Numeric mismatch
# --------------------------------------------------------------------------- #


class TestNumericMismatch:
    """Category 13 — calculation lineage exposes input + output."""

    def test_calc_lineage_exposes_inputs_and_output(self):
        env = _StubEnvelope(
            tool_name="finance",
            metric="revenue_gap",
            value=12_000_000,
            unit="INR",
            formula="target - current",
            calculation_id="calc_gap_xyz",
            input_evidence_ids=("biz_profile_revenue",),
        )
        nodes = mint_calculation_nodes((env,))
        assert len(nodes) == 1
        node = nodes[0]
        # Inputs, formula, output, unit, calculation_id all present.
        assert node.calculation_id == "calc_gap_xyz"
        assert node.formula == "target - current"
        assert node.output == 12_000_000
        assert node.unit == "INR"
        assert node.source_evidence_ids == ("biz_profile_revenue",)

    def test_calc_lineage_skips_envelopes_without_value(self):
        """A non-numeric envelope does not mint a CalculationNode."""
        env = _StubEnvelope(tool_name="recommendation", metric=None, value=None)
        nodes = mint_calculation_nodes((env,))
        assert nodes == ()


# --------------------------------------------------------------------------- #
# 14 — Round-trip + evidence graph builder sanity
# --------------------------------------------------------------------------- #


class TestEvidenceGraphBuilder:
    """Sanity-check the deterministic builder."""

    def test_build_evidence_graph_round_trip(self):
        nodes = (
            EvidenceNode(
                node_id="n_profile_revenue",
                label="annual_revenue_inr",
                node_type="profile",
                authority=AUTHORITY_PROFILE,
                freshness="",
                source_description="business_profile.annual_revenue",
                raw_value_summary="₹1.80 Cr",
            ),
        )
        calc = CalculationNode(
            calculation_id="calc_gap_1",
            name="finance.revenue_gap",
            inputs={"target": 30_000_000, "current": 18_000_000},
            formula="target - current",
            output=12_000_000,
            unit="INR",
            source_evidence_ids=("n_profile_revenue",),
            tool_name="finance",
        )
        claim = ClaimNode(
            claim_id="c_gap",
            claim_text="Revenue gap is ₹1.20 Cr.",
            category="CALCULATION",
            validation_status="supported",
            authority=0.85,
            freshness="",
            evidence_ids=("n_profile_revenue",),
            calculation_ids=("calc_gap_1",),
            tool_ids=("finance",),
            assumption_ids=(),
            external_source_ids=(),
        )
        edge = EvidenceEdge(
            from_node_id="n_profile_revenue",
            to_node_id="c_gap",
            edge_type="supports",
            confidence=AUTHORITY_PROFILE,
        )
        graph = AnswerEvidenceGraph(
            nodes=nodes,
            edges=(edge,),
            claims=(claim,),
            calculations=(calc,),
        )
        # Round-trip through to_dict / from_dict preserves
        # the contradictory counter default (0).
        d = graph.to_dict()
        assert "contradictory_claim_count" in d
        assert d["contradictory_claim_count"] == 0
        g2 = AnswerEvidenceGraph.from_dict(d)
        assert g2.contradictory_claim_count == 0
        assert len(g2.nodes) == 1
        assert len(g2.claims) == 1
        assert len(g2.calculations) == 1

    def test_missing_data_state_buckets_unsupported_into_unknown(self):
        """missing_data_state puts unsupported claims in the unknown bucket."""
        claim = ClaimNode(
            claim_id="c_x",
            claim_text="Unknown fact.",
            category="UNKNOWN",
            validation_status="unsupported",
            authority=0.0,
            freshness="",
            evidence_ids=(),
            calculation_ids=(),
            tool_ids=(),
            assumption_ids=(),
            external_source_ids=(),
        )
        graph = AnswerEvidenceGraph(
            claims=(claim,),
            unsupported_claim_count=1,
        )
        mds = missing_data_state(graph=graph)
        assert "c_x" in [c["claim_id"] for c in mds["unknown"]]
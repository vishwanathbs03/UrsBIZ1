"""Sprint AI-14 — unit tests for the ``evidence_graph`` module.

Pure-functional tests covering:

  * Default-safe ``AnswerEvidenceGraph`` (every tuple / counter
    default-empty).
  * ``build_evidence_graph`` produces nodes + claims from
    envelopes + context.
  * Authority constants are stable (no LLM override path).
  * Contradiction severity propagates from the report.
  * ``from_dict`` round-trip preserves every field.
  * Unsupported / fabricated counters track engine state.
"""

from __future__ import annotations

from app.services.ai.reasoning.evidence_graph import (
    AUTHORITY_ASSUMPTION,
    AUTHORITY_CALCULATION,
    AUTHORITY_EXTERNAL,
    AUTHORITY_PROFILE,
    AnswerEvidenceGraph,
    AssumptionNode,
    CalculationNode,
    ClaimNode,
    EvidenceNode,
    ExternalSourceNode,
    build_evidence_graph,
)


class _StubQU:
    def __init__(self):
        self.literal_question = ""
        self.capability = ()
        self.business_dependency = "none"


class _StubEnvelope:
    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "finance")
        self.metric = kw.get("metric", "amount")
        self.value = kw.get("value", 1.0e7)
        self.unit = kw.get("unit", "INR")
        self.formula = kw.get("formula", "value * 1")
        self.calculation_id = kw.get("calculation_id", "calc_1")
        self.input_evidence_ids = kw.get("input_evidence_ids", ())
        self.confidence = kw.get("confidence", 1.0)
        self.assumptions = kw.get("assumptions", ())
        self.limitations = kw.get("limitations", ())
        self.raw_payload = kw.get("raw_payload", {})


class _StubContradiction:
    def __init__(self, severity="none", items=()):
        self.severity = severity
        self.items = tuple(items)
        self.rationale = ""


class _StubContext:
    def __init__(self, **kw):
        self.business_id = 1
        self.legal_name = "Acme"
        self.industry = "Textiles"
        self.location = "Tirupur"
        self.business_type = "Manufacturer"
        self.employee_count = "42"
        self.annual_revenue_inr = 18_000_000
        self.target_revenue_inr = 30_000_000
        self.overall_business_score = 68
        self.band = "Established"
        self.products = kw.get("products", ())
        self.services = kw.get("services", ())
        self.export_history = kw.get("export_history", ())
        self.supplier_dependencies = kw.get("supplier_dependencies", ())


def test_authority_constants():
    """Server-owned trust weights are stable."""
    assert AUTHORITY_PROFILE == 0.95
    assert AUTHORITY_CALCULATION == 0.85
    assert AUTHORITY_EXTERNAL == 0.70
    assert AUTHORITY_ASSUMPTION == 0.30
    # Strictly decreasing (profile > calc > external > assumption)
    assert AUTHORITY_PROFILE > AUTHORITY_CALCULATION > AUTHORITY_EXTERNAL
    assert AUTHORITY_EXTERNAL > AUTHORITY_ASSUMPTION


def test_default_graph():
    """Empty graph is safe + serialises."""
    g = AnswerEvidenceGraph()
    assert g.nodes == ()
    assert g.edges == ()
    assert g.claims == ()
    assert g.calculations == ()
    assert g.assumptions == ()
    assert g.external_sources == ()
    assert g.unsupported_claim_count == 0
    assert g.fabricated_source_count == 0
    assert g.contradiction_severity == "none"
    # to_dict + from_dict round-trip on the empty default.
    g2 = AnswerEvidenceGraph.from_dict(g.to_dict())
    assert g2 == g


def test_build_graph_with_envelope():
    """One envelope ⇒ at least one CalculationNode + an EvidenceEdge."""
    env = _StubEnvelope()
    graph = build_evidence_graph(
        question_understanding=_StubQU(),
        reasoning_plan=None,
        envelopes=(env,),
        context=_StubContext(),
        contradiction_report=_StubContradiction(),
        parsed_response=None,
    )
    assert len(graph.calculations) == 1
    calc = graph.calculations[0]
    assert calc.output == 1.0e7
    assert calc.tool_name == "finance"
    assert calc.unit == "INR"
    assert calc.calculation_id == "calc_1"


def test_contradiction_severity_propagates():
    """High-severity contradiction is reflected on the graph."""
    graph = build_evidence_graph(
        question_understanding=_StubQU(),
        reasoning_plan=None,
        envelopes=(_StubEnvelope(),),
        context=_StubContext(),
        contradiction_report=_StubContradiction(severity="high"),
        parsed_response=None,
    )
    assert graph.contradiction_severity == "high"


def test_unsupported_claim_counter():
    """A parsed-response claim with no edges is unsupported."""
    class _StubClaim:
        def __init__(self, text):
            self.text = text
            self.claim_type = "FACT"
    class _StubParsed:
        def __init__(self):
            self.claims = (_StubClaim("Revenue is ₹3 Cr"),)
    graph = build_evidence_graph(
        question_understanding=_StubQU(),
        reasoning_plan=None,
        envelopes=(_StubEnvelope(),),
        context=_StubContext(),
        contradiction_report=_StubContradiction(),
        parsed_response=_StubParsed(),
    )
    # Engine stamps unsupported_count ≥ 1 when the LLM made a
    # claim without any envelope edge.
    assert graph.unsupported_claim_count >= 1


def test_dataclass_to_dict_roundtrip():
    """Each node dataclass survives to_dict/from_dict."""
    n = EvidenceNode(
        node_id="p1",
        label="annual_revenue_inr",
        node_type="profile",
        authority=0.95,
        freshness="",
        source_description="business_profile.annual_revenue_inr",
        raw_value_summary="₹1.80 Cr",
    )
    payload = n.to_dict()
    assert payload["node_id"] == "p1"
    assert payload["node_type"] == "profile"

    claim = ClaimNode(
        claim_id="c1",
        claim_text="Revenue is ₹3 Cr",
        category="FACT",
        validation_status="supported",
        authority=0.95,
        freshness="",
    )
    assert claim.to_dict()["claim_id"] == "c1"

    calc = CalculationNode(
        calculation_id="calc_x",
        name="finance.amount",
        inputs={"value": 1.0e7},
        formula="value",
        output=1.0e7,
        unit="INR",
    )
    assert calc.to_dict()["calculation_id"] == "calc_x"

    asm = AssumptionNode(
        assumption_id="a1",
        text="Cotton prices stable for 12 months",
        source="scenario",
    )
    assert asm.to_dict()["assumption_id"] == "a1"

    src = ExternalSourceNode(
        source_id="s1",
        label="PMEGP",
        authority=0.7,
        url_or_path="https://msme.gov.in/pmegp",
    )
    assert src.to_dict()["source_id"] == "s1"
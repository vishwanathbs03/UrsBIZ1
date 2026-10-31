"""Sprint AI-14 — unit tests for ``calculation_lineage``.

Covers:
  * ``mint_calculation_nodes`` preserves inputs / formula /
    output / unit / source / calculation_id.
  * Skips envelopes that have no metric or no value.
  * Multiple envelopes produce N distinct CalculationNodes
    (no silent truncation).
  * ``missing_data_state`` buckets the graph's claims into
    known / derived / estimated / unknown.
  * ``unsupported_claims`` / ``fabricated_sources`` return the
    right tuples.
"""

from __future__ import annotations

from app.services.ai.reasoning.calculation_lineage import (
    calculation_lineage_dicts,
    fabricated_sources,
    mint_calculation_nodes,
    missing_data_state,
    unsupported_claims,
)
from app.services.ai.reasoning.evidence_graph import (
    AnswerEvidenceGraph,
    ClaimNode,
    ExternalSourceNode,
)


class _Env:
    def __init__(self, **kw):
        self.tool_name = kw.get("tool_name", "finance")
        self.metric = kw.get("metric", "amount")
        self.value = kw.get("value", 1.0e7)
        self.unit = kw.get("unit", "INR")
        self.formula = kw.get("formula", "value")
        self.calculation_id = kw.get("calculation_id", "")
        self.input_evidence_ids = kw.get("input_evidence_ids", ())
        self.confidence = kw.get("confidence", 1.0)


def test_mint_preserves_lineage():
    """Each CalculationNode carries the envelope's lineage verbatim."""
    env = _Env(
        tool_name="finance",
        metric="amount",
        value=1.2e7,
        unit="INR",
        formula="revenue * 1",
        calculation_id="calc_abc",
        input_evidence_ids=("p_revenue",),
    )
    nodes = mint_calculation_nodes((env,))
    assert len(nodes) == 1
    n = nodes[0]
    assert n.tool_name == "finance"
    assert n.output == 1.2e7
    assert n.unit == "INR"
    assert n.formula == "revenue * 1"
    assert n.calculation_id == "calc_abc"
    assert "p_revenue" in n.source_evidence_ids


def test_mint_skips_incomplete_envelopes():
    """Envelopes without metric OR without value are skipped silently."""
    incomplete = _Env(metric=None, value=None)
    complete = _Env(metric="amount", value=1.0e6, calculation_id="c1")
    nodes = mint_calculation_nodes((incomplete, complete))
    assert len(nodes) == 1
    assert nodes[0].calculation_id == "c1"


def test_mint_multiple_envelopes_produces_multiple_nodes():
    """No silent truncation across many envelopes."""
    envs = tuple(
        _Env(
            metric=f"m{i}",
            value=float(i + 1),
            calculation_id=f"c{i}",
        )
        for i in range(5)
    )
    nodes = mint_calculation_nodes(envs)
    assert len(nodes) == 5
    calc_ids = {n.calculation_id for n in nodes}
    assert calc_ids == {f"c{i}" for i in range(5)}


def test_calculation_lineage_dicts_wire_shape():
    """The wire-shape list mirrors the dataclass."""
    env = _Env(metric="amount", value=42.0, calculation_id="c1")
    out = calculation_lineage_dicts((env,))
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["calculation_id"] == "c1"
    assert out[0]["output"] == 42.0


def test_missing_data_state_buckets():
    """Unsupported claims fall into the 'unknown' bucket."""
    claims = (
        ClaimNode(
            claim_id="c1",
            claim_text="Revenue is ₹3 Cr",
            category="FACT",
            validation_status="unsupported",
            authority=0.5,
            freshness="",
        ),
        ClaimNode(
            claim_id="c2",
            claim_text="Growth = 12%",
            category="CALCULATION",
            validation_status="supported",
            authority=0.85,
            freshness="",
        ),
    )
    graph = AnswerEvidenceGraph(claims=claims)
    state = missing_data_state(graph=graph, proactive_rows=())
    assert "c1" in {c["claim_id"] for c in state["unknown"]}
    assert "c2" in {c["claim_id"] for c in state["derived"]}


def test_unsupported_claims_accessor():
    """Returns the validation_status == 'unsupported' subset."""
    supported = ClaimNode(
        claim_id="s1",
        claim_text="supported",
        category="FACT",
        validation_status="supported",
        authority=0.9,
        freshness="",
    )
    unsupported = ClaimNode(
        claim_id="u1",
        claim_text="unsupported",
        category="FACT",
        validation_status="unsupported",
        authority=0.0,
        freshness="",
    )
    graph = AnswerEvidenceGraph(claims=(supported, unsupported))
    out = unsupported_claims(graph)
    assert len(out) == 1
    assert out[0].claim_id == "u1"


def test_fabricated_sources_accessor():
    """Sources with authority < 0.5 are flagged as fabricated."""
    good = ExternalSourceNode(
        source_id="s1", label="PMEGP", authority=0.7
    )
    bad = ExternalSourceNode(
        source_id="s2", label="Random", authority=0.3
    )
    graph = AnswerEvidenceGraph(external_sources=(good, bad))
    out = fabricated_sources(graph)
    assert len(out) == 1
    assert out[0].source_id == "s2"
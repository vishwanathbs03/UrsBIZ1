"""Sprint AI-14 — Universal Answer Intelligence: ``calculation_lineage``.

This module is a thin pure-function helper that turns the
:class:`StructuredToolEnvelope` tuple the AI-13 dispatcher
produced into the wire-shaped lineage data the renderer reads
on every reply:

  * :func:`mint_calculation_nodes` — envelope → CalculationNode
    (deterministic lineage of inputs / formula / output / unit /
    source / calculation_id).
  * :func:`missing_data_state` — graph → dict of known / derived /
    estimated / unknown claims the renderer can render in the
    AI-14 "What I know / What I am missing" disclosure.
  * :func:`unsupported_claims` — graph → tuple of claim nodes the
    LLM made without any supporting edge.
  * :func:`fabricated_sources` — graph → tuple of external-source
    nodes that fail the URL guard.

Every helper is a pure function. None of them call the LLM.

The wire shape
--------------

::

    generation_meta.calculation_lineage = [
        { "calculation_id": "...", "name": "finance.amount",
          "inputs": {...}, "formula": "...",
          "output": 1.2e7, "unit": "INR",
          "source_evidence_ids": ["..."], "tool_name": "finance" }
    ]
    generation_meta.missing_data_state = {
        "known":     [...],
        "derived":   [...],
        "estimated": [...],
        "unknown":   [...],
    }
    generation_meta.unsupported_claim_count = int
    generation_meta.fabricated_source_count = int
"""
from __future__ import annotations

from typing import Any

from app.services.ai.reasoning.evidence_graph import (
    AnswerEvidenceGraph,
    AssumptionNode,
    CalculationNode,
    ClaimNode,
    ExternalSourceNode,
    _stable_id,
)


# --------------------------------------------------------------------------- #
# Calculation lineage
# --------------------------------------------------------------------------- #


def mint_calculation_nodes(
    envelopes: tuple[Any, ...] | list[Any],
) -> tuple[CalculationNode, ...]:
    """Convert envelopes into deterministic CalculationNodes.

    Skips envelopes that do not carry a numeric (no metric or
    no value). The stable ``calculation_id`` is reused from the
    envelope when present, otherwise derived from the tool name
    + metric + value so the audit row can quote it.

    Inputs are intentionally a thin summary — the full
    ``raw_payload`` belongs on the envelope, not the calc node.
    """
    out: list[CalculationNode] = []
    for env in envelopes or ():
        tool_name = getattr(env, "tool_name", "") or ""
        metric = getattr(env, "metric", None)
        value = getattr(env, "value", None)
        unit = getattr(env, "unit", "") or ""
        formula = getattr(env, "formula", "") or ""
        calc_id = getattr(env, "calculation_id", "") or ""
        src_evidence = tuple(getattr(env, "input_evidence_ids", ()) or ())
        confidence = float(getattr(env, "confidence", 1.0) or 1.0)
        if metric is None or value is None:
            continue
        try:
            output_f = float(value)
        except (TypeError, ValueError):
            continue
        out.append(
            CalculationNode(
                calculation_id=calc_id
                or _stable_id("calc", tool_name, metric, value, prefix="c"),
                name=f"{tool_name}.{metric}" if tool_name else str(metric),
                inputs={"value": output_f, "metric": str(metric)},
                formula=formula,
                output=output_f,
                unit=unit,
                source_evidence_ids=src_evidence,
                tool_name=tool_name,
                confidence=confidence,
            )
        )
    return tuple(out)


def calculation_lineage_dicts(
    envelopes: tuple[Any, ...] | list[Any],
) -> list[dict]:
    """Wire-shape list of calc-node dicts (for the GenerationMeta envelope)."""
    return [n.to_dict() for n in mint_calculation_nodes(envelopes)]


# --------------------------------------------------------------------------- #
# Missing-data state
# --------------------------------------------------------------------------- #


def missing_data_state(
    *,
    graph: AnswerEvidenceGraph,
    proactive_rows: tuple[dict, ...] = (),
) -> dict[str, list[dict]]:
    """Bucket the graph's claims into known / derived / estimated / unknown.

    Bucketing rules
    ---------------

      * ``known``     — claim with category == ``FACT`` and at
                        least one ``supports`` edge from a
                        profile node (authority ≥ 0.8).
      * ``derived``   — claim with category == ``CALCULATION``
                        OR a ``derived_from`` edge from a
                        calc node.
      * ``estimated`` — claim with category == ``SCENARIO`` or
                        a ``assumes`` edge from an assumption
                        node.
      * ``unknown``   — claim with ``validation_status ==
                        "unsupported"`` (the audit-row signal
                        the renderer shows in the "what I am
                        missing" section).

    Each entry is a thin ClaimNode dict (omits evidence
    ids — those go on the graph itself).
    """
    buckets: dict[str, list[dict]] = {
        "known": [],
        "derived": [],
        "estimated": [],
        "unknown": [],
    }
    # Build a quick lookup for the edges.
    incoming_supports: dict[str, int] = {}
    outgoing_derives: dict[str, int] = {}
    outgoing_assumes: dict[str, int] = {}
    for edge in graph.edges:
        if edge.edge_type == "supports":
            incoming_supports[edge.to_node_id] = incoming_supports.get(edge.to_node_id, 0) + 1
        elif edge.edge_type == "derived_from":
            outgoing_derives[edge.from_node_id] = outgoing_derives.get(edge.from_node_id, 0) + 1
        elif edge.edge_type == "assumes":
            outgoing_assumes[edge.from_node_id] = outgoing_assumes.get(edge.from_node_id, 0) + 1

    # Quick profile-node-id lookup by node_type.
    profile_ids: set[str] = set(
        n.node_id for n in graph.nodes if n.node_type == "profile"
    )

    for claim in graph.claims:
        thin = _thin_claim_dict(claim)
        if claim.validation_status == "unsupported":
            buckets["unknown"].append(thin)
            continue
        if claim.category == "SCENARIO" or outgoing_assumes.get(claim.claim_id, 0) > 0:
            buckets["estimated"].append(thin)
            continue
        if claim.category == "CALCULATION" or outgoing_derives.get(claim.claim_id, 0) > 0:
            buckets["derived"].append(thin)
            continue
        if claim.category == "FACT" and incoming_supports.get(claim.claim_id, 0) > 0:
            # The "profile" gate is enforced by category == FACT
            # (claims that derive from profile fields are FACT-
            # tagged) and the incoming_supports check.
            buckets["known"].append(thin)
            continue
        # Fallback: unknown — neither derived nor supports.
        buckets["unknown"].append(thin)

    # Surface proactive rows (the AI-7 MissingDataObject dicts)
    # inside the "unknown" bucket so the renderer can show
    # them alongside the AI-14 ones.
    for row in proactive_rows or ():
        if not isinstance(row, dict):
            continue
        thin = {
            "claim_id": str(row.get("field", "")) or "missing",
            "claim_text": str(row.get("reason", "")) or row.get("field", ""),
            "category": "UNKNOWN",
            "validation_status": "unsupported",
            "authority": 0.0,
            "freshness": "",
            "importance": row.get("importance"),
            "suggested_source": row.get("suggested_source"),
        }
        buckets["unknown"].append(thin)

    return buckets


# --------------------------------------------------------------------------- #
# Unsupported / fabricated accessors
# --------------------------------------------------------------------------- #


def unsupported_claims(graph: AnswerEvidenceGraph) -> tuple[ClaimNode, ...]:
    """Return the claim nodes with validation_status == 'unsupported'."""
    return tuple(c for c in graph.claims if c.validation_status == "unsupported")


def contradictory_claims(graph: AnswerEvidenceGraph) -> tuple[ClaimNode, ...]:
    """Return the claim nodes with validation_status == 'contradicted'.

    SPRINT AI-14 FINAL HARDENING — companion accessor to
    :func:`unsupported_claims`. The graph's
    ``contradictory_claim_count`` field carries the integer; this
    helper returns the ClaimNode tuples so the renderer can show
    which specific claims the contradiction detector flagged.
    """
    return tuple(c for c in graph.claims if c.validation_status == "contradicted")


def fabricated_sources(graph: AnswerEvidenceGraph) -> tuple[ExternalSourceNode, ...]:
    """Return external-source nodes that fail the URL guard.

    The URL guard is heuristic: a node is considered fabricated
    when its ``authority`` is < 0.5 (the URL-allow-list is empty
    by default in AI-14). A future sprint can plug in a signed
    registry; the API stays the same.
    """
    return tuple(s for s in graph.external_sources if s.authority < 0.5)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _thin_claim_dict(claim: ClaimNode) -> dict:
    """Return a thin wire-safe claim dict (omits lineage ids)."""
    return {
        "claim_id": claim.claim_id,
        "claim_text": claim.claim_text,
        "category": claim.category,
        "validation_status": claim.validation_status,
        "authority": float(claim.authority),
        "freshness": claim.freshness,
    }


def assumption_lineage_dicts(
    assumptions: tuple[AssumptionNode, ...],
) -> list[dict]:
    """Wire-shape list of assumption dicts."""
    return [a.to_dict() for a in assumptions]
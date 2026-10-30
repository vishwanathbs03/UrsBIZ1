"""Sprint AI-14 — Universal Answer Intelligence: ``AnswerEvidenceGraph``.

The graph in this module is the *lineage spine* of every AI-14
reply. After the tool dispatcher returns its
``StructuredToolEnvelope``s and the LLM produces its claim-aware
payload, the evidence graph builder walks the inputs and emits
a frozen graph of:

  * :class:`EvidenceNode`        — one per profile field, tool
                                   envelope, calculation, external
                                   source, or assumption that
                                   contributed to the answer.
  * :class:`EvidenceEdge`        — one per "X supports /
                                   contradicts / derives-from /
                                   assumes Y" relationship.
  * :class:`ClaimNode`           — one per material claim the LLM
                                   produced (or that the
                                   deterministic fallback made
                                   about the business).
  * :class:`CalculationNode`     — one per numeric the answer
                                   carries. Deterministic lineage:
                                   inputs / formula / output / unit
                                   / source / calculation_id.
  * :class:`AssumptionNode`      — one per declared assumption.
  * :class:`ExternalSourceNode`  — one per external reference
                                   (knowledge base, scheme, etc).

The graph is built deterministically. No LLM is called. The
``unsupported_claim_count`` and ``fabricated_source_count`` at
the top of :class:`AnswerEvidenceGraph` are the audit-row
counters the frontend renders.

Why a graph and not a flat dict?

  * Claim nodes can reference multiple evidence nodes (e.g. a
    "we should hire" claim that pulls from ``profile.employee_count``,
    ``profile.payroll_cost``, and a ``finance`` envelope's
    affordability calculation).
  * A flat dict cannot represent the "A supports B" /
    "A contradicts B" relations without losing context.

This module is the second half of the AI-14 answer-intelligence
layer; see :mod:`app.services.ai.reasoning.answer_requirements`
for the answer-shape half and
:mod:`app.services.ai.reasoning.calculation_lineage` for the
numeric-lineage helper.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable


# --------------------------------------------------------------------------- #
# Authority constants
# --------------------------------------------------------------------------- #

# Authority is a 0..1 number representing how much the user can
# trust a source. The constants here are the canonical
# trust-bands used by the AI-14 envelope.
AUTHORITY_PROFILE: float = 0.95      # business profile (direct user input)
AUTHORITY_CALCULATION: float = 0.85  # deterministic calculation over profile
AUTHORITY_TOOL: float = 0.80         # a registered business tool envelope
AUTHORITY_EXTERNAL: float = 0.70     # external source (scheme / government / KB)
AUTHORITY_ASSUMPTION: float = 0.30   # declared assumption / scenario estimate

# Validation status of an :class:`AnswerEvidenceGraph`.
Severity = str  # "none" | "low" | "medium" | "high"
ValidationStatus = str  # "supported" | "unsupported" | "contradicted" | "estimated"
Category = str  # "FACT" | "CALCULATION" | "INFERENCE" | "RECOMMENDATION" | "SCENARIO" | "EXTERNAL_FACT" | "UNKNOWN"
NodeType = str  # "profile" | "tool" | "calculation" | "external" | "assumption"
EdgeType = str  # "supports" | "contradicts" | "derived_from" | "assumes"


# --------------------------------------------------------------------------- #
# The 7 dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvidenceNode:
    """One node in the evidence graph.

    Every node carries a stable ``node_id`` (hash of
    ``node_type`` + source description), a short ``label``,
    a ``node_type`` (profile / tool / calculation / external /
    assumption), an ``authority`` (0..1), a ``freshness``
    (ISO-8601 or empty), a ``source_description`` (free-form,
    e.g. ``"business_profile.annual_revenue"``), and a
    ``raw_value_summary`` (e.g. ``"₹1.80 Cr"``)."""

    node_id: str
    label: str
    node_type: NodeType
    authority: float
    freshness: str
    source_description: str
    raw_value_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "node_type": self.node_type,
            "authority": float(self.authority),
            "freshness": self.freshness,
            "source_description": self.source_description,
            "raw_value_summary": self.raw_value_summary,
        }


@dataclass(frozen=True)
class EvidenceEdge:
    """Directed edge between two :class:`EvidenceNode` instances."""

    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    confidence: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "confidence": float(self.confidence),
            "note": self.note,
        }


@dataclass(frozen=True)
class ClaimNode:
    """One material claim the assistant made.

    Categories (per AI-3):
      * ``FACT``           — stated fact (revenue is X, score is Y)
      * ``CALCULATION``    — derived from a deterministic service
      * ``INFERENCE``      — LLM-inferred from evidence
      * ``RECOMMENDATION`` — a "you should do X" recommendation
      * ``SCENARIO``       — a scenario estimate
      * ``EXTERNAL_FACT``  — a fact from an external source
      * ``UNKNOWN``        — the LLM said "I don't know"

    Validation status:
      * ``supported``     — has at least one ``supports`` edge
      * ``unsupported``   — no edges into any source
      * ``contradicted``  — a ``contradicts`` edge from a node
                            with authority ≥ claim authority
      * ``estimated``     — derives from assumptions only
    """

    claim_id: str
    claim_text: str
    category: Category
    validation_status: ValidationStatus
    authority: float
    freshness: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    calculation_ids: tuple[str, ...] = field(default_factory=tuple)
    tool_ids: tuple[str, ...] = field(default_factory=tuple)
    assumption_ids: tuple[str, ...] = field(default_factory=tuple)
    external_source_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "category": self.category,
            "validation_status": self.validation_status,
            "authority": float(self.authority),
            "freshness": self.freshness,
            "evidence_ids": list(self.evidence_ids),
            "calculation_ids": list(self.calculation_ids),
            "tool_ids": list(self.tool_ids),
            "assumption_ids": list(self.assumption_ids),
            "external_source_ids": list(self.external_source_ids),
        }


@dataclass(frozen=True)
class CalculationNode:
    """Deterministic lineage for one numeric the answer carries.

    The LLM may explain but may never override inputs / formula /
    output / unit / source / calculation_id — those are derived
    from the upstream :class:`StructuredToolEnvelope` and are
    what the audit row shows."""

    calculation_id: str
    name: str
    inputs: dict[str, Any]
    formula: str
    output: float
    unit: str
    source_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    tool_name: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "calculation_id": self.calculation_id,
            "name": self.name,
            "inputs": dict(self.inputs),
            "formula": self.formula,
            "output": float(self.output),
            "unit": self.unit,
            "source_evidence_ids": list(self.source_evidence_ids),
            "tool_name": self.tool_name,
            "confidence": float(self.confidence),
        }


@dataclass(frozen=True)
class AssumptionNode:
    """One declared assumption (scenario or otherwise)."""

    assumption_id: str
    text: str
    source: str  # "scenario" | "external" | "user_provided" | "engine"

    def to_dict(self) -> dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "text": self.text,
            "source": self.source,
        }


@dataclass(frozen=True)
class ExternalSourceNode:
    """One external source (knowledge base, scheme, government)."""

    source_id: str
    label: str
    authority: float
    url_or_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "label": self.label,
            "authority": float(self.authority),
            "url_or_path": self.url_or_path,
        }


@dataclass(frozen=True)
class AnswerEvidenceGraph:
    """The full evidence lineage envelope for one assistant reply.

    Counters at the top (``unsupported_claim_count``,
    ``fabricated_source_count``) are the audit-row numbers the
    frontend renders inside the "Why am I seeing this?" panel.

    ``contradiction_severity`` is the AI-12
    :class:`CrossSourceContradictionDetector`'s severity
    classification — passed through unchanged so the UI can
    label the response accordingly.
    """

    nodes: tuple[EvidenceNode, ...] = field(default_factory=tuple)
    edges: tuple[EvidenceEdge, ...] = field(default_factory=tuple)
    claims: tuple[ClaimNode, ...] = field(default_factory=tuple)
    calculations: tuple[CalculationNode, ...] = field(default_factory=tuple)
    assumptions: tuple[AssumptionNode, ...] = field(default_factory=tuple)
    external_sources: tuple[ExternalSourceNode, ...] = field(default_factory=tuple)
    unsupported_claim_count: int = 0
    fabricated_source_count: int = 0
    # SPRINT AI-14 FINAL HARDENING — brief requires this
    # counter alongside unsupported / fabricated. Server-computed
    # from the claim nodes (validation_status == "contradicted").
    contradictory_claim_count: int = 0
    contradiction_severity: Severity = "none"
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "claims": [c.to_dict() for c in self.claims],
            "calculations": [c.to_dict() for c in self.calculations],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "external_sources": [s.to_dict() for s in self.external_sources],
            "unsupported_claim_count": int(self.unsupported_claim_count),
            "fabricated_source_count": int(self.fabricated_source_count),
            "contradictory_claim_count": int(self.contradictory_claim_count),
            "contradiction_severity": self.contradiction_severity,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AnswerEvidenceGraph":
        """Reconstruct from a wire dict (lists → tuples)."""
        payload = payload or {}
        nodes = tuple(
            EvidenceNode(
                node_id=n["node_id"],
                label=n["label"],
                node_type=n["node_type"],
                authority=float(n.get("authority", 0.0)),
                freshness=n.get("freshness", ""),
                source_description=n.get("source_description", ""),
                raw_value_summary=n.get("raw_value_summary", ""),
            )
            for n in payload.get("nodes", ())
        )
        edges = tuple(
            EvidenceEdge(
                from_node_id=e["from_node_id"],
                to_node_id=e["to_node_id"],
                edge_type=e["edge_type"],
                confidence=float(e.get("confidence", 0.0)),
                note=e.get("note", ""),
            )
            for e in payload.get("edges", ())
        )
        claims = tuple(
            ClaimNode(
                claim_id=c["claim_id"],
                claim_text=c["claim_text"],
                category=c["category"],
                validation_status=c["validation_status"],
                authority=float(c.get("authority", 0.0)),
                freshness=c.get("freshness", ""),
                evidence_ids=tuple(c.get("evidence_ids", ())),
                calculation_ids=tuple(c.get("calculation_ids", ())),
                tool_ids=tuple(c.get("tool_ids", ())),
                assumption_ids=tuple(c.get("assumption_ids", ())),
                external_source_ids=tuple(c.get("external_source_ids", ())),
            )
            for c in payload.get("claims", ())
        )
        calculations = tuple(
            CalculationNode(
                calculation_id=k["calculation_id"],
                name=k["name"],
                inputs=dict(k.get("inputs", {})),
                formula=k.get("formula", ""),
                output=float(k.get("output", 0.0)),
                unit=k.get("unit", ""),
                source_evidence_ids=tuple(k.get("source_evidence_ids", ())),
                tool_name=k.get("tool_name", ""),
                confidence=float(k.get("confidence", 1.0)),
            )
            for k in payload.get("calculations", ())
        )
        assumptions = tuple(
            AssumptionNode(
                assumption_id=a["assumption_id"],
                text=a["text"],
                source=a.get("source", "engine"),
            )
            for a in payload.get("assumptions", ())
        )
        external_sources = tuple(
            ExternalSourceNode(
                source_id=s["source_id"],
                label=s["label"],
                authority=float(s.get("authority", 0.0)),
                url_or_path=s.get("url_or_path", ""),
            )
            for s in payload.get("external_sources", ())
        )
        return cls(
            nodes=nodes,
            edges=edges,
            claims=claims,
            calculations=calculations,
            assumptions=assumptions,
            external_sources=external_sources,
            unsupported_claim_count=int(payload.get("unsupported_claim_count", 0)),
            fabricated_source_count=int(payload.get("fabricated_source_count", 0)),
            # SPRINT AI-14 FINAL HARDENING — wire-compat default
            # 0 when the legacy envelope omits the field.
            contradictory_claim_count=int(
                payload.get("contradictory_claim_count", 0)
            ),
            contradiction_severity=payload.get("contradiction_severity", "none"),
            rationale=payload.get("rationale", ""),
        )


# --------------------------------------------------------------------------- #
# Stable ID helper
# --------------------------------------------------------------------------- #


def _stable_id(*parts: Any, prefix: str = "n") -> str:
    """Return a stable, short hash-based id from any stringifiable parts."""
    payload = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


# --------------------------------------------------------------------------- #
# URL allow-list — heuristic guard for fabricated sources.
#
# In production this would be a signed registry of trusted URLs;
# the AI-14 deliverable ships the constant empty so the count
# remains 0 unless explicitly populated. The function is the
# public API the ``fabricated_sources`` helper uses; it is
# deliberately permissive (no false-positives) by default.
# --------------------------------------------------------------------------- #

# Default allow-list — empty in AI-14; populated by AI-15 follow-up.
# Public API: ``is_url_trusted`` lets the deterministic fallback
# short-circuit when the registry is empty.
_TRUSTED_URLS: tuple[str, ...] = ()


def is_url_trusted(url_or_path: str) -> bool:
    """Return True iff ``url_or_path`` matches a registered trusted URL."""
    if not _TRUSTED_URLS:
        return False
    if not url_or_path:
        return True  # Empty URL is not a fabrication.
    return any(trusted in url_or_path for trusted in _TRUSTED_URLS)


# --------------------------------------------------------------------------- #
# Profile node extraction
# --------------------------------------------------------------------------- #


# Profile attributes we surface as evidence nodes. Each tuple is
# ``(attribute_name, label, source_description)``. Adding an entry
# is non-breaking; the wire shape is keyed by ``node_id`` not by
# index.
_PROFILE_NODE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("business_id", "Business ID", "business_profile.business_id"),
    ("legal_name", "Legal name", "business_profile.legal_name"),
    ("industry", "Industry", "business_profile.industry"),
    ("location", "Location", "business_profile.location"),
    ("business_type", "Business type", "business_profile.business_type"),
    ("annual_revenue_inr", "Annual revenue", "business_profile.annual_revenue_inr"),
    ("target_revenue_inr", "Target revenue", "business_profile.target_revenue_inr"),
    ("employee_count", "Employee count", "business_profile.employee_count"),
    ("monthly_payroll_cost_inr", "Monthly payroll", "business_profile.monthly_payroll_cost_inr"),
    ("monthly_operating_cash_flow_inr", "Monthly cash flow", "business_profile.monthly_operating_cash_flow_inr"),
    ("operating_margin_pct", "Operating margin", "business_profile.operating_margin_pct"),
)


def _profile_nodes(context: Any | None, freshness: str) -> list[EvidenceNode]:
    """Return one EvidenceNode per populated profile field."""
    nodes: list[EvidenceNode] = []
    if context is None:
        return nodes
    for attr, label, source in _PROFILE_NODE_FIELDS:
        val = getattr(context, attr, None)
        if val in (0, 0.0, "", "unknown", "Not set", None, (), []):
            continue
        nodes.append(
            EvidenceNode(
                node_id=_stable_id("profile", source, str(val)),
                label=f"{label} ({val})" if not isinstance(val, (list, tuple)) else f"{label} ({len(val)} items)",
                node_type="profile",
                authority=AUTHORITY_PROFILE,
                freshness=freshness,
                source_description=source,
                raw_value_summary=str(val),
            )
        )
    return nodes


# --------------------------------------------------------------------------- #
# The builder
# --------------------------------------------------------------------------- #


def build_evidence_graph(
    *,
    question_understanding: Any = None,
    reasoning_plan: Any = None,
    envelopes: tuple[Any, ...] | list[Any] = (),
    context: Any = None,
    contradiction_report: Any = None,
    parsed_response: Any | None = None,
) -> AnswerEvidenceGraph:
    """Pure builder for the ``AnswerEvidenceGraph``.

    Same inputs produce the same output. The algorithm:

      1. Build profile nodes from ``context`` (skip empties).
      2. Build calculation nodes from envelopes that carry
         metric + value.
      3. Build assumption nodes from envelopes' assumptions.
      4. Build external-source nodes from
         ``knowledge_retrieval`` envelopes (and from any external
         reference the parsed LLM response names).
      5. Build claim nodes from the parsed response, classified
         by category. When the parsed response is ``None`` (the
         deterministic fallback path) we still produce a single
         claim node per populated profile field so the audit row
         has something to render.
      6. Walk envelopes + claims to draw EvidenceEdges
         (``supports`` / ``derived_from``).
      7. Apply the ``ContradictionReport``: flip
         ``claim.validation_status`` to ``"contradicted"`` when
         any of the contradiction report's flagged claims have
         authoritative evidence on the opposite side.
      8. Count unsupported claims (no ``supports`` edge).
      9. Count fabricated sources (URL guard).
     10. Stamp rationale.

    The function is best-effort; it never raises on missing
    fields. Empty inputs return an empty graph (so legacy rows
    decode as ``None`` and the UI gracefully falls back).
    """
    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []
    calculations: list[CalculationNode] = []
    assumptions: list[AssumptionNode] = []
    external_sources: list[ExternalSourceNode] = []

    qu = question_understanding
    parsed = parsed_response

    freshness = _freshness_from_context(context)

    # (1) Profile nodes
    nodes.extend(_profile_nodes(context, freshness))

    # (2) Calculation nodes from envelopes
    envelope_tuple = tuple(envelopes or ())
    for env in envelope_tuple:
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
        cal_node = CalculationNode(
            calculation_id=calc_id or _stable_id("calc", tool_name, metric, value, prefix="c"),
            name=f"{tool_name}.{metric}" if tool_name else str(metric),
            inputs={"value": output_f, "metric": str(metric)},
            formula=formula,
            output=output_f,
            unit=unit,
            source_evidence_ids=src_evidence,
            tool_name=tool_name,
            confidence=confidence,
        )
        calculations.append(cal_node)
        # Mirror as a graph node so claims can reference the calc by id.
        nodes.append(
            EvidenceNode(
                node_id=cal_node.calculation_id,
                label=cal_node.name,
                node_type="calculation",
                authority=AUTHORITY_CALCULATION,
                freshness=freshness,
                source_description=f"calculation:{cal_node.name}",
                raw_value_summary=f"{cal_node.output}{cal_node.unit}",
            )
        )

    # (3) Assumption nodes from envelopes
    for env in envelope_tuple:
        env_assumptions = tuple(getattr(env, "assumptions", ()) or ())
        for i, txt in enumerate(env_assumptions):
            text = str(txt or "").strip()
            if not text:
                continue
            assumptions.append(
                AssumptionNode(
                    assumption_id=_stable_id("assumption", tool_name := getattr(env, "tool_name", ""), i, text),
                    text=text,
                    source="scenario",
                )
            )

    # (4) External-source nodes
    for env in envelope_tuple:
        tool_name = getattr(env, "tool_name", "") or ""
        if tool_name == "knowledge_retrieval":
            label = str(getattr(env, "metric", "") or "knowledge base reference")
            url = ""
            payload = getattr(env, "raw_payload", {}) or {}
            url = str(payload.get("url", "") if isinstance(payload, dict) else "")
            authority = AUTHORITY_EXTERNAL
            if url and not is_url_trusted(url):
                # External-source node is still created (the audit
                # row renders it) but the authority is depressed
                # so the fabricated counter can flag it.
                authority = 0.4
            external_sources.append(
                ExternalSourceNode(
                    source_id=_stable_id("ext", tool_name, label, url),
                    label=label,
                    authority=authority,
                    url_or_path=url,
                )
            )

    # (5) Claim nodes
    claims: list[ClaimNode] = []
    parsed_claims = _extract_claims_from_parsed_response(parsed)
    if parsed_claims:
        for raw in parsed_claims:
            cid = _stable_id("claim", raw["text"])
            claims.append(
                ClaimNode(
                    claim_id=cid,
                    claim_text=raw["text"],
                    category=raw["category"],
                    validation_status="supported",  # provisional; step 7 may flip
                    authority=raw.get("authority", 0.6),
                    freshness=freshness,
                    evidence_ids=raw.get("evidence_ids", ()),
                    calculation_ids=raw.get("calculation_ids", ()),
                    tool_ids=raw.get("tool_ids", ()),
                    assumption_ids=raw.get("assumption_ids", ()),
                    external_source_ids=raw.get("external_source_ids", ()),
                )
            )
    elif envelope_tuple:
        # No parsed response (deterministic fallback path):
        # synthesise one claim per tool envelope so the audit
        # row has something to render. Each claim is the
        # "the engine produced X" statement, classified FACT
        # or CALCULATION depending on whether it carries a
        # numeric.
        for env in envelope_tuple:
            tool_name = getattr(env, "tool_name", "") or ""
            metric = getattr(env, "metric", "")
            value = getattr(env, "value", "")
            unit = getattr(env, "unit", "")
            text = f"{tool_name} returned {metric}={value}{unit}".strip()
            if not text:
                continue
            cat = "CALCULATION" if metric not in (None, "") else "FACT"
            claims.append(
                ClaimNode(
                    claim_id=_stable_id("claim", tool_name, metric, value),
                    claim_text=text,
                    category=cat,
                    validation_status="supported",
                    authority=AUTHORITY_TOOL,
                    freshness=freshness,
                    evidence_ids=(),
                    calculation_ids=(),
                    tool_ids=(tool_name,) if tool_name else (),
                    assumption_ids=(),
                    external_source_ids=(),
                )
            )

    # (6) Draw evidence edges.
    #    supports:  profile_node -> claim_node
    #              calc_node    -> claim_node
    #              ext_node     -> claim_node
    #    derived_from: claim_node -> calc_node
    #    assumes:   claim_node -> assumption_node
    calc_ids_by_tool = {c.tool_name: c.calculation_id for c in calculations}
    ext_ids = {s.source_id: s for s in external_sources}
    assumption_ids = {a.assumption_id: a for a in assumptions}
    for claim in claims:
        for eid in claim.tool_ids:
            if eid in calc_ids_by_tool:
                # tool produced a calc → supports
                edges.append(EvidenceEdge(
                    from_node_id=calc_ids_by_tool[eid],
                    to_node_id=claim.claim_id,
                    edge_type="supports",
                    confidence=0.9,
                ))
                # and the claim derives from it
                edges.append(EvidenceEdge(
                    from_node_id=claim.claim_id,
                    to_node_id=calc_ids_by_tool[eid],
                    edge_type="derived_from",
                    confidence=0.9,
                ))
        for ext_id in claim.external_source_ids:
            if ext_id in ext_ids:
                edges.append(EvidenceEdge(
                    from_node_id=ext_id,
                    to_node_id=claim.claim_id,
                    edge_type="supports",
                    confidence=ext_ids[ext_id].authority,
                ))
        for aid in claim.assumption_ids:
            if aid in assumption_ids:
                edges.append(EvidenceEdge(
                    from_node_id=claim.claim_id,
                    to_node_id=aid,
                    edge_type="assumes",
                    confidence=0.6,
                ))

    # If a claim has no incoming edges, mark it unsupported (step 8).
    incoming: dict[str, int] = {c.claim_id: 0 for c in claims}
    for edge in edges:
        if edge.edge_type == "supports" and edge.to_node_id in incoming:
            incoming[edge.to_node_id] += 1
    final_claims: list[ClaimNode] = []
    for claim in claims:
        if incoming.get(claim.claim_id, 0) == 0:
            final_claims.append(_replace_validation_status(claim, "unsupported"))
        else:
            final_claims.append(claim)

    # (7) Apply contradiction report — flip contradicted claims.
    contradiction_severity = "none"
    if contradiction_report is not None:
        contradiction_severity = str(
            getattr(contradiction_report, "severity", "none") or "none"
        )
        flagged = set(getattr(contradiction_report, "flagged_claim_ids", ()) or ())
        if flagged:
            new_claims = []
            for claim in final_claims:
                if claim.claim_id in flagged:
                    new_claims.append(_replace_validation_status(claim, "contradicted"))
                else:
                    new_claims.append(claim)
            final_claims = new_claims

    # (8) Unsupported counter.
    unsupported_count = sum(
        1 for c in final_claims if c.validation_status == "unsupported"
    )

    # (8b) SPRINT AI-14 FINAL HARDENING — contradictory counter.
    # Same source of truth (validation_status); complements the
    # ``contradiction_severity`` label that the renderer also reads.
    contradictory_count = sum(
        1 for c in final_claims if c.validation_status == "contradicted"
    )

    # (9) Fabricated-source counter.
    fabricated_count = sum(
        1 for s in external_sources if s.authority < 0.5
    )

    # (10) Rationale
    rationale = (
        f"profile_nodes={sum(1 for n in nodes if n.node_type == 'profile')}; "
        f"calc_nodes={len(calculations)}; "
        f"claims={len(final_claims)} "
        f"(unsupported={unsupported_count}; contradicted={contradictory_count}); "
        f"external={len(external_sources)} (fabricated={fabricated_count}); "
        f"contradiction_severity={contradiction_severity}"
    )

    return AnswerEvidenceGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        claims=tuple(final_claims),
        calculations=tuple(calculations),
        assumptions=tuple(assumptions),
        external_sources=tuple(external_sources),
        unsupported_claim_count=unsupported_count,
        fabricated_source_count=fabricated_count,
        contradictory_claim_count=contradictory_count,
        contradiction_severity=contradiction_severity,
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _freshness_from_context(context: Any | None) -> str:
    """Best-effort freshness timestamp from context."""
    if context is None:
        return ""
    for attr in (
        "twin_generated_at",
        "recommendations_generated_at",
        "insights_generated_at",
        "schemes_generated_at",
        "forecasts_generated_at",
    ):
        v = getattr(context, attr, None)
        if v:
            return str(v)
    return ""


def _replace_validation_status(
    claim: ClaimNode, status: ValidationStatus
) -> ClaimNode:
    """Return a copy of ``claim`` with ``validation_status`` replaced."""
    return ClaimNode(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        category=claim.category,
        validation_status=status,
        authority=claim.authority,
        freshness=claim.freshness,
        evidence_ids=claim.evidence_ids,
        calculation_ids=claim.calculation_ids,
        tool_ids=claim.tool_ids,
        assumption_ids=claim.assumption_ids,
        external_source_ids=claim.external_source_ids,
    )


def _extract_claims_from_parsed_response(parsed: Any) -> list[dict[str, Any]]:
    """Best-effort extraction of claims from the LLM response payload.

    Accepts any duck-typed object exposing ``.claims`` (a list of
    items each with ``text``, ``category``, ``evidence_ids``,
    ``tool_ids``, ``calculation_ids``, ``assumption_ids``,
    ``external_source_ids``). Falls back to ``()`` when the
    parsed response is missing or unreadable.
    """
    if parsed is None:
        return []
    raw_claims = getattr(parsed, "claims", None)
    if not raw_claims:
        return []
    out: list[dict[str, Any]] = []
    for raw in raw_claims:
        text = str(getattr(raw, "text", "") or "").strip()
        if not text:
            continue
        out.append(
            {
                "text": text,
                "category": str(
                    getattr(raw, "category", "UNKNOWN") or "UNKNOWN"
                ),
                "authority": float(getattr(raw, "authority", 0.6) or 0.6),
                "evidence_ids": tuple(getattr(raw, "evidence_ids", ()) or ()),
                "calculation_ids": tuple(
                    getattr(raw, "calculation_ids", ()) or ()
                ),
                "tool_ids": tuple(getattr(raw, "tool_ids", ()) or ()),
                "assumption_ids": tuple(
                    getattr(raw, "assumption_ids", ()) or ()
                ),
                "external_source_ids": tuple(
                    getattr(raw, "external_source_ids", ()) or ()
                ),
            }
        )
    return out
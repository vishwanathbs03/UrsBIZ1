"""Claim-aware response contract — SPRINT AI-3.

The brief for this sprint introduces a new contract the LLM is asked
to fill alongside the existing ``GroundedResponse`` schema. The LLM
authors the *narrative* — which claims, recommendations, calculations,
scenarios, unknowns it wants to surface — and the server validates
that narrative against the ``EvidenceRegistry`` + ``AssistantContext``
+ ``tool_results``, then computes a deterministic confidence score.

The contract is *optional*. When the LLM omits the ``claim_aware``
field, the existing ``GroundedResponse`` flow carries on unchanged and
``ChatMessageOut.claim_aware_response`` is ``None``. When the LLM
fills it but the JSON is malformed, the parser returns ``None`` so
the wire never surfaces a half-parsed payload.

LLM owns
--------

  * Explanation language.
  * Prioritization — which recommendations, scenarios, risks to surface.
  * Exploratory reasoning — scenarios, inferential claims.

Server owns
-----------

  * Numeric reconciliation against ``AssistantContext`` + tool_results.
  * Evidence reference validation against ``EvidenceRegistry``.
  * Confidence calculation (deterministic, weight-documented).
  * Provenance — every claim records the original literal it
    replaced (when the numeric checker mutated prose).

Module shape
------------

``Claim`` + ``ClaimRecommendation`` + ``ClaimCalculation`` +
``ClaimScenario`` + ``ClaimUnknown`` are frozen dataclasses the
parser materialises. ``ClaimAwareResponse`` is the top-level
envelope with ``to_chat_body()`` (Markdown rendering for the
frontend fallback path) and ``to_dict()`` (JSON wire shape).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Allowed enum values
# --------------------------------------------------------------------------- #

# Seven legacy claim categories the LLM is asked to assign.
# SPRINT AI-16 adds three more (INTERNAL_BUSINESS, ASSUMPTION,
# SCENARIO already covered; new ones below). Adding a new one
# is non-breaking; renaming or removing is breaking.
#
# AI-16 extends the vocabulary to cover the brief's six-way
# claim-kind classification (INTERNAL_BUSINESS, CALCULATED,
# EXTERNAL_FACT, SCENARIO, ASSUMPTION, UNKNOWN). The legacy
# labels are preserved for backward compatibility; the
# ``ClaimKindClassifier`` (knowledge/claim_classifier.py) maps
# legacy labels into the new vocabulary as a safety net.
ALLOWED_CLAIM_TYPES: tuple[str, ...] = (
    "FACT",
    "CALCULATION",
    "INFERENCE",
    "RECOMMENDATION",
    "SCENARIO",
    "EXTERNAL_FACT",
    "UNKNOWN",
    # SPRINT AI-16 — three new claim kinds.
    "INTERNAL_BUSINESS",
    "ASSUMPTION",
)

# Allowed CALCULATION.source values. The validator enforces this
# exact set so the LLM cannot invent a source.
ALLOWED_CALCULATION_SOURCES: tuple[str, ...] = (
    "URSBIZ_ENGINE",
    "MODEL_SCENARIO",
    "USER_INPUT",
)

# Allowed UNKNOWN.impact values. Drives the confidence penalty.
ALLOWED_UNKNOWN_IMPACTS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")

# Hard caps protecting the wire payload from runaway model output.
_MAX_LIST_LEN = 32
_MAX_TEXT_LEN = 2000
_MAX_EVIDENCE_REFS = 16


# --------------------------------------------------------------------------- #
# Sub-dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Claim:
    """One atomic assertion the LLM is willing to stand behind.

    Attributes
    ----------
    text:
        The literal sentence the LLM emitted. The numeric checker
        mutates this in-place when a conflict with authoritative
        values is detected — the original is preserved in
        ``audit_log`` so the audit trail is faithful.
    claim_type:
        One of ``ALLOWED_CLAIM_TYPES``. The validator enforces this
        exact set; the parser maps unknown labels to ``"UNKNOWN"``
        so a typoed claim type never throws an exception.
    evidence_references:
        Stable evidence IDs the LLM cited. Every ID is checked
        against the ``EvidenceRegistry``; fabricated IDs are
        rejected by the claim validator.
    confidence:
        Model-reported confidence for this single claim, 0–100.
        Recorded for audit; NOT surfaced as the wire confidence
        (the server computes that from
        :class:`confidence_calculator.ConfidenceCalculator`).
    audit_log:
        Sidecar populated by the numeric checker when it mutates
        ``text``. Each entry is ``{"original": str, "replacement":
        str, "category": str, "authoritative_value": float,
        "tolerance": float}``. The validator never writes here.
    user_provided:
        True when the LLM is repeating a value from the user's own
        prompt (e.g. "₹1.8 Cr to ₹3 Cr"). ``FACT`` claims marked
        ``user_provided=True`` are exempted from the evidence-citation
        rule because the user is the source.
    """

    text: str
    claim_type: str
    evidence_references: tuple[str, ...] = field(default_factory=tuple)
    confidence: int | None = None
    audit_log: tuple[dict, ...] = field(default_factory=tuple)
    user_provided: bool = False
    # SPRINT AI-12 — three additive fields. All default-safe so
    # legacy rows (and the parser's call to ``Claim(text=...,
    # claim_type=..., ...)``) keep working unchanged.
    # ``calculation_ids`` lists the deterministic calc IDs the
    # claim is grounded in (e.g. ``("calc_growth_multiple_42",)``).
    # ``source_authority`` is a 0..1 weight the
    # ``ConfidenceCalculator`` looks at to dampen claims from
    # less-trusted sources (e.g. ``0.6`` for ``EXTERNAL_FACT``
    # vs ``0.95`` for ``URSBIZ_ENGINE``). ``status`` is the
    # claim lifecycle — ``"active"`` is the default; the AI-12
    # ``ClaimGraph`` (future sprint) will flip this to
    # ``"superseded"`` or ``"rejected"`` when a newer claim
    # replaces it.
    calculation_ids: tuple[str, ...] = field(default_factory=tuple)
    source_authority: float = 0.0
    status: str = "active"

    # SPRINT AI-14 — five additive lineage fields the evidence
    # graph uses to walk every claim → its sources (profile /
    # tool / calc / external / assumption). All default-safe so
    # the parser's existing ``Claim(text=..., claim_type=..., ...)``
    # construction sites keep working unchanged.
    #   * ``claim_id`` — the stable ``ClaimNode.claim_id`` the
    #     evidence-graph builder minted for this claim. Empty
    #     string for legacy rows.
    #   * ``tool_ids`` — the deterministic tool-envelope IDs the
    #     claim is grounded in (the AI-13 ``StructuredToolEnvelope
    #     .calculation_id`` for each tool the claim cites).
    #   * ``freshness`` — ISO-8601 timestamp the engine stamped on
    #     the underlying source. Empty string when the source
    #     does not carry a freshness signal.
    #   * ``validation_status`` — one of ``"supported"`` /
    #     ``"unsupported"`` / ``"contradicted"`` / ``"estimated"``.
    #     Default ``"supported"`` so pre-AI-14 rows (and claims
    #     the engine did not inspect) round-trip as supported.
    #   * ``authority`` — 0..1 weight the engine stamped on the
    #     claim's primary source. Defaults to ``source_authority``
    #     to preserve the AI-12 contract; when both are set, the
    #     AI-14 evidence-graph builder prefers ``authority``.
    claim_id: str = ""
    tool_ids: tuple[str, ...] = field(default_factory=tuple)
    freshness: str = ""
    validation_status: str = "supported"
    authority: float = 0.0


@dataclass(frozen=True)
class ClaimRecommendation:
    """One LLM-authored action recommendation.

    ``recommendation_id`` (when set) is the registry ID the LLM
    cited. ``title`` + ``rationale`` are descriptive prose the
    validator never scores on — only ``reason`` and
    ``evidence_references`` are mandatory.
    """

    title: str
    reason: str
    recommendation_id: str = ""
    evidence_references: tuple[str, ...] = field(default_factory=tuple)
    category: str = ""
    priority: str = ""
    estimated_score_gain: int | None = None
    estimated_timeline: str = ""


@dataclass(frozen=True)
class ClaimCalculation:
    """One derived figure the LLM surfaced.

    ``expression`` (when provided) is the human-readable derivation
    formula. ``inputs`` is the dict of variables the LLM substituted
    into the expression. Both are stored for audit so the verifier
    can recompute the result independently.
    """

    name: str
    result: float
    unit: str
    source: str  # one of ALLOWED_CALCULATION_SOURCES
    expression: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    evidence_references: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClaimScenario:
    """One illustrative scenario the LLM authored.

    Scenarios explicitly carry their own ``assumptions`` because
    the brief mandates that no scenario be presented without its
    preconditions. The validator rejects any SCENARIO with an
    empty ``assumptions`` list.
    """

    title: str
    description: str
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    revenue_impact: str = ""
    score_impact: str = ""
    confidence: int | None = None
    evidence_references: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClaimUnknown:
    """One gap in the LLM's knowledge base.

    ``impact`` is the LLM's assessment of how much this gap
    degrades the answer. Only ``HIGH``-impact unknowns drive the
    confidence penalty (per the documented formula).
    """

    question: str
    impact: str = "MEDIUM"
    rationale: str = ""
    clarification_prompt: str = ""


# --------------------------------------------------------------------------- #
# Top-level envelope
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClaimAwareResponse:
    """The validated claim-aware envelope.

    The LLM owns ``claims``, ``recommendations``, ``calculations``,
    ``scenarios``, ``unknowns``, ``assumptions``, ``limitations``,
    and ``narrative``. The server stamps ``server_confidence`` +
    ``server_confidence_rationale`` + ``numeric_conflicts`` after
    validation; those three fields are NOT authorable by the LLM.

    ``narrative`` is the LLM's free-form prose. It is preserved
    verbatim so the frontend has a fallback rendering path even
    when it ignores the structured fields.

    ``audit`` is populated by the numeric checker with the original
    literals the conflict-replacement mutated. It is NOT authorable
    by the LLM and is kept on the wire for the audit trail.

    ``answer`` is the headline string the LLM wanted as the
    assistant reply. Rendered first when non-empty, before the
    structured sections.
    """

    answer: str = ""
    claims: tuple[Claim, ...] = field(default_factory=tuple)
    recommendations: tuple[ClaimRecommendation, ...] = field(default_factory=tuple)
    calculations: tuple[ClaimCalculation, ...] = field(default_factory=tuple)
    scenarios: tuple[ClaimScenario, ...] = field(default_factory=tuple)
    unknowns: tuple[ClaimUnknown, ...] = field(default_factory=tuple)
    evidence_references: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    narrative: str = ""

    # Server-stamped; the LLM may not author these. The parser
    # ignores any ``server_*`` keys the LLM emits so the LLM cannot
    # override the server's value.
    server_confidence: int | None = None
    server_confidence_rationale: str = ""
    numeric_conflicts: tuple[dict, ...] = field(default_factory=tuple)
    server_audit: dict = field(default_factory=dict)

    # ---- convenience: render for the assistant chat UI ------------- #

    def to_chat_body(self) -> str:
        """Render the validated envelope as a Markdown body.

        The renderer prefers ``answer`` (the LLM's headline) and
        then surfaces the structured sections in priority order.
        Sections that are empty tuples are omitted so the body
        is never padded with blank headers.
        """
        lines: list[str] = []
        if self.answer:
            lines.append(self.answer)
            lines.append("")

        if self.claims:
            lines.append("### CLAIMS")
            for i, c in enumerate(self.claims, start=1):
                user_tag = " (user_provided)" if c.user_provided else ""
                refs = (
                    f" [refs: {', '.join(c.evidence_references)}]"
                    if c.evidence_references
                    else ""
                )
                lines.append(f"  {i}. [{c.claim_type}]{user_tag} {c.text}{refs}")
            lines.append("")

        if self.recommendations:
            lines.append("### RECOMMENDATIONS")
            for i, r in enumerate(self.recommendations, start=1):
                rid = f" [{r.recommendation_id}]" if r.recommendation_id else ""
                lines.append(f"  {i}.{rid} {r.title} — {r.reason}")
            lines.append("")

        if self.calculations:
            lines.append("### CALCULATIONS")
            for calc in self.calculations:
                lines.append(
                    f"  - {calc.name}: {calc.result} {calc.unit} "
                    f"({calc.source})"
                )
            lines.append("")

        if self.scenarios:
            lines.append("### SCENARIOS")
            for i, s in enumerate(self.scenarios, start=1):
                lines.append(f"  {i}. {s.title}: {s.description}")
                if s.assumptions:
                    lines.append("    Assumptions:")
                    for a in s.assumptions:
                        lines.append(f"      - {a}")
            lines.append("")

        if self.unknowns:
            lines.append("### UNKNOWNS")
            for i, u in enumerate(self.unknowns, start=1):
                lines.append(f"  {i}. [{u.impact}] {u.question}")
            lines.append("")

        if self.assumptions:
            lines.append("### ASSUMPTIONS")
            for a in self.assumptions:
                lines.append(f"  - {a}")
            lines.append("")

        if self.limitations:
            lines.append("### LIMITATIONS")
            for l_ in self.limitations:
                lines.append(f"  - {l_}")
            lines.append("")

        if self.server_confidence is not None:
            lines.append(
                f"### CONFIDENCE (server): {self.server_confidence}/100"
            )
            if self.server_confidence_rationale:
                lines.append(f"  {self.server_confidence_rationale}")
            lines.append("")

        if self.narrative:
            lines.append("### NARRATIVE")
            lines.append(self.narrative)

        return "\n".join(lines).rstrip()

    # ---- wire serialization ----------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """Serialise the envelope as a JSON-safe dict.

        The wire schema mirrors the Pydantic mirror in
        :class:`app.schemas.chat.ChatClaimAwareResponse`. Tuples
        become lists, every nested dataclass becomes a dict.
        """
        return {
            "answer": self.answer,
            "claims": [
                {
                    "text": c.text,
                    "claim_type": c.claim_type,
                    "evidence_references": list(c.evidence_references),
                    "confidence": c.confidence,
                    "audit_log": list(c.audit_log),
                    "user_provided": c.user_provided,
                    "calculation_ids": list(c.calculation_ids),
                    "source_authority": c.source_authority,
                    "status": c.status,
                    # SPRINT AI-14 — five additive lineage fields.
                    # Default-empty so legacy rows on the wire
                    # round-trip unchanged.
                    "claim_id": c.claim_id,
                    "tool_ids": list(c.tool_ids),
                    "freshness": c.freshness,
                    "validation_status": c.validation_status,
                    "authority": c.authority,
                }
                for c in self.claims
            ],
            "recommendations": [
                {
                    "title": r.title,
                    "reason": r.reason,
                    "recommendation_id": r.recommendation_id,
                    "evidence_references": list(r.evidence_references),
                    "category": r.category,
                    "priority": r.priority,
                    "estimated_score_gain": r.estimated_score_gain,
                    "estimated_timeline": r.estimated_timeline,
                }
                for r in self.recommendations
            ],
            "calculations": [
                {
                    "name": c.name,
                    "result": c.result,
                    "unit": c.unit,
                    "source": c.source,
                    "expression": c.expression,
                    "inputs": c.inputs,
                    "evidence_references": list(c.evidence_references),
                }
                for c in self.calculations
            ],
            "scenarios": [
                {
                    "title": s.title,
                    "description": s.description,
                    "assumptions": list(s.assumptions),
                    "revenue_impact": s.revenue_impact,
                    "score_impact": s.score_impact,
                    "confidence": s.confidence,
                    "evidence_references": list(s.evidence_references),
                }
                for s in self.scenarios
            ],
            "unknowns": [
                {
                    "question": u.question,
                    "impact": u.impact,
                    "rationale": u.rationale,
                    "clarification_prompt": u.clarification_prompt,
                }
                for u in self.unknowns
            ],
            "evidence_references": list(self.evidence_references),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "narrative": self.narrative,
            "server_confidence": self.server_confidence,
            "server_confidence_rationale": self.server_confidence_rationale,
            "numeric_conflicts": list(self.numeric_conflicts),
            "server_audit": self.server_audit,
        }


# --------------------------------------------------------------------------- #
# Capacity / clamp helpers — exposed because the parser shares them
# --------------------------------------------------------------------------- #


def clamp_text(value: Any, field_name: str, errors: list[str]) -> str:
    """Coerce ``value`` to a string and clamp to ``_MAX_TEXT_LEN``.

    Used by the parser when materialising dataclass fields. The
    ``errors`` list is appended-to when the value had to be clamped
    so the caller can log/audit.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            s = str(value)
        except Exception:
            s = ""
        errors.append(f"{field_name} coerced to string from {type(value).__name__}")
    else:
        s = value
    if len(s) > _MAX_TEXT_LEN:
        errors.append(f"{field_name} truncated to {_MAX_TEXT_LEN} chars")
        s = s[: _MAX_TEXT_LEN - 1].rstrip() + "…"
    return s


def clamp_string_list(
    value: Any, field_name: str, errors: list[str]
) -> tuple[str, ...]:
    """Materialise a list-of-strings field capped at ``_MAX_LIST_LEN``."""
    if value is None:
        return ()
    if not isinstance(value, list):
        errors.append(f"{field_name} is not a list")
        return ()
    out: list[str] = []
    for item in value[:_MAX_LIST_LEN]:
        s = clamp_text(item, field_name, errors)
        if s:
            out.append(s)
    return tuple(out)


def clamp_confidence(
    value: Any, field_name: str, errors: list[str]
) -> int | None:
    """Materialise a 0..100 confidence int. None when the LLM omitted it."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} not an integer: {value!r}")
        return None
    if n < 0:
        errors.append(f"{field_name} clamped up to 0")
        return 0
    if n > 100:
        errors.append(f"{field_name} clamped down to 100")
        return 100
    return n

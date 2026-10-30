"""EvidenceRequirementPlanner — SPRINT AI-12 Universal Reasoning Layer.

Determines *what evidence the question demands* BEFORE any
retrieval happens. The plan is consumed by:

  * ``EvidenceRetriever.rank(...)`` (future filter parameter).
  * ``AssistantContext.select_minimal_slice(...)`` (which slices
    the LLM sees).
  * ``GenerationMeta.evidence_requirements`` (audit trail).

The vocabulary is intentionally a `tuple[str, ...]` (not a
typed ``EvidenceType`` enum) so renames don't break the wire
projection. The brief is explicit on this trade-off.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai.reasoning.question_understanding import (
        QuestionUnderstanding,
    )


@dataclass(frozen=True)
class EvidenceRequirements:
    """The evidence kinds the question demands.

    Attributes
    ----------
    required:
        Mandatory evidence kinds for the question to be
        answerable.
    optional:
        Evidence kinds that would improve the answer but are
        not strictly required.
    rationale:
        One-sentence explanation for the audit trail.
    """

    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "required": list(self.required),
            "optional": list(self.optional),
            "rationale": self.rationale,
        }


# Capability → evidence-type table. Drives the requirement
# computation. Matches the plan §3 capability → tool dispatch
# matrix; the evidence set is the "what data the tools need
# to run correctly" complement.
_CAPABILITY_TO_EVIDENCE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # capability → (required evidence types, optional evidence types)
    "GENERAL_KNOWLEDGE": (
        ("document", "knowledge_base"),
        (),
    ),
    "BUSINESS_ANALYSIS": (
        ("profile", "analytics", "kpi_history"),
        ("score_history", "rule_history"),
    ),
    "BUSINESS_FACT": (
        ("profile",),
        ("analytics",),
    ),
    "CALCULATION": (
        ("profile", "transaction", "rate_card"),
        ("forecast_history",),
    ),
    "FINANCIAL": (
        ("profile", "transaction"),
        ("forecast_history",),
    ),
    "OPERATIONAL": (
        ("profile", "process_metrics"),
        ("team_metrics",),
    ),
    "RISK": (
        ("profile", "risk_register"),
        ("scenario_history",),
    ),
    "SCENARIO": (
        ("profile", "historical_assumption"),
        ("scenario_history",),
    ),
    "FORECAST": (
        ("profile", "forecast_history"),
        ("external_market",),
    ),
    "COMPARISON": (
        ("profile", "product", "scheme"),
        ("industry_benchmark",),
    ),
    "RECOMMENDATION": (
        ("profile", "rules"),
        ("recommendation_history",),
    ),
    "GOVERNMENT_SCHEME": (
        ("scheme", "profile", "funding"),
        ("application_history",),
    ),
    "EXPORT": (
        ("scheme", "certification"),
        ("market_intel",),
    ),
    "ROADMAP": (
        ("profile", "recommendation"),
        ("roadmap_history",),
    ),
    "EXTERNAL_INFORMATION": (
        ("document", "regulatory", "external"),
        (),
    ),
    "MIXED": (
        ("profile",),
        ("document",),
    ),
    "UNKNOWN": (
        ("profile",),
        (),
    ),
}


def plan(qu: "QuestionUnderstanding") -> EvidenceRequirements:
    """Return the evidence kinds the question demands.

    Algorithm:
      1. Walk the AI-11 capability tuple in priority order.
      2. Take the union of all required evidence types (de-duped).
      3. Take the union of all optional evidence types.
      4. Always include ``"profile"`` when the question is
         business-specific and ``profile`` is not already
         required — guarantees the renderer has baseline data
         for the disambiguation block.
      5. ``rationale`` is a one-line summary for the audit
         trail.

    Pure function. Same inputs ⇒ same output. No LLM access.
    """
    required: list[str] = []
    optional: list[str] = []
    seen_required: set[str] = set()
    seen_optional: set[str] = set()

    capability = getattr(qu, "capability", ()) or ()
    for cap in capability:
        req, opt = _CAPABILITY_TO_EVIDENCE.get(cap, ((), ()))
        for ev in req:
            if ev not in seen_required:
                seen_required.add(ev)
                required.append(ev)
        for ev in opt:
            if ev not in seen_required and ev not in seen_optional:
                seen_optional.add(ev)
                optional.append(ev)

    # Always inject ``profile`` when the question is business-specific.
    is_biz = bool(getattr(qu, "is_business_specific", False))
    if is_biz and "profile" not in seen_required:
        required.insert(0, "profile")
        seen_required.add("profile")

    # Compose rationale for the audit trail.
    rationale_bits: list[str] = []
    if capability:
        rationale_bits.append("capability=" + ", ".join(capability))
    if is_biz:
        rationale_bits.append("business-specific")
    if not rationale_bits:
        rationale_bits.append("no-capability-detected")
    rationale = "evidence plan keyed by " + " | ".join(rationale_bits)

    return EvidenceRequirements(
        required=tuple(required),
        optional=tuple(optional),
        rationale=rationale,
    )

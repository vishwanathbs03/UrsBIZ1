"""SPRINT AI-10 — Explain My Answer. Decision trace dataclasses.

The ``DecisionTrace`` is the wire shape for the per-recommendation
"Explain this answer" panel. Every section is a typed tuple of
frozen dataclasses; the trace is built by the deterministic
:mod:`app.services.ai.trace.builder` module — no LLM is involved.

Architecture
------------

::

    Recommendation (frozen)
        │
        ▼
    build_trace(rec, ctx, registry, all_recs)
        │
        ▼
    DecisionTrace (frozen, JSON-serialisable)
        │
        ▼
    GenerationMeta.explanation: dict[rec_id, DecisionTrace.to_dict()]

Every string in the trace is derived from a known structured
source (``Recommendation`` fields, ``EvidenceRegistry`` entries,
``AssistantContext`` data, or ``dependencies.DEPENDS_ON`` table
docstrings). The trace is **never** authored by an LLM; the brief
explicitly forbids exposing hidden chain-of-thought.

Section reference
-----------------

Each section maps to one column in the brief's table:

==================  ===================================================
Section             Structured source
==================  ===================================================
``evidence``        ``rec.supporting_rule_ids``, ``rec.related_score_keys``,
                    ``rec.related_intelligence_keys``, ``rec.supporting_article_ids``,
                    ``EvidenceRegistry`` lookup
``calculations``    Re-derivation of ``rec.confidence``, ``estimated_score_gain``,
                    ``estimated_roi`` from ``impact.py`` / ``roi.py`` formulas;
                    the breakdown (priority_bonus, impact_bonus, article_bonus)
                    is preserved BEFORE summing.
``decision_factors`` Rec priority label + business_impact threshold + category
                    phrasing from ``generator._CATEGORY_DNA_EFFECT``.
``assumptions``     ``dependencies.DEPENDS_ON`` docstrings (curated "why this
                    dependency exists" prose).
``uncertainty``     Threshold sensitivity: priority weight + business_impact
                    scaling + category cost/timeline tables.
``alternatives``    ``rec.dependencies`` (forward + reverse from ``DEPENDS_ON``)
                    plus shared-score siblings.
==================  ===================================================

Additive contract
-----------------

The dataclasses are append-only. Renaming a field is breaking;
adding a new one with a default is non-breaking.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Section items
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TraceEvidenceItem:
    """One authoritative fact cited by the trace.

    ``id`` is the canonical registry ID (e.g. ``score_overall``,
    ``rule_supplier_concentration``). ``label`` and ``value`` are
    pulled verbatim from the ``EvidenceRegistry`` entry the ID
    resolves to — never authored by an LLM.
    """

    id: str
    label: str
    value: str


@dataclass(frozen=True)
class TraceCalculationItem:
    """One deterministic calc that produced a numeric field on the rec.

    ``formula`` is the literal expression from the corresponding
    helper module's docstring (``impact.py`` line 23-27, ``roi.py``
    line 21-22). ``inputs`` preserves the intermediate values
    BEFORE they are summed — this is the breakdown that's
    currently lost when ``Recommendation`` collapses the bonuses
    into a single ``confidence`` int.

    Invariant: re-deriving the field from ``inputs`` yields the
    same number stamped on ``rec.<field>``. Verified by the
    ``test_trace_calculations_breakdown_sum_matches`` invariant.
    """

    name: str
    formula: str
    inputs: dict[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass(frozen=True)
class TraceDecisionFactor:
    """One human-readable decision factor rendered from structured fields.

    ``factor`` is a literal constructed from ``rec.priority`` /
    ``rec.category`` / ``rec.business_impact`` — never free-form
    prose. ``source`` is the registry ID or rule ID the factor
    was derived from so the frontend can footnote it.
    """

    factor: str
    source: str


@dataclass(frozen=True)
class TraceAssumption:
    """One assumption baked into the recommendation.

    The text comes from one of two curated sources:

      * ``dependencies.DEPENDS_ON[rule.id]`` docstring — the
        "why this dependency exists" prose the dependencies
        module carries inline.
      * The supporting rule's ``reason`` field (when present).

    The source is stamped so the audit trail can answer
    "where did this string come from?".
    """

    text: str
    source: str


@dataclass(frozen=True)
class TraceUncertainty:
    """One thing that could flip the conclusion.

    Each uncertainty is a one-line sensitivity hook:
      * Priority weight threshold (e.g. "Critical weight 4 → High weight 3
        would drop confidence by ~10 points")
      * Business_impact scaling (e.g. "score_gain scales 0.6x with impact")
      * Category cost / timeline tables (e.g. "export readiness base
        ₹8,000 could shift in a future heuristic revision")
    """

    text: str
    source: str


@dataclass(frozen=True)
class TraceAlternative:
    """One alternative the engine surfaced.

    ``relation`` is one of:
      * ``"is_blocked_by"`` — this rec depends on the alternative
        (``rec.dependencies`` forward)
      * ``"blocks"`` — the alternative depends on this rec
        (reverse from ``DEPENDS_ON``)
      * ``"related_to"`` — shared ``related_score_keys`` with
        another rec
    """

    id: str
    title: str
    relation: str  # "blocks" | "is_blocked_by" | "related_to"


# --------------------------------------------------------------------------- #
# The trace envelope
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DecisionTrace:
    """Compact, structured explanation for ONE recommendation.

    The wire shape is a dict keyed by ``recommendation_id`` on
    ``GenerationMeta.explanation`` and the top-level
    ``ChatMessageOut.explanation`` mirror. The renderer renders
    one :class:`ExplanationPanel` per recommendation.

    Invariants
    ----------

      1. All six sections are tuples of frozen dataclasses.
      2. ``confidence_label`` is a literal — never LLM-authored.
      3. ``to_dict()`` is JSON-serialisable; the round-trip
         preserves every field.
      4. ``is_empty()`` returns True iff every section is empty —
         the renderer uses it to decide whether to hide the panel.
    """

    recommendation_id: str
    evidence: tuple[TraceEvidenceItem, ...] = field(default_factory=tuple)
    calculations: tuple[TraceCalculationItem, ...] = field(default_factory=tuple)
    decision_factors: tuple[TraceDecisionFactor, ...] = field(default_factory=tuple)
    assumptions: tuple[TraceAssumption, ...] = field(default_factory=tuple)
    uncertainty: tuple[TraceUncertainty, ...] = field(default_factory=tuple)
    alternatives: tuple[TraceAlternative, ...] = field(default_factory=tuple)
    confidence: int = 0
    confidence_label: str = ""

    def is_empty(self) -> bool:
        """Return True iff every section list is empty.

        A trace with only ``confidence`` set and no other content
        still counts as "empty" — there is nothing to render.
        """
        return not (
            self.evidence
            or self.calculations
            or self.decision_factors
            or self.assumptions
            or self.uncertainty
            or self.alternatives
        )

    def to_dict(self) -> dict:
        """Project the trace to a JSON-serialisable dict.

        The output is what gets stamped on
        ``GenerationMeta.explanation[recommendation_id]`` and what
        the frontend's ``ExplanationPanel`` reads. Tuples become
        lists; nested dataclasses become dicts via ``asdict``.
        """
        return {
            "recommendation_id": self.recommendation_id,
            "evidence": [asdict(item) for item in self.evidence],
            "calculations": [asdict(item) for item in self.calculations],
            "decision_factors": [asdict(item) for item in self.decision_factors],
            "assumptions": [asdict(item) for item in self.assumptions],
            "uncertainty": [asdict(item) for item in self.uncertainty],
            "alternatives": [asdict(item) for item in self.alternatives],
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
        }


__all__ = [
    "TraceEvidenceItem",
    "TraceCalculationItem",
    "TraceDecisionFactor",
    "TraceAssumption",
    "TraceUncertainty",
    "TraceAlternative",
    "DecisionTrace",
]

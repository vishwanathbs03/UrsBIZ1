"""SPRINT AI-10 — Explain My Answer. The trace builder.

Pure deterministic function that converts a
:class:`app.services.recommendations.base.Recommendation` plus
the surrounding structured context into a
:class:`DecisionTrace`. **No LLM, no clock, no DB.**

Contract
--------

::

    build_trace(rec, ctx, registry, all_recs, rules_by_id)
        -> DecisionTrace

Parameters
----------

``rec``
    The recommendation to explain. ``rec.id`` doubles as the
    trace's ``recommendation_id`` field (and as the registry
    lookup key when one is available).

``ctx``
    The :class:`app.services.ai.providers.base.AssistantContext`
    the assistant provider assembled for this turn. Used to
    resolve score values, business metrics, and DNA archetype
    facts.

``registry``
    The :class:`EvidenceRegistry` the prompt builder assembled.
    Used to resolve every ``rec.supporting_rule_ids`` /
    ``rec.related_score_keys`` into a labelled value. ``None``
    is allowed — the builder falls back to a no-evidence trace.

``all_recs``
    Tuple of every :class:`Recommendation` in this turn. Used
    to populate the "Alternatives" section (shared scores,
    reverse-dependency lookup).

``rules_by_id``
    Optional mapping of rule.id → :class:`RuleSnapshot` so the
    builder can pull each rule's ``reason`` field for the
    "Assumptions" section. ``None`` allowed; assumptions fall
    back to ``dependencies.DEPENDS_ON`` docstrings only.

Guarantees
----------

1. **Pure** — same inputs always produce structurally equal traces.
2. **No fabrication** — every ``EvidenceItem.id`` resolves via the
   registry; every ``Alternative.id`` exists in ``all_recs``.
3. **No LLM** — the function never calls a provider.
4. **No chain-of-thought** — every string comes from a known
   structured source; the brief explicitly forbids CoT leakage.
5. **Defensive** — empty sections are returned as ``()`` tuples;
   the trace never raises on a minimal ``Recommendation``.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.ai.providers.base import AssistantContext
from app.services.ai.providers.evidence_registry import (
    EvidenceEntry,
    EvidenceKind,
    EvidenceRegistry,
)
from app.services.recommendations.base import (
    Category,
    Priority,
    Recommendation,
    RuleSnapshot,
)
from app.services.recommendations.dependencies import (
    DEPENDS_ON,
    _build_required_by,
)
from app.services.recommendations.impact import (
    confidence_for,
    estimate_score_gain,
)
from app.services.recommendations.priorities import (
    PRIORITY_WEIGHT,
    priority_weight,
)
from app.services.recommendations.roi import estimate_roi

from app.services.ai.trace.decision_trace import (
    DecisionTrace,
    TraceAlternative,
    TraceAssumption,
    TraceCalculationItem,
    TraceDecisionFactor,
    TraceEvidenceItem,
    TraceUncertainty,
)


# Confidence label literal mapping. Mirroring the brief's EXAMPLE
# exactly:
#   * High  — "supported by current business evidence."
#   * Medium — partial signal; one input borderline.
#   * Low    — limited evidence; review assumptions.
# These are LITERAL strings — the renderer cannot edit them and
# the LLM never authors them.
_CONFIDENCE_LABEL_HIGH = "High — supported by current business evidence."
_CONFIDENCE_LABEL_MEDIUM = "Medium — partial signal; one input borderline."
_CONFIDENCE_LABEL_LOW = "Low — limited evidence; review assumptions."


# Business-impact threshold for "material" — anything >= 60
# counts as a material driver for the decision factor prose.
_MATERIAL_IMPACT_THRESHOLD = 60


# Maximum number of alternatives surfaced per recommendation.
# The renderer handles overflow gracefully; the builder caps
# to keep the trace scannable.
_MAX_ALTERNATIVES = 5


def confidence_label_for(confidence: int) -> str:
    """Map a 0..100 confidence int to a literal label.

    The mapping is fixed; the renderer never edits these strings.
    """
    if confidence >= 80:
        return _CONFIDENCE_LABEL_HIGH
    if confidence >= 60:
        return _CONFIDENCE_LABEL_MEDIUM
    return _CONFIDENCE_LABEL_LOW


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def build_trace(
    rec: Recommendation | dict,
    *,
    ctx: AssistantContext | None = None,
    registry: EvidenceRegistry | None = None,
    all_recs: tuple[Recommendation | dict, ...] = (),
    rules_by_id: Mapping[str, RuleSnapshot] | None = None,
) -> DecisionTrace:
    """Build a :class:`DecisionTrace` for ``rec``.

    The function is the single source of truth for AI-10 traces.
    The :mod:`app.services.chat.conversation_service` calls it
    once per recommendation in a turn and stamps the resulting
    dict on ``GenerationMeta.explanation[rec.id]``.

    ``rec`` accepts either:

      * An upstream :class:`Recommendation` dataclass (the
        full-fat object from ``recommendations.service``); OR
      * A dict matching the ``Recommendation.to_payload()`` shape
        (used by callers that have already serialised the rec
        — the deterministic fallback path, for example, where
        only the wire-shape slice is available).

    See module docstring for parameter contract.
    """
    rec_payload = _coerce_to_payload(rec)
    rec_id = str(rec_payload.get("id", "") or "")
    confidence = int(rec_payload.get("confidence", 0) or 0)

    evidence = _extract_evidence(rec_payload, registry)
    calculations = _extract_calculations(rec_payload)
    decision_factors = _extract_decision_factors(rec_payload, ctx)
    assumptions = _extract_assumptions(rec_payload, rules_by_id)
    uncertainty = _extract_uncertainty(rec_payload)
    alternatives = _extract_alternatives(
        rec_payload, _coerce_payload_tuple(all_recs), registry
    )

    return DecisionTrace(
        recommendation_id=rec_id,
        evidence=evidence,
        calculations=calculations,
        decision_factors=decision_factors,
        assumptions=assumptions,
        uncertainty=uncertainty,
        alternatives=alternatives,
        confidence=confidence,
        confidence_label=confidence_label_for(confidence),
    )


def _coerce_to_payload(rec: Recommendation | dict) -> dict:
    """Project ``rec`` to the ``to_payload()`` dict shape.

    Centralised so every section extractor reads the same shape,
    regardless of whether the caller passed a dataclass or a dict.
    """
    if isinstance(rec, dict):
        return dict(rec)
    # Recommendation dataclass — call its canonical to_payload().
    try:
        payload = rec.to_payload()
    except Exception:  # noqa: BLE001 — defensive
        payload = {
            "id": getattr(rec, "id", ""),
            "title": getattr(rec, "title", ""),
            "priority": getattr(rec, "priority", "Medium"),
            "category": getattr(rec, "category", ""),
            "business_impact": getattr(rec, "business_impact", 0),
            "estimated_score_gain": getattr(rec, "estimated_score_gain", 0.0),
            "estimated_roi": getattr(rec, "estimated_roi", 0),
            "confidence": getattr(rec, "confidence", 0),
            "supporting_rule_ids": tuple(getattr(rec, "supporting_rule_ids", ())),
            "supporting_article_ids": tuple(getattr(rec, "supporting_article_ids", ())),
            "related_score_keys": tuple(getattr(rec, "related_score_keys", ())),
            "related_intelligence_keys": tuple(getattr(rec, "related_intelligence_keys", ())),
            "dependencies": tuple(getattr(rec, "dependencies", ())),
        }
    return dict(payload)


def _coerce_payload_tuple(
    recs: Iterable[Recommendation | dict],
) -> tuple[dict, ...]:
    """Coerce an iterable of recs (dataclass or dict) to payload tuples."""
    out: list[dict] = []
    for r in recs or ():
        out.append(_coerce_to_payload(r))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Evidence section
# --------------------------------------------------------------------------- #


def _extract_evidence(
    rec_payload: dict,
    registry: EvidenceRegistry | None,
) -> tuple[TraceEvidenceItem, ...]:
    """Resolve every cited rule / score / article ID via the registry.

    Three sources contribute, in priority order:

      1. ``rec.supporting_rule_ids`` — the rule(s) that fired the rec.
         Resolves to ``EvidenceKind.RULE`` entries.
      2. ``rec.related_score_keys`` — the score signals that
         triggered the rule. Resolves to ``EvidenceKind.SCORE``
         entries; the registry stores scores with their
         canonical ``score_<key>`` slug.
      3. ``rec.related_intelligence_keys`` — intelligence signals
         the rule's ``source_keys`` matched. Resolves to
         ``EvidenceKind.INSIGHT`` entries.

    The rec itself is NOT included in evidence — the rec IS the
    conclusion; evidence is the supporting facts.

    When ``registry`` is ``None`` (e.g. the deterministic fallback
    path), the section falls back to a no-evidence trace.
    """
    if registry is None:
        return ()

    items: list[TraceEvidenceItem] = []

    # 1. Supporting rules — convert each rule.id to ``rule_<id>``.
    for rule_id in rec_payload.get("supporting_rule_ids", ()) or ():
        item = _lookup(registry, f"rule_{_slug(str(rule_id))}", EvidenceKind.RULE)
        if item is not None:
            items.append(item)

    # 2. Related score keys — ``score.foo`` → ``score_foo`` slug.
    for key in rec_payload.get("related_score_keys", ()) or ():
        slug = _slug(str(key).removeprefix("score."))
        item = _lookup(registry, f"score_{slug}", EvidenceKind.SCORE)
        if item is not None:
            items.append(item)

    # 3. Related intelligence keys — ``intelligence.foo`` → ``intelligence_foo``.
    for key in rec_payload.get("related_intelligence_keys", ()) or ():
        slug = _slug(str(key).removeprefix("intelligence."))
        item = _lookup(registry, f"intelligence_{slug}", EvidenceKind.INSIGHT)
        if item is not None:
            items.append(item)

    # Deduplicate by id while preserving order.
    seen: set[str] = set()
    deduped: list[TraceEvidenceItem] = []
    for item in items:
        if item.id not in seen:
            seen.add(item.id)
            deduped.append(item)

    return tuple(deduped)


def _lookup(
    registry: EvidenceRegistry,
    evidence_id: str,
    kind: EvidenceKind,
) -> TraceEvidenceItem | None:
    """Resolve ``evidence_id`` via the registry, returning None on miss.

    The registry exposes ``by_id`` / ``by_kind`` accessors. A miss
    means the upstream projector did not emit the entry — the
    builder drops the fact (never fabricates one).
    """
    try:
        entry: EvidenceEntry | None = registry.by_id(evidence_id)
    except Exception:  # noqa: BLE001 — defensive; registry may not exist
        entry = None
    if entry is None or entry.kind != kind:
        return None
    return TraceEvidenceItem(
        id=entry.id,
        label=entry.label,
        value=entry.value,
    )


# --------------------------------------------------------------------------- #
# Calculations section
# --------------------------------------------------------------------------- #


def _extract_calculations(rec_payload: dict) -> tuple[TraceCalculationItem, ...]:
    """Re-derive every numeric field on ``rec`` and surface the breakdown.

    The breakdown is the audit-trail value-add: each numeric
    field on a Recommendation is currently a single int that
    hides the intermediate contributions. AI-10 surfaces the
    intermediate values BEFORE summing, so the renderer (and
    the audit log) can answer "where did this number come
    from?".

    Invariant: ``result`` matches the value stamped on
    ``rec.<field>`` — verified by the breakdown-sum invariant
    test.
    """
    out: list[TraceCalculationItem] = []

    priority = str(rec_payload.get("priority", "Medium") or "Medium")
    business_impact = int(rec_payload.get("business_impact", 0) or 0)
    article_ids = tuple(rec_payload.get("supporting_article_ids", ()) or ())
    confidence_value = int(rec_payload.get("confidence", 0) or 0)
    score_gain_value = float(rec_payload.get("estimated_score_gain", 0.0) or 0.0)
    roi_value = int(rec_payload.get("estimated_roi", 0) or 0)

    # 1. confidence = base(50) + priority_bonus + impact_bonus + article_bonus
    priority_bonus = _priority_bonus(priority)  # type: ignore[arg-type]
    impact_bonus = min(20, business_impact // 5)
    article_bonus = min(10, 5 * len(article_ids))
    confidence_inputs: dict[str, Any] = {
        "base": 50,
        "priority_bonus": priority_bonus,
        "impact_bonus": impact_bonus,
        "article_bonus": article_bonus,
        "article_count": len(article_ids),
        "business_impact": business_impact,
    }
    out.append(
        TraceCalculationItem(
            name="confidence",
            formula=(
                "min(100, 50 + priority_bonus + impact_bonus + "
                "min(10, 5 * article_count))"
            ),
            inputs=confidence_inputs,
            result=str(confidence_value),
        )
    )

    # 2. estimated_score_gain = business_impact * 0.6 + priority_weight * 1.5
    p_weight = priority_weight(priority)  # type: ignore[arg-type]
    out.append(
        TraceCalculationItem(
            name="estimated_score_gain",
            formula="min(25, business_impact * 0.6 + priority_weight * 1.5)",
            inputs={
                "business_impact": business_impact,
                "priority_weight": p_weight,
            },
            result=str(score_gain_value),
        )
    )

    # 3. estimated_roi = priority_weight * 12 + business_impact * 0.4
    out.append(
        TraceCalculationItem(
            name="estimated_roi",
            formula="clamp(priority_weight * 12 + business_impact * 0.4, 0, 100)",
            inputs={
                "priority_weight": p_weight,
                "business_impact": business_impact,
            },
            result=str(roi_value),
        )
    )

    return tuple(out)


def _priority_bonus(priority: Priority) -> int:
    """Map the priority label to its confidence bonus (impact.py line 73-77)."""
    return {
        "Critical": 30,
        "High": 20,
        "Medium": 10,
        "Low": 0,
    }[priority]


# --------------------------------------------------------------------------- #
# Decision factors section
# --------------------------------------------------------------------------- #


def _extract_decision_factors(
    rec_payload: dict,
    ctx: AssistantContext | None,
) -> tuple[TraceDecisionFactor, ...]:
    """Surface the main factors that drove the recommendation.

    Each factor is a literal constructed from ``rec`` fields:

      * Priority → "High-priority rule firing on <category>"
      * Business impact ≥ 60 → "Material business impact"
      * DNA archetype (when ctx is present) → contextual phrasing

    No prose is invented; the factor string is a deterministic
    composition of structured fields.
    """
    out: list[TraceDecisionFactor] = []

    priority = str(rec_payload.get("priority", "Medium") or "Medium")
    category = str(rec_payload.get("category", "") or "").replace("_", " ")
    business_impact = int(rec_payload.get("business_impact", 0) or 0)
    rec_id = str(rec_payload.get("id", "") or "")
    supporting_rule_ids = tuple(
        rec_payload.get("supporting_rule_ids", ()) or ()
    )
    related_score_keys = tuple(
        rec_payload.get("related_score_keys", ()) or ()
    )

    # Priority-based factor.
    priority_text = f"{priority}-priority rule firing on {category}"
    out.append(
        TraceDecisionFactor(
            factor=priority_text,
            source=rec_id,
        )
    )

    # Business impact threshold factor.
    if business_impact >= _MATERIAL_IMPACT_THRESHOLD:
        out.append(
            TraceDecisionFactor(
                factor=f"Material business impact ({business_impact}/100)",
                source="business_impact",
            )
        )
    elif business_impact > 0:
        out.append(
            TraceDecisionFactor(
                factor=f"Moderate business impact ({business_impact}/100)",
                source="business_impact",
            )
        )

    # Supporting rules count — when more than one rule fired, surface that.
    if len(supporting_rule_ids) > 1:
        out.append(
            TraceDecisionFactor(
                factor=(
                    f"{len(supporting_rule_ids)} supporting rule(s) "
                    f"converge on this recommendation"
                ),
                source="supporting_rule_ids",
            )
        )

    # Score-key coverage — when the rec cites multiple score signals.
    if len(related_score_keys) >= 2:
        out.append(
            TraceDecisionFactor(
                factor=(
                    f"Driven by {len(related_score_keys)} score signal(s): "
                    + ", ".join(
                        str(k).removeprefix("score.") for k in related_score_keys
                    )
                ),
                source="related_score_keys",
            )
        )

    # DNA archetype alignment — when ctx is provided.
    if ctx is not None and ctx.dna.archetype_title:
        out.append(
            TraceDecisionFactor(
                factor=(
                    f"Aligned with current DNA archetype "
                    f"({ctx.dna.archetype_title})"
                ),
                source="dna.archetype",
            )
        )

    return tuple(out)


# --------------------------------------------------------------------------- #
# Assumptions section
# --------------------------------------------------------------------------- #


def _extract_assumptions(
    rec_payload: dict,
    rules_by_id: Mapping[str, RuleSnapshot] | None,
) -> tuple[TraceAssumption, ...]:
    """Surface the assumptions baked into the recommendation.

    Two structured sources contribute:

      1. The ``reason`` field of the supporting rule(s) — the
         rule engine's own "why this fired" prose.
      2. The ``dependencies.DEPENDS_ON`` table docstrings — the
         curated ordering rationale. The docstrings explain
         the cross-recommendation ordering, which IS the
         "what assumption must hold for this rec to be the
         right answer" prose.

    When neither source yields prose, the section is empty —
    no free-form text is generated.
    """
    out: list[TraceAssumption] = []
    seen: set[str] = set()

    rec_id = str(rec_payload.get("id", "") or "")
    supporting_rule_ids = tuple(
        rec_payload.get("supporting_rule_ids", ()) or ()
    )

    # 1. Supporting rule reasons.
    if rules_by_id is not None:
        for rule_id in supporting_rule_ids:
            snapshot = rules_by_id.get(rule_id)
            if snapshot is None:
                continue
            reason = (snapshot.reason or "").strip()
            if reason and reason not in seen:
                seen.add(reason)
                out.append(
                    TraceAssumption(
                        text=reason,
                        source=f"rule.reason:{rule_id}",
                    )
                )

    # 2. Dependency table docstrings — for every rule that
    # depends on this rec (reverse lookup), the docstring
    # of that mapping carries the rationale.
    required_by = _build_required_by()
    downstream_rule_ids = list(required_by.get(rec_id, ()))
    for downstream_id in downstream_rule_ids:
        docstring = _depends_on_docstring(downstream_id)
        if docstring and docstring not in seen:
            seen.add(docstring)
            out.append(
                TraceAssumption(
                    text=docstring,
                    source=f"dependencies.DEPENDS_ON:{downstream_id}",
                )
            )

    return tuple(out)


def _depends_on_docstring(rule_id: str) -> str:
    """Return the curated docstring for ``rule_id``'s entry in DEPENDS_ON.

    The dependencies table is hand-written with explicit
    rationale (see ``dependencies.py`` lines 58-86). For rules
    that don't appear in the table, return an empty string —
    the assumption section quietly drops them.
    """
    # Reverse-lookup: if rule_id appears as a VALUE in
    # DEPENDS_ON, surface the docstring of the matching
    # KEY's entry. The dependencies module encodes rationale
    # only on the KEY side.
    for key, downstream in DEPENDS_ON.items():
        if rule_id in downstream:
            return _DEPENDS_ON_DOCSTRINGS.get(key, "")
    return ""


# Curated rationale strings for the DEPENDS_ON keys — mirrors
# the docstrings at dependencies.py lines 58-86.
_DEPENDS_ON_DOCSTRINGS: dict[str, str] = {
    "rule.export.no_iec": (
        "IEC registration is the legal prerequisite for any "
        "export — downstream export rules assume it is in place."
    ),
    "rule.digital.no_website": (
        "A website is the floor of digital presence; every other "
        "digital rule depends on it being established first."
    ),
    "rule.compliance.no_quality_cert": (
        "Quality certification is required before any export to a "
        "regulated market can proceed."
    ),
    "rule.immediate.no_profile_basics": (
        "Profile basics must be filled before any other rule "
        "produces an actionable recommendation."
    ),
}


# --------------------------------------------------------------------------- #
# Uncertainty section
# --------------------------------------------------------------------------- #


def _extract_uncertainty(rec_payload: dict) -> tuple[TraceUncertainty, ...]:
    """Surface the thresholds that could flip the conclusion.

    Three sensitivity hooks contribute:

      1. Priority weight — if ``PRIORITY_WEIGHT`` shifted, the
         rec's confidence / ROI / score_gain would change.
      2. Business-impact scaling — both confidence and ROI scale
         linearly with impact.
      3. Category-driven cost / timeline tables — heuristic, may
         shift in future heuristic revisions.
    """
    out: list[TraceUncertainty] = []

    priority = str(rec_payload.get("priority", "Medium") or "Medium")
    business_impact = int(rec_payload.get("business_impact", 0) or 0)
    category = str(rec_payload.get("category", "") or "").replace("_", " ")

    # 1. Priority weight sensitivity.
    p_weight = priority_weight(priority)  # type: ignore[arg-type]
    out.append(
        TraceUncertainty(
            text=(
                f"Confidence uses priority weight {p_weight} ({priority}); "
                f"weights pinned at "
                + ", ".join(f"{k}={v}" for k, v in PRIORITY_WEIGHT.items())
                + ". A future revision could shift this rec's confidence."
            ),
            source="priorities.PRIORITY_WEIGHT",
        )
    )

    # 2. Business-impact scaling.
    out.append(
        TraceUncertainty(
            text=(
                f"Business impact ({business_impact}/100) drives the "
                f"score_gain (×0.6), ROI (×0.4), and confidence bonuses; "
                f"a +10 impact delta would lift score_gain by ~6 points."
            ),
            source="impact.scale_with_business_impact",
        )
    )

    # 3. Category-driven cost / timeline — heuristic, may shift.
    out.append(
        TraceUncertainty(
            text=(
                f"Category '{category}' cost / timeline tables "
                f"are heuristic estimates; future revisions could "
                f"shift the displayed numbers."
            ),
            source="timeline.CATEGORY_PHASE",
        )
    )

    return tuple(out)


# --------------------------------------------------------------------------- #
# Alternatives section
# --------------------------------------------------------------------------- #


def _extract_alternatives(
    rec_payload: dict,
    all_recs: tuple[dict, ...],
    registry: EvidenceRegistry | None,
) -> tuple[TraceAlternative, ...]:
    """Surface alternatives the engine considered.

    Three relation types contribute:

      1. ``"is_blocked_by"`` — every entry in ``rec.dependencies``.
      2. ``"blocks"`` — every other rec that depends on this one
         (reverse of DEPENDS_ON).
      3. ``"related_to"`` — recs that share at least one
         ``related_score_keys`` with this rec.

    When ``all_recs`` is empty, only relations resolvable from
    the DEPENDS_ON table are surfaced.
    """
    by_id: dict[str, dict] = {str(r.get("id", "")): r for r in all_recs if r.get("id")}
    out: list[TraceAlternative] = []
    seen: set[str] = set()

    rec_id = str(rec_payload.get("id", "") or "")
    dependencies = tuple(rec_payload.get("dependencies", ()) or ())
    shared_score_keys = set(rec_payload.get("related_score_keys", ()) or ())

    # 1. rec.dependencies — recs this one is blocked by.
    for dep_id in dependencies:
        if dep_id in seen or dep_id == rec_id:
            continue
        seen.add(str(dep_id))
        title = _resolve_title(str(dep_id), by_id, registry)
        out.append(
            TraceAlternative(
                id=str(dep_id),
                title=title,
                relation="is_blocked_by",
            )
        )

    # 2. Reverse-dependency — recs that depend on this one.
    required_by = _build_required_by()
    downstream_ids = list(required_by.get(rec_id, ()))
    for downstream_id in downstream_ids:
        if downstream_id in seen or downstream_id == rec_id:
            continue
        seen.add(str(downstream_id))
        title = _resolve_title(str(downstream_id), by_id, registry)
        out.append(
            TraceAlternative(
                id=str(downstream_id),
                title=title,
                relation="blocks",
            )
        )

    # 3. Shared-score siblings — recs that share related_score_keys.
    if all_recs:
        for other in all_recs:
            other_id = str(other.get("id", "") or "")
            if not other_id or other_id == rec_id or other_id in seen:
                continue
            other_scores = set(other.get("related_score_keys", ()) or ())
            if shared_score_keys.intersection(other_scores):
                seen.add(other_id)
                out.append(
                    TraceAlternative(
                        id=other_id,
                        title=str(other.get("title", "") or other_id),
                        relation="related_to",
                    )
                )

    # Cap to keep the trace scannable.
    return tuple(out[:_MAX_ALTERNATIVES])


def _resolve_title(
    rec_id: str,
    by_id: Mapping[str, dict],
    registry: EvidenceRegistry | None,
) -> str:
    """Return the human-readable title for ``rec_id``.

    Priority: the upstream ``Recommendation.title`` → the
    ``EvidenceRegistry`` label → the rec_id itself.
    Never fabricates a title.
    """
    upstream = by_id.get(rec_id)
    if upstream is not None and upstream.get("title"):
        return str(upstream["title"])
    if registry is not None:
        entry = registry.by_id(f"rec_{_slug(rec_id)}")
        if entry is not None and entry.label:
            return entry.label
    return rec_id


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _slug(value: str) -> str:
    """Reduce ``value`` to a registry-safe slug.

    Mirrors the slug behaviour in
    :mod:`app.services.ai.providers.evidence_registry` —
    lowercase alphanumerics and underscores; everything else
    collapses to ``_``.
    """
    import re
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


__all__ = [
    "build_trace",
    "confidence_label_for",
]

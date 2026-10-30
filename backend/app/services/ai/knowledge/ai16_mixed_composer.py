"""SPRINT AI-16 — Mixed-Question Composition.

When a prompt genuinely combines multiple answer domains — for
example "Explain EBITDA and tell me whether my business is
healthy" or "Compare supplier diversification with inventory
buffering and tell me which is better for reaching ₹3 Cr" — the
existing single-shape composer is the wrong tool. The brief asks
for a 7-section decomposition:

  1. ``general_explanation``   — external / general knowledge.
  2. ``business_interpretation`` — internal business evidence.
  3. ``calculation``           — deterministic numbers.
  4. ``recommendation``        — actionable next step.
  5. ``schemes``               — government-scheme advisory.
  6. ``uncertainty``           — limitations + gaps + caveats.
  7. ``next_action``           — one concrete step.

This module is a **pure mapper**: it reads the
:class:`QuestionUnderstanding` capability tuple (already
derived in AI-11/AI-12), the deterministic envelopes, and the
optional ``SchemeAnswerCard`` payload, and emits an ordered tuple
of :class:`MixedSection` records the renderer can iterate.

The composer never duplicates evidence: each ``evidence_id`` is
bound to at most one section. The composer never invokes an
LLM. The composer never fabricates values — every body line is
sourced from one of the deterministic inputs the AI-15 envelope
already exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Section keys — the brief's seven sections. Order matters: the renderer
# iterates in tuple order.
# ---------------------------------------------------------------------------

SECTION_KEYS: tuple[str, ...] = (
    "general_explanation",
    "business_interpretation",
    "calculation",
    "recommendation",
    "schemes",
    "uncertainty",
    "next_action",
)


# Human-readable title for each section. The renderer renders these as the
# ``h3`` heading inside each ``<section>``.
_SECTION_TITLES: dict[str, str] = {
    "general_explanation": "Background",
    "business_interpretation": "What this means for your business",
    "calculation": "The numbers",
    "recommendation": "What we recommend",
    "schemes": "Government schemes",
    "uncertainty": "Caveats and unknowns",
    "next_action": "Next step",
}


# ---------------------------------------------------------------------------
# Section record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MixedSection:
    """One rendered section of a mixed answer.

    Attributes
    ----------
    key
        One of :data:`SECTION_KEYS`.
    title
        Human-readable heading the renderer displays.
    body_lines
        Ordered tuple of short paragraphs (plain strings). The
        renderer renders these as ``<p>`` or ``<li>`` depending
        on the section key. Empty tuple ⇒ section is skipped.
    source_kind
        ``"internal"`` (computed from the user's business data),
        ``"external"`` (cited from the external knowledge
        corpus), or ``"mixed"`` (both). Drives the
        "From external source" badge.
    evidence_ids
        Ordered, deduped tuple of evidence / calculation IDs this
        section references. The composer guarantees no ID
        appears in more than one section of the same result.
    confidence
        0..1 — min over the section's source confidences.
        Defaults to 0.0 when the section has no sources.
    """

    key: str
    title: str
    body_lines: tuple[str, ...] = ()
    source_kind: str = "internal"
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "body_lines": list(self.body_lines),
            "source_kind": self.source_kind,
            "evidence_ids": list(self.evidence_ids),
            "confidence": float(self.confidence),
        }


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MixedSectionsResult:
    """The composer's output.

    Attributes
    ----------
    sections
        Ordered tuple of :class:`MixedSection` records. Empty
        when the prompt was not mixed.
    is_mixed
        ``True`` iff at least one section was emitted.
    rationale
        One short sentence describing why the composer
        classified this prompt as mixed (or empty when it did
        not).
    """

    sections: tuple[MixedSection, ...] = ()
    is_mixed: bool = False
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "is_mixed": bool(self.is_mixed),
            "rationale": str(self.rationale),
        }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if obj is not None else default


def _capability_contains(capability: tuple[str, ...], *needles: str) -> bool:
    if not capability:
        return False
    upper = tuple(c.upper() for c in capability if c)
    return any(any(n in c for n in needles) for c in upper)


def _envelope_metric(env: Any) -> str:
    return str(_get_attr(env, "metric", "") or "")


def _envelope_value(env: Any) -> Any:
    return _get_attr(env, "value", None)


def _envelope_unit(env: Any) -> str:
    return str(_get_attr(env, "unit", "") or "")


def _envelope_calc_id(env: Any) -> str:
    return str(_get_attr(env, "calculation_id", "") or "")


def _envelope_input_ids(env: Any) -> tuple[str, ...]:
    ids = _get_attr(env, "input_evidence_ids", ()) or ()
    return tuple(str(i) for i in ids)


def _envelope_assumptions(env: Any) -> tuple[str, ...]:
    a = _get_attr(env, "assumptions", ()) or ()
    return tuple(str(x) for x in a)


def _envelope_limitations(env: Any) -> tuple[str, ...]:
    a = _get_attr(env, "limitations", ()) or ()
    return tuple(str(x) for x in a)


def _envelope_confidence(env: Any) -> float:
    try:
        c = float(_get_attr(env, "confidence", 1.0) or 1.0)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, c))


def _format_metric_value(env: Any) -> str:
    """Return a short ``"metric = value unit"`` string for an envelope.

    Handles both numeric and dict-shaped ``value`` fields; falls
    back to a JSON-clean repr when the shape is unfamiliar.
    Never invents values.
    """
    metric = _envelope_metric(env)
    unit = _envelope_unit(env)
    value = _envelope_value(env)
    if value is None:
        return f"{metric}: (no value returned)".strip()
    if isinstance(value, (int, float)):
        if unit:
            return f"{metric}: {value:,.4g} {unit}".rstrip()
        return f"{metric}: {value:,.4g}"
    if isinstance(value, dict):
        # Brief: list the keys the envelope returned so the
        # user sees the actual data, not a fabricated sentence.
        keys = ", ".join(sorted(value.keys())) or "(no fields)"
        return f"{metric}: {keys}"
    return f"{metric}: {value!r}"


def _dedupe_evidence(
    *tuples: tuple[str, ...],
) -> tuple[str, ...]:
    """Ordered dedup across the input tuples."""
    seen: set[str] = set()
    out: list[str] = []
    for tup in tuples:
        for v in tup:
            s = str(v).strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return tuple(out)


# ---------------------------------------------------------------------------
# Section builders — one per key.
# ---------------------------------------------------------------------------
#
# Each builder returns either a populated :class:`MixedSection` or ``None``
# (skip the section). Builders never duplicate evidence IDs — they receive
# a `seen_evidence: set[str]` they MUST update in place.


def _build_general_explanation(
    qu: Any,
    envelopes: tuple[Any, ...],
    external_answer: Any | None,
    seen_evidence: set[str],
) -> MixedSection | None:
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    if not _capability_contains(
        capability, "EXTERNAL", "GENERAL_KNOWLEDGE"
    ) and not external_answer:
        return None

    lines: list[str] = []
    evidence: list[str] = []

    # External-answer envelope takes priority.
    if external_answer is not None:
        ea = external_answer
        headline = str(_get_attr(ea, "headline", "") or "").strip()
        if headline:
            lines.append(headline)
        src = _get_attr(ea, "source_attribution", None)
        if src:
            publisher = str(_get_attr(src, "publisher", "") or "").strip()
            url = str(_get_attr(src, "url", "") or "").strip()
            freshness = str(_get_attr(src, "freshness", "") or "").strip()
            bits: list[str] = []
            if publisher:
                bits.append(f"Source: {publisher}")
            if freshness:
                bits.append(f"freshness: {freshness}")
            if url:
                bits.append(url)
            if bits:
                lines.append(" — ".join(bits))
        # External claims may carry an ID.
        for c in (_get_attr(ea, "claims", ()) or ()):
            cid = str(_get_attr(c, "claim_id", "") or "").strip()
            if cid and cid not in seen_evidence:
                seen_evidence.add(cid)
                evidence.append(cid)

    # Knowledge-retrieval envelope as fallback.
    if not lines:
        for env in envelopes:
            if _get_attr(env, "tool_name", "") != "knowledge_retrieval":
                continue
            text = str(_get_attr(env, "value", "") or "").strip()
            if text:
                lines.append(text)
                for cid in _envelope_input_ids(env):
                    if cid not in seen_evidence:
                        seen_evidence.add(cid)
                        evidence.append(cid)
                break

    if not lines:
        return None

    return MixedSection(
        key="general_explanation",
        title=_SECTION_TITLES["general_explanation"],
        body_lines=tuple(lines),
        source_kind="external" if external_answer else "mixed",
        evidence_ids=tuple(evidence),
    )


def _build_business_interpretation(
    qu: Any,
    envelopes: tuple[Any, ...],
    context: Any | None,
    seen_evidence: set[str],
) -> MixedSection | None:
    business_dependency = str(
        _get_attr(qu, "business_dependency", "none") or "none"
    )
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    is_biz = bool(_get_attr(qu, "is_business_specific", False))

    if business_dependency == "none" and not is_biz:
        return None
    if not _capability_contains(
        capability,
        "BUSINESS_ANALYSIS",
        "BUSINESS_FACT",
        "OPERATIONAL",
        "RISK",
        "RECOMMENDATION",
        "EXPORT",
        "ROADMAP",
        "FINANCIAL",
        "MIXED",
    ) and business_dependency == "none":
        return None

    lines: list[str] = []
    evidence: list[str] = []

    if context is not None:
        industry = str(_get_attr(context, "industry", "") or "").strip()
        if industry:
            lines.append(f"Industry on file: {industry}.")
        location = str(_get_attr(context, "location", "") or "").strip()
        if location:
            lines.append(f"Location on file: {location}.")
        revenue = _get_attr(context, "annual_revenue_inr", None)
        if revenue:
            try:
                lines.append(
                    f"Annual revenue on file: ₹{float(revenue):,.0f}."
                )
            except (TypeError, ValueError):
                pass
        employees = _get_attr(context, "employee_count", None)
        if employees is not None and employees != "":
            lines.append(f"Employee count on file: {employees}.")
        certs = _get_attr(context, "certifications", None)
        if certs:
            if isinstance(certs, (list, tuple)):
                lines.append(
                    "Certifications on file: "
                    + ", ".join(str(c) for c in certs)
                    + "."
                )
            else:
                lines.append(f"Certifications on file: {certs}.")

    # Evidence-IDs from non-knowledge envelopes.
    for env in envelopes:
        if _get_attr(env, "tool_name", "") == "knowledge_retrieval":
            continue
        for cid in (*_envelope_input_ids(env), _envelope_calc_id(env)):
            if cid and cid not in seen_evidence:
                seen_evidence.add(cid)
                evidence.append(cid)

    if not lines and not evidence:
        return None

    return MixedSection(
        key="business_interpretation",
        title=_SECTION_TITLES["business_interpretation"],
        body_lines=tuple(lines),
        source_kind="internal",
        evidence_ids=tuple(evidence),
    )


def _build_calculation(
    qu: Any,
    envelopes: tuple[Any, ...],
    seen_evidence: set[str],
) -> MixedSection | None:
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    requires_calc = bool(_get_attr(qu, "requires_calculation", False))
    requires_forecast = bool(_get_attr(qu, "requires_forecast", False))
    requires_scenario = bool(
        _get_attr(qu, "requires_scenario_analysis", False)
    )

    if (
        not _capability_contains(
            capability, "CALCULATION", "FINANCIAL", "SCENARIO", "FORECAST"
        )
        and not requires_calc
        and not requires_forecast
        and not requires_scenario
    ):
        # No calculation orientation — but a single envelope
        # carrying a numeric value still counts as a calculation
        # section (e.g. a one-shot amount envelope).
        has_numeric_env = any(
            isinstance(_envelope_value(env), (int, float))
            for env in envelopes
        )
        if not has_numeric_env:
            return None

    lines: list[str] = []
    evidence: list[str] = []
    confidences: list[float] = []

    for env in envelopes:
        metric = _envelope_metric(env)
        if not metric:
            continue
        lines.append(_format_metric_value(env))
        for cid in (*_envelope_input_ids(env), _envelope_calc_id(env)):
            if cid and cid not in seen_evidence:
                seen_evidence.add(cid)
                evidence.append(cid)
        confidences.append(_envelope_confidence(env))

    if not lines:
        return None

    confidence = min(confidences) if confidences else 0.0
    return MixedSection(
        key="calculation",
        title=_SECTION_TITLES["calculation"],
        body_lines=tuple(lines),
        source_kind="internal",
        evidence_ids=tuple(evidence),
        confidence=confidence,
    )


def _build_recommendation(
    qu: Any,
    parsed: Any | None,
    seen_evidence: set[str],
) -> MixedSection | None:
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    if not _capability_contains(
        capability, "RECOMMENDATION", "COMPARISON", "ROADMAP"
    ):
        return None

    lines: list[str] = []
    if parsed is not None:
        for rec in _get_attr(parsed, "recommendations", ()) or ():
            title = ""
            if isinstance(rec, str):
                title = rec
            else:
                title = (
                    str(_get_attr(rec, "title", "") or "")
                    or str(_get_attr(rec, "action", "") or "")
                    or str(_get_attr(rec, "statement", "") or "")
                )
            title = title.strip()
            if title:
                lines.append(title)
            if len(lines) >= 3:
                break

    if not lines:
        # Fall back to a generic recommendation frame so the
        # section is never empty when the capability fired.
        complexity = str(_get_attr(qu, "complexity", "moderate") or "")
        if complexity == "scenario":
            lines.append(
                "Treat the calculation above as a scenario estimate, not a "
                "guaranteed outcome; re-run it when the input assumption "
                "changes."
            )
        elif complexity == "strategic":
            lines.append(
                "Pick one lever from the calculation section and run a "
                "12-week pilot before scaling it across the business."
            )
        else:
            lines.append(
                "Apply the next-action section below to act on the "
                "numbers above."
            )

    return MixedSection(
        key="recommendation",
        title=_SECTION_TITLES["recommendation"],
        body_lines=tuple(lines[:3]),
        source_kind="internal",
        evidence_ids=(),  # recommendations cite no specific evidence
    )


def _build_schemes(
    qu: Any,
    scheme_card: Any | None,
    seen_evidence: set[str],
) -> MixedSection | None:
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    if not _capability_contains(capability, "GOVERNMENT_SCHEME", "EXPORT"):
        return None
    if scheme_card is None:
        return None

    lines: list[str] = []
    official_name = str(
        _get_attr(scheme_card, "official_name", "") or ""
    ).strip()
    if official_name:
        lines.append(f"Top scheme to evaluate: {official_name}.")
    authority = str(_get_attr(scheme_card, "authority", "") or "").strip()
    if authority:
        lines.append(f"Authority: {authority}.")
    disposition = _get_attr(scheme_card, "match_disposition", None)
    if disposition is not None:
        # Render the enum value; the renderer layers the
        # disposition_phrase() on top for the user-facing label.
        lines.append(
            f"Disposition (server-side): {getattr(disposition, 'value', disposition)}"
        )
    why = _get_attr(scheme_card, "why_business_may_match", ()) or ()
    if why:
        for w in why[:2]:
            lines.append(f"Match signal: {w}")

    return MixedSection(
        key="schemes",
        title=_SECTION_TITLES["schemes"],
        body_lines=tuple(lines),
        source_kind="external",  # scheme facts come from the external corpus
        evidence_ids=(),
    )


def _build_uncertainty(
    qu: Any,
    envelopes: tuple[Any, ...],
    context: Any | None,
    seen_evidence: set[str],
) -> MixedSection | None:
    unknowns = tuple(_get_attr(qu, "unknowns", ()) or ())
    answer_mode = str(_get_attr(qu, "answer_mode", "") or "")
    requires_scenario = bool(
        _get_attr(qu, "requires_scenario_analysis", False)
    )

    # Aggregate caveats from envelopes.
    env_assumptions: list[str] = []
    env_limitations: list[str] = []
    evidence: list[str] = []
    for env in envelopes:
        for a in _envelope_assumptions(env):
            if a not in env_assumptions:
                env_assumptions.append(a)
        for l in _envelope_limitations(env):
            if l not in env_limitations:
                env_limitations.append(l)
        for cid in (_envelope_input_ids(env), _envelope_calc_id(env)):
            if cid and cid not in seen_evidence:
                # Don't add to evidence — uncertainty cites its
                # own meta, not evidence. But still track so
                # other sections can't double-claim.
                seen_evidence.add(cid)

    lines: list[str] = []

    # Unknowns from the QU.
    if unknowns:
        for u in unknowns[:3]:
            lines.append(f"Missing context: {u}.")
    if context is None and not unknowns:
        lines.append(
            "No business profile is on file; the business-specific "
            "interpretation above is generic."
        )

    # Envelope caveats.
    for a in env_assumptions[:2]:
        lines.append(f"Assumption: {a}")
    for l in env_limitations[:2]:
        lines.append(f"Limitation: {l}")

    # Scenario caveat.
    if requires_scenario or answer_mode == "scenario":
        lines.append(
            "Scenario outputs are estimates, not predictions; re-run "
            "when the input assumption changes."
        )

    if not lines:
        return None

    return MixedSection(
        key="uncertainty",
        title=_SECTION_TITLES["uncertainty"],
        body_lines=tuple(lines),
        source_kind="internal",
        evidence_ids=tuple(evidence),
    )


def _build_next_action(
    qu: Any,
    parsed: Any | None,
    sections: tuple[MixedSection, ...],
) -> MixedSection | None:
    """ALWAYS populated when at least one other section is populated.

    The renderer hides it when ``sections`` is empty so a single
    ``next_action`` card never renders in isolation.
    """
    if not sections:
        return None

    unknowns = tuple(_get_attr(qu, "unknowns", ()) or ())
    lines: list[str] = []
    if unknowns:
        # Surface the most actionable unknown.
        first = unknowns[0]
        lines.append(
            f"Tell UrsBiz your {first.replace('_', ' ')} so the "
            f"calculation above can be tightened."
        )
    else:
        # Pull the first recommendation's title as the next action.
        next_action = ""
        if parsed is not None:
            for rec in _get_attr(parsed, "recommendations", ()) or ():
                title = ""
                if isinstance(rec, str):
                    title = rec
                else:
                    title = str(_get_attr(rec, "title", "") or "") or str(
                        _get_attr(rec, "action", "") or ""
                    )
                if title.strip():
                    next_action = title.strip()
                    break
        if not next_action:
            # Fall back to the calculation / scheme first line.
            for s in sections:
                if s.key in ("calculation", "schemes") and s.body_lines:
                    next_action = (
                        f"Act on: {s.body_lines[0]}"
                    )
                    break
        if not next_action:
            next_action = (
                "Re-state the prompt with the missing context above "
                "and UrsBiz will return a tighter answer."
            )
        lines.append(next_action)

    return MixedSection(
        key="next_action",
        title=_SECTION_TITLES["next_action"],
        body_lines=tuple(lines),
        source_kind="internal",
        evidence_ids=(),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compose_mixed_sections(
    *,
    question_understanding: Any,
    envelopes: tuple[Any, ...] = (),
    context: Any | None = None,
    parsed: Any | None = None,
    scheme_card: Any | None = None,
    external_answer: Any | None = None,
) -> MixedSectionsResult:
    """Return the 7-section composition for a mixed prompt.

    Pure function. Same inputs always return the same
    :class:`MixedSectionsResult`. The orchestrator calls this
    AFTER the AI-15 envelope has been stamped and BEFORE the
    message lands on the wire.

    Decision rule
    -------------

    1. If the QU's ``answer_mode != "mixed"`` AND ``"MIXED"`` is
       not in the capability tuple, return
       ``MixedSectionsResult(is_mixed=False)`` — the existing
       10-section composer handles the answer.
    2. Otherwise, walk the 7 section builders in
       :data:`SECTION_KEYS` order. Builders return ``None`` when
       their pre-conditions fail; the tuple only carries the
       sections that fired.

    Evidence IDs are tracked in a per-call ``seen`` set so no
    evidence appears in more than one section. The renderer
    relies on this to attribute every claim to a single
    section.
    """
    qu = question_understanding
    capability = tuple(_get_attr(qu, "capability", ()) or ())
    answer_mode = str(_get_attr(qu, "answer_mode", "") or "")

    is_mixed_signal = "MIXED" in capability or answer_mode == "mixed"
    if not is_mixed_signal:
        return MixedSectionsResult(
            sections=(),
            is_mixed=False,
            rationale="answer_mode is not 'mixed' and MIXED is not in capability",
        )

    envelopes_tuple = tuple(envelopes or ())
    seen_evidence: set[str] = set()

    built: list[MixedSection] = []
    built.append(
        _build_general_explanation(
            qu, envelopes_tuple, external_answer, seen_evidence
        )
        or MixedSection(key="general_explanation", title="")
    )
    built.append(
        _build_business_interpretation(
            qu, envelopes_tuple, context, seen_evidence
        )
        or MixedSection(key="business_interpretation", title="")
    )
    built.append(
        _build_calculation(qu, envelopes_tuple, seen_evidence)
        or MixedSection(key="calculation", title="")
    )
    built.append(
        _build_recommendation(qu, parsed, seen_evidence)
        or MixedSection(key="recommendation", title="")
    )
    built.append(
        _build_schemes(qu, scheme_card, seen_evidence)
        or MixedSection(key="schemes", title="")
    )
    built.append(
        _build_uncertainty(qu, envelopes_tuple, context, seen_evidence)
        or MixedSection(key="uncertainty", title="")
    )
    built.append(
        _build_next_action(qu, parsed, ())  # placeholder; fill below
        or MixedSection(key="next_action", title="")
    )

    # Drop empty placeholders, but always emit ``next_action``
    # when at least one other section survived.
    non_empty: list[MixedSection] = [s for s in built if s.body_lines]
    non_empty_keys = {s.key for s in non_empty}

    if non_empty and "next_action" not in non_empty_keys:
        next_section = _build_next_action(qu, parsed, tuple(non_empty))
        if next_section is not None:
            non_empty.append(next_section)

    # Drop any next_action we built but won't use.
    final_sections: list[MixedSection] = []
    for s in built:
        if s.key == "next_action":
            if "next_action" in {x.key for x in non_empty}:
                na = next(
                    (x for x in non_empty if x.key == "next_action"),
                    None,
                )
                if na is not None:
                    final_sections.append(na)
            continue
        if s in non_empty:
            final_sections.append(s)

    # Ensure the section order matches SECTION_KEYS.
    order = {k: i for i, k in enumerate(SECTION_KEYS)}
    final_sections.sort(key=lambda s: order.get(s.key, 99))

    rationale = (
        f"answer_mode={answer_mode or 'unset'}; "
        f"capability={','.join(capability) or 'none'}; "
        f"emitted={len(final_sections)}/7 sections"
    )

    return MixedSectionsResult(
        sections=tuple(final_sections),
        is_mixed=bool(final_sections),
        rationale=rationale,
    )


__all__ = [
    "MixedSection",
    "MixedSectionsResult",
    "SECTION_KEYS",
    "compose_mixed_sections",
]

"""SPRINT AI-7 — "What I can tell" verified-facts renderer.

The brief's 4-section Missing Information card layout is::

    What I can tell     — verified facts the assistant DOES know
    What I am missing   — the structured MissingDataObject rows
    Why it matters      — aggregate sentence
    Next step           — prompt the user to fill them

This module produces the **first** section: a list of verified
facts the assistant already has, scoped to the detected intent.
The intent scoping matters — for a hire-affordability prompt, the
"verified facts" should be the dimensions the assistant can speak
to (annual revenue, employee count, DNA archetype, business
score); for an export-expansion prompt it should be the export-
readiness dimensions the assistant has.

The renderer is a pure function. No I/O. The caller passes the
:class:`AssistantContext` and the detected
:class:`QuestionIntent` and gets back a tuple of one-line facts.
Empty tuple when the context carries nothing usable.
"""
from __future__ import annotations

from typing import Any

from ..providers.intent_router import QuestionIntent


def _fmt_inr(value: int) -> str:
    """Format INR as ``₹X.XX Cr`` (1 Cr = 1e7 INR)."""
    if not value:
        return "₹0 Cr"
    return f"₹{value / 10_000_000:.2f} Cr"


def _has(value: Any) -> bool:
    """True iff the value is present and meaningful (mirror of
    :func:`detector._is_missing` without the per-field special
    cases the detector needs for ``analytics_metrics``)."""
    if value is None:
        return False
    if isinstance(value, (int, float)) and value <= 0:
        return False
    if isinstance(value, str) and value.strip().lower() in {
        "", "unknown", "n/a", "na", "—"
    }:
        return False
    if isinstance(value, (tuple, list, dict)) and len(value) == 0:
        return False
    return True


def _context_facts(context: Any) -> tuple[str, ...]:
    """Cross-intent facts the assistant always knows."""
    facts: list[str] = []
    legal = getattr(context, "legal_name", "")
    industry = getattr(context, "industry", "")
    location = getattr(context, "location", "")
    if _has(legal):
        facts.append(f"Business: {legal}")
    if _has(industry) and industry not in ("unknown",):
        facts.append(f"Industry: {industry}")
    if _has(location) and location not in ("unknown",):
        facts.append(f"Location: {location}")
    score = getattr(context, "overall_business_score", 0)
    band = getattr(context, "band", "")
    if score:
        facts.append(f"Business score: {score}/100" + (f" ({band})" if band else ""))
    dna = getattr(context, "dna", None)
    if dna is not None:
        archetype = getattr(dna, "archetype", "") or ""
        match = getattr(dna, "match", 0) or 0
        if archetype and _has(archetype) and archetype != "unknown":
            facts.append(f"DNA archetype: {archetype} ({match}% match)")
    return tuple(facts)


def _hiring_facts(context: Any) -> tuple[str, ...]:
    facts: list[str] = []
    rev = getattr(context, "annual_revenue_inr", 0)
    if _has(rev):
        facts.append(f"Current annual revenue: {_fmt_inr(rev)}")
    headcount = getattr(context, "employee_count", "")
    if _has(headcount) and headcount != "unknown":
        facts.append(f"Current headcount: {headcount}")
    payroll = getattr(context, "monthly_payroll_cost_inr", 0)
    if _has(payroll):
        facts.append(f"Current monthly payroll: {_fmt_inr(payroll * 10_000_000)}")
    cf = getattr(context, "monthly_operating_cash_flow_inr", 0)
    if _has(cf):
        facts.append(f"Current monthly operating cash flow: {_fmt_inr(cf * 10_000_000)}")
    margin = getattr(context, "operating_margin_pct", 0.0)
    if _has(margin):
        facts.append(f"Current operating margin: {margin:.1f}%")
    return tuple(facts)


def _revenue_target_facts(context: Any) -> tuple[str, ...]:
    facts: list[str] = []
    rev = getattr(context, "annual_revenue_inr", 0)
    if _has(rev):
        facts.append(f"Current annual revenue: {_fmt_inr(rev)}")
    target = getattr(context, "target_revenue_inr", 0)
    if _has(target):
        facts.append(f"Target annual revenue: {_fmt_inr(target)}")
        if _has(rev):
            gap = max(0, target - rev)
            facts.append(
                f"Implied gap: {_fmt_inr(gap)} "
                f"({target / max(rev, 1):.2f}× growth)."
            )
    recs = getattr(context, "recommendations", ()) or ()
    if recs:
        facts.append(f"{len(recs)} active recommendations in profile.")
    return tuple(facts)


def _export_facts(context: Any) -> tuple[str, ...]:
    facts: list[str] = []
    history = getattr(context, "export_history", ()) or ()
    if _has(history):
        facts.append(
            "Prior export context: " + ", ".join(str(h) for h in history)
        )
    certs = getattr(context, "certifications", ()) or ()
    if _has(certs):
        facts.append(
            "Certifications on file: " + ", ".join(str(c) for c in certs)
        )
    digital = getattr(context, "digital_presence", ()) or ()
    if _has(digital):
        facts.append(
            "Digital presence: " + ", ".join(str(d) for d in digital)
        )
    return tuple(facts)


def _scheme_facts(context: Any) -> tuple[str, ...]:
    facts: list[str] = []
    schemes = getattr(context, "schemes", ()) or ()
    if schemes:
        facts.append(f"{len(schemes)} scheme matches in profile.")
    return tuple(facts)


_PER_INTENT_FACTS = {
    QuestionIntent.HIRING: _hiring_facts,
    QuestionIntent.REACH_REVENUE_TARGET: _revenue_target_facts,
    QuestionIntent.EXPORT_EXPANSION: _export_facts,
    QuestionIntent.GOVERNMENT_SCHEMES: _scheme_facts,
}


def render_what_i_can_tell(
    context: Any,
    intent: Any,
) -> tuple[str, ...]:
    """Return verified facts the assistant already has for this intent.

    Pure function. Returns an empty tuple when the context carries
    nothing usable. Order: cross-intent facts first (business
    identity), then per-intent facts (numbers the prompt is
    asking about). Deduplicated and capped at 8 — the UI renders
    the first 6 and overflows collapse into a "more" disclosure.
    """
    try:
        if context is None:
            return ()
        facts: list[str] = []
        seen: set[str] = set()
        for line in _context_facts(context):
            if line not in seen:
                facts.append(line)
                seen.add(line)
        intent_fn = _PER_INTENT_FACTS.get(intent)
        if intent_fn is not None:
            for line in intent_fn(context):
                if line not in seen:
                    facts.append(line)
                    seen.add(line)
        return tuple(facts[:8])
    except Exception:  # pragma: no cover — defensive
        return ()
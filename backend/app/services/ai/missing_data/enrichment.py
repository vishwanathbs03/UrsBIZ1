"""SPRINT AI-7 — reactive missing-data enrichment.

When the real LLM answer surfaces an additional gap the proactive
detector missed (e.g. the prompt is borderline and the LLM says "I
can't calculate profit without your monthly operating expenses"),
this module extracts those gaps from the prose and adds them to
the existing row list.

Design rules
------------

  * **Pure function** — never raises, never mutates the input
    tuple, returns a fresh tuple. The wire path is wrapped in
    ``ConversationService`` so a regex bug can't crash the
    endpoint.

  * **Narrow cue list** — the regex matches ONLY sentences that
    start with one of the documented "need" cues. False positives
    ("I don't have a particular recommendation") are guarded
    against with a financial-hint filter.

  * **Dedupe by lowercased field name** — if the proactive
    detector already emitted a row for the same field name, the
    enrichment skips it.

  * **Lower importance** — reactive rows are tagged
    ``importance="MEDIUM"`` (the proactive detector uses HIGH for
    fields the brief explicitly calls out).

  * **Cap at 5** — the prose scan never emits more than 5 new
    rows; beyond that the assistant body is assumed to be
    hallucinating and the rest are dropped.
"""
from __future__ import annotations

import re

from .detector import MissingDataObject


# Cues the LLM prose may emit to flag a missing input. The list
# is intentionally narrow — every cue is a sentence-starter the
# AI-7 brief + H7.8C grounded-prompt contract both produce.
_NEED_CUES: tuple[str, ...] = (
    "i don't have",
    "i do not have",
    "could you share",
    "could you provide",
    "without the",
    "to calculate this we need",
    "to answer this we need",
    "missing:",
    "missing data:",
    "we need your",
    "please share",
)

# Financial / numeric hints the extracted noun phrase must
# contain to count as a missing-data row. Without this filter,
# "I don't have a particular recommendation to make" would be
# misclassified.
_FINANCIAL_HINTS: tuple[str, ...] = (
    "payroll", "salary", "salaries",
    "cash flow", "cashflow",
    "operating margin", "margin",
    "revenue", "turnover",
    "expense", "expenses", "cost", "costs",
    "burn rate", "runway",
    "bank statement", "bank balance",
    "headcount", "fte", "employees", "employee count",
    "target revenue", "target turnover",
    "investment", "loan amount",
    "working capital",
    "gross margin", "net margin",
    "rent", "overhead", "overheads",
    "profit", "loss",
    "itr", "tax filing", "gst filing",
    "kpi", "metric", "metrics",
    "export volume", "order book", "shipment",
    "certification", "iso", "bis", "zed",
    "website", "digital presence",
    "industry", "location", "sub-industry",
)

# Pre-compiled cue regex — sentence boundary is approximated as
# the start of the prose or a sentence terminator (`.`, `!`,
# `?`, `;`, `:`) followed by whitespace, plus one of the cues,
# then 1-200 chars of non-terminator text (the noun phrase we
# extract). ``re.VERBOSE`` (the ``(?x)`` inline form) is
# deliberately omitted — combined with the negated character
# class below it breaks matching under CPython's parser; the
# flags are passed explicitly instead. The boundary alternation
# `(?:^|(?<=[.!?;:])\s+)` is checked at the start; the regex
# engine treats each alternative independently, so lookbehind
# variants are safe in Python 3.
_CUE_RE = re.compile(
    r"(?:^|(?<=[.!?;:])\s+)"
    r"(?P<cue>i don't have|i do not have|could you share|could you provide|"
    r"without the|to calculate this we need|to answer this we need|"
    r"missing:\s*|missing data:\s*|we need your|please share)"
    r"\s+"
    r"(?P<noun>[^\n.!?:;]{1,200})",
    re.IGNORECASE | re.MULTILINE,
)

_HINT_RE = re.compile(
    "|".join(re.escape(h) for h in _FINANCIAL_HINTS),
    re.IGNORECASE,
)


def _extract_noun_phrase(text: str) -> list[str]:
    """Yield noun phrases from the prose using the cue regex."""
    if not text:
        return []
    phrases: list[str] = []
    for m in _CUE_RE.finditer(text):
        cue = m.group("cue")
        noun = m.group("noun").strip().rstrip(",;:")
        if not noun:
            continue
        if not _HINT_RE.search(noun):
            # Skip rows where the noun phrase is not
            # financial/numeric — the cue is incidental prose.
            continue
        # Strip the cue from the noun so the resulting row reads
        # as "monthly operating cash flow" rather than "i don't
        # have monthly operating cash flow".
        cleaned = noun
        for prefix in _NEED_CUES:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].lstrip(" :,-")
        phrases.append(cleaned[:200])
    return phrases


def _slug_field_name(phrase: str) -> str:
    """Convert a noun phrase to a stable field-name slug.

    The brief calls for snake_case field names. The slug is the
    canonical key for dedupe (the proactive detector also emits
    snake_case names).
    """
    cleaned = phrase.lower()
    # Replace non-alphanumeric runs with underscores, then strip
    # the leading + trailing underscores the substitution produces.
    slug = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    return slug[:80] or "unknown"


def enrich_missing_data_from_prose(
    prose: str | None,
    base_list: tuple[MissingDataObject, ...],
    *,
    max_new: int = 5,
) -> tuple[MissingDataObject, ...]:
    """Return ``base_list`` + new reactive rows extracted from prose.

    Reactive rows are tagged ``importance="MEDIUM"`` (the proactive
    detector's HIGH tier is reserved for the brief's named gaps).
    Dedupe is by lowercased field name; the proactive rows win on
    conflict (their importance tier is the source of truth).

    Pure function. Never raises.
    """
    if not prose:
        return base_list
    try:
        phrases = _extract_noun_phrase(prose)
        if not phrases:
            return base_list
        seen: set[str] = {row.field.lower() for row in base_list}
        new_rows: list[MissingDataObject] = []
        for phrase in phrases:
            slug = _slug_field_name(phrase)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            new_rows.append(
                MissingDataObject(
                    field=slug,
                    importance="MEDIUM",
                    reason=phrase or "Surfaced by the assistant's prose.",
                    affects=("prose_surfaced",),
                    suggested_source=(
                        "Provide this in your next message or update "
                        "your Business Profile."
                    ),
                )
            )
            if len(new_rows) >= max_new:
                break
        return base_list + tuple(new_rows)
    except Exception:  # pragma: no cover — defensive
        return base_list
"""SPRINT AI-16 — Scheme-Card Orchestrator.

Thin wrapper around :class:`SchemeAnswerCardBuilder`. The
builder (in ``scheme_answer_card.py``) knows how to assemble one
card for a known scheme ID + user context. This wrapper adds:

  * Capability / literal-question gating — only attempt to build
    a card when the QU genuinely asked about a scheme.
  * Scheme-ID selection — a small keyword scan that maps the
    literal question to one of the 5 supported schemes (MUDRA /
    PMEGP / CGTMSE / TReDS / Udyam). When the literal names
    nothing, fall back to Udyam Registration — the universal
    MSME entry point.
  * The brief's 4-tier disposition phrasing on top of the
    builder's 3-value ``MatchDisposition`` enum.
  * A safe ``None`` return when nothing qualifies — never
    fabricate a card.

The module is pure (no I/O). Failures inside
:class:`SchemeAnswerCardBuilder` (missing source, unknown
scheme id) bubble up as ``None``; the orchestrator's fenced
try/except handles any exception the LLM-path might surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Scheme selection — keyword scan over the literal question.
# ---------------------------------------------------------------------------
#
# Order matters: more specific keywords first so a prompt that
# says "Mudra loan for working capital" picks MUDRA (not the
# generic Udyam fallback). Each tuple is (scheme_id, keywords).

_SCHEME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "mudra",
        (
            "mudra",
            "pmmy",
            "shishu",
            "kishore",
            "tarun",
            "micro units",
        ),
    ),
    (
        "pmegp",
        (
            "pmegp",
            "kvic",
            "project cost",
            "self-help group",
            "employment generation",
        ),
    ),
    (
        "cgtmse",
        (
            "cgtmse",
            "credit guarantee",
            "collateral-free",
            "collateral free",
            "guarantee cover",
            "sidbi",
        ),
    ),
    (
        "treds",
        (
            "treds",
            "receivables discounting",
            "rxil",
            "invoice discounting",
            "corporate buyer",
        ),
    ),
    (
        "udyam",
        (
            "udyam",
            "msme registration",
            "register msme",
            "msme certificate",
            "udyam registration",
        ),
    ),
)


def select_scheme_id(literal_question: str) -> str | None:
    """Return a supported scheme ID for the literal question.

    Returns ``"udyam"`` (the universal MSME entry point) when
    the prompt mentions a scheme but does not name a specific
    one. Returns ``None`` when the prompt is not scheme-shaped
    at all (caller should not invoke the builder).
    """
    text = (literal_question or "").lower()

    # Specific match — first tuple wins.
    for scheme_id, keywords in _SCHEME_KEYWORDS:
        if any(kw in text for kw in keywords):
            return scheme_id

    # Generic scheme-shaped prompt — fall back to Udyam.
    scheme_cues = (
        "scheme", "schemes", "subsidy", "msme", "eligibility",
        "eligible", "funding", "loan", "government",
    )
    if any(cue in text for cue in scheme_cues):
        return "udyam"

    return None


# ---------------------------------------------------------------------------
# Disposition phrasing — the brief's 4-tier phrasing on top of the
# 3-value MatchDisposition enum.
# ---------------------------------------------------------------------------
#
# The brief mandates the renderer only uses one of four phrases:
#
#   * "Likely match based on available data."
#   * "Appears eligible based on available data."
#   * "Requires verification to confirm eligibility."
#   * "Insufficient information to determine eligibility."
#
# We map the existing enum + the optional matching score to one
# of the four phrases. The backend passes the enum + score on
# the wire; the frontend renders the phrase directly.

# Aliases kept here so the renderer can do an exact string match.
DISPOSITION_PHRASE_LIKELY_MATCH: str = (
    "Likely match based on available data."
)
DISPOSITION_PHRASE_APPEARS_ELIGIBLE: str = (
    "Appears eligible based on available data."
)
DISPOSITION_PHRASE_REQUIRES_VERIFICATION: str = (
    "Requires verification to confirm eligibility."
)
DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION: str = (
    "Insufficient information to determine eligibility."
)

# Threshold above which a potential match is promoted to
# "likely match". 80 mirrors the schemes_sprint16_service's
# "high-priority" similarity score cutoff.
_LIKELY_MATCH_THRESHOLD: int = 80
_APPEARS_ELIGIBLE_THRESHOLD: int = 50


def disposition_phrase(
    disposition: Any,
    matching_score: int | None = None,
) -> str:
    """Return one of the brief's four disposition phrases.

    Parameters
    ----------
    disposition
        A :class:`MatchDisposition` enum value, or its raw
        ``.value`` string (``"potential_match"``,
        ``"gap_unknown"``, ``"conflict"``).
    matching_score
        Optional integer similarity score (0..100) sourced
        from the scheme catalog ranker. Used only when the
        disposition is ``POTENTIAL_MATCH`` to decide between
        "likely match" and "appears eligible".

    The function never returns a custom phrase — it always
    returns one of the four canonical strings so the renderer
    can do an exact match.
    """
    # Coerce enum-or-string.
    raw: str
    if hasattr(disposition, "value"):
        raw = str(disposition.value or "")
    else:
        raw = str(disposition or "").strip().lower()

    score: int | None
    if matching_score is None:
        score = None
    else:
        try:
            score = int(matching_score)
        except (TypeError, ValueError):
            score = None

    if raw == "potential_match":
        if score is not None and score >= _LIKELY_MATCH_THRESHOLD:
            return DISPOSITION_PHRASE_LIKELY_MATCH
        if score is not None and score >= _APPEARS_ELIGIBLE_THRESHOLD:
            return DISPOSITION_PHRASE_APPEARS_ELIGIBLE
        # No score on file — be conservative and ask for
        # verification rather than asserting likelihood.
        return DISPOSITION_PHRASE_REQUIRES_VERIFICATION

    if raw == "conflict":
        # Two eligibility signals disagree — explicit ask for
        # verification rather than a guess.
        return DISPOSITION_PHRASE_REQUIRES_VERIFICATION

    # gap_unknown — eligibility signals are missing.
    return DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION


def disposition_phrase_for_card(card: Any) -> str:
    """Convenience wrapper that reads the disposition + score
    straight off a :class:`SchemeAnswerCard`.
    """
    if card is None:
        return DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION
    disposition = getattr(card, "match_disposition", None)
    # The card does not carry a matching score today; the
    # service-side score lives on the SchemeItem from the
    # catalog ranker. Callers that have the score can pass it
    # via :func:`disposition_phrase` directly.
    return disposition_phrase(disposition, matching_score=None)


# ---------------------------------------------------------------------------
# Orchestrator wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemeCardPayload:
    """Container for the card + the renderer phrase.

    The orchestrator returns this so the service layer can
    stamp both pieces onto the wire envelope in one pass.
    """

    card: Any  # SchemeAnswerCard (avoid import cycle)
    phrase: str  # one of DISPOSITION_PHRASE_*


def compose_scheme_card(
    *,
    question_understanding: Any,
    context: Any | None = None,
) -> SchemeCardPayload | None:
    """Build a :class:`SchemeCardPayload` for the prompt.

    Returns ``None`` when:

      * the QU capability does not contain ``GOVERNMENT_SCHEME``,
      * the literal question names no scheme and no scheme cue,
      * the builder raises (unknown scheme id, no verified
        source, etc.).

    Pure function. No I/O. Same inputs ⇒ same return.
    """
    # Capability gate — only build when the QU flagged the
    # question as scheme-shaped.
    capability = tuple(
        getattr(question_understanding, "capability", ()) or ()
    )
    if "GOVERNMENT_SCHEME" not in capability and "EXPORT" not in capability:
        return None

    literal = str(
        getattr(question_understanding, "literal_question", "") or ""
    )
    scheme_id = select_scheme_id(literal)
    if scheme_id is None:
        return None

    # Build the card. Any builder exception (unknown scheme id,
    # missing external source, etc.) bubbles up as None — the
    # orchestrator must never fabricate.
    try:
        from app.services.ai.knowledge.scheme_answer_card import (
            SchemeAnswerCardBuilder,
        )
        builder = SchemeAnswerCardBuilder()
        card = builder.build(scheme_id, context=context)
    except Exception:
        return None

    phrase = disposition_phrase(
        getattr(card, "match_disposition", None),
        matching_score=None,
    )
    return SchemeCardPayload(card=card, phrase=phrase)


__all__ = [
    "DISPOSITION_PHRASE_LIKELY_MATCH",
    "DISPOSITION_PHRASE_APPEARS_ELIGIBLE",
    "DISPOSITION_PHRASE_REQUIRES_VERIFICATION",
    "DISPOSITION_PHRASE_INSUFFICIENT_INFORMATION",
    "SchemeCardPayload",
    "compose_scheme_card",
    "disposition_phrase",
    "disposition_phrase_for_card",
    "select_scheme_id",
]

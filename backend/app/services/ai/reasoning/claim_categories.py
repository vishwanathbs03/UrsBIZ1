"""ClaimCategory — SPRINT AI-1 Stage 7.

The legacy :class:`~app.services.ai.providers.grounding_validator.GroundingValidator`
and :class:`~app.services.ai.providers.open_response_validator.OpenResponseValidator`
score the LLM's response for *groundedness* (does every claim
trace back to an evidence entry?) but they do NOT separate the
*kind* of claim the model made. A model that says "your
revenue is ₹1.8 Cr" is making a ``FACT`` claim; a model that
says "if you grow 30%, revenue becomes ₹2.34 Cr" is making a
``SCENARIO`` claim; a model that says "I recommend you hire
five employees" is making a ``RECOMMENDATION`` claim.

Different categories carry different truth conditions:

  * ``FACT`` — must match an evidence entry verbatim.
  * ``CALCULATION`` — must match an authoritative deterministic
    engine output (or be a pure arithmetic identity).
  * ``INFERENCE`` — must be supportable from the evidence
    chain.
  * ``RECOMMENDATION`` — must reference a ``rec_*`` evidence id.
  * ``SCENARIO`` — must declare its assumptions.
  * ``EXTERNAL_FACT`` — must NOT appear in grounded mode
    (external knowledge that the registry does not contain).
  * ``UNKNOWN`` — when the model says "I don't know".

The validators stamp the categories they observe on the
response envelope so the audit trail can answer "what kinds of
claims did the model make?" and so future validation rules
can fire on the right category without having to re-parse the
prose.

Backward compatibility
----------------------

The validators' existing rule sets (H7.8C's 18 grounding
rules and 4 open-mode rules) are unchanged. The new
``_CATEGORY_RULES`` tuple is appended to the existing
``score_breakdown`` list — the additive contract is
preserved. Existing tests that assert
``sum(breakdown scores) == report.score`` keep working
because the new rules contribute positive scores within the
``[0, 100]`` clamp.
"""
from __future__ import annotations

from typing import Literal


# --------------------------------------------------------------------------- #
# Literal type + ordered label list
# --------------------------------------------------------------------------- #


ClaimCategory = Literal[
    "FACT",
    "CALCULATION",
    "INFERENCE",
    "RECOMMENDATION",
    "SCENARIO",
    "EXTERNAL_FACT",
    "UNKNOWN",
]


# The full list of category labels, in priority order. The
# validators use this when deduping the categories they
# observed (priority order = first occurrence wins).
CATEGORY_LABELS: tuple[str, ...] = (
    "FACT",
    "CALCULATION",
    "INFERENCE",
    "RECOMMENDATION",
    "SCENARIO",
    "EXTERNAL_FACT",
    "UNKNOWN",
)


# --------------------------------------------------------------------------- #
# Heuristic categoriser
# --------------------------------------------------------------------------- #


_FACT_OPENERS = (
    "your revenue is", "your revenue was", "your score is",
    "your score was", "your business", "your industry",
    "your location", "you have", "you are",
    "your target", "the score is", "the rule fires",
)
_CALCULATION_KEYWORDS = (
    "growth multiple", "roi", "emi", "gst", "tax",
    "₹", "inr", "crore", "lakh",
    "calculate", "equals", "computed", "totals to",
    "summing", "sum of", "multiplied by", "divided by",
)
_INFERENCE_KEYWORDS = (
    "therefore", "this suggests", "implies", "indicates",
    "likely", "probably", "may be", "could be",
    "based on", "given that",
)
_RECOMMENDATION_KEYWORDS = (
    "i recommend", "we recommend", "you should",
    "next step", "first step", "start with",
    "priority is", "consider", "consider doing",
    "we suggest", "action item", "todo",
)
_SCENARIO_KEYWORDS = (
    "if you", "if your", "if the", "if we",
    "scenario", "what if", "suppose", "imagine",
    "would become", "would be", "could grow to",
    "sensitivity", "best case", "worst case",
    "increase by", "decrease by", "rise by", "fall by",
)
_EXTERNAL_FACT_KEYWORDS = (
    "according to google", "according to wikipedia",
    "i read that", "studies show", "research shows",
    "experts say", "globally", "worldwide",
    "industry standard", "best practice says",
)
_UNKNOWN_KEYWORDS = (
    "i don't know", "i do not know", "i'm not sure",
    "cannot determine", "can't determine",
    "i'm unable to", "i am unable to",
    "no information", "insufficient information",
    "would need more", "need more information",
    "missing", "i lack",
)


def categorize_claim(text: str, context: object = None) -> ClaimCategory:
    """Classify a piece of prose into a :data:`ClaimCategory`.

    Pure function. No I/O. Used by the validators to label
    the claims the model made.

    The categorisation is heuristic. When the text matches
    multiple category keywords, the priority order is:

      1. UNKNOWN — when the model says "I don't know", always
         wins (the prompt contract is satisfied by an explicit
         admission rather than an invented answer).
      2. RECOMMENDATION — actionable language always overrides
         description.
      3. SCENARIO — conditional / hypothetical language.
      4. CALCULATION — arithmetic / number-anchored language.
      5. INFERENCE — reasoning language.
      6. FACT — declarative statement of profile state.
      7. EXTERNAL_FACT — last resort, when the prose references
         sources the registry does not contain.
      8. UNKNOWN — fallback when nothing matches.
    """
    if not text or not text.strip():
        return "UNKNOWN"
    lower = text.lower()

    # 1. UNKNOWN — explicit admission wins.
    if any(kw in lower for kw in _UNKNOWN_KEYWORDS):
        return "UNKNOWN"

    # 2. RECOMMENDATION — actionable / imperative.
    if any(kw in lower for kw in _RECOMMENDATION_KEYWORDS):
        return "RECOMMENDATION"

    # 3. SCENARIO — conditional / hypothetical.
    if any(kw in lower for kw in _SCENARIO_KEYWORDS):
        return "SCENARIO"

    # 4. CALCULATION — arithmetic / number-anchored.
    if any(kw in lower for kw in _CALCULATION_KEYWORDS):
        return "CALCULATION"

    # 5. INFERENCE — reasoning.
    if any(kw in lower for kw in _INFERENCE_KEYWORDS):
        return "INFERENCE"

    # 6. EXTERNAL_FACT — references to outside sources.
    if any(kw in lower for kw in _EXTERNAL_FACT_KEYWORDS):
        return "EXTERNAL_FACT"

    # 7. FACT — declarative.
    if any(kw in lower for kw in _FACT_OPENERS):
        return "FACT"

    # 8. Fallback
    return "UNKNOWN"
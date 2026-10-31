"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

External-only question handler.

When the user asks "What is EBITDA?" the answer should NOT invoke
the health score engine, the finance profile, or the
recommendation engine. It should pull from the verified
external knowledge base and stay concise.

The handler is the entry point for the
``business_dependency == "none"`` / ``answer_mode ==
"general_knowledge"`` case. It produces a small, data-only
envelope; the renderer composes the visual answer.

The four parts of the envelope
------------------------------

  1. ``headline`` — one short sentence (the answer).
  2. ``source_attribution`` — publisher + URL + freshness.
  3. ``business_relevance_note`` — when the user's profile
     could be enriched by the answer, a one-liner suggests it.
     Never asserted; the user must opt in.
  4. ``disclaimer`` — when the source is not FRESH, the
     envelope surfaces the staleness explicitly. The brief:
     "say so explicitly. Do not fabricate dates, rules,
     benefits or links."

What the handler never does
---------------------------

  * Never invokes the finance / health / recommendation
    services.
  * Never falls back to LLM-written prose. When the corpus
    returns no match, the envelope's ``headline`` carries the
    ``empty_reason`` verbatim.
  * Never asserts the user's business data is X. The
    business_relevance_note is a suggestion, not an assertion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ai.knowledge.external_knowledge_base import (
    ExternalKnowledgeRetriever,
    RetrievalResult,
)
from app.services.ai.knowledge.external_types import (
    ClaimKind,
    ExternalSource,
)


# Phrases that mean "this is a definition prompt" — kept
# short and case-insensitive. The handler uses them to keep
# the answer concise.
_DEFINITION_CUES: tuple[str, ...] = (
    "what is", "what are", "what does", "what do",
    "define ", "meaning of", "explain ", "tell me about",
)


# Topics that would benefit from a one-line business
# relevance suggestion. The suggestion is opt-in; the user
# is never told the assistant "ran an analysis".
_BUSINESS_RELEVANCE_HINTS: dict[str, str] = {
    "ebitda": (
        "If you would like, UrsBiz can compute your business's "
        "EBITDA from your income statement next."
    ),
    "working_capital": (
        "If you would like, UrsBiz can project your working "
        "capital gap from your current assets and liabilities."
    ),
    "gst": (
        "If you would like, UrsBiz can summarise your GST "
        "filing cadence against your transaction history."
    ),
    "reach": (
        "If you would like, UrsBiz can check your current "
        "certifications against REACH requirements for your export markets."
    ),
    "brsr": (
        "If you would like, UrsBiz can outline which BRSR "
        "indicators your business profile already covers."
    ),
}


@dataclass(frozen=True)
class ExternalAnswerEnvelope:
    """Pure-data envelope the renderer composes from.

    ``headline`` is a single sentence. ``supporting`` carries
    additional sentences the corpus returned (kept short —
    the brief mandates "the answer should remain concise").
    """

    headline: str = ""
    supporting: tuple[str, ...] = ()
    source: ExternalSource | None = None
    authority_weight: float = 0.0
    freshness_status: str = ""
    is_verified: bool = False
    business_relevance_note: str = ""
    disclaimer: str = ""
    retrieval: RetrievalResult | None = None
    is_empty: bool = False
    empty_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "supporting": list(self.supporting),
            "source": self.source.to_dict() if self.source else None,
            "authority_weight": self.authority_weight,
            "freshness_status": self.freshness_status,
            "is_verified": self.is_verified,
            "business_relevance_note": self.business_relevance_note,
            "disclaimer": self.disclaimer,
            "is_empty": self.is_empty,
            "empty_reason": self.empty_reason,
        }


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #


class ExternalQuestionHandler:
    """Render concise, verified answers to definition-style prompts.

    The handler is the answer path for ``business_dependency ==
    "none"``. It does NOT touch the user's business profile —
    no health score, no finance, no recommendations.

    Concision rule
    --------------

    The brief: "The answer should remain concise." The handler
    therefore returns at most 2 sentences in ``headline`` and
    at most 1 sentence in ``supporting`` (the corpus
    sentences are usually one or two long sentences; we keep
    the first sentence as the headline, the rest as
    supporting).
    """

    def __init__(self, retriever: ExternalKnowledgeRetriever | None = None) -> None:
        self._retriever = retriever or ExternalKnowledgeRetriever()

    def is_definition_prompt(self, prompt: str) -> bool:
        """True when the prompt looks like a definition request."""
        text = (prompt or "").lower().strip()
        return any(text.startswith(c) for c in _DEFINITION_CUES)

    def handle(
        self, prompt: str, *, context: Any = None
    ) -> ExternalAnswerEnvelope:
        """Return the verified, concise answer envelope.

        ``context`` is unused today — accepted for forward
        compatibility. The handler never reads from it (the
        brief: "Do not invoke health score, finance profile,
        recommendation engine, etc.").
        """
        retrieval = self._retriever.retrieve(prompt)
        if retrieval.is_empty:
            return ExternalAnswerEnvelope(
                is_empty=True,
                empty_reason=retrieval.empty_reason,
                retrieval=retrieval,
            )

        # Pick the highest-authority claim; ties broken by
        # FRESH > AGING > UNKNOWN > STALE.
        freshness_rank = {"fresh": 0, "aging": 1, "unknown": 2, "stale": 3}

        def _score(claim: ClassifiedClaim) -> tuple[int, float]:
            if claim.source is None:
                return (99, 0.0)
            return (
                freshness_rank[claim.source.freshness_status.value],
                -claim.authority,
            )

        best = min(retrieval.matches, key=_score)
        source = best.source

        # Split the claim text into sentences; keep one in the
        # headline, the rest in supporting (cap at 1).
        sentences = [
            s.strip() for s in best.text.split(".") if s.strip()
        ]
        headline = (sentences[0] + ".") if sentences else best.text
        supporting = tuple(
            (s + ".") for s in sentences[1:2]
        )

        relevance = self._business_relevance(retrieval.query_tags, context)
        disclaimer = self._disclaimer(best, source)

        return ExternalAnswerEnvelope(
            headline=headline,
            supporting=supporting,
            source=source,
            authority_weight=best.authority,
            freshness_status=(
                source.freshness_status.value if source else "unknown"
            ),
            is_verified=best.is_verified,
            business_relevance_note=relevance,
            disclaimer=disclaimer,
            retrieval=retrieval,
        )

    # --- internals ------------------------------------------------------ #

    def _business_relevance(self, query_tags: tuple[str, ...], context: Any) -> str:
        """One-line opt-in suggestion to personalise the answer.

        The user is never told the assistant already did an
        analysis. The line uses "If you would like" so the
        user retains control.
        """
        for tag in query_tags:
            note = _BUSINESS_RELEVANCE_HINTS.get(tag)
            if note:
                return note
        return ""

    def _disclaimer(self, claim: ClassifiedClaim, source: ExternalSource | None) -> str:
        """Surface staleness explicitly when present.

        The brief: "If current information cannot be verified,
        say so explicitly." The handler surfaces a one-line
        note whenever the freshness is not FRESH.
        """
        if source is None:
            return "External source not provided."
        if source.freshness_status.value == "fresh":
            return ""
        if source.freshness_status.value == "aging":
            return (
                f"Source last published {source.published_at}. "
                "Approaching the safe window for this category. "
                "Re-verify with the publisher before relying on it."
            )
        if source.freshness_status.value == "stale":
            return (
                f"Source last published {source.published_at} — beyond the "
                f"{source.category.value} safe window. Treat this as "
                "unverified; consult the publisher directly."
            )
        return (
            "No published_at available for this source; freshness "
            "cannot be confirmed."
        )

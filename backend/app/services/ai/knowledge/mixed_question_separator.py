"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Mixed-question separator.

A mixed question asks both:

  * "what is X" (external, general knowledge), AND
  * "how does it apply to my business" (internal evidence).

The separator splits the question into the two streams so the
answer can:

  1. Answer the external part with a verified source, AND
  2. Answer the business part with UrsBiz's internal evidence,
  3. State the gap between the two, AND
  4. Conclude what can and cannot currently be concluded.

The four-block output
---------------------

  * ``external_block``   — what UrsBiz knows from external sources
  * ``business_block``   — what UrsBiz knows from internal evidence
  * ``gap_block``        — what is missing to fully answer
  * ``conclusion_block`` — what can and cannot be concluded

The blocks are pure data (no Markdown). The renderer composes
the final answer. The separator NEVER mixes the two streams —
business evidence never appears in ``external_block``, and
external sources never appear in ``business_block``.

Mixed-question detection
------------------------

A prompt is "mixed" when:

  1. It contains an external-information cue (``what is``,
     ``explain``, ``reach``, ``ebitda``, ``certification``,
     ``compliance``, ...), AND
  2. It also contains a business-specific cue (``my``,
     ``our``, ``i should``, ``we are``, ...).

When both fire, ``is_mixed=True`` and ``split`` returns all
four blocks. When only (1) fires, the prompt is pure external
and the ``ExternalQuestionHandler`` (separate module) takes
over. When only (2) fires, the prompt is pure business and
the existing pipeline carries on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.ai.knowledge.external_knowledge_base import (
    ExternalKnowledgeRetriever,
    RetrievalResult,
)


# --------------------------------------------------------------------------- #
# Cue lists
# --------------------------------------------------------------------------- #


_EXTERNAL_CUES: tuple[str, ...] = (
    "what is", "what are", "what does", "what do",
    "explain", "define", "meaning of", "tell me about",
    "reach compliance", "reach ", "ebitda", "brsr", "gst ",
    "bis ", "certification", "compliance", "regulation",
    "scheme", "schemes", "subsidy", "mudra", "pmegp",
    "cgtmse", "treds", "udyam",
    "iso ", "fssai", "fda ", "iec", "european union",
    "rule ", "act ",
)
_BUSINESS_CUES: tuple[str, ...] = (
    "my business", "my company", "our business", "our company",
    "my revenue", "our revenue", "my margin", "our margin",
    "my working capital", "our working capital",
    "my employees", "our employees", "my team", "our team",
    "my product", "our product", "my factory", "our factory",
    "i should", "we should", "should i", "should we",
    "are we ready", "am i ready", "do we", "do i",
    "we are", "i am", "currently", "today",
)


# --------------------------------------------------------------------------- #
# Mixed-question result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MixedAnswerBlocks:
    """The four-block output of a mixed question.

    Each block is a list of short paragraphs (plain strings).
    The renderer composes them with headers. The separator
    NEVER merges business + external streams into a single
    paragraph.
    """

    external_block: tuple[str, ...] = ()
    business_block: tuple[str, ...] = ()
    gap_block: tuple[str, ...] = ()
    conclusion_block: tuple[str, ...] = ()
    is_mixed: bool = False
    retrieval: RetrievalResult | None = None


# --------------------------------------------------------------------------- #
# Separator
# --------------------------------------------------------------------------- #


class MixedQuestionSeparator:
    """Split a mixed prompt into external + business + gap + conclusion.

    Pure. No I/O. No LLM access. Safe to call from anywhere in
    the reasoning pipeline.

    Usage
    -----

    ::

        sep = MixedQuestionSeparator()
        retriever = ExternalKnowledgeRetriever()
        if sep.is_mixed(prompt):
            blocks = sep.split(prompt, context=ctx, retriever=retriever)
            # render blocks.external_block / business_block / ...

    The ``context`` kwarg is optional; when supplied, the
    business block is enriched with the user's profile signals.
    """

    def has_external_cue(self, prompt: str) -> bool:
        """True when the prompt carries an external-information cue."""
        text = (prompt or "").lower()
        return any(cue in text for cue in _EXTERNAL_CUES)

    def has_business_cue(self, prompt: str) -> bool:
        """True when the prompt carries a business-specific cue."""
        text = (prompt or "").lower()
        return any(cue in text for cue in _BUSINESS_CUES)

    def is_mixed(self, prompt: str) -> bool:
        """True when both external and business cues fire."""
        return self.has_external_cue(prompt) and self.has_business_cue(prompt)

    def split(
        self,
        prompt: str,
        *,
        context: Any = None,
        retriever: ExternalKnowledgeRetriever | None = None,
    ) -> MixedAnswerBlocks:
        """Produce the four-block output for a mixed question.

        The function is total — when the retriever returns no
        matches, the external block surfaces the
        ``empty_reason`` instead of fabricating an answer. The
        conclusion block is conservative: it says "we cannot
        fully answer" rather than guessing.
        """
        if not self.is_mixed(prompt):
            return MixedAnswerBlocks(is_mixed=False)

        retriever = retriever or ExternalKnowledgeRetriever()
        retrieval = retriever.retrieve(prompt)

        external_lines: list[str] = []
        if retrieval.is_empty:
            external_lines.append(retrieval.empty_reason)
        else:
            for c in retrieval.matches:
                src = c.source
                line = c.text
                # Add provenance inline so the user can verify
                # without opening a second panel.
                if src is not None:
                    line += (
                        f"  (Source: {src.publisher}, {src.authority_level.label}; "
                        f"freshness: {src.freshness_status.value}; "
                        f"verified: {c.is_verified}.)"
                    )
                external_lines.append(line)

        business_lines = self._business_block(prompt, context)
        gap_lines = self._gap_block(prompt, context, retrieval)
        conclusion_lines = self._conclusion_block(retrieval, business_lines, gap_lines)

        return MixedAnswerBlocks(
            external_block=tuple(external_lines),
            business_block=tuple(business_lines),
            gap_block=tuple(gap_lines),
            conclusion_block=tuple(conclusion_lines),
            is_mixed=True,
            retrieval=retrieval,
        )

    # --- internals ------------------------------------------------------ #

    def _business_block(self, prompt: str, context: Any) -> list[str]:
        """Render the internal-evidence side of the answer.

        Mirrors the brief: never mix external information with
        internal business evidence. When the context is missing
        critical fields (industry, revenue), say so explicitly
        rather than guess.
        """
        lines: list[str] = []
        industry = getattr(context, "industry", None) if context is not None else None
        revenue = (
            getattr(context, "annual_revenue_inr", None) if context is not None else None
        )
        certs = (
            getattr(context, "certifications", None) if context is not None else None
        )
        location = (
            getattr(context, "location", None) if context is not None else None
        )

        if not industry and not revenue:
            lines.append(
                "UrsBiz does not currently have a business profile to compare against."
            )
            return lines

        if industry:
            lines.append(f"Industry on file: {industry}.")
        if location:
            lines.append(f"Location on file: {location}.")
        if revenue:
            lines.append(
                f"Annual revenue on file: ₹{revenue:,.0f}."
            )
        if certs:
            lines.append(f"Certifications on file: {', '.join(certs)}.")
        else:
            lines.append(
                "Certifications on file: none — UrsBiz cannot confirm "
                "compliance against external regulations without this."
            )

        return lines

    def _gap_block(
        self,
        prompt: str,
        context: Any,
        retrieval: RetrievalResult,
    ) -> list[str]:
        """What is missing to fully answer the question.

        The brief: "what evidence is missing." A gap is a field
        the answer requires but UrsBiz does not have. The
        function never invents a field.
        """
        gaps: list[str] = []
        text = (prompt or "").lower()

        # External gaps
        if retrieval.is_empty:
            gaps.append(
                "External source: UrsBiz could not verify the external "
                "fact with the available sources. We do not assert it."
            )
        elif any(
            c.source and c.source.freshness_status.value in ("aging", "stale", "unknown")
            for c in retrieval.matches
        ):
            gaps.append(
                "External source: one or more sources are past their "
                "safe window. Re-verify with the publisher before relying "
                "on the answer."
            )

        # Business gaps
        if context is None:
            gaps.append("Business profile: not provided.")
        else:
            if "export" in text or "certification" in text:
                if not getattr(context, "certifications", None):
                    gaps.append(
                        "Business profile: certifications list is empty. "
                        "Cannot confirm readiness against external "
                        "regulations."
                    )
            if "scheme" in text or "eligibility" in text or "subsidy" in text:
                if not getattr(context, "udyam_number", None) and not getattr(
                    context, "is_registered_msme", None
                ):
                    gaps.append(
                        "Business profile: Udyam / MSME registration not "
                        "on file. Scheme eligibility cannot be confirmed."
                    )
            if "revenue" in text and not getattr(
                context, "annual_revenue_inr", None
            ):
                gaps.append(
                    "Business profile: annual revenue not on file."
                )
        return gaps

    def _conclusion_block(
        self,
        retrieval: RetrievalResult,
        business_lines: list[str],
        gap_lines: list[str],
    ) -> list[str]:
        """What can and cannot currently be concluded.

        The brief: "what can and cannot currently be concluded."
        The conclusion is conservative — when gaps exist, the
        answer says "we cannot fully conclude" rather than
        guessing.
        """
        lines: list[str] = []
        if retrieval.is_empty:
            lines.append(
                "Conclusion: UrsBiz cannot answer the external part of "
                "your question from verified sources. We are also missing "
                "internal context. Please provide more information or "
                "consult the relevant authority directly."
            )
            return lines
        if gap_lines:
            lines.append(
                "Conclusion: UrsBiz can describe the external concept "
                "from a verified source. The readiness assessment requires "
                "additional business profile fields, so we cannot give a "
                "definitive yes/no at this time."
            )
        else:
            lines.append(
                "Conclusion: UrsBiz can answer both the external concept "
                "and the business readiness from current verified sources. "
                "No additional information is required."
            )
        return lines

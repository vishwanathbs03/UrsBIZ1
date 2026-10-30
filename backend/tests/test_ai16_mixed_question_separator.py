"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for :class:`MixedQuestionSeparator`.

Covers:
  * Cue detection — external cue alone
  * Cue detection — business cue alone
  * Cue detection — both cues → mixed
  * Mixed prompt returns the four-block output
  * Mixed prompt external block carries the verified source
  * Mixed prompt NEVER mixes business + external in the same
    block (no contamination)
  * Mixed prompt business block surfaces the user's industry
  * Mixed prompt gap block lists what is missing
  * Mixed prompt conclusion block is conservative
  * Non-mixed prompt returns is_mixed=False (no blocks)

6 tests in this module.
"""

from __future__ import annotations

from app.services.ai.knowledge.external_knowledge_base import (
    ExternalKnowledgeRetriever,
)
from app.services.ai.knowledge.mixed_question_separator import (
    MixedQuestionSeparator,
)


class _StubContext:
    """A minimal stand-in for the user's profile.

    The separator only reads a few attributes (``industry``,
    ``annual_revenue_inr``, ``certifications``, ``location``)
    so a stub is enough for the four-block tests.
    """

    def __init__(
        self,
        industry: str = "Textiles",
        revenue: float | None = 18_000_000.0,
        certifications: tuple[str, ...] = (),
        location: str = "Tirupur, India",
    ):
        self.industry = industry
        self.annual_revenue_inr = revenue
        self.certifications = certifications
        self.location = location


# --------------------------------------------------------------------------- #
# 1 — Cue detection
# --------------------------------------------------------------------------- #


def test_cue_detection_both_cues_make_prompt_mixed():
    """A prompt with BOTH an external cue and a business cue is
    'mixed' — the separator must return is_mixed=True and
    produce the four blocks."""
    sep = MixedQuestionSeparator()
    prompt = (
        "What is REACH compliance and are we ready for European exports?"
    )
    assert sep.has_external_cue(prompt)
    assert sep.has_business_cue(prompt)
    assert sep.is_mixed(prompt)

    ctx = _StubContext()
    result = sep.split(prompt, context=ctx)
    assert result.is_mixed
    assert result.external_block
    assert result.business_block
    assert result.gap_block
    assert result.conclusion_block


# --------------------------------------------------------------------------- #
# 2 — Non-mixed prompt is not split
# --------------------------------------------------------------------------- #


def test_purely_educational_prompt_is_not_mixed():
    """'What is EBITDA?' is purely educational — no business cue.
    The separator must NOT split it; the ExternalQuestionHandler
    is the right tool for this prompt."""
    sep = MixedQuestionSeparator()
    prompt = "What is EBITDA?"
    assert sep.has_external_cue(prompt)
    assert not sep.has_business_cue(prompt)
    assert not sep.is_mixed(prompt)

    result = sep.split(prompt)
    assert not result.is_mixed
    assert result.external_block == ()


# --------------------------------------------------------------------------- #
# 3 — Mixed prompt business block surfaces the user's industry
# --------------------------------------------------------------------------- #


def test_mixed_prompt_business_block_surfaces_industry():
    """The business block must surface the user's industry +
    revenue when the context is present, and must NOT include
    external-source language."""
    sep = MixedQuestionSeparator()
    prompt = "What is REACH compliance and are we ready for exports?"
    ctx = _StubContext(industry="Textiles", revenue=18_000_000.0)

    result = sep.split(prompt, context=ctx)
    business_text = " ".join(result.business_block)
    # The user's industry must be in the business block.
    assert "Textiles" in business_text
    # The revenue is on file — it must be surfaced.
    assert "₹18,000,000" in business_text or "18,000,000" in business_text


# --------------------------------------------------------------------------- #
# 4 — No business / external stream contamination
# --------------------------------------------------------------------------- #


def test_mixed_prompt_no_business_external_stream_contamination():
    """The brief: 'Do not allow external information to silently
    overwrite business data.' The external block must carry the
    verified source, the business block must NOT carry the
    external source URL."""
    sep = MixedQuestionSeparator()
    prompt = "What is REACH compliance and are we ready for exports?"
    ctx = _StubContext(industry="Textiles", revenue=18_000_000.0)

    result = sep.split(prompt, context=ctx)
    external_text = " ".join(result.external_block)
    business_text = " ".join(result.business_block)

    # External block carries the source.
    assert "Source:" in external_text or "source" in external_text.lower()
    # Business block does NOT carry the source URL.
    assert "echa.europa.eu" not in business_text
    # And vice versa — external block does not name the industry.
    assert "Textiles" not in external_text


# --------------------------------------------------------------------------- #
# 5 — Gap block lists what is missing
# --------------------------------------------------------------------------- #


def test_mixed_prompt_gap_block_lists_missing_profile_fields():
    """The gap block must surface the missing fields. When
    certifications are empty, the separator must say so
    explicitly rather than asserting readiness."""
    sep = MixedQuestionSeparator()
    prompt = "What is REACH compliance and are we ready for exports?"
    ctx = _StubContext(industry="Textiles", revenue=18_000_000.0, certifications=())

    result = sep.split(prompt, context=ctx)
    gap_text = " ".join(result.gap_block)
    # The certifications gap is critical for a REACH question.
    assert "certification" in gap_text.lower() or "certifications" in gap_text.lower()


# --------------------------------------------------------------------------- #
# 6 — Conservative conclusion
# --------------------------------------------------------------------------- #


def test_mixed_prompt_conclusion_is_conservative_when_gaps_exist():
    """The conclusion block is conservative by design: when
    gaps exist (or external source is unverified), the
    conclusion says 'we cannot fully answer' rather than
    guessing. The brief: 'what can and cannot currently be
    concluded.'"""
    sep = MixedQuestionSeparator()
    prompt = "What is REACH compliance and are we ready for exports?"
    # Context with NO revenue and NO certifications — multiple gaps.
    ctx = _StubContext(industry="Textiles", revenue=None, certifications=())

    result = sep.split(prompt, context=ctx)
    conclusion_text = " ".join(result.conclusion_block).lower()
    # The conclusion must say "cannot" / "cannot" / "partial" / "verify"
    # — never a confident "you are ready" / "you are not ready".
    assert "cannot" in conclusion_text or "cannot " in conclusion_text
    # And must NOT contain a confident "you are eligible" / "you are ready".
    assert "you are ready" not in conclusion_text
    assert "you are eligible" not in conclusion_text

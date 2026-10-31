"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for :class:`ExternalQuestionHandler`.

Covers:
  * Definition prompt: "What is EBITDA?" returns concise verified
    answer with provenance
  * Concision: headline + supporting are bounded (the brief:
    "the answer should remain concise")
  * Pure-external prompt NEVER touches business profile —
    no "your business" / "your revenue" leakage
  * Empty result carries empty_reason (not fabricated prose)
  * Stale source surfaces a disclaimer line
  * Business-relevance note is opt-in ("If you would like")
  * Definition cue detection works on common openers

4 tests in this module.
"""

from __future__ import annotations

from app.services.ai.knowledge.external_question_handler import (
    ExternalQuestionHandler,
)
from app.services.ai.knowledge.external_types import FreshnessStatus


# --------------------------------------------------------------------------- #
# 1 — Definition prompt returns concise verified answer
# --------------------------------------------------------------------------- #


def test_external_handler_what_is_ebitda_concise_verified():
    """'What is EBITDA?' must return a verified, concise answer
    with the source. The handler must NOT invoke the user's
    business profile — the brief: 'Do not invoke health score,
    finance profile, recommendation engine, etc.'"""
    handler = ExternalQuestionHandler()
    envelope = handler.handle("What is EBITDA?")

    assert not envelope.is_empty
    assert envelope.headline
    # Concision: headline should be a single sentence, not a
    # multi-paragraph essay.
    assert envelope.headline.count(".") <= 2
    # Provenance is mandatory.
    assert envelope.source is not None
    assert envelope.source.source_url.startswith("https://")
    # The headline is not the user's business data.
    assert "your business" not in envelope.headline.lower()
    assert "your revenue" not in envelope.headline.lower()


# --------------------------------------------------------------------------- #
# 2 — Empty result carries empty_reason (not fabricated prose)
# --------------------------------------------------------------------------- #


def test_external_handler_unsupported_question_returns_empty_reason():
    """A question the corpus cannot answer must return an
    is_empty envelope with a non-empty empty_reason. The
    brief: 'If current information cannot be verified, say
    so explicitly. Do not fabricate dates, rules, benefits
    or links.'"""
    handler = ExternalQuestionHandler()
    envelope = handler.handle("How does photosynthesis work?")

    assert envelope.is_empty
    assert envelope.empty_reason != ""
    # The renderer must surface this string verbatim.
    assert "could not verify" in envelope.empty_reason.lower()
    # No headline must be emitted when the source is missing.
    assert envelope.headline == ""


# --------------------------------------------------------------------------- #
# 3 — Stale source surfaces disclaimer
# ------------------------------------------------------------------------ #


def test_external_handler_stale_source_surfaces_disclaimer():
    """The 'repo rate' entry is STALE. The handler must surface
    a disclaimer that says the source is past its safe window
    and that the user must re-verify before relying on it.
    The brief: 'Do not fabricate dates, rules, benefits or
    links.'"""
    handler = ExternalQuestionHandler()
    envelope = handler.handle("What is the repo rate?")

    assert not envelope.is_empty
    assert envelope.source is not None
    assert envelope.source.freshness_status == FreshnessStatus.STALE
    # The disclaimer is the user's safeguard.
    assert envelope.disclaimer != ""
    assert "stale" in envelope.disclaimer.lower() or "safe window" in envelope.disclaimer.lower()
    # is_verified must be False for a stale source.
    assert envelope.is_verified is False


# --------------------------------------------------------------------------- #
# 4 — Business relevance note is opt-in
# ------------------------------------------------------------------------ #


def test_external_handler_business_relevance_note_opt_in():
    """The handler surfaces a 'If you would like, UrsBiz can…'
    opt-in line for topics that have a clear next step (e.g.
    EBITDA, REACH, working capital). The note MUST be opt-in
    — the user is never told the assistant already ran an
    analysis."""
    handler = ExternalQuestionHandler()
    envelope = handler.handle("What is working capital?")

    assert not envelope.is_empty
    # The note uses the brief's opt-in language.
    note = envelope.business_relevance_note.lower()
    assert "if you would like" in note
    # The note never asserts a computation has happened.
    assert "your working capital is" not in note
    assert "computed your" not in note


# --------------------------------------------------------------------------- #
# 5 — Definition cue detection
# ------------------------------------------------------------------------ #


def test_external_handler_definition_cue_detection():
    """The handler identifies definition-style prompts so it
    can switch to the concise answer path. Non-definition
    prompts are NOT short-circuited by the handler — they
    go through the full pipeline."""
    handler = ExternalQuestionHandler()
    assert handler.is_definition_prompt("What is EBITDA?")
    assert handler.is_definition_prompt("Define working capital.")
    assert handler.is_definition_prompt("Explain REACH compliance.")
    assert handler.is_definition_prompt("Tell me about BRSR.")
    # Not a definition prompt.
    assert not handler.is_definition_prompt("Are we eligible for MUDRA?")
    assert not handler.is_definition_prompt("Should I apply for CGTMSE?")
    assert not handler.is_definition_prompt("How can I reduce my costs?")

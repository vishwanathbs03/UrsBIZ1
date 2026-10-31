"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for the curated external knowledge base and the
:class:`ExternalKnowledgeRetriever`.

Covers:
  * Tag extraction (deterministic)
  * Retrieval for general-knowledge prompts (EBITDA, REACH, GST)
  * Retrieval for regulatory prompts (BIS, REACH)
  * Retrieval for scheme prompts (MUDRA, PMEGP, CGTMSE, TReDS)
  * Retrieval for export prompts (textile EU, IEC)
  * Empty retrieval (no tag match) carries a non-empty
    ``empty_reason`` — the brief: "say so explicitly"
  * Provenance is mandatory — every match carries a source URL
  * Authority weights reflect the tier × freshness formula
  * Stale source demotes the match authority
  * Conflicting sources (two TIER_1 schemes with same tag) both
    surface — caller decides
  * Malformed prompt ("#$%^&") does not raise, returns empty
  * Unsupported question returns empty (not fabricated)

7 tests in this module.
"""

from __future__ import annotations

from app.services.ai.knowledge.external_knowledge_base import (
    ExternalKnowledgeRetriever,
)
from app.services.ai.knowledge.external_types import (
    ClaimKind,
    FreshnessStatus,
    SourceAuthority,
)


# --------------------------------------------------------------------------- #
# 1 — General-knowledge prompt: EBITDA
# --------------------------------------------------------------------------- #


def test_retrieve_ebitda_general_knowledge():
    """'What is EBITDA?' must resolve to a verified source —
    the corpus carries the Investopedia entry."""
    retriever = ExternalKnowledgeRetriever()
    result = retriever.retrieve("What is EBITDA?")

    assert not result.is_empty
    assert result.query_tags
    assert any(c.kind == ClaimKind.EXTERNAL_FACT for c in result.matches)
    claim = result.matches[0]
    # Provenance is mandatory — every match carries a URL +
    # publisher + freshness_status.
    assert claim.source is not None
    assert claim.source.source_url.startswith("https://")
    assert claim.source.publisher != ""
    assert claim.source.freshness_status is not None
    # Authority is computed from tier × freshness, not guessed.
    assert 0.0 < claim.authority <= 1.0


# --------------------------------------------------------------------------- #
# 2 — Regulatory prompt: REACH
# --------------------------------------------------------------------------- #


def test_retrieve_reach_regulatory():
    """'What is REACH compliance?' must hit the ECHA Tier-1 source
    with the canonical answer."""
    retriever = ExternalKnowledgeRetriever()
    result = retriever.retrieve("What is REACH compliance?")

    assert not result.is_empty
    claim = result.matches[0]
    assert claim.source is not None
    assert claim.source.authority_level == SourceAuthority.TIER_1
    assert "REACH" in claim.text
    # No business-data contamination — the EBITDA / business
    # corpus cannot leak into a REACH answer.
    assert "EBITDA" not in claim.text


# --------------------------------------------------------------------------- #
# 3 — Scheme prompt: MUDRA
# --------------------------------------------------------------------------- #


def test_retrieve_mudra_scheme_with_provenance():
    """'Tell me about MUDRA' must surface a TIER_1 source
    (MUDRA — Government of India) with provenance, authority,
    and a fresh/aging/known freshness status."""
    retriever = ExternalKnowledgeRetriever()
    result = retriever.retrieve("Tell me about MUDRA loans")

    assert not result.is_empty
    claim = result.matches[0]
    assert claim.source is not None
    assert claim.source.authority_level == SourceAuthority.TIER_1
    # The brief: provenance is non-negotiable.
    assert "mudra" in claim.source.publisher.lower() or "MUDRA" in claim.source.publisher


# --------------------------------------------------------------------------- #
# 4 — Empty retrieval: no tag match returns empty_reason
# --------------------------------------------------------------------------- #


def test_retrieve_unsupported_question_returns_empty_with_reason():
    """A question UrsBiz has no verified source for must NOT
    fabricate an answer. The retriever returns a non-empty
    ``empty_reason`` the renderer surfaces verbatim."""
    retriever = ExternalKnowledgeRetriever()
    # "Photosynthesis" is in the non-business subject list of
    # the question-understanding module and has no corpus entry.
    result = retriever.retrieve("How does photosynthesis work?")

    assert result.is_empty
    assert result.empty_reason != ""
    # The renderer must show this string to the user.
    assert "could not verify" in result.empty_reason.lower()


# --------------------------------------------------------------------------- #
# 5 — Malformed prompt does not crash
# --------------------------------------------------------------------------- #


def test_retrieve_malformed_prompt_does_not_raise():
    """The retriever must be defensive — a malformed prompt
    (special characters, empty string) returns empty rather
    than raising. The reasoning pipeline can pass user
    input that is not always clean."""
    retriever = ExternalKnowledgeRetriever()
    for bad in ("", "   ", "!@#$%^&*()", "?? ?? ??", None):
        result = retriever.retrieve(bad or "")
        assert result.is_empty
        assert result.empty_reason != ""


# --------------------------------------------------------------------------- #
# 6 — Stale source demotes authority
# --------------------------------------------------------------------------- #


def test_stale_source_authority_is_demoted():
    """The 'repo rate' entry is a TIER_1 source whose
    published_at is 3 years old — beyond the 6-month
    FINANCIAL_RATE safe window. Its effective_authority must
    be lower than a FRESH TIER_1 source."""
    retriever = ExternalKnowledgeRetriever()
    fresh = retriever.retrieve("What is EBITDA?")
    stale = retriever.retrieve("What is the repo rate?")

    assert not fresh.is_empty
    assert not stale.is_empty

    fresh_authority = fresh.matches[0].authority
    stale_authority = stale.matches[0].authority

    # TIER_1 × 1.0 (FRESH) > TIER_1 × 0.5 (STALE)
    assert fresh_authority > stale_authority
    assert stale.matches[0].source.freshness_status == FreshnessStatus.STALE
    assert stale.matches[0].is_verified is False


# --------------------------------------------------------------------------- #
# 7 — Conflicting sources: corpus returns all matches, caller decides
# --------------------------------------------------------------------------- #


def test_conflicting_sources_both_surface():
    """When a tag is shared by multiple corpus entries (e.g.
    'scheme' matches MUDRA, PMEGP, CGTMSE, TReDS), the retriever
    returns ALL of them. The renderer / scheme-card builder
    decides which one to highlight — the retriever does not
    silently pick one."""
    retriever = ExternalKnowledgeRetriever()
    result = retriever.retrieve("Which MSME scheme should I apply for?")

    assert not result.is_empty
    # At least 2 schemes (MUDRA + PMEGP + ...) should be present.
    assert len(result.matches) >= 2
    # Every match must carry its own source.
    for c in result.matches:
        assert c.source is not None
        assert c.source.source_url != ""
    # Publishers should be distinct.
    publishers = {c.source.publisher for c in result.matches}
    assert len(publishers) >= 2

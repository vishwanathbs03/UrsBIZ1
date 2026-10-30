"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for ``external_types``: source authority, freshness status,
content category expiry, and the canonical 6-way claim-kind
vocabulary.

8 tests covering:
  * SourceAuthority tier weights monotonically decrease
  * SourceAuthority label exposes the human-readable trust name
  * ExternalSource.freshness_status computes FRESH within window
  * ExternalSource.freshness_status computes STALE past 2x window
  * ExternalSource.freshness_status returns UNKNOWN when
    published_at missing
  * ExternalSource.freshness_penalty multiplies tier weight
  * ClaimKind default authority ordering (INTERNAL_BUSINESS >
    CALCULATED > EXTERNAL_FACT > SCENARIO > ASSUMPTION > UNKNOWN)
  * now_iso produces a parseable UTC timestamp
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.ai.knowledge.external_types import (
    ClaimKind,
    ContentCategory,
    ExternalSource,
    FreshnessStatus,
    SourceAuthority,
    _parse_iso,
    now_iso,
)


# --------------------------------------------------------------------------- #
# 1 — SourceAuthority tier weights monotonically decrease
# --------------------------------------------------------------------------- #


def test_source_authority_weights_monotonically_decrease():
    """TIER_1 must outrank TIER_2, which must outrank TIER_3, which
    must outrank TIER_4. This is the order the renderer shows
    in the trust badge."""
    assert SourceAuthority.TIER_1.weight > SourceAuthority.TIER_2.weight
    assert SourceAuthority.TIER_2.weight > SourceAuthority.TIER_3.weight
    assert SourceAuthority.TIER_3.weight > SourceAuthority.TIER_4.weight
    assert 0.0 < SourceAuthority.TIER_4.weight < 1.0
    assert SourceAuthority.TIER_1.weight <= 1.0


# --------------------------------------------------------------------------- #
# 2 — SourceAuthority label exposes the human-readable trust name
# --------------------------------------------------------------------------- #


def test_source_authority_label_human_readable():
    """The label is what the trust UI shows in plain English.
    The brief mandates that source authority never silently
    changes the kind — labels must be unambiguous."""
    assert "Tier 1" in SourceAuthority.TIER_1.label
    assert "Tier 4" in SourceAuthority.TIER_4.label
    assert "Official" in SourceAuthority.TIER_1.label
    assert "General" in SourceAuthority.TIER_4.label


# --------------------------------------------------------------------------- #
# 3 — ExternalSource.freshness_status computes FRESH within window
# --------------------------------------------------------------------------- #


def test_external_source_freshness_within_window_is_fresh():
    """A source published 30 days ago (well within the 365-day
    STATUTORY window) must report FRESH — no confidence penalty."""
    source = ExternalSource(
        source_url="https://example.gov/scheme",
        publisher="Example Authority",
        retrieved_at="2026-08-12T00:00:00Z",
        published_at="2026-07-12T00:00:00Z",
        authority_level=SourceAuthority.TIER_1,
        category=ContentCategory.STATUTORY,
    )
    assert source.freshness_status == FreshnessStatus.FRESH
    assert source.freshness_penalty == 1.0


# --------------------------------------------------------------------------- #
# 4 — ExternalSource.freshness_status computes STALE past 2x window
# --------------------------------------------------------------------------- #


def test_external_source_freshness_past_double_window_is_stale():
    """A STATUTORY source published 800 days ago is past the 2x
    safe window — must report STALE."""
    source = ExternalSource(
        source_url="https://example.gov/scheme",
        publisher="Example Authority",
        retrieved_at="2026-08-12T00:00:00Z",
        published_at="2024-06-15T00:00:00Z",
        authority_level=SourceAuthority.TIER_1,
        category=ContentCategory.STATUTORY,
    )
    assert source.freshness_status == FreshnessStatus.STALE
    # STALE keeps 50% of the tier weight per the spec.
    assert source.freshness_penalty == 0.5


# --------------------------------------------------------------------------- #
# 5 — ExternalSource.freshness_status returns UNKNOWN when published_at empty
# --------------------------------------------------------------------------- #


def test_external_source_freshness_unknown_when_published_at_missing():
    """Evergreen pages (definition pages) do not always carry a
    published_at. The freshness check must return UNKNOWN, not
    silently treat the source as FRESH (which would be a
    fabricated trust signal)."""
    source = ExternalSource(
        source_url="https://example.org/definition",
        publisher="Example Institution",
        retrieved_at="2026-08-12T00:00:00Z",
        published_at="",
        authority_level=SourceAuthority.TIER_2,
        category=ContentCategory.ENCYCLOPEDIC,
    )
    assert source.freshness_status == FreshnessStatus.UNKNOWN
    assert source.freshness_penalty == 0.6


# --------------------------------------------------------------------------- #
# 6 — ExternalSource.freshness_penalty multiplies tier weight
# --------------------------------------------------------------------------- #


def test_external_source_freshness_penalty_multiplies_tier_weight():
    """effective_authority = tier weight × freshness penalty.
    For a TIER_1 (0.95) source that is AGING (0.8) the
    effective_authority is 0.76 — not 0.95."""
    source = ExternalSource(
        source_url="https://example.gov/scheme",
        publisher="Example Authority",
        retrieved_at="2026-08-12T00:00:00Z",
        # AGING = between safe_window (365) and 2x safe_window (730).
        # 500 days old → AGING.
        published_at="2025-03-29T00:00:00Z",
        authority_level=SourceAuthority.TIER_1,
        category=ContentCategory.STATUTORY,
    )
    assert source.freshness_status == FreshnessStatus.AGING
    # TIER_1 weight 0.95 × AGING penalty 0.8
    assert abs(source.effective_authority - 0.95 * 0.8) < 0.01


# --------------------------------------------------------------------------- #
# 7 — ClaimKind default authority ordering
# --------------------------------------------------------------------------- #


def test_claim_kind_default_authority_ordering():
    """INTERNAL_BUSINESS > CALCULATED > EXTERNAL_FACT > SCENARIO >
    ASSUMPTION > UNKNOWN. The brief's order: internal data is
    most trusted, unknowns are zero-authority. The renderer uses
    this ordering to colour the trust badge."""
    assert (
        ClaimKind.INTERNAL_BUSINESS.default_authority
        > ClaimKind.CALCULATED.default_authority
    )
    assert (
        ClaimKind.CALCULATED.default_authority
        > ClaimKind.EXTERNAL_FACT.default_authority
    )
    assert (
        ClaimKind.EXTERNAL_FACT.default_authority
        > ClaimKind.SCENARIO.default_authority
    )
    assert (
        ClaimKind.SCENARIO.default_authority
        > ClaimKind.ASSUMPTION.default_authority
    )
    assert (
        ClaimKind.ASSUMPTION.default_authority
        > ClaimKind.UNKNOWN.default_authority
    )
    assert ClaimKind.UNKNOWN.default_authority == 0.0
    # The brief caps SCENARIO at 0.7 and ASSUMPTION at 0.5.
    assert ClaimKind.SCENARIO.default_authority <= 0.7
    assert ClaimKind.ASSUMPTION.default_authority <= 0.5


# --------------------------------------------------------------------------- #
# 8 — now_iso + _parse_iso round-trip
# --------------------------------------------------------------------------- #


def test_now_iso_and_parse_round_trip():
    """now_iso must produce an ISO-8601 string that _parse_iso
    can re-parse into a UTC datetime. The freshness checker
    calls _parse_iso on every published_at — the round-trip
    must be lossless."""
    iso = now_iso()
    parsed = _parse_iso(iso)
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    # Allow a few seconds of clock drift between the two calls.
    assert (datetime.now(timezone.utc) - parsed).total_seconds() < 5

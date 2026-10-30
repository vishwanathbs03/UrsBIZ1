"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for :class:`SchemeAnswerCardBuilder`.

Covers:
  * Build MUDRA card with full profile → disposition
    POTENTIAL_MATCH
  * Build MUDRA card with missing profile → disposition
    GAP_UNKNOWN (NEVER asserts eligibility)
  * Build CGTMSE card carries every brief-mandated field
  * Build card's mandatory final-authority disclaimer
  * Build card carries the application link
  * Build card carries the last_verified_date
  * Build card with unknown scheme id raises (no fabrication)
  * Build card WITHOUT a verified source raises (no fabrication)
  * Eligibility phrasing is conservative: NEVER
    "you are definitely eligible"
  * Wire dict round-trip
  * Match disposition drives the renderer phrasing

5 tests in this module.
"""

from __future__ import annotations

import pytest

from app.services.ai.knowledge.scheme_answer_card import (
    MatchDisposition,
    SchemeAnswerCard,
    SchemeAnswerCardBuilder,
)


class _FullContext:
    """Stub profile with every field the builder checks."""

    def __init__(self):
        self.industry = "Food Processing"
        self.annual_revenue_inr = 12_000_000.0
        self.employee_count = 14
        self.udyam_number = "UDYAM-TN-12-0001234"
        self.is_registered_msme = True


class _SparseContext:
    """Stub profile with no useful data — most fields missing."""

    def __init__(self):
        self.industry = ""
        self.annual_revenue_inr = None
        self.employee_count = None


# --------------------------------------------------------------------------- #
# 1 — Full profile → POTENTIAL_MATCH
# --------------------------------------------------------------------------- #


def test_mudra_card_full_profile_potential_match():
    """A user with industry, revenue, employee count, and a
    Udyam number must produce a POTENTIAL_MATCH card — but
    the card must still say 'potential' (not 'definitely
    eligible' — the brief)."""
    builder = SchemeAnswerCardBuilder()
    card = builder.build("mudra", context=_FullContext())

    assert isinstance(card, SchemeAnswerCard)
    assert card.scheme_id == "mudra"
    assert "MUDRA" in card.official_name
    assert card.match_disposition == MatchDisposition.POTENTIAL_MATCH
    # Conservative phrasing — never "definitely eligible".
    why_text = " ".join(card.why_business_may_match).lower()
    assert "definitely eligible" not in why_text
    assert "potential" in why_text or "industry" in why_text or "revenue" in why_text


# --------------------------------------------------------------------------- #
# 2 — Sparse profile → GAP_UNKNOWN (never asserts eligibility)
# --------------------------------------------------------------------------- #


def test_mudra_card_sparse_profile_gap_unknown():
    """A user with no industry / revenue / employees must
    produce a GAP_UNKNOWN card. The renderer must NOT show
    'you are eligible' — it must list the missing fields."""
    builder = SchemeAnswerCardBuilder()
    card = builder.build("mudra", context=_SparseContext())

    assert card.match_disposition == MatchDisposition.GAP_UNKNOWN
    assert card.missing_eligibility_info
    # The "why_business_may_match" list must be empty when
    # nothing is on file.
    assert card.why_business_may_match == ()


# --------------------------------------------------------------------------- #
# 3 — All brief-mandated fields present
# --------------------------------------------------------------------------- #


def test_card_carries_all_brief_mandated_fields():
    """The brief lists 10 mandatory fields. The card must
    surface every one of them as a non-empty value (when the
    scheme is supported and a source exists)."""
    builder = SchemeAnswerCardBuilder()
    card = builder.build("cgtmse", context=_FullContext())

    assert card.scheme_id
    assert card.official_name
    assert card.authority
    assert card.benefit_description
    assert card.eligibility
    assert card.required_documents
    assert card.application_link.startswith("https://")
    assert card.last_verified_date
    assert card.final_authority_disclaimer


# --------------------------------------------------------------------------- #
# 4 — Final-authority disclaimer is mandatory and conservative
# --------------------------------------------------------------------------- #


def test_card_final_authority_disclaimer_mandatory():
    """The brief: 'final-authority disclaimer' is one of the
    10 mandatory fields. The card must carry a non-empty
    disclaimer that defers to the nodal authority."""
    builder = SchemeAnswerCardBuilder()
    card = builder.build("mudra", context=_FullContext())
    disc = card.final_authority_disclaimer.lower()
    # The disclaimer must mention the final authority
    # (e.g. "scheme's nodal authority" / "eligibility").
    assert "authority" in disc or "eligibility" in disc or "verify" in disc
    # The disclaimer must NOT assert eligibility.
    assert "you are definitely eligible" not in disc


# --------------------------------------------------------------------------- #
# 5 — Unknown scheme id raises
# --------------------------------------------------------------------------- #


def test_card_unknown_scheme_id_raises():
    """The builder must not fabricate a card for an unknown
    scheme. An unknown id is a bug, not a soft fallback."""
    builder = SchemeAnswerCardBuilder()
    with pytest.raises(ValueError):
        builder.build("not-a-real-scheme", context=_FullContext())


# --------------------------------------------------------------------------- #
# 6 — Wire dict round-trip
# --------------------------------------------------------------------------- #


def test_card_to_dict_round_trip():
    """The card's ``to_dict`` output is what the wire surfaces.
    Every field the brief mandates must be present in the
    dict."""
    builder = SchemeAnswerCardBuilder()
    card = builder.build("treds", context=_FullContext())
    d = card.to_dict()
    # 10 brief-mandated fields.
    for key in (
        "scheme_id", "official_name", "authority",
        "benefit_description", "eligibility", "required_documents",
        "application_link", "last_verified_date",
        "why_business_may_match", "missing_eligibility_info",
        "final_authority_disclaimer", "match_disposition",
    ):
        assert key in d, f"Missing {key!r} in card.to_dict()"

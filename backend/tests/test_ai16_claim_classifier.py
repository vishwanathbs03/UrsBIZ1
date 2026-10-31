"""SPRINT AI-16 — Verified External Knowledge + Freshness Layer.

Tests for :class:`ClaimKindClassifier`.

Covers:
  * Legacy FACT claim with business context → INTERNAL_BUSINESS
  * Legacy FACT claim with external token → EXTERNAL_FACT
  * Legacy FACT claim with calculation token → CALCULATED
  * Legacy CALCULATION → CALCULATED
  * Legacy SCENARIO → SCENARIO
  * Legacy RECOMMENDATION → ASSUMPTION
  * Legacy INFERENCE → INTERNAL_BUSINESS
  * Legacy EXTERNAL_FACT → EXTERNAL_FACT
  * Legacy UNKNOWN → UNKNOWN
  * classify_text (no legacy label) detects the right kind from
    the claim text alone
  * Business isolation guard: INTERNAL_BUSINESS cannot carry an
    external source
  * Business isolation guard: EXTERNAL_FACT must carry a source
  * validate_no_fabricated_source rejects example.com / empty
    / "placeholder" / "fake"
  * validate_no_fabricated_source accepts real-looking URLs

6 tests in this module.
"""

from __future__ import annotations

import pytest

from app.services.ai.knowledge.claim_classifier import (
    ClaimKindClassifier,
    ClaimKindContaminationError,
)
from app.services.ai.knowledge.external_types import ClaimKind


# --------------------------------------------------------------------------- #
# 1 — Legacy claim mapping (8 sub-cases in one test)
# --------------------------------------------------------------------------- #


def test_legacy_claim_kind_mapping():
    """The classifier maps every legacy label to the new 6-way
    vocabulary. The mapping is the safety net that protects
    the wire contract from silent kind drift."""
    clf = ClaimKindClassifier()

    cases = [
        # (claim_type, text, expected_kind)
        ("FACT", "Your business revenue is ₹1.8 Cr.", ClaimKind.INTERNAL_BUSINESS),
        ("FACT", "REACH is a European regulation on chemicals.", ClaimKind.EXTERNAL_FACT),
        ("FACT", "EBITDA is calculated as earnings before interest.", ClaimKind.CALCULATED),
        ("CALCULATION", "Working capital = current assets - current liabilities.", ClaimKind.CALCULATED),
        ("SCENARIO", "If the supplier raises prices by 10%, margin drops to 12%.", ClaimKind.SCENARIO),
        ("RECOMMENDATION", "We recommend you apply for MUDRA next quarter.", ClaimKind.ASSUMPTION),
        ("INFERENCE", "Your cash cycle suggests a working capital gap.", ClaimKind.INTERNAL_BUSINESS),
        ("EXTERNAL_FACT", "According to the RBI, repo rate is the policy rate.", ClaimKind.EXTERNAL_FACT),
        ("UNKNOWN", "We could not determine this from the available data.", ClaimKind.UNKNOWN),
    ]
    for claim_type, text, expected in cases:
        result = clf.classify_legacy(claim_type=claim_type, text=text)
        assert result.kind == expected, (
            f"{claim_type!r} on {text!r} expected {expected!r}, "
            f"got {result.kind!r}"
        )
        # Every classification carries a non-empty reason.
        assert result.reason != ""


# --------------------------------------------------------------------------- #
# 2 — classify_text (no legacy label)
# --------------------------------------------------------------------------- #


def test_classify_text_infers_kind_from_text_alone():
    """When a caller has only the claim text, classify_text
    must still pick the right kind from the text. Same tokens
    drive the same answer."""
    clf = ClaimKindClassifier()

    # External source tokens win.
    r1 = clf.classify_text("According to the RBI, repo rate is 6.5%.")
    assert r1.kind == ClaimKind.EXTERNAL_FACT

    # Calculation phrasing wins.
    r2 = clf.classify_text("Working capital is calculated as current assets minus liabilities.")
    assert r2.kind == ClaimKind.CALCULATED

    # Advisory phrasing → ASSUMPTION.
    r3 = clf.classify_text("We recommend you apply for MUDRA next quarter.")
    assert r3.kind == ClaimKind.ASSUMPTION

    # Business context tokens → INTERNAL_BUSINESS.
    r4 = clf.classify_text("Your business revenue is ₹1.8 Cr.")
    assert r4.kind == ClaimKind.INTERNAL_BUSINESS

    # No signal → UNKNOWN.
    r5 = clf.classify_text("The weather in Mumbai is pleasant.")
    assert r5.kind == ClaimKind.UNKNOWN


# --------------------------------------------------------------------------- #
# 3 — Business isolation guard: INTERNAL_BUSINESS cannot carry external source
# --------------------------------------------------------------------------- #


def test_business_isolation_internal_cannot_have_external_source():
    """The brief: 'Do not allow external information to silently
    overwrite business data.' The guard must reject any
    INTERNAL_BUSINESS claim that also carries an external
    source URL."""
    clf = ClaimKindClassifier()
    with pytest.raises(ClaimKindContaminationError):
        clf.enforce_business_isolation(
            kind=ClaimKind.INTERNAL_BUSINESS,
            has_external_source=True,
        )
    # CALCULATED is also internal; same rule.
    with pytest.raises(ClaimKindContaminationError):
        clf.enforce_business_isolation(
            kind=ClaimKind.CALCULATED,
            has_external_source=True,
        )


# --------------------------------------------------------------------------- #
# 4 — Business isolation guard: EXTERNAL_FACT must have a source
# --------------------------------------------------------------------------- #


def test_business_isolation_external_fact_must_have_source():
    """An EXTERNAL_FACT claim without a source is a fabrication
    risk. The guard must reject it before the claim reaches
    the wire."""
    clf = ClaimKindClassifier()
    with pytest.raises(ClaimKindContaminationError):
        clf.enforce_business_isolation(
            kind=ClaimKind.EXTERNAL_FACT,
            has_external_source=False,
        )


# --------------------------------------------------------------------------- #
# 5 — Business isolation guard: matching pairs do not raise
# --------------------------------------------------------------------------- #


def test_business_isolation_matching_pairs_ok():
    """The matching pairs (INTERNAL_BUSINESS without external;
    EXTERNAL_FACT with external) must not raise — the guard
    is a positive filter, not a paranoid one."""
    clf = ClaimKindClassifier()
    clf.enforce_business_isolation(
        kind=ClaimKind.INTERNAL_BUSINESS, has_external_source=False
    )
    clf.enforce_business_isolation(
        kind=ClaimKind.EXTERNAL_FACT, has_external_source=True
    )
    # SCENARIO + ASSUMPTION + UNKNOWN are kind-agnostic; they
    # may carry or skip a source without raising.
    for kind in (ClaimKind.SCENARIO, ClaimKind.ASSUMPTION, ClaimKind.UNKNOWN):
        clf.enforce_business_isolation(kind=kind, has_external_source=False)
        clf.enforce_business_isolation(kind=kind, has_external_source=True)


# --------------------------------------------------------------------------- #
# 6 — validate_no_fabricated_source
# --------------------------------------------------------------------------- #


def test_validate_no_fabricated_source():
    """The brief: 'Do not fabricate dates, rules, benefits or
    links.' The validator rejects obvious fakes (example.com,
    empty, placeholder, fake) but accepts real-looking URLs."""
    clf = ClaimKindClassifier()

    # Reject
    for bad in (
        "",
        "   ",
        "https://example.com/page",
        "https://example.com",
        "http://example.com/foo",
        "https://placeholder.gov/scheme",
        "https://fake.org/path",
        "https://example.org/TODO/page",
    ):
        assert clf.validate_no_fabricated_source(bad) is False, (
            f"Should reject {bad!r}"
        )

    # Accept
    for good in (
        "https://www.rbi.org.in/page",
        "https://echa.europa.eu/regulations/reach",
        "https://www.mudra.org.in/",
        "https://udyamregistration.gov.in/",
    ):
        assert clf.validate_no_fabricated_source(good) is True, (
            f"Should accept {good!r}"
        )

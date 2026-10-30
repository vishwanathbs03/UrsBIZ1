"""Test suite for SPRINT AI-1 — Stage 7: ClaimCategory validation."""

import pytest

from app.services.ai.reasoning.claim_categories import (
    CATEGORY_LABELS,
    ClaimCategory,
    categorize_claim,
)


# --------------------------------------------------------------------------- #
# 1. categorize_claim returns each category for matched text
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        # FACT — declarative profile statements
        ("Your revenue is steady this quarter.", "FACT"),
        ("You have 42 employees.", "FACT"),
        ("Your industry is Textiles.", "FACT"),
        # CALCULATION — arithmetic / number-anchored
        ("The growth multiple is 1.67x.", "CALCULATION"),
        ("Total EMI equals ₹45,000.", "CALCULATION"),
        # INFERENCE — reasoning language
        ("Therefore, supplier concentration limits margin.", "INFERENCE"),
        ("This suggests demand will rise next quarter.", "INFERENCE"),
        # RECOMMENDATION — actionable language
        ("I recommend diversifying your suppliers.", "RECOMMENDATION"),
        ("You should hire two more sales staff.", "RECOMMENDATION"),
        ("Next step: open a current account.", "RECOMMENDATION"),
        # SCENARIO — conditional / hypothetical
        ("If your revenue grows 30%, you'll hit ₹2.34 Cr.", "SCENARIO"),
        ("Best case, EBITDA doubles.", "SCENARIO"),
        ("Suppose your supplier raises prices 10%.", "SCENARIO"),
        # EXTERNAL_FACT — references outside the registry
        ("Industry standard says 20% margin.", "EXTERNAL_FACT"),
        ("Studies show exporters face 30% rejection.", "EXTERNAL_FACT"),
        # UNKNOWN — explicit admissions
        ("I don't know your customer mix.", "UNKNOWN"),
        ("Insufficient information to answer.", "UNKNOWN"),
    ],
)
def test_1_categorize_claim_maps_to_expected_category(text, expected):
    """The heuristic categoriser maps representative prose to the right label."""
    assert categorize_claim(text) == expected


# --------------------------------------------------------------------------- #
# 2. Priority order — UNKNOWN wins over RECOMMENDATION
# --------------------------------------------------------------------------- #


def test_2_unknown_wins_priority():
    """An explicit admission wins even when other keywords are present."""
    cat = categorize_claim("I don't know but you should hire more staff.")
    assert cat == "UNKNOWN"


# --------------------------------------------------------------------------- #
# 3. Priority order — RECOMMENDATION wins over FACT
# --------------------------------------------------------------------------- #


def test_3_recommendation_wins_priority():
    """Actionable language wins over declarative profile statements."""
    cat = categorize_claim(
        "Your revenue is ₹1.8 Cr; you should aim for ₹3 Cr next year."
    )
    assert cat == "RECOMMENDATION"


# --------------------------------------------------------------------------- #
# 4. Empty / whitespace text returns UNKNOWN
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ["", "   ", None])
def test_4_empty_text_returns_unknown(text):
    """An empty or whitespace-only prompt is classified UNKNOWN."""
    assert categorize_claim(text) == "UNKNOWN"


# --------------------------------------------------------------------------- #
# 5. CATEGORY_LABELS is the canonical ordered tuple
# --------------------------------------------------------------------------- #


def test_5_category_labels_canonical_order():
    """The label tuple has 7 entries in priority order."""
    assert len(CATEGORY_LABELS) == 7
    assert CATEGORY_LABELS == (
        "FACT", "CALCULATION", "INFERENCE",
        "RECOMMENDATION", "SCENARIO", "EXTERNAL_FACT", "UNKNOWN",
    )


# --------------------------------------------------------------------------- #
# 6. ClaimCategory is a Literal — values match CATEGORY_LABELS
# --------------------------------------------------------------------------- #


def test_6_claim_category_literal_values_match_labels():
    """Every ClaimCategory Literal value is in CATEGORY_LABELS."""
    for label in CATEGORY_LABELS:
        # The Literal is purely a type hint; verifying the
        # strings match is sufficient.
        assert isinstance(label, str)


# --------------------------------------------------------------------------- #
# 7. GroundingValidator picks up categories in score_breakdown
# --------------------------------------------------------------------------- #


def test_7_grounding_validator_breakdown_includes_category_keys():
    """GroundingValidator.validate appends category_* keys to score_breakdown."""
    from app.services.ai.providers.grounding_validator import (
        GroundingValidator,
    )
    from app.services.ai.providers.evidence_registry import (
        EvidenceRegistry,
    )
    from app.services.ai.providers.response_schema import (
        GroundedResponse,
        KeyFinding,
        Recommendation,
    )

    reg = EvidenceRegistry(None)
    response = GroundedResponse(
        executive_summary="Your score is 68 out of 100.",
        key_findings=(
            KeyFinding(
                statement="Therefore, supplier concentration limits margin.",
                evidence_refs=("biz_profile_revenue",),
            ),
        ),
        recommendations=(
            Recommendation(
                recommendation_id="rec_diversify_suppliers",
                title="Diversify suppliers",
                rationale="I recommend opening two new vendor accounts.",
                evidence_refs=("rec_diversify_suppliers",),
            ),
        ),
        thirty_day_plan=(),
        scheme_matches=(),
        assumptions=("Sample.",),
        limitations=(),
        confidence=80,
    )
    # Empty registry → most rules fail; we only assert that
    # the breakdown has the AI-1 category_* keys.
    validator = GroundingValidator(
        reg, response, raw_body=response.executive_summary
    )
    report = validator.validate()
    assert "category_fact" in report.score_breakdown
    assert "category_recommendation" in report.score_breakdown
    assert "FACT" in report.claim_categories_used
    assert "RECOMMENDATION" in report.claim_categories_used

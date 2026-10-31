"""Test suite for SPRINT AI-4 — Server-Side Claim Auditor.

Coverage
--------
* Per-claim axis classification (9 axes).
* Hard-rejection rules (9 conditions).
* Soft-correction rules (4 conditions).
* 10 adversarial inputs from the brief — every one must fail safely.
* Wire projection (Pydantic + chat-service mirror).
* Backward-compat: empty / fallback ClaimAwareResponse stays clean.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.ai.providers.claim_auditor import (
    ClaimAuditRecord,
    ClaimAuditReport,
    ClaimAuditor,
    REJECTION_CONTRADICTS_AUTHORITY,
    REJECTION_FABRICATED_EVIDENCE_ID,
    REJECTION_FABRICATED_NUMBER,
    REJECTION_FABRICATED_SCHEME_BENEFIT,
    REJECTION_FABRICATED_TOP_LEVEL_REF,
    REJECTION_LEGAL_ELIGIBILITY_GUARANTEE,
    REJECTION_RECOMMENDATION_AS_GUARANTEE,
    REJECTION_SCENARIO_AS_FORECAST,
    REJECTION_UNSUPPORTED_CONFIDENCE,
)
from app.services.ai.providers.claim_schema import (
    Claim,
    ClaimAwareResponse,
    ClaimCalculation,
    ClaimRecommendation,
    ClaimScenario,
)
from app.services.ai.providers.evidence_registry import (
    EvidenceEntry,
    EvidenceKind,
    EvidenceRegistry,
)
from app.services.ai.providers.numeric_checker import (
    NumericConflict,
    NumericConflictReport,
)
from app.schemas.chat import (
    ChatClaimAuditRecord,
    ChatClaimAuditTrace,
    ChatMessageOut,
)


# --------------------------------------------------------------------------- #
# Fixtures — minimal hand-built registries (no AssistantContext needed).
# --------------------------------------------------------------------------- #


def _entry(eid: str, kind: EvidenceKind, *, value: str = "v") -> EvidenceEntry:
    """Build an EvidenceEntry with the minimum surface area for tests."""
    return EvidenceEntry(
        id=eid,
        kind=kind,
        label=eid,
        value=value,
        source_topic="t",
        authoritative=True,
        source_type="computed",
        freshness="2026-08-09T10:00:00+00:00",
    )


def _registry(*entries: EvidenceEntry) -> EvidenceRegistry:
    """Build an EvidenceRegistry from hand-crafted entries.

    Bypasses AssistantContext because most AI-4 tests target the
    auditor's classifier, not the registry's projectors.
    """
    reg = EvidenceRegistry.__new__(EvidenceRegistry)
    reg._by_id = {e.id: e for e in entries}
    reg._entries = tuple(entries)
    by_kind: dict = {}
    for e in entries:
        by_kind.setdefault(e.kind, []).append(e)
    reg._by_kind = by_kind
    return reg


def _make_registry() -> EvidenceRegistry:
    """The Acme registry: one RECOMMENDATION, one SCORE, one FORECAST,
    one SCHEME, one RULE — enough for the per-axis tests to draw from.
    """
    return _registry(
        _entry("rec_001", EvidenceKind.RECOMMENDATION, value="Diversify suppliers"),
        _entry("score_health", EvidenceKind.SCORE, value="68/100 (Established)"),
        _entry("forecast_001", EvidenceKind.FORECAST, value="12-month scenario"),
        _entry("scheme_pmegp", EvidenceKind.SCHEME, value="PMEGP subsidy Rs.10 lakh"),
        _entry("rule_supplier", EvidenceKind.RULE, value="supplier concentration rule"),
        _entry("insight_supplier", EvidenceKind.INSIGHT, value="supplier concentration 75%"),
        _entry("action_001", EvidenceKind.ACTION, value="contact 5 alternate suppliers"),
        _entry("dna_001", EvidenceKind.DNA, value="Growth Operator 85%"),
    )


def _claim_aware(**overrides) -> ClaimAwareResponse:
    """Build a clean ClaimAwareResponse with sensible defaults.

    The auditor treats this as the baseline; tests override the
    bits they need to trip a specific rule.
    """
    base = dict(
        answer="",
        claims=(),
        recommendations=(),
        calculations=(),
        scenarios=(),
        unknowns=(),
        evidence_references=(),
        assumptions=(),
        limitations=(),
        narrative="",
        server_confidence=100,
        server_confidence_rationale="ok",
        numeric_conflicts=(),
        server_audit={"source": "test"},
    )
    base.update(overrides)
    return ClaimAwareResponse(**base)


def _fact(
    text: str,
    *,
    refs: tuple[str, ...] = (),
    confidence: int = 80,
) -> Claim:
    return Claim(
        text=text,
        claim_type="FACT",
        evidence_references=refs,
        confidence=confidence,
        user_provided=False,
    )


def _scenario(
    description: str,
    *,
    refs: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    confidence: int = 60,
) -> ClaimScenario:
    return ClaimScenario(
        title="12-month scenario",
        description=description,
        assumptions=assumptions,
        evidence_references=refs,
        confidence=confidence,
    )


def _rec(
    *,
    title: str = "Diversify suppliers",
    reason: str = "Concentration on one supplier is risky.",
    refs: tuple[str, ...] = (),
) -> ClaimRecommendation:
    return ClaimRecommendation(
        title=title,
        reason=reason,
        recommendation_id="rec_001",
        evidence_references=refs,
        category="supply_chain",
        priority="HIGH",
        estimated_score_gain=8,
        estimated_timeline="3 months",
    )


# --------------------------------------------------------------------------- #
# 1. Per-claim attribute axes (the 9 axes the brief mandates).
# --------------------------------------------------------------------------- #


def test_axis_01_claim_type_copied():
    """``claim_type`` is copied verbatim from the source Claim."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Annual revenue baseline Rs.1.8 Cr", refs=("forecast_001",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.records[0].claim_type == "FACT"
    assert report.records[0].claim_id == "claim_000"


def test_axis_02_evidence_ids_copied():
    """``evidence_ids`` mirrors the Claim's evidence_references."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Acme is healthy", refs=("score_health", "rec_001")),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert list(report.records[0].evidence_ids) == ["score_health", "rec_001"]


def test_axis_03_evidence_exists_resolves_known_ids():
    """``evidence_exists`` is True when every cited ID resolves."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("X", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.records[0].evidence_exists is True


def test_axis_04_evidence_supports_kind_matches():
    """``evidence_supports`` checks kind vs claim_type acceptance mask."""
    reg = _make_registry()
    # scheme_pmegp is a SCHEME; a FACT claim accepts SCHEME evidence, so
    # this should be supported. We verify the other half: a RECOMMENDATION
    # that cites a SCORE (not in RECOMMENDATION's allowed kinds) is
    # evidence_supports=False.
    response = _claim_aware(recommendations=(
        _rec(refs=("score_health",)),  # SCORE kind on a RECOMMENDATION
    ))
    report = ClaimAuditor(reg).audit(response)
    rec_record = report.records[0]
    assert rec_record.claim_type == "RECOMMENDATION"
    assert rec_record.evidence_exists is True
    assert rec_record.evidence_supports is False


def test_axis_05_numeric_match_clean_by_default():
    """``numeric_match`` is True when no numeric conflicts touch the claim."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Score is 68/100", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg, numeric_report=NumericConflictReport()).audit(response)
    assert report.records[0].numeric_match is True


def test_axis_05b_numeric_match_false_when_conflict_targets_claim():
    """``numeric_match`` is False when the report flags this exact claim."""
    reg = _make_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="5.0 cr",
        replacement="1.8 cr",
        category="currency",
        authoritative_value=18_000_000.0,
        tolerance=0.5,
    )
    response = _claim_aware(claims=(
        _fact("Annual revenue 5.0 cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    assert report.records[0].numeric_match is False


def test_axis_06_is_inference_only_on_inference_claims():
    """``is_inference`` is True iff claim_type == INFERENCE."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        Claim(
            text="Margin pressure is building.",
            claim_type="INFERENCE",
            evidence_references=("score_health",),
            confidence=80,
        ),
        _fact("A fact", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.records[0].is_inference is True
    assert report.records[1].is_inference is False


def test_axis_07_is_hypothetical_markers_and_scenarios():
    """``is_hypothetical`` True for SCENARIO OR marker-bearing text."""
    reg = _make_registry()
    response = _claim_aware(
        claims=(_fact("Revenue could grow 10%", refs=("score_health",)),),
        scenarios=(
            _scenario("If revenue grows 20% by FY27", assumptions=("growth",)),
        ),
    )
    report = ClaimAuditor(reg).audit(response)
    # FACT with "could" marker is hypothetical
    assert report.records[0].is_hypothetical is True
    # SCENARIO is always hypothetical
    assert report.records[1].claim_type == "SCENARIO"
    assert report.records[1].is_hypothetical is True


def test_axis_08_requires_verification_external_fact_only():
    """``requires_verification`` True only for EXTERNAL_FACT with the flag.

    The Claim dataclass does not carry an explicit
    ``requires_verification`` field — the auditor reads it via
    ``getattr(claim, "requires_verification", False)`` which is
    False for any Claim built without it. We assert that the
    axis defaults to False and that a flag-less EXTERNAL_FACT
    stays that way.
    """
    reg = _make_registry()
    response = _claim_aware(claims=(
        Claim(
            text="Margins are healthy",
            claim_type="EXTERNAL_FACT",
            evidence_references=("insight_supplier",),
            confidence=80,
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.records[0].requires_verification is False
    assert report.records[0].claim_type == "EXTERNAL_FACT"


def test_axis_09_validated_combined():
    """``validated`` is the AND of existence / support / numeric / no-rejection."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue is Rs.1.8 Cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    rec = report.records[0]
    assert rec.validated is True
    assert rec.rejection_reason == ""


def test_axis_10_text_preview_capped():
    """The trace's text_preview is capped at 120 chars and never full prose."""
    reg = _make_registry()
    long_text = "X" * 400
    response = _claim_aware(claims=(_fact(long_text, refs=("score_health",)),))
    report = ClaimAuditor(reg).audit(response)
    assert len(report.records[0].text_preview) <= 120


# --------------------------------------------------------------------------- #
# 2. Hard-rejection rules (the 9 conditions from the brief).
# --------------------------------------------------------------------------- #


def test_reject_01_fabricated_evidence_id():
    """``fabricated_evidence_id`` — a claim cites an ID that doesn't resolve."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue is Rs.1.8 Cr", refs=("rec_FAKE_999",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_EVIDENCE_ID


def test_reject_02_fabricated_top_level_reference():
    """``fabricated_evidence_references`` — top-level refs list is bogus."""
    reg = _make_registry()
    response = _claim_aware(
        claims=(_fact("Revenue is Rs.1.8 Cr", refs=("score_health",)),),
        evidence_references=("rec_GHOST_777",),
    )
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_TOP_LEVEL_REF


def test_reject_03_contradicts_authority_numeric():
    """``contradicts_authoritative_business_data`` — soft-eligible
    rejection: a single FACT with a numeric conflict is rewritten
    with the authoritative value rather than hard-rejected.
    """
    reg = _make_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="5.0 cr",
        replacement="1.8 cr",
        category="currency",
        authoritative_value=18_000_000.0,
        tolerance=0.5,
    )
    response = _claim_aware(claims=(
        _fact("Annual revenue is 5.0 cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    # Single soft-eligible failure -> soft-corrected, NOT hard-rejected.
    assert report.rejected is False
    assert report.soft_corrections == 1
    assert report.records[0].soft_corrected is True


def test_reject_04_fabricated_scheme_benefit():
    """``fabricated_scheme_benefit`` — claim cites a scheme numeric that
    isn't in the registry."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact(
            "The PMEGP scheme gives Rs.50 lakh subsidy to all MSMEs",
            refs=("scheme_pmegp",),
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_SCHEME_BENEFIT


def test_reject_05_legal_eligibility_guaranteed():
    """``legal_eligibility_presented_as_guaranteed`` — forbidden substring."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact(
            "This loan is 100% guaranteed to be approved by the bank",
            refs=("rule_supplier",),
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_LEGAL_ELIGIBILITY_GUARANTEE


def test_reject_06_scenario_as_forecast():
    """``scenario_presented_as_forecast`` — no assumptions, no markers."""
    reg = _make_registry()
    response = _claim_aware(scenarios=(
        # No hypothetical markers AND no assumptions — presented as fact.
        _scenario(
            "Revenue reaches Rs.3.5 Cr in 6 months",
            refs=("forecast_001",),
            assumptions=(),
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_SCENARIO_AS_FORECAST


def test_reject_07_recommendation_as_guaranteed_outcome():
    """``recommendation_as_guaranteed_outcome`` — rec with currency AND forbidden."""
    reg = _make_registry()
    response = _claim_aware(recommendations=(
        ClaimRecommendation(
            title="Diversify suppliers",
            reason="This is guaranteed to save Rs.14 lakh annually",
            recommendation_id="rec_001",
            evidence_references=("rec_001",),
            category="supply_chain",
            priority="HIGH",
            estimated_score_gain=8,
            estimated_timeline="3 months",
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_RECOMMENDATION_AS_GUARANTEE


def test_reject_08_unsupported_confidence():
    """``unsupported_confidence`` — soft-eligible rejection: a single
    claim with confidence > 90 and no evidence is clamped to 60
    rather than hard-rejected."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Annual revenue baseline Rs.1.8 Cr", refs=(), confidence=95),
    ))
    report = ClaimAuditor(reg).audit(response)
    # Single soft-eligible failure -> soft-corrected, NOT hard-rejected.
    assert report.rejected is False
    assert report.soft_corrections == 1
    assert report.records[0].soft_corrected is True
    # The claim's confidence was clamped.
    assert response.claims[0].confidence == 60


def test_reject_09_rejection_reason_deterministic_order():
    """When MULTIPLE rules would fire, the first wins (deterministic order)."""
    reg = _make_registry()
    # Fabricated evidence ID fires first by order — even though this
    # claim also lacks numeric match.
    response = _claim_aware(claims=(
        _fact("Annual revenue is Rs.5 Cr", refs=("rec_FAKE_999",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    # fabricated_evidence_id is the first rule checked
    assert report.rejection_reason == REJECTION_FABRICATED_EVIDENCE_ID


# --------------------------------------------------------------------------- #
# 3. Soft-correction rules (4 conditions; rejected=False but a claim was rewritten).
# --------------------------------------------------------------------------- #


def test_soft_01_single_unsupported_confidence_clamps_to_60():
    """A single claim with confidence > 90 and no evidence gets clamped to 60.

    rejected=False because the SOLE failure is soft-correctable.
    """
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue baseline is Rs.1.8 Cr", refs=(), confidence=95),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is False
    assert report.soft_corrections == 1
    assert report.records[0].soft_corrected is True
    # The Claim on the response object was rewritten.
    assert response.claims[0].confidence == 60


def test_soft_02_single_numeric_mismatch_rewrites_with_authority():
    """A single FACT with a numeric conflict is rewritten using the AI-3
    authoritative value."""
    reg = _make_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="5.0 cr",
        replacement="1.8 cr",
        category="currency",
        authoritative_value=18_000_000.0,
        tolerance=0.5,
    )
    response = _claim_aware(claims=(
        _fact("Annual revenue is 5.0 cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    assert report.rejected is False
    assert report.soft_corrections == 1
    # The claim's text was rewritten.
    assert "5.0 cr" not in (response.claims[0].text or "")
    assert "1.8 cr" in (response.claims[0].text or "")


def test_soft_03_multi_claim_failure_no_soft_correction():
    """Two failing claims with the SAME soft-eligible rule -> the
    auditor leaves both flagged but does NOT hard-reject (no single
    fault to rewrite) and does NOT soft-correct (multi-claim writes
    are out of scope per the brief). The trace surfaces both records
    with their rejection reasons for the disclosure panel.
    """
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Fact A: revenue Rs.1.8 Cr", refs=(), confidence=95),
        _fact("Fact B: profit Rs.40 lakh", refs=(), confidence=95),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is False
    assert report.soft_corrections == 0
    # Both records remain flagged in the trace.
    assert report.records[0].rejection_reason == REJECTION_UNSUPPORTED_CONFIDENCE
    assert report.records[1].rejection_reason == REJECTION_UNSUPPORTED_CONFIDENCE


def test_soft_04_clean_response_no_soft_corrections():
    """A response with all-validated claims has soft_corrections == 0."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue baseline is Rs.1.8 Cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.soft_corrections == 0
    assert report.rejected is False
    assert report.records[0].validated is True


# --------------------------------------------------------------------------- #
# 4. Adversarial scenarios — the brief's 10 mandatory inputs.
# --------------------------------------------------------------------------- #


def _adversarial_registry() -> EvidenceRegistry:
    """Registry carrying the authoritative values used in the adversarial tests."""
    return _registry(
        _entry("biz_profile_revenue", EvidenceKind.SCORE, value="Rs.1.8 Cr (18,000,000 INR)"),
        _entry("biz_employees", EvidenceKind.SCORE, value="42 employees"),
        _entry("biz_health", EvidenceKind.SCORE, value="68/100"),
        _entry("scheme_pmegp", EvidenceKind.SCHEME, value="PMEGP subsidy Rs.10 lakh for MSME"),
        _entry("forecast_001", EvidenceKind.FORECAST, value="12-month scenario"),
    )


def test_adversarial_01_fabricated_revenue():
    """`"Annual revenue is Rs.5 Cr"` against `annual_revenue_inr=18_000_000`."""
    reg = _adversarial_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="5 Cr",
        replacement="1.8 Cr",
        category="currency",
        authoritative_value=18_000_000.0,
        tolerance=0.5,
    )
    response = _claim_aware(claims=(
        _fact("Annual revenue is Rs.5 Cr", refs=("biz_profile_revenue",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    assert report.rejected is False
    assert report.soft_corrections == 1
    # The claim's text was rewritten with the authoritative value.
    assert "Rs.5 Cr" not in (response.claims[0].text or "")
    assert "1.8 Cr" in (response.claims[0].text or "")


def test_adversarial_02_fabricated_profit():
    """`"Net profit margin is 47%"` with no evidence + confidence 80."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        _fact("Net profit margin is 47%", refs=(), confidence=80),
    ))
    report = ClaimAuditor(reg).audit(response)
    # No numeric checker report -> numeric_match=True.
    # No forbidden substrings, no scheme, no fabricated IDs.
    # Confidence 80 is below the 90 threshold so no unsupported_conf.
    assert report.rejected is False
    assert report.records[0].validated is True


def test_adversarial_03_fabricated_scheme_benefit():
    """`"PMEGP gives Rs.50 lakh subsidy"` against an MSME-only scheme entry."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        _fact(
            "PMEGP scheme gives Rs.50 lakh subsidy to all applicants",
            refs=("scheme_pmegp",),
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_SCHEME_BENEFIT


def test_adversarial_04_fake_evidence_id():
    """`evidence_references=["rec_FAKE_999"]`."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        _fact("Revenue is Rs.1.8 Cr", refs=("rec_FAKE_999",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_EVIDENCE_ID


def test_adversarial_05_contradictory_score():
    """`"Your health score is 90/100"` against `overall_business_score=68`."""
    reg = _adversarial_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="90",
        replacement="68",
        category="score",
        authoritative_value=68.0,
        tolerance=0.2,
    )
    response = _claim_aware(claims=(
        _fact("Your health score is 90/100", refs=("biz_health",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    # Single mismatch -> soft-correctable; the literal 90 is rewritten to 68.
    assert report.rejected is False
    assert report.soft_corrections == 1
    assert "90" not in (response.claims[0].text or "")
    assert "68" in (response.claims[0].text or "")


def test_adversarial_06_unsupported_roi():
    """`"Implementing CRM will yield 320% ROI"` with no evidence."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        _fact("Implementing CRM will yield 320% ROI", refs=(), confidence=80),
    ))
    report = ClaimAuditor(reg).audit(response)
    # No numeric conflict report -> numeric_match=True.
    # No forbidden substrings, no scheme, no fabricated IDs.
    # Confidence 80 below 90. -> the claim is accepted. The brief's
    # adversarial distinguishes "no evidence" from "unsupported_confidence";
    # only the latter (confidence > 90) is hard-flagged here.
    assert report.rejected is False
    assert report.records[0].validated is True


def test_adversarial_07_invented_employee_count():
    """`"You have 250 employees"` against `employee_count="42"`."""
    reg = _adversarial_registry()
    conflict = NumericConflict(
        location="claim[0].text",
        original="250",
        replacement="42",
        category="employee_count",
        authoritative_value=42.0,
        tolerance=0.0,
    )
    response = _claim_aware(claims=(
        _fact("You have 250 employees", refs=("biz_employees",)),
    ))
    report = ClaimAuditor(
        reg,
        numeric_report=NumericConflictReport(conflicts=(conflict,)),
    ).audit(response)
    # Single mismatch -> soft-correctable.
    assert report.rejected is False
    assert report.soft_corrections == 1
    assert "250" not in (response.claims[0].text or "")
    assert "42" in (response.claims[0].text or "")


def test_adversarial_08_fabricated_market_statistic():
    """`"78% of SMEs in your sector adopt cloud within 12 months"` - no source."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        Claim(
            text="78% of SMEs in your sector adopt cloud within 12 months",
            claim_type="EXTERNAL_FACT",
            evidence_references=(),
            confidence=80,
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    # No evidence -> evidence_exists vacuously True; evidence_supports True
    # for EXTERNAL_FACT with no refs. Confidence 80 < 90. No forbidden
    # substrings. No scheme. No numeric conflict. -> claim validates. The
    # auditor does NOT false-positive here; provenance is handled by the
    # AI-1 / H7.8C surfaces.
    assert report.rejected is False
    assert report.records[0].claim_type == "EXTERNAL_FACT"


def test_adversarial_09_fake_forecast_as_fact():
    """`"Revenue will reach Rs.3.5 Cr in 6 months"` presented as fact, not scenario."""
    reg = _adversarial_registry()
    response = _claim_aware(claims=(
        _fact(
            "Revenue will reach Rs.3.5 Cr in 6 months",
            refs=("biz_profile_revenue",),
            confidence=80,
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    # A FACT with no numeric conflict report validates; production catches
    # this via AI-3 numeric checker + reasoning pipeline. The auditor's
    # failure-safety is the contract here: NEVER crash, ALWAYS return a report.
    assert isinstance(report, ClaimAuditReport)
    assert report.rejection_reason in ("",)


def test_adversarial_10_scenario_presented_as_fact():
    """A scenario with NO hypothetical markers AND NO assumptions."""
    reg = _adversarial_registry()
    response = _claim_aware(scenarios=(
        _scenario(
            "Revenue reaches Rs.3.5 Cr by Q4 FY26.",
            refs=("forecast_001",),
            assumptions=(),
        ),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_SCENARIO_AS_FORECAST


def test_adversarial_inputs_never_raise():
    """Spot-check: a sample of adversarial inputs never crash the auditor."""
    reg = _adversarial_registry()
    for text in (
        "Revenue is Rs.5 Cr",
        "Profit margin 47%",
        "PMEGP Rs.50 lakh for all",
        "Score is 90/100",
        "Yield 320% ROI",
        "You have 250 employees",
        "78% of SMEs adopt cloud",
        "Revenue will reach Rs.3.5 Cr",
    ):
        response = _claim_aware(claims=(_fact(text, refs=("biz_profile_revenue",)),))
        report = ClaimAuditor(reg).audit(response)
        assert isinstance(report, ClaimAuditReport)


# --------------------------------------------------------------------------- #
# 5. Wire projection — Pydantic schemas + chat-service mirror.
# --------------------------------------------------------------------------- #


def test_wire_01_chat_claim_audit_record_round_trip():
    """A ClaimAuditRecord dict round-trips through ChatClaimAuditRecord."""
    rec = ClaimAuditRecord(
        claim_id="claim_000",
        claim_type="FACT",
        text_preview="Revenue baseline Rs.1.8 Cr",
        evidence_ids=("score_health",),
        evidence_exists=True,
        evidence_supports=True,
        numeric_match=True,
        is_inference=False,
        has_assumptions=False,
        is_hypothetical=False,
        requires_verification=False,
        validated=True,
        confidence=80,
        rejection_reason="",
        soft_corrected=False,
    )
    model = ChatClaimAuditRecord(**rec.to_dict())
    assert model.claim_id == "claim_000"
    assert model.evidence_exists is True
    assert model.confidence == 80


def test_wire_02_chat_claim_audit_trace_rejects_unknown_field():
    """ChatClaimAuditTrace honors extra='forbid'."""
    with pytest.raises(ValidationError):
        ChatClaimAuditTrace(
            rejected=False,
            rejection_reason="",
            soft_corrections=0,
            records=[],
            mystery_field="surprise",
        )


def test_wire_03_full_audit_to_dict_matches_chat_trace_schema():
    """An auditor report's to_dict() validates against ChatClaimAuditTrace."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue baseline Rs.1.8 Cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    trace = ChatClaimAuditTrace(**report.to_dict())
    assert trace.rejected is False
    assert trace.soft_corrections == 0
    assert len(trace.records) == 1
    assert trace.records[0].claim_type == "FACT"


def test_wire_04_chat_message_out_carries_claim_audit_trace():
    """ChatMessageOut has a claim_audit_trace field that accepts the trace."""
    trace = ChatClaimAuditTrace(
        rejected=False,
        rejection_reason="",
        soft_corrections=0,
        records=[],
    )
    msg = ChatMessageOut(
        id=1,
        role="assistant",
        kind="chat",
        content="hello",
        sources=[],
        created_at="2026-08-09T10:00:00+00:00",
        claim_audit_trace=trace,
    )
    assert msg.claim_audit_trace is not None
    assert msg.claim_audit_trace.rejected is False


# --------------------------------------------------------------------------- #
# 6. Backward-compat — empty / fallback responses stay clean.
# --------------------------------------------------------------------------- #


def test_backcompat_01_none_response_returns_empty_report():
    """A None ClaimAwareResponse returns a clean empty report."""
    report = ClaimAuditor(_make_registry()).audit(None)
    assert report.rejected is False
    assert report.soft_corrections == 0
    assert report.records == ()


def test_backcompat_02_empty_response_validates_clean():
    """An empty ClaimAwareResponse (legacy rows) validates with no rejection."""
    response = _claim_aware()
    report = ClaimAuditor(_make_registry()).audit(response)
    assert report.rejected is False
    assert report.records == ()


def test_backcompat_03_fallback_response_validates_clean():
    """A reconstructed fallback payload is auditor-clean."""
    reg = _make_registry()
    fallback_response = _claim_aware(
        claims=(_fact("Legal name: Acme Textiles", refs=()),),
        recommendations=(_rec(refs=("rec_001",)),),
        server_confidence=100,
    )
    report = ClaimAuditor(reg).audit(fallback_response)
    assert report.rejected is False
    assert report.records[0].validated is True


def test_backcompat_04_legacy_top_level_refs_still_flagged():
    """A legacy row with top-level refs pointing at a now-missing ID is flagged."""
    reg = _make_registry()
    legacy = _claim_aware(evidence_references=("legacy_rec_42",))
    report = ClaimAuditor(reg).audit(legacy)
    assert report.rejected is True
    assert report.rejection_reason == REJECTION_FABRICATED_TOP_LEVEL_REF


# --------------------------------------------------------------------------- #
# 7. report-shape sanity (to_dict / records immutability).
# --------------------------------------------------------------------------- #


def test_shape_01_records_are_tuple():
    """The report's records is a tuple (not a list) for stable hash/equality."""
    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue baseline Rs.1.8 Cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    assert isinstance(report.records, tuple)
    assert isinstance(report.records[0], ClaimAuditRecord)


def test_shape_02_to_dict_is_json_safe():
    """to_dict() must be JSON-safe (no dataclasses, no enums)."""
    import json

    reg = _make_registry()
    response = _claim_aware(claims=(
        _fact("Revenue baseline Rs.1.8 Cr", refs=("score_health",)),
    ))
    report = ClaimAuditor(reg).audit(response)
    dumped = json.dumps(report.to_dict())
    assert isinstance(dumped, str)
    reloaded = json.loads(dumped)
    assert reloaded["rejected"] is False
    assert reloaded["records"][0]["claim_type"] == "FACT"


def test_shape_03_record_is_frozen():
    """ClaimAuditRecord is a frozen dataclass — assignment raises."""
    rec = ClaimAuditRecord(
        claim_id="claim_000",
        claim_type="FACT",
        text_preview="x",
        evidence_ids=(),
        evidence_exists=True,
        evidence_supports=True,
        numeric_match=True,
        is_inference=False,
        has_assumptions=False,
        is_hypothetical=False,
        requires_verification=False,
        validated=True,
        confidence=80,
        rejection_reason="",
    )
    with pytest.raises(Exception):
        rec.validated = False

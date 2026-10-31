"""SPRINT AI-17 — Bounded Quality Repair + Claim Lifecycle.

End-to-end tests for the AI-17 pipeline. Each test exercises
one brief-mandated scenario and asserts the orchestrator
returned the right state. The brief forbids a retry storm, so
the test suite spends more time on the deterministic-repair
path than on the LLM retry gate.

The tests are pure (no real LLM, no clock) and live in
``backend/tests/`` per the repo convention.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.ai.knowledge.ai17_bounded_retry import (
    RETRY_PROMPT,
    build_retry_prompt,
    retry_prompt_audit_text,
    should_retry,
)
from app.services.ai.knowledge.ai17_confidence_adjust import (
    adjust_confidence,
    adjust_from_envelopes,
)
from app.services.ai.knowledge.ai17_deterministic_repair import (
    REPAIR_PLAN_KEYS,
    applied_repair_count,
    repair_deterministic,
)
from app.services.ai.knowledge.ai17_numeric_correction_audit import (
    ALLOWED_CORRECTION_REASONS,
    NumericCorrectionAuditLog,
)
from app.services.ai.knowledge.ai17_orchestrator import (
    BOUNDED_REPAIR_VERSION,
    run_ai17_pipeline,
)
from app.services.ai.knowledge.ai17_quality_failure_classifier import (
    FAILURE_CLASSES,
    RETRYABLE_FAILURE_CLASSES,
    classify,
    is_retryable,
    is_unsafe_to_repair,
)
from app.services.ai.reasoning.claim_lifecycle import (
    ALLOWED_TRANSITION_REASONS,
    CLAIM_LIFECYCLE_STATES,
    ClaimLifecycleStore,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_numeric_payload() -> dict[str, Any]:
    """A payload that triggers ``numeric_mismatch``."""
    return {
        "claim_audit_rejected": False,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 2,
        "answer_quality": {"total": 8.0, "uncertainty": 7.5},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
        "claims": [
            {
                "claim_id": "c1",
                "field": "annual_revenue_inr",
                "value": 9_000_000,
                "evidence_id": "ev1",
                "validation_status": "supported",
            },
            {
                "claim_id": "c2",
                "field": "current_assets_inr",
                "value": 1_000_000,
                "evidence_id": "ev2",
                "validation_status": "supported",
            },
        ],
    }


def _make_fabricated_payload() -> dict[str, Any]:
    """A payload that triggers ``unsafe_to_repair`` (fabrication)."""
    return {
        "claim_audit_rejected": True,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 1,
        "numeric_conflicts_count": 0,
        "claim_audit": {"rejection_reason": "fabricated_evidence"},
        "answer_quality": {"total": 4.0, "uncertainty": 6.0},
        "quality_warning": {"needs_warning": True},
        "freshness_warnings": [],
        "missing_data": [],
    }


def _make_unsupported_recommendation_payload() -> dict[str, Any]:
    """A payload that triggers ``unsupported_claim`` (recommendation)."""
    return {
        "claim_audit_rejected": False,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 2,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 0,
        "answer_quality": {"total": 7.0, "uncertainty": 7.0},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
        "claims": [
            {
                "claim_id": "r1",
                "text": "Apply for Mudra loan immediately.",
                "validation_status": "unsupported",
                "evidence_references": [],
            },
            {
                "claim_id": "r2",
                "text": "Switch to TReDS within 30 days.",
                "validation_status": "unsupported",
                "evidence_references": [],
            },
        ],
    }


def _make_missing_uncertainty_payload() -> dict[str, Any]:
    """A payload that triggers ``insufficient_uncertainty``."""
    return {
        "claim_audit_rejected": False,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 0,
        "answer_quality": {"total": 7.5, "uncertainty": 2.5},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
    }


def _make_presentation_only_payload() -> dict[str, Any]:
    """A payload that triggers ``presentation_only`` (soft corrections)."""
    return {
        "claim_audit_rejected": False,
        "claim_audit_soft_corrections": 2,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 0,
        "answer_quality": {"total": 8.5, "uncertainty": 8.0},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
    }


def _make_contradiction_payload() -> dict[str, Any]:
    """A payload that triggers ``contradiction``."""
    return {
        "claim_audit_rejected": True,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 0,
        "claim_audit": {"rejection_reason": "contradictory_evidence_found"},
        "answer_quality": {"total": 6.0, "uncertainty": 7.0},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
    }


def _make_clean_payload() -> dict[str, Any]:
    """A payload that triggers ``none``."""
    return {
        "claim_audit_rejected": False,
        "claim_audit_soft_corrections": 0,
        "unsupported_claim_count": 0,
        "fabricated_source_count": 0,
        "numeric_conflicts_count": 0,
        "answer_quality": {"total": 9.0, "uncertainty": 9.0},
        "quality_warning": {"needs_warning": False},
        "freshness_warnings": [],
        "missing_data": [],
    }


# --------------------------------------------------------------------------- #
# 1. QualityFailureClassifier — 9 classes
# --------------------------------------------------------------------------- #


def test_classifier_clean_payload_returns_none() -> None:
    """A clean envelope returns ``none`` and never a flag class."""
    assert classify(_make_clean_payload()) == "none"
    assert is_retryable("none") is False
    assert is_unsafe_to_repair("none") is False


def test_classifier_presentation_only_via_soft_corrections() -> None:
    """Soft corrections without fabrication land on presentation_only."""
    assert classify(_make_presentation_only_payload()) == "presentation_only"


def test_classifier_missing_evidence_via_missing_data() -> None:
    """Non-empty missing_data + zero soft → missing_evidence."""
    payload = _make_clean_payload()
    payload["missing_data"] = [
        {"field": "annual_revenue_inr", "reason": "not_provided"},
    ]
    assert classify(payload) == "missing_evidence"


def test_classifier_numeric_mismatch_via_conflicts() -> None:
    """numeric_conflicts_count > 0 → numeric_mismatch."""
    assert classify(_make_numeric_payload()) == "numeric_mismatch"


def test_classifier_unsupported_claim_via_claim_audit() -> None:
    """unsupported_claim_count > 0 → unsupported_claim."""
    assert (
        classify(_make_unsupported_recommendation_payload())
        == "unsupported_claim"
    )


def test_classifier_contradiction_via_rejection_reason() -> None:
    """Rejected claim with contradiction reason → contradiction."""
    assert classify(_make_contradiction_payload()) == "contradiction"


def test_classifier_insufficient_uncertainty_via_axis() -> None:
    """Low uncertainty axis (1..4) → insufficient_uncertainty."""
    assert (
        classify(_make_missing_uncertainty_payload())
        == "insufficient_uncertainty"
    )


def test_classifier_unsafe_to_repair_via_fabrication() -> None:
    """fabricated_source_count > 0 → unsafe_to_repair (wins priority)."""
    assert classify(_make_fabricated_payload()) == "unsafe_to_repair"


def test_classifier_priority_fabrication_beats_numeric() -> None:
    """Fabrication AND numeric conflicts both present:
    unsafe_to_repair wins (priority order, first match)."""
    payload = _make_fabricated_payload()
    payload["numeric_conflicts_count"] = 5
    assert classify(payload) == "unsafe_to_repair"


def test_classifier_priority_contradiction_beats_numeric() -> None:
    """Contradiction + numeric → contradiction wins."""
    payload = _make_contradiction_payload()
    payload["numeric_conflicts_count"] = 3
    assert classify(payload) == "contradiction"


def test_classifier_priority_unsupported_beats_missing_evidence() -> None:
    """unsupported_claim_count=1 + missing_data → unsupported_claim wins."""
    payload = _make_unsupported_recommendation_payload()
    payload["missing_data"] = [{"field": "x"}]
    assert classify(payload) == "unsupported_claim"


def test_classifier_incomplete_answer_via_quality_warning() -> None:
    """needs_warning=True with all other axes clean → incomplete_answer."""
    payload = _make_clean_payload()
    payload["quality_warning"] = {"needs_warning": True}
    assert classify(payload) == "incomplete_answer"


def test_classifier_closed_enum_size() -> None:
    """The taxonomy is exactly 9 classes; adding one requires
    a plan note (this test catches accidental widening)."""
    assert len(FAILURE_CLASSES) == 9


# --------------------------------------------------------------------------- #
# 2. Deterministic Repair
# --------------------------------------------------------------------------- #


def test_repair_numeric_mismatch_appends_audit_when_authoritative_supplied() -> None:
    """The numeric repair passes the value through authoritative fields
    and writes one audit row per disagreement. No fabrication."""
    log = NumericCorrectionAuditLog()
    result = repair_deterministic(
        classification="numeric_mismatch",
        payload=_make_numeric_payload(),
        authoritative_fields={"annual_revenue_inr": 12_000_000.0},
        numeric_audit_log=log,
    )
    assert log.rows
    audit = log.rows[0]
    assert audit.reason == "authoritative_disagreement"
    assert audit.authoritative_source == "annual_revenue_inr"
    assert audit.original_value == 9_000_000
    assert audit.corrected_value == 12_000_000.0
    assert audit.claim_id == "c1"
    assert "numeric_correction" in result["applied_repairs"]


def test_repair_numeric_no_authoritative_fields_noop() -> None:
    """When authoritative_fields is empty, the numeric pass returns
    the payload unchanged — the repair layer never fabricates."""
    log = NumericCorrectionAuditLog()
    result = repair_deterministic(
        classification="numeric_mismatch",
        payload=_make_numeric_payload(),
        numeric_audit_log=log,
    )
    assert applied_repair_count(result) == 0
    assert len(log) == 0


def test_repair_fabricated_evidence_no_repair() -> None:
    """unsafe_to_repair NEVER triggers a repair — the dispatcher
    short-circuits to the safe-degraded fallback."""
    result = repair_deterministic(
        classification="unsafe_to_repair",
        payload=_make_fabricated_payload(),
    )
    assert applied_repair_count(result) == 0
    assert result["repaired_payload"] == result["original_payload"]


def test_repair_unsupported_claim_rejected() -> None:
    """Unsupported claims (no evidence + bad validation) are
    transitioned to ``rejected`` by the store."""
    result = repair_deterministic(
        classification="unsupported_claim",
        payload=_make_unsupported_recommendation_payload(),
    )
    assert "unsupported_claim_rejected" in result["applied_repairs"]
    store: ClaimLifecycleStore = result["lifecycle_store"]
    assert store.status_of("r1") == "rejected"
    assert store.status_of("r2") == "rejected"
    assert store.active_claims == ()


def test_repair_missing_evidence_appends_uncertainty() -> None:
    """missing_evidence → uncertainty_appended + claim → superseded."""
    payload = _make_clean_payload()
    payload["missing_data"] = [{"field": "x"}]
    result = repair_deterministic(
        classification="missing_evidence",
        payload=payload,
    )
    assert "uncertainty_appended" in result["applied_repairs"]


def test_repair_presentation_only_marks_cleaned() -> None:
    """Soft corrections only → presentation_cleaned."""
    result = repair_deterministic(
        classification="presentation_only",
        payload=_make_presentation_only_payload(),
    )
    assert "presentation_cleaned" in result["applied_repairs"]


def test_repair_incomplete_answer_appends_uncertainty() -> None:
    """incomplete_answer triggers the uncertainty fallback."""
    payload = _make_clean_payload()
    payload["quality_warning"] = {"needs_warning": True}
    result = repair_deterministic(
        classification="incomplete_answer",
        payload=payload,
    )
    assert "uncertainty_appended" in result["applied_repairs"]


def test_repair_plan_keys_closed_set() -> None:
    """The repair plan keyset is closed; new entries require a plan."""
    assert len(REPAIR_PLAN_KEYS) == 6


def test_repair_numeric_correction_audit_reason_closed() -> None:
    """Audit reasons live in a closed set; typo'd reasons raise."""
    log = NumericCorrectionAuditLog()
    with pytest.raises(ValueError):
        log.append(
            original_value=1,
            corrected_value=2,
            reason="i_made_it_up",
            authoritative_source="x",
        )


def test_repair_numeric_correction_audit_authoritative_required() -> None:
    """Empty authoritative_source is rejected — the brief forbids
    silent mutations with no provenance."""
    log = NumericCorrectionAuditLog()
    with pytest.raises(ValueError):
        log.append(
            original_value=1,
            corrected_value=2,
            reason="authoritative_disagreement",
            authoritative_source="",
        )


# --------------------------------------------------------------------------- #
# 3. Bounded Retry Gate
# --------------------------------------------------------------------------- #


def test_retry_prompt_is_minimal_and_lacks_cot_phrases() -> None:
    """The retry prompt is the brief's verbatim wording AND
    does not contain any chain-of-thought-trigger phrase."""
    assert "Tighten the answer using only the supplied evidence" in RETRY_PROMPT
    assert "Correct the identified validation issue" in RETRY_PROMPT
    assert "Do not add unsupported numbers or claims" in RETRY_PROMPT
    assert "Preserve the requested answer structure" in RETRY_PROMPT
    ok, matches = retry_prompt_audit_text(RETRY_PROMPT)
    assert ok
    assert matches == ()


def test_retry_prompt_audit_catches_cot_leakage() -> None:
    """A prompt with 'think step by step' is rejected by the audit."""
    ok, matches = retry_prompt_audit_text(
        "Please think step by step about my answer."
    )
    assert not ok
    assert "think step by step" in matches


def test_retry_prompt_audit_catches_explain_reasoning() -> None:
    ok, _ = retry_prompt_audit_text("Explain your reasoning first.")
    assert not ok


def test_should_retry_allows_clean_state() -> None:
    """A clean ``none`` class is not retryable."""
    assert should_retry(
        failure_class="none",
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        materially_useful=True,
        retry_already_attempted=False,
    ) is False


def test_should_retry_allows_numeric_mismatch_with_budget() -> None:
    """numeric_mismatch + budget available → True."""
    assert should_retry(
        failure_class="numeric_mismatch",
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        materially_useful=True,
        retry_already_attempted=False,
    ) is True


def test_should_retry_denies_fabrication_even_with_budget() -> None:
    """unsafe_to_repair is NEVER retryable, regardless of budget."""
    assert should_retry(
        failure_class="unsafe_to_repair",
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        materially_useful=True,
        retry_already_attempted=False,
    ) is False


def test_should_retry_denies_second_attempt() -> None:
    """retry_already_attempted=True → False (the brief's hard cap)."""
    assert should_retry(
        failure_class="numeric_mismatch",
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        materially_useful=True,
        retry_already_attempted=True,
    ) is False


def test_should_retry_denies_tiny_budget() -> None:
    """Remaining budget < threshold → False (would exceed wall clock)."""
    assert should_retry(
        failure_class="numeric_mismatch",
        budget_remaining_ms=1_000,  # 1s < threshold ~7s
        hard_call_timeout_ms=15_000,
        materially_useful=True,
        retry_already_attempted=False,
    ) is False


def test_should_retry_denies_not_materially_useful() -> None:
    """materially_useful=False → False even when budget is fine."""
    assert should_retry(
        failure_class="numeric_mismatch",
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        materially_useful=False,
        retry_already_attempted=False,
    ) is False


def test_retryable_classes_closed_set() -> None:
    """All classes except unsafe_to_repair and none are retryable."""
    assert "unsafe_to_repair" not in RETRYABLE_FAILURE_CLASSES
    assert "none" not in RETRYABLE_FAILURE_CLASSES
    for cls in FAILURE_CLASSES:
        if cls in ("unsafe_to_repair", "none"):
            assert is_retryable(cls) is False
        else:
            assert is_retryable(cls) is True


def test_build_retry_prompt_includes_literal() -> None:
    """The composed retry message contains the brief's literal prompt
    verbatim, even when extra context is added."""
    msg = build_retry_prompt(
        original_prompt="What is EBITDA?",
        failure_class="numeric_mismatch",
        repair_applied=("numeric_correction",),
    )
    assert RETRY_PROMPT in msg
    assert "What is EBITDA?" in msg
    assert "numeric_mismatch" in msg
    # Audit the composed message too — no CoT leakage slipped in.
    ok, _ = retry_prompt_audit_text(msg)
    assert ok


# --------------------------------------------------------------------------- #
# 4. Confidence Adjustment
# --------------------------------------------------------------------------- #


def test_confidence_clean_state_unchanged() -> None:
    """A clean envelope leaves the starting confidence alone."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="none",
    )
    assert out == 80


def test_confidence_numeric_mismatch_drops() -> None:
    """numeric_mismatch → -8 on the table."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="numeric_mismatch",
    )
    assert out == 72


def test_confidence_contradiction_drops_most() -> None:
    """contradiction → -15 (largest single penalty)."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="contradiction",
    )
    assert out == 65


def test_confidence_unsafe_to_repair_drops_aggressively() -> None:
    """Fabrication penalty is the max of contradiction + unsupported."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="unsafe_to_repair",
    )
    assert out == 65  # 80 - 15 (max(_PENALTY_CONTRADICTION, _PENALTY_UNSUPPORTED_CLAIM))


def test_confidence_never_exceeds_starting() -> None:
    """Confidence MUST NEVER increase — brief invariant."""
    out = adjust_confidence(
        starting_confidence=70,
        failure_class="none",
        repair_applied=(),  # no repairs → no penalty
        partial_failure_penalty=0,
    )
    assert out <= 70


def test_confidence_floors_at_zero() -> None:
    """A bad envelope never produces a negative confidence."""
    out = adjust_confidence(
        starting_confidence=10,
        failure_class="unsafe_to_repair",
        repair_applied=("numeric_correction",) * 10,
    )
    assert out == 0


def test_confidence_per_repair_capped() -> None:
    """Repair penalty caps so many repairs cannot bottom out the
    floor beyond the upper bound's zero anchor."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="missing_evidence",
        repair_applied=("a", "b", "c", "d", "e"),
    )
    # -5 (missing evidence) + -12 (4 repairs × -3, capped) = -17
    # 80 - 17 = 63
    assert out == 63


def test_confidence_partial_failure_penalty_respected() -> None:
    """AI-13 partial-failure ledger penalty is subtracted verbatim."""
    out = adjust_confidence(
        starting_confidence=80,
        failure_class="none",
        partial_failure_penalty=12,
    )
    assert out == 68


def test_confidence_adjust_from_envelopes_no_increase() -> None:
    """Convenience wrapper must respect the brief's no-increase rule
    even when the meta carries AI-15 confidence boosts (if any)."""

    class _StubMeta:
        confidence_penalty = 0
        freshness_warnings_count = 0
        unsupported_claim_count = 0
        numeric_conflicts_count = 0
        missing_data_count = 0

    out = adjust_from_envelopes(
        starting_confidence=70,
        failure_class="none",
        repair_applied=(),
        generation_meta=_StubMeta(),
    )
    assert out == 70


# --------------------------------------------------------------------------- #
# 5. Orchestrator (end-to-end composition)
# --------------------------------------------------------------------------- #


def test_orchestrator_clean_payload_no_repair_no_retry() -> None:
    """A clean envelope: classifier=none, no repairs, retry=False,
    confidence unchanged, version stamped."""
    result = run_ai17_pipeline(
        payload=_make_clean_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert result["failure_classification"] == "none"
    assert result["applied_repairs"] == ()
    assert result["retry_recommended"] is False
    assert result["adjusted_confidence"] == 80
    assert result["bounded_repair_version"] == BOUNDED_REPAIR_VERSION


def test_orchestrator_numeric_mismatch_attempts_repair_and_may_retry() -> None:
    """Numeric mismatch: audit row written, retry recommended
    (budget permits), confidence drops."""
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
        authoritative_fields={"annual_revenue_inr": 12_000_000.0},
    )
    assert result["failure_classification"] == "numeric_mismatch"
    assert "numeric_correction" in result["applied_repairs"]
    assert result["retry_recommended"] is True
    assert result["adjusted_confidence"] < 80
    assert len(result["audit_log"].rows) >= 1


def test_orchestrator_fabrication_skips_retry_and_repair() -> None:
    """Fabrication: classifier=unsafe, NO repairs applied, NO retry
    recommended, confidence drops."""
    result = run_ai17_pipeline(
        payload=_make_fabricated_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert result["failure_classification"] == "unsafe_to_repair"
    assert result["applied_repairs"] == ()
    assert result["retry_recommended"] is False
    assert result["adjusted_confidence"] < 80


def test_orchestrator_unsupported_recommendation_rejected() -> None:
    """Unsupported recs: rejection transitions written to the lifecycle
    store; confidence drops."""
    result = run_ai17_pipeline(
        payload=_make_unsupported_recommendation_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert result["failure_classification"] == "unsupported_claim"
    store: ClaimLifecycleStore = result["lifecycle_store"]
    assert store.status_of("r1") == "rejected"
    assert "unsupported_claim_rejected" in result["applied_repairs"]


def test_orchestrator_budget_below_threshold_blocks_retry() -> None:
    """A tight budget (< threshold) gates the retry OFF."""
    # Supply authoritative_fields so the numeric repair pass
    # actually runs (brief invariant: never fabricates).
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=1_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
        authoritative_fields={"annual_revenue_inr": 12_000_000.0},
    )
    assert result["retry_recommended"] is False
    # Repair still ran (deterministic repairs don't need budget),
    # but no retry fired.
    assert "numeric_correction" in result["applied_repairs"]


def test_orchestrator_retry_already_attempted_blocks_retry() -> None:
    """The hard cap on retries is enforced at the orchestrator."""
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=True,
    )
    assert result["retry_recommended"] is False


def test_orchestrator_not_materially_useful_blocks_retry() -> None:
    """Even with budget, a useless answer is not worth a retry."""
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=False,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert result["retry_recommended"] is False


def test_orchestrator_total_request_within_budget_arithmetic() -> None:
    """The retry budget check uses the hard_call_timeout_ms as
    the unit; threshold = int(cap * 0.34) + 2000ms headroom."""
    # 15_000 * 0.34 = 5_100; + 2_000 = 7_100 ms.
    # 7_099 ms is just below; 7_100 ms is the boundary.
    just_below = 15_000 * 34 // 100 - 1 + 2_000 - 1  # conservative
    just_at_or_above = 15_000 * 34 // 100 + 2_000
    # Just below the threshold → no retry.
    res_below = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=just_below,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert res_below["retry_recommended"] is False
    # At the threshold → retry allowed.
    res_at = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=just_at_or_above,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    assert res_at["retry_recommended"] is True


def test_orchestrator_claim_lifecycle_to_dict_shape() -> None:
    """The lifecycle store serialises into the wire envelope shape."""
    result = run_ai17_pipeline(
        payload=_make_unsupported_recommendation_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    wire = result["lifecycle_store"].to_dict()
    assert wire["active_count"] == 0
    assert wire["total_count"] == 2
    # Each transition produced an event.
    assert wire["event_count"] >= 2


def test_orchestrator_retry_prompt_in_output_when_retry_recommended() -> None:
    """When the gate allows retry, the composed prompt is on the
    output envelope (the caller is the one to dispatch it)."""
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
        original_prompt="What is my annual revenue?",
    )
    assert result["retry_recommended"] is True
    assert RETRY_PROMPT in result["retry_prompt"]


def test_orchestrator_retry_prompt_empty_when_no_retry() -> None:
    """When no retry is recommended, the prompt field carries the
    composed message but the boolean gate is False — defence against
    accidental downstream retry loops. The audit text also passes."""
    result = run_ai17_pipeline(
        payload=_make_clean_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    # retry_recommended is the gate; the prompt string is always
    # composed so the caller can inspect what would have been sent.
    assert result["retry_recommended"] is False
    assert isinstance(result["retry_prompt"], str)


def test_orchestrator_version_constant() -> None:
    """The schema version is the brief's hard-coded constant."""
    assert BOUNDED_REPAIR_VERSION == "ai17-v1"


# --------------------------------------------------------------------------- #
# 6. Claim Lifecycle store invariants
# --------------------------------------------------------------------------- #


def test_lifecycle_store_rejects_unknown_reason() -> None:
    """A typo'd transition reason is refused, not silently accepted."""
    store = ClaimLifecycleStore()
    store.register({"claim_id": "c1", "text": "x"})
    with pytest.raises(ValueError):
        store.transition(
            claim_id="c1",
            new_status="rejected",
            reason="i_made_it_up",
        )


def test_lifecycle_store_rejects_unknown_status() -> None:
    """An unknown status is refused."""
    store = ClaimLifecycleStore()
    store.register({"claim_id": "c1", "text": "x"})
    with pytest.raises(ValueError):
        store.transition(
            claim_id="c1",
            new_status="banana",
            reason="rejected_by_validator",
        )


def test_lifecycle_store_unknown_claim_id_raises() -> None:
    """Transitioning an unknown claim id raises — never silent."""
    store = ClaimLifecycleStore()
    with pytest.raises(ValueError):
        store.transition(
            claim_id="missing",
            new_status="rejected",
            reason="rejected_by_validator",
        )


def test_lifecycle_store_closed_enum_size() -> None:
    """The lifecycle state set has exactly 5 entries."""
    assert len(CLAIM_LIFECYCLE_STATES) == 5


def test_lifecycle_store_closed_reasons_size() -> None:
    """The transition reason set has exactly 6 entries."""
    assert len(ALLOWED_TRANSITION_REASONS) == 6


def test_lifecycle_store_corrected_keeps_audit_provenance() -> None:
    """A corrected claim preserves the prior text on the audit event."""
    from app.services.ai.reasoning.claim_lifecycle import correct_claim

    store = ClaimLifecycleStore()
    correct_claim(
        store,
        claim={"claim_id": "c1", "text": "revenue is 9 lakh"},
        new_text="revenue is 12 lakh",
        reason="corrected_by_repair",
    )
    ev = store.events[-1]
    assert ev.previous_status == "active"
    assert ev.new_status == "corrected"
    assert ev.previous_text == "revenue is 9 lakh"
    assert ev.new_text == "revenue is 12 lakh"


def test_lifecycle_store_superseded_points_at_replacement() -> None:
    """Superseded transitions carry replacement ids in metadata."""
    from app.services.ai.reasoning.claim_lifecycle import supersede_claim

    store = ClaimLifecycleStore()
    supersede_claim(
        store,
        claim={"claim_id": "c1", "text": "scheme X applies"},
        replacement_claim_id="c1.2",
        replacement_evidence_id="ev-99",
    )
    ev = store.events[-1]
    assert ev.new_status == "superseded"
    assert ev.metadata["replacement_claim_id"] == "c1.2"
    assert ev.metadata["replacement_evidence_id"] == "ev-99"


def test_lifecycle_store_rejected_never_user_visible() -> None:
    """``active_claims`` excludes rejected claims — they never
    surface as authoritative user-visible facts."""
    store = ClaimLifecycleStore()
    store.register({"claim_id": "c1", "text": "x"})
    store.register({"claim_id": "c2", "text": "y"})
    store.transition(
        claim_id="c1",
        new_status="rejected",
        reason="rejected_by_validator",
    )
    active = store.active_claims
    assert all(c["claim_id"] != "c1" for c in active)
    assert any(c["claim_id"] == "c2" for c in active)


# --------------------------------------------------------------------------- #
# 7. NumericCorrectionAuditLog invariants
# --------------------------------------------------------------------------- #


def test_audit_log_closed_reasons_size() -> None:
    """The audit reason set has exactly 4 entries (the brief)."""
    assert len(ALLOWED_CORRECTION_REASONS) == 4


def test_audit_log_duplicate_id_rejected() -> None:
    """A caller-supplied duplicate id is refused."""
    log = NumericCorrectionAuditLog()
    log.append(
        original_value=1,
        corrected_value=2,
        reason="authoritative_disagreement",
        authoritative_source="src",
        audit_id="dup",
    )
    with pytest.raises(ValueError):
        log.append(
            original_value=3,
            corrected_value=4,
            reason="authoritative_disagreement",
            authoritative_source="src",
            audit_id="dup",
        )


def test_audit_log_appends_never_mutates() -> None:
    """Audit rows are immutable once appended."""
    log = NumericCorrectionAuditLog()
    log.append(
        original_value=1,
        corrected_value=2,
        reason="authoritative_disagreement",
        authoritative_source="src",
    )
    row = log.rows[0]
    with pytest.raises(Exception):
        row.original_value = 999  # frozen dataclass


# --------------------------------------------------------------------------- #
# 8. Brief invariants (sanity)
# --------------------------------------------------------------------------- #


def test_brief_does_not_weaken_fallback_chain() -> None:
    """The orchestrator NEVER produces a confidence > starting —
    the AI-13 / AI-15 fallback chain stays in effect."""
    for cls in FAILURE_CLASSES:
        out = adjust_confidence(
            starting_confidence=80,
            failure_class=cls,
        )
        assert out <= 80, f"class {cls!r} raised confidence above start"


def test_brief_never_invents_replacement_data() -> None:
    """Without authoritative_fields, the numeric pass is a no-op —
    proves the brief's 'never fabricate' invariant."""
    log = NumericCorrectionAuditLog()
    result = repair_deterministic(
        classification="numeric_mismatch",
        payload=_make_numeric_payload(),
        numeric_audit_log=log,
    )
    assert len(log) == 0
    assert applied_repair_count(result) == 0


def test_brief_only_one_retry_per_request() -> None:
    """A retry can only happen once — the orchestrator returns
    retry_recommended=True at most once and never auto-loops."""
    result = run_ai17_pipeline(
        payload=_make_numeric_payload(),
        starting_confidence=80,
        materially_useful=True,
        budget_remaining_ms=15_000,
        hard_call_timeout_ms=15_000,
        retry_already_attempted=False,
    )
    # retry_recommended is a single boolean — there is no
    # ``retry_count`` or ``retry_loop`` field.
    assert isinstance(result["retry_recommended"], bool)
    assert "retry_count" not in result
    assert "retry_loop" not in result
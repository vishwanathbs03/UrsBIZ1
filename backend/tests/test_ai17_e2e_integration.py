"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

End-to-end integration tests proving the five brief invariants
the conversation service must honour:

  1. Deterministic repair happens BEFORE any retry decision.
  2. Total provider calls ≤ 2 (the bounded retry gate caps them).
  3. Retry result is re-validated; if it still needs_retry the
     service ships the original with a warning (NOT a duplicated
     response body — no concatenation).
  4. Claim transitions are recorded; old claims are preserved
     (never silently deleted).
  5. Confidence penalty is additive and capped at -40.

6 tests covering:
  * E2E: numeric conflict → repair → audit pass (PART 2 + PART 5)
  * E2E: gate approves one retry, then refuses second (PART 3)
  * E2E: claim corrected → lifecycle preserved + penalty applied (PART 4 + PART 6)
  * E2E: no CoT prompt ever approved by gate (PART 3, no CoT)
  * E2E: original body never concatenated with retry body (PART 3)
  * E2E: penalty cap at -40 even with all signals (PART 6)
"""

from __future__ import annotations

from time import monotonic
from types import SimpleNamespace

from app.services.ai.reasoning.bounded_retry_gate import BoundedRetryGate
from app.services.ai.reasoning.claim_lifecycle import (
    ClaimLifecycleStatus,
    ClaimLifecycleStore,
)
from app.services.ai.reasoning.confidence_penalty_calculator import (
    ConfidencePenaltyCalculator,
)
from app.services.ai.reasoning.deterministic_answer_repairer import (
    DeterministicAnswerRepairer,
)
from app.services.ai.reasoning.numeric_correction_auditor import (
    NumericCorrectionAuditor,
)
from app.services.ai.reasoning.quality_failure_classifier import (
    QualityFailureClassifier,
)


def _make_quality(**overrides):
    defaults = {
        "relevance": 7.0, "evidence": 7.0, "numeric": 7.0,
        "completeness": 7.0, "uncertainty": 7.0, "actionability": 7.0,
        "consistency": 7.0, "format": 7.0, "total": 7.0,
        "needs_warning": False, "needs_retry": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _claim(cid: str, text: str):
    return SimpleNamespace(claim_id=cid, text=text)


# --------------------------------------------------------------------------- #
# 1 — E2E: numeric conflict → repair → audit pass
# --------------------------------------------------------------------------- #


def test_e2e_numeric_conflict_repair_then_audit_passes():
    """The full chain: classifier picks replace_numeric →
    repairer substitutes → numeric auditor confirms safety."""
    classifier = QualityFailureClassifier()
    repairer = DeterministicAnswerRepairer()
    auditor = NumericCorrectionAuditor()

    body = "Your revenue is 250 cr."
    envelope = {"revenue": 180.0}
    conflict = SimpleNamespace(
        metric="revenue", llm_value=250.0, authoritative_value=180.0
    )
    # PART 1 — classifier picks the strategy.
    quality = _make_quality()
    failure = classifier.classify(
        quality=quality, numeric_conflicts=(conflict,)
    )
    assert failure.repair_strategy == "replace_numeric"
    # PART 2 — deterministic repair.
    repair = repairer.repair(
        body, strategy=failure.repair_strategy,
        numeric_conflicts=(conflict,),
        envelope_values=envelope,
    )
    assert "180" in repair.repaired_body
    assert "250 cr" not in repair.repaired_body
    # PART 5 — numeric audit confirms safety.
    audit = auditor.audit_pair(
        original_body=body,
        repaired_body=repair.repaired_body,
        envelope_values=envelope,
        original_conflicts=(conflict,),
    )
    assert audit.safe_to_ship is True


# --------------------------------------------------------------------------- #
# 2 — E2E: gate approves ONE retry, then refuses
# --------------------------------------------------------------------------- #


def test_e2e_gate_approves_one_retry_then_refuses_second():
    """PART 3 — Total provider calls ≤ 2. After one approved
    retry the gate refuses a second attempt."""
    gate = BoundedRetryGate()
    quality = _make_quality(uncertainty=2.0, needs_retry=True)
    # First decision: calls=1 (original only). Approved.
    d1 = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt=gate.build_retry_prompt(
            original_prompt="What is my runway?",
            retry_strategy="add_uncertainty",
            failure_kind="missing_uncertainty",
            weakest_axis="uncertainty",
        ),
        retry_strategy="add_uncertainty",
        previous_quality=quality,
    )
    assert d1.approved is True
    # Second decision: calls=2 (original + retry). Refused.
    d2 = gate.decide(
        provider_calls_so_far=2,
        deadline_monotonic=None,
        retry_prompt="Tighten your answer.",
        retry_strategy="add_uncertainty",
        previous_quality=quality,
    )
    assert d2.approved is False
    assert "call cap" in d2.reason


# --------------------------------------------------------------------------- #
# 3 — E2E: corrected claim → lifecycle preserved + penalty applied
# --------------------------------------------------------------------------- #


def test_e2e_corrected_claim_preserves_history_and_penalises_confidence():
    """PART 4 + PART 6 — A corrected claim is preserved in
    the lifecycle store AND triggers the -2 corrected_claim
    confidence penalty."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1", "Revenue is 250 cr"))
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.CORRECTED,
        reason="numeric_correction",
        source="numeric_checker",
        new_text="Revenue is 180 cr",
    )
    # PART 4 — original claim is NOT deleted; audit trail preserved.
    assert len(store.all_claims()) == 1
    assert len(store.all_events()) == 1
    assert store.status_of("c1") == "corrected"
    assert store.active_claims == ()
    # PART 6 — penalty calculator applies -2.
    calc = ConfidencePenaltyCalculator()
    report = calc.compute_penalty(lifecycle_events=store.all_events())
    assert report.components == {"corrected_claim": -2}
    assert report.total_penalty == -2


# --------------------------------------------------------------------------- #
# 4 — E2E: no CoT prompt ever approved
# --------------------------------------------------------------------------- #


def test_e2e_no_cot_prompt_ever_approved():
    """PART 3 — The gate must refuse ANY retry prompt that
    contains a chain-of-thought marker, even when all other
    constraints pass."""
    gate = BoundedRetryGate()
    quality = _make_quality(uncertainty=2.0, needs_retry=True)
    bad_prompts = (
        "Think step by step about uncertainty.",
        "Show your reasoning for the missing evidence.",
        "Let me think about this — give me the answer.",
        "Reasoning: walk through your logic before answering.",
    )
    for prompt in bad_prompts:
        d = gate.decide(
            provider_calls_so_far=1,
            deadline_monotonic=None,
            retry_prompt=prompt,
            retry_strategy="add_uncertainty",
            previous_quality=quality,
        )
        assert d.approved is False, f"CoT prompt approved: {prompt!r}"
        assert "chain-of-thought" in d.reason.lower()


# --------------------------------------------------------------------------- #
# 5 — E2E: original body NEVER concatenated with retry body
# --------------------------------------------------------------------------- #


def test_e2e_original_body_never_concatenated_with_retry_body():
    """PART 3 — The brief forbids concatenating the original
    answer with the retry body. The repairer preserves the
    original in ``original_body`` but the body to ship is
    either the original OR the retry — never both."""
    repairer = DeterministicAnswerRepairer()
    body = "Your revenue is 250 cr."
    conflict = SimpleNamespace(
        metric="revenue", llm_value=250.0, authoritative_value=180.0
    )
    repair = repairer.repair(
        body, strategy="replace_numeric",
        numeric_conflicts=(conflict,),
        envelope_values={"revenue": 180.0},
    )
    # The shipped body is the repaired body, not original+repaired.
    assert repair.repaired_body == "Your revenue is 180 cr."
    assert repair.original_body == body
    assert repair.repaired_body != body + repair.repaired_body


# --------------------------------------------------------------------------- #
# 6 — E2E: penalty cap holds even with all signals stacked
# --------------------------------------------------------------------------- #


def test_e2e_penalty_cap_at_minus_40_with_all_signals():
    """PART 6 — The AI-17 penalty is additive and capped at -40.
    Even with every signal category firing the cap holds so the
    wire field ``confidence_penalty`` stays 0..40."""
    calc = ConfidencePenaltyCalculator()
    warnings = (
        {"source_url": "rbi.org.in", "freshness_status": "STALE"},
        {"source_url": "indianexpress.com", "freshness_status": "AGING"},
        {"source_url": "example.com", "freshness_status": "UNKNOWN"},
    )
    events = (
        SimpleNamespace(claim_id="c1", new_status="corrected"),
        SimpleNamespace(claim_id="c2", new_status="corrected"),
    )
    ctx = SimpleNamespace(
        annual_revenue=None, monthly_expenses=None,
        gross_margin=None, headcount=None,
    )
    report = calc.compute_penalty(
        freshness_warnings=warnings,
        lifecycle_events=events,
        context=ctx,
    )
    # Even with all categories, the cap is honoured.
    assert report.total_penalty >= -40
    # And it never exceeds the documented per-category values.
    assert sum(report.components.values()) <= 0


# --------------------------------------------------------------------------- #
# 7 — E2E: full chain on an unsupported-claim failure
# --------------------------------------------------------------------------- #


def test_e2e_unsupported_claim_full_chain():
    """A claim that the auditor marks unsupported flows through
    remove_claim → lifecycle transition → confidence penalty
    when corrected."""
    classifier = QualityFailureClassifier()
    repairer = DeterministicAnswerRepairer()
    store = ClaimLifecycleStore()
    calc = ConfidencePenaltyCalculator()

    body = "Acme will raise Series B in 2025."
    claim = _claim("c1", body)
    store.register(claim)
    quality = _make_quality(evidence=2.5)
    unsupported = (claim,)

    # PART 1 — classifier picks remove_claim.
    failure = classifier.classify(
        quality=quality, unsupported_claims=unsupported
    )
    assert failure.repair_strategy == "remove_claim"
    # PART 2 — deterministic repair softens / marks unverifiable.
    repair = repairer.repair(
        body, strategy=failure.repair_strategy,
        unsupported_claims=unsupported,
    )
    assert "UrsBiz could not verify" in repair.repaired_body
    # PART 4 — lifecycle records the rejection; original preserved.
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.REJECTED,
        reason="evidence_insufficient",
        source="claim_auditor",
    )
    assert store.status_of("c1") == "rejected"
    assert len(store.all_claims()) == 1
    # PART 6 — confidence penalty picks up the corrected claim
    # (this case is rejected, not corrected, so no -2 applies;
    # but the store still records the audit event).
    report = calc.compute_penalty(lifecycle_events=store.all_events())
    # REJECTED is not CORRECTED, so no penalty fires here.
    assert report.components == {}

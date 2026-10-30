"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``bounded_retry_gate``: the four-constraint gate
that may approve ONE additional provider call per request.

8 tests covering:
  * Total provider calls cap → approved=False
  * Insufficient remaining timeout budget → approved=False
  * CoT marker in retry prompt → approved=False
  * Empty retry strategy → approved=False
  * Passing previous quality → approved=False
  * All constraints pass → approved=True
  * build_retry_prompt contains no CoT markers
  * Infinite budget (deadline=None) does not block retry
"""

from __future__ import annotations

from time import monotonic

from types import SimpleNamespace

from app.services.ai.reasoning.bounded_retry_gate import (
    BoundedRetryGate,
    RetryDecision,
)


def _quality(*, needs_retry: bool = True):
    return SimpleNamespace(needs_retry=needs_retry)


# --------------------------------------------------------------------------- #
# 1 — Provider call cap
# --------------------------------------------------------------------------- #


def test_provider_call_cap_blocks_retry():
    """When the conversation service has already used 2 calls
    the gate must refuse — total provider calls ≤ 2."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=2,
        deadline_monotonic=None,
        retry_prompt="Tighten your answer.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is False
    assert "call cap" in decision.reason
    assert decision.provider_calls_so_far == 2
    assert decision.max_provider_calls == 2


# --------------------------------------------------------------------------- #
# 2 — Insufficient remaining budget
# --------------------------------------------------------------------------- #


def test_insufficient_remaining_budget_blocks_retry():
    """When fewer than ``min_remaining_seconds`` remain the gate
    must refuse — the 15s SLA would be violated."""
    gate = BoundedRetryGate(min_remaining_seconds=2.0)
    # Deadline is already past → ~0 seconds remaining.
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=monotonic() - 0.5,
        retry_prompt="Tighten your answer.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is False
    assert "budget" in decision.reason.lower()


# --------------------------------------------------------------------------- #
# 3 — CoT marker blocks retry
# --------------------------------------------------------------------------- #


def test_chain_of_thought_marker_blocks_retry():
    """When the retry prompt contains a CoT marker the gate
    must refuse — the brief forbids chain-of-thought requests
    on the retry path."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt="Think step by step and tighten your answer.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is False
    assert "chain-of-thought" in decision.reason.lower()


# --------------------------------------------------------------------------- #
# 4 — Empty retry strategy blocks retry
# --------------------------------------------------------------------------- #


def test_empty_retry_strategy_blocks_retry():
    """The gate refuses retries without a targeted strategy —
    retrying without a plan is wasteful."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt="Try again.",
        retry_strategy="",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is False
    assert "strategy" in decision.reason.lower()


# --------------------------------------------------------------------------- #
# 5 — Passing previous quality blocks retry
# --------------------------------------------------------------------------- #


def test_passing_previous_quality_blocks_retry():
    """When the previous attempt already passed quality the
    gate must refuse — retrying a passing answer is wasteful."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt="Tighten your answer.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=False),
    )
    assert decision.approved is False
    assert "passed" in decision.reason.lower()


# --------------------------------------------------------------------------- #
# 6 — All constraints pass → approved
# --------------------------------------------------------------------------- #


def test_all_constraints_pass_approve_retry():
    """When the gate has budget, no CoT, a targeted strategy,
    and the previous attempt needs retry, the gate approves."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt="Tighten your answer on uncertainty.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is True
    assert "approved" in decision.reason.lower()
    assert decision.provider_calls_so_far == 1


# --------------------------------------------------------------------------- #
# 7 — build_retry_prompt contains no CoT markers
# --------------------------------------------------------------------------- #


def test_build_retry_prompt_avoids_cot_markers():
    """The retry prompt the gate builds must NEVER contain a
    CoT marker — the brief forbids them."""
    gate = BoundedRetryGate()
    prompt = gate.build_retry_prompt(
        original_prompt="What is my runway?",
        retry_strategy="add_uncertainty",
        failure_kind="missing_uncertainty",
        weakest_axis="uncertainty",
    )
    # Scan for CoT markers manually (the gate's own scanner).
    found = gate._find_cot_marker(prompt)
    assert found == "", f"retry prompt contains CoT marker {found!r}"
    # And the prompt includes the strategy hint so the LLM
    # knows what to tighten.
    assert "add_uncertainty" in prompt
    assert "uncertainty" in prompt


# --------------------------------------------------------------------------- #
# 8 — Infinite budget (deadline=None) does not block retry
# --------------------------------------------------------------------------- #


def test_infinite_budget_does_not_block_retry():
    """When no deadline is supplied the gate treats the budget
    as infinite and does NOT block the retry on timing alone."""
    gate = BoundedRetryGate()
    decision = gate.decide(
        provider_calls_so_far=1,
        deadline_monotonic=None,
        retry_prompt="Tighten your answer on uncertainty.",
        retry_strategy="add_uncertainty",
        previous_quality=_quality(needs_retry=True),
    )
    assert decision.approved is True
    assert decision.budget_remaining_seconds == float("inf")


# --------------------------------------------------------------------------- #
# 9 — to_dict round-trip
# --------------------------------------------------------------------------- #


def test_retry_decision_to_dict_round_trip():
    """:meth:`RetryDecision.to_dict` serialises the four
    wire-relevant fields."""
    d = RetryDecision(
        approved=False,
        reason="blocked by gate",
        budget_remaining_seconds=1.5,
        provider_calls_so_far=2,
        max_provider_calls=2,
    ).to_dict()
    assert d["approved"] is False
    assert d["reason"] == "blocked by gate"
    assert d["budget_remaining_seconds"] == 1.5
    assert d["provider_calls_so_far"] == 2
    assert d["max_provider_calls"] == 2

"""SPRINT AI-18 — Universal AI Evaluation Harness.

Provider failure scenarios.

The brief (PART 4) requires the assistant to remain safe and
useful across:

  * timeout
  * 429
  * 500
  * malformed response
  * schema failure
  * grounding failure
  * tool timeout
  * partial tool failure
  * unavailable provider

The user must always receive a safe, useful response OR an
honest limitation. Each scenario is a
:class:`ProviderFailureScenario` whose
``injected_failure`` describes what to simulate and whose
``expected_outcome`` is the safety contract the runner
verifies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Failure kind vocabulary
# --------------------------------------------------------------------------- #


class FailureKind(str):
    """Plain-string vocabulary of provider failure modes."""

    TIMEOUT = "timeout"
    RATE_LIMIT_429 = "rate_limit_429"
    SERVER_500 = "server_500"
    MALFORMED_RESPONSE = "malformed_response"
    SCHEMA_FAILURE = "schema_failure"
    GROUNDING_FAILURE = "grounding_failure"
    TOOL_TIMEOUT = "tool_timeout"
    PARTIAL_TOOL_FAILURE = "partial_tool_failure"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


# --------------------------------------------------------------------------- #
# Outcome assertion
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FailureOutcome:
    """What the runner expects when ``injected_failure`` fires.

    Supported predicates
    --------------------
    * ``"body_nonempty"`` — assistant body must NOT be empty
    * ``"body_must_contain_any"`` — at least one of these
      substrings must appear (the safety contract)
    * ``"body_must_not_contain_any"`` — none of these may appear
    * ``"fallback_used"`` — the deterministic fallback path
      must have been taken
    * ``"warning_expected"`` — the response must carry a
      low-quality warning
    * ``"disclosure_expected"`` — the response must disclose
      the failure to the user (e.g. "I could not retrieve…")
    * ``"confidence_max"`` — trust-band ceiling
    """

    body_nonempty: bool = True
    body_must_contain_any: tuple[str, ...] = ()
    body_must_not_contain_any: tuple[str, ...] = ()
    fallback_used: bool = True
    warning_expected: bool = False
    disclosure_expected: bool = False
    confidence_max: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_nonempty": bool(self.body_nonempty),
            "body_must_contain_any": list(self.body_must_contain_any),
            "body_must_not_contain_any": list(self.body_must_not_contain_any),
            "fallback_used": bool(self.fallback_used),
            "warning_expected": bool(self.warning_expected),
            "disclosure_expected": bool(self.disclosure_expected),
            "confidence_max": float(self.confidence_max),
        }


# --------------------------------------------------------------------------- #
# Scenario
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProviderFailureScenario:
    """One provider failure mode + the prompt that exposes it.

    The runner uses ``prompt`` to drive the pipeline and the
    failure simulation hooks inject the failure at the right
    point. ``expected_outcome`` is the safety contract the
    reply must satisfy.
    """

    scenario_id: str
    failure_kind: str
    prompt: str
    expected_outcome: FailureOutcome
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "failure_kind": self.failure_kind,
            "prompt": self.prompt,
            "expected_outcome": self.expected_outcome.to_dict(),
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


FAILURE_SCENARIOS: tuple[ProviderFailureScenario, ...] = (
    # ---- 1 — timeout --------------------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_timeout_001",
        failure_kind=FailureKind.TIMEOUT,
        prompt="What is our current revenue?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=(
                "could not", "timed out", "try again", "UrsBiz",
            ),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Provider timeout must fall back to deterministic reply "
        "and disclose the issue.",
    ),
    # ---- 2 — 429 rate-limit -------------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_429_001",
        failure_kind=FailureKind.RATE_LIMIT_429,
        prompt="What is our biggest risk?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=(
                "could not", "try again", "busy", "momentarily",
            ),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="429 must NOT crash; deterministic fallback engages.",
    ),
    # ---- 3 — 500 ------------------------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_500_001",
        failure_kind=FailureKind.SERVER_500,
        prompt="How much revenue do we need to reach ₹3 Cr?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "error", "try", "again"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="500 server error must surface a useful message.",
    ),
    # ---- 4 — malformed response --------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_malformed_001",
        failure_kind=FailureKind.MALFORMED_RESPONSE,
        prompt="What's our headcount?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "data"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Garbage response must be discarded; deterministic path "
        "produces a useful answer.",
    ),
    # ---- 5 — schema failure ------------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_schema_001",
        failure_kind=FailureKind.SCHEMA_FAILURE,
        prompt="What government schemes apply to us?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "scheme"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Wrong schema must NOT crash the response.",
    ),
    # ---- 6 — grounding failure ---------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_grounding_001",
        failure_kind=FailureKind.GROUNDING_FAILURE,
        prompt="Recommend our top 3 actions for next quarter.",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "recommend"),
            fallback_used=True,
            warning_expected=True,
            confidence_max=70.0,
        ),
        notes="Grounding failure must lower confidence but still "
        "return something useful.",
    ),
    # ---- 7 — tool timeout --------------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_tool_timeout_001",
        failure_kind=FailureKind.TOOL_TIMEOUT,
        prompt="What is our working capital requirement?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "working capital"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Tool timeout must NOT take down the whole reply.",
    ),
    # ---- 8 — partial tool failure ------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_partial_tool_001",
        failure_kind=FailureKind.PARTIAL_TOOL_FAILURE,
        prompt="What export markets should we target?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("export", "market"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Partial tool failure must disclose which tool failed.",
    ),
    # ---- 9 — provider unavailable ------------------------------- #
    ProviderFailureScenario(
        scenario_id="fail_provider_unavailable_001",
        failure_kind=FailureKind.PROVIDER_UNAVAILABLE,
        prompt="How do we compare to peers in Tirupur?",
        expected_outcome=FailureOutcome(
            body_nonempty=True,
            body_must_contain_any=("UrsBiz", "compare"),
            fallback_used=True,
            warning_expected=True,
            disclosure_expected=True,
        ),
        notes="Provider unreachable → deterministic path engages.",
    ),
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def all_failure_scenarios() -> tuple[ProviderFailureScenario, ...]:
    """Return every provider failure scenario."""
    return FAILURE_SCENARIOS


def failure_kinds() -> tuple[str, ...]:
    """Return the canonical 9-kind vocabulary."""
    return (
        FailureKind.TIMEOUT,
        FailureKind.RATE_LIMIT_429,
        FailureKind.SERVER_500,
        FailureKind.MALFORMED_RESPONSE,
        FailureKind.SCHEMA_FAILURE,
        FailureKind.GROUNDING_FAILURE,
        FailureKind.TOOL_TIMEOUT,
        FailureKind.PARTIAL_TOOL_FAILURE,
        FailureKind.PROVIDER_UNAVAILABLE,
    )


__all__ = [
    "FailureKind",
    "FailureOutcome",
    "ProviderFailureScenario",
    "all_failure_scenarios",
    "failure_kinds",
]

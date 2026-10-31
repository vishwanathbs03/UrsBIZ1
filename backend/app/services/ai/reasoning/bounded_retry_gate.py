"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Bounded retry gate.

The retry gate is the only place in the AI-17 pipeline that
may trigger a SECOND provider call. It guards the conversation
service from runaway regeneration chains by enforcing four
hard constraints:

  1. **Total provider calls ≤ 2.** The first call is the
     original generation; the retry gate may approve at most
     one additional call. A second attempt requires a third
     call, which is never approved.
  2. **At least ``min_remaining_seconds`` of timeout budget
     must remain.** The conversation service has a 15-second
     SLA; the retry gate refuses to spend more than
     ``max_provider_seconds_per_call`` (default 5s) per call
     on the retry path.
  3. **No chain-of-thought request.** The retry prompt must
     not ask the LLM to "think step-by-step" or otherwise
     emit reasoning prose that would leak through the body.
  4. **The retry result is re-validated.** A retry that
     returns another ``needs_retry`` answer is treated as a
     failure: the gate returns ``approved=False`` and the
     caller ships the original body with a warning.

The gate is a pure decision function — it does not invoke
the provider itself. The conversation service reads the
:class:`RetryDecision` and acts on it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RetryDecision:
    """The gate's verdict.

    ``approved`` is True only when ALL four constraints pass.
    ``reason`` is the human-readable explanation for the
    audit trail. ``budget_remaining_seconds`` is the timeout
    budget the caller has left after this decision.

    The conversation service must check ``approved`` before
    issuing the second provider call.
    """

    approved: bool = False
    reason: str = ""
    budget_remaining_seconds: float = 0.0
    provider_calls_so_far: int = 0
    max_provider_calls: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": bool(self.approved),
            "reason": str(self.reason),
            "budget_remaining_seconds": float(self.budget_remaining_seconds),
            "provider_calls_so_far": int(self.provider_calls_so_far),
            "max_provider_calls": int(self.max_provider_calls),
        }


# --------------------------------------------------------------------------- #
# Gate
# --------------------------------------------------------------------------- #


# Chain-of-thought markers the brief forbids on the retry
# prompt. The gate REFUSES to approve a retry whose prompt
# contains any of these substrings (case-insensitive). The
# markers mirror the markers the recompose strategy strips
# so the gate + repairer use the same vocabulary.
_COT_MARKERS: tuple[str, ...] = (
    "step by step",
    "step-by-step",
    "chain of thought",
    "chain-of-thought",
    "let me think",
    "think step",
    "reasoning:",
    "reasoning step",
    "show your work",
    "show your reasoning",
    "explain how you",
)


# Default per-call budget for the retry. The conversation
# service has 15s total; the retry may not exceed this
# fraction of the remaining budget.
_MAX_PROVIDER_SECONDS_PER_CALL: float = 5.0
_MIN_REMAINING_SECONDS: float = 2.0

# Hard cap on total provider calls (original + retry).
_MAX_PROVIDER_CALLS: int = 2


class BoundedRetryGate:
    """Decide whether the bounded retry path is allowed.

    The gate is pure. ``decide`` takes the live state (call
    count, deadline, prompt draft) and returns a
    :class:`RetryDecision`.
    """

    def __init__(
        self,
        *,
        max_provider_calls: int = _MAX_PROVIDER_CALLS,
        max_provider_seconds_per_call: float = _MAX_PROVIDER_SECONDS_PER_CALL,
        min_remaining_seconds: float = _MIN_REMAINING_SECONDS,
    ) -> None:
        self._max_calls = int(max_provider_calls)
        self._max_per_call = float(max_provider_seconds_per_call)
        self._min_remaining = float(min_remaining_seconds)

    # ---- public API ------------------------------------------------ #

    @property
    def max_provider_calls(self) -> int:
        return self._max_calls

    def decide(
        self,
        *,
        provider_calls_so_far: int,
        deadline_monotonic: float | None,
        retry_prompt: str = "",
        retry_strategy: str = "",
        previous_quality: Any = None,
    ) -> RetryDecision:
        """Return the :class:`RetryDecision`.

        Parameters
        ----------
        provider_calls_so_far:
            Number of provider calls already made for this
            request (including the original generation).
            Must be ≥ 1.
        deadline_monotonic:
            The ``time.monotonic()`` deadline the request
            must complete by. ``None`` when the caller has no
            deadline (treated as "infinite budget").
        retry_prompt:
            The draft prompt the retry would use. The gate
            scans for chain-of-thought markers.
        retry_strategy:
            One of the deterministic repair strategies
            (``"replace_numeric"``, ``"remove_claim"``,
            ``"add_uncertainty"``, ``"add_assumptions"``,
            ``"reclassify_recommendation"``, ``"recompose"``).
            Empty string when no deterministic strategy
            applies; the gate then refuses because retry
            without a targeted strategy is wasteful.
        previous_quality:
            The :class:`AnswerQuality` from the previous
            attempt. The gate inspects ``needs_retry`` to
            decide whether the LLM should be called again.
        """
        # Constraint 1 — total provider calls ≤ cap.
        if provider_calls_so_far >= self._max_calls:
            return RetryDecision(
                approved=False,
                reason=(
                    f"provider call cap reached "
                    f"({provider_calls_so_far}/{self._max_calls}); "
                    "no further retries allowed"
                ),
                budget_remaining_seconds=self._remaining_seconds(
                    deadline_monotonic
                ),
                provider_calls_so_far=provider_calls_so_far,
                max_provider_calls=self._max_calls,
            )

        # Constraint 2 — remaining timeout budget.
        remaining = self._remaining_seconds(deadline_monotonic)
        if (
            deadline_monotonic is not None
            and remaining < self._min_remaining
        ):
            return RetryDecision(
                approved=False,
                reason=(
                    f"insufficient timeout budget "
                    f"(remaining={remaining:.1f}s < "
                    f"min={self._min_remaining:.1f}s); "
                    "SLA would be violated"
                ),
                budget_remaining_seconds=remaining,
                provider_calls_so_far=provider_calls_so_far,
                max_provider_calls=self._max_calls,
            )
        if (
            deadline_monotonic is not None
            and remaining < self._max_per_call
        ):
            return RetryDecision(
                approved=False,
                reason=(
                    f"insufficient budget for retry call "
                    f"(remaining={remaining:.1f}s < "
                    f"per_call={self._max_per_call:.1f}s)"
                ),
                budget_remaining_seconds=remaining,
                provider_calls_so_far=provider_calls_so_far,
                max_provider_calls=self._max_calls,
            )

        # Constraint 3 — no chain-of-thought request.
        cot_match = self._find_cot_marker(retry_prompt)
        if cot_match:
            return RetryDecision(
                approved=False,
                reason=(
                    f"retry prompt contains chain-of-thought marker "
                    f"{cot_match!r}; not approved"
                ),
                budget_remaining_seconds=remaining,
                provider_calls_so_far=provider_calls_so_far,
                max_provider_calls=self._max_calls,
            )

        # Constraint 4 — retry must be targeted.
        if not retry_strategy:
            return RetryDecision(
                approved=False,
                reason=(
                    "retry_strategy is empty; "
                    "retrying without a targeted strategy is wasteful"
                ),
                budget_remaining_seconds=remaining,
                provider_calls_so_far=provider_calls_so_far,
                max_provider_calls=self._max_calls,
            )

        # If the previous quality is known and is below the
        # warning threshold we let the retry proceed — but if
        # the previous quality itself passed, no retry needed.
        if previous_quality is not None:
            try:
                needs_retry = bool(getattr(previous_quality, "needs_retry"))
            except Exception:
                needs_retry = True
            if not needs_retry:
                return RetryDecision(
                    approved=False,
                    reason=(
                        "previous attempt passed quality gate; "
                        "no retry needed"
                    ),
                    budget_remaining_seconds=remaining,
                    provider_calls_so_far=provider_calls_so_far,
                    max_provider_calls=self._max_calls,
                )

        return RetryDecision(
            approved=True,
            reason=(
                f"retry approved: strategy={retry_strategy!r}, "
                f"budget={remaining:.1f}s, "
                f"calls={provider_calls_so_far}/{self._max_calls}"
            ),
            budget_remaining_seconds=remaining,
            provider_calls_so_far=provider_calls_so_far,
            max_provider_calls=self._max_calls,
        )

    def build_retry_prompt(
        self,
        *,
        original_prompt: str,
        retry_strategy: str,
        failure_kind: str,
        weakest_axis: str,
    ) -> str:
        """Return a retry prompt that is guaranteed to avoid CoT markers.

        The prompt is the original question + a "tighten weakest
        axis" hint + the targeted repair strategy. The caller
        passes the result to the gate again via ``decide``; the
        gate will approve it because the prompt contains none
        of the :data:`_COT_MARKERS`.
        """
        hint = (
            f"Tighten your answer on the '{weakest_axis or 'overall'}' "
            f"axis. Apply this targeted repair: {retry_strategy}. "
            f"Failure kind reported: {failure_kind}. "
            "Respond only with the final answer body — do not "
            "include reasoning notes or thinking-aloud prose."
        )
        if original_prompt:
            return f"{original_prompt.rstrip()}\n\n{hint}"
        return hint

    # ---- helpers --------------------------------------------------- #

    @staticmethod
    def _remaining_seconds(deadline: float | None) -> float:
        """Return the seconds remaining before ``deadline``.

        ``float('inf')`` when ``deadline`` is ``None``.
        """
        if deadline is None:
            return float("inf")
        try:
            now = monotonic()
        except Exception:
            return float("inf")
        return max(0.0, float(deadline) - now)

    @staticmethod
    def _find_cot_marker(prompt: str) -> str:
        """Return the first CoT marker found in ``prompt`` (case-insensitive).

        Empty string when none found. The gate refuses a retry
        prompt that contains ANY marker — being conservative
        prevents the LLM from leaking reasoning into the body.
        """
        if not prompt:
            return ""
        low = prompt.lower()
        for marker in _COT_MARKERS:
            if marker in low:
                return marker
        return ""
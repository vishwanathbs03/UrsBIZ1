"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Bounded retry gate.

PART 3 of the AI-17 brief mandates ONE — and only one —
additional LLM generation attempt when:

  * the failure is not safely deterministic-repairable, AND
  * the answer is materially useful enough to retry, AND
  * the remaining wall-clock budget covers the retry.

No retry storm. No recursive regeneration. No hidden
second-generation call. The wall-clock cap is enforced from
the provider's ``HARD_CALL_TIMEOUT_SECONDS`` (15s); this gate
adds a *budget-arithmetic* check on top.

The retry prompt is the brief's exact wording. The model is
NEVER asked to expose its reasoning.
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# The retry prompt — verbatim from the brief. ANY character
# change requires a plan note.
# --------------------------------------------------------------------------- #


RETRY_PROMPT: str = (
    "Tighten the answer using only the supplied evidence. "
    "Correct the identified validation issue. Do not add "
    "unsupported numbers or claims. Preserve the requested "
    "answer structure."
)


# Phrases the retry prompt must NEVER contain. Presence of
# any of these signals the orchestrator to abort the retry —
# the brief forbids chain-of-thought leakage.
_FORBIDDEN_RETRY_PROMPT_PHRASES: tuple[str, ...] = (
    "think step by step",
    "explain your reasoning",
    "explain your process",
    "show your work",
    "your thought process",
    "step-by-step reasoning",
    "let me think",
)


# --------------------------------------------------------------------------- #
# Budget arithmetic
# --------------------------------------------------------------------------- #


# Conservative per-retry cost estimate. The provider's
# `_call_with_hard_timeout` cap is 15s; we keep ~2x headroom
# so the retry can actually finish even with slow downstream
# provider latency.
_RETRY_BUDGET_HEADROOM_MS: int = 2_000  # 2s headroom for orchestration
_MIN_REMAINING_BUDGET_FRACTION: float = 0.34  # retry needs ≥ 1/3 of the cap


# --------------------------------------------------------------------------- #
# Public gate
# --------------------------------------------------------------------------- #


def should_retry(
    *,
    failure_class: str,
    budget_remaining_ms: int,
    hard_call_timeout_ms: int,
    materially_useful: bool,
    retry_already_attempted: bool,
) -> bool:
    """Decide whether to attempt the (one and only) retry.

    Parameters
    ----------
    failure_class
        Output of the AI-17 QualityFailureClassifier.
    budget_remaining_ms
        Wall-clock milliseconds remaining for the whole
        request (the provider's ``HARD_CALL_TIMEOUT_SECONDS``
        is the unit; subtract the elapsed time).
    hard_call_timeout_ms
        The configured cap (e.g. ``15000``). The retry never
        fits when remaining < this * headroom fraction.
    materially_useful
        ``True`` when the answer delivered partial value and
        a retry might bring it above the brief's quality
        floor. When ``False``, we skip even when the budget
        is ample.
    retry_already_attempted
        ``True`` when the prior turn already used its retry
        quota. The brief mandates a hard ceiling of ONE retry
        per request — this flag enforces the cap.

    Returns
    -------
    ``True`` iff ALL of:

      * the failure class is retryable (i.e. not
        ``none``, ``unsafe_to_repair``);
      * the retry has not already been attempted;
      * the answer is materially useful;
      * the remaining budget covers the retry with
        headroom.
    """
    from app.services.ai.knowledge.ai17_quality_failure_classifier import (
        is_retryable,
    )

    if retry_already_attempted:
        return False
    if not is_retryable(failure_class):
        return False
    if not materially_useful:
        return False

    # Budget check: the retry needs at least hard_cap *
    # headroom_fraction + 2s of orchestration slack to
    # finish before the request cap.
    threshold = (
        int(hard_call_timeout_ms * _MIN_REMAINING_BUDGET_FRACTION)
        + _RETRY_BUDGET_HEADROOM_MS
    )
    if budget_remaining_ms < threshold:
        return False

    return True


def retry_prompt_audit_text(prompt: str) -> tuple[bool, tuple[str, ...]]:
    """Return ``(ok, matched_forbidden_phrases)``.

    The orchestrator calls this on the actual prompt the
    retry will be issued with; matches mean the prompt has
    chain-of-thought leakage and the retry must be aborted.
    """
    lower = (prompt or "").lower()
    matches = tuple(
        phrase for phrase in _FORBIDDEN_RETRY_PROMPT_PHRASES
        if phrase in lower
    )
    return (not matches, matches)


def build_retry_prompt(
    *,
    original_prompt: str,
    failure_class: str,
    repair_applied: tuple[str, ...] = (),
    extra_context: str = "",
) -> str:
    """Compose the retry message the provider actually sees.

    The brief mandates the literal prompt above; this function
    composes the *full* message by prepending the original
    request and the failure-class hint. The literal
    :data:`RETRY_PROMPT` MUST appear verbatim in the output.
    """
    parts: list[str] = [RETRY_PROMPT]
    parts.append("")
    parts.append(f"Identified validation issue: {failure_class}.")
    if repair_applied:
        parts.append(
            "Deterministic repairs already applied: "
            + ", ".join(repair_applied)
            + "."
        )
    if extra_context:
        parts.append("")
        parts.append(extra_context)
    parts.append("")
    parts.append("Original question:")
    parts.append((original_prompt or "").strip() or "(no question)")
    return "\n".join(parts)


__all__ = [
    "RETRY_PROMPT",
    "build_retry_prompt",
    "retry_prompt_audit_text",
    "should_retry",
]

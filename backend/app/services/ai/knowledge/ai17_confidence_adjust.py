"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Confidence adjustment rules.

PART 7 of the AI-17 brief mandates that confidence MUST decrease
when:

  * evidence is missing
  * contradictions remain
  * tool execution partially fails
  * claims are repaired
  * external information is stale
  * assumptions materially affect the answer

Confidence MUST NEVER increase merely because the LLM sounds
confident. The function :func:`adjust_confidence` is pure,
deterministic, and clamping-monotone in one direction — its
range is ``[0, max(start, 100)]`` and it never returns a value
greater than ``start``.
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Per-cause penalties (a small, opinionated table — change
# requires a plan note).
# --------------------------------------------------------------------------- #


_PENALTY_MISSING_EVIDENCE: int = 5
_PENALTY_NUMERIC_MISMATCH: int = 8
_PENALTY_UNSUPPORTED_CLAIM: int = 10
_PENALTY_CONTRADICTION: int = 15
_PENALTY_INSUFFICIENT_UNCERTAINTY: int = 4
_PENALTY_INCOMPLETE_ANSWER: int = 6
_PENALTY_PER_REPAIR: int = 3
_PENALTY_PER_STALE_EXTERNAL: int = 3
_PENALTY_PER_MATERIAL_ASSUMPTION: int = 2

# Existing AI-13 partial-failure penalty already applies a
# clamped 0..40 reduction; we re-import it via a duck-typed
# read so this module stays stand-alone (and unit-testable
# without spinning the provider stack).


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_len(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple, dict)):
        return len(value)
    return 0


def _safe_max(value: Any) -> int:
    """Return the integer clamp; defaults to 100."""
    if value is None or value == "":
        return 100
    try:
        n = int(value)
        return max(0, n)
    except (TypeError, ValueError):
        return 100


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #


def adjust_confidence(
    *,
    starting_confidence: int,
    failure_class: str,
    repair_applied: tuple[str, ...] | list[str] = (),
    partial_failure_penalty: int = 0,
    freshness_warning_count: int | None = None,
    unsupported_claim_count: int | None = None,
    numeric_conflict_count: int | None = None,
    missing_data_count: int | None = None,
    material_assumption_count: int | None = None,
    contradiction: bool | None = None,
    upper_bound: int = 100,
) -> int:
    """Apply the AI-17 confidence-decrease table and clamp to ``upper_bound``.

    The function is **monotone-decreasing in corrections** and
    **monotone-increasing only in the starting_confidence
    argument**. No "model sounded confident → bump up" path
    exists.

    Parameters
    ----------
    starting_confidence
        The confidence the prior turn delivered (0..100).
    failure_class
        Output of the AI-17 QualityFailureClassifier. Drives
        the leading cause penalty.
    repair_applied
        Tuple of repair names the deterministic repair pass
        applied. Each entry contributes -3 (capped so a
        many-repair turn cannot bottom out below the
        upper-bound floor).
    partial_failure_penalty
        Existing AI-13 ledger figure (0..40). Subtracted
        verbatim — the AI-13 ledger never raises confidence.
    freshness_warning_count, unsupported_claim_count, etc.
        Allow the caller to pass the raw counts; ``None``
        means "not provided" (the function refuses to assume
        a value).
    upper_bound
        Maximum the function may return. Defaults to 100 so
        the caller does not have to pass it for healthy
        requests; the AI-13 ledger already clamps to 100 so
        the brief's "never exceeds starting" invariant is
        preserved when the starting value is the bound.
    """
    total_penalty = 0

    # Leading cause — derived from the failure_class the
    # classifier returned. The classifier's priority order
    # already enforced "fabrication beats presentation"; we
    # apply the matching penalty here.
    if failure_class == "missing_evidence":
        total_penalty += _PENALTY_MISSING_EVIDENCE
    elif failure_class == "numeric_mismatch":
        total_penalty += _PENALTY_NUMERIC_MISMATCH
    elif failure_class == "unsupported_claim":
        total_penalty += _PENALTY_UNSUPPORTED_CLAIM
    elif failure_class == "contradiction":
        total_penalty += _PENALTY_CONTRADICTION
    elif failure_class == "insufficient_uncertainty":
        total_penalty += _PENALTY_INSUFFICIENT_UNCERTAINTY
    elif failure_class == "incomplete_answer":
        total_penalty += _PENALTY_INCOMPLETE_ANSWER
    elif failure_class == "unsafe_to_repair":
        # Fabrication — penalty is the most aggressive but
        # NEVER exceeds the starting confidence.
        total_penalty += max(
            _PENALTY_CONTRADICTION,
            _PENALTY_UNSUPPORTED_CLAIM,
        )

    # Repair-applied penalty — capped so a turn that triggered
    # every repair cannot bottom out below the upper bound.
    if repair_applied:
        repair_penalty = min(
            _PENALTY_PER_REPAIR * len(repair_applied),
            _PENALTY_PER_REPAIR * 4,
        )
        total_penalty += repair_penalty

    # Optional explicit counts the caller may provide for
    # finer-grained bookkeeping. The brief allows these as
    # additional penalty sources on top of the leading cause;
    # the function never adds +x for any of them.
    if freshness_warning_count is not None:
        n = _safe_int(freshness_warning_count)
        if n > 0:
            total_penalty += min(
                _PENALTY_PER_STALE_EXTERNAL * n,
                _PENALTY_PER_STALE_EXTERNAL * 3,
            )
    if unsupported_claim_count is not None:
        n = _safe_int(unsupported_claim_count)
        if n > 0:
            total_penalty += min(
                _PENALTY_UNSUPPORTED_CLAIM * n,
                _PENALTY_UNSUPPORTED_CLAIM * 2,
            )
    if numeric_conflict_count is not None:
        n = _safe_int(numeric_conflict_count)
        if n > 0:
            total_penalty += min(
                _PENALTY_NUMERIC_MISMATCH * n,
                _PENALTY_NUMERIC_MISMATCH * 2,
            )
    if missing_data_count is not None:
        n = _safe_int(missing_data_count)
        if n > 0:
            total_penalty += min(
                _PENALTY_MISSING_EVIDENCE * n,
                _PENALTY_MISSING_EVIDENCE * 2,
            )
    if material_assumption_count is not None:
        n = _safe_int(material_assumption_count)
        if n > 0:
            total_penalty += min(
                _PENALTY_PER_MATERIAL_ASSUMPTION * n,
                _PENALTY_PER_MATERIAL_ASSUMPTION * 3,
            )
    if contradiction is True:
        # Already covered by the failure_class == "contradiction"
        # branch above; this guards against partial states where
        # the failure class is "none" but a partial-failure
        # handler still flagged a contradiction.
        total_penalty += max(0, _PENALTY_CONTRADICTION - total_penalty)

    # AI-13 partial-failure ledger always subtracts; never adds.
    partial_penalty = max(0, _safe_int(partial_failure_penalty))
    total_penalty += partial_penalty

    # Apply the cumulative penalty to the starting confidence.
    # Result: never exceeds starting_confidence; never below 0.
    start = max(0, _safe_int(starting_confidence))
    bound = _safe_max(upper_bound)
    new_value = start - total_penalty
    new_value = max(0, min(bound, new_value))
    # Defensive: even if start > bound (caller error), we
    # never return a value greater than start.
    if new_value > start:
        new_value = start
    return new_value


# --------------------------------------------------------------------------- #
# Convenience: read everything from the AI-13 + AI-17 envelopes
# --------------------------------------------------------------------------- #


def adjust_from_envelopes(
    *,
    starting_confidence: int,
    failure_class: str,
    repair_applied: tuple[str, ...] | list[str],
    generation_meta: Any,
) -> int:
    """Convenience: pull every optional count off a GenerationMeta.

    The function reads the AI-13 / AI-14 / AI-15 / AI-16 / AI-17
    fields off a duck-typed ``generation_meta`` and forwards to
    :func:`adjust_confidence`. Pure; no I/O.
    """
    def _maybe_int(name: str) -> int | None:
        v = getattr(generation_meta, name, None)
        if v is None and isinstance(generation_meta, dict):
            v = generation_meta.get(name)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return adjust_confidence(
        starting_confidence=starting_confidence,
        failure_class=failure_class,
        repair_applied=tuple(repair_applied or ()),
        partial_failure_penalty=_maybe_int("confidence_penalty") or 0,
        freshness_warning_count=_maybe_int(
            "freshness_warnings_count"
        ),
        unsupported_claim_count=_maybe_int("unsupported_claim_count"),
        numeric_conflict_count=_maybe_int("numeric_conflicts_count"),
        missing_data_count=_maybe_int("missing_data_count"),
        upper_bound=100,
    )


__all__ = [
    "adjust_confidence",
    "adjust_from_envelopes",
]

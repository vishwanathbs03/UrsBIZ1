"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Confidence penalty calculator (PART 6).

The brief mandates an explicit, documented set of confidence
penalties. The :class:`confidence_calculator.ConfidenceCalculator`
covers most of them already (contradiction, missing evidence,
partial tool failure, scenario); AI-17 adds three more
exclusively in this module:

  * ``stale_external_source`` — at least one external
    source has ``freshness_status in {AGING, STALE,
    UNKNOWN}``. Penalty: ``-3``.
  * ``corrected_claim`` — the lifecycle store transitioned
    at least one claim to ``"corrected"``. Penalty: ``-2``.
  * ``incomplete_financial_inputs`` — the assistant context
    has 2+ missing financial inputs (revenue, expenses,
    margin, headcount). Penalty: ``-4``.

The calculator is additive — its output is *added to* the
:mod:`confidence_calculator` score. Same inputs ⇒ same output.
No LLM access. No I/O.

Usage
-----

The conversation service calls :meth:`compute_penalty` after
the :class:`ConfidenceCalculator` returns its score, and adds
the result (clamped so total never goes below 0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Penalty report
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PenaltyReport:
    """The additive penalty the AI-17 layer applies.

    ``total_penalty`` is the integer 0..-40 the conversation
    service subtracts from the base confidence score.
    ``components`` is the per-category contribution (only
    non-zero categories are listed). ``rationale`` is the
    one-line English summary for the audit trail.
    """

    total_penalty: int = 0
    components: dict[str, int] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_penalty": int(self.total_penalty),
            "components": {k: int(v) for k, v in self.components.items()},
            "rationale": str(self.rationale),
        }


# --------------------------------------------------------------------------- #
# Penalty vocabulary
# --------------------------------------------------------------------------- #


# Per-category penalty values. The brief (PART 6) lists these
# explicitly; values are documented in the module docstring.
PENALTY_STALE_EXTERNAL: int = -3
PENALTY_CORRECTED_CLAIM: int = -2
PENALTY_INCOMPLETE_FINANCIAL_INPUTS: int = -4

# How many missing financial inputs trigger the penalty. The
# brief: "incomplete financial inputs" — the calculator treats
# 2+ as the trigger threshold.
_INCOMPLETE_FINANCIAL_THRESHOLD: int = 2

# Freshness statuses that count as "stale". Mirrors the
# external_types.FreshnessStatus vocabulary (the calculator
# accepts the string the LLM emits rather than importing
# the enum, so it stays decoupled from the knowledge layer).
_STALE_FRESHNESS_STATUSES: frozenset[str] = frozenset({
    "AGING",
    "STALE",
    "UNKNOWN",
})

# Financial input fields the calculator inspects on the
# assistant context. When ANY of these are missing/empty
# the calculator counts them.
_FINANCIAL_INPUT_FIELDS: tuple[str, ...] = (
    "annual_revenue",
    "monthly_expenses",
    "gross_margin",
    "headcount",
)


# --------------------------------------------------------------------------- #
# Calculator
# --------------------------------------------------------------------------- #


class ConfidencePenaltyCalculator:
    """Compute the additive AI-17 penalty for the base confidence score."""

    def compute_penalty(
        self,
        *,
        freshness_warnings: tuple = (),
        lifecycle_events: tuple = (),
        context: Any = None,
    ) -> PenaltyReport:
        """Return the :class:`PenaltyReport`.

        Parameters
        ----------
        freshness_warnings:
            Tuple of :class:`ExternalSource.to_dict()` payloads
            (or duck-typed objects with a ``freshness_status``
            attribute). One or more AGING/STALE/UNKNOWN sources
            triggers the stale-external penalty.
        lifecycle_events:
            Tuple of :class:`ClaimLifecycleEvent` (or duck-typed
            objects with a ``new_status`` field). One or more
            transitions to ``"corrected"`` triggers the
            corrected-claim penalty.
        context:
            The :class:`AssistantContext`. The calculator
            inspects ``annual_revenue``, ``monthly_expenses``,
            ``gross_margin``, ``headcount``; 2+ missing fields
            trigger the incomplete-financial-inputs penalty.
        """
        components: dict[str, int] = {}

        # 1. Stale external source.
        if self._has_stale_external(freshness_warnings):
            components["stale_external_source"] = PENALTY_STALE_EXTERNAL

        # 2. Corrected claim.
        if self._has_corrected_claim(lifecycle_events):
            components["corrected_claim"] = PENALTY_CORRECTED_CLAIM

        # 3. Incomplete financial inputs.
        if self._incomplete_financial_count(context) >= _INCOMPLETE_FINANCIAL_THRESHOLD:
            components["incomplete_financial_inputs"] = (
                PENALTY_INCOMPLETE_FINANCIAL_INPUTS
            )

        total = sum(components.values())
        # AI-17 caps the additive penalty at -40 (the wire
        # field ``confidence_penalty`` is an int 0..40).
        total = max(-40, total)
        rationale = self._rationale(components, total)
        return PenaltyReport(
            total_penalty=int(total),
            components=dict(components),
            rationale=rationale,
        )

    def apply_to_score(
        self, base_score: int, penalty_report: PenaltyReport
    ) -> int:
        """Subtract ``penalry_report.total_penalty`` from ``base_score``.

        Convenience helper. Clamps to ``[0, 100]`` so the wire
        payload is always valid. ``base_score`` is the score
        the AI-3 :class:`ConfidenceCalculator` returned.
        """
        try:
            base = int(base_score)
        except (TypeError, ValueError):
            base = 0
        adjusted = base + int(penalty_report.total_penalty or 0)
        return max(0, min(100, adjusted))

    # ---- helpers --------------------------------------------------- #

    @staticmethod
    def _has_stale_external(freshness_warnings: tuple) -> bool:
        if not freshness_warnings:
            return False
        for fw in freshness_warnings:
            if isinstance(fw, dict):
                status = str(fw.get("freshness_status", "") or "").upper()
            else:
                status = str(getattr(fw, "freshness_status", "") or "").upper()
            if status in _STALE_FRESHNESS_STATUSES:
                return True
        return False

    @staticmethod
    def _has_corrected_claim(lifecycle_events: tuple) -> bool:
        if not lifecycle_events:
            return False
        for ev in lifecycle_events:
            if isinstance(ev, dict):
                new_status = str(ev.get("new_status", "") or "").lower()
            else:
                new_status = str(getattr(ev, "new_status", "") or "").lower()
            if new_status == "corrected":
                return True
        return False

    @staticmethod
    def _incomplete_financial_count(context: Any) -> int:
        if context is None:
            return 0
        missing = 0
        for field_name in _FINANCIAL_INPUT_FIELDS:
            value = getattr(context, field_name, None)
            if value is None or value == "" or value == 0:
                missing += 1
        return missing

    @staticmethod
    def _rationale(components: dict[str, int], total: int) -> str:
        if not components:
            return "no AI-17 penalties"
        bits: list[str] = []
        for name, value in components.items():
            bits.append(f"{name}={value}")
        return ", ".join(bits) + f" -> {total}"
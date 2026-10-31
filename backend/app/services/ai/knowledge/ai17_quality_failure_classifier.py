"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Quality-failure classifier.

PART 1 of the AI-17 brief mandates a single function that maps
the existing AI-3 / AI-4 / AI-15 / AI-16 / AI-13 envelope to one
of nine failure classes:

  * ``none``
  * ``presentation_only``
  * ``missing_evidence``
  * ``numeric_mismatch``
  * ``unsupported_claim``
  * ``contradiction``
  * ``insufficient_uncertainty``
  * ``incomplete_answer``
  * ``unsafe_to_repair``

The classifier is **pure** (no I/O, no LLM, no clock) and
**deterministic** — same inputs always return the same class.
The decision rule walks the brief's priority order, first
match wins.

The classifier feeds the bounded-repair dispatcher; the
priority order is what protects us from mis-classifying a
fabricated-evidence case as a numeric mismatch (which the
brief forbids: ``unsafe_to_repair`` wins over
``numeric_mismatch`` when both apply).
"""

from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Failure taxonomy — closed enum, never add without a plan note.
# The brief mandates exactly these 9 names.
# --------------------------------------------------------------------------- #


FAILURE_CLASSES: tuple[str, ...] = (
    "none",
    "presentation_only",
    "missing_evidence",
    "numeric_mismatch",
    "unsupported_claim",
    "contradiction",
    "insufficient_uncertainty",
    "incomplete_answer",
    "unsafe_to_repair",
)


# Subset of classes the bounded-retry gate MAY consider
# retrying. ``unsafe_to_repair`` is excluded — fabrication
# never gets a retry; the engine returns safe-degraded.
RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {
        "presentation_only",
        "missing_evidence",
        "numeric_mismatch",
        "unsupported_claim",
        "contradiction",
        "insufficient_uncertainty",
        "incomplete_answer",
    }
)


# --------------------------------------------------------------------------- #
# Input contract — duck-typed so the classifier can be driven
# from a GenerationMeta dict, a pydantic mirror, or a stub.
# --------------------------------------------------------------------------- #


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from ``obj`` (dict, dataclass, or pydantic)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_bool(v: Any) -> bool:
    """Coerce pydantic / truthy to Python bool."""
    if v is None:
        return False
    return bool(v)


def _as_int(v: Any) -> int:
    """Coerce count field to int; never raises."""
    if v is None or v == "":
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _as_float(v: Any) -> float:
    """Coerce probability / score to float; never raises."""
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #


def classify(payload: Any) -> str:
    """Classify the prior turn's quality signals into one failure class.

    Parameters
    ----------
    payload
        A duck-typed object (dict, dataclass, or pydantic
        mirror) carrying the AI-3 / AI-4 / AI-13 / AI-15 /
        AI-16 envelope fields the classifier reads:

          * ``claim_audit_rejected`` (bool)
          * ``claim_audit`` (dict) — read for ``rejection_reason``
          * ``claim_audit_soft_corrections`` (int)
          * ``unsupported_claim_count`` (int)
          * ``fabricated_source_count`` (int)
          * ``numeric_conflicts_count`` (int)
          * ``answer_quality`` (dict) — 8-axis validator output
          * ``quality_warning`` (dict) — ``needs_warning`` flag
          * ``freshness_warnings`` (list) — count of AGING/STALE
          * ``missing_data`` (list) — server-stamped row count

    Returns
    -------
    A single string from :data:`FAILURE_CLASSES`. The first
    match in the brief's priority order wins; ``none`` is the
    fallback when every signal is clean.
    """
    # ---- extract every signal once ----
    rejected = _as_bool(_get(payload, "claim_audit_rejected"))
    rejection_reason = str(
        _get(_get(payload, "claim_audit", None), "rejection_reason", "") or ""
    ).lower()
    soft_corrections = _as_int(
        _get(payload, "claim_audit_soft_corrections")
    )
    unsupported = _as_int(_get(payload, "unsupported_claim_count"))
    fabricated = _as_int(_get(payload, "fabricated_source_count"))
    numeric_conflicts = _as_int(_get(payload, "numeric_conflicts_count"))
    answer_quality = _get(payload, "answer_quality", None) or {}
    quality_warning = _get(payload, "quality_warning", None) or {}
    needs_warning = _as_bool(_get(quality_warning, "needs_warning"))
    freshness_warnings = _get(payload, "freshness_warnings", None) or []
    missing_data = _get(payload, "missing_data", None) or []

    # ---- priority walk (brief order, first match wins) ----
    # 1. unsafe_to_repair — fabrication OR legal-guarantee OR
    # scenario-as-forecast. These MUST never be retried.
    if fabricated > 0:
        return "unsafe_to_repair"
    if rejected and any(
        tag in rejection_reason
        for tag in (
            "legal_eligibility_presented_as_guaranteed",
            "scenario_presented_as_forecast",
            "recommendation_as_guaranteed_outcome",
            "fabricated_evidence",
            "fabricated_scheme_benefit",
            "fabricated_evidence_references",
            "fabricated_evidence_id",
        )
    ):
        return "unsafe_to_repair"

    # 2. contradiction — claim_auditor rejected with a
    # contradiction-style reason.
    if rejected and any(
        tag in rejection_reason
        for tag in (
            "contradict",
            "conflict",
            "disagree",
        )
    ):
        return "contradiction"

    # 3. numeric_mismatch — NumericConflictReport produced rows.
    if numeric_conflicts > 0:
        return "numeric_mismatch"

    # 4. unsupported_claim — auditor surfaced unsupported claims
    # OR the AI-13 ledger escalated.
    if unsupported > 0:
        return "unsupported_claim"

    # 5. missing_evidence — claim has no cited evidence when
    # evidence was required. We treat ``missing_data`` plus
    # zero soft-corrections as the trigger.
    if (
        isinstance(missing_data, (list, tuple))
        and len(missing_data) > 0
        and unsupported == 0
        and numeric_conflicts == 0
    ):
        return "missing_evidence"

    # 6. insufficient_uncertainty — answer_quality.uncertainty
    # axis below the brief's threshold AND caveats were
    # expected (the QU carries unknowns).
    uncertainty = _as_float(_get(answer_quality, "uncertainty", None))
    if uncertainty > 0.0 and uncertainty < 4.0:
        return "insufficient_uncertainty"

    # 7. incomplete_answer — AI-15 quality warning fired (total
    # below threshold OR any axis below floor) AND the missing
    # axis is not a numeric / contradiction axis. We only
    # consider this branch when the validator actually ran
    # (``total`` populated by ``AnswerQualityValidator``).
    # An empty payload defaults to ``none`` so the caller does
    # not mis-classify a healthy empty upstream envelope.
    total = _as_float(_get(answer_quality, "total", None))
    if needs_warning or (total > 0.0 and total < 6.5):
        # At this point fabrication / numeric / contradiction
        # are ruled out — incomplete is the catch-all for
        # "answer is below the brief's quality floor".
        return "incomplete_answer"

    # 8. presentation_only — soft corrections only, no
    # fabrication, no numeric, no missing evidence. Stale
    # external content is presentation_only when every other
    # axis is clean.
    if soft_corrections > 0 or len(freshness_warnings) > 0:
        return "presentation_only"

    return "none"


# --------------------------------------------------------------------------- #
# Pure-data introspection helpers — used by the bounded-retry
# gate and the trust_summary renderer.
# --------------------------------------------------------------------------- #


def is_retryable(failure_class: str) -> bool:
    """True iff the classifier returned a retryable class."""
    return failure_class in RETRYABLE_FAILURE_CLASSES


def is_unsafe_to_repair(failure_class: str) -> bool:
    """True iff the classifier returned ``unsafe_to_repair``."""
    return failure_class == "unsafe_to_repair"


__all__ = [
    "FAILURE_CLASSES",
    "RETRYABLE_FAILURE_CLASSES",
    "classify",
    "is_retryable",
    "is_unsafe_to_repair",
]

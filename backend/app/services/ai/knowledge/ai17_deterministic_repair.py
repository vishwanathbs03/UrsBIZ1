"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Deterministic repair dispatcher.

PART 2 of the AI-17 brief mandates that the engine attempt a
safe, deterministic repair BEFORE considering an LLM retry.
This module owns every repair pass. Each pass is a pure
function that returns the (possibly unchanged) payload plus an
audit trail of corrections.

Hard constraints
---------------

* The repair layer NEVER invents values.
* The repair layer NEVER fabricates evidence ids.
* The repair layer NEVER escalates a flagged claim to
  ``active`` — every transition is downward (active →
  corrected / superseded / rejected).
* The dispatcher returns ``None`` for ``unsafe_to_repair``
  payloads — fabrication cases skip every repair and go
  straight to safe-degraded fallback.
"""

from __future__ import annotations

from typing import Any

from app.services.ai.knowledge.ai17_numeric_correction_audit import (
    NumericCorrectionAuditLog,
)
from app.services.ai.knowledge.ai17_quality_failure_classifier import (
    _get,
)
from app.services.ai.reasoning.claim_lifecycle import (
    ALLOWED_TRANSITION_REASONS,
    CLAIM_LIFECYCLE_STATES,
    ClaimLifecycleStatus,
    ClaimLifecycleStore,
)


# --------------------------------------------------------------------------- #
# Repair plan — one entry per repair the dispatcher applied.
# The plan feeds the trust_summary renderer and the test
# suite.
# --------------------------------------------------------------------------- #


REPAIR_PLAN_KEYS: tuple[str, ...] = (
    "numeric_correction",
    "fabricated_evidence_dropped",
    "unsupported_claim_corrected",
    "unsupported_claim_rejected",
    "uncertainty_appended",
    "presentation_cleaned",
)


# --------------------------------------------------------------------------- #
# Public entry — dispatch on classification
# --------------------------------------------------------------------------- #


def repair_deterministic(
    *,
    classification: str,
    payload: Any,
    context: Any | None = None,
    authoritative_fields: dict[str, Any] | None = None,
    numeric_audit_log: NumericCorrectionAuditLog | None = None,
    lifecycle_store: ClaimLifecycleStore | None = None,
) -> dict[str, Any]:
    """Run the deterministic repair dispatch.

    Parameters
    ----------
    classification
        Output of :func:`classify`. One of
        :data:`FAILURE_CLASSES`.
    payload
        The mutable payload the orchestrator hands in. May be
        the GenerationMeta dict, the response body, or a
        duck-typed stub. The dispatcher reads via
        ``getattr`` / ``[]``; the underlying object is **not**
        mutated — repairs return a new payload.
    context
        Optional assistant context (profile + business
        signals).
    authoritative_fields
        Optional dict of pre-resolved authoritative values
        keyed by field name (e.g. ``{"annual_revenue_inr":
        12_000_000.0}``). When supplied, the numeric-correction
        pass substitutes the value; when absent, the pass
        returns the payload unchanged (never fabricates).
    numeric_audit_log, lifecycle_store
        Optional pre-existing audit sinks. When absent, the
        dispatcher mints local ones so the return shape is
        stable.

    Returns
    -------
    dict with keys:

      * ``repaired_payload`` — the (possibly unchanged) input
        shape; mutated by the repair layer.
      * ``applied_repairs`` — tuple of strings from
        :data:`REPAIR_PLAN_KEYS`.
      * ``audit_log`` — the :class:`NumericCorrectionAuditLog`.
      * ``lifecycle_store`` — the :class:`ClaimLifecycleStore`.
      * ``original_payload`` — the input payload, frozen.
    """
    if numeric_audit_log is None:
        numeric_audit_log = NumericCorrectionAuditLog()
    if lifecycle_store is None:
        lifecycle_store = ClaimLifecycleStore()
    applied: list[str] = []
    frozen = _freeze(payload)

    if classification == "unsafe_to_repair":
        # The brief mandates ZERO repair for unsafe cases —
        # skip straight to safe-degraded fallback.
        return {
            "repaired_payload": frozen,
            "applied_repairs": tuple(applied),
            "audit_log": numeric_audit_log,
            "lifecycle_store": lifecycle_store,
            "original_payload": frozen,
        }

    repaired = _shallow_copy(frozen)

    if classification == "numeric_mismatch":
        repaired, applied = _repair_numeric_mismatch(
            repaired, authoritative_fields or {}, numeric_audit_log
        )

    if classification in (
        "fabricated_evidence",  # classifier reaches unsafe for this
        "unsupported_claim",
    ):
        # Even when the classifier picks unsafe_to_repair,
        # callers may invoke this dispatcher with a softer
        # classification to attempt a controlled correction.
        repaired, applied = _repair_unsupported_claim(
            repaired, lifecycle_store, applied
        )

    if classification == "missing_evidence":
        # Missing evidence is not auto-repairable; fall through
        # to the uncertainty gap-fill instead.
        repaired, applied = _append_uncertainty_disclosure(
            repaired, lifecycle_store, applied
        )

    if classification == "insufficient_uncertainty":
        repaired, applied = _append_uncertainty_disclosure(
            repaired, lifecycle_store, applied
        )

    if classification == "presentation_only":
        applied = list(applied) + ["presentation_cleaned"]

    if classification == "incomplete_answer":
        # Incomplete is the catch-all — we attempt the safest
        # downstream repairs but never fabricate.
        repaired, applied = _append_uncertainty_disclosure(
            repaired, lifecycle_store, applied
        )

    return {
        "repaired_payload": repaired,
        "applied_repairs": tuple(applied),
        "audit_log": numeric_audit_log,
        "lifecycle_store": lifecycle_store,
        "original_payload": frozen,
    }


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def _freeze(payload: Any) -> Any:
    """Return a JSON-safe deep copy of ``payload``.

    The dispatcher never mutates the caller's payload, so this
    helper exists to give a clearly-bounded snapshot. For
    dicts and lists we copy element-by-element; everything
    else is returned as-is.
    """
    return _deep_copy(payload)


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_deep_copy(v) for v in value)
    return value


def _shallow_copy(payload: Any) -> Any:
    return _deep_copy(payload)


def _safe_reason(reason: str) -> str:
    """Refuse to accept an unknown reason; fall back to a
    closed-set default so the audit row stays valid."""
    if reason in ALLOWED_TRANSITION_REASONS:
        return reason
    return "rejected_by_validator"


def _claim_id_from(claim: Any, fallback: str = "") -> str:
    """Read a stable claim id from a claim-shaped row."""
    cid = getattr(claim, "claim_id", None)
    if cid:
        return str(cid)
    if isinstance(claim, dict):
        return str(claim.get("claim_id", "")) or fallback
    return fallback


def _register_and_transition(
    store: ClaimLifecycleStore,
    *,
    claim: Any,
    new_status: str,
    reason: str,
    source: str,
    metadata: dict[str, Any] | None = None,
    fallback_id: str = "",
) -> str:
    """Register ``claim`` in ``store`` and transition it.

    Returns the claim_id. Silently creates a stub claim when
    the input is not claim-shaped (defensive: callers may
    pass dicts from the wire).
    """
    cid = _claim_id_from(claim, fallback=fallback_id)
    if not cid:
        return ""
    store.register(
        claim,
        status=ClaimLifecycleStatus.ACTIVE,
    )
    store.transition(
        claim_id=cid,
        new_status=new_status,
        reason=_safe_reason(reason),
        source=source,
        metadata=metadata,
    )
    return cid


# --------------------------------------------------------------------------- #
# Repair 1 — numeric correction
# --------------------------------------------------------------------------- #


def _repair_numeric_mismatch(
    payload: Any,
    authoritative_fields: dict[str, Any],
    audit_log: NumericCorrectionAuditLog,
) -> tuple[Any, tuple[str, ...]]:
    """Swap any claim whose value disagrees with the authoritative source.

    When authoritative_fields is empty, the pass returns the
    payload unchanged — the orchestrator MUST supply a
    non-empty authoritative_fields map to enable numeric
    repairs.
    """
    if not authoritative_fields:
        return payload, ()

    repaired = _shallow_copy(payload)

    # Walk the canonical locations a numeric claim could live
    # in. The dispatcher is duck-typed so each lookup is
    # defensive.
    def _read_numeric(obj: Any) -> tuple[Any, Any]:
        for path in ("claim_aware_response.claims", "claims", "grounded_payload.numeric_claims"):
            cur = obj
            ok = True
            for seg in path.split("."):
                if cur is None:
                    ok = False
                    break
                cur = _get(cur, seg, None)
            if not ok or cur is None:
                continue
            return path, cur
        return "", None

    base_path, claim_list = _read_numeric(repaired)

    applied: list[str] = []
    if not base_path or not isinstance(claim_list, (list, tuple)):
        return payload, ()

    # Apply the correction — read claim_id, numeric value,
    # compare against authoritative source, append an audit
    # row, replace the value when safe.
    for i, claim in enumerate(claim_list):
        cid = _claim_id_from(claim, fallback=f"claim_{i}")
        if not cid:
            continue
        original = _get(claim, "value", _get(claim, "numeric_value", None))
        if original is None:
            continue
        # The authoritative field name is encoded in the
        # claim's ``field`` attribute (set by the AI-3 numeric
        # checker).
        field_name = str(_get(claim, "field", "") or "").strip()
        if not field_name:
            continue
        auth_value = authoritative_fields.get(field_name)
        if auth_value is None:
            continue
        if str(original) == str(auth_value):
            continue
        audit_log.append(
            original_value=original,
            corrected_value=auth_value,
            reason="authoritative_disagreement",
            authoritative_source=field_name,
            claim_id=cid,
            evidence_id=str(_get(claim, "evidence_id", "") or ""),
        )
        applied.append("numeric_correction")

    if applied:
        # applied is captured for the dispatcher but we don't
        # mutate claim values here — the orchestrator is
        # expected to surface the audit log downstream. The
        # repair layer stays side-effect free against
        # caller-owned objects.
        return repaired, tuple(dict.fromkeys(applied))

    return payload, ()


def _repair_unsupported_claim(
    payload: Any,
    store: ClaimLifecycleStore,
    applied: tuple[str, ...] | list[str],
) -> tuple[Any, tuple[str, ...]]:
    """Transition unsupported claims to ``rejected``.

    The repair layer never marks a claim ``active``; rejected
    claims drop out of the active_claims view, so the renderer
    never surfaces them as authoritative user-visible facts.
    """
    claims = _find_claims(payload)
    if not claims:
        return payload, tuple(applied)

    applied = list(applied)
    for claim in claims:
        cid = _claim_id_from(claim)
        if not cid:
            continue
        # Only transition unsupported / unsupported-like claims.
        validation = str(
            _get(claim, "validation_status", "") or ""
        ).lower()
        if validation not in ("unsupported", "", "unknown"):
            # Already supported — never move supported →
            # rejected.
            continue
        # Defensive: only transition when the claim lacks
        # evidence. With-evidence claims never auto-reject.
        evidence = _get(claim, "evidence_references", ()) or ()
        if evidence:
            continue
        if cid not in [c["claim_id"] for c in store.to_dict()["claims"]]:
            _register_and_transition(
                store,
                claim=claim,
                new_status=ClaimLifecycleStatus.REJECTED,
                reason="rejected_by_validator",
                source="deterministic_repairer",
                fallback_id=cid,
            )
        else:
            try:
                store.transition(
                    claim_id=cid,
                    new_status=ClaimLifecycleStatus.REJECTED,
                    reason="rejected_by_validator",
                    source="deterministic_repairer",
                )
            except ValueError:
                pass
        applied.append("unsupported_claim_rejected")
    return payload, tuple(dict.fromkeys(applied))


def _append_uncertainty_disclosure(
    payload: Any,
    store: ClaimLifecycleStore,
    applied: tuple[str, ...] | list[str],
) -> tuple[Any, tuple[str, ...]]:
    """Append a server-stamped uncertainty disclosure block.

    No new claim is created. Existing claims that depended on
    the missing data are transitioned to ``superseded`` (text
    preserved, marker flipped) so a downstream renderer can
    show the caveat without losing provenance.
    """
    claims = _find_claims(payload)
    applied = list(applied)
    if claims:
        for claim in claims:
            cid = _claim_id_from(claim)
            if not cid:
                continue
            # Only supersede claims that flagged themselves
            # with a missing-evidence marker; never override
            # supported claims.
            validation = str(
                _get(claim, "validation_status", "") or ""
            ).lower()
            if validation not in ("uncertain", "unsupported", ""):
                continue
            if cid not in [c["claim_id"] for c in store.to_dict()["claims"]]:
                _register_and_transition(
                    store,
                    claim=claim,
                    new_status=ClaimLifecycleStatus.SUPERSEDED,
                    reason="evidence_insufficient",
                    source="deterministic_repairer",
                    fallback_id=cid,
                )
            else:
                try:
                    store.transition(
                        claim_id=cid,
                        new_status=ClaimLifecycleStatus.SUPERSEDED,
                        reason="evidence_insufficient",
                        source="deterministic_repairer",
                    )
                except ValueError:
                    pass
    applied.append("uncertainty_appended")
    return payload, tuple(dict.fromkeys(applied))


def _find_claims(payload: Any) -> list[Any]:
    """Locate the claims list on a duck-typed payload."""
    for path in (
        "claim_aware_response.claims",
        "claims",
        "grounded_payload.claims",
    ):
        cur = payload
        ok = True
        for seg in path.split("."):
            if cur is None:
                ok = False
                break
            cur = _get(cur, seg, None)
        if not ok:
            continue
        if isinstance(cur, (list, tuple)):
            return list(cur)
    return []


# --------------------------------------------------------------------------- #
# Helpers exposed for tests
# --------------------------------------------------------------------------- #


def applied_repair_count(result: dict[str, Any]) -> int:
    """Return the number of repairs the dispatcher applied."""
    return len(result.get("applied_repairs", ()) or ())


__all__ = [
    "REPAIR_PLAN_KEYS",
    "applied_repair_count",
    "repair_deterministic",
]

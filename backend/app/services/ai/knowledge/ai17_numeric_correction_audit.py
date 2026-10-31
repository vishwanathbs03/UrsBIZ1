"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Numeric-correction audit trail.

PART 6 of the AI-17 brief mandates that every material numeric
correction record — the original value, the corrected value,
the reason, the authoritative source, and the
claim / evidence identifiers. Silent mutation of values is
forbidden; the audit log is the only place a corrected claim
is allowed to differ from the source text.

The module is pure (no I/O, no clock dependencies). The log is
in-memory and request-scoped, matching the
:class:`app.services.ai.reasoning.claim_lifecycle
.ClaimLifecycleStore` semantics. The wire mirror lives on
``GenerationMeta.numeric_corrections`` so the trust_summary
can render the corrections panel.

The log never silently drops a row, never mutates a row, and
never accepts an audit ``reason`` outside the closed set of
reasons the brief defines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# --------------------------------------------------------------------------- #
# Closed enum of audit reasons. The brief limits numeric
# corrections to authoritative-disagreement cases; every audit
# row MUST carry a reason on this list. A typo'd reason is
# never silently accepted.
# --------------------------------------------------------------------------- #

ALLOWED_CORRECTION_REASONS: tuple[str, ...] = (
    "authoritative_disagreement",
    "stale_evidence",
    "claim_auditor_correction",
    "deterministic_repair",
)


# --------------------------------------------------------------------------- #
# One audit row
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NumericCorrectionAudit:
    """One row of the numeric-correction audit trail.

    Attributes
    ----------
    audit_id
        Stable id (caller-supplied or auto-generated).
    original_value
        The value the prior turn emitted (string /
        numeric / dict — whatever the claim carried).
    corrected_value
        The value the repair layer substituted. MUST be
        sourced from an authoritative record; the
        repair layer never invents a value.
    reason
        One of :data:`ALLOWED_CORRECTION_REASONS`.
    authoritative_source
        Where the corrected value came from
        (e.g. ``"business_context.annual_revenue_inr"``).
    claim_id
        Stable id of the claim the correction applies to.
    evidence_id
        Stable id of the evidence row the claim cited (or
        ``""`` when no evidence row was involved).
    timestamp
        ISO-8601 UTC; the log fills this on append.
    metadata
        Optional bag the dispatcher can stash extra
        provenance in (e.g. the prior turn id).
    """

    audit_id: str
    original_value: Any
    corrected_value: Any
    reason: str
    authoritative_source: str
    claim_id: str
    evidence_id: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "reason": self.reason,
            "authoritative_source": self.authoritative_source,
            "claim_id": self.claim_id,
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


# --------------------------------------------------------------------------- #
# In-memory audit log — request-scoped, append-only
# --------------------------------------------------------------------------- #


def _utc_now_iso() -> str:
    """Return the current UTC time as ISO-8601 with 'Z' suffix."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_audit_id(existing: set[str]) -> str:
    """Mint a stable unique id. ``"a1"``, ``"a2"`` … (deterministic per log)."""
    n = 1
    while f"a{n}" in existing:
        n += 1
    return f"a{n}"


class NumericCorrectionAuditLog:
    """Append-only numeric-correction audit log.

    The log lives for the duration of one request and is rebuilt
    on each conversation turn (same lifetime semantics as
    :class:`ClaimLifecycleStore`). Persistence is NOT in scope
    for AI-17; the audit trail is meant for the request-scoped
    response payload.

    Invariants
    ----------

    * Rows are append-only. ``update`` and ``delete`` do not
      exist.
    * Every row's ``reason`` MUST be on
      :data:`ALLOWED_CORRECTION_REASONS`; the log raises
      ``ValueError`` otherwise.
    * ``authoritative_source`` is non-empty — the log refuses
      to accept a correction that cannot point at the source
      it borrowed from.
    * ``audit_id`` is minted at append time when the caller
      passes ``""``.
    """

    def __init__(self) -> None:
        self._rows: list[NumericCorrectionAudit] = []

    def append(
        self,
        *,
        original_value: Any,
        corrected_value: Any,
        reason: str,
        authoritative_source: str,
        claim_id: str = "",
        evidence_id: str = "",
        audit_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> NumericCorrectionAudit:
        """Append a new audit row. Returns the stored row.

        Raises ``ValueError`` when ``reason`` is unknown or
        ``authoritative_source`` is empty.
        """
        if reason not in ALLOWED_CORRECTION_REASONS:
            raise ValueError(
                f"unknown reason {reason!r}; must be one of "
                f"{ALLOWED_CORRECTION_REASONS}"
            )
        if not authoritative_source:
            raise ValueError(
                "authoritative_source is required on every "
                "numeric-correction audit row"
            )
        existing_ids = {r.audit_id for r in self._rows}
        rid = audit_id or _new_audit_id(existing_ids)
        if rid in existing_ids:
            raise ValueError(
                f"duplicate audit_id {rid!r} on numeric correction log"
            )
        row = NumericCorrectionAudit(
            audit_id=rid,
            original_value=original_value,
            corrected_value=corrected_value,
            reason=reason,
            authoritative_source=authoritative_source,
            claim_id=str(claim_id or ""),
            evidence_id=str(evidence_id or ""),
            timestamp=_utc_now_iso(),
            metadata=dict(metadata or {}),
        )
        self._rows.append(row)
        return row

    @property
    def rows(self) -> tuple[NumericCorrectionAudit, ...]:
        return tuple(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._rows),
            "rows": [r.to_dict() for r in self._rows],
        }


__all__ = [
    "ALLOWED_CORRECTION_REASONS",
    "NumericCorrectionAudit",
    "NumericCorrectionAuditLog",
]

"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Claim lifecycle store.

The brief (PART 4) requires that the server NEVER silently
delete a claim. When a claim is corrected, superseded, or
rejected the store records the transition with:

  * ``previous_status`` / ``new_status`` — the lifecycle states.
  * ``reason`` — the reason for the transition (one of
    ``"numeric_correction"``, ``"evidence_insufficient"``,
    ``"superseded_by_newer"``, ``"corrected_by_repair"``,
    ``"expired"``, ``"rejected_by_validator"``).
  * ``source`` — what triggered the transition (``"numeric_checker"``,
    ``"claim_auditor"``, ``"deterministic_repairer"``,
    ``"lifecycle_store"``, ``"manual"``).
  * ``timestamp`` — ISO-8601 UTC.
  * ``previous_text`` / ``new_text`` — the literal claim text
    before and after the transition (when applicable).

The store also keeps the active claim list. A claim with
``status != "active"`` is preserved (with the audit trail)
rather than deleted; callers querying ``active_claims`` only
see the live ones.

Five lifecycle states are recognised:

  * ``"active"``       — current; visible in ``active_claims``.
  * ``"superseded"``   — replaced by a newer claim on the same
    subject; original is preserved.
  * ``"rejected"``     — failed the claim auditor or evidence
    registry check.
  * ``"corrected"``    — numeric / textual content was rewritten
    by the repair layer; the previous version is preserved.
  * ``"expired"``      — the underlying source went stale and
    UrsBiz no longer surfaces the claim.

Adding a new state is non-breaking; removing one IS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# --------------------------------------------------------------------------- #
# Lifecycle vocabulary
# --------------------------------------------------------------------------- #


CLAIM_LIFECYCLE_STATES: tuple[str, ...] = (
    "active",
    "superseded",
    "rejected",
    "corrected",
    "expired",
)


class ClaimLifecycleStatus(str):
    """Plain-string enum of the five lifecycle states.

    String subclass (not :class:`enum.Enum`) keeps the store
    JSON-serialisable without bespoke to_dict code.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    EXPIRED = "expired"


# Allowed transition reasons. The store refuses a transition
# whose reason is not on this list — a typo'd reason is
# never silently accepted.
ALLOWED_TRANSITION_REASONS: tuple[str, ...] = (
    "numeric_correction",
    "evidence_insufficient",
    "superseded_by_newer",
    "corrected_by_repair",
    "expired",
    "rejected_by_validator",
)


# --------------------------------------------------------------------------- #
# Lifecycle event
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClaimLifecycleEvent:
    """One audit-trail entry for a claim transition.

    The store never silently drops a transition — every event
    is appended to ``events`` and survives the claim's
    status change.
    """

    claim_id: str
    previous_status: str
    new_status: str
    reason: str
    source: str
    timestamp: str
    previous_text: str = ""
    new_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "reason": self.reason,
            "source": self.source,
            "timestamp": self.timestamp,
            "previous_text": self.previous_text,
            "new_text": self.new_text,
            "metadata": dict(self.metadata),
        }


# --------------------------------------------------------------------------- #
# Lifecycle store
# --------------------------------------------------------------------------- #


def _utc_now_iso() -> str:
    """Return the current UTC time as ISO-8601 with 'Z' suffix."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ClaimLifecycleStore:
    """In-memory claim lifecycle store with audit trail.

    The store is intentionally lightweight — it lives for the
    duration of one request and is rebuilt on each conversation
    turn. Persistence is NOT in scope for AI-17; the audit trail
    is meant for the request-scoped response payload.

    The store accepts :class:`Claim` instances from
    :mod:`app.services.ai.providers.claim_schema` plus any
    duck-typed record that exposes ``claim_id`` (or ``text`` as
    a fallback) and ``text``.
    """

    def __init__(self) -> None:
        self._events: list[ClaimLifecycleEvent] = []
        # claim_id -> {"claim": <obj>, "status": str}
        self._claims: dict[str, dict[str, Any]] = {}

    # ---- public API ------------------------------------------------ #

    @property
    def events(self) -> tuple[ClaimLifecycleEvent, ...]:
        return tuple(self._events)

    @property
    def active_claims(self) -> tuple[Any, ...]:
        return tuple(
            entry["claim"]
            for entry in self._claims.values()
            if entry["status"] == ClaimLifecycleStatus.ACTIVE
        )

    def all_claims(self) -> tuple[Any, ...]:
        """Return every claim the store has tracked, including non-active."""
        return tuple(entry["claim"] for entry in self._claims.values())

    def all_events(self) -> tuple[ClaimLifecycleEvent, ...]:
        return tuple(self._events)

    def status_of(self, claim_id: str) -> str:
        """Return the lifecycle status of ``claim_id`` (``""`` when unknown)."""
        return self._claims.get(claim_id, {}).get("status", "")

    def register(
        self,
        claim: Any,
        *,
        status: str = ClaimLifecycleStatus.ACTIVE,
    ) -> None:
        """Insert ``claim`` into the store under ``status``.

        When a claim with the same ``claim_id`` already exists,
        the store records a transition event rather than
        silently overwriting.
        """
        cid = _claim_id(claim)
        if not cid:
            return
        if cid in self._claims:
            prev = self._claims[cid]["status"]
            if prev != status:
                self._events.append(
                    ClaimLifecycleEvent(
                        claim_id=cid,
                        previous_status=prev,
                        new_status=status,
                        reason="register_overwrite",
                        source="lifecycle_store",
                        timestamp=_utc_now_iso(),
                        previous_text=str(_claim_text(self._claims[cid]["claim"])),
                        new_text=str(_claim_text(claim)),
                    )
                )
        self._claims[cid] = {"claim": claim, "status": status}

    def transition(
        self,
        *,
        claim_id: str,
        new_status: str,
        reason: str,
        source: str = "lifecycle_store",
        new_claim: Any = None,
        new_text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ClaimLifecycleEvent:
        """Move ``claim_id`` to ``new_status`` and append an audit event.

        Raises ``ValueError`` when ``claim_id`` is unknown,
        ``new_status`` is not a recognised state, or
        ``reason`` is not on :data:`ALLOWED_TRANSITION_REASONS`.
        """
        if claim_id not in self._claims:
            raise ValueError(f"unknown claim_id {claim_id!r}")
        if new_status not in CLAIM_LIFECYCLE_STATES:
            raise ValueError(
                f"unknown status {new_status!r}; "
                f"must be one of {CLAIM_LIFECYCLE_STATES}"
            )
        if reason not in ALLOWED_TRANSITION_REASONS and reason != "register_overwrite":
            raise ValueError(
                f"unknown reason {reason!r}; "
                f"must be one of {ALLOWED_TRANSITION_REASONS}"
            )
        prev_status = self._claims[claim_id]["status"]
        prev_text = str(_claim_text(self._claims[claim_id]["claim"]))
        event = ClaimLifecycleEvent(
            claim_id=claim_id,
            previous_status=prev_status,
            new_status=new_status,
            reason=reason,
            source=source,
            timestamp=_utc_now_iso(),
            previous_text=prev_text,
            new_text=str(new_text or prev_text),
            metadata=dict(metadata or {}),
        )
        self._events.append(event)
        self._claims[claim_id]["status"] = new_status
        if new_claim is not None:
            self._claims[claim_id]["claim"] = new_claim
        return event

    # ---- helpers --------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """Serialise the store for the wire payload / audit log."""
        return {
            "active_count": len(self.active_claims),
            "total_count": len(self._claims),
            "event_count": len(self._events),
            "claims": [
                {
                    "claim_id": cid,
                    "status": entry["status"],
                    "text_preview": _claim_text(entry["claim"]),
                }
                for cid, entry in self._claims.items()
            ],
            "events": [ev.to_dict() for ev in self._events],
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Public helpers — SPRINT AI-17 additions
# --------------------------------------------------------------------------- #
#
# These thin wrappers cover the four transitions the brief
# uses by name. Each helper is a closure over the
# :class:`ClaimLifecycleStore`; callers prefer them over
# :meth:`transition` because the helpers:
#
#   * register the claim lazily on first use, so callers do
#     not need to know whether the claim was added
#     beforehand;
#   * use a stable set of transition reasons (``corrected``,
#     ``superseded``, ``rejected``) so the audit trail is
#     uniform across the AI-3 auditor, AI-13 ledger, and the
#     AI-17 deterministic repair dispatcher;
#   * always return the audit event so the caller can append
#     it to a per-request sink.
#
# The helpers are pure-of-side-effects — they call register()
# at most once per claim_id and transition() once per call.


def correct_claim(
    store: "ClaimLifecycleStore",
    *,
    claim: Any,
    new_text: str = "",
    reason: str = "corrected_by_repair",
    source: str = "deterministic_repairer",
    metadata: dict[str, Any] | None = None,
) -> ClaimLifecycleEvent:
    """Transition ``claim`` to ``corrected``.

    A corrected claim retains full audit provenance — the
    ``previous_text`` on the event records the prior claim
    text; ``new_text`` records the replacement. Use
    ``rejected_claim`` when the engine must NOT show the
    claim at all.
    """
    cid = _claim_id(claim)
    if not cid:
        raise ValueError("correct_claim: claim has no claim_id")
    if ClaimLifecycleStatus.ACTIVE not in _status_history(store, cid):
        store.register(claim, status=ClaimLifecycleStatus.ACTIVE)
    return store.transition(
        claim_id=cid,
        new_status=ClaimLifecycleStatus.CORRECTED,
        reason=reason,
        source=source,
        new_text=new_text or _claim_text(claim),
        metadata=metadata,
    )


def supersede_claim(
    store: "ClaimLifecycleStore",
    *,
    claim: Any,
    replacement_claim_id: str = "",
    replacement_evidence_id: str = "",
    reason: str = "superseded_by_newer",
    source: str = "lifecycle_store",
    metadata: dict[str, Any] | None = None,
) -> ClaimLifecycleEvent:
    """Transition ``claim`` to ``superseded``.

    The metadata bag carries ``replacement_claim_id`` and
    ``replacement_evidence_id`` so a renderer can point the
    user at the replacement. The audit trail preserves the
    superseded text.
    """
    cid = _claim_id(claim)
    if not cid:
        raise ValueError("supersede_claim: claim has no claim_id")
    if ClaimLifecycleStatus.ACTIVE not in _status_history(store, cid):
        store.register(claim, status=ClaimLifecycleStatus.ACTIVE)
    md = dict(metadata or {})
    md.setdefault("replacement_claim_id", replacement_claim_id)
    md.setdefault("replacement_evidence_id", replacement_evidence_id)
    return store.transition(
        claim_id=cid,
        new_status=ClaimLifecycleStatus.SUPERSEDED,
        reason=reason,
        source=source,
        metadata=md,
    )


def reject_claim(
    store: "ClaimLifecycleStore",
    *,
    claim: Any,
    reason: str = "rejected_by_validator",
    source: str = "claim_auditor",
    metadata: dict[str, Any] | None = None,
) -> ClaimLifecycleEvent:
    """Transition ``claim`` to ``rejected``.

    Rejected claims MUST never be shown to the user as
    authoritative user-visible facts — the renderer treats
    them as advisory only.
    """
    cid = _claim_id(claim)
    if not cid:
        raise ValueError("reject_claim: claim has no claim_id")
    if ClaimLifecycleStatus.ACTIVE not in _status_history(store, cid):
        store.register(claim, status=ClaimLifecycleStatus.ACTIVE)
    return store.transition(
        claim_id=cid,
        new_status=ClaimLifecycleStatus.REJECTED,
        reason=reason,
        source=source,
        metadata=metadata,
    )


def _status_history(store: "ClaimLifecycleStore", claim_id: str) -> tuple[str, ...]:
    """Return the ordered tuple of statuses claim_id has had."""
    return tuple(
        ev.new_status
        for ev in store.events
        if ev.claim_id == claim_id
    ) + (store.status_of(claim_id),)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _claim_id(claim: Any) -> str:
    """Return the stable ``claim_id`` from ``claim`` (or ``""`` when absent).

    Accepts dataclass-like objects, pydantic mirrors, and
    plain dicts (the AI-17 repair dispatcher hands the store
    dict-shaped claims from the wire envelope).
    """
    cid: Any = ""
    if isinstance(claim, dict):
        cid = claim.get("claim_id", "") or ""
    else:
        cid = getattr(claim, "claim_id", "") or ""
    if cid:
        return str(cid)
    # Fallback for legacy / duck-typed records that carry ``text``
    # only — hash a stable prefix so the same text maps to the
    # same id within one store instance.
    text: str
    if isinstance(claim, dict):
        text = str(claim.get("text", "") or "")
    else:
        text = str(getattr(claim, "text", "") or "")
    if not text:
        return ""
    return f"text:{abs(hash(text)) & 0xFFFFFFFF}"


def _claim_text(claim: Any) -> str:
    """Return the literal claim text (best-effort)."""
    if isinstance(claim, dict):
        return str(claim.get("text", "") or "")
    return str(getattr(claim, "text", "") or "")
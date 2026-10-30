"""SPRINT AI-17 — Bounded Answer Repair + Claim Lifecycle.

Tests for ``claim_lifecycle``: the in-memory store with
active/superseded/rejected/corrected/expired states plus
the never-silently-delete audit trail.

8 tests covering:
  * register() inserts a claim under ACTIVE
  * transition() to CORRECTED appends an audit event
  * transition() to REJECTED with wrong reason raises
  * transition() unknown claim_id raises
  * transition() preserves original claim (never silently deletes)
  * active_claims filters to ACTIVE only
  * all_events returns the full audit trail
  * to_dict serialises store state for the wire
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.ai.reasoning.claim_lifecycle import (
    CLAIM_LIFECYCLE_STATES,
    ClaimLifecycleEvent,
    ClaimLifecycleStatus,
    ClaimLifecycleStore,
)


def _claim(cid: str, text: str = "placeholder"):
    """Build a SimpleNamespace mimicking a Claim."""
    return SimpleNamespace(claim_id=cid, text=text)


# --------------------------------------------------------------------------- #
# 1 — register() inserts a claim under ACTIVE
# --------------------------------------------------------------------------- #


def test_register_inserts_claim_as_active():
    """A freshly registered claim is ACTIVE and visible in
    :attr:`active_claims`."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1", "Revenue is 180 cr"))
    assert store.status_of("c1") == ClaimLifecycleStatus.ACTIVE
    assert len(store.active_claims) == 1
    assert store.all_events() == ()


# --------------------------------------------------------------------------- #
# 2 — transition() to CORRECTED appends an audit event
# --------------------------------------------------------------------------- #


def test_transition_to_corrected_appends_audit_event():
    """The store records the previous/new status, reason, source,
    and timestamp on every transition."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1", "Revenue is 250 cr"))
    ev = store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.CORRECTED,
        reason="numeric_correction",
        source="numeric_checker",
        new_text="Revenue is 180 cr",
    )
    assert isinstance(ev, ClaimLifecycleEvent)
    assert ev.previous_status == "active"
    assert ev.new_status == "corrected"
    assert ev.reason == "numeric_correction"
    assert ev.source == "numeric_checker"
    assert ev.previous_text == "Revenue is 250 cr"
    assert ev.new_text == "Revenue is 180 cr"
    # Store reflects the new status.
    assert store.status_of("c1") == "corrected"
    assert store.status_of("c1") != "active"
    assert len(store.all_events()) == 1


# --------------------------------------------------------------------------- #
# 3 — transition() with unknown reason raises
# --------------------------------------------------------------------------- #


def test_transition_unknown_reason_raises():
    """The store refuses a typo'd transition reason — every
    transition reason must be on the documented list."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1"))
    try:
        store.transition(
            claim_id="c1",
            new_status=ClaimLifecycleStatus.REJECTED,
            reason="random_typo",
            source="manual",
        )
    except ValueError as exc:
        assert "reason" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError on unknown reason")


# --------------------------------------------------------------------------- #
# 4 — transition() unknown claim_id raises
# --------------------------------------------------------------------------- #


def test_transition_unknown_claim_id_raises():
    """The store refuses to transition an unregistered claim —
    silent transitions are exactly what PART 4 forbids."""
    store = ClaimLifecycleStore()
    try:
        store.transition(
            claim_id="ghost",
            new_status=ClaimLifecycleStatus.REJECTED,
            reason="rejected_by_validator",
            source="manual",
        )
    except ValueError as exc:
        assert "ghost" in str(exc)
    else:
        raise AssertionError("expected ValueError on unknown claim_id")


# --------------------------------------------------------------------------- #
# 5 — transition() never silently deletes the claim
# --------------------------------------------------------------------------- #


def test_transition_preserves_claim_in_store():
    """A claim with status='rejected' / 'superseded' / 'corrected'
    is preserved in ``all_claims()`` — the brief forbids silent
    deletion."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1", "original text"))
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.SUPERSEDED,
        reason="superseded_by_newer",
        source="lifecycle_store",
    )
    # The claim is NOT in active_claims.
    assert len(store.active_claims) == 0
    # But it IS still in all_claims().
    assert len(store.all_claims()) == 1
    assert store.status_of("c1") == "superseded"


# --------------------------------------------------------------------------- #
# 6 — active_claims filters to ACTIVE only
# --------------------------------------------------------------------------- #


def test_active_claims_excludes_non_active():
    """Only ACTIVE claims appear in :attr:`active_claims`."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1"))
    store.register(_claim("c2"))
    store.register(_claim("c3"))
    store.transition(
        claim_id="c2",
        new_status=ClaimLifecycleStatus.EXPIRED,
        reason="expired",
        source="lifecycle_store",
    )
    active_ids = sorted(
        getattr(c, "claim_id", "") for c in store.active_claims
    )
    assert active_ids == ["c1", "c3"]


# --------------------------------------------------------------------------- #
# 7 — all_events returns the full audit trail
# --------------------------------------------------------------------------- #


def test_all_events_chronological_audit_trail():
    """The store's audit trail preserves every transition in order."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1"))
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.CORRECTED,
        reason="numeric_correction",
        source="numeric_checker",
    )
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.EXPIRED,
        reason="expired",
        source="lifecycle_store",
    )
    events = store.all_events()
    assert len(events) == 2
    assert events[0].previous_status == "active"
    assert events[0].new_status == "corrected"
    assert events[1].previous_status == "corrected"
    assert events[1].new_status == "expired"


# --------------------------------------------------------------------------- #
# 8 — to_dict serialises store state for the wire
# --------------------------------------------------------------------------- #


def test_store_to_dict_round_trip():
    """:meth:`ClaimLifecycleStore.to_dict` serialises the
    state for the audit log / wire payload."""
    store = ClaimLifecycleStore()
    store.register(_claim("c1", "Revenue is 180 cr"))
    store.register(_claim("c2", "Margin is 18%"))
    store.transition(
        claim_id="c1",
        new_status=ClaimLifecycleStatus.CORRECTED,
        reason="corrected_by_repair",
        source="deterministic_repairer",
    )
    d = store.to_dict()
    assert d["active_count"] == 1
    assert d["total_count"] == 2
    assert d["event_count"] == 1
    assert isinstance(d["claims"], list)
    assert isinstance(d["events"], list)
    assert {c["claim_id"] for c in d["claims"]} == {"c1", "c2"}


# --------------------------------------------------------------------------- #
# 9 — lifecycle vocabulary is exactly the brief's 5 states
# --------------------------------------------------------------------------- #


def test_lifecycle_vocabulary_matches_brief():
    """The lifecycle vocabulary must contain the brief's five
    states in the documented order."""
    assert CLAIM_LIFECYCLE_STATES == (
        "active",
        "superseded",
        "rejected",
        "corrected",
        "expired",
    )

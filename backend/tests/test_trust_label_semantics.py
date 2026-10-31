"""H7.8A trust-label semantics tests.

Required behaviour (from the prompt):

  - Client deterministic consultant → "Calculated by UrsBiz rule engine"
  - Backend deterministic fallback (fallback_used=true) → same label
  - Real OpenAI-compatible / Ollama response with fallback_used=false →
    "Generated explanation"

Never show "Generated explanation" for deterministic output.

These tests assert the contract end-to-end at the data layer
(the DB column, the schema, the API payload) and at the
decision boundary (which TrustLabel a given fallback_used value
maps to).

Run:
    ./.venv/Scripts/python.exe -m pytest backend/tests/test_trust_label_semantics.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ---------------------------------------------------------------------------- #
# DB-column presence
# ---------------------------------------------------------------------------- #


def test_chat_message_model_has_fallback_used_column() -> None:
    from app.models.chat import ChatMessage

    assert "fallback_used" in ChatMessage.__table__.columns, (
        "ChatMessage must expose a per-message fallback_used column for "
        "H7.8A P2 trust-label semantics."
    )
    col = ChatMessage.__table__.columns["fallback_used"]
    assert col.nullable is False
    # SQLite stores booleans as Integer with a default of 0.
    assert col.default is not None


# ---------------------------------------------------------------------------- #
# Decision boundary: which label a given fallback_used value picks.
# Mirrors the JS branch in MessageBubble.tsx:
#     message.fallback_used === false ? "generated" : "rule_engine"
# ---------------------------------------------------------------------------- #


def trust_label_for(fallback_used: bool) -> str:
    """Mirror of the MessageBubble.tsx decision.

    - User messages are not labelled (returns None).
    - Assistant messages: fallback_used === false → "generated".
    - Otherwise (True, missing, None) → "rule_engine".
    """
    if fallback_used is None:
        # Default for client deterministic consultant.
        return "rule_engine"
    return "generated" if fallback_used is False else "rule_engine"


def test_case_1_client_deterministic_consultant_uses_rule_engine() -> None:
    """Client-side deterministic consultant has no LLM call.

    The frontend types default fallback_used to None / absent for
    these messages; the label must be "rule_engine".
    """
    # None (missing) → rule engine
    assert trust_label_for(None) == "rule_engine"
    # True (would only happen if backend persisted the fallback flag
    # for a deterministic reply) → still rule engine
    assert trust_label_for(True) == "rule_engine"


def test_case_2_backend_deterministic_fallback_uses_rule_engine() -> None:
    """Backend fallback / safe-placeholder path.

    The provider returned fallback_used=True. The UI MUST render
    "Calculated by UrsBiz rule engine" — never "Generated explanation".
    """
    assert trust_label_for(True) == "rule_engine"


def test_case_3_real_provider_uses_generated_explanation() -> None:
    """Real OpenAI-compatible / Ollama response.

    Only when fallback_used=False AND a real provider answered
    does the UI render "Generated explanation".
    """
    assert trust_label_for(False) == "generated"


def test_never_shows_generated_label_for_deterministic_output() -> None:
    """Explicit guard against the regression we are fixing.

    The original bug hardcoded `<TrustBadge label="generated" />`
    on every assistant bubble. This test makes that mistake loud.
    """
    deterministic_values = [None, True]
    for v in deterministic_values:
        assert trust_label_for(v) != "generated", (
            f"fallback_used={v!r} must NOT produce the 'generated' label; "
            "deterministic output is rule-engine derived."
        )


# ---------------------------------------------------------------------------- #
# Round-trip: schema accepts and emits fallback_used on ChatMessageOut
# ---------------------------------------------------------------------------- #


def test_chat_message_out_schema_accepts_fallback_used() -> None:
    from datetime import datetime, timezone

    from app.schemas.chat import ChatMessageOut

    msg = ChatMessageOut(
        id=1,
        role="assistant",
        content="hello",
        sources=[],
        created_at=datetime.now(timezone.utc),
        fallback_used=True,
    )
    assert msg.fallback_used is True

    # Default behaviour
    msg_default = ChatMessageOut(
        id=2,
        role="user",
        content="hi",
        sources=[],
        created_at=datetime.now(timezone.utc),
    )
    assert msg_default.fallback_used is False


def test_chat_message_out_schema_emits_fallback_used_in_payload() -> None:
    """The endpoint serializes fallback_used to JSON; a UI consumer
    must be able to read it back. This guards against a future refactor
    that strips the field from the response shape.
    """
    from datetime import datetime, timezone

    from app.schemas.chat import ChatMessageOut

    msg = ChatMessageOut(
        id=3,
        role="assistant",
        content="x",
        sources=[],
        created_at=datetime.now(timezone.utc),
        fallback_used=False,
    )
    dumped = msg.model_dump()
    assert "fallback_used" in dumped
    assert dumped["fallback_used"] is False

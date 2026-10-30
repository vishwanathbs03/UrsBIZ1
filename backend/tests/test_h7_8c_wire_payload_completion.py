"""Regression tests for H7.8C — assistant response wire-payload completion.

The brief mandates that every assistant response carries the
following fields at the TOP level of the message payload:

  * provider
  * model
  * runtime_provider
  * grounding_score
  * evidence_references
  * assumptions
  * limitations
  * fallback_active
  * mode
  * confidence

The previous implementation only exposed these fields inside
``generation.*``, forcing the frontend to drill into the
envelope to render the trust disclosure. The H7.8C fix
flattens the envelope to the top level while preserving the
``generation`` block for backward compatibility.

The brief also mandates that the assistant response NEVER
exposes:

  * API keys
  * Authorization headers
  * Base URLs

The H7.8C fix adds a leak guard at the projection boundary
that asserts these fields are never present in the payload.

These tests assert:

  (1) ``ChatMessageOut`` schema declares every required top-level
      field with sane defaults.
  (2) The schema is exposed in the OpenAPI document under the
      expected component name.
  (3) ``_generation_meta_to_payload`` fills
      ``runtime_provider`` from ``provider`` when the
      dataclass omits it (deterministic fallback path).
  (4) ``_message_payload`` flattens every required field to
      the TOP level.
  (5) The leak guard raises ``ValueError`` if any secret-
      bearing field is ever present in the payload.
  (6) The existing ``generation`` block is preserved for
      backward compatibility.
  (7) Backward compatibility — old clients that only read
      ``id``, ``role``, ``content``, ``fallback_used`` still
      parse the response.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pytest


# --------------------------------------------------------------------------- #
# (1) Schema declares every required field
# --------------------------------------------------------------------------- #


REQUIRED_TOP_LEVEL_FIELDS = (
    "provider",
    "model",
    "runtime_provider",
    "grounding_score",
    "evidence_references",
    "assumptions",
    "limitations",
    "fallback_active",
    "mode",
    "confidence",
)


def _import_schema():
    """Lazy import so the test file errors cleanly if the schema changes."""
    from app.schemas.chat import ChatMessageOut
    return ChatMessageOut


@pytest.mark.parametrize("field_name", REQUIRED_TOP_LEVEL_FIELDS)
def test_chat_message_out_declares_required_top_level_field(field_name):
    """Every brief-mandated field is a first-class schema field."""
    schema = _import_schema()
    assert field_name in schema.model_fields, (
        f"ChatMessageOut missing required top-level field {field_name!r}; "
        f"declared fields: {list(schema.model_fields)}"
    )


def test_chat_message_out_preserves_generation_block_for_backward_compat():
    """The ``generation`` block is still present for any client that reads it."""
    schema = _import_schema()
    assert "generation" in schema.model_fields
    assert "fallback_used" in schema.model_fields


def test_chat_message_out_accepts_minimal_legacy_payload():
    """A legacy payload (no new fields) still parses."""
    schema = _import_schema()
    payload = {
        "id": 1,
        "role": "assistant",
        "kind": "",
        "content": "hello",
        "sources": [],
        "created_at": "2026-08-07T00:00:00Z",
        "fallback_used": False,
    }
    parsed = schema.model_validate(payload)
    assert parsed.id == 1
    # All new fields default to safe empties.
    assert parsed.provider == ""
    assert parsed.model == ""
    assert parsed.runtime_provider == ""
    assert parsed.grounding_score == 0
    assert parsed.evidence_references == []
    assert parsed.assumptions == []
    assert parsed.limitations == []
    assert parsed.fallback_active is False
    assert parsed.mode is None
    assert parsed.confidence is None


# --------------------------------------------------------------------------- #
# (2) OpenAPI component
# --------------------------------------------------------------------------- #


def test_openapi_documents_chat_message_out_with_new_fields():
    """The OpenAPI document exposes the new fields under the right schema name."""
    schema = _import_schema()
    # Build the JSON schema the way FastAPI / Pydantic emit it.
    json_schema = schema.model_json_schema()
    props = set(json_schema.get("properties", {}).keys())
    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        assert field_name in props, (
            f"OpenAPI schema for ChatMessageOut missing {field_name!r}; "
            f"declared properties: {sorted(props)}"
        )


# --------------------------------------------------------------------------- #
# (3) GenerationMeta projector fills runtime_provider
# --------------------------------------------------------------------------- #


def test_generation_meta_to_payload_fills_runtime_provider_from_provider():
    """When the dataclass omits runtime_provider, the projector defaults it."""
    from app.services.ai.providers.base import GenerationMeta
    from app.services.chat.conversation_service import _generation_meta_to_payload

    meta = GenerationMeta(
        provider="deterministic-fallback",
        model="deterministic-fallback",
        mode="grounded",
        fallback_used=True,
        fallback_reason="not_configured",
        generation_method="deterministic",
        schema_validated=True,
        grounding_validated=True,
        server_grounding_score=100,
        evidence_count=22,
        confidence=72,
        assumptions=("Read from profile",),
        limitations=("No roadmap engine",),
        evidence_references=("biz_profile_revenue",),
        generated_at="2026-08-07T07:00:00Z",
        prompt_truncated=False,
        provider_latency_ms=None,
        grounded_payload=None,
        business_evidence_validated=True,
        context_manifest=None,
        # runtime_provider omitted on purpose
    )
    payload = _generation_meta_to_payload(meta)
    assert payload is not None
    assert payload["runtime_provider"] == "deterministic-fallback"
    assert payload["provider"] == "deterministic-fallback"


def test_generation_meta_to_payload_preserves_explicit_runtime_provider():
    """When the dataclass sets runtime_provider, that value wins."""
    from app.services.ai.providers.base import GenerationMeta
    from app.services.chat.conversation_service import _generation_meta_to_payload

    meta = GenerationMeta(
        provider="openai_compatible",
        model="gemini-1.5-flash",
        mode="grounded",
        fallback_used=False,
        fallback_reason=None,
        generation_method="generative",
        schema_validated=True,
        grounding_validated=True,
        server_grounding_score=85,
        evidence_count=15,
        confidence=80,
        assumptions=(),
        limitations=(),
        evidence_references=(),
        generated_at="2026-08-07T07:00:00Z",
        prompt_truncated=False,
        provider_latency_ms=1200,
        grounded_payload=None,
        business_evidence_validated=True,
        context_manifest=None,
        runtime_provider="openai_compatible",
    )
    payload = _generation_meta_to_payload(meta)
    assert payload["runtime_provider"] == "openai_compatible"


# --------------------------------------------------------------------------- #
# (4) _message_payload flattens every required field
# --------------------------------------------------------------------------- #


class _StubMessage:
    """Minimal SQLAlchemy-shaped stub for _message_payload."""

    def __init__(
        self,
        *,
        generation_meta: dict | None = None,
        fallback_used: bool = True,
    ) -> None:
        self.id = 1
        self.role = "assistant"
        self.kind = ""
        self.content = "stub body"
        self.created_at = datetime(2026, 8, 7, 7, 0, 0)
        self.fallback_used = bool(fallback_used)
        self.generation_meta_json = (
            json.dumps(generation_meta) if generation_meta else ""
        )
        self.sources_json = "[]"


def _stub_message(
    *,
    generation_meta: dict | None = None,
    fallback_used: bool = True,
) -> _StubMessage:
    """Build a minimal SQLAlchemy-shaped stub for _message_payload."""
    return _StubMessage(
        generation_meta=generation_meta,
        fallback_used=fallback_used,
    )


def test_message_payload_flattens_generation_to_top_level():
    """Every brief-mandated field is present on the top-level payload."""
    from app.services.chat.conversation_service import _message_payload

    generation = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "not_configured",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 22,
        "confidence": 72,
        "assumptions": ["Read from profile"],
        "limitations": ["No roadmap engine"],
        "evidence_references": ["biz_profile_revenue", "rec_x"],
        "generated_at": "2026-08-07T07:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "grounded_payload": None,
        "business_evidence_validated": True,
        "context_manifest": None,
        "runtime_provider": "deterministic-fallback",
    }
    payload = _message_payload(_stub_message(generation_meta=generation))
    assert payload["provider"] == "deterministic-fallback"
    assert payload["model"] == "deterministic-fallback"
    assert payload["runtime_provider"] == "deterministic-fallback"
    assert payload["grounding_score"] == 100
    assert payload["evidence_references"] == ["biz_profile_revenue", "rec_x"]
    assert payload["assumptions"] == ["Read from profile"]
    assert payload["limitations"] == ["No roadmap engine"]
    assert payload["fallback_active"] is True
    assert payload["mode"] == "grounded"
    assert payload["confidence"] == 72
    # The generation block is preserved for backward compat.
    assert payload["generation"] == generation


def test_message_payload_handles_missing_generation_meta():
    """Rows without ``generation_meta_json`` return safe defaults."""
    from app.services.chat.conversation_service import _message_payload

    payload = _message_payload(_stub_message(generation_meta=None))
    assert payload["provider"] == ""
    assert payload["model"] == ""
    assert payload["runtime_provider"] == ""
    assert payload["grounding_score"] == 0
    assert payload["evidence_references"] == []
    assert payload["assumptions"] == []
    assert payload["limitations"] == []
    assert payload["fallback_active"] is True  # from fallback_used
    assert payload["mode"] is None
    assert payload["confidence"] is None
    assert payload["generation"] is None


def test_message_payload_fallback_active_mirrors_fallback_used():
    """The brief-mandated ``fallback_active`` equals ``fallback_used``."""
    from app.services.chat.conversation_service import _message_payload

    payload_no_fb = _message_payload(
        _stub_message(generation_meta=None, fallback_used=False)
    )
    assert payload_no_fb["fallback_used"] is False
    assert payload_no_fb["fallback_active"] is False

    payload_fb = _message_payload(
        _stub_message(generation_meta=None, fallback_used=True)
    )
    assert payload_fb["fallback_used"] is True
    assert payload_fb["fallback_active"] is True


def test_message_payload_defaults_runtime_provider_when_missing_in_generation():
    """If the persisted generation lacks runtime_provider, top-level mirrors
    fall back to ``provider`` so the field is always present."""
    from app.services.chat.conversation_service import _message_payload

    generation = {
        "provider": "openai_compatible",
        "model": "gemini-1.5-flash",
        "mode": "grounded",
        "fallback_used": False,
        "fallback_reason": None,
        "generation_method": "generative",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 85,
        "evidence_count": 15,
        "confidence": 80,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-08-07T07:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": 1200,
        "grounded_payload": None,
        "business_evidence_validated": True,
        "context_manifest": None,
        # runtime_provider omitted on purpose
    }
    payload = _message_payload(_stub_message(generation_meta=generation))
    assert payload["runtime_provider"] == "openai_compatible"


# --------------------------------------------------------------------------- #
# (5) Leak guard
# --------------------------------------------------------------------------- #


def test_leak_guard_raises_on_api_key():
    """The leak guard raises ValueError when api_key is in the payload."""
    from app.services.chat.conversation_service import _assert_no_leaked_secrets

    with pytest.raises(ValueError, match="api_key"):
        _assert_no_leaked_secrets(
            {"api_key": "sk-secret", "provider": "x"},
            where="test",
        )


def test_leak_guard_raises_on_authorization():
    """The leak guard raises ValueError when authorization is in the payload."""
    from app.services.chat.conversation_service import _assert_no_leaked_secrets

    with pytest.raises(ValueError, match="authorization"):
        _assert_no_leaked_secrets(
            {"authorization": "Bearer sk-secret", "provider": "x"},
            where="test",
        )


def test_leak_guard_raises_on_base_url():
    """The leak guard raises ValueError when base_url is in the payload."""
    from app.services.chat.conversation_service import _assert_no_leaked_secrets

    with pytest.raises(ValueError, match="base_url"):
        _assert_no_leaked_secrets(
            {"base_url": "https://generativelanguage.googleapis.com", "provider": "x"},
            where="test",
        )


def test_leak_guard_passes_on_clean_payload():
    """The leak guard is a no-op on safe payloads."""
    from app.services.chat.conversation_service import _assert_no_leaked_secrets

    _assert_no_leaked_secrets(
        {"provider": "x", "model": "y", "fallback_used": True},
        where="test",
    )
    _assert_no_leaked_secrets(None, where="test")
    _assert_no_leaked_secrets({}, where="test")


def test_leak_guard_catches_substring_collision():
    """Fields that *contain* a leaked name (e.g. ``fake_api_key``) are NOT
    flagged — the guard matches exact field names, not substrings. This
    documents the intended precision."""
    from app.services.chat.conversation_service import _assert_no_leaked_secrets

    # These should NOT raise — the field name is a different identifier.
    _assert_no_leaked_secrets(
        {"fake_api_key": "x", "authorization_level": "high"},
        where="test",
    )


# --------------------------------------------------------------------------- #
# (6) Real provider / fallback path discriminated
# --------------------------------------------------------------------------- #


def test_real_provider_payload_carries_runtime_provider_unchanged():
    """A real-provider response keeps the configured + runtime provider name."""
    from app.services.chat.conversation_service import _message_payload

    generation = {
        "provider": "openai_compatible",
        "model": "gemini-1.5-flash",
        "runtime_provider": "openai_compatible",
        "mode": "grounded",
        "fallback_used": False,
        "fallback_reason": None,
        "generation_method": "generative",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 88,
        "evidence_count": 12,
        "confidence": 81,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-08-07T07:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": 1500,
        "grounded_payload": None,
        "business_evidence_validated": True,
        "context_manifest": None,
    }
    payload = _message_payload(
        _stub_message(generation_meta=generation, fallback_used=False)
    )
    assert payload["provider"] == "openai_compatible"
    assert payload["runtime_provider"] == "openai_compatible"
    assert payload["model"] == "gemini-1.5-flash"
    assert payload["fallback_used"] is False
    assert payload["fallback_active"] is False
    assert payload["grounding_score"] == 88
    assert payload["confidence"] == 81


def test_deterministic_fallback_payload_routes_runtime_provider_to_fallback():
    """A fallback response uses ``deterministic-fallback`` as runtime provider."""
    from app.services.chat.conversation_service import _message_payload

    generation = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "runtime_provider": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "not_configured",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 22,
        "confidence": 72,
        "assumptions": ["Read from profile"],
        "limitations": [],
        "evidence_references": ["biz_profile_revenue"],
        "generated_at": "2026-08-07T07:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "grounded_payload": None,
        "business_evidence_validated": True,
        "context_manifest": None,
    }
    payload = _message_payload(_stub_message(generation_meta=generation))
    assert payload["provider"] == "deterministic-fallback"
    assert payload["runtime_provider"] == "deterministic-fallback"
    assert payload["fallback_used"] is True
    assert payload["fallback_active"] is True
    assert payload["grounding_score"] == 100

"""Sprint AI-14 — regression wire tests.

These tests guard against the AI-14 schema additions breaking
pre-AI-14 rows + frontend clients.

Covered:
  * ``GenerationMeta.empty(**kwargs)`` constructs with all 6
    AI-14 fields default-safe (None / [] / 0).
  * ``GenerationMeta.from_dict(...)`` round-trips the 6 AI-14
    fields without raising on legacy payloads (rows that omit
    the new keys).
  * ``ChatGenerationMeta`` Pydantic model accepts the 6 new
    AI-14 fields and ignores their absence on legacy payloads.
  * ``ChatMessageOut`` mirrors the 2 top-level AI-14 fields.
  * Wire shape (``to_dict``) returns JSON-safe values (lists,
    not tuples) for the AI-14 fields.
"""

from __future__ import annotations

from app.services.ai.providers.base import GenerationMeta
from app.schemas.chat import (
    ChatGenerationMeta,
    ChatMessageOut,
)


def _legacy_kwargs():
    """Mimic the AI-13 era — every AI-14 key is missing."""
    return dict(
        provider="deterministic-fallback",
        model="deterministic-fallback",
        mode="grounded",
        fallback_used=True,
        fallback_reason="not_configured",
        generation_method="deterministic",
        schema_validated=True,
        grounding_validated=True,
        server_grounding_score=100,
        evidence_count=0,
        confidence=100,
        assumptions=(),
        limitations=(),
        evidence_references=(),
        generated_at="2026-08-12T00:00:00Z",
        prompt_truncated=False,
        provider_latency_ms=None,
        grounded_payload=None,
    )


def test_generation_meta_empty_default_safe():
    """The 6 AI-14 fields default-safe in GenerationMeta.empty()."""
    m = GenerationMeta.empty(
        mode="grounded",
        provider_used="fb",
        model="fb",
        provider_latency_ms=None,
        fallback_used=True,
    )
    assert m.answer_requirements is None
    assert m.evidence_graph is None
    assert m.calculation_lineage == []
    assert m.missing_data_state is None
    assert m.unsupported_claim_count == 0
    assert m.fabricated_source_count == 0


def test_generation_meta_from_dict_legacy_row():
    """Pre-AI-14 wire payloads deserialize without raising."""
    legacy = _legacy_kwargs()
    m = GenerationMeta.from_dict(legacy)
    assert m.provider == "deterministic-fallback"
    assert m.answer_requirements is None
    assert m.evidence_graph is None
    assert m.calculation_lineage == []
    assert m.missing_data_state is None
    assert m.unsupported_claim_count == 0
    assert m.fabricated_source_count == 0


def test_generation_meta_round_trip_ai14_fields():
    """All 6 AI-14 fields survive to_dict / from_dict round-trip."""
    payload = _legacy_kwargs()
    payload.update(
        answer_requirements={"needs_direct_answer": True},
        evidence_graph={"nodes": [], "claims": [], "edges": []},
        calculation_lineage=[{"calculation_id": "c1"}],
        missing_data_state={"known": [], "unknown": []},
        unsupported_claim_count=2,
        fabricated_source_count=1,
    )
    m = GenerationMeta.from_dict(payload)
    assert m.answer_requirements == {"needs_direct_answer": True}
    assert isinstance(m.evidence_graph, dict)
    assert isinstance(m.calculation_lineage, list)
    assert m.calculation_lineage == [{"calculation_id": "c1"}]
    assert m.missing_data_state == {"known": [], "unknown": []}
    assert m.unsupported_claim_count == 2
    assert m.fabricated_source_count == 1
    # Round-trip back to dict.
    out = m.to_dict()
    assert out["answer_requirements"] == {"needs_direct_answer": True}
    assert out["calculation_lineage"] == [{"calculation_id": "c1"}]
    assert out["unsupported_claim_count"] == 2


def test_generation_meta_from_dict_coerces_list_to_list():
    """calculation_lineage stays a list even when supplied as tuple."""
    payload = _legacy_kwargs()
    payload["calculation_lineage"] = ({"calculation_id": "x"},)
    m = GenerationMeta.from_dict(payload)
    assert isinstance(m.calculation_lineage, list)


def test_generation_meta_from_dict_int_coercion():
    """unsupported_claim_count + fabricated_source_count coerce from float."""
    payload = _legacy_kwargs()
    payload["unsupported_claim_count"] = "3"
    payload["fabricated_source_count"] = 1.7
    m = GenerationMeta.from_dict(payload)
    assert m.unsupported_claim_count == 3
    assert m.fabricated_source_count == 1  # int(float) truncates


def test_chat_generation_meta_legacy_payload():
    """ChatGenerationMeta accepts a pre-AI-14 payload."""
    legacy = {
        "provider": "fb",
        "model": "fb",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "not_configured",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": 100,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-08-12T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
    }
    g = ChatGenerationMeta(**legacy)
    assert g.answer_requirements is None
    assert g.evidence_graph is None
    assert g.calculation_lineage == []
    assert g.missing_data_state is None
    assert g.unsupported_claim_count == 0
    assert g.fabricated_source_count == 0


def test_chat_generation_meta_ai14_payload():
    """ChatGenerationMeta accepts the 6 AI-14 fields when present."""
    legacy = {
        "provider": "fb",
        "model": "fb",
        "mode": "grounded",
        "fallback_used": False,
        "fallback_reason": None,
        "generation_method": "generative",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": 90,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-08-12T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": 120,
    }
    legacy.update(
        answer_requirements={"needs_direct_answer": True},
        evidence_graph={"claims": [{"claim_id": "c1"}]},
        calculation_lineage=[{"calculation_id": "c1"}],
        missing_data_state={"known": [], "unknown": []},
        unsupported_claim_count=1,
        fabricated_source_count=0,
    )
    g = ChatGenerationMeta(**legacy)
    assert g.answer_requirements == {"needs_direct_answer": True}
    assert g.evidence_graph == {"claims": [{"claim_id": "c1"}]}
    assert g.unsupported_claim_count == 1


def test_chat_message_out_top_level_mirrors():
    """ChatMessageOut mirrors answer_requirements + evidence_graph at top level."""
    # Just construct + read; full validation belongs to the API layer.
    fields = ChatMessageOut.model_fields
    assert "answer_requirements" in fields
    assert "evidence_graph" in fields
    # Both default to None on a legacy payload.
    legacy_min = {
        "id": 1,
        "role": "assistant",
        "content": "hello",
        "created_at": "2026-08-12T00:00:00Z",
        "sources": [],
        "generation": None,
    }
    m = ChatMessageOut(**legacy_min)
    assert m.answer_requirements is None
    assert m.evidence_graph is None
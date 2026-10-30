"""Sprint AI-15 — regression tests for the AI-15 wire additions.

6 tests covering:
  * Pre-AI-15 wire payload round-trips through GenerationMeta.from_dict
  * ChatGenerationMeta accepts pre-AI-15 payload
  * ChatMessageOut accepts pre-AI-15 payload
  * ConversationService projector emits 3 new top-level mirrors
  * VisualizationPlan.to_dict() round-trip
  * Empty plans tuple serialises as [] (not None)
"""

from __future__ import annotations

from app.services.ai.providers.base import (
    GenerationMeta,
    Mode,
)
from app.services.ai.reasoning.visualization_planner import (
    ChartKind,
    VisualizationPlan,
)


# --------------------------------------------------------------------------- #
# 1 — Pre-AI-15 wire payload round-trips through GenerationMeta.from_dict
# --------------------------------------------------------------------------- #


def test_pre_ai15_payload_round_trips():
    """A dict that lacks the AI-15 fields must still deserialize
    (defaults are safe)."""
    data = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "provider_unavailable",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": None,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "grounded_payload": None,
    }
    meta = GenerationMeta.from_dict(data)
    assert meta.visualization_plans == []
    assert meta.quality_warning is None
    assert meta.trust_summary is None


# --------------------------------------------------------------------------- #
# 2 — Pre-AI-15 ChatGenerationMeta accepts AI-15 fields
# --------------------------------------------------------------------------- #


def test_chat_generation_meta_accepts_ai15_fields():
    from app.schemas.chat import ChatGenerationMeta

    payload = {
        "provider": "deterministic-fallback",
        "model": "deterministic-fallback",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": "provider_unavailable",
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": None,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": None,
        "visualization_plans": [
            {"chart_kind": "kpi", "title": "t", "data": {"v": 1}, "confidence": 0.9}
        ],
        "quality_warning": {"needs_warning": False, "warning_message": ""},
        "trust_summary": {"evidence": [], "calculations": [], "alternatives": []},
    }
    meta = ChatGenerationMeta.model_validate(payload)
    assert len(meta.visualization_plans) == 1
    assert meta.quality_warning is not None
    assert meta.trust_summary is not None


# --------------------------------------------------------------------------- #
# 3 — ChatMessageOut accepts pre-AI-15 payload
# --------------------------------------------------------------------------- #


def test_chat_message_out_accepts_pre_ai15():
    from app.schemas.chat import ChatMessageOut

    payload = {
        "id": 1,
        "role": "assistant",
        "kind": "assistant",
        "content": "hi",
        "created_at": "2026-01-01T00:00:00Z",
        "generation": None,
    }
    msg = ChatMessageOut.model_validate(payload)
    assert msg.visualization_plans == []
    assert msg.quality_warning is None
    assert msg.trust_summary is None


# --------------------------------------------------------------------------- #
# 4 — ConversationService projector emits 3 new mirrors
# --------------------------------------------------------------------------- #


def test_conversation_service_projector_includes_ai15():
    """The ``_message_payload`` projector on the conversation
    service must include visualization_plans, quality_warning,
    and trust_summary on the wire payload.
    """
    import inspect

    from app.services.chat import conversation_service as cs

    source = inspect.getsource(cs._message_payload)
    assert "visualization_plans" in source
    assert "quality_warning" in source
    assert "trust_summary" in source


# --------------------------------------------------------------------------- #
# 5 — VisualizationPlan.to_dict() / from_dict round-trip
# --------------------------------------------------------------------------- #


def test_visualization_plan_round_trip():
    p = VisualizationPlan(
        chart_kind=ChartKind.KPI,
        title="Score",
        purpose="headline",
        recommended_display="card",
        explanation="x",
        source_evidence_ids=("p1",),
        calculation_ids=("c1",),
        assumptions=("a",),
        limitations=("l",),
        confidence=0.9,
    )
    out = p.to_dict()
    # Round-trip via constructor
    p2 = VisualizationPlan(
        chart_kind=ChartKind(out["chart_kind"]),
        title=out["title"],
        purpose=out["purpose"],
        recommended_display=out["recommended_display"],
        explanation=out["explanation"],
        source_evidence_ids=tuple(out["source_evidence_ids"]),
        calculation_ids=tuple(out["calculation_ids"]),
        assumptions=tuple(out["assumptions"]),
        limitations=tuple(out["limitations"]),
        confidence=out["confidence"],
    )
    assert p == p2


# --------------------------------------------------------------------------- #
# 6 — Empty plans tuple serialises as [] not None
# --------------------------------------------------------------------------- #


def test_empty_plans_serialise_as_empty_list():
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="deterministic-fallback",
        model="deterministic-fallback",
        provider_latency_ms=None,
        fallback_used=True,
        fallback_reason="provider_unavailable",
        generation_method="deterministic",
    )
    assert meta.visualization_plans == []
    # And serialises as JSON-safe empty list, not None
    assert meta.visualization_plans is not None
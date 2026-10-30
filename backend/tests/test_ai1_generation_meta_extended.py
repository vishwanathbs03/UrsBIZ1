"""Test suite for SPRINT AI-1 — Stage 9: GenerationMeta + wire schema extensions."""

import pytest

from app.services.ai.providers.base import GenerationMeta
from app.schemas.chat import ChatGenerationMeta, ChatMessageOut


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. GenerationMeta accepts the five new AI-1 fields
# --------------------------------------------------------------------------- #


def test_1_generation_meta_ai1_fields_default_empty():
    """Without AI-1 fields, the new defaults are empty safe values."""
    meta = GenerationMeta(
        provider="openai_compatible",
        model="gpt-4o",
        mode="grounded",
        fallback_used=False,
        fallback_reason=None,
        generation_method="generative",
        schema_validated=True,
        grounding_validated=True,
        server_grounding_score=85,
        evidence_count=10,
        confidence=80,
        assumptions=(),
        limitations=(),
        evidence_references=(),
        generated_at=_now(),
        prompt_truncated=False,
        provider_latency_ms=300,
        grounded_payload=None,
    )
    assert meta.deterministic_services_used == ()
    assert meta.calculations_used == ()
    assert meta.question_understanding is None
    assert meta.tool_calls == ()
    assert meta.claim_categories_used == ()


def test_2_generation_meta_empty_factory_accepts_ai1_kwargs():
    """GenerationMeta.empty() forwards the AI-1 kwargs into the instance."""
    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="ollama",
        model="llama3.1",
        provider_latency_ms=500,
        fallback_used=False,
        deterministic_services_used=("health_score", "schemes_sprint16"),
        calculations_used=("gap_math",),
        question_understanding={"topic": "finance", "complexity": "strategic"},
        tool_calls=({"service_name": "health_score"},),
        claim_categories_used=("FACT", "RECOMMENDATION"),
    )
    assert meta.deterministic_services_used == ("health_score", "schemes_sprint16")
    assert meta.calculations_used == ("gap_math",)
    assert meta.question_understanding == {"topic": "finance", "complexity": "strategic"}
    assert meta.tool_calls == ({"service_name": "health_score"},)
    assert meta.claim_categories_used == ("FACT", "RECOMMENDATION")


def test_3_generation_meta_from_dict_round_trips_ai1_fields():
    """GenerationMeta.from_dict reconstructs the AI-1 fields from a dict."""
    src = GenerationMeta(
        provider="openai_compatible",
        model="gpt-4o",
        mode="grounded",
        fallback_used=False,
        fallback_reason=None,
        generation_method="generative",
        schema_validated=True,
        grounding_validated=True,
        server_grounding_score=85,
        evidence_count=10,
        confidence=80,
        assumptions=("a",),
        limitations=("l",),
        evidence_references=("rec_x",),
        generated_at=_now(),
        prompt_truncated=False,
        provider_latency_ms=300,
        grounded_payload=None,
        deterministic_services_used=("health_score",),
        calculations_used=(),
        question_understanding={"topic": "strategy"},
        tool_calls=(),
        claim_categories_used=("FACT",),
    )
    rebuilt = GenerationMeta.from_dict(src.to_dict())
    assert rebuilt.deterministic_services_used == ("health_score",)
    assert rebuilt.question_understanding == {"topic": "strategy"}
    assert rebuilt.claim_categories_used == ("FACT",)


# --------------------------------------------------------------------------- #
# 4. ChatGenerationMeta wire schema carries the AI-1 fields
# --------------------------------------------------------------------------- #


def test_4_chat_generation_meta_carries_ai1_fields():
    """The wire mirror declares the AI-1 fields with list defaults."""
    meta = ChatGenerationMeta(
        provider="ollama",
        model="llama3.1",
        generated_at=_now(),
        generation_method="generative",
        fallback_used=False,
        deterministic_services_used=["health_score"],
        calculations_used=["gap_math"],
        question_understanding={"topic": "finance"},
        tool_calls=[{"service_name": "health_score"}],
        claim_categories_used=["FACT", "INFERENCE"],
    )
    assert meta.deterministic_services_used == ["health_score"]
    assert meta.calculations_used == ["gap_math"]
    assert meta.question_understanding == {"topic": "finance"}
    assert meta.tool_calls == [{"service_name": "health_score"}]
    assert meta.claim_categories_used == ["FACT", "INFERENCE"]


def test_5_chat_generation_meta_rejects_unknown_field():
    """``extra='forbid'`` is preserved — an unknown field returns a validation error."""
    with pytest.raises(Exception):
        ChatGenerationMeta(
            provider="ollama",
            model="llama3.1",
            generated_at=_now(),
            generation_method="generative",
            fallback_used=False,
            this_field_is_unknown=True,  # type: ignore[call-arg]
        )


# --------------------------------------------------------------------------- #
# 6. ChatMessageOut top-level mirrors
# --------------------------------------------------------------------------- #


def test_6_chat_message_out_top_level_ai1_mirrors():
    """The ChatMessageOut top-level mirrors the generation AI-1 fields."""
    from datetime import datetime, timezone

    msg = ChatMessageOut(
        id=1,
        role="assistant",
        content="Answer body.",
        created_at=datetime.now(tz=timezone.utc),
        provider="ollama",
        model="llama3.1",
        deterministic_services_used=["health_score", "schemes_sprint16"],
        calculations_used=["gap_math"],
        question_understanding={"topic": "strategy", "complexity": "strategic"},
        tool_calls=[{"service_name": "health_score"}],
        claim_categories_used=["FACT", "RECOMMENDATION"],
    )
    assert msg.deterministic_services_used == ["health_score", "schemes_sprint16"]
    assert msg.calculations_used == ["gap_math"]
    assert msg.question_understanding == {"topic": "strategy", "complexity": "strategic"}
    assert msg.tool_calls == [{"service_name": "health_score"}]
    assert msg.claim_categories_used == ["FACT", "RECOMMENDATION"]
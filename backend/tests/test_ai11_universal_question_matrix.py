"""SPRINT AI-11 — Universal Business-Aware Assistant — test matrix.

Locks down the ``QuestionUnderstanding`` capability +
``business_dependency`` derivation across the 15+ question
categories the hardening brief enumerates, plus the universal
non-rejection contract (no flagship-intent required), and the
wire projection onto ``GenerationMeta`` /
``ChatGenerationMeta`` / ``ChatMessageOut``.

These tests are acceptance criteria. If any of these fail,
the assistant can no longer claim to be a universal
business-aware AI assistant — it has regressed to the
flagship-intent gate that AI-1 broke through.
"""
from __future__ import annotations

import json
import os

import pytest


# --------------------------------------------------------------------------- #
# 1. Capability detection — the 15+ question categories from the brief.
# --------------------------------------------------------------------------- #


_CAPABILITY_FIXTURES: list[tuple[str, str, str]] = [
    # (prompt, expected_capability_token, expected_business_dependency)
    # GENERAL_KNOWLEDGE — pure concept question, no business marker.
    (
        "What is EBITDA?",
        "GENERAL_KNOWLEDGE",
        "none",
    ),
    # BUSINESS_FACT — facts about the user's own business.
    (
        "How many employees do I have?",
        "BUSINESS_FACT",
        "required",
    ),
    # BUSINESS_ANALYSIS — analysis of the user's own state.
    (
        "Why is my business health score only 68?",
        "BUSINESS_ANALYSIS",
        "required",
    ),
    # CALCULATION — explicit arithmetic request.
    (
        "What is my revenue growth percentage?",
        "CALCULATION",
        "required",
    ),
    # RECOMMENDATION — recommendation language ("how can i").
    (
        "How can I reduce my biggest business risk?",
        "RECOMMENDATION",
        "required",
    ),
    # SCENARIO — "what happens if" framing.
    (
        "What happens if my supplier concentration falls from 75% to 40%?",
        "SCENARIO",
        "required",
    ),
    # FORECAST — projection language.
    (
        "What is my projected revenue next year if I grow at 20%?",
        "FORECAST",
        "required",
    ),
    # COMPARISON — vs / compare language.
    (
        "Compare my gross margin to the industry average.",
        "COMPARISON",
        "required",
    ),
    # FINANCIAL — finance topic without explicit arithmetic.
    (
        "Should I take a working capital loan or stretch my payables?",
        "FINANCIAL",
        "required",
    ),
    # OPERATIONAL — operations topic, directive phrasing.
    (
        "How should I reorganize my inventory storage?",
        "OPERATIONAL",
        "required",
    ),
    # RISK — risk topic.
    (
        "What is my biggest business risk right now?",
        "RISK",
        "required",
    ),
    # GOVERNMENT_SCHEME — explicit scheme keyword.
    (
        "Are there schemes that can help me buy machinery?",
        "GOVERNMENT_SCHEME",
        "required",
    ),
    # EXPORT — export topic (mixes GENERAL_KNOWLEDGE + RECOMMENDATION
    # + BUSINESS_ANALYSIS too — the multi-label rollup is the point).
    (
        "How do I expand into the UAE market for textiles?",
        "BUSINESS_ANALYSIS",
        "required",
    ),
    # ROADMAP — 12-month roadmap / playbook language.
    (
        "Give me a 12-month roadmap to reach ₹3 Cr turnover.",
        "ROADMAP",
        "required",
    ),
    # EXTERNAL_INFORMATION — industry / common-ways phrasing.
    (
        "What are common ways textile companies handle FX risk?",
        "EXTERNAL_INFORMATION",
        "optional",
    ),
    # MIXED — explanation + business-context combo.
    (
        "Explain working capital and tell me whether it is a problem for my business.",
        "FINANCIAL",
        "required",
    ),
    # Recommendation + roadmap (DEFAULT to behaviour).
    (
        "Where should I focus next month?",
        "RECOMMENDATION",
        "required",
    ),
]


@pytest.mark.parametrize("prompt, expected_cap, expected_dep", _CAPABILITY_FIXTURES)
def test_capability_and_business_dependency(prompt, expected_cap, expected_dep):
    """Every brief §4/§5 fixture classifies to its expected slot.

    The matrix uses SUBSET semantics — the expected capability
    token must appear in the multi-label tuple. The heuristic
    can over-fire (e.g. "msme" → GOVERNMENT_SCHEME), and that
    over-firing is intentional; the matrix locks down the
    primary capability token so a regression in the topic /
    overlay heuristic surfaces immediately.
    """
    from app.services.ai.reasoning.question_understanding import (
        understand_question,
    )

    qu = understand_question(prompt, context=None)

    assert qu.capability, f"empty capability tuple for prompt={prompt!r}"
    assert expected_cap in qu.capability, (
        f"missing {expected_cap!r} in capability {qu.capability!r} "
        f"for prompt={prompt!r}"
    )
    # The dependency literal must be one of the allowed 3-valued set.
    assert qu.business_dependency in {"none", "optional", "required"}, (
        f"unknown business_dependency value {qu.business_dependency!r} "
        f"for prompt={prompt!r}"
    )
    # Dependency expectations are strict — the matrix locks them down
    # so a future heuristic change breaks the test (visible regression).
    assert qu.business_dependency == expected_dep, (
        f"expected dependency {expected_dep!r} got {qu.business_dependency!r} "
        f"for prompt={prompt!r}"
    )


# --------------------------------------------------------------------------- #
# 2. Universal non-rejection contract — no flagship intent required.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "prompt",
    [
        "What is working capital?",  # non-flagship concept question
        "Are there subsidies for compostable packaging?",  # non-flagship scheme
        "Should I hire two contract workers?",  # non-flagship directive
        "Explain the difference between gross margin and net margin.",
        "What is a SWOT analysis for my business?",
        "How do I track GST filing deadlines?",
        "Recommend a pricing strategy for a boutique saree brand.",
        "What is the FX risk if I export to the US?",
        "Tell me about Udyam registration.",  # govt scheme, not flagship
        "How do I compute runway in months?",
        "xyz",  # gibberish — must NOT raise
        "",  # empty — must NOT raise
        "    ",  # whitespace — must NOT raise
    ],
)
def test_no_question_rejection(prompt):
    """No prompt is rejected because it is not one of the six flagship intents.

    Acceptance criterion §19 of the hardening brief. The
    ``understand_question`` function MUST return a fully-typed
    :class:`QuestionUnderstanding` for every input — including
    empty / whitespace / gibberish — and ``GenerationMeta.empty()``
    MUST accept the resulting capability / dependency without
    crashing.
    """
    from app.services.ai.providers.base import GenerationMeta
    from app.services.ai.reasoning.question_understanding import (
        understand_question,
    )

    qu = understand_question(prompt, context=None)

    assert isinstance(qu.capability, tuple)
    assert qu.business_dependency in {"none", "optional", "required"}
    assert qu.parsed_at  # always stamped

    # The capability tuple MUST always contain at least one
    # allowed value (even if it's UNKNOWN). This guarantees the
    # renderer always has a trust label.
    _ALLOWED = {
        "GENERAL_KNOWLEDGE", "BUSINESS_FACT", "BUSINESS_ANALYSIS",
        "CALCULATION", "RECOMMENDATION", "SCENARIO", "FORECAST",
        "COMPARISON", "FINANCIAL", "OPERATIONAL", "RISK",
        "GOVERNMENT_SCHEME", "EXPORT", "ROADMAP",
        "EXTERNAL_INFORMATION", "MIXED", "UNKNOWN",
    }
    for cap in qu.capability:
        assert cap in _ALLOWED, f"unknown capability {cap!r}"

    # ``GenerationMeta.empty()`` MUST accept the result without crashing.
    gen = GenerationMeta.empty(
        mode="open",
        provider_used="test",
        model="test",
        provider_latency_ms=0,
        fallback_used=False,
        capability=list(qu.capability),
        business_dependency=qu.business_dependency,
    )
    assert tuple(gen.capability) == tuple(qu.capability)
    assert gen.business_dependency == qu.business_dependency


# --------------------------------------------------------------------------- #
# 3. Wire projection — GenerationMeta + ChatMessageOut round-trip.
# --------------------------------------------------------------------------- #


def test_generation_meta_round_trip():
    """GenerationMeta(empty) → to_dict → from_dict preserves capability + dep."""
    from app.services.ai.providers.base import GenerationMeta

    meta = GenerationMeta.empty(
        mode="grounded",
        provider_used="x",
        model="x",
        provider_latency_ms=0,
        fallback_used=False,
        capability=["RECOMMENDATION", "MIXED"],
        business_dependency="optional",
    )
    serialised = {
        "provider": meta.provider,
        "model": meta.model,
        "mode": meta.mode,
        "fallback_used": meta.fallback_used,
        "fallback_reason": meta.fallback_reason,
        "generation_method": meta.generation_method,
        "schema_validated": meta.schema_validated,
        "grounding_validated": meta.grounding_validated,
        "server_grounding_score": meta.server_grounding_score,
        "evidence_count": meta.evidence_count,
        "confidence": meta.confidence,
        "assumptions": list(meta.assumptions),
        "limitations": list(meta.limitations),
        "evidence_references": list(meta.evidence_references),
        "generated_at": meta.generated_at,
        "prompt_truncated": meta.prompt_truncated,
        "provider_latency_ms": meta.provider_latency_ms,
        "grounded_payload": meta.grounded_payload,
        "business_evidence_validated": meta.business_evidence_validated,
        "context_manifest": meta.context_manifest,
        "deterministic_services_used": list(meta.deterministic_services_used),
        "calculations_used": list(meta.calculations_used),
        "question_understanding": meta.question_understanding,
        "tool_calls": list(meta.tool_calls),
        "claim_categories_used": list(meta.claim_categories_used),
        "claim_aware_validated": meta.claim_aware_validated,
        "numeric_conflicts_count": meta.numeric_conflicts_count,
        "server_confidence": meta.server_confidence,
        "server_confidence_rationale": meta.server_confidence_rationale,
        "claim_audit": meta.claim_audit,
        "claim_audit_rejected": meta.claim_audit_rejected,
        "claim_audit_soft_corrections": meta.claim_audit_soft_corrections,
        "scenario_analysis": meta.scenario_analysis,
        "direct_answer": meta.direct_answer,
        "missing_data": list(meta.missing_data),
        "llm_tool_results": list(meta.llm_tool_results),
        "explanation": meta.explanation,
        "capability": list(meta.capability),  # list→tuple coercion in from_dict
        "business_dependency": meta.business_dependency,
    }
    # JSON round-trip — wire payloads come back as lists.
    round_tripped = GenerationMeta.from_dict(json.loads(json.dumps(serialised)))
    assert round_tripped.capability == ("RECOMMENDATION", "MIXED")
    assert round_tripped.business_dependency == "optional"


def test_chat_message_out_accepts_capability_field():
    """Pre-AI-11 rows deserialise unchanged; new rows accept the field."""
    from app.schemas.chat import ChatMessageOut

    legacy = {
        "id": 1,
        "role": "assistant",
        "kind": "assistant",
        "content": "Hi.",
        "sources": [],
        "created_at": "2026-08-11T00:00:00Z",
        "fallback_used": False,
    }
    legacy_msg = ChatMessageOut(**legacy)
    assert legacy_msg.capability == []
    assert legacy_msg.business_dependency == "none"

    enriched = dict(legacy)
    enriched["capability"] = ["BUSINESS_ANALYSIS", "RISK"]
    enriched["business_dependency"] = "required"
    enriched_msg = ChatMessageOut(**enriched)
    assert enriched_msg.capability == ["BUSINESS_ANALYSIS", "RISK"]
    assert enriched_msg.business_dependency == "required"


def test_chat_generation_meta_accepts_capability_field():
    """``ChatGenerationMeta`` accepts ``capability`` + ``business_dependency``."""
    from app.schemas.chat import ChatGenerationMeta

    legacy = {
        "provider": "deterministic-fallback",
        "model": "deterministic",
        "mode": "grounded",
        "fallback_used": True,
        "fallback_reason": None,
        "generation_method": "deterministic",
        "schema_validated": True,
        "grounding_validated": True,
        "server_grounding_score": 100,
        "evidence_count": 0,
        "confidence": 100,
        "assumptions": [],
        "limitations": [],
        "evidence_references": [],
        "generated_at": "2026-08-11T00:00:00Z",
        "prompt_truncated": False,
    }
    legacy_meta = ChatGenerationMeta(**legacy)
    assert legacy_meta.capability == []
    assert legacy_meta.business_dependency == "none"

    enriched = dict(legacy)
    enriched["capability"] = ["SCENARIO"]
    enriched["business_dependency"] = "required"
    enriched_meta = ChatGenerationMeta(**enriched)
    assert enriched_meta.capability == ["SCENARIO"]
    assert enriched_meta.business_dependency == "required"


# --------------------------------------------------------------------------- #
# 4. ``understand_question`` is deterministic — same inputs ⇒ same outputs.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "prompt",
    [
        "What is working capital?",
        "Are there schemes for compostable packaging?",
        "How can I reduce my biggest business risk?",
    ],
)
def test_understand_question_is_deterministic(prompt):
    """``understand_question`` is a pure function — same inputs ⇒ same output."""
    from app.services.ai.reasoning.question_understanding import (
        understand_question,
    )

    a = understand_question(prompt, context=None)
    b = understand_question(prompt, context=None)

    # ``parsed_at`` differs each call (ISO timestamp), so compare
    # only the meaningful fields.
    assert a.capability == b.capability
    assert a.business_dependency == b.business_dependency
    assert a.topic == b.topic
    assert a.is_business_specific == b.is_business_specific
    assert a.is_purely_educational == b.is_purely_educational

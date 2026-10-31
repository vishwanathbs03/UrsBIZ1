"""H8.11 — Vertical-slice integration test for the new
BusinessReasoningEngine + EvidenceRetriever pipeline.

The smallest possible end-to-end proof that the new
layer is wired in:

  1. Build an :class:`AssistantProviderService` with a stub
     context builder.
  2. Call ``generate(user_prompt="How can I reach 3 crore?")``.
  3. Inspect the :class:`AssistantRequest` that the prompt
     builder produced — it must carry a non-None
     ``reasoning_plan`` AND a non-None ``ranked_evidence``.
  4. The deterministic fallback body must include the
     detected intent + the question-specific sections the
     intent requires.

This is the spec's "smallest vertical slice": three
assertions, one test, proves the new architecture end-to-end
without changing the existing test surfaces.
"""
from __future__ import annotations

import sys

import pytest


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    from app.services.ai.providers.base import (
        AssistantContext,
        AssistantContextDna,
    )
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
        industry="textiles",
        location="Mumbai, MH, India",
    )


@pytest.fixture
def stub_context_builder(acme_context):
    class _StubContextBuilder:
        def build(self, *, owner_id, user_prompt=""):
            return acme_context

    return _StubContextBuilder()


@pytest.fixture
def service(stub_context_builder):
    from app.services.ai.providers.service import AssistantProviderService
    return AssistantProviderService(context_builder=stub_context_builder)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_h8_11_service_wires_reasoning_engine_and_retriever(
    service, stub_context_builder
):
    """The service.hooks the new engine + retriever into generate()."""
    # Spy on the engine/retriever by replacing them with
    # deterministic stubs and counting calls.
    from app.services.ai.reasoning.pipeline import (
        ReasoningPipeline,
        ReasoningPlan,
        ReasoningTrace,
        ReasoningStageResult,
        Hypothesis,
    )
    from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine
    from app.services.ai.reasoning.evidence_retriever import EvidenceRetriever

    calls = {"plan": 0, "rank": 0}

    class TrackingEngine(BusinessReasoningEngine):
        def plan(self, *, user_prompt, context):
            calls["plan"] += 1
            return super().plan(user_prompt=user_prompt, context=context)

    class TrackingRetriever(EvidenceRetriever):
        def rank(self, *, context, registry, reasoning_plan, top_n=None):
            calls["rank"] += 1
            return super().rank(
                context=context,
                registry=registry,
                reasoning_plan=reasoning_plan,
                top_n=top_n,
            )

    service._reasoning_engine = TrackingEngine()
    service._evidence_retriever = TrackingRetriever()

    # Call the prompt builder path directly — bypass the
    # LLM call by using the deterministic fallback
    # explicitly. The service still runs the engine +
    # retriever before invoking the provider.
    from app.services.ai.providers.base import DeterministicFallbackProvider
    resp = service.generate(
        owner_id=1,
        user_prompt="How can I reach 3 crore revenue?",
        provider=DeterministicFallbackProvider(),
    )

    assert calls["plan"] == 1, "BusinessReasoningEngine.plan must run once"
    assert calls["rank"] == 1, "EvidenceRetriever.rank must run once"
    assert resp.fallback_used is True
    assert resp.model == "deterministic-fallback"


def test_h8_11_service_detects_reach_revenue_target_intent(service):
    """The flagship question routes to the right intent end-to-end."""
    from app.services.ai.providers.base import DeterministicFallbackProvider
    resp = service.generate(
        owner_id=1,
        user_prompt="How can I reach 3 crore revenue?",
        provider=DeterministicFallbackProvider(),
    )
    # The deterministic fallback body acknowledges the
    # intent. The "Intent detected: Reach revenue target"
    # line is a stable marker of the intent-aware path.
    assert "Intent detected: Reach revenue target" in resp.body


def test_h8_11_service_detects_biggest_weakness_intent(service):
    """Biggest-weakness question routes correctly."""
    from app.services.ai.providers.base import DeterministicFallbackProvider
    resp = service.generate(
        owner_id=1,
        user_prompt="What is my biggest weakness?",
        provider=DeterministicFallbackProvider(),
    )
    assert "Biggest weakness" in resp.body


def test_h8_11_service_detects_government_schemes_intent(service):
    """Schemes question routes correctly."""
    from app.services.ai.providers.base import DeterministicFallbackProvider
    resp = service.generate(
        owner_id=1,
        user_prompt="Which government schemes should I apply for?",
        provider=DeterministicFallbackProvider(),
    )
    assert "Government schemes" in resp.body


def test_h8_11_prompt_builder_renders_reasoning_trace_block(service):
    """Direct-call the prompt builder and assert the trace block.

    This is the spec's third assertion — the prompt
    surface must contain a ``=== REASONING TRACE ===``
    block when the engine has run.
    """
    from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
    from app.services.ai.providers.base import AssistantContext, AssistantContextDna

    pb = AssistantPromptBuilder()
    ctx = AssistantContext(
        business_id=1,
        legal_name="Acme",
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        annual_revenue_inr=18_000_000,
        target_revenue_inr=30_000_000,
    )
    # Build a plan with the engine so the prompt gets a
    # non-None reasoning_plan.
    plan = service._reasoning_engine.plan(
        user_prompt="How can I reach 3 crore?", context=ctx,
    )
    from app.services.ai.providers.evidence_registry import EvidenceRegistry
    registry = EvidenceRegistry(ctx)
    ranked = service._evidence_retriever.rank(
        context=ctx, registry=registry, reasoning_plan=plan,
    )

    req = pb.build(
        context=ctx,
        user_prompt="How can I reach 3 crore?",
        reasoning_plan=plan,
        ranked_evidence=ranked,
    )
    msg = AssistantPromptBuilder.render_user_message(req)

    assert "=== REASONING TRACE" in msg
    assert "=== END REASONING TRACE ===" in msg
    assert "intent: reach_revenue_target" in msg


def test_h8_11_prompt_builder_renders_ranked_registry_footer(service):
    """When the retriever truncates, the footer appears."""
    from app.services.ai.providers.base import (
        AssistantContext,
        AssistantContextDna,
        AssistantContextRecommendation,
    )
    from app.services.ai.providers.prompt_builder import AssistantPromptBuilder

    # Build a context with enough recommendations to
    # trigger truncation.
    recs = tuple(
        AssistantContextRecommendation(
            id=f"rec_{i}",
            title=f"Recommendation {i}",
            category="ops",
            priority="High",
            estimated_score_gain=10,
            estimated_roi=1000.0,
            estimated_timeline="3 months",
        )
        for i in range(20)
    )
    from dataclasses import replace
    ctx = AssistantContext(
        business_id=1,
        legal_name="Acme",
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_seeker",
            archetype_title="Growth Seeker",
            match_score=82,
        ),
        annual_revenue_inr=18_000_000,
        recommendations=recs,
    )
    # Force a small top_n so the retriever truncates.
    from app.services.ai.reasoning.evidence_retriever import EvidenceRetriever
    small_retriever = EvidenceRetriever(top_n=5)
    plan = service._reasoning_engine.plan(
        user_prompt="How can I reach 3 crore?", context=ctx,
    )
    from app.services.ai.providers.evidence_registry import EvidenceRegistry
    registry = EvidenceRegistry(ctx)
    ranked = small_retriever.rank(
        context=ctx, registry=registry, reasoning_plan=plan,
    )
    assert ranked.truncated is True

    pb = AssistantPromptBuilder()
    req = pb.build(
        context=ctx,
        user_prompt="How can I reach 3 crore?",
        reasoning_plan=plan,
        ranked_evidence=ranked,
    )
    msg = AssistantPromptBuilder.render_user_message(req)
    assert "ranked by relevance" in msg
    assert "5 of" in msg
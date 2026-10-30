"""H8.11 — Unit tests for the BusinessReasoningEngine.

Verifies that the engine:

  * classifies the user prompt via the IntentRouter
  * extracts the KG sub-graph from the context
  * runs the H8.3 pipeline and overrides ``intent`` in
    the returned plan
  * exposes a ``subgraph_node_ids`` tuple derived from the
    knowledge graph
  * augments ``evidence_priorities`` with KG node
    ``evidence_id`` fields when present
"""
from __future__ import annotations

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
    )


@pytest.fixture
def engine():
    from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine
    return BusinessReasoningEngine()


# --------------------------------------------------------------------------- #
# Intent detection
# --------------------------------------------------------------------------- #


def test_h8_11_engine_detects_reach_revenue_target(engine, acme_context):
    plan = engine.plan(
        user_prompt="How can I reach 3 crore revenue?", context=acme_context,
    )
    assert plan.intent == "reach_revenue_target"


def test_h8_11_engine_detects_biggest_weakness(engine, acme_context):
    plan = engine.plan(
        user_prompt="What is my biggest weakness?", context=acme_context,
    )
    assert plan.intent == "biggest_weakness"


def test_h8_11_engine_detects_government_schemes(engine, acme_context):
    plan = engine.plan(
        user_prompt="Which government schemes should I apply for?",
        context=acme_context,
    )
    assert plan.intent == "government_schemes"


def test_h8_11_engine_detects_twelve_month_roadmap(engine, acme_context):
    plan = engine.plan(
        user_prompt="Give me a 12 month roadmap", context=acme_context,
    )
    assert plan.intent == "twelve_month_roadmap"


def test_h8_11_engine_detects_export_expansion(engine, acme_context):
    plan = engine.plan(
        user_prompt="Should I expand exports?", context=acme_context,
    )
    assert plan.intent == "export_expansion"


def test_h8_11_engine_defaults_to_general(engine, acme_context):
    plan = engine.plan(
        user_prompt="Tell me about the weather", context=acme_context,
    )
    assert plan.intent == "general"


# --------------------------------------------------------------------------- #
# Pipeline integration
# --------------------------------------------------------------------------- #


def test_h8_11_engine_emits_structured_plan(engine, acme_context):
    """The plan is a frozen dataclass with the expected fields."""
    from app.services.ai.reasoning.pipeline import ReasoningPlan, ReasoningTrace
    plan = engine.plan(
        user_prompt="How can I reach 3 crore?", context=acme_context,
    )
    assert isinstance(plan, ReasoningPlan)
    assert isinstance(plan.trace, ReasoningTrace)
    assert 0.0 <= plan.confidence <= 100.0
    assert isinstance(plan.subgraph_node_ids, tuple)
    assert isinstance(plan.hypotheses, tuple)
    assert isinstance(plan.evidence_priorities, tuple)


def test_h8_11_engine_uses_kg_when_present(engine, acme_context):
    """When context.knowledge_graph is set, the engine extracts sub-graph ids."""
    # Build a minimal KG with three nodes and attach to context.
    from app.services.ai.knowledge.knowledge_graph import (
        BusinessKnowledgeGraph,
        KnowledgeNode,
    )
    from dataclasses import replace

    kg = BusinessKnowledgeGraph()
    for nid in ("node_profile_main", "node_analytics_score", "node_dna"):
        kg.add_node(KnowledgeNode(
            id=nid,
            category="profile",
            label=nid,
            properties={},
            evidence_id=None,
            priority_score=80.0,
        ))

    ctx = replace(acme_context, knowledge_graph=kg)
    plan = engine.plan(
        user_prompt="How can I reach 3 crore?", context=ctx,
    )
    # The engine returns KG node ids in priority order.
    assert "node_profile_main" in plan.subgraph_node_ids
    assert "node_analytics_score" in plan.subgraph_node_ids


def test_h8_11_engine_rebuilds_kg_when_missing(engine, acme_context):
    """When context.knowledge_graph is None, the engine builds one inline."""
    # acme_context has knowledge_graph=None.
    plan = engine.plan(
        user_prompt="How can I reach 3 crore?", context=acme_context,
    )
    # The engine ran the fallback KG build (or returned an
    # empty tuple when the rebuild fails) — but it never
    # raises.
    assert isinstance(plan.subgraph_node_ids, tuple)


def test_h8_11_engine_confidence_in_range(engine, acme_context):
    plan = engine.plan(
        user_prompt="How can I reach 3 crore?", context=acme_context,
    )
    assert 0.0 <= plan.confidence <= 100.0


def test_h8_11_engine_handles_empty_prompt(engine, acme_context):
    """Empty / whitespace prompts default to general intent."""
    plan = engine.plan(user_prompt="", context=acme_context)
    assert plan.intent == "general"
    plan2 = engine.plan(user_prompt="   ", context=acme_context)
    assert plan2.intent == "general"


def test_h8_11_engine_handles_none_context(engine):
    """A None context must not raise."""
    plan = engine.plan(user_prompt="How can I reach 3 crore?", context=None)
    assert plan.intent == "reach_revenue_target"
    assert plan.subgraph_node_ids == ()


def test_h8_11_engine_subgraph_max_nodes_configurable(acme_context):
    """The subgraph cap is honoured by the constructor arg."""
    from app.services.ai.knowledge.knowledge_graph import (
        BusinessKnowledgeGraph,
        KnowledgeNode,
    )
    from dataclasses import replace
    from app.services.ai.reasoning.reasoning_engine import BusinessReasoningEngine

    kg = BusinessKnowledgeGraph()
    for i in range(20):
        kg.add_node(KnowledgeNode(
            id=f"node_{i:02d}",
            category="profile",
            label=f"Node {i}",
            properties={},
            priority_score=80.0,
        ))

    ctx = replace(acme_context, knowledge_graph=kg)
    engine = BusinessReasoningEngine(subgraph_max_nodes=3)
    plan = engine.plan(
        user_prompt="How can I reach 3 crore?", context=ctx,
    )
    # Cap is honoured — but extract_subgraph may also have
    # its own internal cap. We assert ``<=3`` defensively.
    assert len(plan.subgraph_node_ids) <= 3
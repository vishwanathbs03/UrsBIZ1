"""Test suite for Sprint H8.2 — Multi-Module Business Knowledge Graph & Evidence Fusion Engine."""

import pytest
from app.services.ai.knowledge.context_ranker import ContextRanker
from app.services.ai.knowledge.evidence_fusion import EvidenceFusion
from app.services.ai.knowledge.knowledge_graph import (
    BusinessKnowledgeGraph,
    KnowledgeNode,
    KnowledgeRelationship,
)
from app.services.ai.knowledge.priority_engine import PriorityEngine
from app.services.ai.knowledge.relationship_engine import RelationshipEngine
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextRule,
    AssistantContextScheme,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder


@pytest.fixture
def multi_module_context() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=85,
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="supplier_diversification",
                title="Diversify yarn suppliers",
                category="supply_chain",
                priority="High",
                estimated_score_gain=10,
                estimated_roi=15000.0,
                estimated_timeline="2-3 months",
            ),
        ),
        rules=(
            AssistantContextRule(
                id="supplier_risk",
                title="Single Supplier Dependency Risk",
                category="risk",
                priority="Critical",
                reason="Top vendor supplies 75% of raw materials",
                estimated_impact=15,
            ),
        ),
        schemes=(
            AssistantContextScheme(
                scheme_id="scheme_export_incentive",
                title="Market Access Export Scheme",
                authority="Ministry of Textiles",
                application_url="https://schemes.gov.in/export",
                profile_match_score=85,
                last_verified_date="2026-01-01",
            ),
        ),
        products=("Cotton Yarn", "Denim Fabric"),
        export_history=("Vietnam", "Bangladesh"),
        goals=("Expand exports to Europe", "Achieve ₹3 Cr turnover"),
        challenges=("High yarn raw material cost volatility",),
    )


def test_1_knowledge_graph_ingestion(multi_module_context):
    """Verify BusinessKnowledgeGraph ingests nodes from all business modules."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    nodes = kg.nodes
    categories = {n.category for n in nodes}

    assert "profile" in categories
    assert "analytics" in categories
    assert "dna" in categories
    assert "risk" in categories
    assert "recommendation" in categories
    assert "scheme" in categories
    assert "product" in categories
    assert "export" in categories
    assert "goal" in categories


def test_2_relationship_engine_cross_module_edges(multi_module_context):
    """Verify RelationshipEngine establishes cross-module relationships (Risk -> Rec, Scheme -> Rec)."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    engine = RelationshipEngine()
    count = engine.infer_and_link_relationships(kg)

    assert count > 0
    rel_types = {r.relation_type for r in kg.relationships}
    assert "mitigated_by" in rel_types or "improves_health_score" in rel_types or "driven_by_action" in rel_types


def test_3_priority_engine_scoring(multi_module_context):
    """Verify PriorityEngine scores nodes based on risk criticality & connectivity."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    RelationshipEngine().infer_and_link_relationships(kg)
    scored = PriorityEngine().score_nodes(kg)

    top_node = scored[0]
    assert top_node.priority_score >= 85.0


def test_4_context_ranker_intent_selection(multi_module_context):
    """Verify ContextRanker selects multi-module subgraph nodes matching prompt intent."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    RelationshipEngine().infer_and_link_relationships(kg)
    PriorityEngine().score_nodes(kg)

    ranker = ContextRanker()
    selected = ranker.select_multi_module_context(kg, user_prompt="How do I expand my exports?", max_nodes=10)

    selected_cats = {n.category for n in selected}
    assert len(selected_cats) >= 3


def test_5_evidence_fusion_bundle(multi_module_context):
    """Verify EvidenceFusion extracts grounded evidence items across graph nodes."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    fusion = EvidenceFusion()
    items = fusion.fuse_evidence_bundle(kg)

    assert len(items) >= 4
    e_kinds = {item["kind"] for item in items}
    assert "score" in e_kinds or "recommendation" in e_kinds or "rule" in e_kinds


def test_6_prompt_builder_includes_knowledge_graph_triples(multi_module_context):
    """Verify AssistantPromptBuilder includes Knowledge Graph triples in user message."""
    kg = BusinessKnowledgeGraph.from_context(multi_module_context)
    RelationshipEngine().infer_and_link_relationships(kg)
    PriorityEngine().score_nodes(kg)

    from dataclasses import replace
    ctx_with_kg = replace(multi_module_context, knowledge_graph=kg)

    builder = AssistantPromptBuilder()
    req = builder.build(context=ctx_with_kg, user_prompt="Help Acme Textiles grow", mode="grounded")
    user_msg = builder.render_user_message(req)

    assert "KNOWLEDGE GRAPH RELATIONSHIPS" in user_msg
    assert "MITIGATED BY" in user_msg or "HAS SCORE" in user_msg or "EXPOSED TO RISK" in user_msg

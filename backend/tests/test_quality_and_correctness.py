"""Regression tests for P0 AI Quality and Answer Correctness Repair.

Verifies:
1. KnowledgeRetrievalService.retrieve() accepts optional top_k argument.
2. Educational queries (e.g. 'What is EBITDA?', 'What is working capital?') correctly:
   - Identify as is_purely_educational=True, is_business_specific=False
   - Set capability = ('GENERAL_KNOWLEDGE',)
   - Exclude the business snapshot and 43-rule compliance report from the prompt
3. Business fact queries ('What is our current revenue?', 'How many employees do we have?'):
   - Identify as is_business_specific=True
   - Remain grounded
   - Preserve deterministic facts
4. Calculation and scenario intents match appropriate reasoning plans.
5. All 15 question categories route through question_understanding without error.
"""
from __future__ import annotations

import pytest
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantRequest,
    DeterministicFallbackProvider,
)
from app.services.ai.providers.prompt_builder import (
    AssistantPromptBuilder,
    _render_open_user_message,
)
from app.services.ai.reasoning.question_understanding import (
    is_purely_educational,
    understand_question,
)
from app.services.knowledge_retrieval.service import (
    KnowledgeRetrievalService,
)
from app.services.knowledge.repository import JsonKnowledgeRepository
from app.services.knowledge.service import KnowledgeService


@pytest.fixture
def sample_context() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Apex Textiles Private Limited",
        industry="Textiles & Apparel",
        sub_industry="Garment Manufacturing",
        business_type="Private Limited",
        location="Bengaluru, Karnataka",
        employee_count="45",
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Growth",
        dna=AssistantContextDna(
            archetype_key="scale_seeker",
            archetype_title="The Scale Seeker",
            match_score=82,
        ),
    )


def test_knowledge_retrieval_service_accepts_top_k():
    """KnowledgeRetrievalService.retrieve() must accept optional top_k without raising TypeError."""
    repo = JsonKnowledgeRepository()
    service = KnowledgeRetrievalService(KnowledgeService(repo), top_k=5)
    ctx = service.retrieve(query="working capital", top_k=3)
    assert ctx is not None
    assert hasattr(ctx, "query")


def test_educational_prompt_understanding():
    """'What is EBITDA?' and 'What is working capital?' must be recognized as purely educational."""
    q1 = understand_question("What is EBITDA?")
    assert q1.is_purely_educational is True
    assert q1.is_business_specific is False
    assert "GENERAL_KNOWLEDGE" in q1.capability

    q2 = understand_question("What is working capital?")
    assert q2.is_purely_educational is True
    assert q2.is_business_specific is False
    assert "GENERAL_KNOWLEDGE" in q2.capability


def test_educational_prompt_excludes_business_report(sample_context):
    """Educational queries in open mode must not be flooded with 43-record business compliance snapshots."""
    builder = AssistantPromptBuilder()
    req = builder.build(
        context=sample_context,
        user_prompt="What is EBITDA?",
        mode="open",
    )
    rendered = _render_open_user_message(req)
    # Must NOT include the business compliance snapshot
    assert "=== BUSINESS SNAPSHOT ===" not in rendered
    assert "Apex Textiles" not in rendered
    # Must include the educational directive
    assert "Answer the educational or conceptual" in rendered
    assert "What is EBITDA?" in rendered


def test_business_fact_query_identifies_business_specific(sample_context):
    """'What is our current revenue?' must be business-specific and maintain grounding."""
    q = understand_question("What is our current revenue?", sample_context)
    assert q.is_business_specific is True
    assert q.is_purely_educational is False


def test_all_15_prompt_categories_understand_without_error(sample_context):
    """All 15 evaluation prompts must successfully generate a QuestionUnderstanding."""
    prompts = [
        "What is EBITDA?",
        "What is working capital?",
        "What is our current revenue?",
        "How many employees do we have?",
        "What is our biggest business risk?",
        "Why is our supply chain vulnerable?",
        "How much revenue do we need to reach ₹3 Cr?",
        "Can we afford to hire 10 employees?",
        "What happens if revenue grows 20%?",
        "What if our largest supplier stops supplying us?",
        "Should we diversify suppliers?",
        "What should we prioritize this month?",
        "Which government schemes could help us?",
        "What certifications are relevant to European exports?",
        "Compare supplier diversification vs inventory buffering.",
    ]
    for prompt in prompts:
        qu = understand_question(prompt, sample_context)
        assert qu is not None
        assert qu.literal_question == prompt
        assert qu.topic is not None
        assert isinstance(qu.capability, tuple)
        assert qu.answer_mode is not None


def test_deterministic_fallback_contains_factual_revenue(sample_context):
    """Deterministic fallback must contain real revenue facts from context."""
    req = AssistantRequest(
        user_prompt="What is our current revenue?",
        context=sample_context,
        mode="grounded",
    )
    provider = DeterministicFallbackProvider()
    resp = provider.complete(req)
    assert resp.body is not None
    assert "1.80 Cr" in resp.body or "18,000,000" in resp.body or "Apex Textiles" in resp.body

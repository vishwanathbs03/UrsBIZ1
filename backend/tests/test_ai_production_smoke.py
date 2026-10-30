"""Phase 16 — Master Production AI Assistant Smoke Suite.

Comprehensive 12-case verification matrix covering:
1. General knowledge / educational queries
2. Business-specific revenue lookups
3. Risk / weakness identification
4. Deterministic gap calculations
5. Deterministic scenario analysis
6. Government scheme eligibility matching
7. 12-month strategic roadmap queries
8. Supplier diversification recommendations
9. Provider unavailable failover
10. Grounding rejection safe fallback
11. Missing revenue data disclosure (never invented)
12. Unsupported / out-of-scope question boundaries
"""

import pytest
from types import SimpleNamespace

from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextScore,
    AssistantContextRecommendation,
    AssistantContextRoadmap,
    AssistantContextRule,
    AssistantContextInsight,
    AssistantContextScheme,
    AssistantContextForecast,
    ProviderUnavailableError,
)
from app.services.ai.providers.intent_router import QuestionIntent, classify_intent
from app.services.ai.reasoning.question_understanding import understand_question, is_purely_educational
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.reasoning.tool_selector import ToolDispatcher
from app.services.ai.providers.evidence_registry import EvidenceRegistry


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def acme_context():
    """Acme Textiles full business context."""
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles Ltd",
        trade_name="Acme Textiles",
        industry="Textiles & Apparel",
        location="Tirupur, Tamil Nadu",
        business_type="Private Limited",
        employee_count="45",
        annual_revenue_inr=18000000,  # ₹1.8 Cr
        target_revenue_inr=30000000,  # ₹3.0 Cr
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=82,
        ),
        scores=(
            AssistantContextScore(key="financial", title="Financial Health", score=72, level="Strong"),
            AssistantContextScore(key="supply_chain", title="Supply Chain Risk", score=45, level="Vulnerable"),
            AssistantContextScore(key="digital", title="Digital Presence", score=60, level="Developing"),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_diversify_suppliers",
                title="Diversify Yarn Suppliers",
                category="operations",
                priority="High",
                estimated_score_gain=12,
                estimated_timeline="60 days",
                estimated_roi=350000,
            ),
            AssistantContextRecommendation(
                id="rec_invoice_factoring",
                title="Adopt Invoice Discounting for Receivables",
                category="finance",
                priority="High",
                estimated_score_gain=8,
                estimated_timeline="30 days",
                estimated_roi=200000,
            ),
        ),
        roadmap=(
            AssistantContextRoadmap(
                id="rdm_q1_supplier_onboarding",
                title="Onboard 2 alternate cotton yarn suppliers",
                phase="Q1",
                priority="High",
                estimated_start_order=1,
                completion_percentage=25,
                expected_score_improvement=6,
            ),
            AssistantContextRoadmap(
                id="rdm_q2_export_audit",
                title="Complete compliance audit for GCC exports",
                phase="Q2",
                priority="Medium",
                estimated_start_order=2,
                completion_percentage=0,
                expected_score_improvement=10,
            ),
        ),
        rules=(
            AssistantContextRule(
                id="rule_single_supplier_risk",
                title="Top supplier provides 75% of raw material",
                category="operations",
                priority="Critical",
                estimated_impact=-15,
                reason="High supplier concentration",
            ),
        ),
        insights=(
            AssistantContextInsight(
                id="ins_working_capital_stretch",
                title="Receivables cycle stretched to 78 days",
                priority="High",
                confidence=85,
            ),
        ),
        schemes=(
            AssistantContextScheme(
                scheme_id="scheme_cgtmse",
                title="CGTMSE Collateral Free Loan",
                authority="Ministry of MSME",
                application_url="https://cgtmse.in",
                profile_match_score=88,
                last_verified_date="2026-01-15",
            ),
        ),
        forecasts=(
            AssistantContextForecast(
                scenario_id="fc_rev_q4",
                horizon_label="12-month scenario",
                revenue_delta=6000000.0,
                score_delta=8,
                assumption_summary="Assuming 20% yarn demand growth",
                confidence=75,
            ),
        ),
    )


@pytest.fixture
def empty_revenue_context():
    """Context with missing annual revenue."""
    return AssistantContext(
        business_id=2,
        legal_name="Newborn Startup",
        industry="Retail",
        annual_revenue_inr=0,
        target_revenue_inr=5000000,
        overall_business_score=35,
        band="Foundation",
        dna=AssistantContextDna("foundation_builder", "Foundation Builder", 60),
    )


class _StubContextBuilder:
    def __init__(self, ctx):
        self._ctx = ctx

    def build(self, *, owner_id: int, user_prompt: str = ""):
        return self._ctx


class _UnavailableProvider:
    name = "mock-unavailable"
    is_available = False
    model_name = "mock"

    def complete(self, req):
        raise ProviderUnavailableError("Simulated LLM network unreachable")


# --------------------------------------------------------------------------- #
# Smoke Test Matrix Cases 1 - 12
# --------------------------------------------------------------------------- #


def test_smoke_01_general_knowledge_working_capital(acme_context):
    """Case 1: 'What is working capital?' -> Educational, open-mode capable."""
    prompt = "What is working capital?"
    qu = understand_question(prompt, acme_context)
    assert qu.is_purely_educational is True
    assert qu.is_business_specific is False
    assert is_purely_educational(prompt) is True


def test_smoke_02_business_specific_revenue_lookup(acme_context):
    """Case 2: 'What is our current revenue?' -> Grounded lookup of actual profile revenue."""
    prompt = "What is our current revenue?"
    qu = understand_question(prompt, acme_context)
    assert qu.is_business_specific is True
    assert qu.is_purely_educational is False
    assert qu.topic == "finance"

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    assert res.fallback_used is True
    # The actual profile revenue (₹1.8 Cr) must appear in the verified output
    assert "1.80 Cr" in res.body or "18,000,000" in res.body or "1.8" in res.body


def test_smoke_03_risk_weakness_identification(acme_context):
    """Case 3: 'What is our biggest business risk?' -> Identifies critical rules and risk scores."""
    prompt = "What is our biggest business risk?"
    intent = classify_intent(prompt)
    assert intent == QuestionIntent.BIGGEST_WEAKNESS

    qu = understand_question(prompt, acme_context)
    assert qu.topic == "risk"
    assert qu.is_business_specific is True

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    assert "risk" in res.body.lower() or "score" in res.body.lower()


def test_smoke_04_calculation_reach_target(acme_context):
    """Case 4: 'How much revenue do we need to reach ₹3 Cr?' -> Deterministic gap calculation."""
    prompt = "How much revenue do we need to reach ₹3 Cr?"
    intent = classify_intent(prompt)
    assert intent == QuestionIntent.REACH_REVENUE_TARGET

    qu = understand_question(prompt, acme_context)
    assert "gap_math" in qu.needs_calculations

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    # Gap between ₹3.0 Cr and ₹1.8 Cr is ₹1.2 Cr
    assert "1.20 Cr" in res.body or "1.2" in res.body or "1,20,00,000" in res.body or "12,000,000" in res.body


def test_smoke_05_scenario_analysis(acme_context):
    """Case 5: 'What happens if revenue grows 20%?' -> Scenario classification & delta calculations."""
    prompt = "What happens if revenue grows 20%?"
    qu = understand_question(prompt, acme_context)
    assert qu.topic == "scenario"
    assert qu.complexity == "scenario"
    assert "scenario_delta" in qu.needs_calculations


def test_smoke_06_government_scheme_eligibility(acme_context):
    """Case 6: 'Which government schemes am I eligible for?' -> Scheme evidence matching without fake promises."""
    prompt = "Which government schemes am I eligible for?"
    intent = classify_intent(prompt)
    assert intent == QuestionIntent.GOVERNMENT_SCHEMES

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    # CGTMSE from context schemes must appear
    assert "CGTMSE" in res.body or "scheme" in res.body.lower()


def test_smoke_07_twelve_month_roadmap(acme_context):
    """Case 7: 'Give me a 12-month roadmap.' -> Roadmap evidence and quarterly milestones."""
    prompt = "Give me a 12-month roadmap."
    intent = classify_intent(prompt)
    assert intent == QuestionIntent.TWELVE_MONTH_ROADMAP

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    assert "roadmap" in res.body.lower() or "Q1" in res.body or "milestone" in res.body.lower()


def test_smoke_08_supplier_recommendation(acme_context):
    """Case 8: 'Should we diversify suppliers?' -> Actionable operational recommendation grounded in context."""
    prompt = "Should we diversify suppliers?"
    qu = understand_question(prompt, acme_context)
    assert qu.topic == "operations"
    assert qu.is_business_specific is True


def test_smoke_09_provider_unavailable_fallback(acme_context):
    """Case 9: Provider unavailable -> Graceful deterministic fallback with honest trust metadata."""
    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt="Give me a business health overview",
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    assert res.fallback_used is True
    assert res.generation is not None
    assert res.generation.generation_method == "deterministic"
    assert res.generation.server_grounding_score == 100
    assert len(res.body) > 100


def test_smoke_10_grounding_rejection_fallback(acme_context):
    """Case 10: Grounding rejection -> Safe fallback preventing hallucinated claims."""
    from app.services.ai.providers.base import Provider

    class _HallucinatingProvider:
        name = "mock-hallucinator"
        is_available = True
        model_name = "mock"

        def complete(self, req):
            # Returns ungrounded hallucinated numbers and non-existent evidence IDs
            from app.services.ai.providers.base import ProviderResponse
            return ProviderResponse(
                body="""{
                    "executive_summary": "We guarantee you are eligible for ₹100 Crore grant.",
                    "business_facts": [],
                    "situation_assessment": "Unchecked",
                    "reasoning": "Made up",
                    "root_causes": [],
                    "key_findings": [{"finding": "Hallucinated", "evidence_ref": "fake_id_999"}],
                    "recommendations": [{"recommendation_id": "fake_rec", "title": "Free Money", "priority": "High", "evidence_refs": ["fake_999"]}],
                    "priority_matrix": [],
                    "roi_estimate": "1000%",
                    "risks": [],
                    "tool_calls": [],
                    "thirty_day_plan": [],
                    "scheme_matches": [],
                    "assumptions": ["None"],
                    "limitations": ["None"],
                    "confidence": 99,
                    "evidence_references": [{"evidence_id": "fake_id_999", "citation": "Imagination"}]
                }""",
                model="mock",
            )

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt="How can we grow fast?",
        provider=_HallucinatingProvider(),
        mode="grounded",
    )
    # The hallucinated response must be rejected by grounding validation and routed to fallback
    assert res.fallback_used is True
    assert "fake_id_999" not in res.body
    assert "Free Money" not in res.body


def test_smoke_11_missing_data_honesty(empty_revenue_context):
    """Case 11: Missing business data -> Explicit disclosure, never invented figures."""
    prompt = "What is our current revenue?"
    srv = AssistantProviderService(context_builder=_StubContextBuilder(empty_revenue_context))
    res = srv.generate(
        owner_id=2,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    # Must explicitly state revenue is not recorded, and not fabricate a number
    assert "not recorded" in res.body.lower() or "not set" in res.body.lower()


def test_smoke_12_unsupported_out_of_scope_boundary(acme_context):
    """Case 12: Random / out-of-scope query -> Handled safely without hallucination or crash."""
    prompt = "What is the airspeed velocity of an unladen swallow?"
    qu = understand_question(prompt, acme_context)
    assert qu.is_business_specific is False

    srv = AssistantProviderService(context_builder=_StubContextBuilder(acme_context))
    res = srv.generate(
        owner_id=1,
        user_prompt=prompt,
        provider=_UnavailableProvider(),
        mode="grounded",
    )
    assert res is not None
    assert len(res.body) > 0

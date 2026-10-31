"""Test suite for Sprint H8.1 — Senior MSME Business Consultant Prompting & Structured Reasoning Engine."""

import json
import pytest
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextRule,
    AssistantRequest,
    AssistantResponse,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
from app.services.ai.providers.response_schema import (
    GroundedResponse,
    parse_model_output,
    parse_open_model_output,
)
from app.services.ai.providers.service import AssistantProviderService


@pytest.fixture
def consultant_context() -> AssistantContext:
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
                id="rule_supplier_risk",
                title="Single Supplier Risk",
                category="risk",
                priority="Critical",
                reason="High single vendor dependency",
                estimated_impact=15,
            ),
        ),
    )


def test_1_parse_senior_consultant_10_sections():
    """Verify parse_model_output correctly extracts all 10 consultant fields."""
    payload = {
        "executive_summary": "Acme Textiles is positioned for growth with a ₹1.8 Cr baseline revenue.",
        "business_facts": ["Revenue is ₹1.8 Cr", "Established Band score 68/100"],
        "situation_assessment": "Solid operational foundation with high supplier concentration risk.",
        "reasoning": "High dependency on top yarn vendor limits margin expansion.",
        "root_causes": ["Lack of secondary yarn vendor agreements", "Manual purchase order workflow"],
        "key_findings": [
            {
                "statement": "Single vendor handles 75% of raw materials",
                "evidence_refs": ["biz_profile_revenue"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "supplier_diversification",
                "title": "Diversify yarn suppliers",
                "rationale": "Reduces concentration risk and unlocks 12% margin savings",
                "evidence_refs": ["biz_profile_revenue"],
            }
        ],
        "priority_matrix": [
            {
                "action": "Audit top 3 yarn vendors",
                "impact": "High",
                "effort": "Low",
                "priority_category": "Quick Win",
            }
        ],
        "roi_estimate": "Estimated ₹1.5L annual margin improvement with 2-3 months payback.",
        "risks": ["Potential transition delays in Q3"],
        "thirty_day_plan": [
            {
                "week": 1,
                "task": "Audit yarn suppliers",
                "recommendation_ref": "rec_supplier_diversification",
                "evidence_refs": ["biz_profile_revenue"],
            }
        ],
        "assumptions": ["Yarn prices remain stable"],
        "limitations": ["Requires initial vendor vetting effort"],
        "confidence": 88,
        "evidence_references": [{"id": "biz_profile_revenue", "kind": "score", "label": "Revenue"}],
    }

    result = parse_model_output(json.dumps(payload))
    assert result.ok is True
    resp: GroundedResponse = result.response
    assert resp.executive_summary.startswith("Acme Textiles")
    assert len(resp.business_facts) >= 1
    assert "supplier concentration risk" in resp.situation_assessment
    assert "Single vendor" in resp.root_causes[0] or "Lack of secondary" in resp.root_causes[0]
    assert len(resp.priority_matrix) == 1
    assert resp.priority_matrix[0]["priority_category"] == "Quick Win"
    assert "₹1.5L" in resp.roi_estimate
    assert len(resp.risks) >= 1


def test_2_grounded_system_prompt_has_senior_consultant_persona(consultant_context):
    """Verify prompt_builder injects Senior Consultant persona and 10-section instructions."""
    builder = AssistantPromptBuilder()
    sys_prompt = builder.system_message("grounded")

    assert "Senior MSME Business Consultant" in sys_prompt
    assert "10 Required Sections" in sys_prompt
    assert "Root Cause Analysis" in sys_prompt
    assert "Priority Matrix" in sys_prompt


def test_3_open_system_prompt_has_senior_consultant_sections(consultant_context):
    """Verify Open mode prompt includes Senior Consultant 10-section structure."""
    builder = AssistantPromptBuilder()
    sys_prompt = builder.system_message("open")

    assert "Senior MSME Business Consultant" in sys_prompt
    assert "SITUATION ASSESSMENT" in sys_prompt
    assert "ROOT CAUSE ANALYSIS" in sys_prompt
    assert "PRIORITY MATRIX" in sys_prompt


def test_4_deterministic_fallback_contains_senior_consultant_sections(consultant_context):
    """Verify deterministic engine fallback formats 10 Senior Consultant sections."""
    builder = AssistantPromptBuilder()
    req: AssistantRequest = builder.build(
        context=consultant_context,
        user_prompt="Help me optimize costs",
        mode="grounded",
    )

    from app.services.ai.providers.base import DeterministicFallbackProvider
    fallback = DeterministicFallbackProvider()
    resp = fallback.complete(req)

    assert "SITUATION ASSESSMENT" in resp.body
    assert "DIAGNOSTIC REASONING" in resp.body
    assert "ROI & FINANCIAL IMPACT ESTIMATE" in resp.body
    assert "KEY RISKS & MITIGATIONS" in resp.body


def test_5_to_chat_body_renders_all_10_sections():
    """Verify GroundedResponse.to_chat_body() renders markdown with all 10 consultant section headers."""
    resp = GroundedResponse(
        executive_summary="Acme growth plan",
        business_facts=("Revenue ₹1.8 Cr",),
        situation_assessment="Strong growth opportunity",
        reasoning="Supplier concentration is bottleneck",
        root_causes=("Single yarn vendor",),
        recommendations=(),
        priority_matrix=({"action": "Vendor audit", "impact": "High", "effort": "Low", "priority_category": "Quick Win"},),
        roi_estimate="₹1.5L annual margin improvement",
        risks=("Vendor transition risk",),
        confidence=90,
    )

    body = resp.to_chat_body()
    assert "### 1. BUSINESS FACTS" in body
    assert "### 2. SITUATION ASSESSMENT" in body
    assert "### 3. DIAGNOSTIC REASONING" in body
    assert "### 4. ROOT CAUSE ANALYSIS" in body
    assert "### 6. PRIORITY MATRIX" in body
    assert "### 7. ROI & FINANCIAL IMPACT ESTIMATE" in body
    assert "### 8. KEY RISKS & MITIGATIONS" in body

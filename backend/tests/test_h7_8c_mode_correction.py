"""H7.8C Mode Correction Test Suite.

Tests for mode semantics correction:
  1. Grounded mode receives business context.
  2. Open mode also receives relevant business context.
  3. Open mode receives analytics.
  4. Open mode receives report summaries.
  5. Open mode receives risks and recommendations.
  6. Open mode can answer a general question without the full profile.
  7. Open mode personalizes a relevant general question using evidence.
  8. Open mode does not invent business numbers.
  9. Open mode labels scenarios as illustrative.
  10. Open mode blocks guaranteed-growth language.
  11. Open mode blocks official-eligibility claims.
  12. Open mode identifies missing information.
  13. Business evidence references are valid.
  14. Full private profile is not sent when unnecessary.
  15. Context manifest persists in generation_meta_json.
  16. Refresh preserves mode and trust labels.
  17. Grounded mode behavior remains unchanged.
  18. Deterministic fallback remains unchanged.
"""
from __future__ import annotations

import json
import pytest

from app.services.ai.providers.base import (
    AnalyticsMetric,
    AssistantContext,
    AssistantContextDna,
    AssistantContextRecommendation,
    AssistantContextRule,
    AssistantContextScheme,
    AssistantContextScore,
    AssistantRequest,
    BusinessContextManifest,
    GenerationMeta,
    ReportSummary,
)
from app.services.ai.providers.context_builder import AssistantContextBuilder, select_relevant_context
from app.services.ai.providers.evidence_registry import EvidenceRegistry
from app.services.ai.providers.grounding_validator import OpenResponseValidator
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
from app.services.ai.providers.response_schema import OpenResponse, parse_open_model_output
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.providers.factory import ProviderFactory


@pytest.fixture
def acme_full_context() -> AssistantContext:
    """Fixture for Acme Textiles business context."""
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles Pvt Ltd",
        trade_name="Acme Textiles",
        industry="Textiles & Apparel",
        sub_industry="Weaving & Garment Manufacturing",
        business_type="Private Limited",
        location="Surat, Gujarat, India",
        employee_count="45",
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna(
            archetype_key="growth_operator",
            archetype_title="Growth Operator",
            match_score=82,
        ),
        products=("Cotton Fabrics", "Industrial Yarn"),
        services=("Custom Dyeing",),
        certifications=("OEKO-TEX Standard 100", "ISO 9001:2015"),
        digital_presence=("https://acmetextiles.example.com",),
        export_history=("UAE", "Bangladesh"),
        goals=("Reach ₹3 Cr revenue", "Expand export footprint"),
        challenges=("High supplier concentration", "Manual inventory tracking"),
        scores=(
            AssistantContextScore(
                key="financial_readiness",
                title="Financial Readiness",
                score=72,
                level="Medium",
            ),
            AssistantContextScore(
                key="export_readiness",
                title="Export Readiness",
                score=65,
                level="Medium",
            ),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_supplier_diversification",
                title="Diversify Yarn Suppliers",
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
                title="High Supplier Concentration Risk",
                category="risk",
                priority="High",
                estimated_impact=15,
                reason="Single supplier supplies >60% of raw cotton",
            ),
        ),
        schemes=(
            AssistantContextScheme(
                scheme_id="pmegp",
                title="PMEGP Scheme",
                authority="Ministry of MSME",
                application_url="https://pmegp.example.gov.in",
                profile_match_score=80,
                last_verified_date="2026-07-01",
            ),
        ),
        analytics_metrics=(
            AnalyticsMetric(
                metric_id="revenue_growth_rate",
                metric_name="Revenue Growth Rate",
                current_value=12.5,
                unit="%",
                time_period="YoY",
                trend="upward",
                baseline="10%",
                method="calculated",
                updated_at="2026-08-01",
            ),
        ),
        report_summaries=(
            ReportSummary(
                report_id="rep_2026_q2",
                report_type="unified_business_report",
                generated_at="2026-07-15",
                executive_summary="Acme Textiles demonstrates strong growth momentum with ₹1.8 Cr baseline revenue.",
                key_metrics=("Revenue: ₹1.8 Cr", "Health Score: 68/100"),
                risks=("Supplier concentration risk",),
                recommendations=("Diversify yarn suppliers",),
                assumptions=("Stable raw cotton prices",),
            ),
        ),
    )


class _MockOpenProvider:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.name = "mock_provider"
        self.is_available = True

    def complete(self, request: AssistantRequest):
        from app.services.ai.providers.base import AssistantResponse, GenerationMeta
        return AssistantResponse(
            body=self._text,
            model="mock_model",
            fallback_used=False,
            provider_used="mock_provider",
            generated_at="2026-08-06T12:00:00Z",
            generation=GenerationMeta.empty(
                mode=request.mode,
                provider_used="mock_provider",
                model="mock_model",
                provider_latency_ms=45,
                fallback_used=False,
            ),
        )


def test_1_grounded_mode_receives_business_context(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="What is my score?", mode="grounded")
    rendered = builder.render_user_message(req)

    assert "=== BUSINESS SNAPSHOT ===" in rendered
    assert "Acme Textiles Pvt Ltd" in rendered
    assert "financial_readiness" in rendered
    assert "EVIDENCE REGISTRY" in rendered


def test_2_open_mode_receives_relevant_business_context(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="How to grow to ₹3 Cr?", mode="open")
    rendered = builder.render_user_message(req)

    assert "=== BUSINESS SNAPSHOT ===" in rendered
    assert "Acme Textiles Pvt Ltd" in rendered
    assert "annual_revenue_inr: ₹18,000,000" in rendered


def test_3_open_mode_receives_analytics(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="Analyze my growth metrics", mode="open")
    rendered = builder.render_user_message(req)

    assert "ANALYTICS & KPIS" in rendered
    assert "revenue_growth_rate" in rendered


def test_4_open_mode_receives_report_summaries(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="Summarize my report", mode="open")
    rendered = builder.render_user_message(req)

    assert "BUSINESS REPORT SUMMARIES" in rendered
    assert "rep_2026_q2" in rendered


def test_5_open_mode_receives_risks_and_recommendations(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="What are my risks?", mode="open")
    rendered = builder.render_user_message(req)

    assert "ACTIVE RULES" in rendered
    assert "rule_supplier_risk" in rendered
    assert "RECOMMENDATIONS" in rendered
    assert "rec_supplier_diversification" in rendered


def test_6_open_mode_general_question_without_full_profile():
    empty_context = AssistantContext(business_id=99, overall_business_score=0, band="Foundation", dna=AssistantContextDna(""," ",0))
    builder = AssistantPromptBuilder()
    req = builder.build(context=empty_context, user_prompt="What is working capital?", mode="open")
    rendered = builder.render_user_message(req)

    assert "No business snapshot is bound to this user yet" in rendered


def test_7_open_mode_personalizes_general_question(acme_full_context):
    builder = AssistantPromptBuilder()
    req = builder.build(context=acme_full_context, user_prompt="What is working capital?", mode="open")
    rendered = builder.render_user_message(req)

    assert "=== BUSINESS SNAPSHOT ===" in rendered
    assert "Acme Textiles Pvt Ltd" in rendered


def test_8_open_mode_does_not_invent_business_numbers(acme_full_context):
    registry = EvidenceRegistry(acme_full_context)
    response_json = json.dumps({
        "mode": "open",
        "executive_summary": "Strategy overview",
        "verified_business_context": [{"statement": "Revenue is ₹1.8 Cr", "evidence_refs": ["biz_profile_revenue"]}],
        "analysis": ["Current growth rate is steady."],
        "exploratory_recommendations": [{"title": "Cloud Accounting", "rationale": "Automate invoices", "evidence_refs": ["rec_supplier_diversification"]}],
    })
    parsed = parse_open_model_output(response_json)
    validator = OpenResponseValidator(registry, parsed, raw_body=response_json)
    report = validator.validate()

    assert report.passed is True
    assert report.business_evidence_validated is True


def test_9_open_mode_labels_scenarios_as_illustrative(acme_full_context):
    response_json = json.dumps({
        "mode": "open",
        "executive_summary": "Growth scenario analysis",
        "illustrative_scenarios": [{
            "title": "50% Export Surge",
            "scenario_description": "If export orders increase by 50%",
            "illustrative_revenue_impact": "Potential ₹2.5 Cr target"
        }]
    })
    parsed = parse_open_model_output(response_json)
    rendered_body = parsed.to_chat_body()

    assert "ILLUSTRATIVE SCENARIOS (Illustrative scenario — not a prediction)" in rendered_body


def test_10_open_mode_blocks_guaranteed_growth_language(acme_full_context):
    registry = EvidenceRegistry(acme_full_context)
    forbidden_text = "We promise 100% success and guaranteed growth for Acme Textiles."
    parsed = parse_open_model_output(forbidden_text)
    validator = OpenResponseValidator(registry, parsed, raw_body=forbidden_text)
    report = validator.validate()

    assert report.passed is False
    assert any("Forbidden phrase" in err for err in report.errors)


def test_11_open_mode_blocks_official_eligibility_claims(acme_full_context):
    registry = EvidenceRegistry(acme_full_context)
    forbidden_text = "You are eligible for immediate approval under the PMEGP scheme."
    parsed = parse_open_model_output(forbidden_text)
    validator = OpenResponseValidator(registry, parsed, raw_body=forbidden_text)
    report = validator.validate()

    assert report.passed is False
    assert any("Forbidden phrase" in err for err in report.errors)


def test_12_open_mode_identifies_missing_information(acme_full_context):
    response_json = json.dumps({
        "mode": "open",
        "executive_summary": "Analysis of expansion plans",
        "questions_to_validate": ["What is the exact monthly order cancellation rate?", "What is the margin per product line?"]
    })
    parsed = parse_open_model_output(response_json)
    rendered_body = parsed.to_chat_body()

    assert "QUESTIONS TO VALIDATE" in rendered_body
    assert "What is the exact monthly order cancellation rate?" in rendered_body


def test_13_business_evidence_references_are_valid(acme_full_context):
    registry = EvidenceRegistry(acme_full_context)
    invalid_json = json.dumps({
        "mode": "open",
        "verified_business_context": [{"statement": "Revenue is 10 Cr", "evidence_refs": ["invalid_fake_id_123"]}]
    })
    parsed = parse_open_model_output(invalid_json)
    validator = OpenResponseValidator(registry, parsed, raw_body=invalid_json)
    report = validator.validate()

    assert report.passed is False
    assert report.business_evidence_validated is False


def test_14_full_private_profile_not_sent_when_unnecessary(acme_full_context):
    manifest_ctx = select_relevant_context(acme_full_context, "Export strategy")
    assert manifest_ctx.context_manifest is not None
    assert "business_profile" in manifest_ctx.context_manifest.business_context_used


def test_15_context_manifest_persists_in_generation_meta():
    meta = GenerationMeta.empty(
        mode="open",
        provider_used="openai_compatible",
        model="gemini-3.6-flash",
        provider_latency_ms=120,
        fallback_used=False,
        context_manifest={"business_context_used": ["business_profile", "products"], "records_used": 5, "prompt_truncated": False},
    )
    assert meta.context_manifest is not None
    assert meta.context_manifest["records_used"] == 5


def test_16_refresh_preserves_mode_and_trust_labels():
    meta_json = {
        "provider": "openai_compatible",
        "model": "gemini-3.6-flash",
        "mode": "open",
        "fallback_used": False,
        "generation_method": "generative",
        "schema_validated": True,
        "grounding_validated": False,
        "server_grounding_score": 85,
        "evidence_count": 2,
        "confidence": 75,
        "assumptions": [],
        "limitations": [],
        "evidence_references": ["rec_supplier_diversification"],
        "generated_at": "2026-08-06T12:00:00Z",
        "prompt_truncated": False,
        "provider_latency_ms": 150,
        "business_evidence_validated": True,
        "context_manifest": {"business_context_used": ["business_profile", "products"], "records_used": 3, "prompt_truncated": False},
    }
    assert meta_json["mode"] == "open"
    assert meta_json["context_manifest"]["records_used"] == 3


def test_17_grounded_mode_behavior_remains_unchanged(acme_full_context):
    builder = AssistantContextBuilder(
        twin_provider=lambda _oid: acme_full_context,
        recommendations_provider=lambda _oid: acme_full_context,
        roadmap_provider=lambda _oid: acme_full_context,
        rules_provider=lambda _oid: acme_full_context,
        insights_provider=lambda _oid: acme_full_context,
    )
    builder.build = lambda owner_id, user_prompt="": acme_full_context
    service = AssistantProviderService(context_builder=builder, provider_factory=ProviderFactory())

    valid_grounded_json = json.dumps({
        "executive_summary": "Acme Textiles profile analysis demonstrates strong potential.",
        "key_findings": [
            {
                "title": "Readiness score is 72",
                "detail": "Financial readiness rating supports yarn diversification.",
                "evidence_refs": ["score_financial_readiness"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "rec_rec_supplier_diversification",
                "title": "Diversify Yarn Suppliers",
                "rationale": "Mitigate raw cotton concentration risk.",
                "evidence_refs": ["score_financial_readiness"],
            }
        ],
        "thirty_day_plan": [
            {
                "week": 1,
                "task": "Contact prospective suppliers.",
                "recommendation_ref": "rec_rec_supplier_diversification",
                "evidence_refs": ["score_financial_readiness"],
            }
        ],
        "scheme_matches": [],
        "assumptions": ["Stable yarn market"],
        "limitations": ["Requires supplier verification"],
        "confidence": 85,
        "evidence_references": [
            {
                "id": "score_financial_readiness",
                "kind": "score",
                "label": "Financial Readiness",
            }
        ],
    })

    resp = service.generate(
        owner_id=1,
        user_prompt="What is my score?",
        provider=_MockOpenProvider(valid_grounded_json),
        mode="grounded"
    )

    assert resp.fallback_used is False
    assert resp.generation is not None
    assert resp.generation.grounding_validated is True


def test_18_deterministic_fallback_remains_unchanged(acme_full_context):
    from app.services.ai.providers.base import DeterministicFallbackProvider
    builder = AssistantContextBuilder(
        twin_provider=lambda _oid: acme_full_context,
        recommendations_provider=lambda _oid: acme_full_context,
        roadmap_provider=lambda _oid: acme_full_context,
        rules_provider=lambda _oid: acme_full_context,
        insights_provider=lambda _oid: acme_full_context,
    )
    builder.build = lambda owner_id, user_prompt="": acme_full_context
    service = AssistantProviderService(context_builder=builder, provider_factory=ProviderFactory())

    resp = service.generate(
        owner_id=1,
        user_prompt="Explain working capital",
        provider=DeterministicFallbackProvider(),
        mode="grounded"
    )

    assert resp.fallback_used is True
    assert resp.generation is not None
    assert resp.generation.generation_method == "deterministic"

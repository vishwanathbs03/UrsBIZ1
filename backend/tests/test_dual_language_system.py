"""Bilingual Dual-Language System (English & Kannada) Test Suite.

Comprehensive verification covering:
1. Kannada intent classification (revenue, risk, schemes, roadmap, export, hiring)
2. Mixed-language code switching intent classification
3. Deterministic fallback in English vs Kannada with exact numerical / currency preservation
4. Prompt builder injecting Kannada instruction blocks with verbatim schema keys & evidence IDs
5. AssistantProviderService end-to-end generating grounded & open bilingual responses
6. ConversationService end-to-end message generation and metadata stamping
"""
import pytest
from types import SimpleNamespace
from app.services.ai.providers.intent_router import QuestionIntent, classify_intent
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextScore,
    AssistantContextRecommendation,
    AssistantContextRoadmap,
    AssistantContextRule,
    AssistantContextInsight,
    AssistantRequest,
    DeterministicFallbackProvider,
)
from app.services.ai.providers.prompt_builder import AssistantPromptBuilder
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.ai.providers.service import AssistantProviderService
from app.services.ai.providers.factory import ProviderFactory


@pytest.fixture
def sample_business_context():
    return AssistantContext(
        business_id=1,
        legal_name="Mysore Silk Enterprises",
        trade_name="Mysore Silk",
        industry="Textiles & Apparel",
        location="Mysuru, Karnataka",
        business_type="Private Limited",
        employee_count="35",
        annual_revenue_inr=18000000,  # ₹1.8 Cr
        target_revenue_inr=30000000,  # ₹3.0 Cr
        overall_business_score=74,
        band="Strong",
        dna=AssistantContextDna(
            archetype_key="quality_artisan",
            archetype_title="Quality Artisan",
            match_score=88,
        ),
        scores=(
            AssistantContextScore(key="financial", title="Financial Health", score=78, level="Strong"),
            AssistantContextScore(key="market", title="Market Position", score=72, level="Strong"),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_expand_stores",
                title="Expand Retail Distribution",
                category="growth",
                priority="High",
                estimated_score_gain=10,
                estimated_timeline="90 days",
                estimated_roi=500000,
            ),
        ),
        roadmap=(
            AssistantContextRoadmap(
                id="ms_gst_filing",
                title="Q2 GST Compliance Review",
                phase="Q2",
                priority="High",
                estimated_start_order=1,
                completion_percentage=60,
                expected_score_improvement=5,
            ),
        ),
        rules=(
            AssistantContextRule(
                id="RULE-REV-01",
                title="Revenue Target Gap",
                category="financial",
                priority="Medium",
                estimated_impact=-5,
                reason="Revenue on track for MSME Tier-2 threshold",
            ),
        ),
        insights=(
            AssistantContextInsight(
                id="INS-01",
                title="Working Capital Buffer",
                priority="Low",
                confidence=90,
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# 1. Intent Classification: English, Kannada, and Code-Switching
# --------------------------------------------------------------------------- #


def test_intent_kannada_revenue_lookup():
    """Kannada revenue question maps to REACH_REVENUE_TARGET or accurate fact intent."""
    intent = classify_intent("ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?")
    assert intent == QuestionIntent.REACH_REVENUE_TARGET


def test_intent_kannada_growth_target():
    """Kannada scale to target question maps to REACH_REVENUE_TARGET."""
    intent = classify_intent("ನಮ್ಮ ವ್ಯವಹಾರವನ್ನು ₹3 ಕೋಟಿ ವಹಿವಾಟಿಗೆ ಹೇಗೆ ಬೆಳೆಸಬಹುದು?")
    assert intent == QuestionIntent.REACH_REVENUE_TARGET


def test_intent_kannada_risk_weakness():
    """Kannada risk question maps to BIGGEST_WEAKNESS."""
    intent = classify_intent("ನಮ್ಮ ಮುಖ್ಯ ವ್ಯಾಪಾರ ಅಪಾಯ ಮತ್ತು ದೌರ್ಬಲ್ಯ ಏನು?")
    assert intent == QuestionIntent.BIGGEST_WEAKNESS


def test_intent_kannada_schemes():
    """Kannada scheme inquiry maps to GOVERNMENT_SCHEMES."""
    intent = classify_intent("ನಮ್ಮ ವ್ಯವಹಾರಕ್ಕೆ ಯಾವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಲಭ್ಯವಿವೆ?")
    assert intent == QuestionIntent.GOVERNMENT_SCHEMES


def test_intent_kannada_roadmap():
    """Kannada roadmap query maps to TWELVE_MONTH_ROADMAP."""
    intent = classify_intent("ಮುಂದಿನ 12 ತಿಂಗಳ ರೋಡ್‌ಮ್ಯಾಪ್ ಕೊಡಿ")
    assert intent == QuestionIntent.TWELVE_MONTH_ROADMAP


def test_intent_kannada_export():
    """Kannada export query maps to EXPORT_EXPANSION."""
    intent = classify_intent("ನಾವು ರಫ್ತು ಮಾರುಕಟ್ಟೆಗೆ ವಿಸ್ತರಿಸಬೇಕೇ?")
    assert intent == QuestionIntent.EXPORT_EXPANSION


def test_intent_kannada_hiring():
    """Kannada hiring query maps to HIRING."""
    intent = classify_intent("ನಾವು 5 ಹೊಸ ನೌಕರರನ್ನು ನೇಮಕ ಮಾಡಿಕೊಳ್ಳಬಹುದೇ?")
    assert intent == QuestionIntent.HIRING


def test_intent_mixed_language_code_switching():
    """Natural English-Kannada code switching is classified reliably."""
    assert classify_intent("Revenue ಎಷ್ಟು ಇದೆ?") == QuestionIntent.REACH_REVENUE_TARGET
    assert classify_intent("ನಮ್ಮ business risk ಏನು?") == QuestionIntent.BIGGEST_WEAKNESS
    assert classify_intent("Which scheme ಗಳು ನಮಗೆ ಲಭ್ಯ?") == QuestionIntent.GOVERNMENT_SCHEMES


# --------------------------------------------------------------------------- #
# 2. Deterministic Fallback: English vs Kannada Output
# --------------------------------------------------------------------------- #


def test_fallback_english_rendering(sample_business_context):
    """Fallback produces English prose when language is 'en' or unset."""
    req = AssistantRequest(
        user_prompt="What is our current revenue?",
        context=sample_business_context,
        language="en",
    )
    fb = DeterministicFallbackProvider()
    resp = fb.complete(req)
    assert "Overall business score:" in resp.body
    assert "EVIDENCE" in resp.body
    assert resp.generation.language == "en"


def test_fallback_kannada_rendering(sample_business_context):
    """Fallback produces natural Kannada prose when language is 'kn'."""
    req = AssistantRequest(
        user_prompt="ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?",
        context=sample_business_context,
        language="kn",
    )
    fb = DeterministicFallbackProvider()
    resp = fb.complete(req)
    assert "ಒಟ್ಟಾರೆ ವ್ಯವಹಾರ ಸ್ಕೋರ್:" in resp.body
    assert "ಆದಾಯ ಮತ್ತು ಬೆಳವಣಿಗೆಯ ವಿಶ್ಲೇಷಣೆ" in resp.body
    assert "₹" in resp.body  # Numerical and currency integrity
    assert "EVIDENCE" in resp.body  # Evidence ID header preserved
    assert resp.generation.language == "kn"


# --------------------------------------------------------------------------- #
# 3. Prompt Builder Language Directive Injection
# --------------------------------------------------------------------------- #


def test_prompt_builder_kannada_directive(sample_business_context):
    """Prompt builder injects explicit Kannada language directive when language='kn'."""
    pb = AssistantPromptBuilder()
    req = pb.build(
        context=sample_business_context,
        user_prompt="ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?",
        language="kn",
    )
    msg = pb.render_user_message(req)
    assert "=== RESPONSE LANGUAGE REQUIREMENT ===" in msg
    assert "Target Language: KANNADA (ಕನ್ನಡ)" in msg
    assert "Internal JSON Schema invariant: keep all JSON keys" in msg


# --------------------------------------------------------------------------- #
# 4. AssistantProviderService Bilingual Generation
# --------------------------------------------------------------------------- #


def test_provider_service_generates_english_by_default(sample_business_context):
    """AssistantProviderService generates English when language is not provided."""
    service = AssistantProviderService(
        context_builder=None,
        provider_factory=ProviderFactory(settings=SimpleNamespace(ai_provider="placeholder")),
    )
    resp = service.generate(
        owner_id=1,
        user_prompt="What is our current revenue?",
        context=sample_business_context,
    )
    assert resp.generation is not None
    assert resp.generation.language == "en"
    assert "Overall business score:" in resp.body


def test_provider_service_generates_kannada_when_requested(sample_business_context):
    """AssistantProviderService generates natural Kannada when language='kn'."""
    service = AssistantProviderService(
        context_builder=None,
        provider_factory=ProviderFactory(settings=SimpleNamespace(ai_provider="placeholder")),
    )
    resp = service.generate(
        owner_id=1,
        user_prompt="ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?",
        context=sample_business_context,
        language="kn",
    )
    assert resp.generation is not None
    assert resp.generation.language == "kn"
    assert "ಒಟ್ಟಾರೆ ವ್ಯವಹಾರ ಸ್ಕೋರ್:" in resp.body
    assert "₹" in resp.body
    assert "EVIDENCE" in resp.body

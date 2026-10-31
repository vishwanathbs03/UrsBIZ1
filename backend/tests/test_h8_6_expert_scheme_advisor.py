"""Test suite for Sprint H8.6 — Expert Scheme Advisory Engine Upgrade."""

import pytest
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextScheme,
)
from app.services.ai.schemes.advisor import ExpertSchemeAdvisor


@pytest.fixture
def sim_context() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


@pytest.fixture
def export_scheme() -> AssistantContextScheme:
    return AssistantContextScheme(
        scheme_id="scheme_mai_export",
        title="Market Access Initiative (MAI) Export Scheme",
        authority="Ministry of Commerce and Industry",
        application_url="https://mai.gov.in",
        profile_match_score=88,
        last_verified_date="2026-01-01",
    )


def test_1_expert_scheme_advisor_populates_all_8_fields(sim_context, export_scheme):
    """Verify ExpertSchemeAdvisor populates all 8 consultant fields."""
    advisor = ExpertSchemeAdvisor()
    advice = advisor.advise(export_scheme, sim_context)

    assert len(advice.why_eligible) >= 1
    assert len(advice.why_not_eligible_gaps) >= 1
    assert len(advice.documents_required) >= 1
    assert 0 <= advice.approval_probability_pct <= 100
    assert len(advice.preparation_checklist) >= 1
    assert advice.application_timeline != ""
    assert len(advice.common_rejection_reasons) >= 1
    assert len(advice.alternative_schemes) >= 1


def test_2_expert_scheme_markdown_formatting(sim_context, export_scheme):
    """Verify ExpertSchemeAdvice formats as a clean consultant-grade Markdown card."""
    advisor = ExpertSchemeAdvisor()
    advice = advisor.advise(export_scheme, sim_context)
    md = advice.to_markdown()

    assert "EXPERT ADVISORY:" in md
    assert "Why Your Business Qualifies" in md
    assert "Compliance Gaps to Address" in md
    assert "Mandatory Documentation Checklist" in md
    assert "Top Rejection Reasons" in md
    assert "Alternative / Secondary Schemes" in md

"""Test suite for Sprint H8.7 — One-Click Multi-Audience Executive Summary Suite."""

import pytest
from app.services.ai.providers.base import AssistantContext, AssistantContextDna
from app.services.ai.summaries.generator import ExecutiveSummarySuiteGenerator


@pytest.fixture
def sim_context() -> AssistantContext:
    return AssistantContext(
        business_id=1,
        legal_name="Acme Textiles",
        industry="Textiles",
        annual_revenue_inr=18000000,
        target_revenue_inr=30000000,
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


def test_1_executive_summary_suite_generates_7_cards(sim_context):
    """Verify ExecutiveSummarySuiteGenerator generates all 7 multi-audience cards."""
    gen = ExecutiveSummarySuiteGenerator()
    suite = gen.generate(sim_context)

    assert suite.ceo_summary.audience == "ceo"
    assert suite.investor_summary.audience == "investor"
    assert suite.bank_summary.audience == "bank"
    assert suite.export_summary.audience == "export"
    assert suite.risk_summary.audience == "risk"
    assert suite.growth_summary.audience == "growth"
    assert suite.compliance_summary.audience == "compliance"


def test_2_summary_cards_have_audience_metrics(sim_context):
    """Verify each card contains metrics_block, key_highlights, and strategic_recommendation."""
    gen = ExecutiveSummarySuiteGenerator()
    suite = gen.generate(sim_context)
    cards = [
        suite.ceo_summary,
        suite.investor_summary,
        suite.bank_summary,
        suite.export_summary,
        suite.risk_summary,
        suite.growth_summary,
        suite.compliance_summary,
    ]

    for card in cards:
        assert card.title != ""
        assert card.headline != ""
        assert len(card.metrics_block) >= 2
        assert len(card.key_highlights) >= 2
        assert card.strategic_recommendation != ""


def test_3_unified_markdown_report(sim_context):
    """Verify ExecutiveSummarySuite formats clean unified Markdown report."""
    gen = ExecutiveSummarySuiteGenerator()
    suite = gen.generate(sim_context)
    md = suite.to_markdown()

    assert "# URSBIZ EXECUTIVE SUMMARY SUITE" in md
    assert "CEO EXECUTIVE STRATEGIC BRIEF" in md
    assert "INVESTOR & EQUITY OVERVIEW" in md
    assert "BANK & LENDER CREDITWORTHINESS REPORT" in md

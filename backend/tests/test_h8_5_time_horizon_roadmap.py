"""Test suite for Sprint H8.5 — Multi-Horizon Action Roadmap Generator."""

import pytest
from app.services.ai.providers.base import AssistantContext, AssistantContextDna
from app.services.ai.roadmap.generator import TimeHorizonRoadmapGenerator


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


def test_1_roadmap_generation_4_horizons(sim_context):
    """Verify TimeHorizonRoadmapGenerator builds items across 30-day, 90-day, 6-month, and 1-year horizons."""
    gen = TimeHorizonRoadmapGenerator()
    roadmap = gen.generate(sim_context)

    assert len(roadmap.day_30_plan) >= 1
    assert len(roadmap.day_90_plan) >= 1
    assert len(roadmap.month_6_roadmap) >= 1
    assert len(roadmap.year_1_roadmap) >= 1


def test_2_roadmap_items_have_all_9_mandatory_attributes(sim_context):
    """Verify every roadmap milestone item contains all 9 mandatory judge attributes."""
    gen = TimeHorizonRoadmapGenerator()
    roadmap = gen.generate(sim_context)
    all_items = (
        roadmap.day_30_plan
        + roadmap.day_90_plan
        + roadmap.month_6_roadmap
        + roadmap.year_1_roadmap
    )

    for item in all_items:
        assert item.title != ""
        assert item.horizon in ("30_day", "90_day", "6_month", "1_year")
        assert item.priority in ("Critical", "High", "Medium")
        assert item.timeline != ""
        assert item.impact != ""
        assert item.cost != ""
        assert item.difficulty in ("Easy", "Moderate", "Challenging")
        assert isinstance(item.dependencies, tuple)
        assert item.expected_outcome != ""
        assert isinstance(item.risks, tuple)
        assert isinstance(item.success_metrics, tuple) and len(item.success_metrics) > 0


def test_3_roadmap_markdown_rendering(sim_context):
    """Verify TimeHorizonRoadmap formats as clean, judge-friendly Markdown tables."""
    gen = TimeHorizonRoadmapGenerator()
    roadmap = gen.generate(sim_context)
    md = roadmap.to_markdown()

    assert "EXECUTION-READY MULTI-HORIZON ROADMAP" in md
    assert "30-DAY IMMEDIATE ACTION PLAN" in md
    assert "90-DAY OPERATIONAL PLAN" in md
    assert "6-MONTH STRATEGIC ROADMAP" in md
    assert "1-YEAR TRANSFORMATION ROADMAP" in md
    assert "| Action Milestone | Priority | Timeline |" in md

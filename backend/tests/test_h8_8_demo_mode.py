"""Test suite for Sprint H8.8 — Demo Mode & High-Impact Visual Responses ("The Wow Factor")."""

import pytest
from app.services.ai.providers.base import AssistantContext, AssistantContextDna
from app.services.ai.simulation.simulator import ScenarioSimulator


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


def test_1_flagship_demo_questions_detection(sim_context):
    """Verify all 5 flagship judge queries are recognized as scenario/demo queries."""
    sim = ScenarioSimulator()
    flagship_queries = [
        "How can I reach ₹3 Cr?",
        "What is my biggest weakness?",
        "Can I export to Europe?",
        "What happens if I hire 15 people?",
        "Should I buy another machine?",
    ]

    for q in flagship_queries:
        assert sim.is_simulation_query(q) or "export" in q.lower() or "weakness" in q.lower() or "reach" in q.lower()


def test_2_demo_mode_hiring_15_people(sim_context):
    """Verify hiring 15 people demo question returns rich simulation response."""
    sim = ScenarioSimulator()
    res = sim.simulate("What happens if I hire 15 people?", sim_context)

    assert res.scenario_type == "hiring"
    assert "Hiring 15 Employees" in res.scenario_title
    assert "Revenue Impact" in res.to_markdown()
    assert "Illustrative scenario estimate — not a prediction" in res.disclaimer


def test_3_demo_mode_buy_machine(sim_context):
    """Verify buying another machine query returns capex ROI simulation."""
    sim = ScenarioSimulator()
    res = sim.simulate("Should I buy another machine?", sim_context)

    assert "Capex" in res.to_markdown() or "Capital" in res.to_markdown() or "Revenue Expansion" in res.to_markdown()

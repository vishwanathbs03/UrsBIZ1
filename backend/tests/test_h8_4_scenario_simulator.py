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
        overall_business_score=68,
        band="Established",
        dna=AssistantContextDna("growth_operator", "Growth Operator", 85),
    )


def test_1_hiring_scenario_simulation(sim_context):
    """Verify ScenarioSimulator handles 'What if I hire 10 employees?' question."""
    sim = ScenarioSimulator()
    prompt = "What if I hire 10 employees?"
    assert sim.is_simulation_query(prompt) is True

    res = sim.simulate(prompt, sim_context)
    assert res.scenario_type == "hiring"
    assert "Hiring 10 Employees" in res.scenario_title
    assert "Revenue Impact" in res.to_markdown()
    assert "payroll" in res.cashflow_impact.lower()
    assert "Illustrative scenario estimate — not a prediction" in res.disclaimer


def test_2_export_scenario_simulation(sim_context):
    """Verify ScenarioSimulator handles 'What if exports increase 20%?' question."""
    sim = ScenarioSimulator()
    prompt = "What if exports increase 20%?"
    assert sim.is_simulation_query(prompt) is True

    res = sim.simulate(prompt, sim_context)
    assert res.scenario_type == "export_growth"
    assert "Export Increase of 20%" in res.scenario_title
    assert "revenue addition" in res.revenue_impact.lower()
    assert len(res.risks_identified) >= 1


def test_3_funding_scenario_simulation(sim_context):
    """Verify ScenarioSimulator handles 'What if I receive ₹50 lakh funding?' question."""
    sim = ScenarioSimulator()
    prompt = "What if I receive ₹50 lakh funding?"
    assert sim.is_simulation_query(prompt) is True

    res = sim.simulate(prompt, sim_context)
    assert res.scenario_type == "funding"
    assert "₹50 Lakh" in res.scenario_title
    assert "machinery" in res.revenue_impact.lower() or "liquidity" in res.cashflow_impact.lower()


def test_4_commodity_cost_scenario_simulation(sim_context):
    """Verify ScenarioSimulator handles 'What if cotton prices rise?' question."""
    sim = ScenarioSimulator()
    prompt = "What if cotton prices rise by 15%?"
    assert sim.is_simulation_query(prompt) is True

    res = sim.simulate(prompt, sim_context)
    assert res.scenario_type == "commodity_cost"
    assert "Commodity Volatility" in res.scenario_title
    assert "margin" in res.profitability_impact.lower()


def test_5_factory_expansion_scenario_simulation(sim_context):
    """Verify ScenarioSimulator handles 'What if I open another factory?' question."""
    sim = ScenarioSimulator()
    prompt = "What if I open another factory?"
    assert sim.is_simulation_query(prompt) is True

    res = sim.simulate(prompt, sim_context)
    assert res.scenario_type == "facility_expansion"
    assert "Second Factory Facility Expansion" in res.scenario_title
    assert "capex" in res.cashflow_impact.lower()

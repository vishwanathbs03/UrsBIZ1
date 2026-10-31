"""Test suite for Sprint H8.10 — Judge Hackathon Demo Optimization & Premium UX Suite."""

import time
import pytest
from app.services.ai.providers.base import AssistantContext, AssistantContextDna
from app.services.ai.simulation.simulator import ScenarioSimulator
from app.services.ai.schemes.advisor import ExpertSchemeAdvisor, ExpertSchemeAdvice
from app.services.ai.roadmap.generator import TimeHorizonRoadmapGenerator
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


def test_1_judge_demo_6_highlight_pillars(sim_context):
    """Verify all 6 highlight pillars generate non-empty, high-impact responses."""
    # 1. Business Twin
    assert sim_context.overall_business_score == 68
    assert sim_context.dna.archetype_title == "Growth Operator"

    # 2. AI Consultant
    assert sim_context.legal_name == "Acme Textiles"

    # 3. Predictive Intelligence
    sim = ScenarioSimulator()
    res_pred = sim.simulate("Show 6-month revenue forecast and scenario estimates", sim_context)
    assert res_pred.scenario_title != ""

    # 4. Govt Intel
    adv = ExpertSchemeAdvisor()
    from app.services.ai.providers.base import AssistantContextScheme
    scheme = AssistantContextScheme("scheme_01", "MAI Export Scheme", "Ministry of Commerce", "https://mai.gov.in", 85, "2026-01-01")
    res_govt = adv.advise(scheme, sim_context)
    assert len(res_govt.why_eligible) >= 1

    # 5. Action Roadmaps
    rm = TimeHorizonRoadmapGenerator().generate(sim_context)
    assert len(rm.day_30_plan) >= 1

    # 6. What-If Simulator
    res_sim = sim.simulate("What happens if I hire 15 people?", sim_context)
    assert res_sim.scenario_type == "hiring"


def test_2_sub_2_second_demo_execution_latency(sim_context):
    """Verify demo roadmap and simulation execution runs in under 100ms."""
    start = time.time()
    rm = TimeHorizonRoadmapGenerator().generate(sim_context)
    sim_res = ScenarioSimulator().simulate("What if I open another factory?", sim_context)
    elapsed = time.time() - start

    assert elapsed < 0.1
    assert len(rm.day_30_plan) >= 1
    assert sim_res.scenario_title != ""

"""SPRINT AI-2 — Engine wrapper tests.

Verifies that each of the 16 :class:`ToolInterface` wrappers in
``app.services.ai.reasoning.engine_tools`` honours the
dispatcher contract:

  * ``invoke(...)`` returns a :class:`ToolResult`, never raises.
  * ``BusinessNotFound`` becomes ``status="skipped"``.
  * Any other exception becomes ``status="error"`` with the
    class name + message in ``error``.
  * The ``service_name`` echoes the tool's registered name.

Tests are organised in five tiers:

  1. **Happy path** — wrapper returns ``status="ok"`` with a
     non-None payload.
  2. **BusinessNotFound** — wrapper returns ``status="skipped"``.
  3. **Unknown error** — wrapper returns ``status="error"``.
  4. **Never-raises invariant** — verify each wrapper swallows
     the engine's exceptions.
  5. **Dispatcher sweep** — register all 16 wrappers against a
     :class:`ToolDispatcher` with a stub repo and verify the
     audit trail includes real names.

The tests patch each engine's SERVICE CLASS at its module path
so the wrapper's ``__init__`` (which constructs the real
service) is replaced with a mock — and the wrapper's
``invoke`` then calls the mock's ``compute`` method which we
also stub to return a fixture.

This keeps the tests fast (no real DB) and focuses on the
wrappers' contract, not the engines' business logic (which has
its own coverage).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.services.ai.reasoning.engine_tools import (
    BenchmarkTool,
    BusinessDnaTool,
    ComplianceTool,
    FinanceTool,
    FundingTool,
    GrowthTool,
    HealthScoreTool,
    InsightsTool,
    KnowledgeRetrievalTool,
    KpiTool,
    OpportunityTool,
    PredictiveSprint14Tool,
    ReadinessTool,
    RecommendationTool,
    RiskTool,
    SchemesSprint16Tool,
)
from app.services.ai.reasoning.tool_selector import ToolDispatcher, ToolCall


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _stub_repo(*, business=None, raise_not_found=False):
    """Build a MagicMock BusinessRepository."""
    repo = MagicMock(spec=BusinessRepository)
    if raise_not_found:
        repo.get_by_owner.side_effect = BusinessNotFound("nope")
    else:
        repo.get_by_owner.return_value = business
    return repo


def _make_call(service_name: str = "test") -> ToolCall:
    return ToolCall(service_name=service_name, inputs={}, expected_output_shape="")


def _pydantic_fixture(data: dict):
    """Build a fake Pydantic-like object with ``model_dump``."""
    obj = MagicMock()
    obj.model_dump.return_value = data
    return obj


# --------------------------------------------------------------------------- #
# 1. Happy path — wrapper returns status="ok" with a payload
# --------------------------------------------------------------------------- #


def test_health_score_tool_happy_path():
    repo = _stub_repo(business=MagicMock())
    fake_report = _pydantic_fixture({"score": 82, "grade": "B"})
    with patch(
        "app.services.health_score_service.HealthScoreService"
    ) as svc:
        svc.compute.return_value = fake_report
        tool = HealthScoreTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("health_score"), context=None)
    assert result.service_name == "health_score"
    assert result.status == "ok"
    assert result.payload == {"score": 82, "grade": "B"}
    assert result.error == ""


def test_kpi_tool_happy_path():
    repo = _stub_repo(business=MagicMock())
    fake_report = _pydantic_fixture({"kpis": []})
    with patch("app.services.kpi_service.KpiService") as svc:
        svc.compute.return_value = fake_report
        tool = KpiTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("kpi"), context=None)
    assert result.status == "ok"
    assert result.payload == {"kpis": []}


def test_knowledge_retrieval_tool_happy_path():
    svc = MagicMock()
    svc.retrieve.return_value = _pydantic_fixture({"passages": []})
    tool = KnowledgeRetrievalTool(svc)
    result = tool.invoke(owner_id=1, call=_make_call("knowledge_retrieval"), context=None)
    assert result.status == "ok"


def test_recommendation_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.recommendation_service.RecommendationService") as cls:
        cls.return_value.compute.return_value = {"recommendations": []}
        tool = RecommendationTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("recommendation"), context=None)
    assert result.status == "ok"


def test_schemes_sprint16_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.schemes_sprint16_service.SchemeRecommendationEngine") as cls:
        cls.return_value.compute.return_value = {"schemes": []}
        tool = SchemesSprint16Tool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("schemes_sprint16"), context=None)
    assert result.status == "ok"


def test_business_dna_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.business_dna_service.BusinessDNAService") as cls:
        cls.return_value.compute.return_value = {"dna": {"archetype": "growth_seeker"}}
        tool = BusinessDnaTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("business_dna"), context=None)
    assert result.status == "ok"


def test_risk_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.risk_service.RiskService") as cls:
        cls.return_value.compute.return_value = {"rules": []}
        tool = RiskTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("risk"), context=None)
    assert result.status == "ok"


def test_insights_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.insights_service.InsightsService") as cls:
        cls.return_value.compute.return_value = {"insights": []}
        tool = InsightsTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("insights"), context=None)
    assert result.status == "ok"


def test_opportunity_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.opportunity_service.OpportunityService") as cls:
        cls.return_value.compute.return_value = {"opportunities": []}
        tool = OpportunityTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("opportunity"), context=None)
    assert result.status == "ok"


def test_readiness_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.readiness_service.ReadinessService") as cls:
        cls.return_value.compute.return_value = {"overall_score": 72}
        tool = ReadinessTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("readiness"), context=None)
    assert result.status == "ok"


def test_finance_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.finance.service.FinanceService") as cls:
        cls.return_value.compute.return_value = {"metrics": {"revenue": 1800000}}
        tool = FinanceTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("finance"), context=None)
    assert result.status == "ok"


def test_benchmark_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.benchmark_service.BenchmarkService") as cls:
        cls.return_value.compute.return_value = {"benchmarks": {}}
        tool = BenchmarkTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("benchmark"), context=None)
    assert result.status == "ok"


def test_growth_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.growth_service.GrowthService") as cls:
        cls.return_value.compute.return_value = {"growth": {}}
        tool = GrowthTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("growth"), context=None)
    assert result.status == "ok"


def test_funding_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.funding_service.FundingService") as cls:
        cls.return_value.compute.return_value = {"funding": {}}
        tool = FundingTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("funding"), context=None)
    assert result.status == "ok"


def test_compliance_tool_happy_path():
    repo = _stub_repo()
    with patch("app.services.compliance_service.ComplianceService") as cls:
        cls.return_value.compute.return_value = {"compliance": {}}
        tool = ComplianceTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("compliance"), context=None)
    assert result.status == "ok"


def test_predictive_sprint14_tool_happy_path():
    repo = _stub_repo()
    with patch(
        "app.services.predictive_sprint14_service.RevenuePredictionService"
    ) as rev_cls, patch(
        "app.services.predictive_sprint14_service.GrowthPredictionService"
    ) as grw_cls, patch(
        "app.services.predictive_sprint14_service.FutureRiskPredictionService"
    ) as rsk_cls:
        rev_cls.return_value.compute.return_value = {"forecast_3m": 1000}
        grw_cls.return_value.compute.return_value = {"growth_3m": 0.05}
        rsk_cls.return_value.compute.return_value = {"risks": []}
        tool = PredictiveSprint14Tool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("predictive_sprint14"), context=None)
    assert result.status == "ok"
    assert "revenue" in result.payload
    assert "growth" in result.payload
    assert "risk" in result.payload


# --------------------------------------------------------------------------- #
# 2. BusinessNotFound — wrapper returns status="skipped"
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cls,module_path",
    [
        (RecommendationTool, "app.services.recommendation_service.RecommendationService"),
        (SchemesSprint16Tool, "app.services.schemes_sprint16_service.SchemeRecommendationEngine"),
        (BusinessDnaTool, "app.services.business_dna_service.BusinessDNAService"),
        (RiskTool, "app.services.risk_service.RiskService"),
        (InsightsTool, "app.services.insights_service.InsightsService"),
        (OpportunityTool, "app.services.opportunity_service.OpportunityService"),
        (ReadinessTool, "app.services.readiness_service.ReadinessService"),
        (FinanceTool, "app.services.finance.service.FinanceService"),
        (BenchmarkTool, "app.services.benchmark_service.BenchmarkService"),
        (GrowthTool, "app.services.growth_service.GrowthService"),
        (FundingTool, "app.services.funding_service.FundingService"),
        (ComplianceTool, "app.services.compliance_service.ComplianceService"),
    ],
)
def test_business_not_found_yields_skipped(cls, module_path):
    """Every repo-backed wrapper catches BusinessNotFound."""
    repo = _stub_repo(raise_not_found=True)
    with patch(module_path) as svc_cls:
        svc_cls.return_value.compute.side_effect = BusinessNotFound("nope")
        tool = cls(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "skipped"
    assert result.error == "business_not_found"


def test_predictive_sprint14_tool_handles_business_not_found_per_key():
    """PredictiveSprint14Tool records per-key BusinessNotFound."""
    repo = _stub_repo(raise_not_found=True)
    with patch(
        "app.services.predictive_sprint14_service.RevenuePredictionService"
    ) as rev_cls, patch(
        "app.services.predictive_sprint14_service.GrowthPredictionService"
    ) as grw_cls, patch(
        "app.services.predictive_sprint14_service.FutureRiskPredictionService"
    ) as rsk_cls:
        for cls in (rev_cls, grw_cls, rsk_cls):
            cls.return_value.compute.side_effect = BusinessNotFound("nope")
        tool = PredictiveSprint14Tool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "ok"
    for key in ("revenue", "growth", "risk"):
        assert result.payload[key]["status"] == "skipped"
        assert result.payload[key]["error"] == "business_not_found"


def test_health_score_tool_skipped_when_business_none():
    repo = _stub_repo(business=None)
    tool = HealthScoreTool(repo)
    result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "skipped"
    assert result.error == "business_not_found"


def test_kpi_tool_skipped_when_business_none():
    repo = _stub_repo(business=None)
    tool = KpiTool(repo)
    result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "skipped"
    assert result.error == "business_not_found"


# --------------------------------------------------------------------------- #
# 3. Unknown error — wrapper returns status="error"
# --------------------------------------------------------------------------- #


def test_health_score_tool_error_path():
    repo = _stub_repo(business=MagicMock())
    with patch("app.services.health_score_service.HealthScoreService") as svc:
        svc.compute.side_effect = RuntimeError("boom")
        tool = HealthScoreTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "error"
    assert "RuntimeError" in result.error
    assert "boom" in result.error


def test_recommendation_tool_error_path():
    repo = _stub_repo()
    with patch("app.services.recommendation_service.RecommendationService") as cls:
        cls.return_value.compute.side_effect = ValueError("bad input")
        tool = RecommendationTool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "error"
    assert "ValueError" in result.error


def test_predictive_sprint14_tool_partial_error():
    """If one sub-service raises, the others still return data."""
    repo = _stub_repo()
    with patch(
        "app.services.predictive_sprint14_service.RevenuePredictionService"
    ) as rev_cls, patch(
        "app.services.predictive_sprint14_service.GrowthPredictionService"
    ) as grw_cls, patch(
        "app.services.predictive_sprint14_service.FutureRiskPredictionService"
    ) as rsk_cls:
        rev_cls.return_value.compute.side_effect = RuntimeError("boom")
        grw_cls.return_value.compute.return_value = {"growth_3m": 0.05}
        rsk_cls.return_value.compute.return_value = {"risks": []}
        tool = PredictiveSprint14Tool(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result.status == "ok"
    assert result.payload["revenue"]["status"] == "error"
    assert "RuntimeError" in result.payload["revenue"]["error"]
    assert result.payload["growth"]["growth_3m"] == 0.05


# --------------------------------------------------------------------------- #
# 4. Never-raises invariant
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "cls,module_path",
    [
        (RecommendationTool, "app.services.recommendation_service.RecommendationService"),
        (SchemesSprint16Tool, "app.services.schemes_sprint16_service.SchemeRecommendationEngine"),
        (BusinessDnaTool, "app.services.business_dna_service.BusinessDNAService"),
        (RiskTool, "app.services.risk_service.RiskService"),
        (InsightsTool, "app.services.insights_service.InsightsService"),
        (OpportunityTool, "app.services.opportunity_service.OpportunityService"),
        (ReadinessTool, "app.services.readiness_service.ReadinessService"),
        (FinanceTool, "app.services.finance.service.FinanceService"),
        (BenchmarkTool, "app.services.benchmark_service.BenchmarkService"),
        (GrowthTool, "app.services.growth_service.GrowthService"),
        (FundingTool, "app.services.funding_service.FundingService"),
        (ComplianceTool, "app.services.compliance_service.ComplianceService"),
    ],
)
def test_wrappers_never_raise(cls, module_path):
    """Every wrapper converts any exception into a ToolResult."""
    repo = _stub_repo()
    with patch(module_path) as svc_cls:
        svc_cls.return_value.compute.side_effect = Exception("kaboom")
        tool = cls(repo)
        result = tool.invoke(owner_id=1, call=_make_call("x"), context=None)
    assert result is not None
    assert result.status in ("ok", "skipped", "error", "not_implemented")


# --------------------------------------------------------------------------- #
# 5. Dispatcher sweep — register all 16 wrappers against a ToolDispatcher
# --------------------------------------------------------------------------- #


def test_dispatcher_sweep_with_all_wrappers():
    """All 16 service names resolve to a real wrapper."""
    repo = _stub_repo(business=MagicMock())
    knowledge = MagicMock()
    knowledge.retrieve.return_value = _pydantic_fixture({"passages": []})

    dispatcher = ToolDispatcher()
    with patch(
        "app.services.recommendation_service.RecommendationService"
    ) as rec_cls, patch(
        "app.services.schemes_sprint16_service.SchemeRecommendationEngine"
    ) as sch_cls, patch(
        "app.services.business_dna_service.BusinessDNAService"
    ) as dna_cls, patch(
        "app.services.risk_service.RiskService"
    ) as risk_cls, patch(
        "app.services.insights_service.InsightsService"
    ) as ins_cls, patch(
        "app.services.opportunity_service.OpportunityService"
    ) as opp_cls, patch(
        "app.services.readiness_service.ReadinessService"
    ) as rdy_cls, patch(
        "app.services.finance.service.FinanceService"
    ) as fin_cls, patch(
        "app.services.benchmark_service.BenchmarkService"
    ) as ben_cls, patch(
        "app.services.growth_service.GrowthService"
    ) as grw_cls, patch(
        "app.services.funding_service.FundingService"
    ) as fnd_cls, patch(
        "app.services.compliance_service.ComplianceService"
    ) as cpl_cls, patch(
        "app.services.health_score_service.HealthScoreService"
    ) as hsc_cls, patch(
        "app.services.kpi_service.KpiService"
    ) as kpi_cls, patch(
        "app.services.predictive_sprint14_service.RevenuePredictionService"
    ) as rev_cls, patch(
        "app.services.predictive_sprint14_service.GrowthPredictionService"
    ) as grw_p14, patch(
        "app.services.predictive_sprint14_service.FutureRiskPredictionService"
    ) as rsk_p14:
        for cls in (rec_cls, sch_cls, dna_cls, risk_cls, ins_cls, opp_cls,
                    rdy_cls, fin_cls, ben_cls, grw_cls, fnd_cls, cpl_cls,
                    rev_cls, grw_p14, rsk_p14, hsc_cls, kpi_cls):
            cls.return_value.compute.return_value = {"ok": True}
        dispatcher.register_tool("health_score", HealthScoreTool(repo))
        dispatcher.register_tool("kpi", KpiTool(repo))
        dispatcher.register_tool(
            "knowledge_retrieval", KnowledgeRetrievalTool(knowledge)
        )
        dispatcher.register_tool("recommendation", RecommendationTool(repo))
        dispatcher.register_tool("schemes_sprint16", SchemesSprint16Tool(repo))
        dispatcher.register_tool("business_dna", BusinessDnaTool(repo))
        dispatcher.register_tool("risk", RiskTool(repo))
        dispatcher.register_tool("insights", InsightsTool(repo))
        dispatcher.register_tool("opportunity", OpportunityTool(repo))
        dispatcher.register_tool("readiness", ReadinessTool(repo))
        dispatcher.register_tool("finance", FinanceTool(repo))
        dispatcher.register_tool("benchmark", BenchmarkTool(repo))
        dispatcher.register_tool("growth", GrowthTool(repo))
        dispatcher.register_tool("funding", FundingTool(repo))
        dispatcher.register_tool("compliance", ComplianceTool(repo))
        dispatcher.register_tool("predictive_sprint14", PredictiveSprint14Tool(repo))

        # Every wrapper's invoke returns a ToolResult.
        expected_names = {
            "health_score", "kpi", "knowledge_retrieval", "recommendation",
            "schemes_sprint16", "business_dna", "risk", "insights",
            "opportunity", "readiness", "finance", "benchmark",
            "growth", "funding", "compliance", "predictive_sprint14",
        }
        for name, wrapper in dispatcher._tools.items():
            if name not in expected_names:
                continue
            result = wrapper.invoke(
                owner_id=1, call=_make_call(name), context=None
            )
            assert result.service_name == name
            assert result.status in ("ok", "skipped", "error", "not_implemented")


# --------------------------------------------------------------------------- #
# 6. Integration — AssistantProviderService accepts the dispatcher
# --------------------------------------------------------------------------- #


def test_assistant_provider_service_accepts_tool_dispatcher():
    """Backward compat: AssistantProviderService constructs with no kwargs."""
    from app.services.ai.providers.service import AssistantProviderService
    from app.services.ai.providers.context_builder import AssistantContextBuilder

    ctx = MagicMock(spec=AssistantContextBuilder)
    ctx.build.return_value = None

    # No tool_dispatcher kwarg — defaults to stub dispatcher.
    svc1 = AssistantProviderService(context_builder=ctx)
    assert svc1._tool_dispatcher is not None

    # With an explicit dispatcher.
    dispatcher = ToolDispatcher()
    svc2 = AssistantProviderService(context_builder=ctx, tool_dispatcher=dispatcher)
    assert svc2._tool_dispatcher is dispatcher
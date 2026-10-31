"""SPRINT AI-2 — Real ToolInterface wrappers for the 16 deterministic engines.

Each wrapper is a thin shim around an existing engine that already
powers other parts of the system (the deterministic-fallback
renderer, the standalone /api endpoints, the dashboard, etc.).

The shims exist for one reason: the chat assistant's tool
dispatcher expects every tool to satisfy the
:class:`ToolInterface` Protocol — a synchronous
``invoke(*, owner_id, call, context) -> ToolResult`` contract that
never raises. The underlying engines raise ``BusinessNotFound`` for
missing businesses and may raise anything else on bugs. The
shims translate those exceptions into ``ToolResult`` so the
dispatcher contract holds.

Wrapper anatomy
---------------

Every wrapper follows the same template::

    class XTool:
        name = "x"

        def __init__(self, repo_or_singleton) -> None: ...

        def invoke(self, *, owner_id, call, context):
            t0 = time.perf_counter()
            try:
                payload = self._service.compute(owner_id)
                return ToolResult(self.name, "ok", _to_dict(payload), _ms(t0))
            except BusinessNotFound:
                return ToolResult(self.name, "skipped", None, 0, "business_not_found")
            except Exception as exc:
                return ToolResult(self.name, "error", None, _ms(t0), f"{type(exc).__name__}: {exc}")

The constructors fall into three camps:

  * **Repo-backed** — most engines take a
    ``BusinessRepository``. The chat endpoint constructs them
    once per request inside ``_service(db)``.
  * **Stateless** — ``HealthScoreService`` and ``KpiService``
    have no ``__init__`` (they are static helpers around a
    ``Business`` instance). The wrappers take a
    ``BusinessRepository`` so they can fetch the business.
  * **Singleton** — ``KnowledgeRetrievalService`` is a
    process-level singleton built from
    ``JsonKnowledgeRepository``. The wrapper takes the
    singleton itself.

The ``PredictiveSprint14Tool`` combines the three Sprint 14
sub-services (``RevenuePredictionService``,
``GrowthPredictionService``, ``FutureRiskPredictionService``) into
one wrapper because they all read the same ``Business`` + DNA +
Health + Readiness inputs — splitting them into three tool calls
would inflate the audit trail without buying any new signal.
"""
from __future__ import annotations

import time
from dataclasses import asdict, is_dataclass
from typing import Any

from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.services.ai.reasoning.tool_selector import ToolResult


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _ms(t0: float) -> int:
    """Return milliseconds elapsed since ``t0`` (perf_counter)."""
    return int((time.perf_counter() - t0) * 1000)


def _to_dict(obj: Any) -> Any:
    """Coerce engine output to a JSON-friendly structure.

    The engines return a mix of Pydantic v2 models, dataclasses,
    plain dicts, and ``BaseModel`` subclasses. We try each
    serialiser in turn. Failures fall through to ``str(obj)``
    so the audit trail always has SOMETHING to record.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    # Pydantic v2 first (``hasattr`` guard avoids the deprecation
    # path on v1).
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1 fallback.
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        except Exception:
            pass
    return str(obj)


def _skipped(name: str, reason: str) -> ToolResult:
    return ToolResult(
        service_name=name,
        status="skipped",
        payload=None,
        duration_ms=0,
        error=reason,
    )


def _ok(name: str, payload: Any, t0: float) -> ToolResult:
    return ToolResult(
        service_name=name,
        status="ok",
        payload=_to_dict(payload),
        duration_ms=_ms(t0),
        error="",
    )


def _error(name: str, exc: Exception, t0: float) -> ToolResult:
    return ToolResult(
        service_name=name,
        status="error",
        payload=None,
        duration_ms=_ms(t0),
        error=f"{type(exc).__name__}: {exc}",
    )


def _safe_invoke(name: str, fn, t0: float) -> ToolResult:
    """Wrap an engine call with the standard except-clauses."""
    try:
        return _ok(name, fn(), t0)
    except BusinessNotFound:
        return _skipped(name, "business_not_found")
    except Exception as exc:  # noqa: BLE001 — dispatcher contract forbids raises
        return _error(name, exc, t0)


# --------------------------------------------------------------------------- #
# 1. HealthScoreTool — static, needs Business
# --------------------------------------------------------------------------- #


class HealthScoreTool:
    """ToolInterface wrapper for :class:`HealthScoreService`."""

    name = "health_score"

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            from app.services.health_score_service import HealthScoreService

            business = self._repo.get_by_owner(owner_id)
            if business is None:
                return _skipped(self.name, "business_not_found")
            report = HealthScoreService.compute(business)
            return _ok(self.name, report, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 2. KpiTool — static, needs Business
# --------------------------------------------------------------------------- #


class KpiTool:
    """ToolInterface wrapper for :class:`KpiService`."""

    name = "kpi"

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            from app.services.kpi_service import KpiService

            business = self._repo.get_by_owner(owner_id)
            if business is None:
                return _skipped(self.name, "business_not_found")
            report = KpiService.compute(business)
            return _ok(self.name, report, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 3. KnowledgeRetrievalTool — singleton wrapper
# --------------------------------------------------------------------------- #


class KnowledgeRetrievalTool:
    """ToolInterface wrapper for the knowledge retrieval singleton.

    The chat endpoint already maintains a process-level
    ``JsonKnowledgeRepository`` singleton via
    ``_get_knowledge_repository()``. That singleton is wrapped
    into a ``KnowledgeRetrievalService`` once per request; this
    wrapper accepts the service.
    """

    name = "knowledge_retrieval"

    def __init__(self, service: Any) -> None:
        self._service = service

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            # Knowledge retrieval is keyed by a query string.
            # The tool call's ``inputs`` carries the query
            # (default: empty string — full-corpus scan).
            inputs = getattr(call, "inputs", {}) or {}
            query = str(inputs.get("query", "") or "")
            result = self._service.retrieve(query=query, top_k=3)
            return _ok(self.name, result, t0)
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 4. RecommendationTool — repo-backed, owner_id dispatch
# --------------------------------------------------------------------------- #


class RecommendationTool:
    """ToolInterface wrapper for :class:`RecommendationService`."""

    name = "recommendation"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.recommendation_service import RecommendationService

        self._service = RecommendationService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 5. SchemesSprint16Tool — repo-backed
# --------------------------------------------------------------------------- #


class SchemesSprint16Tool:
    """ToolInterface wrapper for the schemes engine."""

    name = "schemes_sprint16"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.schemes_sprint16_service import SchemeRecommendationEngine

        self._service = SchemeRecommendationEngine(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 6. BusinessDnaTool — repo-backed
# --------------------------------------------------------------------------- #


class BusinessDnaTool:
    """ToolInterface wrapper for :class:`BusinessDNAService`."""

    name = "business_dna"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.business_dna_service import BusinessDNAService

        self._service = BusinessDNAService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 7. RiskTool — repo-backed
# --------------------------------------------------------------------------- #


class RiskTool:
    """ToolInterface wrapper for :class:`RiskService`."""

    name = "risk"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.risk_service import RiskService

        self._service = RiskService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 8. InsightsTool — repo-backed
# --------------------------------------------------------------------------- #


class InsightsTool:
    """ToolInterface wrapper for :class:`InsightsService`."""

    name = "insights"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.insights_service import InsightsService

        self._service = InsightsService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 9. OpportunityTool — repo-backed
# --------------------------------------------------------------------------- #


class OpportunityTool:
    """ToolInterface wrapper for :class:`OpportunityService`."""

    name = "opportunity"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.opportunity_service import OpportunityService

        self._service = OpportunityService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 10. ReadinessTool — repo-backed
# --------------------------------------------------------------------------- #


class ReadinessTool:
    """ToolInterface wrapper for :class:`ReadinessService`."""

    name = "readiness"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.readiness_service import ReadinessService

        self._service = ReadinessService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 11. FinanceTool — repo-backed
# --------------------------------------------------------------------------- #


class FinanceTool:
    """ToolInterface wrapper for :class:`FinanceService`."""

    name = "finance"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.finance.service import FinanceService

        self._service = FinanceService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 12. BenchmarkTool — repo-backed
# --------------------------------------------------------------------------- #


class BenchmarkTool:
    """ToolInterface wrapper for :class:`BenchmarkService`."""

    name = "benchmark"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.benchmark_service import BenchmarkService

        self._service = BenchmarkService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 13. GrowthTool — repo-backed
# --------------------------------------------------------------------------- #


class GrowthTool:
    """ToolInterface wrapper for :class:`GrowthService`."""

    name = "growth"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.growth_service import GrowthService

        self._service = GrowthService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 14. FundingTool — repo-backed
# --------------------------------------------------------------------------- #


class FundingTool:
    """ToolInterface wrapper for :class:`FundingService`."""

    name = "funding"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.funding_service import FundingService

        self._service = FundingService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 15. ComplianceTool — repo-backed
# --------------------------------------------------------------------------- #


class ComplianceTool:
    """ToolInterface wrapper for :class:`ComplianceService`."""

    name = "compliance"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.compliance_service import ComplianceService

        self._service = ComplianceService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            result = self._service.compute(owner_id)
            return _ok(self.name, result, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# 16. PredictiveSprint14Tool — combined (revenue + growth + risk)
# --------------------------------------------------------------------------- #


class PredictiveSprint14Tool:
    """ToolInterface wrapper for the three Sprint 14 prediction engines.

    The three sub-services all read the same
    ``Business`` + DNA + Health + Readiness inputs and run in
    <100ms each. Splitting them into three tool calls would
    triple the audit-trail size without buying any new signal.
    One wrapper returns a combined payload::

        {
            "revenue": RevenuePredictionResponse,
            "growth": GrowthPredictionResponse,
            "risk": FutureRiskPredictionResponse,
        }

    If any sub-service raises (other than ``BusinessNotFound``)
    the wrapper records the error per-key in the payload and
    still returns ``status="ok"`` so the LLM can use the
    partial output.
    """

    name = "predictive_sprint14"

    def __init__(self, repo: BusinessRepository) -> None:
        from app.services.predictive_sprint14_service import (
            FutureRiskPredictionService,
            GrowthPredictionService,
            RevenuePredictionService,
        )

        self._revenue = RevenuePredictionService(repo)
        self._growth = GrowthPredictionService(repo)
        self._risk = FutureRiskPredictionService(repo)

    def invoke(self, *, owner_id: int, call: Any, context: Any) -> ToolResult:
        t0 = time.perf_counter()
        try:
            payload: dict[str, Any] = {}
            for key, service in (
                ("revenue", self._revenue),
                ("growth", self._growth),
                ("risk", self._risk),
            ):
                try:
                    payload[key] = _to_dict(service.compute(owner_id))
                except BusinessNotFound:
                    payload[key] = {"status": "skipped", "error": "business_not_found"}
                except Exception as exc:  # noqa: BLE001
                    payload[key] = {
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
            return _ok(self.name, payload, t0)
        except BusinessNotFound:
            return _skipped(self.name, "business_not_found")
        except Exception as exc:
            return _error(self.name, exc, t0)


# --------------------------------------------------------------------------- #
# All-wrappers registry — convenient single import for the chat endpoint
# --------------------------------------------------------------------------- #


# Order matches the SUCCESS CONDITION table in the SPRINT AI-2
# plan. The chat endpoint registers these against the dispatcher
# in the same order so the audit trail reads top-to-bottom
# from the most-frequently-called to the most-specialised.
ALL_TOOL_CLASSES = (
    HealthScoreTool,
    KpiTool,
    RecommendationTool,
    SchemesSprint16Tool,
    BusinessDnaTool,
    RiskTool,
    InsightsTool,
    OpportunityTool,
    ReadinessTool,
    FinanceTool,
    BenchmarkTool,
    GrowthTool,
    FundingTool,
    ComplianceTool,
    PredictiveSprint14Tool,
)


__all__ = [
    "ALL_TOOL_CLASSES",
    "BenchmarkTool",
    "BusinessDnaTool",
    "ComplianceTool",
    "FinanceTool",
    "FundingTool",
    "GrowthTool",
    "HealthScoreTool",
    "InsightsTool",
    "KnowledgeRetrievalTool",
    "KpiTool",
    "OpportunityTool",
    "PredictiveSprint14Tool",
    "ReadinessTool",
    "RecommendationTool",
    "RiskTool",
    "SchemesSprint16Tool",
]
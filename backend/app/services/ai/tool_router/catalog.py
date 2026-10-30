"""SPRINT AI-8 — Tool catalog.

The catalog is the single source of truth for the 12
whitelisted tools the LLM may request. Each entry binds:

  * a stable tool name (``get_business_profile`` ...)
  * a one-line description (shown to the LLM in the
    system-prompt block)
  * the Pydantic arg schema (validates ``arguments``)
  * an engine name (``ToolInterface.name``) — the AI-2
    wrapper that actually runs the call
  * an EvidenceKind — which registry taxonomy the router
    should stamp the output with
  * an ``intents`` frozenset — which classified intents
    are allowed to call this tool (step 4 of the pipeline)

``INTENT_COMPATIBILITY`` is the inverse map: given a
:class:`QuestionIntent`, which tools can the LLM request?
Used at step 4.

The catalog never holds an instance of the engine — only a
*name* and a resolver callback. The router receives a
``ToolDispatcher`` (or any mapping from engine name →
ToolInterface) and asks for the engine lazily. This keeps
the catalog pure: constructing one does not require a
repository / DB / request context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from app.services.ai.providers.evidence_registry import EvidenceKind

from app.services.ai.tool_router.types import (
    CompareRecommendationsArgs,
    ForecastArgs,
    GrowthArgs,
    KpiArgs,
    RecommendationArgs,
    RoadmapArgs,
    ScenarioArgs,
)


# --------------------------------------------------------------------------- #
# Specs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToolSpec:
    """One row in the catalog.

    Fields
    ------
    name:
        The stable tool name the LLM emits (and what the
        frontend renders in the ReasoningTrace pill row).
    description:
        A short, single-sentence description rendered into
        the system prompt so the LLM knows what the tool
        returns. Must NOT mention internal engine names.
    arg_schema:
        The Pydantic model that validates the tool's
        ``arguments``. ``None`` means "no arguments".
    engine_name:
        The AI-2 ``ToolInterface.name`` to dispatch through
        the ``ToolDispatcher``. Matches
        ``engine_tools.ALL_TOOL_CLASSES[*].name`` exactly.
    evidence_kind:
        Which :class:`EvidenceKind` the router stamps onto
        the output. Drives the registry lookup + UI hyperlink.
    intents:
        The frozenset of classified intents (string labels)
        this tool is allowed for. Used at step 4 of the
        pipeline to reject cross-intent tool drift.
    rationale:
        One-line audit explanation — who/what is this tool
        backed by. Shown in the audit log only.
    """

    name: str
    description: str
    arg_schema: type[BaseModel] | None
    engine_name: str
    evidence_kind: EvidenceKind
    intents: frozenset[str]
    rationale: str = ""


# --------------------------------------------------------------------------- #
# Intent vocabulary
# --------------------------------------------------------------------------- #
#
# The strings match ``QuestionIntent`` values produced by
# ``app.services.ai.providers.intent_router``. AI-8 lets the
# LLM request a tool only when the caller's intent is in
# ``ToolSpec.intents``. The ``GENERAL`` intent is a fallback
# allowed for every tool — the LLM may legitimately want to
# query the business profile or analytics even when no
# specialist intent fired.

_INTENT_GENERAL = "general"

# Existing QuestionIntent values (kept here as strings so this
# module doesn't reach into the intent_router — avoids any
# import cycle).
_INTENT_HIRING = "hiring"
_INTENT_REACH_REVENUE_TARGET = "reach_revenue_target"
_INTENT_BIGGEST_WEAKNESS = "biggest_weakness"
_INTENT_GOVERNMENT_SCHEMES = "government_schemes"
_INTENT_TWELVE_MONTH_ROADMAP = "twelve_month_roadmap"
_INTENT_EXPORT_EXPANSION = "export_expansion"

_ALL_INTENTS = frozenset(
    {
        _INTENT_HIRING,
        _INTENT_REACH_REVENUE_TARGET,
        _INTENT_BIGGEST_WEAKNESS,
        _INTENT_GOVERNMENT_SCHEMES,
        _INTENT_TWELVE_MONTH_ROADMAP,
        _INTENT_EXPORT_EXPANSION,
        _INTENT_GENERAL,
    }
)


# --------------------------------------------------------------------------- #
# TOOL_REGISTRY — the 12 whitelisted tools
# --------------------------------------------------------------------------- #

TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_business_profile": ToolSpec(
        name="get_business_profile",
        description=(
            "Returns the business DNA profile (industry, location, "
            "type, employee count, archetype)."
        ),
        arg_schema=None,
        engine_name="business_dna",
        evidence_kind=EvidenceKind.DNA,
        # Profile is meta — every intent is allowed to ask
        # for it (e.g. "tell me about my business").
        intents=_ALL_INTENTS,
        rationale="BusinessDNAService via BusinessDnaTool (AI-2).",
    ),
    "get_health_score": ToolSpec(
        name="get_health_score",
        description=(
            "Returns the overall business health score (0–100) + "
            "level (Critical / Developing / Strong)."
        ),
        arg_schema=None,
        engine_name="health_score",
        evidence_kind=EvidenceKind.SCORE,
        intents=frozenset(
            {
                _INTENT_BIGGEST_WEAKNESS,
                _INTENT_HIRING,
                _INTENT_GENERAL,
            }
        ),
        rationale="HealthScoreService via HealthScoreTool (AI-2).",
    ),
    "get_risks": ToolSpec(
        name="get_risks",
        description=(
            "Returns the active risk rules for the business "
            "(priority, category, reason, mitigation)."
        ),
        arg_schema=None,
        engine_name="risk",
        evidence_kind=EvidenceKind.RULE,
        intents=frozenset(
            {
                _INTENT_BIGGEST_WEAKNESS,
                _INTENT_HIRING,
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_GOVERNMENT_SCHEMES,
                _INTENT_GENERAL,
            }
        ),
        rationale="RiskService via RiskTool (AI-2).",
    ),
    "get_recommendations": ToolSpec(
        name="get_recommendations",
        description=(
            "Returns the top recommended actions for the business, "
            "ranked by priority + estimated score gain."
        ),
        arg_schema=RecommendationArgs,
        engine_name="recommendation",
        evidence_kind=EvidenceKind.RECOMMENDATION,
        intents=_ALL_INTENTS,
        rationale="RecommendationService via RecommendationTool (AI-2).",
    ),
    "get_schemes": ToolSpec(
        name="get_schemes",
        description=(
            "Returns government scheme matches keyed off industry + "
            "location (PMEGP, MUDRA, ZED, state schemes, ...)."
        ),
        arg_schema=None,
        engine_name="schemes_sprint16",
        evidence_kind=EvidenceKind.SCHEME,
        intents=frozenset(
            {
                _INTENT_GOVERNMENT_SCHEMES,
                _INTENT_EXPORT_EXPANSION,
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_GENERAL,
            }
        ),
        rationale="SchemeRecommendationEngine via SchemesSprint16Tool (AI-2).",
    ),
    "get_forecast": ToolSpec(
        name="get_forecast",
        description=(
            "Returns the Sprint-14 revenue + growth + risk forecast "
            "for a given horizon in months."
        ),
        arg_schema=ForecastArgs,
        engine_name="predictive_sprint14",
        evidence_kind=EvidenceKind.FORECAST,
        intents=frozenset(
            {
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_TWELVE_MONTH_ROADMAP,
                _INTENT_HIRING,
                _INTENT_GENERAL,
            }
        ),
        rationale="RevenuePredictionService + Growth + FutureRisk via PredictiveSprint14Tool (AI-2).",
    ),
    "get_roadmap": ToolSpec(
        name="get_roadmap",
        description=(
            "Returns the business roadmap (quarterly milestones) "
            "for a given horizon in months."
        ),
        arg_schema=RoadmapArgs,
        engine_name="roadmap",   # NEW wrapper in business_tools.py
        evidence_kind=EvidenceKind.RECOMMENDATION,
        intents=frozenset(
            {
                _INTENT_TWELVE_MONTH_ROADMAP,
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_GENERAL,
            }
        ),
        rationale="RoadmapService (NEW thin wrapper RoadmapServiceTool — AI-8).",
    ),
    "calculate_revenue_growth": ToolSpec(
        name="calculate_revenue_growth",
        description=(
            "Returns the revenue growth percentage between two "
            "periods (e.g. FY24 → FY25)."
        ),
        arg_schema=GrowthArgs,
        engine_name="growth",
        evidence_kind=EvidenceKind.SCORE,
        intents=frozenset(
            {
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_TWELVE_MONTH_ROADMAP,
                _INTENT_GENERAL,
            }
        ),
        rationale="GrowthService via GrowthTool (AI-2).",
    ),
    "calculate_scenario": ToolSpec(
        name="calculate_scenario",
        description=(
            "Returns an illustrative scenario projection "
            "(baseline / best_case / worst_case) using a "
            "user-supplied lever map."
        ),
        arg_schema=ScenarioArgs,
        engine_name="finance",
        evidence_kind=EvidenceKind.SCORE,
        intents=frozenset(
            {
                _INTENT_HIRING,
                _INTENT_REACH_REVENUE_TARGET,
                _INTENT_TWELVE_MONTH_ROADMAP,
                _INTENT_GENERAL,
            }
        ),
        rationale="FinanceService via FinanceTool (AI-2).",
    ),
    "compare_recommendations": ToolSpec(
        name="compare_recommendations",
        description=(
            "Returns a side-by-side comparison of 2–12 "
            "recommendations by score gain, timeline, category."
        ),
        arg_schema=CompareRecommendationsArgs,
        engine_name="compare_recommendations",   # NEW wrapper in business_tools.py
        evidence_kind=EvidenceKind.RECOMMENDATION,
        intents=_ALL_INTENTS,
        rationale="Comparison combiner (NEW thin wrapper CompareRecommendationsTool — AI-8).",
    ),
    "get_analytics": ToolSpec(
        name="get_analytics",
        description=(
            "Returns the analytics KPIs for a given rolling "
            "window (e.g. 90d)."
        ),
        arg_schema=KpiArgs,
        engine_name="kpi",
        evidence_kind=EvidenceKind.INSIGHT,
        intents=_ALL_INTENTS,
        rationale="KpiService via KpiTool (AI-2).",
    ),
    "get_action_board": ToolSpec(
        name="get_action_board",
        description=(
            "Returns the user's current action board "
            "(status, priority, due_in_days, title)."
        ),
        arg_schema=None,
        engine_name="action_board",   # NEW wrapper in business_tools.py
        evidence_kind=EvidenceKind.ACTION,
        intents=_ALL_INTENTS,
        rationale="ActionBoardService (NEW thin wrapper ActionBoardTool — AI-8).",
    ),
}


# --------------------------------------------------------------------------- #
# INTENT_COMPATIBILITY — what the router checks at step 4
# --------------------------------------------------------------------------- #


INTENT_COMPATIBILITY: dict[str, frozenset[str]] = {
    intent: frozenset(
        spec.name
        for spec in TOOL_REGISTRY.values()
        if intent in spec.intents
    )
    for intent in _ALL_INTENTS
}


# --------------------------------------------------------------------------- #
# Catalog wrapper — exposes a typed query API
# --------------------------------------------------------------------------- #


class ToolCatalog:
    """Read-only view over :data:`TOOL_REGISTRY`.

    The catalog never instantiates an engine; the router
    uses the ``ToolSpec.engine_name`` to look up a
    ``ToolInterface`` in the dispatcher's registry.
    """

    __slots__ = ("_specs",)

    def __init__(
        self,
        specs: dict[str, ToolSpec] | None = None,
    ) -> None:
        # Default to the canonical 12-entry registry.
        self._specs: dict[str, ToolSpec] = (
            dict(specs) if specs is not None else dict(TOOL_REGISTRY)
        )

    def get(self, name: str) -> ToolSpec | None:
        """Return the spec for ``name`` (case-sensitive)."""
        if not name:
            return None
        return self._specs.get(name)

    def all(self) -> tuple[ToolSpec, ...]:
        """All catalog entries, in registry insertion order."""
        return tuple(self._specs.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs.keys())

    def tools_for_intent(self, intent: str) -> frozenset[str]:
        """Names the LLM may request when the caller's intent is ``intent``."""
        return INTENT_COMPATIBILITY.get(intent, frozenset())

    def is_allowed_for_intent(self, name: str, intent: str) -> bool:
        return name in self.tools_for_intent(intent)


__all__ = [
    "ToolSpec",
    "ToolCatalog",
    "TOOL_REGISTRY",
    "INTENT_COMPATIBILITY",
]

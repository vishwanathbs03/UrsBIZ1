"""SPRINT AI-8 — Controlled Business Tool Router.

Whitelists the tools the LLM may REQUEST through its
response payload, then validates + dispatches + sanitises
each call, then feeds the verified result back so the LLM
can explain it.

The brief calls the model "an explainer, not an actor" —
the deterministic engines in
``app.services.ai.reasoning.engine_tools`` remain the only
data-source actors. AI-8 adds the typed, validated handshake
that lets the LLM *ask* for those engines to do work.
"""
from __future__ import annotations

from app.services.ai.tool_router.types import (
    LLMToolRequest,
    LLMToolResult,
    GrowthArgs,
    ScenarioArgs,
    RecommendationArgs,
    ForecastArgs,
    RoadmapArgs,
    KpiArgs,
    CompareRecommendationsArgs,
    ActionBoardArgs,
)
from app.services.ai.tool_router.catalog import (
    ToolSpec,
    ToolCatalog,
    TOOL_REGISTRY,
)
from app.services.ai.tool_router.router import (
    LLMToolRequestRouter,
)

__all__ = [
    "LLMToolRequest",
    "LLMToolResult",
    "GrowthArgs",
    "ScenarioArgs",
    "RecommendationArgs",
    "ForecastArgs",
    "RoadmapArgs",
    "KpiArgs",
    "CompareRecommendationsArgs",
    "ActionBoardArgs",
    "ToolSpec",
    "ToolCatalog",
    "TOOL_REGISTRY",
    "LLMToolRequestRouter",
]

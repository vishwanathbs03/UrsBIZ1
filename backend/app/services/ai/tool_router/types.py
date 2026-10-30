"""SPRINT AI-8 — Wire types for the controlled tool router.

The LLM may emit a ``tool_calls`` array on its response
payload. Every entry is parsed into :class:`LLMToolRequest`.
The router validates + dispatches it, then returns a
:class:`LLMToolResult`.

All models use ``extra="forbid"`` so a future LLM cannot
slip hidden fields past the security boundary:

  * ``arguments.owner_id`` is rejected before the request
    reaches the router (cardinal security test).
  * Unknown ``tool`` names are rejected at step 1.
  * Argument shapes are Pydantic-checked at step 2.

Status vocabulary is the same as the AI-1 ``ToolResult``:
``"ok"`` / ``"skipped"`` / ``"error"``. Adding new statuses
is non-breaking.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# LLM ↔ Router wire
# --------------------------------------------------------------------------- #


ToolStatus = Literal["ok", "skipped", "error"]


class LLMToolRequest(BaseModel):
    """The LLM's request for a tool to run.

    Lives in the model JSON output: a list of these under
    ``tool_calls``. The router validates each one before
    dispatching.
    """

    model_config = ConfigDict(extra="forbid")
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Optional reasoning the LLM sends — logged to audit,
    # never trusted (the LLM is untrusted on intent).
    reason: str = Field(default="", max_length=500)


class LLMToolResult(BaseModel):
    """What the router returns to the LLM on the 2nd turn.

    ``payload`` is the JSON-safe dict the deterministic
    engine returned, after sanitisation (``_LEAKED_FIELDS``
    stripped). ``evidence_ids`` are the stable IDs the
    provider layer can hyperlink against. ``status="error"``
    always carries a human-readable ``error`` reason so the
    LLM can narrate the rejection.
    """

    model_config = ConfigDict(extra="forbid")
    tool: str
    status: ToolStatus
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = Field(default=0, ge=0)
    error: str | None = None


# --------------------------------------------------------------------------- #
# Per-tool argument schemas
#
# Each tool from the 12-brief whitelist has its own Pydantic
# model for ``arguments``. Extra fields are forbidden across
# the board — the LLM cannot smuggle in ``owner_id``,
# ``base_url``, ``api_key``, or anything else the security
# boundary was designed to block.
# --------------------------------------------------------------------------- #


class GrowthArgs(BaseModel):
    """Args for ``calculate_revenue_growth``.

    Splits the period string into two halves so the router
    never reads the actual period labels from an upstream
    service — the LLM picks them, the deterministic engine
    binds them.
    """

    model_config = ConfigDict(extra="forbid")
    from_period: str = Field(min_length=2, max_length=16)   # "FY24"
    to_period: str = Field(min_length=2, max_length=16)     # "FY25"


class ScenarioArgs(BaseModel):
    """Args for ``calculate_scenario``.

    ``scenario`` is the brief's friendly name (``"baseline"`` /
    ``"best_case"`` / ``"worst_case"``); ``params`` is a
    flat dict of numeric levers the engine accepts.
    """

    model_config = ConfigDict(extra="forbid")
    scenario: str = Field(min_length=1, max_length=32)
    params: dict[str, Any] = Field(default_factory=dict)


class RecommendationArgs(BaseModel):
    """Args for ``get_recommendations``."""

    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=5, ge=1, le=20)


class ForecastArgs(BaseModel):
    """Args for ``get_forecast``."""

    model_config = ConfigDict(extra="forbid")
    horizon_months: int = Field(default=12, ge=1, le=60)


class RoadmapArgs(BaseModel):
    """Args for ``get_roadmap``."""

    model_config = ConfigDict(extra="forbid")
    horizon_months: int = Field(default=12, ge=1, le=60)


class KpiArgs(BaseModel):
    """Args for ``get_analytics``."""

    model_config = ConfigDict(extra="forbid")
    window: str = Field(default="90d", min_length=2, max_length=16)


class CompareRecommendationsArgs(BaseModel):
    """Args for ``compare_recommendations``."""

    model_config = ConfigDict(extra="forbid")
    recommendation_ids: list[str] = Field(
        min_length=1, max_length=12,
    )


class ActionBoardArgs(BaseModel):
    """Args for ``get_action_board`` (no args)."""

    model_config = ConfigDict(extra="forbid")


# Tools that take NO arguments: empty BaseModel with extra="forbid"
# would still require `{}`; we keep the public class around for
# clarity but don't gate the router on it — step 2 of the
# pipeline accepts the empty arguments dict verbatim.


__all__ = [
    "ToolStatus",
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
]

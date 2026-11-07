"""Pydantic v2 schemas for the Dashboard API (Sprint 10 Task 10.1)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.business import BusinessSummary


class DashboardResponse(BaseModel):
    """Response payload for GET /api/v1/dashboard."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    business: BusinessSummary | None = Field(
        default=None,
        description="Business summary card for the authenticated user",
    )
    kpis: dict[str, Any] = Field(
        default_factory=lambda: {
            "total_revenue": 0.0,
            "active_projects": 0,
            "efficiency_score": 85,
            "health_index": "Good",
        },
        description="KPI placeholder metrics",
    )
    health_score: int = Field(
        default=85,
        alias="healthScore",
        description="Health score placeholder (0-100)",
    )
    healthScore: int = Field(
        default=85,
        description="Health score placeholder alias",
    )
    ai_summary: str = Field(
        default="Business operations are active and running within expected parameters.",
        alias="aiSummary",
        description="AI summary placeholder",
    )
    aiSummary: str = Field(
        default="Business operations are active and running within expected parameters.",
        description="AI summary placeholder alias",
    )
    recent_activity: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="recentActivity",
        description="Recent activity feed (placeholder)",
    )
    recentActivity: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent activity feed alias",
    )
    quick_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="quickActions",
        description="Quick actions list (placeholder)",
    )
    quickActions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Quick actions list alias",
    )
    is_degraded: bool = Field(
        default=False,
        alias="isDegraded",
        description="Whether dashboard data is served in degraded / snapshot continuity mode",
    )
    isDegraded: bool = Field(
        default=False,
        description="Whether dashboard data is served in degraded / snapshot continuity mode alias",
    )
    continuity_notice: str | None = Field(
        default=None,
        alias="continuityNotice",
        description="Continuity notice describing degraded read-only state or cached snapshot provenance",
    )
    continuityNotice: str | None = Field(
        default=None,
        description="Continuity notice describing degraded read-only state or cached snapshot provenance alias",
    )

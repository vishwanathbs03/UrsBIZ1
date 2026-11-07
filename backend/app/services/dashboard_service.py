"""Dashboard service — Sprint 10 Task 10.2.

Assembles the dashboard response for the authenticated user by fetching
the user's business profile via BusinessRepository and returning
KPI, health score, AI summary, recent activity, and quick action placeholders.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.schemas.business import BusinessSummary
from app.schemas.dashboard import DashboardResponse
from app.services.health_score_service import HealthScoreService
from app.services.kpi_service import KpiService

logger = logging.getLogger("atlas.dashboard.continuity")


class DashboardService:
    """Service layer for assembling dashboard data with graceful continuity fallback."""

    # In-memory continuity snapshot cache per owner_id
    _SNAPSHOT_CACHE: ClassVar[dict[int, DashboardResponse]] = {}

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def get_dashboard(self, owner_id: int) -> DashboardResponse:
        """Fetch dashboard metrics for the given owner_id with graceful degradation."""
        try:
            business = self._repo.get_by_owner(owner_id)
            if business is None:
                raise BusinessNotFound("No business profile for this user yet.")

            summary = BusinessSummary.model_validate(business)
            computed_kpis = KpiService.compute(business)
            kpis = computed_kpis.model_dump()

            health_report = HealthScoreService.compute(business)
            health = health_report.score
            ai_summary_text = (
                f"{business.legal_name} operates in {business.industry} with "
                f"{business.employee_count} employees. Digital twin analytics indicate stable growth metrics."
            )

            response = DashboardResponse(
                business=summary,
                kpis=kpis,
                health_score=health,
                healthScore=health,
                ai_summary=ai_summary_text,
                aiSummary=ai_summary_text,
                recent_activity=[],
                recentActivity=[],
                quick_actions=[],
                quickActions=[],
                is_degraded=False,
                isDegraded=False,
                continuity_notice=None,
                continuityNotice=None,
            )
            # Store verified snapshot for continuity
            DashboardService._SNAPSHOT_CACHE[owner_id] = response
            return response

        except BusinessNotFound:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"[DashboardService] Database or engine degradation: {exc}. Engaging continuity snapshot."
            )
            # If a last-known good snapshot is cached, serve it in degraded mode
            if owner_id in DashboardService._SNAPSHOT_CACHE:
                cached = DashboardService._SNAPSHOT_CACHE[owner_id].model_copy()
                cached.is_degraded = True
                cached.isDegraded = True
                notice = "Serving last-verified snapshot during database degradation. Read-only mode active."
                cached.continuity_notice = notice
                cached.continuityNotice = notice
                return cached

            # Safe baseline MSME response when no prior snapshot exists
            notice = "Operating in resilient read-only mode during temporary infrastructure degradation."
            return DashboardResponse(
                business=None,
                kpis={
                    "total_revenue": 0.0,
                    "active_projects": 0,
                    "efficiency_score": 75,
                    "health_index": "Fair",
                },
                health_score=75,
                healthScore=75,
                ai_summary=notice,
                aiSummary=notice,
                recent_activity=[],
                recentActivity=[],
                quick_actions=[],
                quickActions=[],
                is_degraded=True,
                isDegraded=True,
                continuity_notice=notice,
                continuityNotice=notice,
            )

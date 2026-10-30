"""Analytics Service for /api/v1/analytics — Sprint 13.1."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.business import Business
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.schemas.analytics_v1 import (
    AnalyticsOverviewData,
    AnalyticsOverviewInfo,
    AnalyticsOverviewResponse,
    AnalyticsTrends,
    BusinessMetrics,
    TrendPoint,
)
from app.services.health_score_service import HealthScoreService


class AnalyticsV1Service:
    """Computes full analytics data directly from Business profile."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def calculate_overview(self, business: Business) -> AnalyticsOverviewData:
        rev = float(business.annual_revenue or 0.0)
        emp = max(0, business.employee_count or 0)
        curr_year = datetime.now(tz=timezone.utc).year
        est_year = business.established_year or curr_year
        years = max(0, curr_year - est_year)

        health = HealthScoreService.compute(business)
        health_sc = health.score

        # Profile completion
        completed = 0
        total = 6
        if business.legal_name: completed += 1
        if business.industry: completed += 1
        if business.established_year: completed += 1
        if business.employee_count is not None: completed += 1
        if business.annual_revenue is not None: completed += 1
        if business.country: completed += 1

        comp_pct = round((completed / total) * 100)

        # Metrics computation
        dp = business.digital_presence
        digital_readiness = 80 if dp and dp.has_website else 45
        operational_maturity = 85 if emp >= 15 else (70 if emp >= 5 else 50)
        market_presence = 75 if years >= 3 else 55
        customer_reach = 80 if rev >= 250000.0 else 60

        overview_info = AnalyticsOverviewInfo(
            business_name=business.legal_name,
            industry=business.industry or "General MSME",
            profile_completion=comp_pct,
            health_score=health_sc,
            employee_count=emp,
            years_in_business=years,
        )

        metrics = BusinessMetrics(
            growth_score=health_sc,
            digital_readiness=digital_readiness,
            operational_maturity=operational_maturity,
            market_presence=market_presence,
            customer_reach=customer_reach,
        )

        # Monthly & Yearly Trends
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        m_base = rev / 12.0
        monthly_trend = [
            TrendPoint(label=m, value=round(m_base * (1.0 + idx * 0.02), 2))
            for idx, m in enumerate(months)
        ]

        yearly_trend = [
            TrendPoint(label=str(curr_year - 2), value=round(rev * 0.82, 2)),
            TrendPoint(label=str(curr_year - 1), value=round(rev * 0.91, 2)),
            TrendPoint(label=str(curr_year), value=round(rev, 2)),
        ]

        trends = AnalyticsTrends(
            monthly_trend=monthly_trend,
            yearly_trend=yearly_trend,
        )

        # Strengths, Weaknesses, Opportunities, Risks
        strengths = []
        weaknesses = []
        opportunities = []
        risks = []

        if rev >= 200000.0:
            strengths.append("Strong annual revenue foundation")
        else:
            weaknesses.append("Revenue below target growth threshold")

        if emp >= 10:
            strengths.append("Established workforce capacity")
        else:
            weaknesses.append("Lean team size constraining scale")

        if dp and dp.has_website:
            strengths.append("Active digital presence and web channel")
        else:
            opportunities.append("Expand online presence with e-commerce & web portal")

        opportunities.append("Automate core operational workflows for 15% margin gain")
        risks.append("Market competition in primary operating region")

        return AnalyticsOverviewData(
            overview=overview_info,
            metrics=metrics,
            trends=trends,
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            risks=risks,
        )

    def compute(self, owner_id: int) -> AnalyticsOverviewResponse:
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")

        data = self.calculate_overview(business)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        return AnalyticsOverviewResponse(generated_at=now_iso, analytics=data)

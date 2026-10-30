"""Predictive Engines Service — Sprint 14.

Rule-based prediction services:
  * RevenuePredictionService (Sprint 14.1)
  * GrowthPredictionService (Sprint 14.2)
  * FutureRiskPredictionService (Sprint 14.3)

Zero ML, pure deterministic rules based on Business profile, DNA, Health, and Readiness.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.business import Business
from app.repositories.business_repository import BusinessNotFound, BusinessRepository
from app.schemas.predictive_sprint14 import (
    FutureRiskItem,
    FutureRiskPredictionResponse,
    FutureRiskReport,
    GrowthPredictionResponse,
    GrowthPredictionReport,
    RevenuePredictionResponse,
    RevenuePredictionReport,
)
from app.services.business_dna_service import BusinessDNAService
from app.services.health_score_service import HealthScoreService
from app.services.readiness_service import ReadinessService


class RevenuePredictionService:
    """Deterministic Revenue Forecast Engine (Sprint 14.1)."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo
        self._dna_service = BusinessDNAService(repo)
        self._readiness_service = ReadinessService(repo)

    def forecast_revenue(self, business: Business) -> RevenuePredictionReport:
        rev = business.annual_revenue or 0.0
        health = HealthScoreService.compute(business)
        dna = self._dna_service.analyze_dna(business)
        readiness = self._readiness_service.analyze_readiness(business)

        # Deterministic growth rate multiplier derived from Health & Readiness
        base_annual_growth = 0.08  # 8% baseline
        if health.score >= 80:
            base_annual_growth += 0.10
        elif health.score >= 60:
            base_annual_growth += 0.05

        if readiness.overall_score >= 80:
            base_annual_growth += 0.07
        elif readiness.overall_score >= 60:
            base_annual_growth += 0.03

        if dna.growth_potential in ["Very High", "High"]:
            base_annual_growth += 0.05

        f_3m = round(rev * (1.0 + (base_annual_growth * 0.25)), 2)
        f_6m = round(rev * (1.0 + (base_annual_growth * 0.50)), 2)
        f_12m = round(rev * (1.0 + base_annual_growth), 2)

        if rev <= 0:
            conf = 0
            trend = "Insufficient Data"
        else:
            conf = min(95, max(50, round((health.score + readiness.overall_score) / 2.0)))
            trend = "Upward Growth" if base_annual_growth > 0.12 else ("Stable" if base_annual_growth >= 0.05 else "Downward Risk")

        return RevenuePredictionReport(
            current_annual_revenue=rev,
            forecast_3m=f_3m,
            forecast_6m=f_6m,
            forecast_12m=f_12m,
            confidence=conf,
            trend=trend,
        )

    def compute(self, owner_id: int) -> RevenuePredictionResponse:
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")
        report = self.forecast_revenue(business)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        return RevenuePredictionResponse(generated_at=now_iso, report=report)


class GrowthPredictionService:
    """Deterministic Business Growth Prediction Engine (Sprint 14.2)."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo
        self._dna_service = BusinessDNAService(repo)
        self._readiness_service = ReadinessService(repo)

    def forecast_growth(self, business: Business) -> GrowthPredictionReport:
        emp = business.employee_count or 0
        prods = len(business.products) if business.products else 0
        health = HealthScoreService.compute(business)
        readiness = self._readiness_service.analyze_readiness(business)

        # Deterministic employee & product scaling
        emp_addition = 2 if health.score >= 70 else 1
        prod_addition = 3 if readiness.overall_score >= 70 else 1

        p_emp = emp + emp_addition
        p_prod = prods + prod_addition
        p_health = min(100, health.score + (8 if readiness.overall_score >= 70 else 4))

        readiness_label = "High" if readiness.overall_score >= 75 else ("Medium" if readiness.overall_score >= 55 else "Low")
        conf = min(95, max(50, round((health.score + readiness.overall_score) / 2.0)))

        return GrowthPredictionReport(
            current_employees=emp,
            predicted_employees_12m=p_emp,
            current_products=prods,
            predicted_products_12m=p_prod,
            predicted_health_score_12m=p_health,
            expansion_readiness=readiness_label,
            growth_confidence=conf,
        )

    def compute(self, owner_id: int) -> GrowthPredictionResponse:
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")
        report = self.forecast_growth(business)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        return GrowthPredictionResponse(generated_at=now_iso, report=report)


class FutureRiskPredictionService:
    """Deterministic Future Risk Prediction Engine (Sprint 14.3)."""

    def __init__(self, repo: BusinessRepository) -> None:
        self._repo = repo

    def forecast_risks(self, business: Business) -> FutureRiskReport:
        risks: list[FutureRiskItem] = []
        rev = business.annual_revenue or 0.0
        emp = business.employee_count or 0
        exports = len(business.export_history) if business.export_history else 0
        dp = business.digital_presence

        if rev < 100000.0:
            risks.append(
                FutureRiskItem(
                    risk_name="Liquidity & Working Capital Contraction",
                    category="Financial",
                    probability_pct=75,
                    severity="High",
                    timeline="3-6 months",
                )
            )

        if emp <= 5:
            risks.append(
                FutureRiskItem(
                    risk_name="Key Person Operational Overload",
                    category="Operational",
                    probability_pct=65,
                    severity="Medium",
                    timeline="1-3 months",
                )
            )

        if exports == 0:
            risks.append(
                FutureRiskItem(
                    risk_name="Domestic Market Saturation Vulnerability",
                    category="Market",
                    probability_pct=60,
                    severity="Medium",
                    timeline="6-12 months",
                )
            )

        if not dp or not dp.has_ecommerce:
            risks.append(
                FutureRiskItem(
                    risk_name="Competitor E-Commerce Share Erosion",
                    category="Market",
                    probability_pct=70,
                    severity="High",
                    timeline="3-6 months",
                )
            )

        return FutureRiskReport(
            total_predicted_risks=len(risks),
            future_risks=risks,
        )

    def compute(self, owner_id: int) -> FutureRiskPredictionResponse:
        business = self._repo.get_by_owner(owner_id)
        if business is None:
            raise BusinessNotFound("No business profile found for this user.")
        report = self.forecast_risks(business)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        return FutureRiskPredictionResponse(generated_at=now_iso, report=report)

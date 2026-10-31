"""Phase 2 Automated Data Integrity, Multi-Tenant Isolation, and Calculation Tests.

Verifies:
  1. Multi-tenant business account isolation (active_business_id switching).
  2. Data integrity on missing/zero revenue (no fabricated figures, 0% confidence on missing data).
  3. Scoring boundary constraints (0 <= score <= 100 across both Executive Health and Twin Composite Index).
  4. Non-destructive scenario simulation (persistent DB row remains intact).
"""

import time
import pytest
from app.utils.database import SessionLocal
from app.models.user import User
from app.models.business import Business
from app.repositories.business_repository import BusinessRepository
from app.services.business_service import BusinessService
from app.services.health_score_service import HealthScoreService
from app.services.analytics_sprint13_service import BusinessAnalyticsService
from app.services.predictive_sprint14_service import RevenuePredictionService
from app.services.scenario.service import ScenarioService
from app.schemas.scenario import ScenarioRequest, ImproveDigitalPresence
from app.services.twin import TwinService


def test_multi_tenant_business_account_isolation():
    db = SessionLocal()
    try:
        ts = int(time.time() * 1000)
        user = User(
            email=f"multi_biz_{ts}@example.com",
            password_hash="testhash",
            full_name="Multi Biz Owner",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)

        # Create Business A (Textiles, 1.8 Cr revenue)
        biz_a = repo.create(
            owner_id=user.id,
            legal_name="Alpha Textiles",
            industry="Textiles",
            established_year=2015,
            employee_count=15,
            annual_revenue=18000000.0,
            revenue_currency="INR",
        )
        db.commit()

        # Create Business B (Ceramics, 50 Lakhs revenue)
        biz_b = repo.create(
            owner_id=user.id,
            legal_name="Beta Ceramics",
            industry="Ceramics",
            established_year=2020,
            employee_count=5,
            annual_revenue=5000000.0,
            revenue_currency="INR",
        )
        db.commit()

        # 1. Set Business A as active
        user.active_business_id = biz_a.id
        db.commit()
        repo.invalidate_cache(user.id)

        # Verify repo.get_by_owner returns Business A
        active_1 = repo.get_by_owner(user.id)
        assert active_1 is not None
        assert active_1.id == biz_a.id
        assert active_1.legal_name == "Alpha Textiles"
        assert active_1.annual_revenue == 18000000.0

        # Verify twin computes for Business A
        twin_svc = TwinService(repo)
        twin_a = twin_svc.compute(user.id)
        assert twin_a["identity"]["business_id"] == biz_a.id
        assert twin_a["identity"]["legal_name"] == "Alpha Textiles"

        # 2. Switch to Business B as active
        user.active_business_id = biz_b.id
        db.commit()
        repo.invalidate_cache(user.id)

        # Verify repo.get_by_owner now returns Business B
        active_2 = repo.get_by_owner(user.id)
        assert active_2 is not None
        assert active_2.id == biz_b.id
        assert active_2.legal_name == "Beta Ceramics"
        assert active_2.annual_revenue == 5000000.0

        # Verify twin immediately computes for Business B
        twin_b = twin_svc.compute(user.id)
        assert twin_b["identity"]["business_id"] == biz_b.id
        assert twin_b["identity"]["legal_name"] == "Beta Ceramics"

    finally:
        db.close()


def test_zero_revenue_data_integrity():
    """Verify that businesses with zero revenue do not receive fabricated numbers or inflated confidence."""
    db = SessionLocal()
    try:
        ts = int(time.time() * 1000)
        user = User(
            email=f"zero_rev_{ts}@example.com",
            password_hash="testhash",
            full_name="Zero Rev Owner",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        biz = repo.create(
            owner_id=user.id,
            legal_name="Pre-Revenue Startup",
            industry="Software",
            established_year=2024,
            employee_count=2,
            annual_revenue=0.0,
            revenue_currency="INR",
        )
        user.active_business_id = biz.id
        db.commit()
        repo.invalidate_cache(user.id)

        # 1. Analytics Service
        analytics_svc = BusinessAnalyticsService(repo)
        analytics = analytics_svc.compute(user.id)
        # Monthly run rate must be 0, never a fabricated 120,000 baseline
        for item in analytics.analytics.monthly_growth:
            assert item.revenue == 0.0
            assert item.growth_rate == 0.0

        # 2. Forecast Service
        pred_svc = RevenuePredictionService(repo)
        pred = pred_svc.compute(user.id)
        # Confidence must be 0 for zero baseline turnover
        assert pred.report.confidence == 0
        assert pred.report.current_annual_revenue == 0.0
        assert "Insufficient" in pred.report.trend

    finally:
        db.close()


def test_health_score_and_twin_boundaries():
    """Verify score bounds: 0 <= score <= 100 across both scoring engines."""
    db = SessionLocal()
    try:
        ts = int(time.time() * 1000)
        user = User(
            email=f"score_bounds_{ts}@example.com",
            password_hash="testhash",
            full_name="Score Bounds User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        biz = repo.create(
            owner_id=user.id,
            legal_name="Boundary Test Company",
            industry="Manufacturing",
            established_year=2010,
            employee_count=50,
            annual_revenue=25000000.0,
            revenue_currency="INR",
        )
        user.active_business_id = biz.id
        db.commit()
        repo.invalidate_cache(user.id)

        # 1. Executive Health Score
        exec_health = HealthScoreService.compute(biz)
        assert 0 <= exec_health.score <= 100
        assert exec_health.grade in ["A", "B", "C", "D", "E", "F"]

        # 2. Digital Twin Composite Index
        twin_svc = TwinService(repo)
        twin = twin_svc.compute(user.id)
        assert 0 <= twin["overall_twin_health"] <= 100
        assert 0 <= twin["scores"]["overall_score"] <= 100

        # Verify all 11 health summary lenses are clamped between 0 and 100
        for key, val in twin["health_summary"].items():
            if isinstance(val, (int, float)):
                assert 0 <= val <= 100, f"Lens {key} value {val} out of bounds!"

    finally:
        db.close()


def test_scenario_simulation_non_destructive():
    """Verify that scenario simulation does NOT alter the persistent database row."""
    db = SessionLocal()
    try:
        ts = int(time.time() * 1000)
        user = User(
            email=f"scenario_test_{ts}@example.com",
            password_hash="testhash",
            full_name="Scenario Test User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = BusinessRepository(db)
        biz = repo.create(
            owner_id=user.id,
            legal_name="Simulate Me Ltd",
            industry="Retail",
            established_year=2018,
            employee_count=8,
            annual_revenue=6000000.0,
            revenue_currency="INR",
        )
        user.active_business_id = biz.id
        db.commit()
        repo.invalidate_cache(user.id)

        # Run scenario change
        scenario_svc = ScenarioService(repo)
        request = ScenarioRequest(
            changes=[
                ImproveDigitalPresence(
                    label="Launch Web Store",
                    enable_ecommerce=True,
                    enable_digital_marketing=True,
                    enable_cloud_systems=True,
                )
            ]
        )
        result = scenario_svc.simulate(user.id, request)

        # Projected delta must show improvement
        assert result["delta"]["digital_readiness_difference"] > 0

        # Verify persistent database row was NOT modified
        repo.invalidate_cache(user.id)
        fresh_biz = repo.get_by_owner(user.id)
        assert fresh_biz is not None
        # Digital presence was not in DB before, should still not exist or ecommerce should still be False
        if fresh_biz.digital_presence:
            assert fresh_biz.digital_presence.has_ecommerce is False

    finally:
        db.close()

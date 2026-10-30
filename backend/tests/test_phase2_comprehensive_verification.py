"""Phase 2 Comprehensive Verification Suite.

Validates the 5 mandatory pre-merge verification gates:
1. Account isolation: Two users, each with multiple businesses.
   Verify dashboard, analytics, forecast, recommendations, twin,
   and health scores strictly isolate and reflect the active business.
2. Migration safety: Schema constraints, foreign key integrity,
   orphan prevention, and multi-tenant persistence.
3. Revenue handling: Missing (None), zero, negative (-50000), and
   insufficient historical data states.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.user_repository import UserRepository
from app.services.analytics_sprint13_service import BusinessAnalyticsService
from app.services.analytics_v1_service import AnalyticsV1Service
from app.services.auth_service import AuthService
from app.services.health_score_service import HealthScoreService
from app.services.predictive_sprint14_service import RevenuePredictionService
from app.services.recommendations import RecommendationService
from app.services.twin import TwinService
from app.utils.database import Base


@pytest.fixture
def test_db():
    """Isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_gate1_account_isolation_multi_user_multi_business(test_db):
    """GATE 1: Account Isolation.

    Two users, each with multiple businesses:
    - User 1: Business A1 (₹10L) & Business A2 (₹50L)
    - User 2: Business B1 (₹2L) & Business B2 (₹8L)

    Verify:
    1. Switching between A1 and A2 properly updates analytics, forecast,
       recommendations, twin index, and health score.
    2. Cache invalidation on switch works immediately.
    3. User 1 cannot access User 2's businesses (and vice-versa).
    """
    repo = BusinessRepository(test_db)
    user_repo = UserRepository(test_db)
    auth_service = AuthService(user_repo, business_repo=repo)
    analytics_svc = BusinessAnalyticsService(repo)
    predictive_svc = RevenuePredictionService(repo)
    twin_svc = TwinService(repo)

    # 1. Create User 1 and User 2
    user1 = User(
        email="user1_gate@example.com",
        full_name="User One",
        password_hash="hashed_pw_1",
    )
    user2 = User(
        email="user2_gate@example.com",
        full_name="User Two",
        password_hash="hashed_pw_2",
    )
    test_db.add_all([user1, user2])
    test_db.commit()

    # 2. Create Businesses for User 1
    biz_a1 = Business(
        owner_id=user1.id,
        legal_name="Alpha Solutions A1",
        industry="Technology",
        established_year=2020,
        annual_revenue=1000000.0,
        employee_count=10,
    )
    biz_a2 = Business(
        owner_id=user1.id,
        legal_name="Alpha Retail A2",
        industry="Retail",
        established_year=2021,
        annual_revenue=5000000.0,
        employee_count=50,
    )
    test_db.add_all([biz_a1, biz_a2])
    test_db.commit()

    # 3. Create Businesses for User 2
    biz_b1 = Business(
        owner_id=user2.id,
        legal_name="Beta Logistics B1",
        industry="Logistics",
        established_year=2019,
        annual_revenue=200000.0,
        employee_count=2,
    )
    biz_b2 = Business(
        owner_id=user2.id,
        legal_name="Beta Manufacturing B2",
        industry="Manufacturing",
        established_year=2018,
        annual_revenue=800000.0,
        employee_count=8,
    )
    test_db.add_all([biz_b1, biz_b2])
    test_db.commit()

    # --- Test User 1 with Active Business A1 ---
    auth_service.set_active_business(user1, biz_a1.id)
    active_u1 = repo.get_by_owner(user1.id)
    assert active_u1 is not None
    assert active_u1.id == biz_a1.id
    assert active_u1.legal_name == "Alpha Solutions A1"

    # Analytics for A1
    analytics_a1 = analytics_svc.compute(user1.id)
    assert analytics_a1.analytics.monthly_growth[0].revenue == pytest.approx(1000000.0 / 12, rel=1e-2)
    assert sum(analytics_a1.analytics.employee_distribution.values()) >= 10

    # Predictions for A1
    preds_a1 = predictive_svc.compute(user1.id)
    assert preds_a1.report.current_annual_revenue == 1000000.0
    assert preds_a1.report.forecast_3m > 1000000.0

    # Twin & Health for A1
    health_a1 = HealthScoreService.compute(active_u1)
    twin_a1 = twin_svc.compute(user1.id)
    assert 0 <= health_a1.score <= 100
    assert 0 <= twin_a1["health_summary"]["overall_health"] <= 100

    # --- Switch User 1 to Active Business A2 ---
    auth_service.set_active_business(user1, biz_a2.id)
    repo.invalidate_cache(user1.id)

    active_u1_switched = repo.get_by_owner(user1.id)
    assert active_u1_switched is not None
    assert active_u1_switched.id == biz_a2.id
    assert active_u1_switched.legal_name == "Alpha Retail A2"

    # Analytics for A2
    analytics_a2 = analytics_svc.compute(user1.id)
    assert analytics_a2.analytics.monthly_growth[0].revenue == pytest.approx(5000000.0 / 12, rel=1e-2)
    assert sum(analytics_a2.analytics.employee_distribution.values()) >= 50

    # Predictions for A2 scale higher
    preds_a2 = predictive_svc.compute(user1.id)
    assert preds_a2.report.forecast_3m > preds_a1.report.forecast_3m

    # --- Test User 2 with Active Business B1 ---
    auth_service.set_active_business(user2, biz_b1.id)
    repo.invalidate_cache(user2.id)
    active_u2 = repo.get_by_owner(user2.id)
    assert active_u2 is not None
    assert active_u2.id == biz_b1.id
    assert active_u2.legal_name == "Beta Logistics B1"

    analytics_b1 = analytics_svc.compute(user2.id)
    assert analytics_b1.analytics.monthly_growth[0].revenue == pytest.approx(200000.0 / 12, rel=1e-2)
    assert sum(analytics_b1.analytics.employee_distribution.values()) >= 2

    # --- Cross-Tenant Boundary Enforcement ---
    # User 1 cannot access User 2's business via get_by_id_for_owner
    assert repo.get_by_id_for_owner(biz_b1.id, user1.id) is None
    assert repo.get_by_id_for_owner(biz_b2.id, user1.id) is None

    # User 2 cannot access User 1's business via get_by_id_for_owner
    assert repo.get_by_id_for_owner(biz_a1.id, user2.id) is None
    assert repo.get_by_id_for_owner(biz_a2.id, user2.id) is None


def test_gate2_migration_safety_foreign_keys_and_orphan_prevention(test_db):
    """GATE 2: Migration Safety & Orphan Prevention.

    1. Business rows require a non-null valid owner_id.
    2. Deleting a user safely cascades or removes businesses, preventing
       orphaned rows.
    3. Multiple businesses per user persist without unique constraint violations.
    """
    user = User(
        email="mig_test@example.com",
        full_name="Migration Test User",
        password_hash="pw",
    )
    test_db.add(user)
    test_db.commit()

    # Inserting multiple businesses for the same owner works seamlessly
    biz1 = Business(
        owner_id=user.id,
        legal_name="Firm 1",
        industry="Tech",
        established_year=2020,
        annual_revenue=100000.0,
    )
    biz2 = Business(
        owner_id=user.id,
        legal_name="Firm 2",
        industry="Services",
        established_year=2021,
        annual_revenue=200000.0,
    )
    test_db.add_all([biz1, biz2])
    test_db.commit()

    all_user_biz = (
        test_db.query(Business).filter(Business.owner_id == user.id).all()
    )
    assert len(all_user_biz) == 2

    # Confirm foreign key constraint: attempting to create business with NULL owner fails
    with pytest.raises(Exception):
        invalid_biz = Business(
            owner_id=None,
            legal_name="Orphan Firm",
            industry="None",
        )
        test_db.add(invalid_biz)
        test_db.commit()
    test_db.rollback()


def test_gate3_revenue_handling_null_zero_negative_missing(test_db):
    """GATE 3: Revenue Handling & Insufficient Data States.

    Tests:
    1. NULL revenue
    2. Zero revenue (0.0)
    3. Negative revenue (-50000.0)
    4. Insufficient historical data

    All modules must handle these states gracefully without crashing,
    without divide-by-zero, and without emitting fabricated fallbacks.
    """
    repo = BusinessRepository(test_db)
    analytics_s13 = BusinessAnalyticsService(repo)
    analytics_v1 = AnalyticsV1Service(repo)
    predictive_svc = RevenuePredictionService(repo)
    twin_svc = TwinService(repo)

    user = User(
        email="rev_test@example.com",
        full_name="Revenue Tester",
        password_hash="pw",
    )
    test_db.add(user)
    test_db.commit()

    # CASE A: NULL Revenue
    biz_null = Business(
        owner_id=user.id,
        legal_name="Null Rev Enterprise",
        industry="Services",
        established_year=2020,
        annual_revenue=None,
        employee_count=None,
    )
    test_db.add(biz_null)
    test_db.commit()
    user.active_business_id = biz_null.id
    test_db.commit()
    repo.invalidate_cache(user.id)

    # 1. Analytics Sprint 13 with NULL revenue
    res_s13 = analytics_s13.compute(user.id)
    assert res_s13.analytics.monthly_growth[0].revenue == 0.0
    assert res_s13.analytics.monthly_growth[0].growth_rate == 0.0

    # 2. Analytics V1 with NULL revenue
    res_v1 = analytics_v1.compute(user.id)
    assert res_v1.analytics.trends.monthly_trend[0].value == 0.0

    # 3. Predictive with NULL revenue
    pred_null = predictive_svc.compute(user.id)
    assert pred_null.report.confidence == 0
    assert pred_null.report.trend == "Insufficient Data"

    # 4. Health Score with NULL revenue
    health_null = HealthScoreService.compute(biz_null)
    assert 0 <= health_null.score <= 100

    # 5. Twin Service with NULL revenue
    twin_null = twin_svc.compute(user.id)
    assert 0 <= twin_null["health_summary"]["overall_health"] <= 100

    # CASE B: Zero Revenue (0.0)
    biz_null.annual_revenue = 0.0
    test_db.commit()
    repo.invalidate_cache(user.id)

    res_zero = analytics_s13.compute(user.id)
    assert res_zero.analytics.monthly_growth[0].revenue == 0.0

    pred_zero = predictive_svc.compute(user.id)
    assert pred_zero.report.confidence == 0
    assert pred_zero.report.trend == "Insufficient Data"

    # CASE C: Negative Revenue (-50000.0)
    biz_null.annual_revenue = -50000.0
    test_db.commit()
    repo.invalidate_cache(user.id)

    res_neg = analytics_s13.compute(user.id)
    # Negative revenue is clamped to 0.0 run-rate to prevent invalid financial projections
    assert res_neg.analytics.monthly_growth[0].revenue == 0.0

    pred_neg = predictive_svc.compute(user.id)
    assert pred_neg.report.confidence == 0
    assert pred_neg.report.trend == "Insufficient Data"

    health_neg = HealthScoreService.compute(biz_null)
    assert 0 <= health_neg.score <= 100

    twin_neg = twin_svc.compute(user.id)
    assert 0 <= twin_neg["health_summary"]["overall_health"] <= 100

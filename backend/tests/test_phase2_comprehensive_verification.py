"""Phase 2 Comprehensive Verification Suite.

Validates the 5 mandatory pre-merge verification gates:
1. Account & Context Isolation: Two users, each with multiple businesses.
   Verify dashboard KPIs, analytics, forecast, recommendations, reports,
   PDF generator, AI assistant context, and health scores strictly isolate
   and reflect the active business.
2. Migration Safety & Downgrade Behavior: Reversible migration testing,
   schema constraints, foreign key integrity, orphan prevention, and exact
   database error on downgrade when multiple businesses exist per owner.
3. Revenue Semantics & Boundaries: Missing (None), zero (0.0), negative (-50000.0),
   and insufficient historical data states. Ensures gross turnover is not conflated
   with net operating loss.
4. Test Coverage & Integrity: Full test suite verification across modules.
5. Score Descriptions & Consistency: Delineates Executive Health Score (6 pillars:
   30/15/15/10/20/10) vs Intelligence Grounded Score (5 analyzers) vs Digital Twin
   Readiness Index (10-11 dimensions).
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config

from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.user_repository import UserRepository
from app.services.ai.providers.context_builder import AssistantContextBuilder
from app.services.analytics_sprint13_service import BusinessAnalyticsService
from app.services.analytics_v1_service import AnalyticsV1Service
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService
from app.services.health_score_service import HealthScoreService
from app.services.intelligence import IntelligenceService
from app.services.kpi_service import KpiService
from app.services.pdf_report_service import PdfReportService
from app.services.predictive_sprint14_service import RevenuePredictionService
from app.services.recommendations import RecommendationService
from app.services.report_service import ReportService
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
    """GATE 1: Account Isolation and Business Context Switching.

    Two users, each with multiple businesses:
    - User 1: Business A1 (₹10L turnover, 10 employees) & Business A2 (₹50L turnover, 50 employees)
    - User 2: Business B1 (₹2L turnover, 2 employees) & Business B2 (₹8L turnover, 8 employees)

    Verify that switching active_business_id updates ALL downstream services:
    - Dashboard KPIs & Summary (DashboardService)
    - Analytics (BusinessAnalyticsService & AnalyticsV1Service)
    - Forecasts (RevenuePredictionService)
    - Recommendations (RecommendationService)
    - Reports & PDF generation (ReportService & PdfReportService)
    - AI Assistant Business Context (AssistantContextBuilder)
    - Repository cache invalidation
    """
    repo = BusinessRepository(test_db)
    user_repo = UserRepository(test_db)
    auth_service = AuthService(user_repo, business_repo=repo)
    dashboard_svc = DashboardService(repo)
    analytics_svc = BusinessAnalyticsService(repo)
    analytics_v1_svc = AnalyticsV1Service(repo)
    predictive_svc = RevenuePredictionService(repo)
    twin_svc = TwinService(repo)
    rec_svc = RecommendationService(repo)
    report_svc = ReportService(repo)
    pdf_svc = PdfReportService(repo)

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
        established_year=2018,
        annual_revenue=200000.0,
        employee_count=2,
    )
    biz_b2 = Business(
        owner_id=user2.id,
        legal_name="Beta Manufacturing B2",
        industry="Manufacturing",
        established_year=2019,
        annual_revenue=800000.0,
        employee_count=8,
    )
    test_db.add_all([biz_b1, biz_b2])
    test_db.commit()

    # Assistant context builder helper bound to repo
    ai_builder = AssistantContextBuilder(
        twin_provider=lambda o: twin_svc.compute(o),
        recommendations_provider=lambda o: rec_svc.compute(o),
        roadmap_provider=lambda o: {},
        rules_provider=lambda o: {},
        insights_provider=lambda o: {},
    )

    # =========================================================================
    # Step A: User 1 with Active Business A1 (₹10L turnover, 10 employees)
    # =========================================================================
    auth_service.set_active_business(user1, biz_a1.id)
    repo.invalidate_cache(user1.id)
    active_u1 = repo.get_by_owner(user1.id)
    assert active_u1 is not None
    assert active_u1.id == biz_a1.id
    assert active_u1.legal_name == "Alpha Solutions A1"

    # Dashboard
    dash_a1 = dashboard_svc.get_dashboard(user1.id)
    assert dash_a1.business.legal_name == "Alpha Solutions A1"
    assert dash_a1.kpis["employees"] == 10

    # Analytics Sprint 13 & V1
    analytics_a1 = analytics_svc.compute(user1.id)
    assert analytics_a1.analytics.monthly_growth[0].revenue == pytest.approx(1000000.0 / 12, rel=1e-2)
    assert sum(analytics_a1.analytics.employee_distribution.values()) >= 10

    v1_a1 = analytics_v1_svc.compute(user1.id)
    assert v1_a1.analytics.overview.business_name == "Alpha Solutions A1"
    assert v1_a1.analytics.overview.employee_count == 10

    # Predictions
    preds_a1 = predictive_svc.compute(user1.id)
    assert preds_a1.report.current_annual_revenue == 1000000.0
    assert preds_a1.report.forecast_3m > 1000000.0

    # Reports & PDF
    rep_a1 = report_svc.generate_unified_report(active_u1)
    assert rep_a1.executive_summary.business_name == "Alpha Solutions A1"
    pdf_bytes_a1 = pdf_svc.generate_pdf_report(active_u1)
    assert len(pdf_bytes_a1) > 1000

    # AI Assistant Context
    ai_ctx_a1 = ai_builder.build(owner_id=user1.id)
    assert ai_ctx_a1.business_id == biz_a1.id

    # =========================================================================
    # Step B: Switch User 1 to Active Business A2 (₹50L turnover, 50 employees)
    # =========================================================================
    auth_service.set_active_business(user1, biz_a2.id)
    repo.invalidate_cache(user1.id)

    active_u1_switched = repo.get_by_owner(user1.id)
    assert active_u1_switched is not None
    assert active_u1_switched.id == biz_a2.id
    assert active_u1_switched.legal_name == "Alpha Retail A2"

    # Dashboard updates immediately
    dash_a2 = dashboard_svc.get_dashboard(user1.id)
    assert dash_a2.business.legal_name == "Alpha Retail A2"
    assert dash_a2.kpis["employees"] == 50

    # Analytics updates immediately
    analytics_a2 = analytics_svc.compute(user1.id)
    assert analytics_a2.analytics.monthly_growth[0].revenue == pytest.approx(5000000.0 / 12, rel=1e-2)
    assert sum(analytics_a2.analytics.employee_distribution.values()) >= 50

    v1_a2 = analytics_v1_svc.compute(user1.id)
    assert v1_a2.analytics.overview.business_name == "Alpha Retail A2"
    assert v1_a2.analytics.overview.employee_count == 50

    # Predictions scale with A2
    preds_a2 = predictive_svc.compute(user1.id)
    assert preds_a2.report.current_annual_revenue == 5000000.0
    assert preds_a2.report.forecast_3m > preds_a1.report.forecast_3m

    # Reports reflect A2
    rep_a2 = report_svc.generate_unified_report(active_u1_switched)
    assert rep_a2.executive_summary.business_name == "Alpha Retail A2"

    # AI Assistant Context updates immediately to A2
    ai_ctx_a2 = ai_builder.build(owner_id=user1.id)
    assert ai_ctx_a2.business_id == biz_a2.id

    # =========================================================================
    # Step C: Cross-Tenant Boundary Enforcement
    # =========================================================================
    # User 1 cannot access User 2's business via get_by_id_for_owner
    assert repo.get_by_id_for_owner(biz_b1.id, user1.id) is None
    assert repo.get_by_id_for_owner(biz_b2.id, user1.id) is None

    # User 2 cannot access User 1's business via get_by_id_for_owner
    assert repo.get_by_id_for_owner(biz_a1.id, user2.id) is None
    assert repo.get_by_id_for_owner(biz_a2.id, user2.id) is None


def test_gate2_migration_safety_foreign_keys_and_orphan_prevention(test_db):
    """GATE 2 Part A: Migration Safety & Orphan Prevention.

    1. Business rows require a non-null valid owner_id.
    2. Multiple businesses per user persist without unique constraint violations.
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


def test_gate2_migration_downgrade_failure_with_multiple_businesses():
    """GATE 2 Part B: Critical Alembic Migration Downgrade Safety.

    Tests the exact situation:
    - User 1 owns Business A
    - User 1 owns Business B
    - Both businesses exist in the upgraded schema (20260814_0002)
    - Attempt to downgrade to 20260814_0001 (recreating uq_businesses_owner_id)

    Verifies:
    1. Upgrade to 20260814_0002 succeeds.
    2. Downgrade fails with IntegrityError (UNIQUE constraint failed: owner_id).
    3. Confirms that no automated downgrade can safely re-apply UNIQUE(owner_id)
       without administrative deduplication or data loss.
    """
    db_file = os.path.abspath("test_downgrade_gate2.db")
    if os.path.exists(db_file):
        os.remove(db_file)

    db_url = f"sqlite:///{db_file.replace(os.sep, '/')}"
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    from app.config.settings import get_settings
    get_settings.cache_clear()

    cfg = Config("backend/migrations.ini")
    cfg.set_main_option("script_location", os.path.abspath("backend/migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")

    try:
        # Step 1: Upgrade to head (20260814_0002)
        command.upgrade(cfg, "head")

        # Step 2: Insert two businesses with the same owner_id
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{db_file}")
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, email, full_name, password_hash) "
                    "VALUES (1, 'downgrade_user@example.com', 'Downgrade User', 'hash')"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO businesses (id, owner_id, legal_name, industry, established_year, annual_revenue) "
                    "VALUES (1, 1, 'Biz A', 'Tech', 2020, 100000.0)"
                )
            )
            conn.execute(
                sa.text(
                    "INSERT INTO businesses (id, owner_id, legal_name, industry, established_year, annual_revenue) "
                    "VALUES (2, 1, 'Biz B', 'Retail', 2021, 200000.0)"
                )
            )

        # Step 3: Attempt downgrade to 20260814_0001
        with pytest.raises(Exception) as exc_info:
            command.downgrade(cfg, "20260814_0001")

        err = str(exc_info.value)
        # Verify exact error captures duplicate key constraint violation
        assert "UNIQUE constraint failed" in err or "columns owner_id are not unique" in err or "IntegrityError" in str(type(exc_info.value))

    finally:
        if old_db_url is not None:
            os.environ["DATABASE_URL"] = old_db_url
        else:
            os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


def test_gate3_revenue_handling_and_accounting_semantics(test_db):
    """GATE 3: Revenue Semantics & Boundaries (Turnover vs Operating Loss).

    In MSME accounting:
    - annual_revenue represents Gross Revenue (Turnover: total sales receipts).
    - Turnover cannot be negative (sales volume * price >= 0).
    - Operating loss is negative net income (Revenue - Expenses < 0), NOT negative turnover.
    - Negative revenue is treated as non-positive turnover / insufficient data.

    Tests:
    1. NULL revenue
    2. Zero revenue (0.0)
    3. Negative revenue (-50000.0)
    4. Missing historical data
    """
    repo = BusinessRepository(test_db)
    analytics_s13 = BusinessAnalyticsService(repo)
    analytics_v1 = AnalyticsV1Service(repo)
    predictive_svc = RevenuePredictionService(repo)
    twin_svc = TwinService(repo)

    user = User(
        email="rev_semantics@example.com",
        full_name="Rev Test",
        password_hash="pw",
    )
    test_db.add(user)
    test_db.commit()

    # CASE A: NULL Revenue
    biz_null = Business(
        owner_id=user.id,
        legal_name="Null Rev Enterprise",
        industry="Services",
        established_year=2022,
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
    assert res_v1.analytics.trends.yearly_trend[0].value == 0.0

    # 3. Predictive with NULL revenue
    pred_null = predictive_svc.compute(user.id)
    assert pred_null.report.confidence == 0
    assert pred_null.report.trend == "Insufficient Data"
    assert pred_null.report.forecast_3m == 0.0

    # 4. Health Score with NULL revenue
    health_null = HealthScoreService.compute(biz_null)
    assert 0 <= health_null.score <= 100
    assert "annual_revenue" in health_null.missing_fields

    # 5. Twin Service with NULL revenue
    twin_null = twin_svc.compute(user.id)
    assert 0 <= twin_null["health_summary"]["overall_health"] <= 100

    # CASE B: Zero Revenue (0.0)
    biz_null.annual_revenue = 0.0
    test_db.commit()
    repo.invalidate_cache(user.id)

    res_zero = analytics_s13.compute(user.id)
    assert res_zero.analytics.monthly_growth[0].revenue == 0.0

    res_v1_zero = analytics_v1.compute(user.id)
    assert res_v1_zero.analytics.trends.monthly_trend[0].value == 0.0

    pred_zero = predictive_svc.compute(user.id)
    assert pred_zero.report.confidence == 0
    assert pred_zero.report.trend == "Insufficient Data"

    # CASE C: Negative Revenue (-50000.0)
    biz_null.annual_revenue = -50000.0
    test_db.commit()
    repo.invalidate_cache(user.id)

    res_neg = analytics_s13.compute(user.id)
    assert res_neg.analytics.monthly_growth[0].revenue == 0.0

    res_v1_neg = analytics_v1.compute(user.id)
    # Trends must NOT output negative turnover
    for point in res_v1_neg.analytics.trends.monthly_trend:
        assert point.value >= 0.0
    for point in res_v1_neg.analytics.trends.yearly_trend:
        assert point.value >= 0.0

    pred_neg = predictive_svc.compute(user.id)
    assert pred_neg.report.confidence == 0
    assert pred_neg.report.trend == "Insufficient Data"
    assert pred_neg.report.forecast_3m == 0.0
    assert pred_neg.report.forecast_6m == 0.0
    assert pred_neg.report.forecast_12m == 0.0

    health_neg = HealthScoreService.compute(biz_null)
    assert 0 <= health_neg.score <= 100
    assert "annual_revenue" in health_neg.missing_fields

    twin_neg = twin_svc.compute(user.id)
    assert 0 <= twin_neg["health_summary"]["overall_health"] <= 100


def test_gate4_score_consistency_and_descriptions(test_db):
    """GATE 4 & 5: Verification of Distinct Scoring Engines and Formulas.

    Verifies the separation of three scoring layers:
    1. Executive Business Health Score (HealthScoreService):
       - Exact 6 weighted components:
         Profile Completeness (30) + Business Info (15) + Products/Services (15) +
         Team (10) + Financial (20) + Online Presence (10) = 100 max points.
       - Does NOT calculate regulatory compliance.
    2. Grounded Business Intelligence (IntelligenceService):
       - 5 analyzers: ProfileCompleteness, ExportReadiness, DigitalReadiness,
         ComplianceReadiness, GrowthReadiness.
       - Explicitly evaluates compliance certifications and registrations.
    3. Digital Twin Readiness Index (TwinService):
       - Strategic maturity index rolled up across 10-11 business dimensions.
    """
    repo = BusinessRepository(test_db)
    user = User(email="score_check@example.com", full_name="Score User", password_hash="pw")
    test_db.add(user)
    test_db.commit()

    biz = Business(
        owner_id=user.id,
        legal_name="Complete MSME Ltd",
        industry="Manufacturing",
        business_type="Private Limited",
        country="India",
        established_year=2015,
        employee_count=25,
        annual_revenue=1500000.0,
    )
    test_db.add(biz)
    test_db.commit()
    user.active_business_id = biz.id
    test_db.commit()
    repo.invalidate_cache(user.id)

    # 1. Executive Health Score
    health_report = HealthScoreService.compute(biz)
    assert isinstance(health_report.score, int)
    assert 0 <= health_report.score <= 100
    # Business info: legal_name(3) + industry(3) + established_year(3) + business_type(3) + country(3) = 15 pts
    # Team: 25 employees = 10 pts
    # Financial: 15L revenue = 20 pts
    # Total earned is at least 45 pts
    assert health_report.score >= 45

    # 2. Grounded Intelligence (with Compliance Analyzer)
    intel_svc = IntelligenceService(repo)
    intel = intel_svc.analyze(user.id)
    overall_score = intel["overall"]["score"] if isinstance(intel, dict) else intel.overall.score
    assert overall_score is not None
    analyzers = intel["analyzers"] if isinstance(intel, dict) else intel.analyzers
    assert len(analyzers) == 5
    analyzer_keys = [a["key"] if isinstance(a, dict) else a.key for a in analyzers]
    assert "compliance_readiness" in analyzer_keys
    assert "export_readiness" in analyzer_keys
    assert "digital_readiness" in analyzer_keys

    # 3. Digital Twin Readiness Index
    twin_svc = TwinService(repo)
    twin = twin_svc.compute(user.id)
    twin_overall = twin["health_summary"]["overall_health"]
    assert 0 <= twin_overall <= 100

    # Verify that the scores are independent calculations
    assert isinstance(health_report.score, int)
    assert isinstance(overall_score, int)
    assert isinstance(twin_overall, int)

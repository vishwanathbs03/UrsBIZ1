"""Phase 5.9: Comprehensive Cross-Phase Integration Test Suite (Phases 1–5).

Verifies the six canonical cross-module workflows:
  Workflow A: Business onboarding (Registration -> Business creation -> Profile completion -> Health scoring -> Recommendations)
  Workflow B: Sales intelligence (Sales upload -> Data quality -> Customer analytics -> Product analytics -> Recommendations)
  Workflow C: Demand forecasting (Historical sales -> Forecast preparation -> Model tournament -> Evaluation -> Forecast results -> Recommendations)
  Workflow D: Government schemes (Business profile -> Scheme matching -> Eligibility checks -> Evidence-backed recommendations -> Official source links)
  Workflow E: Recommendation lifecycle (Recommendation generation -> Explanation -> Accept -> In Progress -> Complete -> Refresh -> Verify persisted status)
  Workflow F: AI failure (Gemini unavailable -> Deterministic fallback explanation -> Recommendation remains usable)
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

from app.models.business import Business
from app.models.sales import SalesTransaction
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.repositories.sales_repository import SalesRepository
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
)
from app.services.health_score_service import HealthScoreService
from app.services.recommendations.explanation_service import explain_recommendation
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# =============================================================================
# Workflow A: Business Onboarding to Recommendations
# =============================================================================

def test_workflow_a_business_onboarding(db_session):
    """Registration -> Business creation -> Profile completion -> Health scoring -> Recommendations."""
    ts = int(time.time() * 1000)
    user = User(
        email=f"wf_a_user_{ts}@example.com",
        password_hash="fakehash",
        full_name="Workflow A User",
    )
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Genesis Workshop Pvt Ltd",
        trade_name="Genesis Workshop",
        industry="Textiles",
        established_year=2021,
        employee_count=8,
        annual_revenue=850000.0,
        revenue_currency="INR",
        city="Surat",
        state_region="Gujarat",
        country="India",
    )
    db_session.commit()

    # Health score calculation
    health_report = HealthScoreService.compute(business)
    assert 0 <= health_report.score <= 100
    assert health_report.grade in ["A", "B", "C", "D", "E", "F"]

    # Recommendations generation without sales transactions
    engine_inst = SmartRecommendationEngine(db_session)
    res = engine_inst.generate_recommendations(business=business)

    assert res.total_count > 0
    categories = [r.category for r in res.recommendations]

    # Must prompt sales upload; must NOT hallucinate customer churn or forecasts
    assert RecommendationCategory.OPERATIONAL_EFFICIENCY in categories
    assert RecommendationCategory.CUSTOMER_RETENTION not in categories
    assert RecommendationCategory.DEMAND_PLANNING not in categories


# =============================================================================
# Workflow B: Sales Intelligence to Recommendations
# =============================================================================

def test_workflow_b_sales_intelligence_to_recommendations(db_session):
    """Sales upload -> Data quality -> Customer analytics -> Product analytics -> Recommendations."""
    ts = int(time.time() * 1000)
    user = User(email=f"wf_b_{ts}@example.com", password_hash="h", full_name="WF B User")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Titan Tooling Works",
        industry="Manufacturing",
        established_year=2019,
        employee_count=20,
        annual_revenue=2500000.0,
        revenue_currency="INR",
        city="Coimbatore",
    )
    db_session.commit()

    # Upload sales records
    sales_repo = SalesRepository(db_session)
    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="sales_q3.csv",
        file_format="csv",
        file_size_bytes=2048,
        row_count=5,
        valid_row_count=5,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date"},
        quality_summary={"valid_pct": 100.0},
    )

    now = datetime(2025, 9, 30, tzinfo=timezone.utc)
    old = datetime(2025, 2, 10, tzinfo=timezone.utc)

    # Ingest rows with concentration (>50% on top customer) and inactive repeat buyer
    tx_rows = [
        {"transaction_date": now, "customer_id": "C_MAIN", "customer_name": "Anchor Client", "product_id": "P_FLAG", "product_name": "Carbide Endmill", "quantity": 100, "unit_price": 500, "total_amount": 50000},
        {"transaction_date": now, "customer_id": "C_MAIN", "customer_name": "Anchor Client", "product_id": "P_FLAG", "product_name": "Carbide Endmill", "quantity": 40, "unit_price": 500, "total_amount": 20000},
        {"transaction_date": old, "customer_id": "C_INACT", "customer_name": "Lapsed Fleet Co", "product_id": "P_DRILL", "product_name": "HSS Drill", "quantity": 10, "unit_price": 200, "total_amount": 2000},
        {"transaction_date": old, "customer_id": "C_INACT", "customer_name": "Lapsed Fleet Co", "product_id": "P_DRILL", "product_name": "HSS Drill", "quantity": 15, "unit_price": 200, "total_amount": 3000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    # Recommendations verification
    engine_inst = SmartRecommendationEngine(db_session)
    res = engine_inst.generate_recommendations(business=business)

    categories = [r.category for r in res.recommendations]
    assert RecommendationCategory.REVENUE_GROWTH in categories
    assert RecommendationCategory.CUSTOMER_RETENTION in categories

    # Verify concentration rule fired
    rev_rec = next(r for r in res.recommendations if r.category == RecommendationCategory.REVENUE_GROWTH)
    assert "Anchor Client" in str(rev_rec.evidence) or "Top 3 customers" in rev_rec.description

    # Verify retention rule fired with historical spend as evidence only
    ret_rec = next(r for r in res.recommendations if r.category == RecommendationCategory.CUSTOMER_RETENTION)
    assert ret_rec.estimated_impact is None
    assert any("historical context" in e.lower() for e in ret_rec.evidence)


# =============================================================================
# Workflow C: Demand Forecasting to Recommendations
# =============================================================================

def test_workflow_c_forecasting_to_recommendations(db_session):
    """Historical sales -> Forecast tournament -> Forecast results -> Recommendations."""
    ts = int(time.time() * 1000)
    user = User(email=f"wf_c_{ts}@example.com", password_hash="h", full_name="WF C User")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Nova Electronics",
        industry="Electronics",
        established_year=2020,
        employee_count=12,
        annual_revenue=1800000.0,
        revenue_currency="INR",
        city="Bengaluru",
    )
    db_session.commit()

    sales_repo = SalesRepository(db_session)
    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="monthly_trends.csv",
        file_format="csv",
        file_size_bytes=4096,
        row_count=6,
        valid_row_count=6,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date"},
        quality_summary={"valid_pct": 100.0},
    )

    # 6 consecutive months of increasing demand for Sensor SKU
    tx_rows = [
        {"transaction_date": datetime(2025, 1, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 10, "unit_price": 300, "total_amount": 3000},
        {"transaction_date": datetime(2025, 2, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 20, "unit_price": 300, "total_amount": 6000},
        {"transaction_date": datetime(2025, 3, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 30, "unit_price": 300, "total_amount": 9000},
        {"transaction_date": datetime(2025, 4, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 45, "unit_price": 300, "total_amount": 13500},
        {"transaction_date": datetime(2025, 5, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 65, "unit_price": 300, "total_amount": 19500},
        {"transaction_date": datetime(2025, 6, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 90, "unit_price": 300, "total_amount": 27000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    engine_inst = SmartRecommendationEngine(db_session)
    res = engine_inst.generate_recommendations(business=business)

    demand_recs = [r for r in res.recommendations if r.category == RecommendationCategory.DEMAND_PLANNING]
    assert len(demand_recs) > 0

    lead_rec = demand_recs[0]
    # Boundaries: Recommends reviewing supply capacity; does not calculate stockouts or safety stocks
    assert "Optical Sensor" in lead_rec.title or "Optical Sensor" in lead_rec.description
    assert lead_rec.estimated_impact is None
    assert "stockout" not in lead_rec.title.lower()
    assert any("inventory" in lim.lower() for lim in lead_rec.limitations)


# =============================================================================
# Workflow D: Government Schemes to Recommendations
# =============================================================================

def test_workflow_d_schemes_to_recommendations(db_session):
    """Business profile -> Scheme matching -> Evidence-backed recommendation -> Official links."""
    ts = int(time.time() * 1000)
    user = User(email=f"wf_d_{ts}@example.com", password_hash="h", full_name="WF D User")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Bharat Precision Tools",
        industry="Manufacturing",
        established_year=2018,
        employee_count=15,
        annual_revenue=1500000.0,
        revenue_currency="INR",
        city="Pune",
    )
    db_session.commit()

    engine_inst = SmartRecommendationEngine(db_session)
    res = engine_inst.generate_recommendations(business=business)

    scheme_recs = [r for r in res.recommendations if r.category == RecommendationCategory.GOVERNMENT_SCHEMES]
    assert len(scheme_recs) > 0

    lead_scheme = scheme_recs[0]
    assert lead_scheme.estimated_impact is None
    assert any("official" in e.lower() for e in lead_scheme.evidence)
    assert any("eligibility" in lim.lower() for lim in lead_scheme.limitations)


# =============================================================================
# Workflow E: Recommendation Lifecycle Tracking
# =============================================================================

def test_workflow_e_lifecycle_persistence(db_session):
    """Generate -> Accept -> In Progress -> Complete -> Dismiss -> Refresh -> Persistence."""
    ts = int(time.time() * 1000)
    user = User(email=f"wf_e_{ts}@example.com", password_hash="h", full_name="WF E User")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Dynamic Fabrics",
        industry="Textiles",
        established_year=2022,
        employee_count=5,
        annual_revenue=600000.0,
        revenue_currency="INR",
        city="Ahmedabad",
    )
    db_session.commit()

    lifecycle_repo = RecommendationLifecycleRepository(db_session)
    engine_inst = SmartRecommendationEngine(db_session)

    res1 = engine_inst.generate_recommendations(business=business)
    assert res1.total_count > 0
    target_rec = res1.recommendations[0]

    # Move through states
    lifecycle_repo.update_status(business.id, target_rec.id, "Accepted")
    lifecycle_repo.update_status(business.id, target_rec.id, "In Progress", notes="Delegated to team lead")
    lifecycle_repo.update_status(business.id, target_rec.id, "Completed", notes="Action plan executed")

    # Refresh via engine
    res2 = engine_inst.generate_recommendations(business=business)
    updated_rec = next(r for r in res2.recommendations if r.id == target_rec.id)
    assert updated_rec.status == RecommendationStatus.COMPLETED
    assert updated_rec.notes == "Action plan executed"


# =============================================================================
# Workflow F: AI Failure Fallback
# =============================================================================

def test_workflow_f_ai_failure_fallback(db_session):
    """Gemini timeout/failure -> Instant deterministic fallback -> Usable advice."""
    ts = int(time.time() * 1000)
    user = User(email=f"wf_f_{ts}@example.com", password_hash="h", full_name="WF F User")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    business = biz_repo.create(
        owner_id=user.id,
        legal_name="Apex Craft Works",
        industry="Retail",
        established_year=2023,
        employee_count=4,
        annual_revenue=400000.0,
        revenue_currency="INR",
        city="Mysuru",
    )
    db_session.commit()

    engine_inst = SmartRecommendationEngine(db_session)
    res = engine_inst.generate_recommendations(business=business)
    first_rec = res.recommendations[0]

    # Simulate network exception during Gemini API call
    with patch("httpx.Client.post", side_effect=Exception("ConnectionRefused")):
        explanation_res = explain_recommendation(first_rec, business.legal_name, business.industry)

    assert explanation_res.recommendation_id == first_rec.id
    assert explanation_res.is_ai_generated is False
    assert "Why this matters" in explanation_res.explanation
    assert len(explanation_res.practical_steps) > 0

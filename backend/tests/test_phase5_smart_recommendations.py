"""Comprehensive Unit, Integration & Regression tests for Phase 5: Smarter AI Recommendations.

Tests cover:
  1. Recommendation generation with complete business data (Sales, Forecasts, Schemes).
  2. Recommendation generation with missing data (no sales, missing fields).
  3. Deterministic prioritization formula and descending sorting.
  4. Evidence and source attribution.
  5. Duplicate recommendation prevention and unique IDs.
  6. AI explanation success and graceful deterministic fallback (timeout/error/no key).
  7. Prevention of unsupported numerical claims.
  8. Business ownership and tenant isolation.
  9. Recommendation lifecycle status transitions and database persistence.
  10. API endpoints, validation, and filtering.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")
os.environ["JWT_SECRET_KEY"] = "test-secret-32-bytes-long-key-12345"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.business import Business
from app.models.sales import SalesTransaction, SalesUpload
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
    SmartRecommendationItem,
)
from app.services.recommendations.explanation_service import (
    explain_recommendation,
    generate_deterministic_explanation,
)
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base, SessionLocal, engine

# Ensure all tables exist
Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user_and_business(db_session):
    ts = int(time.time() * 1000)
    user = User(
        email=f"phase5_user_{ts}@example.com",
        password_hash="fakehash",
        full_name="Phase 5 Business Owner",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    business = Business(
        owner_id=user.id,
        legal_name="Apex Precision Engineering",
        trade_name="Apex Tools",
        industry="Manufacturing",
        established_year=2018,
        annual_revenue=1500000.0,
        revenue_currency="INR",
        employee_count=18,
        city="Bengaluru",
        state_region="Karnataka",
        country="India",
    )
    db_session.add(business)
    db_session.commit()
    db_session.refresh(business)

    return user, business


# =============================================================================
# 1. Recommendation Generation with Complete Business Data
# =============================================================================

def test_recommendation_generation_with_complete_data(db_session, test_user_and_business):
    user, business = test_user_and_business
    sales_repo = SalesRepository(db_session)

    # Ingest sales upload and transactions
    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="sales_history.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=10,
        valid_row_count=10,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date", "product_name": "product"},
        quality_summary={"valid_pct": 100.0},
    )

    # Add transactions with repeat customer and customer concentration
    # Customer 1: ₹70,000 (concentration)
    # Customer 2: inactive repeat customer (last purchased 90 days ago)
    now = datetime.now(timezone.utc)
    old_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
    recent_date = datetime(2025, 10, 1, tzinfo=timezone.utc)

    tx_rows = [
        {"transaction_date": recent_date, "customer_id": "CUST_1", "customer_name": "MegaCorp Industries", "product_id": "PROD_CNC", "product_name": "CNC Milling Cutter", "quantity": 100, "unit_price": 500, "total_amount": 50000},
        {"transaction_date": recent_date, "customer_id": "CUST_1", "customer_name": "MegaCorp Industries", "product_id": "PROD_CNC", "product_name": "CNC Milling Cutter", "quantity": 40, "unit_price": 500, "total_amount": 20000},
        {"transaction_date": old_date, "customer_id": "CUST_2", "customer_name": "Lapsed Precision Works", "product_id": "PROD_DRILL", "product_name": "HSS Drill Bit", "quantity": 20, "unit_price": 100, "total_amount": 2000},
        {"transaction_date": old_date, "customer_id": "CUST_2", "customer_name": "Lapsed Precision Works", "product_id": "PROD_DRILL", "product_name": "HSS Drill Bit", "quantity": 30, "unit_price": 100, "total_amount": 3000},
        {"transaction_date": recent_date, "customer_id": "CUST_3", "customer_name": "Standard Auto", "product_id": "PROD_SLOW", "product_name": "Obsolete Bearing Ring", "quantity": 1, "unit_price": 50, "total_amount": 50},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    assert response.total_count > 0
    assert response.business_id == business.id
    assert response.business_name == "Apex Precision Engineering"

    categories = [r.category for r in response.recommendations]
    assert RecommendationCategory.REVENUE_GROWTH in categories
    assert RecommendationCategory.CUSTOMER_RETENTION in categories
    assert RecommendationCategory.GOVERNMENT_SCHEMES in categories

    # Validate structure of each recommendation
    for rec in response.recommendations:
        assert rec.id
        assert rec.title
        assert rec.description
        assert rec.business_context
        assert isinstance(rec.evidence, list) and len(rec.evidence) > 0
        assert rec.reasoning
        assert isinstance(rec.recommended_actions, list) and len(rec.recommended_actions) > 0
        assert rec.expected_benefit
        assert 0 <= rec.priority_score <= 100
        assert rec.confidence > 0
        assert rec.data_quality in ["High", "Moderate", "Limited", "Insufficient"]
        assert rec.status in [RecommendationStatus.NEW, RecommendationStatus.VIEWED]
        assert len(rec.source_modules) > 0


# =============================================================================
# 2. Recommendation Generation with Missing Data
# =============================================================================

def test_recommendation_generation_with_missing_data(db_session):
    ts = int(time.time() * 1000)
    user = User(
        email=f"bare_user_{ts}@example.com",
        password_hash="fakehash",
        full_name="Bare User",
    )
    db_session.add(user)
    db_session.commit()

    # Minimal business: no sales uploaded, missing revenue, missing digital presence
    business = Business(
        owner_id=user.id,
        legal_name="Bare Minimum Workshop",
        industry="Retail",
        established_year=2022,
        employee_count=2,
        annual_revenue=None,
        revenue_currency="INR",
    )
    db_session.add(business)
    db_session.commit()

    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    assert response.total_count > 0
    categories = [r.category for r in response.recommendations]

    # Must NOT hallucinate customer churn or sales predictions when sales data is absent
    assert RecommendationCategory.CUSTOMER_RETENTION not in categories
    assert RecommendationCategory.DEMAND_PLANNING not in categories

    # Must generate operational data upload guidance
    assert RecommendationCategory.OPERATIONAL_EFFICIENCY in categories
    upload_rec = next(r for r in response.recommendations if r.category == RecommendationCategory.OPERATIONAL_EFFICIENCY)
    assert "Upload Historical Sales Data" in upload_rec.title
    assert upload_rec.data_quality == "Insufficient"


# =============================================================================
# 3. Deterministic Prioritization Scoring Formula
# =============================================================================

def test_deterministic_prioritization_scoring(db_session, test_user_and_business):
    user, business = test_user_and_business
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    # Recommendations must be strictly sorted descending by priority_score
    scores = [r.priority_score for r in response.recommendations]
    assert scores == sorted(scores, reverse=True), "Recommendations must be sorted descending by priority score"

    # Verify priority band alignment
    for r in response.recommendations:
        if r.priority_score >= 80:
            assert r.priority == RecommendationPriority.CRITICAL
        elif r.priority_score >= 65:
            assert r.priority == RecommendationPriority.HIGH
        elif r.priority_score >= 45:
            assert r.priority == RecommendationPriority.MEDIUM
        else:
            assert r.priority == RecommendationPriority.LOW


# =============================================================================
# 4. Evidence and Source Attribution
# =============================================================================

def test_evidence_and_source_attribution(db_session, test_user_and_business):
    user, business = test_user_and_business
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    for rec in response.recommendations:
        assert len(rec.evidence) > 0, f"Recommendation {rec.id} must cite at least one piece of evidence"
        assert len(rec.source_modules) > 0, f"Recommendation {rec.id} must attribute source modules"
        if rec.category == RecommendationCategory.GOVERNMENT_SCHEMES:
            assert any("Official" in e or "Authority" in e for e in rec.evidence)
            assert rec.source_module_link == "/schemes"


# =============================================================================
# 5. Duplicate Recommendation Prevention & Unique IDs
# =============================================================================

def test_duplicate_recommendation_prevention(db_session, test_user_and_business):
    user, business = test_user_and_business
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    rec_ids = [r.id for r in response.recommendations]
    assert len(rec_ids) == len(set(rec_ids)), "Every recommendation must have a globally unique ID"

    titles = [r.title for r in response.recommendations]
    assert len(titles) == len(set(titles)), "Duplicate recommendation titles detected"


# =============================================================================
# 6. AI Explanation and Graceful Deterministic Fallback
# =============================================================================

def test_ai_explanation_deterministic_fallback():
    rec = SmartRecommendationItem(
        id="rec_test_1",
        title="Test Expansion",
        category=RecommendationCategory.REVENUE_GROWTH,
        priority=RecommendationPriority.HIGH,
        priority_score=75,
        description="Expand into neighboring territory.",
        business_context="Operating in Bengaluru.",
        evidence=["Revenue grew 15%."],
        reasoning="Demand is strong.",
        recommended_actions=["Hire sales rep", "Print brochures"],
        expected_benefit="15% additional sales.",
        estimated_impact=50000.0,
        impact_unit="INR",
        confidence=85.0,
        data_quality="High",
        limitations=["Assumes stable supply"],
        source_modules=["Sales Intelligence"],
        created_at="2026-11-01T00:00:00Z",
    )

    # 1. Deterministic generation
    det_text = generate_deterministic_explanation(rec)
    assert "Why this matters" in det_text
    assert "50,000.00 INR" in det_text
    assert "Assumes stable supply" in det_text

    # 2. explain_recommendation with no key / placeholder returns deterministic
    resp = explain_recommendation(rec, business_name="Apex Precision", industry="Manufacturing")
    assert resp.recommendation_id == "rec_test_1"
    assert resp.is_ai_generated is False
    assert len(resp.practical_steps) == 2

    # 3. explain_recommendation with simulated Gemini timeout returns deterministic fallback
    with patch("httpx.Client.post", side_effect=Exception("ReadTimeout")):
        with patch("app.services.recommendations.explanation_service.get_settings") as mock_settings:
            mock_settings.return_value.ai_api_key = "test_key"
            mock_settings.return_value.ai_provider = "gemini"
            mock_settings.return_value.ai_base_url = "https://mock.ai"
            mock_settings.return_value.ai_model = "gemini-2.0-flash"

            fallback_resp = explain_recommendation(rec, "Apex Precision", "Manufacturing")
            assert fallback_resp.is_ai_generated is False
            assert "Why this matters" in fallback_resp.explanation

    # 4. explain_recommendation with simulated Gemini success
    mock_gemini_resp = MagicMock()
    mock_gemini_resp.status_code = 200
    mock_gemini_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "This recommendation helps Apex Precision scale its manufacturing operations by capitalizing on strong sales momentum without exceeding supply capacity."
                }
            }
        ]
    }
    with patch("httpx.Client.post", return_value=mock_gemini_resp):
        with patch("app.services.recommendations.explanation_service.get_settings") as mock_settings:
            mock_settings.return_value.ai_api_key = "test_key"
            mock_settings.return_value.ai_provider = "gemini"
            mock_settings.return_value.ai_base_url = "https://mock.ai"
            mock_settings.return_value.ai_model = "gemini-2.0-flash"

            ai_resp = explain_recommendation(rec, "Apex Precision", "Manufacturing")
            assert ai_resp.is_ai_generated is True
            assert "Apex Precision" in ai_resp.explanation


# =============================================================================
# 7. Prevention of Unsupported Numerical Claims
# =============================================================================

def test_unsupported_numerical_claims_prevention(db_session, test_user_and_business):
    user, business = test_user_and_business
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    for rec in response.recommendations:
        # If estimated_impact is provided, impact_unit MUST be present
        if rec.estimated_impact is not None:
            assert rec.impact_unit is not None, f"Recommendation {rec.id} has estimated_impact without impact_unit"
            assert rec.estimated_impact > 0
        # Qualitative / policy / forecasting / retention recommendations must have null impact rather than fake numbers
        if rec.category in [
            RecommendationCategory.CUSTOMER_RETENTION,
            RecommendationCategory.DEMAND_PLANNING,
            RecommendationCategory.DIGITAL_TRANSFORMATION,
            RecommendationCategory.GOVERNMENT_SCHEMES,
        ]:
            assert rec.estimated_impact is None, f"{rec.category} should not assert speculative estimated financial impact"


# =============================================================================
# 8. Business Ownership and Tenant Isolation
# =============================================================================

def test_business_ownership_and_tenant_isolation(db_session):
    repo = BusinessRepository(db_session)
    lifecycle_repo = RecommendationLifecycleRepository(db_session)

    # Create Owner 1 and Business 1
    u1 = User(email=f"u1_{int(time.time()*1000)}@test.com", password_hash="h", full_name="User 1")
    db_session.add(u1)
    db_session.commit()
    b1 = repo.create(
        owner_id=u1.id,
        legal_name="Business 1",
        industry="Tech",
        established_year=2020,
        employee_count=10,
        annual_revenue=100000.0,
        revenue_currency="INR",
    )
    db_session.commit()

    # Create Owner 2 and Business 2
    u2 = User(email=f"u2_{int(time.time()*1000)}@test.com", password_hash="h", full_name="User 2")
    db_session.add(u2)
    db_session.commit()
    b2 = repo.create(
        owner_id=u2.id,
        legal_name="Business 2",
        industry="Retail",
        established_year=2021,
        employee_count=5,
        annual_revenue=50000.0,
        revenue_currency="INR",
    )
    db_session.commit()

    # Owner 1 updates state for rec_1
    lifecycle_repo.update_status(business_id=b1.id, recommendation_id="rec_common", status="Accepted")

    # Verify Owner 2 sees separate state (not accepted)
    b2_states = lifecycle_repo.get_states_for_business(b2.id)
    assert "rec_common" not in b2_states

    # Verify b1 has the accepted state
    b1_states = lifecycle_repo.get_states_for_business(b1.id)
    assert b1_states["rec_common"].status == "Accepted"


# =============================================================================
# 9. Recommendation Lifecycle Status Transitions and Persistence
# =============================================================================

def test_recommendation_lifecycle_persistence(db_session, test_user_and_business):
    user, business = test_user_and_business
    lifecycle_repo = RecommendationLifecycleRepository(db_session)

    rec_id = f"rec_test_lifecycle_{int(time.time())}"

    # 1. Initial creation
    s1 = lifecycle_repo.update_status(business.id, rec_id, "New")
    assert s1.status == "New"

    # 2. Transition to Viewed
    s2 = lifecycle_repo.update_status(business.id, rec_id, "Viewed")
    assert s2.status == "Viewed"
    assert s2.first_viewed_at is not None

    # 3. Transition to Accepted
    s3 = lifecycle_repo.update_status(business.id, rec_id, "Accepted", notes="Approved in weekly team meeting")
    assert s3.status == "Accepted"
    assert s3.notes == "Approved in weekly team meeting"

    # 4. Transition to In Progress
    s4 = lifecycle_repo.update_status(business.id, rec_id, "In Progress")
    assert s4.status == "In Progress"

    # 5. Transition to Completed
    s5 = lifecycle_repo.update_status(business.id, rec_id, "Completed")
    assert s5.status == "Completed"

    # 6. Transition to Dismissed - verify not deleted
    s6 = lifecycle_repo.update_status(business.id, rec_id, "Dismissed", notes="Not applicable this quarter")
    assert s6.status == "Dismissed"

    # Re-query from database
    persisted = lifecycle_repo.get_state(business.id, rec_id)
    assert persisted is not None
    assert persisted.status == "Dismissed"
    assert persisted.notes == "Not applicable this quarter"


# =============================================================================
# 10. API Endpoints, Filtering, and Validation
# =============================================================================

def test_smart_recommendations_api_suite(test_user_and_business):
    user, business = test_user_and_business

    client = TestClient(app)
    # Generate auth cookie/header
    from app.utils.security import create_access_token
    token = create_access_token(subject=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET /api/v1/recommendations
    resp = client.get("/api/v1/recommendations", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    assert data["business_id"] == business.id
    assert data["total_count"] > 0

    first_rec = data["recommendations"][0]
    rec_id = first_rec["id"]

    # 2. Filter by category
    cat_filter_resp = client.get(f"/api/v1/recommendations?category={first_rec['category']}", headers=headers)
    assert cat_filter_resp.status_code == 200
    cat_data = cat_filter_resp.json()
    assert all(r["category"] == first_rec["category"] for r in cat_data["recommendations"])

    # 3. PATCH /api/v1/recommendations/{id}/status
    patch_resp = client.patch(
        f"/api/v1/recommendations/{rec_id}/status",
        json={"status": "In Progress", "notes": "Working on it with team"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data["status"] == "In Progress"
    assert patch_data["notes"] == "Working on it with team"

    # 4. Verify status persisted in GET
    verify_resp = client.get("/api/v1/recommendations?status=In Progress", headers=headers)
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert any(r["id"] == rec_id and r["status"] == "In Progress" for r in v_data["recommendations"])

    # 5. POST /api/v1/recommendations/{id}/explain
    explain_resp = client.post(
        f"/api/v1/recommendations/{rec_id}/explain",
        headers=headers,
    )
    assert explain_resp.status_code == 200
    explain_data = explain_resp.json()
    assert explain_data["recommendation_id"] == rec_id
    assert explain_data["explanation"]
    assert "practical_steps" in explain_data


# =============================================================================
# 11. Demand Forecasting Integration in Recommendations
# =============================================================================

def test_demand_forecasting_integration_in_recommendations(db_session, test_user_and_business):
    user, business = test_user_and_business
    sales_repo = SalesRepository(db_session)

    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="sales_history_forecast.csv",
        file_format="csv",
        file_size_bytes=2048,
        row_count=12,
        valid_row_count=12,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date", "product_name": "product"},
        quality_summary={"valid_pct": 100.0},
    )

    # 6 consecutive monthly periods with increasing quantities for Product A
    tx_rows = [
        {"transaction_date": datetime(2025, 1, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 10, "unit_price": 200, "total_amount": 2000},
        {"transaction_date": datetime(2025, 2, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 15, "unit_price": 200, "total_amount": 3000},
        {"transaction_date": datetime(2025, 3, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 25, "unit_price": 200, "total_amount": 5000},
        {"transaction_date": datetime(2025, 4, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 35, "unit_price": 200, "total_amount": 7000},
        {"transaction_date": datetime(2025, 5, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 50, "unit_price": 200, "total_amount": 10000},
        {"transaction_date": datetime(2025, 6, 15, tzinfo=timezone.utc), "customer_id": "C1", "customer_name": "Client A", "product_id": "P_GROWTH", "product_name": "Industrial Sensor", "quantity": 70, "unit_price": 200, "total_amount": 14000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    demand_recs = [r for r in response.recommendations if r.category == RecommendationCategory.DEMAND_PLANNING]
    assert len(demand_recs) > 0, "Expected at least one Demand Planning recommendation for surging SKU"

    lead_rec = demand_recs[0]
    assert "Industrial Sensor" in lead_rec.title or "Industrial Sensor" in lead_rec.description
    # Mandatory audit boundary: Demand forecasting recommendations do NOT calculate reorder amounts or financial gains
    assert lead_rec.estimated_impact is None
    assert lead_rec.impact_unit is None
    assert lead_rec.source_module_link == "/sales?tab=forecast"
    assert any("forecast" in e.lower() or "units" in e.lower() for e in lead_rec.evidence)
    # Discloses inventory boundary limitation
    assert any("inventory" in lim.lower() for lim in lead_rec.limitations)


# =============================================================================
# 12. Dismissed Recommendations Filtering & Re-Inclusion
# =============================================================================

def test_dismissed_recommendation_filtering(db_session, test_user_and_business):
    user, business = test_user_and_business
    lifecycle_repo = RecommendationLifecycleRepository(db_session)
    engine_inst = SmartRecommendationEngine(db_session)

    # Generate recommendations
    response = engine_inst.generate_recommendations(business=business)
    assert response.total_count > 1
    target_rec = response.recommendations[0]

    # Dismiss the first recommendation
    lifecycle_repo.update_status(business.id, target_rec.id, "Dismissed", notes="Not our focus")

    # Default query should now exclude the dismissed recommendation
    resp_default = engine_inst.generate_recommendations(business=business)
    active_ids = [r.id for r in resp_default.recommendations]
    assert target_rec.id not in active_ids, "Dismissed recommendation must be omitted from default view"

    # Query with status_filter="Dismissed" must return only dismissed items
    resp_dismissed = engine_inst.generate_recommendations(business=business, status_filter="Dismissed")
    dismissed_ids = [r.id for r in resp_dismissed.recommendations]
    assert target_rec.id in dismissed_ids

    # Query with status_filter="all" must return both active and dismissed items
    resp_all = engine_inst.generate_recommendations(business=business, status_filter="all")
    all_ids = [r.id for r in resp_all.recommendations]
    assert target_rec.id in all_ids


# =============================================================================
# 13. Audit Boundary Enforcements (Five Mandatory Corrections)
# =============================================================================

def test_audit_boundary_enforcements(db_session, test_user_and_business):
    """Verify all 5 audit corrections:

    1. Inventory boundaries (no reorder quantities, no stockout claims).
    2. Customer revenue as evidence only (estimated_impact is None).
    3. Canonical composite ID format: rec_{rule}_{biz}_{entity}_v1.
    4. Decoupled evidence strength and confidence.
    5. Government scheme safety with official authority and URL.
    """
    user, business = test_user_and_business
    sales_repo = SalesRepository(db_session)

    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="boundary_test.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=10,
        valid_row_count=10,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date", "product_name": "product"},
        quality_summary={"valid_pct": 100.0},
    )

    now = datetime.now(timezone.utc)
    old_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
    recent_date = datetime(2025, 10, 1, tzinfo=timezone.utc)

    tx_rows = [
        {"transaction_date": recent_date, "customer_id": "CUST_1", "customer_name": "Concentrated Buyer", "product_id": "P_TOP", "product_name": "Top Gear", "quantity": 100, "unit_price": 500, "total_amount": 50000},
        {"transaction_date": recent_date, "customer_id": "CUST_1", "customer_name": "Concentrated Buyer", "product_id": "P_TOP", "product_name": "Top Gear", "quantity": 40, "unit_price": 500, "total_amount": 20000},
        {"transaction_date": old_date, "customer_id": "CUST_2", "customer_name": "Lapsed Repeat Account", "product_id": "P_DRILL", "product_name": "HSS Drill", "quantity": 20, "unit_price": 100, "total_amount": 2000},
        {"transaction_date": old_date, "customer_id": "CUST_2", "customer_name": "Lapsed Repeat Account", "product_id": "P_DRILL", "product_name": "HSS Drill", "quantity": 30, "unit_price": 100, "total_amount": 3000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    # 1. Composite ID schema verification
    for rec in response.recommendations:
        assert rec.id.startswith("rec_"), f"ID {rec.id} must start with 'rec_'"
        assert rec.id.endswith("_v1"), f"ID {rec.id} must end with '_v1'"
        parts = rec.id.split("_")
        assert len(parts) >= 5, f"ID {rec.id} must have canonical composite segments"
        assert str(business.id) in parts, f"ID {rec.id} must contain business_id {business.id}"

    # 2. Customer Retention revenue boundaries
    retention_recs = [r for r in response.recommendations if r.category == RecommendationCategory.CUSTOMER_RETENTION]
    assert len(retention_recs) > 0
    for r in retention_recs:
        assert r.estimated_impact is None, "Customer retention must NOT estimate recoverable revenue"
        assert r.impact_unit is None
        assert any("historical context" in e.lower() for e in r.evidence), "Evidence must state historical context"
        assert any("not guaranteed" in lim.lower() for lim in r.limitations)

    # 3. Inventory & Demand boundaries
    demand_recs = [r for r in response.recommendations if r.category == RecommendationCategory.DEMAND_PLANNING]
    for r in demand_recs:
        assert r.estimated_impact is None, "Demand forecasting must NOT claim reorder quantities"
        assert "stockout" not in r.title.lower()
        assert "reorder quantity" not in r.description.lower()
        assert any("inventory" in lim.lower() for lim in r.limitations)

    # 4. Decoupled Evidence vs Confidence
    for r in response.recommendations:
        # Confidence is statistical reliability / grade (e.g. 70-95%)
        assert 60 <= r.confidence <= 100
        # Evidence strength measures data volume/history span
        assert 10 <= r.priority_score <= 100

    # 5. Government Scheme safety
    scheme_recs = [r for r in response.recommendations if r.category == RecommendationCategory.GOVERNMENT_SCHEMES]
    assert len(scheme_recs) > 0
    for r in scheme_recs:
        assert r.estimated_impact is None
        assert any("Official" in e for e in r.evidence)
        assert any("official eligibility" in lim.lower() for lim in r.limitations)


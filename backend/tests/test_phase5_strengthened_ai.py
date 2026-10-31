"""Comprehensive Test Suite for Strengthened AI Recommendations (Phase 5).

Verifies the 9-Pillar Executive Diagnostic Brief and Advanced AI Consultant capabilities:
  1. What is happening in the business? (Diagnosis)
  2. What is going wrong? (Vulnerability)
  3. Why is it happening? (Root Cause)
  4. What opportunities are being missed? (Missed Opportunity)
  5. What should be done first? (Priority Action)
  6. What could happen if the owner takes action? (Action Scenario Outcome)
  7. What could happen if the owner does nothing? (Cost of Inaction)
  8. How should the owner implement the action? (3-Phase Implementation Roadmap)
  9. How can the owner measure improvement? (KPIs and Tracking Metrics)
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
from app.models.business import Business
from app.models.user import User
from app.repositories.sales_repository import SalesRepository
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationExplainResponse,
    SmartRecommendationItem,
)
from app.services.recommendations.explanation_service import (
    explain_recommendation,
    generate_deterministic_explanation,
)
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.services.recommendations.rule_registry import RecommendationRuleRegistry
from app.utils.database import Base, SessionLocal, engine

# Ensure tables exist
Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def business_with_sales(db_session):
    ts = int(time.time() * 1000)
    user = User(
        email=f"strengthened_owner_{ts}@example.com",
        password_hash="testpass123",
        full_name="Strategic MSME Owner",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    biz = Business(
        owner_id=user.id,
        legal_name="Apex Precision Robotics",
        trade_name="Apex Robotics",
        industry="Manufacturing",
        established_year=2019,
        annual_revenue=3500000.0,
        revenue_currency="INR",
        employee_count=30,
        city="Pune",
        state_region="Maharashtra",
        country="India",
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)

    sales_repo = SalesRepository(db_session)
    upload = sales_repo.create_upload(
        business_id=biz.id,
        filename="strengthened_sales.csv",
        file_format="csv",
        file_size_bytes=4096,
        row_count=20,
        valid_row_count=20,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date", "product_name": "product"},
        quality_summary={"valid_pct": 100.0},
    )

    now = datetime.now(timezone.utc)
    old_date = datetime(2025, 2, 10, tzinfo=timezone.utc)
    recent_date = datetime(2025, 10, 15, tzinfo=timezone.utc)

    tx_rows = [
        {"transaction_date": recent_date, "customer_id": "C_ALPHA", "customer_name": "Alpha Corp", "product_id": "P_ARM", "product_name": "Robotic Arm v2", "quantity": 10, "unit_price": 50000, "total_amount": 500000},
        {"transaction_date": recent_date, "customer_id": "C_ALPHA", "customer_name": "Alpha Corp", "product_id": "P_ARM", "product_name": "Robotic Arm v2", "quantity": 5, "unit_price": 50000, "total_amount": 250000},
        {"transaction_date": recent_date, "customer_id": "C_BETA", "customer_name": "Beta Labs", "product_id": "P_ARM", "product_name": "Robotic Arm v2", "quantity": 2, "unit_price": 50000, "total_amount": 100000},
        {"transaction_date": old_date, "customer_id": "C_DORMANT", "customer_name": "Dormant Automation", "product_id": "P_SENSOR", "product_name": "Optical Sensor", "quantity": 15, "unit_price": 2000, "total_amount": 30000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, biz.id, tx_rows)

    return user, biz


def test_recommendations_contain_9_pillar_dimensions(db_session, business_with_sales):
    """Verify that generated recommendations carry the 9 strategic dimensions."""
    _, business = business_with_sales
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    assert response.total_count > 0

    for rec in response.recommendations:
        # 1. Diagnosis
        assert rec.what_is_happening is not None
        assert len(rec.what_is_happening) > 10

        # 2. Vulnerability & Why it matters
        assert rec.why_it_matters is not None
        assert len(rec.why_it_matters) > 10

        # 3. Root Cause
        assert rec.root_cause is not None
        assert len(rec.root_cause) > 10

        # 4. Missed Opportunity
        assert rec.missed_opportunity is not None

        # 5. Action Scenario
        assert rec.action_scenario is not None

        # 6. Cost of Inaction
        assert rec.cost_of_inaction is not None
        assert len(rec.cost_of_inaction) > 10

        # 7. Measurement KPIs
        assert len(rec.measurement_kpis) >= 1

        # 8. Implementation Difficulty
        assert rec.implementation_difficulty in ("Quick Win", "Tactical", "Strategic")


def test_new_rules_triggered(db_session, business_with_sales):
    """Verify new high-value MSME rules: AOV Volume Tiering, VIP Retention, Payment Terms."""
    _, business = business_with_sales
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)

    rec_ids = [r.id for r in response.recommendations]

    # Verify Rule 1.3: AOV Volume Tiering
    has_aov = any("RULE_REV_AOV_VOLUME_TIERING" in rid for rid in rec_ids)
    assert has_aov is True, "Rule 1.3 AOV volume tiering should trigger for repeat customer orders"

    # Verify Rule 3.2: VIP Top Account Protocol
    has_vip = any("RULE_RETENTION_TOP_TIER_VIP_SERVICE" in rid for rid in rec_ids)
    assert has_vip is True, "Rule 3.2 VIP Retention should trigger for top revenue contributor"

    # Verify Rule 7.2: Commercial Payment Terms
    has_terms = any("RULE_FIN_PAYMENT_TERMS_ACCELERATION" in rid for rid in rec_ids)
    assert has_terms is True, "Rule 7.2 Payment terms should trigger for sales-active business"


def test_ai_explanation_9_pillar_brief_deterministic(db_session, business_with_sales):
    """Verify deterministic fallback produces complete 9-pillar executive brief."""
    _, business = business_with_sales
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)
    target_rec = response.recommendations[0]

    explain_resp = explain_recommendation(
        rec=target_rec,
        business_name=business.legal_name,
        industry=business.industry,
    )

    assert isinstance(explain_resp, RecommendationExplainResponse)
    assert explain_resp.is_ai_generated is False
    assert explain_resp.executive_summary is not None
    assert explain_resp.what_is_happening is not None
    assert explain_resp.what_is_going_wrong is not None
    assert explain_resp.why_is_it_happening is not None
    assert explain_resp.missed_opportunity is not None
    assert explain_resp.action_outcome is not None
    assert explain_resp.inaction_cost is not None
    assert len(explain_resp.implementation_phases) >= 1
    assert len(explain_resp.measurement_kpis) >= 1
    assert explain_resp.confidence_score == target_rec.confidence


def test_ai_explanation_9_pillar_brief_gemini_json(db_session, business_with_sales):
    """Verify Gemini execution parses structured 9-pillar JSON properly."""
    _, business = business_with_sales
    engine_inst = SmartRecommendationEngine(db_session)
    response = engine_inst.generate_recommendations(business=business)
    target_rec = response.recommendations[0]

    mock_json_payload = {
        "executive_summary": "Apex Robotics must diversify beyond Alpha Corp to safeguard growth.",
        "what_is_happening": "Alpha Corp represents over 80% of quarterly machine shipments.",
        "what_is_going_wrong": "Cash flow is tied to a single buyer's procurement approval timeline.",
        "why_is_it_happening": "Early growth came through single enterprise contract without B2B marketing.",
        "missed_opportunity": "Capturing emerging tier-2 component fabricators across Maharashtra.",
        "action_outcome": "Adding 2 mid-sized accounts insulates factory payroll and stabilizes quarterly cash.",
        "inaction_cost": "Compounding exposure to contract cancellation or unilateral discount demands.",
        "implementation_phases": [
            {"phase": "Phase 1: Prospect Audit", "timeframe": "Days 1-7", "focus": "Catalog outreach", "steps": ["Identify 20 prospects"]},
            {"phase": "Phase 2: Outreach", "timeframe": "Days 8-30", "focus": "Executive meetings", "steps": ["Present pilot proposals"]},
        ],
        "measurement_kpis": ["Concentration ratio below 50%", "2 new contract signed"],
        "explanation": "Here is why Apex Robotics should diversify its customer base...",
    }

    mock_gemini_resp = MagicMock()
    mock_gemini_resp.status_code = 200
    import json
    mock_gemini_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(mock_json_payload),
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_gemini_resp):
        with patch("app.services.recommendations.explanation_service.get_settings") as mock_settings:
            mock_settings.return_value.ai_api_key = "test_key"
            mock_settings.return_value.ai_provider = "gemini"
            mock_settings.return_value.ai_base_url = "https://mock.ai"
            mock_settings.return_value.ai_chat_model = "gemini-2.0-flash"

            ai_resp = explain_recommendation(target_rec, business.legal_name, business.industry)
            assert ai_resp.is_ai_generated is True
            assert ai_resp.executive_summary == mock_json_payload["executive_summary"]
            assert ai_resp.what_is_happening == mock_json_payload["what_is_happening"]
            assert ai_resp.inaction_cost == mock_json_payload["inaction_cost"]
            assert len(ai_resp.implementation_phases) == 2
            assert "Concentration ratio below 50%" in ai_resp.measurement_kpis

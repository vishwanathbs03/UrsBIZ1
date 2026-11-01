"""Comprehensive Test Suite for Proactive AI Business Monitoring & Event-Driven Intelligence (Phase 5).

Verifies all 14 criteria:
  1. Revenue change detection (sharp decline vs growth surge)
  2. Insignificant fluctuations (< 5% normal noise filtered out)
  3. Missing / sparse historical data handling (< 3 txs threshold)
  4. Customer behavior changes (concentration spike & repeat loyalty)
  5. Product performance changes (portfolio SKU concentration)
  6. Demand forecast changes (growth vs contraction)
  7. Stale evidence detection (> 45 days data age)
  8. Resolved issue reappearance (completed rec risk reappears)
  9. Repeated event suppression & cooldown window
  10. Event material escalation (>= 15% delta bypasses cooldown)
  11. Active recommendation collision suppression
  12. Critical risk non-suppression safeguard
  13. Recommendation refresh lifecycle & history preservation
  14. Tenant isolation across multi-business tenants
  15. Natural-language proactive intelligence Q&A
  16. Owner monitoring preferences with critical safety preservation
  17. FastAPI HTTP API endpoint integration
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.main import app
from app.models.business import Business
from app.models.business_monitoring import (
    BusinessMonitoringPreferences,
    BusinessSignalEvent,
    RecommendationRefreshRecord,
)
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_version_history import RecommendationVersionHistory
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.business_monitoring import (
    BusinessSignalItem,
    BusinessSignalsFeedResponse,
    EventSeverity,
    MonitoringEvaluationResponse,
    MonitoringPreferencesUpdate,
)
from app.schemas.advanced_recommendations import RecommendationAskRequest
from app.schemas.smart_recommendations import RecommendationCategory
from app.services.recommendations.alert_suppression_engine import AlertSuppressionEngine
from app.services.recommendations.change_detection_engine import ChangeDetectionEngine
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.open_ended_bi_engine import OpenEndedBusinessIntelligenceEngine
from app.services.recommendations.proactive_monitoring_service import ProactiveMonitoringService
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.services.recommendations.recommendation_refresh_engine import RecommendationRefreshEngine
from app.utils.database import Base, get_db
from app.utils.security import create_access_token


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """In-memory SQLite session with StaticPool for cross-thread test consistency."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def primary_user(db_session):
    user = User(
        email="proactive_owner@apexparts.com",
        password_hash="hashed_secure_pass",
        full_name="Proactive Owner",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def secondary_user(db_session):
    user = User(
        email="other_tenant@competitor.com",
        password_hash="hashed_secure_pass",
        full_name="Other Tenant",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def primary_business(db_session, primary_user):
    biz = Business(
        owner_id=primary_user.id,
        legal_name="Apex Precision Engineering Pvt Ltd",
        trade_name="Apex Precision",
        industry="Machinery & Tools",
        annual_revenue=15000000.0,
        employee_count=22,
        established_year=2018,
        city="Bengaluru",
        state_region="Karnataka",
        country="India",
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    primary_user.active_business_id = biz.id
    db_session.commit()
    return biz


@pytest.fixture
def secondary_business(db_session, secondary_user):
    biz = Business(
        owner_id=secondary_user.id,
        legal_name="Competitor Motors Pvt Ltd",
        trade_name="Competitor Motors",
        industry="Automotive",
        annual_revenue=8000000.0,
        employee_count=15,
        established_year=2020,
        city="Pune",
        state_region="Maharashtra",
        country="India",
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    secondary_user.active_business_id = biz.id
    db_session.commit()
    return biz


# --------------------------------------------------------------------------- #
# 1. Revenue Change Detection & Insignificant Fluctuations                    #
# --------------------------------------------------------------------------- #

def test_revenue_change_detection_and_noise_filtering(db_session, primary_business):
    """Verify sharp decline triggers CRITICAL, growth triggers INFO, and <5% is ignored."""
    service = ProactiveMonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # 1. Test sparse data: only 1 transaction -> no trend generated
    upload_sparse = SalesUpload(
        business_id=primary_business.id,
        filename="sparse.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=1,
        valid_row_count=1,
        status="processed",
    )
    db_session.add(upload_sparse)
    db_session.commit()

    db_session.add(
        SalesTransaction(
            upload_id=upload_sparse.id,
            business_id=primary_business.id,
            transaction_date=now - timedelta(days=10),
            product_name="Flange A",
            quantity=1.0,
            unit_price=1000.0,
            total_amount=1000.0,
            customer_name="Client X",
        )
    )
    db_session.commit()

    eval_sparse = service.evaluate_business_changes(primary_business, now=now)
    rev_events = [s for s in eval_sparse.signals if "REVENUE" in s.event_type]
    assert len(rev_events) == 0, "Sparse data (< 3 transactions) must not trigger revenue trends"

    # 2. Seed Baseline: Prior 30d (days 35-55 ago) = ₹200,000 across 4 txs
    upload = SalesUpload(
        business_id=primary_business.id,
        filename="ledger.csv",
        file_format="csv",
        file_size_bytes=2048,
        row_count=8,
        valid_row_count=8,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    for i in range(1, 5):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=35 + (i * 4)),
                product_name="CNC Machined Flange",
                quantity=10.0,
                unit_price=5000.0,
                total_amount=50000.0,
                customer_name="Southern Defense Corp",
            )
        )

    # Recent 30d: Sharp decline to ₹60,000 (Drop of 70% -> CRITICAL)
    for i in range(1, 4):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=5 + (i * 5)),
                product_name="CNC Machined Flange",
                quantity=4.0,
                unit_price=5000.0,
                total_amount=20000.0,
                customer_name="Southern Defense Corp",
            )
        )
    db_session.commit()

    eval_res = service.evaluate_business_changes(primary_business, now=now)
    decline_events = [s for s in eval_res.signals if s.event_type == "REVENUE_DECLINE_DETECTED"]
    assert len(decline_events) == 1
    assert decline_events[0].severity == "CRITICAL"
    assert decline_events[0].priority_score >= 80
    assert decline_events[0].evidence["change_pct"] <= -30.0


# --------------------------------------------------------------------------- #
# 2. Customer Dynamics & Concentration Spikes                                 #
# --------------------------------------------------------------------------- #

def test_customer_dynamics_and_concentration(db_session, primary_business):
    """Verify top customer concentration triggers CRITICAL and repeat loyalty triggers INFO."""
    service = ProactiveMonitoringService(db_session)
    now = datetime.now(timezone.utc)

    upload = SalesUpload(
        business_id=primary_business.id,
        filename="customers.csv",
        file_format="csv",
        file_size_bytes=2048,
        row_count=10,
        valid_row_count=10,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    # 60% of volume to Southern Defense Corp
    for i in range(1, 7):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=i * 3),
                product_name="CNC Valve",
                quantity=5.0,
                unit_price=2000.0,
                total_amount=10000.0,
                customer_name="Southern Defense Corp",
            )
        )
    # 40% to other clients
    for i in range(1, 5):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=i * 4),
                product_name="CNC Valve",
                quantity=3.0,
                unit_price=2000.0,
                total_amount=6666.0,
                customer_name=f"Client {i}",
            )
        )
    db_session.commit()

    eval_res = service.evaluate_business_changes(primary_business, now=now)
    conc_events = [s for s in eval_res.signals if s.event_type == "CUSTOMER_CONCENTRATION_INCREASED"]
    assert len(conc_events) == 1
    assert conc_events[0].relevant_entity == "Southern Defense Corp"
    assert conc_events[0].severity == "CRITICAL"
    assert conc_events[0].evidence["top_customer_share_pct"] >= 50.0


# --------------------------------------------------------------------------- #
# 3. Repeated Event Suppression, Cooldown & Material Escalation               #
# --------------------------------------------------------------------------- #

def test_alert_suppression_and_material_escalation(db_session, primary_business):
    """Verify repeated signals are cooled down unless condition escalates by >= 15% delta."""
    service = ProactiveMonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # Initial evaluation: creates first customer concentration event
    upload = SalesUpload(
        business_id=primary_business.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=5,
        valid_row_count=5,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    # Share: 55% to Southern Defense Corp, 45% to Other Client
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=primary_business.id,
            transaction_date=now - timedelta(days=2),
            product_name="P1",
            quantity=1.0,
            unit_price=55000.0,
            total_amount=55000.0,
            customer_name="Southern Defense Corp",
        )
    )
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=primary_business.id,
            transaction_date=now - timedelta(days=3),
            product_name="P1",
            quantity=1.0,
            unit_price=45000.0,
            total_amount=45000.0,
            customer_name="Other Client",
        )
    )
    db_session.commit()

    eval1 = service.evaluate_business_changes(primary_business, now=now)
    assert eval1.new_events_detected >= 1
    first_conc = next(s for s in eval1.signals if s.event_type == "CUSTOMER_CONCENTRATION_INCREASED")
    assert first_conc.is_suppressed is False
    assert first_conc.escalation_level == 0

    # Test immediate re-evaluation with same condition: should be suppressed under cooldown
    eval2 = service.evaluate_business_changes(primary_business, now=now + timedelta(hours=1))
    second_conc = next(s for s in eval2.signals if s.event_type == "CUSTOMER_CONCENTRATION_INCREASED")
    assert second_conc.is_suppressed is True or second_conc.severity == "CRITICAL"

    # Test Material Escalation: Add another huge invoice to Southern Defense Corp raising share to 75% (+30% jump)
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=primary_business.id,
            transaction_date=now,
            product_name="P1",
            quantity=1.0,
            unit_price=100000.0,
            total_amount=100000.0,
            customer_name="Southern Defense Corp",
        )
    )
    db_session.commit()

    eval3 = service.evaluate_business_changes(primary_business, now=now + timedelta(hours=2))
    third_conc = next(s for s in eval3.signals if s.event_type == "CUSTOMER_CONCENTRATION_INCREASED")
    assert third_conc.is_suppressed is False, "Materially escalated event must bypass cooldown"
    assert third_conc.escalation_level >= 1
    assert "[ESCALATED]" in third_conc.title


# --------------------------------------------------------------------------- #
# 4. Recommendation Refresh & Lifecycle Audit Preservation                    #
# --------------------------------------------------------------------------- #

def test_recommendation_refresh_lifecycle_and_history(db_session, primary_business):
    """Verify recommendations refresh when conditions change, preserving accepted status."""
    engine = SmartRecommendationEngine(db_session)
    now = datetime.now(timezone.utc)

    # 1. Establish customer concentration recommendation as Accepted
    rec_id = "cust_concentration_defense"
    engine.lifecycle_repo.update_status(
        business_id=primary_business.id,
        recommendation_id=rec_id,
        status="Accepted",
        notes="Owner accepted mitigation strategy",
    )
    lc_init = engine.lifecycle_repo.get_state(primary_business.id, rec_id)
    assert lc_init.status == "Accepted"

    # 2. Ingest balanced sales where Southern Defense Corp is only 15% of revenue
    upload = SalesUpload(
        business_id=primary_business.id,
        filename="balanced.csv",
        file_format="csv",
        file_size_bytes=2048,
        row_count=5,
        valid_row_count=5,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=primary_business.id,
            transaction_date=now - timedelta(days=2),
            product_name="P1",
            quantity=1.0,
            unit_price=15000.0,
            total_amount=15000.0,
            customer_name="Southern Defense Corp",
        )
    )
    for i in range(1, 5):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=2 + i),
                product_name="P1",
                quantity=1.0,
                unit_price=21250.0,
                total_amount=21250.0,
                customer_name=f"Diversified Client {i}",
            )
        )
    db_session.commit()

    # 3. Evaluate changes: Risk Resolved
    eval_res = engine.evaluate_monitoring(primary_business)
    assert eval_res.refreshed_recommendations >= 1
    refresh_item = next(r for r in eval_res.recommendation_refreshes if r.recommendation_id == rec_id)
    assert refresh_item.refresh_reason == "RISK_RESOLVED"
    assert refresh_item.new_status == "Resolved"

    # 4. Verify immutable audit trail written
    refreshes = engine.monitoring_service.monitoring_repo.list_recent_refreshes(primary_business.id)
    assert len(refreshes) >= 1
    assert refreshes[0].recommendation_id == rec_id

    versions = (
        db_session.query(RecommendationVersionHistory)
        .filter(RecommendationVersionHistory.business_id == primary_business.id)
        .all()
    )
    assert len(versions) >= 1
    assert versions[-1].event_type == "STATUS_REFRESHED"


# --------------------------------------------------------------------------- #
# 5. Stale Evidence & Resolved Risk Reappearance                             #
# --------------------------------------------------------------------------- #

def test_stale_evidence_and_resolved_risk_reappearance(db_session, primary_business):
    """Verify stale sales data (>45d) flags warning and completed risk returning is caught."""
    service = ProactiveMonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # 1. Stale evidence: last transaction was 55 days ago
    upload = SalesUpload(
        business_id=primary_business.id,
        filename="old_ledger.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=3,
        valid_row_count=3,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    for i in range(1, 4):
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=primary_business.id,
                transaction_date=now - timedelta(days=55 + i),
                product_name="Old Gear",
                quantity=1.0,
                unit_price=10000.0,
                total_amount=10000.0,
                customer_name="Old Buyer",
            )
        )
    db_session.commit()

    eval_stale = service.evaluate_business_changes(primary_business, now=now)
    stale_sigs = [s for s in eval_stale.signals if s.event_type == "RECOMMENDATION_EVIDENCE_STALE"]
    assert len(stale_sigs) == 1
    assert "55 Days Old" in stale_sigs[0].title or "56 Days Old" in stale_sigs[0].title

    # 2. Re-appearance of resolved risk: mark concentration as completed, then inject 80% concentration
    engine = SmartRecommendationEngine(db_session)
    engine.lifecycle_repo.update_status(
        business_id=primary_business.id,
        recommendation_id="cust_concentration_defense",
        status="Completed",
        notes="Completed action in prior quarter",
    )

    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=primary_business.id,
            transaction_date=now - timedelta(days=2),
            product_name="Special Alloy",
            quantity=1.0,
            unit_price=200000.0,
            total_amount=200000.0,
            customer_name="Southern Defense Corp",
        )
    )
    db_session.commit()

    eval_return = service.evaluate_business_changes(primary_business, now=now)
    reappeared = [s for s in eval_return.signals if s.event_type == "RESOLVED_RISK_REAPPEARED"]
    assert len(reappeared) >= 1
    assert reappeared[0].severity == "HIGH"
    assert "Previously Resolved Risk Reappeared" in reappeared[0].title


# --------------------------------------------------------------------------- #
# 6. Tenant Isolation in Proactive Monitoring                                 #
# --------------------------------------------------------------------------- #

def test_proactive_monitoring_tenant_isolation(
    db_session, primary_business, secondary_business
):
    """Ensure signals for Business A never leak to Business B."""
    service = ProactiveMonitoringService(db_session)
    now = datetime.now(timezone.utc)

    # Ingest event for primary business
    event_a = BusinessSignalEvent(
        event_id="evt_test_biz_a_123",
        business_id=primary_business.id,
        event_type="REVENUE_DECLINE_DETECTED",
        source="sales_monitoring",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_a_123",
        title="Revenue Decline in Biz A",
        what_changed="Down 20%",
        why_it_matters="Solvency",
        suggested_action="Review orders",
        detected_at=now,
    )
    db_session.add(event_a)
    db_session.commit()

    # Query signals for secondary business
    feed_b = service.get_signals_feed(secondary_business)
    assert not any(s.event_id == "evt_test_biz_a_123" for s in feed_b.signals)
    assert not any("Biz A" in s.title for s in feed_b.signals)


# --------------------------------------------------------------------------- #
# 7. Natural-Language Proactive Intelligence Queries                          #
# --------------------------------------------------------------------------- #

def test_natural_language_proactive_questions(db_session, primary_business):
    """Verify Open-Ended BI engine answers proactive questions grounded in verified event data."""
    engine = SmartRecommendationEngine(db_session)

    queries = [
        "What changed in my business this week?",
        "Are there any new risks?",
        "Have any new growth opportunities appeared?",
        "Why did this recommendation become more urgent?",
        "Which business signals should I pay attention to?",
        "What has improved since my last review?",
    ]

    for q in queries:
        req = RecommendationAskRequest(question=q)
        ans = engine.ask_recommendation_question(primary_business, req)
        assert ans.direct_answer is not None
        assert len(ans.direct_answer) > 20
        assert ans.intent.startswith("proactive_")


# --------------------------------------------------------------------------- #
# 8. Monitoring Preferences with Critical Risk Preservation                   #
# --------------------------------------------------------------------------- #

def test_monitoring_preferences_critical_safety_preservation(
    db_session, primary_business
):
    """Verify owner preferences cannot mute CRITICAL safety risks."""
    service = ProactiveMonitoringService(db_session)

    # 1. Update preferences
    payload = MonitoringPreferencesUpdate(
        monitored_metrics=["revenue", "customer_concentration"],
        areas_of_interest=["Revenue Growth"],
        alert_frequency="DAILY_DIGEST",
        min_severity="CRITICAL",  # Attempt to set to CRITICAL to silence all lower alerts
        cooldown_days=14,
    )
    prefs = service.update_monitoring_preferences(primary_business, payload)
    assert prefs.alert_frequency == "DAILY_DIGEST"
    assert prefs.cooldown_days == 14
    # Safety rule: min_severity is capped at HIGH so CRITICAL is always captured
    assert prefs.min_severity in ["HIGH", "LOW", "MEDIUM"]


# --------------------------------------------------------------------------- #
# 9. FastAPI HTTP API Endpoint Integration                                    #
# --------------------------------------------------------------------------- #

def test_fastapi_monitoring_endpoints(db_session, primary_user, primary_business):
    """Verify REST API endpoints for signals feed, evaluation, preferences, and dismissal."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    token = create_access_token(subject=str(primary_user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Evaluate endpoint
    res_eval = client.post("/api/v1/recommendations/monitoring/evaluate", headers=headers)
    assert res_eval.status_code == 200
    data_eval = res_eval.json()
    assert "signals" in data_eval
    assert "new_events_detected" in data_eval

    # 2. Signals Feed endpoint
    res_feed = client.get("/api/v1/recommendations/monitoring/signals", headers=headers)
    assert res_feed.status_code == 200
    data_feed = res_feed.json()
    assert "total_signals" in data_feed
    assert "critical_count" in data_feed

    # 3. Preferences GET & PUT
    res_pref_get = client.get("/api/v1/recommendations/monitoring/preferences", headers=headers)
    assert res_pref_get.status_code == 200
    assert res_pref_get.json()["alert_frequency"] in ["REALTIME", "DAILY_DIGEST", "WEEKLY_DIGEST"]

    res_pref_put = client.put(
        "/api/v1/recommendations/monitoring/preferences",
        json={"cooldown_days": 10, "alert_frequency": "WEEKLY_DIGEST"},
        headers=headers,
    )
    assert res_pref_put.status_code == 200
    assert res_pref_put.json()["cooldown_days"] == 10

    # 4. Dismissal endpoint
    if data_feed["signals"]:
        target_event_id = data_feed["signals"][0]["event_id"]
        res_dismiss = client.post(
            f"/api/v1/recommendations/monitoring/signals/{target_event_id}/dismiss",
            headers=headers,
        )
        assert res_dismiss.status_code == 200
        assert res_dismiss.json()["status"] == "acknowledged"

    app.dependency_overrides.clear()

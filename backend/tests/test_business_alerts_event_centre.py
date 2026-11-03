"""Comprehensive Test Suite for Business Alerts / Event Centre (Prompt 6.22).

Covers all 20 required verification scenarios:
  1. Statistical 2-sigma revenue drop anomaly (with >= 6 weekly buckets)
  2. Statistical minimum-history boundary condition (< 6 buckets falls back with disclosure)
  3. Zero-variance handling (sigma = 0 handled gracefully without divide-by-zero)
  4. Key customer inactivity calculation (> normal_cycle + 30 days)
  5. Key customer purchase-cycle minimum history (< 3 purchases does not trigger inactivity)
  6. Product velocity deceleration (>= 30% decline with baseline >= 5 units)
  7. Failed CSV upload detection via SalesUpload
  8. Stale forecast detection (and no alert if no forecast exists)
  9. Empty ledger data behavior (SALES_DATA_MISSING assumption disclosure; no false trend alerts)
  10. event_nature persistence across all four classifications (CONFIRMED_EVENT, WARNING, ESTIMATE, ASSUMPTION)
  11. Deterministic fingerprinting and duplicate suppression
  12. Escalation bypass when conditions worsen by >= 15%
  13. State machine status transitions (NEW -> ACKNOWLEDGED -> RESOLVED)
  14. Invalid status transitions rejected (e.g. RESOLVED -> NEW returns 400)
  15. Immutable status audit history logging in business_signal_event_audits
  16. Multi-tenant isolation: User A cannot read, acknowledge, or dismiss User B's alerts (returns 404)
  17. Unauthenticated access returns 401
  18. Non-mutating AI explanations (underlying event severity and evidence remain unchanged)
  19. Deterministic explanation fallback when AI is unavailable or fails
  20. Alert summary counters (AlertSummaryResponse) and paginated listing with query filters
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.main import app
from app.models.business import Business
from app.models.business_monitoring import (
    BusinessSignalEvent,
    BusinessSignalEventAudit,
)
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.business_monitoring import (
    AlertExplainResponse,
    AlertSummaryResponse,
    BusinessSignalItem,
    EventNature,
    EventSeverity,
    MonitoringEvaluationResponse,
    MonitoringEventType,
)
from app.schemas.recommendation_context import (
    DemandForecastContext,
    ProductForecastItemContext,
)
from app.services.business_alerts_service import (
    ALLOWED_TRANSITIONS,
    BusinessAlertsService,
)
from app.services.recommendations.change_detection_engine import ChangeDetectionEngine
from app.services.recommendations.context_service import (
    RecommendationContextService,
    UnifiedRecommendationContext,
)
from app.services.recommendations.proactive_monitoring_service import (
    ProactiveMonitoringService,
)
from app.utils.database import Base, get_db
from app.utils.security import create_access_token


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with StaticPool."""
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
def user_a(db_session):
    user = User(
        email="owner_a@acme.com",
        password_hash="hashed_pw_123",
        full_name="Alice Owner",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    user = User(
        email="owner_b@competitor.com",
        password_hash="hashed_pw_456",
        full_name="Bob Competitor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def biz_a(db_session, user_a):
    biz = Business(
        owner_id=user_a.id,
        legal_name="Acme Precision Tools Pvt Ltd",
        trade_name="Acme Tools",
        industry="Manufacturing",
        annual_revenue=12000000.0,
        employee_count=18,
        established_year=2019,
        city="Bengaluru",
        state_region="Karnataka",
        country="India",
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    user_a.active_business_id = biz.id
    db_session.commit()
    return biz


@pytest.fixture
def biz_b(db_session, user_b):
    biz = Business(
        owner_id=user_b.id,
        legal_name="Bob Enterprises Pvt Ltd",
        trade_name="Bob Retail",
        industry="Retail",
        annual_revenue=5000000.0,
        employee_count=8,
        established_year=2021,
        city="Mysuru",
        state_region="Karnataka",
        country="India",
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    user_b.active_business_id = biz.id
    db_session.commit()
    return biz


@pytest.fixture
def client_a(db_session, user_a):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    token = create_access_token(subject=str(user_a.id))
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(db_session, user_b):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    token = create_access_token(subject=str(user_b.id))
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Helper to populate test sales upload                                        #
# --------------------------------------------------------------------------- #

def _create_sales_upload(db_session, business_id: int, status: str = "processed") -> SalesUpload:
    upload = SalesUpload(
        business_id=business_id,
        filename="sales_history.csv",
        file_format="csv",
        file_size_bytes=10240,
        row_count=100,
        valid_row_count=100,
        invalid_row_count=0,
        status=status,
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    return upload


# =========================================================================== #
# 1. Statistical 2-Sigma Revenue Drop Anomaly (>= 6 weekly buckets)            #
# =========================================================================== #

def test_statistical_2sigma_revenue_drop_anomaly(db_session, biz_a):
    """Verify statistical 2-sigma revenue drop anomaly detection when >= 6 weeks history exists."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # 7 historical weeks between 30d and 85d ago with mean ~ 100,000, std dev ~ 4,000
    weekly_revenues = [95000.0, 105000.0, 98000.0, 102000.0, 96000.0, 104000.0, 100000.0]
    for i, rev in enumerate(weekly_revenues):
        # 35, 42, 49, 56, 63, 70, 77 days ago
        tx_date = now - timedelta(days=35 + (i * 7))
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=biz_a.id,
                transaction_date=tx_date,
                customer_name="Southern Defense Corp",
                product_name="Standard SKU",
                quantity=10,
                unit_price=rev / 10.0,
                total_amount=rev,
            )
        )

    # Current period (recent 30d) has a severe drop: only 1 small transaction of 20,000
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=5),
            customer_name="Southern Defense Corp",
            product_name="Standard SKU",
            quantity=2,
            unit_price=10000.0,
            total_amount=20000.0,
        )
    )
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    stat_events = [e for e in events if e.get("event_type") == "STATISTICAL_REVENUE_DROP"]
    assert len(stat_events) == 1, f"Expected 1 STATISTICAL_REVENUE_DROP, got {len(stat_events)}"
    event = stat_events[0]

    assert event["event_nature"] == "ESTIMATE"
    assert event["severity"] == "CRITICAL"
    assert "statistical revenue anomaly" in event["title"].lower()
    assert event["evidence"]["historical_bucket_count"] >= 6
    assert event["evidence"]["recent_weekly_equivalent"] < event["evidence"]["two_sigma_threshold"]


# =========================================================================== #
# 2. Statistical Minimum-History Boundary Condition (< 6 buckets fallback)    #
# =========================================================================== #

def test_statistical_minimum_history_fallback(db_session, biz_a):
    """Verify that with < 6 weekly buckets, detection falls back to period-over-period with disclosure."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # Only 3 transactions across 2 weekly buckets (< 6 required for 2-sigma sample statistics)
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=40),
            customer_name="Southern Defense Corp",
            product_name="Item A",
            quantity=5,
            unit_price=10000.0,
            total_amount=50000.0,
        )
    )
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=35),
            customer_name="Southern Defense Corp",
            product_name="Item A",
            quantity=5,
            unit_price=10000.0,
            total_amount=50000.0,
        )
    )
    # Severe drop in recent 30d
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=5),
            customer_name="Southern Defense Corp",
            product_name="Item A",
            quantity=1,
            unit_price=10000.0,
            total_amount=10000.0,
        )
    )
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    # Must NOT claim STATISTICAL_REVENUE_DROP when n < 6; falls back to REVENUE_DECLINE_DETECTED
    stat_events = [e for e in events if e.get("event_type") == "STATISTICAL_REVENUE_DROP"]
    assert len(stat_events) == 0, "Should not emit STATISTICAL_REVENUE_DROP with < 6 observation weeks"

    delta_events = [e for e in events if e.get("event_type") == "REVENUE_DECLINE_DETECTED"]
    assert len(delta_events) == 1
    assert delta_events[0]["event_nature"] == "WARNING"
    assert delta_events[0]["evidence"]["change_pct"] <= -15.0


# =========================================================================== #
# 3. Zero-Variance Handling (sigma = 0)                                       #
# =========================================================================== #

def test_zero_variance_handling(db_session, biz_a):
    """Verify zero variance (sigma = 0.0) is handled safely without division by zero or false crash."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # 6 identical weeks of exactly 50,000 -> sample std dev = 0.0
    for i in range(6):
        tx_date = now - timedelta(days=7 * (i + 1) + 1)
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=biz_a.id,
                transaction_date=tx_date,
                customer_name="Client A",
                product_name="Fixed Fee",
                quantity=1,
                unit_price=50000.0,
                total_amount=50000.0,
            )
        )
    # Current week is also 50,000
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=2),
            customer_name="Client A",
            product_name="Fixed Fee",
            quantity=1,
            unit_price=50000.0,
            total_amount=50000.0,
        )
    )
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    # Zero variance with stable revenue should NOT trigger any false revenue anomaly
    stat_events = [e for e in events if e.get("event_type") == "STATISTICAL_REVENUE_DROP"]
    assert len(stat_events) == 0


# =========================================================================== #
# 4. Key Customer Inactivity Calculation (> normal_cycle + 30 days)          #
# =========================================================================== #

def test_key_customer_inactivity_detected(db_session, biz_a):
    """Verify key customer inactivity triggers when days_since_last_order > normal_cycle + 30."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # 4 historical purchases spaced 10 days apart (normal cycle = 10 days)
    # Dates: 75d ago, 65d ago, 55d ago, 45d ago.
    dates = [
        now - timedelta(days=75),
        now - timedelta(days=65),
        now - timedelta(days=55),
        now - timedelta(days=45),  # Last order was 45 days ago
    ]
    for d in dates:
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=biz_a.id,
                transaction_date=d,
                customer_id="cust_vip_1",
                customer_name="Key Partner Ltd",
                product_name="Core Machinery",
                quantity=1,
                unit_price=50000.0,
                total_amount=50000.0,
            )
        )
    db_session.commit()

    # normal_cycle = (75 - 45) / 3 = 10 days.
    # days_since_last_order = 45 days.
    # inactivity_threshold = normal_cycle + 30 = 40 days.
    # 45 > 40 -> Inactivity detected!

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    inactivity_events = [e for e in events if e.get("event_type") == "CUSTOMER_INACTIVITY_DETECTED"]
    assert len(inactivity_events) == 1
    event = inactivity_events[0]
    assert event["event_nature"] == "CONFIRMED_EVENT"
    assert event["severity"] in ["HIGH", "CRITICAL"]
    assert event["evidence"]["customer_name"] == "Key Partner Ltd"
    assert event["evidence"]["normal_cycle_days"] == 10
    assert event["evidence"]["days_since_last_order"] >= 45
    assert event["evidence"]["inactivity_threshold_days"] == 40


# =========================================================================== #
# 5. Key Customer Purchase-Cycle Minimum History (< 3 txs does not trigger)   #
# =========================================================================== #

def test_key_customer_inactivity_minimum_history(db_session, biz_a):
    """Verify customer with < 3 purchases does NOT trigger inactivity (cannot estimate normal cycle)."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # Customer only has 2 purchases
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=60),
            customer_id="cust_sparse",
            customer_name="Sparse Buyer",
            product_name="Parts",
            quantity=1,
            unit_price=100000.0,
            total_amount=100000.0,
        )
    )
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=45),
            customer_id="cust_sparse",
            customer_name="Sparse Buyer",
            product_name="Parts",
            quantity=1,
            unit_price=100000.0,
            total_amount=100000.0,
        )
    )
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    inactivity_events = [e for e in events if e.get("event_type") == "CUSTOMER_INACTIVITY_DETECTED"]
    assert len(inactivity_events) == 0, "Should not infer purchase cycle or inactivity from < 3 purchases"


# =========================================================================== #
# 6. Product Velocity Deceleration (>= 30% decline with baseline >= 5 units)  #
# =========================================================================== #

def test_product_velocity_deceleration(db_session, biz_a):
    """Verify product velocity deceleration detects >= 30% unit volume decline with baseline >= 5."""
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # Prior 30-day window (days 31-60): 20 units sold
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=40),
            customer_name="Southern Defense Corp",
            product_name="Popular Valve",
            quantity=20,
            unit_price=1000.0,
            total_amount=20000.0,
        )
    )

    # Recent 30-day window (days 1-30): only 5 units sold (75% velocity drop)
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=10),
            customer_name="Southern Defense Corp",
            product_name="Popular Valve",
            quantity=5,
            unit_price=1000.0,
            total_amount=5000.0,
        )
    )
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a, now=now)

    velo_events = [e for e in events if e.get("event_type") == "PRODUCT_VELOCITY_DECELERATION"]
    assert len(velo_events) == 1
    event = velo_events[0]
    assert event["event_nature"] == "CONFIRMED_EVENT"
    assert event["severity"] == "HIGH"
    assert event["evidence"]["product_name"] == "Popular Valve"
    assert event["evidence"]["prior_30d_units"] == 20.0
    assert event["evidence"]["recent_30d_units"] == 5.0
    assert event["evidence"]["velocity_delta_pct"] == -75.0
    assert "warehouse inventory balances" in event["evidence"]["inventory_disclosure"].lower()


# =========================================================================== #
# 7. Failed CSV Upload Detection via SalesUpload                              #
# =========================================================================== #

def test_failed_csv_upload_detected(db_session, biz_a):
    """Verify failed sales data upload is flagged as a confirmed event."""
    upload_failed = SalesUpload(
        business_id=biz_a.id,
        filename="corrupted_october_sales.csv",
        file_format="csv",
        file_size_bytes=5120,
        row_count=50,
        valid_row_count=0,
        invalid_row_count=50,
        status="failed",
        error_message="Invalid column format: missing 'total_amount'",
    )
    db_session.add(upload_failed)
    db_session.commit()

    engine = ChangeDetectionEngine(db_session)
    now = datetime.now(timezone.utc)
    events = engine.detect_changes(biz_a, now=now)

    failed_events = [e for e in events if e.get("event_type") == "CSV_UPLOAD_FAILED"]
    assert len(failed_events) == 1
    event = failed_events[0]
    assert event["event_nature"] == "CONFIRMED_EVENT"
    assert event["severity"] == "HIGH"
    assert "corrupted_october_sales.csv" in event["title"]
    assert event["evidence"]["filename"] == "corrupted_october_sales.csv"
    assert "missing 'total_amount'" in event["evidence"]["error_message"]


# =========================================================================== #
# 8. Stale Forecast Detection                                                 #
# =========================================================================== #

def test_stale_forecast_detection(db_session, biz_a):
    """Verify stale forecast detection when sales transaction records are > 30 days old."""
    now = datetime.now(timezone.utc)
    engine = ChangeDetectionEngine(db_session)

    # 1. When no forecast data exists, no false alert is emitted
    ctx_service = RecommendationContextService(db_session)
    ctx_empty = ctx_service.build_context(biz_a)
    events_empty = engine._analyze_demand_forecast(biz_a, ctx_empty, now)
    assert len(events_empty) == 0

    # 2. When forecast exists but transactions are 45 days old (> 30 days threshold)
    ctx_mock = ctx_service.build_context(biz_a)
    ctx_mock.sales.has_sales_data = True
    ctx_mock.sales.latest_transaction_date = (now - timedelta(days=45)).isoformat()
    ctx_mock.forecast.has_forecast_data = True
    ctx_mock.forecast.product_forecasts = [
        ProductForecastItemContext(
            product_name="Legacy Pump",
            demand_trend="Stable",
            forecasted_units_total=100.0,
            forecast_horizon_periods=3,
            selected_model="linear_regression",
            reliability="HIGH",
        )
    ]

    events_stale = engine._analyze_demand_forecast(biz_a, ctx_mock, now)
    assert len(events_stale) == 1
    event = events_stale[0]
    assert event["event_type"] == "STALE_FORECAST"
    assert event["event_nature"] == "WARNING"
    assert event["evidence"]["forecast_age_days"] == 45


# =========================================================================== #
# 9. Empty Ledger Data Behavior (SALES_DATA_MISSING Assumption Disclosure)     #
# =========================================================================== #

def test_empty_ledger_data_guard(db_session, biz_a):
    """Verify empty business ledger generates SALES_DATA_MISSING disclosure and zero false trends."""
    engine = ChangeDetectionEngine(db_session)
    events = engine.detect_changes(biz_a)

    # Must contain SALES_DATA_MISSING disclosure
    empty_events = [e for e in events if e.get("event_type") == "SALES_DATA_MISSING"]
    assert len(empty_events) == 1
    event = empty_events[0]
    assert event["event_nature"] == "ASSUMPTION"
    assert event["severity"] == "INFORMATIONAL"
    assert "Sales Ledger Required" in event["title"]

    # Crucially: NO false trend alerts
    assert not any(e.get("event_type") == "REVENUE_DECLINE_DETECTED" for e in events)
    assert not any(e.get("event_type") == "CUSTOMER_INACTIVITY_DETECTED" for e in events)
    assert not any(e.get("event_type") == "PRODUCT_VELOCITY_DECELERATION" for e in events)


# =========================================================================== #
# 10. event_nature Persistence Across All 4 Classifications                   #
# =========================================================================== #

def test_event_nature_persistence_and_filtering(client_a, db_session, biz_a):
    """Verify event_nature persistence and filtering for CONFIRMED_EVENT, WARNING, ESTIMATE, ASSUMPTION."""
    now = datetime.now(timezone.utc)
    natures = ["CONFIRMED_EVENT", "WARNING", "ESTIMATE", "ASSUMPTION"]

    for i, nat in enumerate(natures):
        db_session.add(
            BusinessSignalEvent(
                event_id=f"evt_nature_{i}",
                business_id=biz_a.id,
                event_type="TEST_EVENT",
                event_nature=nat,
                source="test_source",
                severity="MEDIUM",
                data_period="30d",
                fingerprint=f"fp_nature_{i}",
                title=f"Test {nat}",
                what_changed=f"Nature test {nat}",
                why_it_matters="Verification",
                suggested_action="Review",
                detected_at=now - timedelta(minutes=i),
            )
        )
    db_session.commit()

    # Query without filter -> returns all 4
    resp = client_a.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4

    # Query filtered by ESTIMATE
    resp_est = client_a.get("/api/v1/alerts?event_nature=ESTIMATE")
    assert resp_est.status_code == 200
    est_data = resp_est.json()
    assert est_data["total"] == 1
    assert est_data["alerts"][0]["event_nature"] == "ESTIMATE"

    # Query filtered by CONFIRMED_EVENT
    resp_conf = client_a.get("/api/v1/alerts?event_nature=CONFIRMED_EVENT")
    assert resp_conf.status_code == 200
    conf_data = resp_conf.json()
    assert conf_data["total"] == 1
    assert conf_data["alerts"][0]["event_nature"] == "CONFIRMED_EVENT"


# =========================================================================== #
# 11. Deterministic Fingerprinting and Duplicate Suppression                  #
# =========================================================================== #

def test_deterministic_fingerprint_and_suppression(db_session, biz_a):
    """Verify repeated scans within cooldown suppress duplicate alerts using deterministic fingerprint."""
    service = ProactiveMonitoringService(db_session)
    upload = _create_sales_upload(db_session, biz_a.id)
    now = datetime.now(timezone.utc)

    # 3 transactions: prior 30d has 2 txs (₹20,000), recent 30d has 1 tx (₹5,000) -> 75% drop
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=45),
            customer_name="Client X",
            product_name="Widget",
            quantity=10,
            unit_price=1000.0,
            total_amount=10000.0,
        )
    )
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=40),
            customer_name="Client X",
            product_name="Widget",
            quantity=10,
            unit_price=1000.0,
            total_amount=10000.0,
        )
    )
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=biz_a.id,
            transaction_date=now - timedelta(days=5),
            customer_name="Client X",
            product_name="Widget",
            quantity=5,
            unit_price=1000.0,
            total_amount=5000.0,
        )
    )
    db_session.commit()

    # Scan 1: creates events
    eval1 = service.evaluate_business_changes(biz_a, now=now)
    assert eval1.new_events_detected > 0

    # Scan 2 immediately: duplicate events suppressed under cooldown
    eval2 = service.evaluate_business_changes(biz_a, now=now)
    assert eval2.suppressed_events >= 1


# =========================================================================== #
# 12. Escalation Bypass When Conditions Worsen (>= 15%)                       #
# =========================================================================== #

def test_escalation_bypass_when_worsening(db_session, biz_a):
    """Verify escalation bypasses cooldown when metric worsens by >= 15%."""
    now = datetime.now(timezone.utc)
    service = ProactiveMonitoringService(db_session)
    prefs = service.monitoring_repo.get_or_create_preferences(biz_a.id)

    # Initial event: 20% decline
    event_initial = BusinessSignalEvent(
        event_id="evt_initial_decline",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="sales_monitoring",
        severity="MEDIUM",
        data_period="30d",
        fingerprint=service.suppression_engine.compute_fingerprint(biz_a.id, "REVENUE_DECLINE_DETECTED"),
        title="Revenue Decline Detected",
        what_changed="Down 20%",
        why_it_matters="Solvency",
        suggested_action="Review pipeline",
        detected_at=now - timedelta(days=2),
        evidence={"change_pct": -20.0},
    )
    db_session.add(event_initial)
    db_session.commit()

    # Incoming candidate: worsened from -20% to -40% (20% material worsening >= 15% threshold)
    candidate_dict = {
        "event_type": "REVENUE_DECLINE_DETECTED",
        "event_nature": "WARNING",
        "source": "sales_monitoring",
        "severity": "CRITICAL",
        "data_period": "30d",
        "title": "Severe Revenue Drop",
        "what_changed": "Down 40%",
        "why_it_matters": "Solvency",
        "suggested_action": "Emergency cashflow review",
        "evidence": {"change_pct": -40.0},
    }

    result = service.suppression_engine.evaluate_event_suppression(
        business_id=biz_a.id,
        event_dict=candidate_dict,
        prefs=prefs,
    )
    assert result["is_suppressed"] is False
    assert result["escalation_level"] >= 1
    assert "[ESCALATED]" in result["title"]


# =========================================================================== #
# 13. State Machine Status Transitions (NEW -> ACKNOWLEDGED -> RESOLVED)      #
# =========================================================================== #

def test_state_machine_valid_transitions(client_a, db_session, biz_a):
    """Verify valid state transitions: NEW -> ACKNOWLEDGED -> RESOLVED."""
    now = datetime.now(timezone.utc)
    alert = BusinessSignalEvent(
        event_id="evt_lifecycle_1",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="test",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_life_1",
        title="Revenue Drop",
        what_changed="Down 15%",
        why_it_matters="Cashflow",
        suggested_action="Review",
        status="NEW",
        detected_at=now,
    )
    db_session.add(alert)
    db_session.commit()

    # 1. NEW -> ACKNOWLEDGED
    resp_ack = client_a.patch(
        f"/api/v1/alerts/{alert.event_id}/status",
        json={"status": "ACKNOWLEDGED", "reason": "Owner acknowledged alert"},
    )
    assert resp_ack.status_code == 200, resp_ack.text
    data_ack = resp_ack.json()
    assert data_ack["status"] == "ACKNOWLEDGED"

    # 2. ACKNOWLEDGED -> RESOLVED
    resp_res = client_a.patch(
        f"/api/v1/alerts/{alert.event_id}/status",
        json={"status": "RESOLVED", "reason": "Issue corrected with supplier"},
    )
    assert resp_res.status_code == 200, resp_res.text
    data_res = resp_res.json()
    assert data_res["status"] == "RESOLVED"
    assert data_res["resolved_at"] is not None


# =========================================================================== #
# 14. Invalid Status Transitions Rejected (e.g. RESOLVED -> NEW returns 400)  #
# =========================================================================== #

def test_invalid_status_transitions_rejected(client_a, db_session, biz_a):
    """Verify invalid state transitions are rejected with HTTP 400."""
    now = datetime.now(timezone.utc)
    alert = BusinessSignalEvent(
        event_id="evt_lifecycle_terminal",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="test",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_life_term",
        title="Terminal Alert",
        what_changed="Test",
        why_it_matters="Test",
        suggested_action="Test",
        status="RESOLVED",
        detected_at=now,
    )
    db_session.add(alert)
    db_session.commit()

    # Attempt to transition terminal RESOLVED to ACKNOWLEDGED -> Must fail with 400
    resp_invalid = client_a.patch(
        f"/api/v1/alerts/{alert.event_id}/status",
        json={"status": "ACKNOWLEDGED", "reason": "Attempting illegal transition from terminal state"},
    )
    assert resp_invalid.status_code == 400
    assert "Invalid status transition" in resp_invalid.json()["detail"]


# =========================================================================== #
# 15. Immutable Status Audit History Logging                                  #
# =========================================================================== #

def test_immutable_audit_history_logging(client_a, db_session, biz_a, user_a):
    """Verify status updates append immutable records into business_signal_event_audits."""
    now = datetime.now(timezone.utc)
    alert = BusinessSignalEvent(
        event_id="evt_audit_test",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="test",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_audit_1",
        title="Audit Test Alert",
        what_changed="Test",
        why_it_matters="Test",
        suggested_action="Test",
        status="NEW",
        detected_at=now,
    )
    db_session.add(alert)
    db_session.commit()

    # Transition 1: NEW -> ACKNOWLEDGED
    client_a.patch(
        f"/api/v1/alerts/{alert.event_id}/status",
        json={"status": "ACKNOWLEDGED", "reason": "Under active investigation"},
    )
    # Transition 2: ACKNOWLEDGED -> DISMISSED
    client_a.patch(
        f"/api/v1/alerts/{alert.event_id}/status",
        json={"status": "DISMISSED", "reason": "Expected seasonal dip"},
    )

    # Fetch audit history
    resp_hist = client_a.get(f"/api/v1/alerts/{alert.event_id}/history")
    assert resp_hist.status_code == 200
    history = resp_hist.json()
    assert len(history) == 2

    # Verify transition details
    assert history[0]["previous_status"] == "ACKNOWLEDGED"
    assert history[0]["new_status"] == "DISMISSED"
    assert history[0]["reason"] == "Expected seasonal dip"
    assert history[0]["changed_by_user_id"] == user_a.id

    assert history[1]["previous_status"] == "NEW"
    assert history[1]["new_status"] == "ACKNOWLEDGED"
    assert history[1]["reason"] == "Under active investigation"


# =========================================================================== #
# 16. Multi-Tenant Isolation (User B cannot access User A's alerts)           #
# =========================================================================== #

def test_multi_tenant_isolation(client_a, client_b, db_session, biz_a, biz_b):
    """Verify strict tenant isolation: cross-tenant access returns 404."""
    now = datetime.now(timezone.utc)
    alert_a = BusinessSignalEvent(
        event_id="evt_tenant_a_secret",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="sales",
        severity="CRITICAL",
        data_period="30d",
        fingerprint="fp_tenant_a",
        title="Biz A Confidential Alert",
        what_changed="Private data",
        why_it_matters="Strictly private",
        suggested_action="Keep safe",
        status="NEW",
        detected_at=now,
    )
    db_session.add(alert_a)
    db_session.commit()

    # User B tries to view Alert A -> 404 Not Found
    resp_view = client_b.get(f"/api/v1/alerts/{alert_a.event_id}")
    assert resp_view.status_code == 404

    # User B tries to update Alert A status -> 404 Not Found
    resp_patch = client_b.patch(
        f"/api/v1/alerts/{alert_a.event_id}/status",
        json={"status": "ACKNOWLEDGED"},
    )
    assert resp_patch.status_code == 404

    # User B tries to view Alert A audit history -> 404 Not Found
    resp_hist = client_b.get(f"/api/v1/alerts/{alert_a.event_id}/history")
    assert resp_hist.status_code == 404

    # User B lists alerts -> Biz A alert does NOT appear
    resp_list = client_b.get("/api/v1/alerts")
    assert resp_list.status_code == 200
    assert not any(a["event_id"] == alert_a.event_id for a in resp_list.json()["alerts"])


# =========================================================================== #
# 17. Unauthenticated Access Returns 401                                      #
# =========================================================================== #

def test_unauthenticated_access_returns_401(db_session):
    """Verify all /alerts endpoints require valid authentication."""
    app.dependency_overrides[get_db] = lambda: db_session
    raw_client = TestClient(app)

    assert raw_client.get("/api/v1/alerts").status_code == 401
    assert raw_client.get("/api/v1/alerts/summary").status_code == 401
    assert raw_client.post("/api/v1/alerts/evaluate").status_code == 401
    assert raw_client.get("/api/v1/alerts/evt_test").status_code == 401
    assert raw_client.patch("/api/v1/alerts/evt_test/status", json={"status": "ACKNOWLEDGED"}).status_code == 401
    assert raw_client.get("/api/v1/alerts/evt_test/history").status_code == 401
    assert raw_client.post("/api/v1/alerts/evt_test/explain", json={"language": "en"}).status_code == 401
    app.dependency_overrides.clear()


# =========================================================================== #
# 18. Non-Mutating AI Explanations                                            #
# =========================================================================== #

def test_non_mutating_ai_explanation(client_a, db_session, biz_a):
    """Verify AI explanation generation does not alter the underlying alert evidence."""
    now = datetime.now(timezone.utc)
    original_evidence = {"historical_drop": -25.5, "benchmark": 100000.0}
    alert = BusinessSignalEvent(
        event_id="evt_explain_immutability",
        business_id=biz_a.id,
        event_type="REVENUE_DECLINE_DETECTED",
        event_nature="WARNING",
        source="sales",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_explain_1",
        title="Revenue Decline 25%",
        what_changed="Down 25%",
        why_it_matters="Working capital risk",
        suggested_action="Review top customer orders",
        status="NEW",
        evidence=original_evidence,
        detected_at=now,
    )
    db_session.add(alert)
    db_session.commit()

    # Call explain endpoint
    resp = client_a.post(
        f"/api/v1/alerts/{alert.event_id}/explain",
        json={"language": "en"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == alert.event_id
    assert len(data["explanation"]) > 20
    assert data["language"] == "en"

    # Refresh alert from database and verify underlying fields remain pristine
    db_session.refresh(alert)
    assert alert.title == "Revenue Decline 25%"
    assert alert.severity == "HIGH"
    assert alert.event_nature == "WARNING"
    assert alert.status == "NEW"
    assert alert.evidence == original_evidence


# =========================================================================== #
# 19. Deterministic Explanation Fallback When AI Is Unavailable               #
# =========================================================================== #

def test_deterministic_explanation_fallback(db_session, biz_a):
    """Verify explain_alert gracefully falls back to deterministic text when Gemini raises error."""
    mock_gemini = MagicMock()
    mock_gemini.execute_chat_completion.side_effect = RuntimeError("Gemini API connection timeout")
    mock_gemini.generate.side_effect = RuntimeError("Gemini API connection timeout")

    service = BusinessAlertsService(db_session, gemini_client=mock_gemini)
    now = datetime.now(timezone.utc)
    alert = BusinessSignalEvent(
        event_id="evt_fallback_test",
        business_id=biz_a.id,
        event_type="PRODUCT_VELOCITY_DECELERATION",
        event_nature="CONFIRMED_EVENT",
        source="sales",
        severity="HIGH",
        data_period="30d",
        fingerprint="fp_fallback_1",
        title="Product Velocity Deceleration",
        what_changed="Volume down 40%",
        why_it_matters="Dead stock accumulation",
        suggested_action="Discount excess stock",
        status="NEW",
        evidence={"velocity_drop_percent": 40.0},
        detected_at=now,
    )
    db_session.add(alert)
    db_session.commit()

    # English fallback
    res_en = service.explain_alert(biz_a.id, alert.event_id, language="en")
    assert res_en.is_fallback is True
    assert res_en.provider_used == "deterministic_fallback"
    assert "Alert Summary" in res_en.explanation or "Observation" in res_en.explanation
    assert "Volume down 40%" in res_en.explanation

    # Kannada fallback
    res_kn = service.explain_alert(biz_a.id, alert.event_id, language="kn")
    assert res_kn.is_fallback is True
    assert res_kn.provider_used == "deterministic_fallback"
    assert "ವಿವರಣೆ" in res_kn.explanation


# =========================================================================== #
# 20. Alert Summary Counters and Paginated Listing with Query Filters         #
# =========================================================================== #

def test_alert_summary_counters_and_pagination(client_a, db_session, biz_a):
    """Verify aggregated dashboard counters and paginated listing with query filters."""
    now = datetime.now(timezone.utc)

    # Ingest 5 diverse alerts
    test_alerts = [
        ("evt_sum_1", "CRITICAL", "NEW", "ESTIMATE"),
        ("evt_sum_2", "CRITICAL", "ACKNOWLEDGED", "CONFIRMED_EVENT"),
        ("evt_sum_3", "HIGH", "RESOLVED", "WARNING"),
        ("evt_sum_4", "MEDIUM", "DISMISSED", "CONFIRMED_EVENT"),
        ("evt_sum_5", "LOW", "NEW", "ASSUMPTION"),
    ]
    for eid, sev, stat, nat in test_alerts:
        db_session.add(
            BusinessSignalEvent(
                event_id=eid,
                business_id=biz_a.id,
                event_type="TEST_METRIC",
                event_nature=nat,
                source="test",
                severity=sev,
                data_period="30d",
                fingerprint=f"fp_{eid}",
                title=f"Alert {eid}",
                what_changed="Change",
                why_it_matters="Matters",
                suggested_action="Action",
                status=stat,
                detected_at=now,
            )
        )
    db_session.commit()

    # 1. Summary counters
    resp_sum = client_a.get("/api/v1/alerts/summary")
    assert resp_sum.status_code == 200
    summary = resp_sum.json()
    assert summary["total_alerts"] == 5
    assert summary["critical_count"] == 2
    assert summary["high_count"] == 1
    assert summary["medium_count"] == 1
    assert summary["low_and_info_count"] == 1
    assert summary["new_count"] == 2
    assert summary["acknowledged_count"] == 1
    assert summary["resolved_count"] == 1
    assert summary["dismissed_count"] == 1
    assert summary["confirmed_events_count"] == 2
    assert summary["warnings_count"] == 1
    assert summary["estimates_count"] == 1
    assert summary["assumptions_count"] == 1

    # 2. Pagination (limit=2, offset=0)
    resp_page1 = client_a.get("/api/v1/alerts?limit=2&offset=0")
    assert resp_page1.status_code == 200
    data_page1 = resp_page1.json()
    assert data_page1["total"] == 5
    assert len(data_page1["alerts"]) == 2

    # 3. Pagination offset (limit=2, offset=2)
    resp_page2 = client_a.get("/api/v1/alerts?limit=2&offset=2")
    assert resp_page2.status_code == 200
    data_page2 = resp_page2.json()
    assert len(data_page2["alerts"]) == 2

    # 4. Filter by severity=CRITICAL
    resp_crit = client_a.get("/api/v1/alerts?severity=CRITICAL")
    assert resp_crit.status_code == 200
    assert resp_crit.json()["total"] == 2

    # 5. Filter by status=NEW
    resp_new = client_a.get("/api/v1/alerts?status=NEW")
    assert resp_new.status_code == 200
    assert resp_new.json()["total"] == 2

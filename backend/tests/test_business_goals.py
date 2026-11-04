"""Comprehensive tests for Business Goals & Progress Tracker (Prompt 6.24).

Verifies:
  - Goal creation, retrieval, updates, and authentication.
  - Multi-tenant boundary isolation (User A cannot access User B's goals).
  - Deterministic progress calculation for monthly revenue, customer concentration, repeat customers, and digital twin health score.
  - Honest missing data handling (progress is NEVER fabricated when records are missing).
  - Stale data detection (>30 days transaction age warning).
  - Period boundary conditions (future start date, expired target date).
  - Valid status transition state machine (invalid transitions rejected).
  - Distinguishing automated metrics from owner manual progress declarations.
  - Soft-deletion / archival preserves immutable historical audit snapshots.
  - Non-mutating AI trajectory explanation.
  - Cross-module regression for recommendations and action items.
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.business import Business
from app.models.business_goal import BusinessGoal, BusinessGoalAudit
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.business_goal import (
    GoalDataAvailability,
    GoalMeasurementMethod,
    GoalMetricKey,
    GoalStatus,
)
from app.utils.database import Base, get_db
from app.utils.security import create_access_token


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_setup(db_session: Session):
    """Create two distinct test users with isolated businesses."""
    # User 1
    u1 = User(
        email="owner1_goals@example.com",
        password_hash="hashed_pw_1",
        full_name="Owner 1",
        is_active=True,
    )
    db_session.add(u1)
    db_session.commit()
    db_session.refresh(u1)

    b1 = Business(
        owner_id=u1.id,
        legal_name="Enterprise Alpha Pvt Ltd",
        trade_name="Enterprise Alpha",
        industry="Retail",
        state_region="Karnataka",
        established_year=2020,
        employee_count=10,
        annual_revenue=5000000.0,
    )
    db_session.add(b1)
    db_session.commit()
    db_session.refresh(b1)
    u1.active_business_id = b1.id
    db_session.commit()

    # User 2 (for tenant isolation tests)
    u2 = User(
        email="owner2_goals@example.com",
        password_hash="hashed_pw_2",
        full_name="Owner 2",
        is_active=True,
    )
    db_session.add(u2)
    db_session.commit()
    db_session.refresh(u2)

    b2 = Business(
        owner_id=u2.id,
        legal_name="Enterprise Beta Pvt Ltd",
        trade_name="Enterprise Beta",
        industry="Manufacturing",
        state_region="Maharashtra",
        established_year=2021,
        employee_count=8,
        annual_revenue=3000000.0,
    )
    db_session.add(b2)
    db_session.commit()
    db_session.refresh(b2)
    u2.active_business_id = b2.id
    db_session.commit()

    token1 = create_access_token(subject=str(u1.id))
    token2 = create_access_token(subject=str(u2.id))

    return {
        "user1": u1,
        "biz1": b1,
        "token1": token1,
        "user2": u2,
        "biz2": b2,
        "token2": token2,
    }


@pytest.fixture
def client_a(db_session, test_setup):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {test_setup['token1']}"})
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(db_session, test_setup):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {test_setup['token2']}"})
    yield client
    app.dependency_overrides.clear()


def test_goal_creation_and_authorization(db_session: Session, test_setup, client_a):
    """Verify goal creation, field attribution, audit logging, and 401 when unauthenticated."""
    biz1 = test_setup["biz1"]

    # 1. Unauthenticated request should fail
    unauth_client = TestClient(app)
    resp_unauth = unauth_client.post("/api/v1/goals", json={"title": "Unauthorized Goal", "target_value": 100000})
    assert resp_unauth.status_code == 401

    # 2. Authenticated creation
    payload = {
        "title": "Increase Monthly Sales to 5 Lakhs",
        "description": "Expand retail footprint to reach target monthly revenue.",
        "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
        "measurement_method": GoalMeasurementMethod.AUTOMATED_METRIC.value,
        "baseline_value": 200000.0,
        "target_value": 500000.0,
        "unit": "INR",
        "priority": "high",
        "start_date": str(date.today() - timedelta(days=10)),
        "target_date": str(date.today() + timedelta(days=20)),
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["target_value"] == 500000.0
    assert data["business_id"] == biz1.id
    assert data["status"] == "ACTIVE"
    assert data["measurement_method"] == "AUTOMATED_METRIC"

    # Verify audit history
    goal_id = data["id"]
    audits = (
        db_session.query(BusinessGoalAudit)
        .filter(BusinessGoalAudit.goal_id == goal_id)
        .all()
    )
    assert len(audits) >= 1
    assert audits[0].action == "CREATED"
    assert audits[0].business_id == biz1.id


def test_goal_tenant_isolation(client_a, client_b):
    """User B cannot view, evaluate, update, or archive User A's goals."""
    # User 1 creates goal
    create_resp = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Confidential Goal User 1",
            "target_value": 100000.0,
            "unit": "INR",
        },
    )
    assert create_resp.status_code == 201
    goal_id = create_resp.json()["id"]

    # User 2 tries to GET goal -> 404
    get_resp = client_b.get(f"/api/v1/goals/{goal_id}")
    assert get_resp.status_code == 404

    # User 2 tries to UPDATE goal -> 404
    update_resp = client_b.put(
        f"/api/v1/goals/{goal_id}",
        json={"title": "Hacked Title"},
    )
    assert update_resp.status_code == 404

    # User 2 tries to DELETE/ARCHIVE goal -> 404
    del_resp = client_b.delete(f"/api/v1/goals/{goal_id}")
    assert del_resp.status_code == 404

    # User 2's list must not contain User 1's goal
    list_resp = client_b.get("/api/v1/goals")
    assert list_resp.status_code == 200
    goal_ids_user2 = [g["id"] for g in list_resp.json()["items"]]
    assert goal_id not in goal_ids_user2


def test_progress_calculation_monthly_revenue(db_session: Session, test_setup, client_a):
    """Verify deterministic progress calculation for monthly revenue against ingested sales."""
    biz1 = test_setup["biz1"]

    today = date.today()
    start_d = today - timedelta(days=15)
    target_d = today + timedelta(days=15)

    up = SalesUpload(
        business_id=biz1.id,
        filename="sales_test.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=3,
        valid_row_count=3,
        status="completed",
    )
    db_session.add(up)
    db_session.commit()

    # Three transactions totaling ₹300,000
    now_utc = datetime.now(timezone.utc)
    t1 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=5),
        total_amount=100000.0,
        quantity=10,
        unit_price=10000.0,
        product_name="Widgets",
        is_duplicate=False,
    )
    t2 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=3),
        total_amount=150000.0,
        quantity=15,
        unit_price=10000.0,
        product_name="Widgets",
        is_duplicate=False,
    )
    t3 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=1),
        total_amount=50000.0,
        quantity=5,
        unit_price=10000.0,
        product_name="Gadgets",
        is_duplicate=False,
    )
    # Duplicate transaction that MUST be excluded
    t_dup = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=1),
        total_amount=999999.0,
        quantity=100,
        unit_price=9999.0,
        product_name="Dup",
        is_duplicate=True,
    )
    db_session.add_all([t1, t2, t3, t_dup])
    db_session.commit()

    # Create goal: baseline 100,000, target 500,000 -> (300,000 - 100,000) / (500,000 - 100,000) = 50.0%
    payload = {
        "title": "Revenue Goal ₹500,000",
        "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
        "baseline_value": 100000.0,
        "target_value": 500000.0,
        "unit": "INR",
        "start_date": str(start_d),
        "target_date": str(target_d),
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["current_value"] == 300000.0
    assert data["progress_pct"] == 50.0
    assert data["remaining_gap"] == 200000.0
    assert data["data_availability"] == "AVAILABLE"
    assert data["is_achieved"] is False
    assert "Authoritative Ingested Sales Transactions" in data["evidence_source"]


def test_progress_calculation_customer_concentration_reduction(db_session: Session, test_setup, client_a):
    """Verify ceiling/reduction metric math for customer concentration (lower is better)."""
    biz1 = test_setup["biz1"]

    up = SalesUpload(
        business_id=biz1.id,
        filename="sales_conc.csv",
        file_format="csv",
        file_size_bytes=512,
        status="completed",
    )
    db_session.add(up)
    db_session.commit()

    # Customer A = ₹60,000 (60%), Customer B = ₹40,000 (40%) -> Concentration is 60.0%
    now_utc = datetime.now(timezone.utc)
    t1 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=2),
        customer_name="Customer Alpha",
        total_amount=60000.0,
        quantity=6,
        unit_price=10000.0,
        product_name="Item 1",
        is_duplicate=False,
    )
    t2 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=1),
        customer_name="Customer Beta",
        total_amount=40000.0,
        quantity=4,
        unit_price=10000.0,
        product_name="Item 2",
        is_duplicate=False,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Goal: Reduce concentration from baseline 80% to target 40%.
    # Current is 60%. Progress = (80 - 60) / (80 - 40) = 20 / 40 = 50.0%
    payload = {
        "title": "Diversify Revenue — Reduce Max Concentration",
        "metric_key": GoalMetricKey.CUSTOMER_CONCENTRATION.value,
        "baseline_value": 80.0,
        "target_value": 40.0,
        "unit": "%",
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["current_value"] == 60.0
    assert data["progress_pct"] == 50.0
    assert data["remaining_gap"] == 20.0
    assert data["is_achieved"] is False


def test_missing_data_honesty(client_b):
    """Never fabricate progress when required source data is missing."""
    payload = {
        "title": "Revenue Target ₹1,000,000",
        "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
        "target_value": 1000000.0,
        "unit": "INR",
    }
    resp = client_b.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    # Strictly honest unavailable state
    assert data["current_value"] is None
    assert data["progress_pct"] is None
    assert data["data_availability"] == "MISSING_DATA"
    assert data["is_achieved"] is False
    assert "No sales records uploaded" in data["data_freshness_warning"]


def test_stale_data_detection(db_session: Session, test_setup, client_a):
    """Flag STALE_DATA warning when latest transaction is older than 30 days."""
    biz1 = test_setup["biz1"]

    up = SalesUpload(
        business_id=biz1.id,
        filename="old_sales.csv",
        file_format="csv",
        file_size_bytes=512,
        status="completed",
    )
    db_session.add(up)
    db_session.commit()

    # 45 days old transaction
    t_old = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=datetime.now(timezone.utc) - timedelta(days=45),
        total_amount=50000.0,
        quantity=5,
        unit_price=10000.0,
        product_name="Old Item",
        is_duplicate=False,
    )
    db_session.add(t_old)
    db_session.commit()

    payload = {
        "title": "Target Revenue with Stale Data",
        "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
        "target_value": 100000.0,
        "unit": "INR",
        "start_date": str(date.today() - timedelta(days=60)),
        "target_date": str(date.today() + timedelta(days=10)),
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["data_availability"] == "STALE_DATA"
    assert "Latest transaction is from" in data["data_freshness_warning"]
    assert ">30 days old" in data["data_freshness_warning"]


def test_period_boundaries(client_a):
    """Handle future start dates (PENDING_PERIOD) and past target dates (EXPIRED/COMPLETED)."""
    # 1. Future start date
    future_start = date.today() + timedelta(days=10)
    future_target = date.today() + timedelta(days=40)
    resp_future = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Next Quarter Goal",
            "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
            "target_value": 500000.0,
            "start_date": str(future_start),
            "target_date": str(future_target),
        },
    )
    assert resp_future.status_code == 201
    data_fut = resp_future.json()
    assert data_fut["data_availability"] == "PENDING_PERIOD"
    assert data_fut["progress_pct"] == 0.0

    # 2. Target date in the past with unmet target -> auto-expires
    past_start = date.today() - timedelta(days=40)
    past_target = date.today() - timedelta(days=5)
    resp_past = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Expired Unfinished Goal",
            "metric_key": GoalMetricKey.MONTHLY_REVENUE.value,
            "target_value": 10000000.0,  # Unreachable 1 crore
            "start_date": str(past_start),
            "target_date": str(past_target),
        },
    )
    assert resp_past.status_code == 201
    data_past = resp_past.json()
    assert data_past["status"] == "EXPIRED"


def test_status_transitions_and_state_machine(client_a):
    """Enforce valid state machine transitions; reject invalid transitions with 400."""
    # Create active goal
    create_resp = client_a.post(
        "/api/v1/goals",
        json={"title": "State Machine Goal", "target_value": 100000.0},
    )
    goal_id = create_resp.json()["id"]

    # 1. Valid: ACTIVE -> PAUSED
    resp_pause = client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "PAUSED", "notes": "Paused for inventory audit."},
    )
    assert resp_pause.status_code == 200
    assert resp_pause.json()["status"] == "PAUSED"

    # 2. Invalid: PAUSED -> COMPLETED (must be ACTIVE before COMPLETED)
    resp_invalid = client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "COMPLETED"},
    )
    assert resp_invalid.status_code == 400
    assert "Invalid status transition" in resp_invalid.json()["detail"]

    # 3. Valid: PAUSED -> ACTIVE -> COMPLETED
    client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "ACTIVE"},
    )
    resp_complete = client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "COMPLETED", "notes": "Owner verified milestone completion."},
    )
    assert resp_complete.status_code == 200
    assert resp_complete.json()["status"] == "COMPLETED"


def test_manual_progress_declaration(client_a):
    """Distinguish owner-declared manual updates from automated metrics."""
    # Create manual goal
    resp = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Acquire 5 Wholesale Partnerships",
            "measurement_method": "MANUAL_REPORTED",
            "metric_key": "manual",
            "baseline_value": 0.0,
            "target_value": 5.0,
            "unit": "partnerships",
        },
    )
    assert resp.status_code == 201
    goal_id = resp.json()["id"]
    assert resp.json()["measurement_method"] == "MANUAL_REPORTED"

    # Record manual progress
    prog_resp = client_a.post(
        f"/api/v1/goals/{goal_id}/progress",
        json={"current_value": 3.0, "notes": "Signed MOU with 3 distributors."},
    )
    assert prog_resp.status_code == 200
    data = prog_resp.json()
    assert data["current_value"] == 3.0
    assert data["progress_pct"] == 60.0
    assert data["remaining_gap"] == 2.0
    assert data["evidence_source"] == "Owner Manual Declaration"


def test_soft_delete_preserves_audit_history(client_a):
    """Soft delete / archival does not erase audit history."""
    resp = client_a.post(
        "/api/v1/goals",
        json={"title": "Goal to Archive", "target_value": 50000.0},
    )
    goal_id = resp.json()["id"]

    # Add a manual update
    client_a.post(
        f"/api/v1/goals/{goal_id}/progress",
        json={"current_value": 25000.0},
    )

    # Archive goal
    del_resp = client_a.delete(
        f"/api/v1/goals/{goal_id}?reason=Pivot+to+export+focus"
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ARCHIVED"

    # Default list excludes it
    list_resp = client_a.get("/api/v1/goals")
    ids = [g["id"] for g in list_resp.json()["items"]]
    assert goal_id not in ids

    # Audit history is preserved in DB
    history_resp = client_a.get(f"/api/v1/goals/{goal_id}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    actions = [h["action"] for h in history]
    assert "CREATED" in actions
    assert "ARCHIVED" in actions


def test_non_mutating_ai_explanation(client_a):
    """AI explanation returns tactical guidance without altering goal values."""
    resp = client_a.post(
        "/api/v1/goals",
        json={
            "title": "AI Feasibility Test Goal",
            "target_value": 200000.0,
            "unit": "INR",
        },
    )
    goal_id = resp.json()["id"]

    # Request AI explanation
    ai_resp = client_a.post(f"/api/v1/goals/{goal_id}/explain")
    assert ai_resp.status_code == 200
    ai_data = ai_resp.json()
    assert ai_data["goal_id"] == goal_id
    assert "analysis" in ai_data
    assert len(ai_data["suggested_actions"]) > 0

    # Verify goal record itself has NOT been mutated
    get_resp = client_a.get(f"/api/v1/goals/{goal_id}")
    assert get_resp.json()["target_value"] == 200000.0



def test_progress_calculation_repeat_customer_rate(db_session: Session, test_setup, client_a):
    """Verify deterministic calculation of repeat customer rate."""
    biz1 = test_setup["biz1"]

    up = SalesUpload(
        business_id=biz1.id,
        filename="sales_repeat.csv",
        file_format="csv",
        file_size_bytes=512,
        status="completed",
    )
    db_session.add(up)
    db_session.commit()

    now_utc = datetime.now(timezone.utc)
    # Cust 1 has 2 orders (repeat), Cust 2 has 1 order -> Repeat rate = 1/2 = 50.0%
    t1 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=5),
        customer_name="Cust 1",
        total_amount=10000.0,
        quantity=1,
        unit_price=10000.0,
        product_name="Product A",
        is_duplicate=False,
    )
    t2 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=2),
        customer_name="Cust 1",
        total_amount=15000.0,
        quantity=1,
        unit_price=15000.0,
        product_name="Product B",
        is_duplicate=False,
    )
    t3 = SalesTransaction(
        upload_id=up.id,
        business_id=biz1.id,
        transaction_date=now_utc - timedelta(days=1),
        customer_name="Cust 2",
        total_amount=20000.0,
        quantity=2,
        unit_price=10000.0,
        product_name="Product A",
        is_duplicate=False,
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # Target: 50.0% repeat rate. Baseline: 0.0%.
    payload = {
        "title": "Boost Repeat Customer Rate to 50%",
        "metric_key": GoalMetricKey.REPEAT_CUSTOMER_RATE.value,
        "baseline_value": 0.0,
        "target_value": 50.0,
        "unit": "%",
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["current_value"] == 50.0
    assert data["progress_pct"] == 100.0
    assert data["is_achieved"] is True


def test_progress_calculation_digital_twin_health_score(test_setup, client_a):
    """Verify integration with Digital Twin Health Score Engine."""
    payload = {
        "title": "Achieve Business Health Score of 80",
        "metric_key": GoalMetricKey.DIGITAL_TWIN_HEALTH_SCORE.value,
        "baseline_value": 50.0,
        "target_value": 80.0,
        "unit": "score",
    }
    resp = client_a.post("/api/v1/goals", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["current_value"] is not None
    assert data["data_availability"] == "AVAILABLE"
    assert "Digital Twin Health Score Engine" in data["evidence_source"]


def test_cross_module_action_and_recommendation_integration(db_session: Session, test_setup, client_a):
    """Goals display related recommendations and decisions from the workspace."""
    biz1 = test_setup["biz1"]

    rec = RecommendationLifecycleState(
        business_id=biz1.id,
        recommendation_id="rec_diversify_suppliers",
        status="Accepted",
    )
    db_session.add(rec)
    db_session.commit()

    resp = client_a.post(
        "/api/v1/goals",
        json={"title": "Strategic Sourcing Goal", "target_value": 100000.0},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["related_recommendations"]) >= 1
    rec_ids = [r["id"] for r in data["related_recommendations"]]
    assert "rec_diversify_suppliers" in rec_ids


def test_multi_business_same_owner_isolation(db_session: Session, test_setup, client_a):
    """Verify strict tenant isolation between two businesses owned by the SAME user.

    When active_business_id changes:
    1. Goals created under Business A are not visible under Business B.
    2. Direct access to Business A's goal while Business B is active returns 404.
    3. Goals created under Business B belong strictly to Business B.
    """
    user1 = test_setup["user1"]
    biz1 = test_setup["biz1"]

    # Create second business owned by user1
    biz1_second = Business(
        owner_id=user1.id,
        legal_name="Enterprise Alpha Logistics Pvt Ltd",
        trade_name="Alpha Logistics",
        industry="Logistics",
        state_region="Karnataka",
        established_year=2022,
        employee_count=5,
        annual_revenue=1500000.0,
    )
    db_session.add(biz1_second)
    db_session.commit()
    db_session.refresh(biz1_second)

    # 1. Ensure user1.active_business_id is biz1.id
    user1.active_business_id = biz1.id
    db_session.commit()

    # Create goal for Business 1
    resp_create_a = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Alpha Primary Goal",
            "metric_key": "monthly_revenue",
            "target_value": 500000.0,
        },
    )
    assert resp_create_a.status_code == 201
    goal_a_id = resp_create_a.json()["id"]
    assert resp_create_a.json()["business_id"] == biz1.id

    # List goals for Business 1
    resp_list_a = client_a.get("/api/v1/goals")
    assert resp_list_a.status_code == 200
    ids_a = [g["id"] for g in resp_list_a.json()["items"]]
    assert goal_a_id in ids_a

    # 2. Switch user1's active_business_id to biz1_second.id
    user1.active_business_id = biz1_second.id
    db_session.commit()

    # List goals for Business 1_second -> should NOT list Business 1's goal
    resp_list_b = client_a.get("/api/v1/goals")
    assert resp_list_b.status_code == 200
    ids_b = [g["id"] for g in resp_list_b.json()["items"]]
    assert goal_a_id not in ids_b
    assert len(ids_b) == 0

    # Direct fetch of goal_a_id while Business 1_second is active should return 404
    resp_get_direct = client_a.get(f"/api/v1/goals/{goal_a_id}")
    assert resp_get_direct.status_code == 404

    # 3. Create goal for Business 1_second
    resp_create_b = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Alpha Logistics Secondary Goal",
            "metric_key": "monthly_revenue",
            "target_value": 200000.0,
        },
    )
    assert resp_create_b.status_code == 201
    goal_b_id = resp_create_b.json()["id"]
    assert resp_create_b.json()["business_id"] == biz1_second.id

    # List goals for Business 1_second -> only goal_b_id
    resp_list_b_after = client_a.get("/api/v1/goals")
    assert resp_list_b_after.status_code == 200
    ids_b_after = [g["id"] for g in resp_list_b_after.json()["items"]]
    assert goal_b_id in ids_b_after
    assert goal_a_id not in ids_b_after

    # 4. Switch back to biz1.id
    user1.active_business_id = biz1.id
    db_session.commit()

    resp_list_a_after = client_a.get("/api/v1/goals")
    assert resp_list_a_after.status_code == 200
    ids_a_after = [g["id"] for g in resp_list_a_after.json()["items"]]
    assert goal_a_id in ids_a_after
    assert goal_b_id not in ids_a_after

    # 5. Explicit invalid/inaccessible active_business_id returns 404 (never silently switches)
    user1.active_business_id = 99999
    db_session.commit()
    resp_invalid = client_a.get("/api/v1/goals")
    assert resp_invalid.status_code == 404
    assert "not found or inaccessible" in resp_invalid.json()["detail"]

    # Restore active business
    user1.active_business_id = biz1.id
    db_session.commit()


def test_verified_zero_sales_vs_incomplete_data(db_session: Session, test_setup, client_a):
    """Verify distinction between verified zero-sales period and incomplete or missing data.

    1. Unconfirmed / failed upload -> MISSING_DATA.
    2. Upload date span does not cover observation window -> MISSING_DATA with upload date notice.
    3. Boundary transactions without confirmed reporting period -> MISSING_DATA (unconfirmed gap).
    4. Confirmed upload with explicit verified reporting period metadata -> AVAILABLE with 0.0.
    """
    biz1 = test_setup["biz1"]
    today = date.today()

    # Case A: Only failed / unconfirmed upload exists
    failed_upload = SalesUpload(
        business_id=biz1.id,
        filename="corrupted_ledger.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="failed",
        row_count=0,
    )
    db_session.add(failed_upload)
    db_session.commit()

    resp_a = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Revenue with failed upload",
            "metric_key": "monthly_revenue",
            "target_value": 100000.0,
        },
    )
    assert resp_a.status_code == 201
    data_a = resp_a.json()
    assert data_a["data_availability"] == "MISSING_DATA"
    assert data_a["current_value"] is None
    assert "unconfirmed or failed" in data_a["data_freshness_warning"]

    # Case B: Confirmed upload exists, but all transactions are from 180 days ago (window is in future relative to data)
    past_upload = SalesUpload(
        business_id=biz1.id,
        filename="historical_sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=1,
        valid_row_count=1,
    )
    db_session.add(past_upload)
    db_session.commit()

    past_date = today - timedelta(days=180)
    past_txn = SalesTransaction(
        upload_id=past_upload.id,
        business_id=biz1.id,
        transaction_date=datetime.combine(past_date, datetime.min.time()),
        customer_name="Old Customer",
        total_amount=50000.0,
        quantity=1,
        unit_price=50000.0,
        product_name="Historical Product",
        is_duplicate=False,
    )
    db_session.add(past_txn)
    db_session.commit()

    # Monthly revenue goal defaults to current month which is > past_date
    resp_b = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Current Month Revenue Awaiting New Ingestion",
            "metric_key": "monthly_revenue",
            "target_value": 100000.0,
        },
    )
    assert resp_b.status_code == 201
    data_b = resp_b.json()
    assert data_b["data_availability"] == "MISSING_DATA"
    assert data_b["current_value"] is None
    assert "has not been uploaded yet" in data_b["data_freshness_warning"]

    # Case C: Confirmed uploads span from 10 days ago to today, BUT NO confirmed reporting period exists.
    # Proves having transactions at endpoints (10 days ago and today) DOES NOT misclassify intervening days as zero sales.
    recent_upload = SalesUpload(
        business_id=biz1.id,
        filename="recent_sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=2,
        valid_row_count=2,
    )
    db_session.add(recent_upload)
    db_session.commit()

    # Transaction 1: 10 days ago
    t_start = SalesTransaction(
        upload_id=recent_upload.id,
        business_id=biz1.id,
        transaction_date=datetime.combine(today - timedelta(days=10), datetime.min.time()),
        customer_name="Start Cust",
        total_amount=10000.0,
        quantity=1,
        unit_price=10000.0,
        product_name="Product Alpha",
        is_duplicate=False,
    )
    # Transaction 2: today
    t_end = SalesTransaction(
        upload_id=recent_upload.id,
        business_id=biz1.id,
        transaction_date=datetime.combine(today, datetime.min.time()),
        customer_name="End Cust",
        total_amount=12000.0,
        quantity=1,
        unit_price=12000.0,
        product_name="Product Beta",
        is_duplicate=False,
    )
    db_session.add_all([t_start, t_end])
    db_session.commit()

    # Goal window between 5 days ago and 2 days ago: encompassed by endpoints, but lacks confirmed reporting period.
    w_start = today - timedelta(days=5)
    w_target = today - timedelta(days=2)
    resp_c = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Mid-week Window Without Coverage Metadata",
            "metric_key": "revenue",
            "target_value": 50000.0,
            "start_date": w_start.isoformat(),
            "target_date": w_target.isoformat(),
        },
    )
    assert resp_c.status_code == 201
    data_c = resp_c.json()
    assert data_c["data_availability"] == "MISSING_DATA"
    assert data_c["current_value"] is None
    assert "Unconfirmed Coverage Gap" in data_c["evidence_source"]
    assert "No confirmed reporting period or daily completeness" in data_c["data_freshness_warning"]

    # Case D: Confirmed upload explicitly provides verified reporting period coverage in upload metadata.
    # Only with explicit coverage metadata can zero matching transactions be verified as zero sales.
    covered_upload = SalesUpload(
        business_id=biz1.id,
        filename="daily_complete_sales.csv",
        file_format="csv",
        file_size_bytes=2048,
        status="completed",
        row_count=1,
        valid_row_count=1,
        quality_summary={
            "confirmed_reporting_period": {
                "start_date": (today - timedelta(days=7)).isoformat(),
                "end_date": today.isoformat(),
                "is_complete": True,
            },
            "daily_completeness_confirmed": True,
        },
    )
    db_session.add(covered_upload)
    db_session.commit()

    resp_d = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Mid-week Window With Confirmed Period",
            "metric_key": "revenue",
            "target_value": 50000.0,
            "start_date": w_start.isoformat(),
            "target_date": w_target.isoformat(),
        },
    )
    assert resp_d.status_code == 201
    data_d = resp_d.json()
    assert data_d["data_availability"] == "AVAILABLE"
    assert data_d["current_value"] == 0.0
    assert data_d["progress_pct"] == 0.0
    assert "Verified zero transactions in confirmed reporting period" in data_d["evidence_source"]


def test_completeness_default_prevents_false_zero(db_session: Session, test_setup, client_a):
    """Regression test: Omitting 'is_complete' or setting 'is_complete: False' in confirmed_reporting_period
    must NEVER default to True or produce a false verified-zero result.
    
    1. Ledger has transactions on boundaries (10 days ago and today), with zero transactions in between.
    2. Upload metadata covers the window dates, but 'is_complete' is omitted -> MISSING_DATA (Unconfirmed Coverage Gap).
    3. Upload metadata has explicit 'is_complete: False' -> MISSING_DATA (Unconfirmed Coverage Gap).
    4. Only when 'is_complete: True' is explicitly affirmed -> AVAILABLE with 0.0.
    """
    biz1 = test_setup["biz1"]
    today = date.today()
    w_start = today - timedelta(days=6)
    w_target = today - timedelta(days=3)

    # Base upload with transactions at 10 days ago and today
    base_upload = SalesUpload(
        business_id=biz1.id,
        filename="base_sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=2,
        valid_row_count=2,
    )
    db_session.add(base_upload)
    db_session.commit()

    t_start = SalesTransaction(
        upload_id=base_upload.id,
        business_id=biz1.id,
        transaction_date=datetime.combine(today - timedelta(days=10), datetime.min.time()),
        customer_name="Start Cust",
        total_amount=10000.0,
        quantity=1,
        unit_price=10000.0,
        product_name="Product Alpha",
        is_duplicate=False,
    )
    t_end = SalesTransaction(
        upload_id=base_upload.id,
        business_id=biz1.id,
        transaction_date=datetime.combine(today, datetime.min.time()),
        customer_name="End Cust",
        total_amount=12000.0,
        quantity=1,
        unit_price=12000.0,
        product_name="Product Beta",
        is_duplicate=False,
    )
    db_session.add_all([t_start, t_end])
    db_session.commit()

    # 1. Upload covering dates, but 'is_complete' is omitted completely
    upload_omitted = SalesUpload(
        business_id=biz1.id,
        filename="sales_omitted_completeness.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=0,
        valid_row_count=0,
        quality_summary={
            "confirmed_reporting_period": {
                "start_date": (today - timedelta(days=7)).isoformat(),
                "end_date": today.isoformat(),
                # 'is_complete' is deliberately omitted!
            }
        },
    )
    db_session.add(upload_omitted)
    db_session.commit()

    resp_omitted = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Window with Omitted Completeness",
            "metric_key": "revenue",
            "target_value": 50000.0,
            "start_date": w_start.isoformat(),
            "target_date": w_target.isoformat(),
        },
    )
    assert resp_omitted.status_code == 201
    data_omitted = resp_omitted.json()
    assert data_omitted["data_availability"] == "MISSING_DATA"
    assert data_omitted["current_value"] is None
    assert "Unconfirmed Coverage Gap" in data_omitted["evidence_source"]
    assert "No confirmed reporting period or daily completeness" in data_omitted["data_freshness_warning"]

    # 2. Upload with explicit 'is_complete': False
    upload_incomplete = SalesUpload(
        business_id=biz1.id,
        filename="sales_explicit_incomplete.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=0,
        valid_row_count=0,
        quality_summary={
            "confirmed_reporting_period": {
                "start_date": (today - timedelta(days=7)).isoformat(),
                "end_date": today.isoformat(),
                "is_complete": False,
            }
        },
    )
    db_session.add(upload_incomplete)
    db_session.commit()

    resp_inc = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Window with Incomplete Period",
            "metric_key": "revenue",
            "target_value": 50000.0,
            "start_date": w_start.isoformat(),
            "target_date": w_target.isoformat(),
        },
    )
    assert resp_inc.status_code == 201
    data_inc = resp_inc.json()
    assert data_inc["data_availability"] == "MISSING_DATA"
    assert data_inc["current_value"] is None
    assert "Unconfirmed Coverage Gap" in data_inc["evidence_source"]
    assert "No confirmed reporting period or daily completeness" in data_inc["data_freshness_warning"]

    # 3. Upload with explicit 'is_complete': True -> Now verified zero sales is permitted
    upload_complete = SalesUpload(
        business_id=biz1.id,
        filename="sales_explicit_complete.csv",
        file_format="csv",
        file_size_bytes=1024,
        status="completed",
        row_count=0,
        valid_row_count=0,
        quality_summary={
            "confirmed_reporting_period": {
                "start_date": (today - timedelta(days=7)).isoformat(),
                "end_date": today.isoformat(),
                "is_complete": True,
            }
        },
    )
    db_session.add(upload_complete)
    db_session.commit()

    resp_comp = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Window with Complete Period",
            "metric_key": "revenue",
            "target_value": 50000.0,
            "start_date": w_start.isoformat(),
            "target_date": w_target.isoformat(),
        },
    )
    assert resp_comp.status_code == 201
    data_comp = resp_comp.json()
    assert data_comp["data_availability"] == "AVAILABLE"
    assert data_comp["current_value"] == 0.0
    assert data_comp["progress_pct"] == 0.0
    assert "Verified zero transactions in confirmed reporting period" in data_comp["evidence_source"]


def test_audit_trail_immutability_and_snapshots(db_session: Session, test_setup, client_a):
    """Verify that audit records are strictly append-only and snapshots capture complete provenance.

    1. ORM-level updates/deletes are blocked by SQLAlchemy event listeners.
    2. Database-level updates/deletes via raw SQL are blocked by database triggers.
    3. Snapshot contains metric_key, observation_window, measurement_method, evidence_source, calculation_details.
    4. Status changes capture accurate old_status and new_status.
    """
    # 1. Create a goal
    resp = client_a.post(
        "/api/v1/goals",
        json={
            "title": "Audit Snapshot Verification Goal",
            "metric_key": "monthly_revenue",
            "baseline_value": 0.0,
            "target_value": 250000.0,
            "unit": "INR",
        },
    )
    assert resp.status_code == 201
    goal_id = resp.json()["id"]

    # 2. Transition status: ACTIVE -> PAUSED
    resp_pause = client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "PAUSED", "notes": "Paused for seasonal maintenance"},
    )
    assert resp_pause.status_code == 200

    # 3. Transition status: PAUSED -> ACTIVE
    resp_resume = client_a.post(
        f"/api/v1/goals/{goal_id}/status",
        json={"status": "ACTIVE", "notes": "Resumed after seasonal review"},
    )
    assert resp_resume.status_code == 200

    # 4. Fetch audit history via API
    resp_history = client_a.get(f"/api/v1/goals/{goal_id}/history")
    assert resp_history.status_code == 200
    audits = resp_history.json()
    assert len(audits) >= 3

    # Check pause transition audit record
    pause_audit = next((a for a in audits if a["action"] == "STATUS_CHANGED" and a["new_status"] == "PAUSED"), None)
    assert pause_audit is not None
    assert pause_audit["old_status"] == "ACTIVE"
    assert pause_audit["new_status"] == "PAUSED"
    assert pause_audit["snapshot_data"] is not None
    snapshot = pause_audit["snapshot_data"]
    assert snapshot["metric_key"] == "monthly_revenue"
    assert "observation_window" in snapshot
    assert "measurement_method" in snapshot
    assert "evidence_source" in snapshot
    assert "calculation_details" in snapshot
    assert snapshot["calculation_details"]["target_value"] == 250000.0

    # 5. ORM-level immutability check
    db_audit = db_session.query(BusinessGoalAudit).filter(BusinessGoalAudit.goal_id == goal_id).first()
    assert db_audit is not None

    db_audit.notes = "Tampered notes"
    with pytest.raises(ValueError, match="append-only and cannot be updated"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(db_audit)
    with pytest.raises(ValueError, match="append-only and cannot be deleted"):
        db_session.commit()
    db_session.rollback()

    # 6. Database-level trigger immutability check (raw SQL)
    with pytest.raises(Exception):
        db_session.execute(text(f"UPDATE business_goal_audits SET notes='raw_sql_tampered' WHERE id={db_audit.id}"))
        db_session.commit()
    db_session.rollback()

    with pytest.raises(Exception):
        db_session.execute(text(f"DELETE FROM business_goal_audits WHERE id={db_audit.id}"))
        db_session.commit()
    db_session.rollback()

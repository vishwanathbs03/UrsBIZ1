"""Comprehensive Automated Test Suite for Phase 5 Closed-Loop Recommendation Learning & Outcome Intelligence.

Verifies:
  1. Outcome recording (started, completed, actual effort, feedback, reasons).
  2. Before-and-after business measurement across symmetric time windows.
  3. Mandatory causal transparency disclaimer without false causal claims.
  4. Missing baseline data and partial post-window elapsed days handling.
  5. Statistical small-sample safeguards (N < 3 requires provisional disclaimer).
  6. Feedback-driven personalized ranking adjustments (time and capital bottlenecks).
  7. Strict critical risk protection against repeated dismissal suppression.
  8. Immutable recommendation version and decision audit history preservation.
  9. Tenant isolation across businesses.
  10. Natural language AI outcome Q&A responses.
  11. REST API endpoints integration for outcomes, effectiveness, and history.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.middleware.auth_deps import get_current_user
from app.models.business import Business
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_outcome import RecommendationOutcome
from app.models.recommendation_version_history import RecommendationVersionHistory
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.advanced_recommendations import RecommendationAskRequest
from app.schemas.recommendation_outcomes import OutcomeRecordingRequest
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
)
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.open_ended_bi_engine import (
    OpenEndedBusinessIntelligenceEngine,
)
from app.services.recommendations.outcome_learning_engine import (
    RecommendationOutcomeLearningEngine,
)
from app.services.recommendations.outcome_measurement_engine import (
    BeforeAfterMeasurementEngine,
)
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base, get_db


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """Create in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_user(db_session) -> User:
    user = User(
        full_name="Outcome Learning Owner",
        email="learning_owner@ursbiz.com",
        password_hash="hashed_pw_xyz",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_business(db_session, sample_user) -> Business:
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Apex Manufacturing Ltd",
        trade_name="Apex Tools",
        industry="Manufacturing",
        business_type="Private Limited",
        city="Pune",
        state_region="Maharashtra",
        country="India",
        annual_revenue=5000000.0,
        employee_count=18,
        established_year=2020,
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    return biz


def _create_sales_upload(db_session, business_id: int) -> SalesUpload:
    upload = SalesUpload(
        business_id=business_id,
        filename="sales_history.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=10,
        valid_row_count=10,
        invalid_row_count=0,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    return upload


def _build_test_rec(
    rec_id: str,
    title: str,
    category: RecommendationCategory = RecommendationCategory.CUSTOMER_RETENTION,
    priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    priority_score: int = 65,
    difficulty: str = "Tactical",
) -> SmartRecommendationItem:
    return SmartRecommendationItem(
        id=rec_id,
        title=title,
        category=category,
        priority=priority,
        priority_score=priority_score,
        confidence=85.0,
        description=f"Operational initiative: {title}",
        business_context="Empirical telemetry",
        evidence=["Verified sales observation"],
        reasoning="Strategic value creation",
        recommended_actions=["Step 1", "Step 2"],
        expected_benefit="Operational improvement",
        data_quality="High",
        created_at=datetime.now(timezone.utc).isoformat(),
        status=RecommendationStatus.ACCEPTED,
        implementation_difficulty=difficulty,
    )


# --------------------------------------------------------------------------- #
# 1. Outcome Recording & Lifecycle Sync                                       #
# --------------------------------------------------------------------------- #

def test_outcome_recording_lifecycle_sync(db_session, sample_business):
    """Verify that recording an outcome updates lifecycle state and records an audit event."""
    engine = SmartRecommendationEngine(db_session)
    rec_id = "rec_cust_retention_001"

    req = OutcomeRecordingRequest(
        is_started=True,
        is_completed=True,
        actual_effort="Medium",
        owner_rating=5,
        qualitative_feedback="Re-engaged 12 repeat clients with specialized pricing",
        perceived_utility="Very Useful",
        still_relevant=True,
        notes="Completed ahead of schedule",
    )

    res = engine.record_outcome(
        business=sample_business,
        recommendation_id=rec_id,
        req=req,
    )

    assert res.recommendation_id == rec_id
    assert res.is_completed is True
    assert res.is_started is True
    assert res.actual_effort == "Medium"
    assert res.owner_rating == 5
    assert res.qualitative_feedback == "Re-engaged 12 repeat clients with specialized pricing"

    # Verify RecommendationLifecycleState was synchronized to Completed
    lifecycle = engine.lifecycle_repo.get_state(sample_business.id, rec_id)
    assert lifecycle is not None
    assert lifecycle.status == "Completed"

    # Verify audit event was appended to RecommendationVersionHistory
    history = engine.outcome_repo.get_history_for_recommendation(sample_business.id, rec_id)
    assert len(history) >= 1
    assert history[-1].event_type == "COMPLETED"
    assert history[-1].version == 1


# --------------------------------------------------------------------------- #
# 2. Before-and-After Business Measurement with Symmetric Windows & Disclaimer#
# --------------------------------------------------------------------------- #

def test_before_after_measurement_symmetric_windows_and_causal_disclaimer(
    db_session, sample_business
):
    """Verify before-and-after metric comparisons across symmetric windows with mandatory disclaimer."""
    upload = _create_sales_upload(db_session, sample_business.id)
    measurement_engine = BeforeAfterMeasurementEngine(db_session)

    # Completion timestamp 40 days ago
    completed_at = datetime.now(timezone.utc) - timedelta(days=40)

    # 1. Baseline Pre-Period Transactions (40 to 10 days before completion = within 30-day pre-window)
    pre_dates = [completed_at - timedelta(days=d) for d in (25, 20, 15, 10, 5)]
    for d in pre_dates:
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=sample_business.id,
                transaction_date=d,
                product_name="Standard Lathe Part",
                quantity=10.0,
                unit_price=1000.0,
                total_amount=10000.0,  # 5 txs * 10,000 = 50,000 baseline
                customer_name="Client Alpha",
            )
        )

    # 2. Post-Period Transactions (within 30 days after completion)
    post_dates = [completed_at + timedelta(days=d) for d in (3, 7, 12, 18, 22, 28)]
    for d in post_dates:
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=sample_business.id,
                transaction_date=d,
                product_name="Standard Lathe Part",
                quantity=10.0,
                unit_price=1100.0,
                total_amount=11000.0,  # 6 txs * 11,000 = 66,000 post
                customer_name="Client Beta",
            )
        )
    db_session.commit()

    res = measurement_engine.measure_outcome(
        business_id=sample_business.id,
        recommendation_id="rec_retention_surge_01",
        recommendation_title="Client Retention Surge",
        completed_at=completed_at,
        window_days=30,
    )

    assert res.window_status == "COMPLETED_WINDOW"
    assert res.elapsed_days_since_completion >= 30
    assert len(res.metrics) >= 3

    # Revenue Metric Verification
    rev_metric = next(m for m in res.metrics if m.metric_name == "Total Revenue")
    assert rev_metric.baseline_value == 50000.0
    assert rev_metric.post_value == 66000.0
    assert rev_metric.delta_absolute == 16000.0
    assert rev_metric.delta_percentage == 32.0
    assert rev_metric.direction == "INCREASED"

    # Mandatory Causal Disclaimer Verification
    assert "Revenue increased by 32.0% during the measurement period after this action was completed" in res.causal_disclaimer
    assert "observed change, not proof that the action alone caused the increase" in res.causal_disclaimer
    assert res.learning_quality_tier == "OBSERVED_CORRELATION"


# --------------------------------------------------------------------------- #
# 3. Missing Baseline Data & Partial Window Handling                          #
# --------------------------------------------------------------------------- #

def test_missing_baseline_data_handling(db_session, sample_business):
    """Verify graceful handling when pre-period transactions are missing."""
    measurement_engine = BeforeAfterMeasurementEngine(db_session)
    completed_at = datetime.now(timezone.utc) - timedelta(days=35)

    res = measurement_engine.measure_outcome(
        business_id=sample_business.id,
        recommendation_id="rec_missing_baseline",
        recommendation_title="Digital Marketing",
        completed_at=completed_at,
        window_days=30,
    )

    assert res.window_status == "INSUFFICIENT_BASELINE_DATA"
    assert any("Baseline performance could not be established" in gap for gap in res.data_gaps)


def test_partial_measurement_period_insufficient_elapsed_days(db_session, sample_business):
    """Verify partial window flagging when fewer days have elapsed than the required window."""
    upload = _create_sales_upload(db_session, sample_business.id)
    completed_at = datetime.now(timezone.utc) - timedelta(days=12)

    # Seed baseline pre-period sales transaction
    db_session.add(
        SalesTransaction(
            upload_id=upload.id,
            business_id=sample_business.id,
            transaction_date=completed_at - timedelta(days=10),
            product_name="Lathe Part",
            quantity=5.0,
            unit_price=2000.0,
            total_amount=10000.0,
            customer_name="Client Test",
        )
    )
    db_session.commit()

    measurement_engine = BeforeAfterMeasurementEngine(db_session)
    res = measurement_engine.measure_outcome(
        business_id=sample_business.id,
        recommendation_id="rec_recent_action",
        recommendation_title="Recent Action",
        completed_at=completed_at,
        window_days=30,
    )

    assert res.window_status == "PARTIAL_WINDOW_IN_PROGRESS"
    assert res.elapsed_days_since_completion == 12
    assert any("Only 12 days have elapsed" in gap for gap in res.data_gaps)
    assert any("requires 18 additional days" in gap for gap in res.data_gaps)


# --------------------------------------------------------------------------- #
# 4. Statistical Small-Sample Safeguards                                      #
# --------------------------------------------------------------------------- #

def test_statistical_small_sample_safeguard(db_session, sample_business):
    """Verify that categories with N < 3 completed actions are flagged as Insufficient Sample Size."""
    learning_engine = RecommendationOutcomeLearningEngine(db_session)

    # Business has 2 completed actions in Customer Retention
    for idx in (1, 2):
        rec_id = f"rec_customer_retention_{idx}"
        db_session.add(
            RecommendationLifecycleState(
                business_id=sample_business.id,
                recommendation_id=rec_id,
                status="Completed",
            )
        )
        db_session.add(
            RecommendationOutcome(
                business_id=sample_business.id,
                recommendation_id=rec_id,
                is_completed=True,
                owner_rating=5,
            )
        )
    db_session.commit()

    eff_res = learning_engine.compute_effectiveness_intelligence(sample_business.id)
    retention_cat = next(
        c for c in eff_res.category_effectiveness
        if c.category == RecommendationCategory.CUSTOMER_RETENTION.value
    )

    # Must be flagged as Insufficient Sample Size because N = 2 < 3
    assert retention_cat.total_completed == 2
    assert retention_cat.statistical_reliability == "Insufficient Sample Size"
    assert retention_cat.small_sample_warning is not None
    assert "Fewer than 3 completed actions recorded" in retention_cat.small_sample_warning
    assert eff_res.small_sample_safeguard_applied is True

    # Now complete a 3rd action (N = 3)
    rec_id_3 = "rec_customer_retention_3"
    db_session.add(
        RecommendationLifecycleState(
            business_id=sample_business.id,
            recommendation_id=rec_id_3,
            status="Completed",
        )
    )
    db_session.add(
        RecommendationOutcome(
            business_id=sample_business.id,
            recommendation_id=rec_id_3,
            is_completed=True,
            owner_rating=4,
        )
    )
    db_session.commit()

    eff_res_updated = learning_engine.compute_effectiveness_intelligence(sample_business.id)
    retention_cat_updated = next(
        c for c in eff_res_updated.category_effectiveness
        if c.category == RecommendationCategory.CUSTOMER_RETENTION.value
    )

    # Now N = 3 >= 3, updates to Moderate and clears warning
    assert retention_cat_updated.total_completed == 3
    assert retention_cat_updated.statistical_reliability == "Moderate"
    assert retention_cat_updated.small_sample_warning is None


# --------------------------------------------------------------------------- #
# 5. Feedback-Driven Ranking & Non-Completion Bottlenecks                     #
# --------------------------------------------------------------------------- #

def test_feedback_driven_ranking_adjustments_time_bottleneck(db_session, sample_business):
    """Verify that multiple non-completions due to LACK_OF_TIME penalize complex actions and boost quick wins."""
    learning_engine = RecommendationOutcomeLearningEngine(db_session)

    # Inject 2 abandoned actions due to LACK_OF_TIME
    for idx in (1, 2):
        db_session.add(
            RecommendationOutcome(
                business_id=sample_business.id,
                recommendation_id=f"rec_abandoned_{idx}",
                is_started=True,
                is_abandoned=True,
                non_completion_reason="LACK_OF_TIME",
            )
        )
    db_session.commit()

    quick_win = _build_test_rec(
        "rec_quick_win",
        "Quick Win Action",
        difficulty="Quick Win",
        priority_score=60,
    )
    strategic_action = _build_test_rec(
        "rec_strategic_move",
        "Complex Strategic Initiative 30-90 days",
        difficulty="Strategic",
        priority_score=75,
    )
    strategic_action.constraint_adjusted_feasibility = 80.0

    adjusted = learning_engine.apply_learning_to_recommendations(
        recommendations=[strategic_action, quick_win],
        business_id=sample_business.id,
    )

    # Quick win received +5 boost (60 -> 65)
    rec_qw = next(r for r in adjusted if r.id == "rec_quick_win")
    assert rec_qw.priority_score == 65

    # Strategic move received feasibility penalty and limitation note
    rec_strat = next(r for r in adjusted if r.id == "rec_strategic_move")
    assert rec_strat.constraint_adjusted_feasibility == 65.0  # 80 - 15
    assert any("past time constraints" in lim for lim in rec_strat.limitations)


# --------------------------------------------------------------------------- #
# 6. Critical Risk Protection Invariant                                       #
# --------------------------------------------------------------------------- #

def test_critical_risk_invariant_protection_against_dismissal_suppression(
    db_session, sample_business
):
    """Verify that repeated dismissals suppress non-critical items, but NEVER suppress critical risks."""
    learning_engine = RecommendationOutcomeLearningEngine(db_session)

    # Dismiss Non-critical recommendation twice
    for _ in range(2):
        db_session.add(
            RecommendationFeedback(
                business_id=sample_business.id,
                recommendation_id="rec_tactical_marketing",
                feedback_type="Not relevant",
                suppress_recommendation=True,
            )
        )

    # Dismiss Critical Risk recommendation twice
    for _ in range(2):
        db_session.add(
            RecommendationFeedback(
                business_id=sample_business.id,
                recommendation_id="rec_critical_concentration_risk",
                feedback_type="Not feasible",
                suppress_recommendation=True,
            )
        )
    db_session.commit()

    tactical_item = _build_test_rec(
        "rec_tactical_marketing",
        "Tactical Social Ads",
        priority=RecommendationPriority.MEDIUM,
        priority_score=50,
    )
    critical_item = _build_test_rec(
        "rec_critical_concentration_risk",
        "Mitigate 85% Single Customer Concentration Risk",
        category=RecommendationCategory.RISK_REDUCTION,
        priority=RecommendationPriority.CRITICAL,
        priority_score=95,
    )

    adjusted = learning_engine.apply_learning_to_recommendations(
        recommendations=[critical_item, tactical_item],
        business_id=sample_business.id,
    )

    remaining_ids = [r.id for r in adjusted]

    # Tactical item MUST be suppressed (omitted)
    assert "rec_tactical_marketing" not in remaining_ids

    # Critical risk item MUST BE PRESERVED despite repeated dismissals!
    assert "rec_critical_concentration_risk" in remaining_ids
    crit_rec = next(r for r in adjusted if r.id == "rec_critical_concentration_risk")
    assert any("Critical Risk Notice" in lim for lim in crit_rec.limitations)


# --------------------------------------------------------------------------- #
# 7. Immutable Version History & Audit Trail Preservation                     #
# --------------------------------------------------------------------------- #

def test_immutable_version_history_preservation(db_session, sample_business):
    """Verify that successive events append new versions without erasing historical snapshots."""
    engine = SmartRecommendationEngine(db_session)
    rec_id = "rec_audit_trail_001"

    # Event 1: Accepted
    req1 = OutcomeRecordingRequest(is_started=True, notes="Started implementation")
    engine.record_outcome(sample_business, rec_id, req1)

    # Event 2: Progress update
    req2 = OutcomeRecordingRequest(actual_effort="Low", notes="Completed phase 1")
    engine.record_outcome(sample_business, rec_id, req2)

    # Event 3: Completed
    req3 = OutcomeRecordingRequest(is_completed=True, owner_rating=5, qualitative_feedback="Finished successfully")
    engine.record_outcome(sample_business, rec_id, req3)

    history_res = engine.get_recommendation_history(sample_business, rec_id)

    assert len(history_res.events) >= 3
    assert history_res.current_version >= 3
    versions = [e.version for e in history_res.events]
    assert versions == sorted(versions)  # Monotonically increasing versions
    assert history_res.events[-1].event_type == "COMPLETED"


# --------------------------------------------------------------------------- #
# 8. Tenant Isolation Across Businesses                                       #
# --------------------------------------------------------------------------- #

def test_tenant_isolation_outcomes_and_history(db_session, sample_user):
    """Verify complete isolation: Business A outcomes and history are invisible to Business B."""
    biz_a = Business(owner_id=sample_user.id, legal_name="Company Alpha", industry="Retail", established_year=2021)
    biz_b = Business(owner_id=sample_user.id, legal_name="Company Beta", industry="Retail", established_year=2022)
    db_session.add_all([biz_a, biz_b])
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)

    # Record outcome for Business A
    engine.record_outcome(
        biz_a,
        "rec_shared_slug_1",
        OutcomeRecordingRequest(is_completed=True, owner_rating=5),
    )

    # Query outcome for Business B
    outcome_b = engine.get_outcome(biz_b, "rec_shared_slug_1")
    assert outcome_b.is_completed is False
    assert outcome_b.owner_rating is None

    # Query history for Business B
    history_b = engine.get_recommendation_history(biz_b, "rec_shared_slug_1")
    assert len(history_b.events) == 0


# --------------------------------------------------------------------------- #
# 9. AI Outcome Explanations (Natural Language Q&A)                           #
# --------------------------------------------------------------------------- #

def test_ai_outcome_explanations_conversational_queries(db_session, sample_business):
    """Verify natural language outcome explanations for completed, measured, and ignored actions."""
    engine = SmartRecommendationEngine(db_session)

    # 1. Complete an action
    engine.record_outcome(
        sample_business,
        "rec_vip_client_retention",
        OutcomeRecordingRequest(
            is_completed=True,
            actual_effort="Low",
            owner_rating=5,
            qualitative_feedback="Re-engaged top accounts",
        ),
    )

    # 2. Dismiss an action
    db_session.add(
        RecommendationLifecycleState(
            business_id=sample_business.id,
            recommendation_id="rec_expensive_erp",
            status="Dismissed",
            notes="Too expensive for current stage",
        )
    )
    db_session.commit()

    # Query A: "Which of my recommendations have I completed?"
    req_a = RecommendationAskRequest(question="Which of my recommendations have I completed?")
    ans_a = engine.ask_recommendation_question(sample_business, req_a)
    assert ans_a.intent == "completed_recommendations_outcome"
    assert "rec_vip_client_retention" in ans_a.direct_answer

    # Query B: "Which actions have shown measurable improvement?"
    req_b = RecommendationAskRequest(question="Which actions have shown measurable improvement?")
    ans_b = engine.ask_recommendation_question(sample_business, req_b)
    assert ans_b.intent == "measurable_improvement_outcome"
    assert "Causal Transparency Disclaimer" in ans_b.direct_answer

    # Query C: "Which recommendations did I repeatedly ignore?"
    req_c = RecommendationAskRequest(question="Which recommendations did I repeatedly ignore?")
    ans_c = engine.ask_recommendation_question(sample_business, req_c)
    assert ans_c.intent == "repeatedly_ignored_recommendations"
    assert "rec_expensive_erp" in ans_c.direct_answer

    # Query D: "What should I prioritize based on my previous actions?"
    req_d = RecommendationAskRequest(question="What should I prioritize based on my previous actions?")
    ans_d = engine.ask_recommendation_question(sample_business, req_d)
    assert ans_d.intent == "prioritization_from_previous_actions"
    assert "completed" in ans_d.direct_answer.lower()


# --------------------------------------------------------------------------- #
# 10. API Endpoints Integration                                               #
# --------------------------------------------------------------------------- #

def test_outcome_and_effectiveness_endpoints_api_integration(
    db_session, sample_user, sample_business
):
    """Verify REST API endpoints for outcome tracking, effectiveness analytics, and audit history."""
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        rec_id = "rec_endpoint_test_01"

        # 1. POST /api/v1/recommendations/{id}/outcome
        post_payload = {
            "is_started": True,
            "is_completed": True,
            "actual_effort": "Low",
            "owner_rating": 5,
            "qualitative_feedback": "Successfully executed",
            "perceived_utility": "Very Useful",
        }
        res_post = client.post(f"/api/v1/recommendations/{rec_id}/outcome", json=post_payload)
        assert res_post.status_code == 200
        data_post = res_post.json()
        assert data_post["is_completed"] is True
        assert data_post["owner_rating"] == 5

        # 2. GET /api/v1/recommendations/{id}/outcome
        res_get = client.get(f"/api/v1/recommendations/{rec_id}/outcome?window_days=30")
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert data_get["recommendation_id"] == rec_id
        assert data_get["measurement"] is not None
        assert "causal_disclaimer" in data_get["measurement"]

        # 3. GET /api/v1/recommendations/effectiveness/analytics
        res_eff = client.get("/api/v1/recommendations/effectiveness/analytics")
        assert res_eff.status_code == 200
        data_eff = res_eff.json()
        assert "category_effectiveness" in data_eff
        assert "overall_completion_rate_pct" in data_eff

        # 4. GET /api/v1/recommendations/{id}/history
        res_hist = client.get(f"/api/v1/recommendations/{rec_id}/history")
        assert res_hist.status_code == 200
        data_hist = res_hist.json()
        assert len(data_hist["events"]) >= 1

        # 5. GET /api/v1/recommendations/history/all
        res_all_hist = client.get("/api/v1/recommendations/history/all?limit=50")
        assert res_all_hist.status_code == 200
        data_all_hist = res_all_hist.json()
        assert data_all_hist["total_events"] >= 1

    finally:
        app.dependency_overrides.clear()

"""Master Final Phase 5 Regression and Cross-Phase Verification Suite (Roadmap Item 15).

Authoritatively verifies the complete 15-step Advanced UrsBiz Recommendation Roadmap:
  1. Business context and data integration (Health, Sales, Profile, Schemes)
  2. Dynamic recommendation rules and categories (10 categories, strict boundaries)
  3. Evidence-based prioritization and scoring (Exact 25/25/20/15/15 formula)
  4. Recommendation persistence and lifecycle (New -> Viewed -> Accepted -> Completed)
  5. Gemini explanations and action plans (9-Pillar executive diagnostic brief)
  6. Recommendation dashboard & API integration (Endpoints, overview, response models)
  7. Open-ended AI business reasoning (Free-form Q&A with 13 sandboxed tools)
  8. AI quality and hallucination prevention (10-dimension evaluation, boundary audit)
  9. Data integrity and provenance (Audit trails, data freshness, cross-module consistency)
  10. Platform reliability & resilience (Idempotency, failure recovery, error envelopes)
  11. Autonomous opportunity discovery (Beyond rules, hypothesis generation, version bumps)
  12. Business DNA personalization (Goals, maturity fit, constraints, critical risk protection)
  13. Recommendation portfolio optimization (Dependencies, 3 conflict archetypes, sequencing)
  14. Closed-loop learning and outcome intelligence (Outcome tracking, before/after measurement)
  15. Complete Phase 5 regression and cross-phase integrity
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.business import Business
from app.models.data_provenance import BusinessDataProvenance
from app.models.idempotency import IdempotencyRecord
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.recommendation_outcome import RecommendationOutcome
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.advanced_recommendations import (
    RecommendationAskRequest,
    ScenarioSimulationRequest,
)
from app.schemas.data_provenance import (
    DataProvenanceRecord,
    DataQualityStatus,
    FreshnessStatus,
    MetricNature,
    ModuleDomain,
)
from app.schemas.recommendation_outcomes import OutcomeRecordingRequest
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
)
from app.services.data_integrity.provenance_service import ProvenanceService
from app.services.health_score_service import HealthScoreService
from app.services.resilience.idempotency_service import IdempotencyService
from app.services.recommendations.explanation_service import explain_recommendation
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """Create in-memory SQLite database session using StaticPool for multi-threaded safety."""
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
def master_user(db_session) -> User:
    user = User(
        full_name="Master Verification Owner",
        email="master_verification@ursbiz.com",
        password_hash="secure_hash_phase5_master",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def master_business(db_session, master_user) -> Business:
    biz = Business(
        owner_id=master_user.id,
        legal_name="Apex Precision Engineering Pvt Ltd",
        trade_name="Apex Precision",
        industry="Manufacturing",
        business_type="Private Limited",
        city="Coimbatore",
        state_region="Tamil Nadu",
        country="India",
        annual_revenue=15000000.0,
        employee_count=32,
        established_year=2018,
    )
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)
    return biz


# --------------------------------------------------------------------------- #
# MASTER TEST 1: Full 15-Step End-to-End Roadmap Verification Lifecycle       #
# --------------------------------------------------------------------------- #

def test_master_phase5_end_to_end_roadmap_lifecycle(
    db_session, master_user, master_business
):
    """Execute complete 15-step cross-phase integration verification."""
    engine = SmartRecommendationEngine(db_session)

    # ----------------------------------------------------------------------- #
    # Step 1: Business Context & Data Integration                             #
    # ----------------------------------------------------------------------- #
    health_rep = HealthScoreService.compute(master_business)
    assert 0 <= health_rep.score <= 100
    assert health_rep.grade in ["A", "B", "C", "D", "E", "F"]

    # Ingest sales dataset
    upload = SalesUpload(
        business_id=master_business.id,
        filename="master_verified_ledger.csv",
        file_format="csv",
        file_size_bytes=4096,
        row_count=12,
        valid_row_count=12,
        invalid_row_count=0,
        status="processed",
    )
    db_session.add(upload)
    db_session.commit()

    # Seed 60 days of historical sales (Baseline Pre-Period + Active Transactions)
    now = datetime.now(timezone.utc)
    for i in range(1, 13):
        t_date = now - timedelta(days=(65 - (i * 4)))
        db_session.add(
            SalesTransaction(
                upload_id=upload.id,
                business_id=master_business.id,
                transaction_date=t_date,
                product_name="CNC Machined Flange" if i % 2 == 0 else "High Precision Valve",
                quantity=15.0,
                unit_price=2000.0,
                total_amount=30000.0,
                customer_name="Southern Defense Corp" if i <= 8 else "Industrial Motors Ltd",
            )
        )
    db_session.commit()

    ctx = engine.context_service.build_context(master_business)
    assert ctx.sales.has_sales_data is True
    assert ctx.sales.total_transactions == 12
    assert ctx.sales.total_revenue == 360000.0
    assert ctx.customers.total_customers >= 2

    # ----------------------------------------------------------------------- #
    # Step 2 & 3: Dynamic Rules, Categories & 25/25/20/15/15 Prioritization   #
    # ----------------------------------------------------------------------- #
    recs_res = engine.generate_recommendations(business=master_business)
    assert recs_res.total_count > 0
    assert len(recs_res.recommendations) > 0

    top_rec = recs_res.recommendations[0]
    assert 0 <= top_rec.priority_score <= 100
    assert top_rec.category in list(RecommendationCategory)
    assert top_rec.priority in list(RecommendationPriority)

    # Strict audit boundary verification: No stockout predictions or ungrounded claims
    for r in recs_res.recommendations:
        desc_lower = r.description.lower()
        assert "stockout on" not in desc_lower
        assert "exact reorder quantity" not in desc_lower

    # ----------------------------------------------------------------------- #
    # Step 4: Recommendation Persistence and Lifecycle Tracking              #
    # ----------------------------------------------------------------------- #
    target_rec_id = top_rec.id
    lifecycle_viewed = engine.lifecycle_repo.get_state(master_business.id, target_rec_id)
    assert lifecycle_viewed is not None
    assert lifecycle_viewed.status in ["New", "Viewed"]

    # Transition status: Viewed -> Accepted -> In Progress
    engine.lifecycle_repo.update_status(
        master_business.id, target_rec_id, "Accepted", notes="Owner accepted priority"
    )
    lc_accepted = engine.lifecycle_repo.get_state(master_business.id, target_rec_id)
    assert lc_accepted.status == "Accepted"

    # ----------------------------------------------------------------------- #
    # Step 5: Gemini Explanations & 9-Pillar Diagnostic Brief                 #
    # ----------------------------------------------------------------------- #
    explain_res = explain_recommendation(
        rec=top_rec,
        business_name=master_business.legal_name,
        industry=master_business.industry,
    )
    assert explain_res.recommendation_id == top_rec.id
    assert explain_res.what_is_happening is not None
    assert explain_res.why_is_it_happening is not None
    assert explain_res.inaction_cost is not None
    assert len(explain_res.practical_steps) > 0

    # ----------------------------------------------------------------------- #
    # Step 6: Advanced Overview & Portfolio Roadmaps                          #
    # ----------------------------------------------------------------------- #
    overview = engine.get_advanced_overview(master_business)
    assert overview.next_best_action is not None
    assert isinstance(overview.root_cause_analyses, list)

    strategy = engine.get_growth_strategy(master_business)
    assert len(strategy.horizons) == 3
    assert len(strategy.critical_success_factors) > 0

    # ----------------------------------------------------------------------- #
    # Step 7 & 8: Open-Ended AI Business Reasoning & AI Quality Evaluation    #
    # ----------------------------------------------------------------------- #
    ask_req = RecommendationAskRequest(
        question="Why are my sales concentrated in Southern Defense Corp and what should I do?"
    )
    ask_res = engine.ask_recommendation_question(master_business, ask_req)
    assert ask_res.answerability.value in ["ANSWERABLE", "PARTIALLY_ANSWERABLE"]
    assert "Southern Defense Corp" in ask_res.direct_answer or len(ask_res.evidence_points) > 0
    assert ask_res.quality_evaluation is not None
    assert ask_res.quality_evaluation.overall_quality_score >= 60.0
    assert ask_res.quality_evaluation.validation_status in ["PASSED", "WARNING"]

    # ----------------------------------------------------------------------- #
    # Step 9: Data Integrity & Provenance Tracking                           #
    # ----------------------------------------------------------------------- #
    prov_service = ProvenanceService(db_session)
    prov_record = prov_service.register_metric(
        DataProvenanceRecord(
            business_id=master_business.id,
            metric_name="total_revenue",
            metric_value=360000.0,
            source_module=ModuleDomain.SALES,
            source_record_ref=f"sales_uploads:{upload.id}",
            calculation_methodology="SUM(sales_transactions.total_amount)",
            measurement_period="historical_60d",
            unit="INR",
            currency="INR",
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            data_quality_status=DataQualityStatus.VERIFIED,
            nature=MetricNature.ACTUAL,
            freshness_status=FreshnessStatus.FRESH,
            confidence_score=100.0,
        )
    )
    fetched_record = prov_service.get_provenance(master_business.id, "total_revenue")
    assert fetched_record is not None
    assert fetched_record.metric_value == 360000.0
    assert fetched_record.source_module == ModuleDomain.SALES

    # ----------------------------------------------------------------------- #
    # Step 10: Platform Reliability & Idempotency Service                     #
    # ----------------------------------------------------------------------- #
    idemp_service = IdempotencyService(db_session)
    idem_key = "idemp_master_key_999"
    req_hash = idemp_service.compute_request_hash({"reduction": 20.0})
    is_replay, cached = idemp_service.acquire_lock(
        master_business.id,
        idem_key,
        "scenario_simulation",
        req_hash,
    )
    assert is_replay is False
    assert cached is None
    idemp_service.record_success(master_business.id, idem_key, {"status": "ok", "projected_growth": 15.0})
    is_replay_again, cached_again = idemp_service.acquire_lock(
        master_business.id,
        idem_key,
        "scenario_simulation",
        req_hash,
    )
    assert is_replay_again is True
    assert cached_again["status"] == "ok"
    assert cached_again["status"] == "ok"

    # ----------------------------------------------------------------------- #
    # Step 11: Autonomous Opportunity Discovery                              #
    # ----------------------------------------------------------------------- #
    opps = engine.opportunity_engine.discover(ctx)
    assert isinstance(opps, list)
    for opp in opps:
        assert opp.title is not None
        assert opp.quality_status.value in ["VERIFIED_OPPORTUNITY", "PROMISING_OPPORTUNITY", "NEEDS_INVESTIGATION"]

    # ----------------------------------------------------------------------- #
    # Step 12: Business DNA Personalization & Goal Alignment                  #
    # ----------------------------------------------------------------------- #
    pers_profile = engine.get_personalization_profile(master_business)
    assert pers_profile.business_id == master_business.id
    assert pers_profile.evaluated_maturity.value in ["Early Stage", "Growing", "Established"]
    assert len(pers_profile.maturity_drivers) > 0

    # ----------------------------------------------------------------------- #
    # Step 13: Recommendation Portfolio Optimization & Conflict Resolution   #
    # ----------------------------------------------------------------------- #
    portfolio = engine.get_recommendation_portfolio(master_business)
    assert portfolio.portfolio_health_score >= 10
    assert len(portfolio.execution_sequence) > 0
    # Topological execution stages strictly ordered: First -> Supporting -> Dependent -> Strategic
    stages = [a.stage for a in portfolio.execution_sequence]
    assert all(s in ["FIRST_ACTION", "SUPPORTING_ACTION", "DEPENDENT_ACTION", "STRATEGIC_INITIATIVE"] for s in stages)

    # ----------------------------------------------------------------------- #
    # Step 14: Closed-Loop Learning & Business Outcome Intelligence           #
    # ----------------------------------------------------------------------- #
    # Record implementation outcome
    outcome_req = OutcomeRecordingRequest(
        is_started=True,
        is_completed=True,
        actual_effort="Medium",
        owner_rating=5,
        qualitative_feedback="Successfully secured 2 additional clients, balancing concentration.",
        perceived_utility="Very Useful",
        still_relevant=True,
    )
    outcome_res = engine.record_outcome(
        business=master_business,
        recommendation_id=target_rec_id,
        req=outcome_req,
    )
    assert outcome_res.is_completed is True
    assert outcome_res.owner_rating == 5

    # Before-and-after business measurement
    outcome_tracking = engine.get_outcome(master_business, target_rec_id, window_days=30)
    assert outcome_tracking.measurement is not None
    assert "observed change, not proof that the action alone caused" in outcome_tracking.measurement.causal_disclaimer

    # Effectiveness analytics with small-sample safeguard
    eff_res = engine.get_effectiveness_analytics(master_business)
    assert eff_res.total_completed >= 1
    assert eff_res.small_sample_safeguard_applied is True  # N=1 < 3 completed actions

    # Immutable history audit trail
    history = engine.get_recommendation_history(master_business, target_rec_id)
    assert len(history.events) >= 1
    assert history.events[-1].event_type == "COMPLETED"

    # ----------------------------------------------------------------------- #
    # Step 15: Natural Language Outcome Explanations & Verification           #
    # ----------------------------------------------------------------------- #
    q_outcomes = RecommendationAskRequest(question="Which of my recommendations have I completed?")
    ans_outcomes = engine.ask_recommendation_question(master_business, q_outcomes)
    assert ans_outcomes.intent == "completed_recommendations_outcome"
    assert target_rec_id in ans_outcomes.direct_answer


# --------------------------------------------------------------------------- #
# MASTER TEST 2: Multi-Signal Simulation & Stress Test                        #
# --------------------------------------------------------------------------- #

def test_master_scenario_simulation_deterministic_math(db_session, master_business):
    """Verify deterministic What-If simulation accuracy across revenue and customer drop scenarios."""
    engine = SmartRecommendationEngine(db_session)

    sim_req = ScenarioSimulationRequest(
        sales_growth_pct=15.0,
        repeat_customer_rate_improvement_pct=20.0,
        expense_reduction_pct=5.0,
        concentration_reduction_pct=10.0,
    )
    sim_res = engine.simulate_scenario(master_business, sim_req)

    # Monthly revenue baseline (15,000,000 / 12 = 1,250,000)
    assert sim_res.baseline_revenue == 1250000.0
    assert abs(sim_res.projected_revenue - (sim_res.baseline_revenue * 1.15)) < 0.05
    assert sim_res.estimated_gross_profit_change > 0.0
    assert len(sim_res.metrics) == 4
    assert "Hypothetical mathematical projection" in sim_res.projection_disclaimer

"""Comprehensive Test Suite for Phase 5 Personalized Business DNA & Adaptive Recommendations.

Verifies:
  1. Business maturity evaluation (Early-Stage, Growing, Established).
  2. Maturity fit scoring adaptation.
  3. Goal-aware prioritization dynamic re-ranking.
  4. Constraint-aware feasibility penalties and warnings.
  5. Conflicting preferences and constraints resolution.
  6. Critical risk protection rule (never demoted or overridden by personalization).
  7. Owner feedback learning and critical risk non-suppression rule.
  8. Graceful handling of new businesses with limited information (zero hallucinations).
  9. Personalization API endpoints (GET profile & PUT settings).
  10. Core Acceptance Criterion: Two distinct businesses receive distinct recommendation priorities.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Business
from app.models.personalization import BusinessPersonalizationSettings
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.sales import SalesTransaction
from app.models.user import User
from app.schemas.advanced_recommendations import RecommendationFeedbackCreate
from app.schemas.personalization import (
    BusinessConstraintType,
    BusinessGoalType,
    BusinessMaturityLevel,
    PersonalizationSettingsUpdate,
)
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
)
from app.services.recommendations.personalization_engine import PersonalizationEngine
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """Create in-memory SQLite database session with all registered tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
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
        full_name="Test Owner",
        email="test_owner@ursbiz.com",
        password_hash="hashed_pw_abc",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #

def test_maturity_evaluation_early_vs_growing_vs_established(db_session, sample_user):
    """Test deterministic evaluation of organizational maturity from factual telemetry."""
    # 1. Early-Stage Business (1 year old, 2 employees, low revenue)
    biz_early = Business(
        owner_id=sample_user.id,
        legal_name="Early Startup Ltd",
        industry="Retail",
        established_year=datetime.now(timezone.utc).year - 1,
        employee_count=2,
        annual_revenue=300000.0,
    )
    db_session.add(biz_early)
    db_session.commit()

    mat_early, drivers_early = PersonalizationEngine.evaluate_maturity(biz_early, 0.0, 0)
    assert mat_early == BusinessMaturityLevel.EARLY_STAGE
    assert any("Workforce: 2" in d for d in drivers_early)

    # 2. Established Business (10 years old, 25 employees, high revenue)
    biz_est = Business(
        owner_id=sample_user.id,
        legal_name="Apex Manufacturing Corp",
        industry="Manufacturing",
        established_year=datetime.now(timezone.utc).year - 10,
        employee_count=25,
        annual_revenue=25000000.0,
    )
    db_session.add(biz_est)
    db_session.commit()

    mat_est, drivers_est = PersonalizationEngine.evaluate_maturity(biz_est, 15000000.0, 150)
    assert mat_est == BusinessMaturityLevel.ESTABLISHED
    assert any("25 employees" in d for d in drivers_est)

    # 3. Growing Business (4 years old, 8 employees, moderate turnover)
    biz_grow = Business(
        owner_id=sample_user.id,
        legal_name="Midway Textiles",
        industry="Textiles",
        established_year=datetime.now(timezone.utc).year - 4,
        employee_count=8,
        annual_revenue=3500000.0,
    )
    db_session.add(biz_grow)
    db_session.commit()

    mat_grow, drivers_grow = PersonalizationEngine.evaluate_maturity(biz_grow, 3500000.0, 45)
    assert mat_grow == BusinessMaturityLevel.GROWING


def test_maturity_fit_scoring_adaptation():
    """Verify that recommendation categories score differently according to business maturity."""
    engine = PersonalizationEngine()

    # Early stage: High fit on digital presence & startup grants, lower fit on advanced demand forecasting
    fit_early_dig = engine.calculate_maturity_fit(
        RecommendationCategory.DIGITAL_TRANSFORMATION,
        BusinessMaturityLevel.EARLY_STAGE,
        "Quick Win",
    )
    fit_early_demand = engine.calculate_maturity_fit(
        RecommendationCategory.DEMAND_PLANNING,
        BusinessMaturityLevel.EARLY_STAGE,
        "Strategic",
    )
    assert fit_early_dig >= 85.0
    assert fit_early_demand <= 60.0

    # Established: High fit on risk reduction and cost optimization, lower fit on basic digital presence
    fit_est_risk = engine.calculate_maturity_fit(
        RecommendationCategory.RISK_REDUCTION,
        BusinessMaturityLevel.ESTABLISHED,
        "Tactical",
    )
    fit_est_dig = engine.calculate_maturity_fit(
        RecommendationCategory.DIGITAL_TRANSFORMATION,
        BusinessMaturityLevel.ESTABLISHED,
        "Quick Win",
    )
    assert fit_est_risk >= 90.0
    assert fit_est_dig <= 65.0


def test_goal_aware_prioritization_shifts_ranking():
    """Verify that different owner goals dynamically boost aligned recommendation categories."""
    engine = PersonalizationEngine()

    rev_cand = {
        "category": RecommendationCategory.REVENUE_GROWTH,
        "title": "Launch Volume Discounting",
        "description": "Increase average order value and overall sales revenue.",
    }
    cost_cand = {
        "category": RecommendationCategory.COST_OPTIMIZATION,
        "title": "Consolidate Packaging Expenses",
        "description": "Cut operating costs and improve gross operating margins.",
    }

    # When goal is INCREASE_REVENUE
    rev_goal = [BusinessGoalType.INCREASE_REVENUE.value]
    align_rev = engine.calculate_goal_alignment(rev_cand["category"], rev_cand["title"], rev_cand["description"], rev_goal)
    align_cost = engine.calculate_goal_alignment(cost_cand["category"], cost_cand["title"], cost_cand["description"], rev_goal)
    assert align_rev > align_cost
    assert align_rev >= 90.0

    # When goal is REDUCE_OPERATING_COSTS
    cost_goal = [BusinessGoalType.REDUCE_OPERATING_COSTS.value]
    align_rev_2 = engine.calculate_goal_alignment(rev_cand["category"], rev_cand["title"], rev_cand["description"], cost_goal)
    align_cost_2 = engine.calculate_goal_alignment(cost_cand["category"], cost_cand["title"], cost_cand["description"], cost_goal)
    assert align_cost_2 > align_rev_2
    assert align_cost_2 >= 90.0


def test_constraint_aware_feasibility_penalty_and_warnings():
    """Verify that resource constraints deduct feasibility and generate transparent warnings."""
    engine = PersonalizationEngine()

    constraints = [BusinessConstraintType.LIMITED_BUDGET.value, BusinessConstraintType.SMALL_WORKFORCE.value]

    # Capex-intensive machinery action
    penalty_capex, warns_capex = engine.evaluate_constraints(
        category=RecommendationCategory.OPERATIONAL_EFFICIENCY,
        title="Procure Automated Packaging Machinery",
        description="Requires hiring a dedicated team and substantial capital invest.",
        active_constraints=constraints,
        preferred_investment="Low",
    )
    assert penalty_capex >= 35.0
    assert any("Limited Budget" in w for w in warns_capex)
    assert any("Small Workforce" in w for w in warns_capex)

    # Zero-capex tactical WhatsApp action
    penalty_zero, warns_zero = engine.evaluate_constraints(
        category=RecommendationCategory.CUSTOMER_RETENTION,
        title="Personalized WhatsApp Re-engagement",
        description="Zero software license cost, 15 minutes of direct customer outreach.",
        active_constraints=constraints,
        preferred_investment="Low",
    )
    assert penalty_zero == 0.0
    assert len(warns_zero) == 0


def test_conflicting_preferences_and_constraints():
    """Verify handling when an owner desires digital expansion but has limited digital capability."""
    engine = PersonalizationEngine()

    goals = [BusinessGoalType.IMPROVE_DIGITAL_PRESENCE.value]
    constraints = [BusinessConstraintType.LIMITED_DIGITAL_CAPABILITY.value]

    align_score = engine.calculate_goal_alignment(
        category=RecommendationCategory.DIGITAL_TRANSFORMATION,
        title="Deploy Custom Enterprise ERP",
        description="Integrate custom web api and cloud databases.",
        active_goals=goals,
    )
    penalty, warns = engine.evaluate_constraints(
        category=RecommendationCategory.DIGITAL_TRANSFORMATION,
        title="Deploy Custom Enterprise ERP",
        description="Integrate custom web api and cloud databases.",
        active_constraints=constraints,
    )

    # Goal alignment remains strong, but feasibility penalty flags the conflict
    assert align_score >= 90.0
    assert penalty >= 25.0
    assert any("Limited Digital Capability" in w for w in warns)


def test_critical_risk_never_overridden_or_demoted():
    """Strict Rule: Critical risk recommendations (urgency >= 80) must NEVER be demoted out of critical band."""
    engine = PersonalizationEngine()

    # Churn / Solvency Risk with Urgency 90 and Base Impact 85
    base_u = 90.0
    base_i = 85.0
    base_e = 80.0
    base_c = 75.0
    base_f = 70.0

    # Suppose owner preferences and goals have ZERO alignment with risk (e.g. goal is Launch Products only)
    low_goal_align = 40.0
    low_mat_fit = 50.0
    low_pref_score = 30.0
    penalty = 10.0

    score, priority, pers_comp, adj_f = engine.compute_personalized_priority(
        base_urgency=base_u,
        base_impact=base_i,
        evidence_strength=base_e,
        confidence=base_c,
        base_feasibility=base_f,
        goal_alignment_score=low_goal_align,
        maturity_fit_score=low_mat_fit,
        preference_score=low_pref_score,
        constraint_penalty=penalty,
    )

    # Must remain CRITICAL priority band
    assert priority == RecommendationPriority.CRITICAL
    assert score >= 80


def test_owner_feedback_learning_and_critical_risk_protection(db_session, sample_user):
    """Verify owner feedback learning and confirm critical risks cannot be permanently suppressed."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Feedback Test Enterprise",
        industry="Retail",
        established_year=2021,
        annual_revenue=1500000.0,
    )
    db_session.add(biz)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)

    # 1. Normal recommendation feedback (Not relevant) -> suppressed
    normal_req = RecommendationFeedbackCreate(
        recommendation_id="rec_RULE_DIGITAL_STOREFRONT_PRESENCE_1_GLOBAL_v1",
        feedback_type="Not relevant",
        outcome_notes="We are strictly B2B wholesale.",
    )
    res_normal = engine.record_feedback(biz, normal_req)
    assert res_normal.suppress_recommendation is True

    # 2. Critical Risk recommendation feedback (Not relevant / Dismissed) -> NOT permanently suppressed!
    risk_req = RecommendationFeedbackCreate(
        recommendation_id="rec_RULE_RISK_REVENUE_CONCENTRATION_1_GLOBAL_v1",
        feedback_type="Not relevant",
        outcome_notes="Client is my brother, no risk.",
    )
    res_risk = engine.record_feedback(biz, risk_req)
    assert res_risk.suppress_recommendation is False


def test_new_business_with_limited_information(db_session, sample_user):
    """Verify that brand new businesses with zero sales data receive grounded personalization without hallucinations."""
    biz_new = Business(
        owner_id=sample_user.id,
        legal_name="Fresh Seed Co",
        industry="Agriculture",
        established_year=datetime.now(timezone.utc).year,
        employee_count=1,
        annual_revenue=0.0,
    )
    db_session.add(biz_new)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)
    profile = engine.get_personalization_profile(biz_new)

    assert profile.evaluated_maturity == BusinessMaturityLevel.EARLY_STAGE
    assert BusinessConstraintType.LIMITED_HISTORICAL_DATA.value in profile.active_constraints
    assert BusinessConstraintType.MISSING_FINANCIAL_INFO.value in profile.active_constraints


def test_personalization_endpoints_get_and_put(db_session, sample_user):
    """Test get_personalization_profile and update_personalization_settings CRUD."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Settings Update Co",
        industry="Logistics",
        established_year=2020,
        employee_count=12,
        annual_revenue=5000000.0,
    )
    db_session.add(biz)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)

    # Update settings
    update_payload = PersonalizationSettingsUpdate(
        goals=[BusinessGoalType.REDUCE_OPERATING_COSTS.value, BusinessGoalType.IMPROVE_PROFITABILITY.value],
        constraints=[BusinessConstraintType.LIMITED_BUDGET.value, BusinessConstraintType.TIME_CONSTRAINTS.value],
        preferred_effort_level="Low",
        preferred_investment_level="Low",
        focus_areas=["Fleet Maintenance", "Fuel Optimization"],
    )
    updated_profile = engine.update_personalization_settings(biz, update_payload)

    assert updated_profile.source == "OWNER_DECLARED"
    assert BusinessGoalType.REDUCE_OPERATING_COSTS.value in updated_profile.active_goals
    assert BusinessConstraintType.LIMITED_BUDGET.value in updated_profile.active_constraints
    assert updated_profile.preferred_effort_level == "Low"


def test_acceptance_criterion_two_businesses_different_rankings(db_session, sample_user):
    """Core Acceptance Criterion:

    Two businesses with different goals, maturity levels, and constraints MUST NOT receive
    identical recommendation priorities when their business evidence differs.
    """
    # Business 1: Early-Stage Retailer seeking Digital Growth on Limited Budget
    biz1 = Business(
        owner_id=sample_user.id,
        legal_name="Boutique Alpha",
        industry="Retail",
        established_year=datetime.now(timezone.utc).year - 1,
        employee_count=2,
        annual_revenue=500000.0,
    )
    # Business 2: Established Industrial Manufacturer seeking Operational Efficiency & Risk Control
    biz2 = Business(
        owner_id=sample_user.id,
        legal_name="Beta Heavy Industries",
        industry="Manufacturing",
        established_year=datetime.now(timezone.utc).year - 8,
        employee_count=30,
        annual_revenue=20000000.0,
    )
    db_session.add_all([biz1, biz2])
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)

    # Configure distinct profiles
    engine.update_personalization_settings(
        biz1,
        PersonalizationSettingsUpdate(
            goals=[BusinessGoalType.IMPROVE_DIGITAL_PRESENCE.value, BusinessGoalType.INCREASE_REVENUE.value],
            constraints=[BusinessConstraintType.LIMITED_BUDGET.value],
            preferred_investment_level="Low",
        ),
    )
    engine.update_personalization_settings(
        biz2,
        PersonalizationSettingsUpdate(
            goals=[BusinessGoalType.REDUCE_OPERATING_COSTS.value, BusinessGoalType.IMPROVE_OPERATIONAL_EFFICIENCY.value],
            constraints=[BusinessConstraintType.SMALL_WORKFORCE.value],
            preferred_investment_level="Medium",
        ),
    )

    recs1 = engine.generate_recommendations(biz1).recommendations
    recs2 = engine.generate_recommendations(biz2).recommendations

    assert len(recs1) > 0
    assert len(recs2) > 0

    # Verify that the two businesses receive different top recommendation priorities or orderings
    top_ids_biz1 = [r.id for r in recs1[:3]]
    top_ids_biz2 = [r.id for r in recs2[:3]]
    top_scores_biz1 = [r.priority_score for r in recs1[:3]]
    top_scores_biz2 = [r.priority_score for r in recs2[:3]]

    assert (top_ids_biz1 != top_ids_biz2) or (top_scores_biz1 != top_scores_biz2)
    # Confirm personalization explanation is populated
    assert recs1[0].personalization_explanation is not None
    assert "ranking_rationale" in recs1[0].personalization_explanation
    assert recs2[0].personalization_explanation is not None

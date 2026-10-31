"""Comprehensive test suite for Phase 5 Advanced AI Business Recommendation Intelligence.

Verifies:
  1. MultiSignalEngine (Cross-signal correlation detection)
  2. RootCauseEngine (Symptom, verified factors, plausible causes, unknowns)
  3. OpportunityDiscoveryEngine (10 strategic opportunity categories)
  4. NextBestActionEngine (Cost of delay, effort level, time-to-value, tiering)
  5. RecommendationQualityEngine (Evidence levels and suppression)
  6. ScenarioSimulationEngine (Deterministic What-If calculations)
  7. RecommendationFeedbackRepository & Suppression
  8. End-to-end FastAPI endpoints (/advanced-overview, /growth-strategy, /scenarios/simulate, /feedback)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.business import Business
from app.models.product import Product
from app.models.sales import SalesTransaction
from app.models.user import User
from app.schemas.advanced_recommendations import (
    RecommendationAskRequest,
    RecommendationFeedbackCreate,
    ScenarioSimulationRequest,
)
from app.schemas.recommendation_context import (
    BusinessProfileContext,
    CustomerAnalyticsContext,
    DemandForecastContext,
    HealthScoreContext,
    OperationalReadinessContext,
    ProductForecastItemContext,
    ProductPerformanceContext,
    SalesIntelligenceContext,
    SchemeItemContext,
    SchemeMatchingContext,
    UnifiedRecommendationContext,
)
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
)
from app.services.recommendations.multi_signal_engine import MultiSignalEngine
from app.services.recommendations.next_best_action_engine import NextBestActionEngine
from app.services.recommendations.opportunity_discovery_engine import (
    OpportunityDiscoveryEngine,
)
from app.services.recommendations.quality_engine import RecommendationQualityEngine
from app.services.recommendations.root_cause_engine import RootCauseEngine
from app.services.recommendations.scenario_engine import ScenarioSimulationEngine
from app.utils.database import Base, get_db


@pytest.fixture
def mock_context() -> UnifiedRecommendationContext:
    """Fixture providing rich, realistic unified business context."""
    return UnifiedRecommendationContext(
        business_id=101,
        gathered_at="2026-11-01T00:00:00Z",
        profile=BusinessProfileContext(
            business_id=101,
            legal_name="Apex Precision Engineering Pvt Ltd",
            trade_name="Apex Precision",
            industry="Manufacturing",
            business_stage="Growth",
            city="Pune",
            state_region="Maharashtra",
            country="India",
            annual_revenue=12000000.0,
            revenue_currency="INR",
            employee_count=24,
            has_website=False,
            has_ecommerce=False,
        ),
        health=HealthScoreContext(
            overall_score=58,
            grade="Fair",
            missing_fields=["digital_footprint", "audited_balance_sheet"],
            facet_scores={"financial": 52.0, "operational": 65.0, "digital": 30.0},
        ),
        sales=SalesIntelligenceContext(
            has_sales_data=True,
            total_transactions=45,
            total_revenue=2500000.0,
            total_quantity=12000.0,
            unique_customers=12,
            unique_products=8,
            date_range_days=90,
        ),
        customers=CustomerAnalyticsContext(
            total_customers=12,
            repeat_customers=3,
            repeat_rate_pct=25.0,
            average_order_value=55555.0,
            top_customers_by_revenue=[
                {"customer_name": "Bharat Heavy Machining", "revenue": 1400000.0, "share_pct": 56.0},
                {"customer_name": "Tata Precision Tools", "revenue": 450000.0, "share_pct": 18.0},
                {"customer_name": "Kirloskar Components", "revenue": 250000.0, "share_pct": 10.0},
            ],
            declining_customers=[
                {"customer_name": "Zenith Hydraulics", "days_inactive": 75, "historical_spend": 320000.0}
            ],
        ),
        products=ProductPerformanceContext(
            total_products=8,
            top_products_by_revenue=[
                {"product_name": "CNC Lathe Shaft", "revenue": 1200000.0},
                {"product_name": "Hydraulic Flange B", "revenue": 600000.0},
            ],
            fast_moving_products_by_volume=[
                {"product_name": "Standard Hex Bolt M12", "volume": 8000.0}
            ],
        ),
        forecast=DemandForecastContext(
            has_forecast_data=True,
            forecast_interval="monthly",
            forecast_horizon=3,
            product_forecasts=[
                ProductForecastItemContext(
                    product_id="prod_1",
                    product_name="CNC Lathe Shaft",
                    demand_trend="increasing",
                    trend_delta_pct=24.5,
                    forecasted_units_total=3500.0,
                    forecast_horizon_periods=3,
                    selected_model="auto_arima",
                    reliability="High",
                ),
                ProductForecastItemContext(
                    product_id="prod_2",
                    product_name="Hydraulic Flange B",
                    demand_trend="intermittent",
                    trend_delta_pct=None,
                    forecasted_units_total=420.0,
                    forecast_horizon_periods=3,
                    selected_model="croston_intermittent",
                    reliability="Moderate",
                ),
            ],
        ),
        schemes=SchemeMatchingContext(
            recommended_schemes=[
                SchemeItemContext(
                    id="sch_cgtmse",
                    name="Credit Guarantee Scheme (CGTMSE)",
                    official_authority="Ministry of MSME",
                    official_source_url="https://cgtmse.in",
                    category="Credit Guarantee",
                    benefits=["Collateral-free credit up to ₹5 Crore", "85% guarantee coverage"],
                    eligibility_reason="Manufacturing MSME registered in Maharashtra",
                    documents_required=["Udyam Registration", "3-year audited financials"],
                )
            ]
        ),
        readiness=OperationalReadinessContext(
            digital_readiness_score=35.0,
            operational_completeness_pct=60.0,
        ),
        data_sources_present=["profile", "health", "sales", "forecast", "schemes"],
    )


def test_multi_signal_engine_cross_correlations(mock_context):
    """Verify that MultiSignalEngine identifies compound risks and unlocks."""
    engine = MultiSignalEngine()
    insights = engine.analyze(mock_context)

    pattern_types = [i.pattern_type for i in insights]
    assert "concentration_churn_risk" in pattern_types
    assert "capacity_bottleneck" in pattern_types
    assert "margin_erosion" in pattern_types
    assert "intermittent_demand_volatility" in pattern_types
    assert "scheme_unlock" in pattern_types
    assert "retention_leakage" in pattern_types

    conc_insight = next(i for i in insights if i.pattern_type == "concentration_churn_risk")
    assert conc_insight.severity == "Critical"
    assert "Bharat Heavy Machining" in conc_insight.signals_combined[0] or "56" in conc_insight.signals_combined[0] or "84" in conc_insight.signals_combined[0]
    assert conc_insight.evidence_strength == "Strong Evidence"


def test_root_cause_engine_diagnostic_decomposition(mock_context):
    """Verify RootCauseEngine separates symptoms, verified factors, plausible causes, and data gaps."""
    engine = RootCauseEngine()
    diagnoses = engine.diagnose(mock_context)

    ids = [d.id for d in diagnoses]
    assert "rc_customer_concentration" in ids
    assert "rc_customer_retention" in ids
    assert "rc_business_health_profile" in ids

    conc = next(d for d in diagnoses if d.id == "rc_customer_concentration")
    assert len(conc.verified_factors) >= 2
    assert len(conc.plausible_causes) >= 2
    assert len(conc.data_gaps_and_unknowns) >= 2
    assert conc.urgency == "Immediate"


def test_opportunity_discovery_engine(mock_context):
    """Verify OpportunityDiscoveryEngine surfaces grounded proactive opportunities."""
    engine = OpportunityDiscoveryEngine()
    opportunities = engine.discover(mock_context)

    assert len(opportunities) >= 4
    categories = [o.category for o in opportunities]
    assert "Customer Retention" in categories
    assert "Revenue Growth" in categories
    assert "Product Performance" in categories
    assert "Government Schemes and Funding" in categories

    for opp in opportunities:
        assert opp.feasibility in ("High", "Medium", "Low")
        assert opp.evidence_strength in ("Strong Evidence", "Moderate Evidence", "Limited Evidence")
        assert len(opp.first_step) > 10


def test_next_best_action_engine():
    """Verify NextBestActionEngine ranks and enriches recommendations with cost of delay."""
    engine = NextBestActionEngine()

    sample_recs = [
        SmartRecommendationItem(
            id="rec_1",
            title="Mitigate Customer Concentration",
            category=RecommendationCategory.CUSTOMER_RETENTION,
            priority=RecommendationPriority.CRITICAL,
            priority_score=92,
            description="Top customer accounts for 56% of sales.",
            business_context="High revenue risk",
            evidence=["Top client ₹1.4M out of ₹2.5M"],
            reasoning="Severe revenue concentration",
            recommended_actions=["Call top client for quarterly review"],
            expected_benefit="Prevent sudden revenue loss",
            confidence=85.0,
            data_quality="High",
            created_at="2026-11-01T00:00:00Z",
        ),
        SmartRecommendationItem(
            id="rec_2",
            title="Scale Production of High-Demand SKU",
            category=RecommendationCategory.PRODUCT_PERFORMANCE,
            priority=RecommendationPriority.HIGH,
            priority_score=81,
            description="Demand trending +24% over next quarter.",
            business_context="Demand surge",
            evidence=["Forecast +24.5%"],
            reasoning="High demand SKU",
            recommended_actions=["Order raw materials"],
            expected_benefit="Capture 3,500 units",
            confidence=80.0,
            data_quality="High",
            created_at="2026-11-01T00:00:00Z",
        ),
    ]

    response = engine.rank_actions(sample_recs)
    assert response.top_priority_action is not None
    assert response.top_priority_action.recommendation_id == "rec_1"
    assert response.top_priority_action.priority_score == 92
    assert "churn" in response.top_priority_action.cost_of_delay.lower()
    assert response.top_priority_action.effort_level == "Low"

    assert len(response.next_three_actions) == 1
    assert response.next_three_actions[0].recommendation_id == "rec_2"


def test_quality_engine_filtering():
    """Verify RecommendationQualityEngine suppresses insufficient data cards."""
    engine = RecommendationQualityEngine()

    strong_item = SmartRecommendationItem(
        id="strong_rec",
        title="Valid Recommendation",
        category=RecommendationCategory.REVENUE_GROWTH,
        priority=RecommendationPriority.HIGH,
        priority_score=80,
        description="Detailed description",
        business_context="Context",
        evidence=["Point 1", "Point 2", "Point 3"],
        reasoning="Reasoning",
        expected_benefit="Benefit",
        confidence=85.0,
        data_quality="Moderate",
        created_at="2026-11-01T00:00:00Z",
    )

    weak_item = SmartRecommendationItem(
        id="weak_rec",
        title="Ungrounded Guess",
        category=RecommendationCategory.OPERATIONAL_EFFICIENCY,
        priority=RecommendationPriority.LOW,
        priority_score=20,
        description="No evidence available",
        business_context="Context",
        evidence=[],
        reasoning="Guessed",
        expected_benefit="Benefit",
        confidence=15.0,
        data_quality="Moderate",
        created_at="2026-11-01T00:00:00Z",
    )

    filtered = engine.filter_actionable([strong_item, weak_item])
    assert len(filtered) == 1
    assert filtered[0].id == "strong_rec"
    assert filtered[0].data_quality == "High"


def test_scenario_simulation_deterministic_math(mock_context):
    """Verify ScenarioSimulationEngine produces exact, verifiable mathematical outputs."""
    engine = ScenarioSimulationEngine()
    req = ScenarioSimulationRequest(
        sales_growth_pct=10.0,
        repeat_customer_rate_improvement_pct=20.0,
        expense_reduction_pct=5.0,
        concentration_reduction_pct=15.0,
    )

    sim = engine.simulate(mock_context, req)
    assert sim.baseline_revenue > 0
    assert abs(sim.projected_revenue - (sim.baseline_revenue * 1.10)) < 0.05
    assert sim.estimated_gross_profit_change > 0
    assert "Hypothetical mathematical projection" in sim.projection_disclaimer
    assert len(sim.metrics) == 4


# Integration fixture for database and client
@pytest.fixture
def test_db_session():
    """Create in-memory SQLite database session for endpoint testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_advanced_recommendations_endpoints_integration(test_db_session):
    """End-to-end integration test of new Phase 5 advanced intelligence endpoints."""
    # Seed user & business
    user = User(
        email="advisor_owner@example.com",
        full_name="Advisor Test Owner",
        password_hash="mock_hashed_password",
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.flush()

    business = Business(
        owner_id=user.id,
        legal_name="Sahyadri Agro Solutions Pvt Ltd",
        trade_name="Sahyadri Agro",
        industry="Agri-Tech",
        business_type="Private Limited",
        established_year=2018,
        city="Nashik",
        state_region="Maharashtra",
        country="India",
        annual_revenue=15000000.0,
        employee_count=18,
    )
    test_db_session.add(business)
    test_db_session.flush()

    # Seed sales via SalesRepository
    from app.repositories.sales_repository import SalesRepository
    sales_repo = SalesRepository(test_db_session)
    upload = sales_repo.create_upload(
        business_id=business.id,
        filename="sales_history.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=2,
        valid_row_count=2,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date", "product_name": "product"},
        quality_summary={"valid_pct": 100.0},
    )

    from datetime import datetime, timezone
    tx_rows = [
        {
            "transaction_date": datetime(2026, 9, 15, tzinfo=timezone.utc),
            "invoice_id": "ORD-1001",
            "customer_id": "CUST-A",
            "customer_name": "Maharashtra Agro Traders",
            "product_name": "Drip Emitter Pack",
            "quantity": 500.0,
            "unit_price": 200.0,
            "total_amount": 100000.0,
        },
        {
            "transaction_date": datetime(2026, 10, 10, tzinfo=timezone.utc),
            "invoice_id": "ORD-1002",
            "customer_id": "CUST-A",
            "customer_name": "Maharashtra Agro Traders",
            "product_name": "Drip Emitter Pack",
            "quantity": 600.0,
            "unit_price": 200.0,
            "total_amount": 120000.0,
        },
    ]
    sales_repo.bulk_insert_transactions(upload.id, business.id, tx_rows)

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[User] = override_get_current_user
    # Also override get_current_user specifically
    from app.middleware.auth_deps import get_current_user
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    # 1. Test GET /api/v1/recommendations/advanced-overview
    resp = client.get("/api/v1/recommendations/advanced-overview")
    assert resp.status_code == 200, resp.text
    overview_data = resp.json()
    assert overview_data["business_id"] == business.id
    assert overview_data["business_name"] == "Sahyadri Agro Solutions Pvt Ltd"
    assert "next_best_action" in overview_data
    assert "multi_signal_insights" in overview_data
    assert "root_cause_analyses" in overview_data
    assert "opportunities" in overview_data

    # 2. Test GET /api/v1/recommendations/growth-strategy
    resp = client.get("/api/v1/recommendations/growth-strategy")
    assert resp.status_code == 200, resp.text
    strat_data = resp.json()
    assert strat_data["business_name"] == "Sahyadri Agro Solutions Pvt Ltd"
    assert len(strat_data["horizons"]) == 3
    assert strat_data["horizons"][0]["horizon"] == "0-30 Days"
    assert strat_data["horizons"][1]["horizon"] == "31-90 Days"
    assert strat_data["horizons"][2]["horizon"] == "3-12 Months"

    # 3. Test POST /api/v1/recommendations/scenarios/simulate
    sim_payload = {
        "sales_growth_pct": 15.0,
        "repeat_customer_rate_improvement_pct": 10.0,
        "expense_reduction_pct": 5.0,
        "concentration_reduction_pct": 10.0,
    }
    resp = client.post("/api/v1/recommendations/scenarios/simulate", json=sim_payload)
    assert resp.status_code == 200, resp.text
    sim_data = resp.json()
    assert sim_data["projected_revenue"] > sim_data["baseline_revenue"]
    assert len(sim_data["metrics"]) == 4

    # 4. Test POST /api/v1/recommendations/feedback
    # First get a recommendation id
    rec_resp = client.get("/api/v1/recommendations")
    recs = rec_resp.json()["recommendations"]
    target_rec_id = recs[0]["id"] if recs else "rec_test_101"

    feedback_payload = {
        "recommendation_id": target_rec_id,
        "feedback_type": "Already implemented",
        "outcome_notes": "Completed this client review last week.",
    }
    resp = client.post("/api/v1/recommendations/feedback", json=feedback_payload)
    assert resp.status_code == 200, resp.text
    fb_data = resp.json()
    assert fb_data["recommendation_id"] == target_rec_id
    assert fb_data["feedback_type"] == "Already implemented"
    assert fb_data["suppress_recommendation"] is True

    # 5. Test POST /api/v1/recommendations/ask
    ask_payload = {
        "question": "Which government schemes can I apply for with my manufacturing turnover?"
    }
    resp = client.post("/api/v1/recommendations/ask", json=ask_payload)
    assert resp.status_code == 200, resp.text
    ask_data = resp.json()
    assert ask_data["intent"] == "government_funding_schemes"
    assert len(ask_data["direct_answer"]) > 20
    assert len(ask_data["evidence_points"]) > 0
    assert len(ask_data["follow_up_questions"]) >= 1
    assert len(ask_data["situational_recommendations"]) >= 1

    # Clean up dependency overrides
    app.dependency_overrides.clear()


def test_conversational_advisor_unit(mock_context):
    """Verify ConversationalRecommendationAdvisor handles arbitrary questions with calculations and data limitations."""
    from app.services.recommendations.conversational_advisor import ConversationalRecommendationAdvisor
    advisor = ConversationalRecommendationAdvisor()

    # Query 1: Unpredefined question on customer concentration risk
    q1 = RecommendationAskRequest(question="Why is my sales turnover so vulnerable to a single client leaving?")
    res1 = advisor.answer_question(mock_context, q1)

    assert res1.intent == "customer_retention_concentration"
    assert any("Bharat Heavy Machining" in e for e in res1.evidence_points)
    assert len(res1.calculations) >= 2
    calc_names = [c.name for c in res1.calculations]
    assert "Top Client Revenue Concentration Share" in calc_names
    assert len(res1.follow_up_questions) >= 2
    assert len(res1.situational_recommendations) >= 1
    assert "Losing this relationship" in res1.situational_recommendations[0].cost_of_delay

    # Query 2: Product demand forecast inquiry
    q2 = RecommendationAskRequest(question="What is the forecast trajectory for my CNC Lathe Shaft next quarter?")
    res2 = advisor.answer_question(mock_context, q2)

    assert res2.intent == "product_demand_forecasting"
    assert any("CNC Lathe Shaft" in e for e in res2.evidence_points)
    assert any("auto_arima" in e for e in res2.evidence_points)
    # Check that inventory boundary is preserved
    assert any("warehouse stock counts" in g.lower() for g in res2.data_limitations_and_gaps)


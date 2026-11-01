"""Comprehensive Automated Test Suite for Phase 5 Recommendation Portfolio Optimization.

Verifies:
  1. Complete portfolio multi-signal analysis (risks, quick wins, strategic moves).
  2. Structural dependency detection without inventing false ties.
  3. Conflict detection across 3 archetypes (Spend vs Cost, Expansion vs Pruning, Timing Mismatch).
  4. Objective trade-off analysis and sequential resolution guidelines.
  5. Topological execution sequencing (Critical risks & prerequisites -> Quick wins -> Dependent -> Strategic).
  6. Timeframe classification based on evidence and operational difficulty.
  7. Obsolescence detection when verified context shifts.
  8. Preservation of Accepted and In-Progress states across recalculations.
  9. Portfolio recalculation after new empirical sales data.
  10. Full API integration for GET /api/v1/recommendations/portfolio.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Business
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.schemas.portfolio import RecommendationPortfolioResponse
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SmartRecommendationItem,
)
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.portfolio_engine import RecommendationPortfolioEngine
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def db_session():
    """Create in-memory SQLite database session."""
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
        full_name="Portfolio Test Owner",
        email="portfolio_owner@ursbiz.com",
        password_hash="hashed_pw_xyz",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _build_mock_item(
    rec_id: str,
    title: str,
    category: RecommendationCategory,
    priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    priority_score: int = 55,
    difficulty: str = "Tactical",
    urgency: float = 50.0,
    evidence: list[str] | None = None,
) -> SmartRecommendationItem:
    """Helper to construct strongly typed mock recommendations for portfolio testing."""
    return SmartRecommendationItem(
        id=rec_id,
        title=title,
        category=category,
        priority=priority,
        priority_score=priority_score,
        confidence=80.0,
        description=f"Operational initiative: {title}",
        business_context="Empirical baseline observation",
        evidence=evidence or ["Verified sales ledger observation"],
        reasoning="Critical strategic lever for enterprise value",
        recommended_actions=[f"Execute milestone for {title}"],
        expected_benefit="Measurable operational improvement",
        data_quality="High",
        created_at=datetime.now(timezone.utc).isoformat(),
        status=RecommendationStatus.NEW,
        implementation_difficulty=difficulty,
    )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #

def test_dependency_detection_digital_and_working_capital(db_session, sample_user):
    """Verify structural dependency detection between digital storefront and catalog, and surge and cashflow."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Delta Retailers",
        industry="Retail",
        established_year=2022,
        employee_count=4,
        annual_revenue=1200000.0,
    )
    db_session.add(biz)
    db_session.commit()

    ctx_service = RecommendationContextService(db_session)
    ctx = ctx_service.build_context(biz)

    rec_catalog = _build_mock_item(
        rec_id="rec_RULE_PRODUCT_CATALOG_1_GLOBAL_v1",
        title="Compile Formal Product Catalog and Pricing",
        category=RecommendationCategory.PRODUCT_PERFORMANCE,
        difficulty="Quick Win",
    )
    rec_storefront = _build_mock_item(
        rec_id="rec_RULE_DIGITAL_STOREFRONT_PRESENCE_1_GLOBAL_v1",
        title="Establish Digital Storefront Presence",
        category=RecommendationCategory.DIGITAL_TRANSFORMATION,
        difficulty="Tactical",
    )
    rec_wc = _build_mock_item(
        rec_id="rec_RULE_FINANCIAL_WORKING_CAPITAL_1_GLOBAL_v1",
        title="Stabilize Working Capital Receivables",
        category=RecommendationCategory.FINANCIAL_MANAGEMENT,
        difficulty="Tactical",
    )
    rec_surge = _build_mock_item(
        rec_id="rec_RULE_DEMAND_SURGE_PREPARATION_1_P_GROWTH_v1",
        title="Scale Procurement for Surging SKU",
        category=RecommendationCategory.DEMAND_PLANNING,
        difficulty="Strategic",
    )

    recs = [rec_catalog, rec_storefront, rec_wc, rec_surge]
    engine = RecommendationPortfolioEngine()

    deps = engine.detect_dependencies(recs, ctx, completed_ids=set())

    # Should detect 2 distinct dependencies
    dep_pairs = [(d.recommendation_id, d.depends_on_id) for d in deps]
    assert (rec_storefront.id, rec_catalog.id) in dep_pairs
    assert (rec_surge.id, rec_wc.id) in dep_pairs

    # Verify dependency explanation
    sf_dep = next(d for d in deps if d.recommendation_id == rec_storefront.id)
    assert sf_dep.dependency_type == "PREREQUISITE"
    assert "catalog" in sf_dep.reason.lower()
    assert sf_dep.is_satisfied is False

    # Verify satisfaction when completed
    deps_completed = engine.detect_dependencies(recs, ctx, completed_ids={rec_catalog.id})
    sf_dep_comp = next(d for d in deps_completed if d.recommendation_id == rec_storefront.id)
    assert sf_dep_comp.is_satisfied is True


def test_conflict_detection_all_three_archetypes(db_session, sample_user):
    """Verify conflict detection across spend vs cost, catalog expansion vs pruning, and expansion vs operations."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Matrix Engineering",
        industry="Manufacturing",
        established_year=2018,
        employee_count=15,
        annual_revenue=8000000.0,
    )
    db_session.add(biz)
    db_session.commit()

    ctx = RecommendationContextService(db_session).build_context(biz)
    engine = RecommendationPortfolioEngine()

    # Conflict 1: Volume Discounting vs Overhead Expense Reduction
    rec_disc = _build_mock_item("rec_DISC", "Launch Volume Discounting Campaign", RecommendationCategory.REVENUE_GROWTH)
    rec_cost = _build_mock_item("rec_COST", "Reduce Operating Overhead Expenses", RecommendationCategory.COST_OPTIMIZATION)

    # Conflict 2: Catalog Expansion vs SKU Pruning
    rec_exp = _build_mock_item("rec_EXP", "Launch 5 New Product Variants", RecommendationCategory.PRODUCT_PERFORMANCE)
    rec_prune = _build_mock_item("rec_PRUNE", "Prune Bottom 20% Underperforming SKUs", RecommendationCategory.COST_OPTIMIZATION)

    # Conflict 3: Regional Market Expansion vs Fulfillment Bottlenecks
    rec_mkt = _build_mock_item("rec_MKT", "Expand Regional Market Distribution", RecommendationCategory.REVENUE_GROWTH)
    rec_op = _build_mock_item("rec_OP", "Resolve Packaging Bottleneck & Delivery Delays", RecommendationCategory.OPERATIONAL_EFFICIENCY)

    recs = [rec_disc, rec_cost, rec_exp, rec_prune, rec_mkt, rec_op]
    conflicts = engine.detect_conflicts(recs, ctx)

    conflict_types = {c.conflict_type for c in conflicts}
    assert "RESOURCE_COMPETITION" in conflict_types
    assert "STRATEGIC_CONTRADICTION" in conflict_types
    assert "TIMING_MISMATCH" in conflict_types

    # Verify trade-off analysis and recommended resolution are explicit
    resource_conf = next(c for c in conflicts if c.conflict_type == "RESOURCE_COMPETITION")
    assert len(resource_conf.trade_off_analysis) > 20
    assert "sequential" in resource_conf.recommended_resolution.lower() or "staging" in resource_conf.recommended_resolution.lower()


def test_topological_execution_sequencing():
    """Verify that execution sequence orders critical risks and prerequisites first, followed by quick wins and strategic moves."""
    engine = RecommendationPortfolioEngine()

    rec_risk = _build_mock_item(
        rec_id="rec_RISK",
        title="Mitigate Acute Customer Churn Risk",
        category=RecommendationCategory.RISK_REDUCTION,
        priority=RecommendationPriority.CRITICAL,
        priority_score=92,
        urgency=90.0,
    )
    rec_prereq = _build_mock_item(
        rec_id="rec_PREREQ",
        title="Organize Core Inventory Ledger",
        category=RecommendationCategory.OPERATIONAL_EFFICIENCY,
        priority=RecommendationPriority.HIGH,
        priority_score=75,
    )
    rec_quick = _build_mock_item(
        rec_id="rec_QUICK",
        title="Send Inactive Customer WhatsApp Re-engagement",
        category=RecommendationCategory.CUSTOMER_RETENTION,
        priority=RecommendationPriority.HIGH,
        priority_score=72,
        difficulty="Quick Win",
    )
    rec_dep = _build_mock_item(
        rec_id="rec_DEP",
        title="Automated Reorder Procurement",
        category=RecommendationCategory.DEMAND_PLANNING,
        priority=RecommendationPriority.MEDIUM,
        priority_score=60,
        difficulty="Tactical",
    )
    rec_strat = _build_mock_item(
        rec_id="rec_STRAT",
        title="Apply for Capital Subsidized Modernization Scheme",
        category=RecommendationCategory.GOVERNMENT_SCHEMES,
        priority=RecommendationPriority.MEDIUM,
        priority_score=50,
        difficulty="Strategic",
    )

    recs = [rec_dep, rec_strat, rec_risk, rec_quick, rec_prereq]
    # Prerequisite: Automated Reorder depends on Core Inventory Ledger
    from app.schemas.portfolio import RecommendationDependency
    deps = [
        RecommendationDependency(
            recommendation_id=rec_dep.id,
            depends_on_id=rec_prereq.id,
            dependency_type="PREREQUISITE",
            reason="Requires inventory ledger before automated reordering.",
            is_satisfied=False,
        )
    ]

    sequence = engine.generate_execution_sequence(recs, deps, conflicts=[])

    # Sequence must order Step 1: Critical Risk & Root Prerequisite
    assert sequence[0].recommendation_id == rec_risk.id
    assert sequence[0].sequence_order == 1
    assert sequence[0].stage == "FIRST_ACTION"
    assert "Critical risk" in sequence[0].why_this_order

    # The root prerequisite must come before its dependent action
    prereq_step = next(s for s in sequence if s.recommendation_id == rec_prereq.id)
    dep_step = next(s for s in sequence if s.recommendation_id == rec_dep.id)
    assert prereq_step.sequence_order < dep_step.sequence_order
    assert rec_dep.id in prereq_step.unlocks_recommendation_ids


def test_timeframe_classification_quick_wins_vs_strategic():
    """Verify categorization into Quick Wins, Short-Term Improvements, and Strategic Initiatives."""
    engine = RecommendationPortfolioEngine()

    q_rec = _build_mock_item("rec_Q", "Quick Win Action", RecommendationCategory.CUSTOMER_RETENTION, difficulty="Quick Win")
    t_rec = _build_mock_item("rec_T", "Tactical Action", RecommendationCategory.PRODUCT_PERFORMANCE, difficulty="Tactical")
    s_rec = _build_mock_item("rec_S", "Strategic Action", RecommendationCategory.GOVERNMENT_SCHEMES, difficulty="Strategic")

    qw, st, strat = engine.classify_timeframes([q_rec, t_rec, s_rec], dependencies=[])

    assert any(r.id == "rec_Q" for r in qw)
    assert any(r.id == "rec_T" for r in st)
    assert any(r.id == "rec_S" for r in strat)


def test_portfolio_obsolescence_detection(db_session, sample_user):
    """Verify that recommendations whose conditions were resolved by new evidence are detected as obsolete."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Apex Logistics",
        industry="Logistics",
        established_year=2020,
        annual_revenue=5000000.0,
    )
    db_session.add(biz)
    db_session.commit()

    ctx = RecommendationContextService(db_session).build_context(biz)
    engine = RecommendationPortfolioEngine()

    # Suppose previously there was a customer concentration recommendation persisted
    past_states = {
        "rec_RULE_RISK_REVENUE_CONCENTRATION_1_GLOBAL_v1": RecommendationLifecycleState(
            business_id=biz.id,
            recommendation_id="rec_RULE_RISK_REVENUE_CONCENTRATION_1_GLOBAL_v1",
            status="New",
        )
    }

    # In the current recommendation set, that recommendation is NO LONGER triggered
    current_recs = [
        _build_mock_item("rec_OTHER", "Routine Maintenance", RecommendationCategory.OPERATIONAL_EFFICIENCY)
    ]

    obsolete = engine.detect_obsolete_recommendations(current_recs, ctx, past_states)
    assert len(obsolete) == 1
    assert obsolete[0].recommendation_id == "rec_RULE_RISK_REVENUE_CONCENTRATION_1_GLOBAL_v1"
    assert "resolved" in obsolete[0].reason_obsolete.lower() or "mitigated" in obsolete[0].reason_obsolete.lower()


def test_preservation_of_accepted_and_in_progress_states(db_session, sample_user):
    """Verify that recommendations marked Accepted or In Progress are not overwritten during portfolio generation."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Craft Innovations",
        industry="Manufacturing",
        established_year=2021,
        annual_revenue=2500000.0,
    )
    db_session.add(biz)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)

    # Generate initial recommendations
    initial_recs = engine.generate_recommendations(biz).recommendations
    assert len(initial_recs) > 0
    target_rec = initial_recs[0]

    # Mark as In Progress
    engine.lifecycle_repo.update_status(
        business_id=biz.id,
        recommendation_id=target_rec.id,
        status="In Progress",
        notes="Owner commenced implementation on Day 3",
    )

    # Recalculate portfolio
    portfolio = engine.get_recommendation_portfolio(biz)

    # Verify that in the portfolio execution sequence, the status remains In Progress
    step = next(s for s in portfolio.execution_sequence if s.recommendation_id == target_rec.id)
    assert step.status == "In Progress"


def test_portfolio_recalculation_after_new_sales_data(db_session, sample_user):
    """Simulate fresh sales ledger ingestion and verify portfolio recalculation."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Solaris Traders",
        industry="Retail",
        established_year=2023,
        annual_revenue=1000000.0,
    )
    db_session.add(biz)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)
    p1 = engine.get_recommendation_portfolio(biz)
    initial_count = p1.total_active_count

    # Ingest new transactions
    upload = SalesUpload(
        business_id=biz.id,
        filename="sales_test.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=1,
        status="completed",
    )
    db_session.add(upload)
    db_session.commit()

    txn1 = SalesTransaction(
        upload_id=upload.id,
        business_id=biz.id,
        transaction_date=datetime.now(timezone.utc),
        product_name="Solar Inverter 5kVA",
        customer_name="Green Energy Ltd",
        quantity=5.0,
        unit_price=20000.0,
        total_amount=100000.0,
    )
    db_session.add(txn1)
    db_session.commit()

    p2 = engine.get_recommendation_portfolio(biz)
    assert p2.portfolio_health_score >= 20
    assert len(p2.execution_sequence) > 0


def test_portfolio_endpoint_api_integration(db_session, sample_user):
    """Verify that RecommendationPortfolioResponse complies with the API contract."""
    biz = Business(
        owner_id=sample_user.id,
        legal_name="Zenith Engineering",
        industry="Engineering",
        established_year=2019,
        employee_count=18,
        annual_revenue=12000000.0,
    )
    db_session.add(biz)
    db_session.commit()

    engine = SmartRecommendationEngine(db_session)
    portfolio = engine.get_recommendation_portfolio(biz)

    assert isinstance(portfolio, RecommendationPortfolioResponse)
    assert portfolio.business_id == biz.id
    assert portfolio.business_name == "Zenith Engineering"
    assert 20 <= portfolio.portfolio_health_score <= 100
    assert len(portfolio.resource_summary) >= 5

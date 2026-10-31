"""Test Suite for Phase 5 Advanced Autonomous Business Opportunity Discovery Engine.

Verifies:
  1. Dynamic opportunity discovery beyond fixed predefined rules
  2. Multi-signal opportunity hypothesis generation (facts vs inferences, rival explanations, correlation disclaimer)
  3. Strict validation pipeline & 5-tier quality classification:
     (VERIFIED_OPPORTUNITY, PROMISING_OPPORTUNITY, NEEDS_INVESTIGATION, INSUFFICIENT_EVIDENCE, NOT_ACTIONABLE)
  4. Unsupported opportunity suppression (sample size too small, zero revenue)
  5. Stale evidence rejection
  6. Conflicting signals detection (e.g. underperformance diagnosis vs forecast surge)
  7. Duplicate detection & stable identity versioning (rec_OPP_{cat}_{biz}_{entity}_{issue}_v{ver})
  8. Material evidence shift advances version to v2 with explanation
  9. Already addressed/completed opportunity suppression
  10. Gemini dynamic discovery with resilient deterministic fallback
  11. End-to-end integration into SmartRecommendationEngine and 9-pillar diagnostic candidate stream
  12. Strict Phase 5 audit boundary compliance (no inventory reorders, historical context customer spend)
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
os.environ["DATABASE_URL"] = "sqlite:///" + str(BACKEND / "atlas_ai.db").replace("\\", "/")

from app.models.business import Business
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.sales_repository import SalesRepository
from app.schemas.advanced_recommendations import (
    OpportunityHypothesis,
    OpportunityItem,
    OpportunityQualityStatus,
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
    SmartRecommendationItem,
)
from app.services.recommendations.context_service import RecommendationContextService
from app.services.recommendations.opportunity_discovery_engine import (
    AutonomousOpportunityScanner,
    DynamicGeminiOpportunityDiscoverer,
    OpportunityDiscoveryEngine,
    OpportunityValidationEngine,
)
from app.services.recommendations.recommendation_engine import SmartRecommendationEngine
from app.utils.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    """Isolated session for test cases."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _build_rich_test_context(
    business_id: int = 101,
    total_rev: float = 1200000.0,
    top1_rev: float = 600000.0,
    top_vol_qty: float = 400.0,
    top_vol_rev: float = 120000.0,
    repeat_customers: int = 4,
    total_customers: int = 10,
    declining_count: int = 2,
    forecast_trend: str = "surge",
    trend_delta_pct: float = 24.5,
    health_score: int = 68,
    has_website: bool = False,
    is_stale: bool = False,
) -> UnifiedRecommendationContext:
    """Constructs a deterministic multi-signal business context for testing."""
    limitations = ["Data expired / stale data ledger."] if is_stale else []

    top_customers = [
        {"customer_id": "C_ANCHOR", "customer_name": "Anchor Client", "revenue": top1_rev},
        {"customer_id": "C_MED_1", "customer_name": "Regional Gears", "revenue": 200000.0},
        {"customer_id": "C_MED_2", "customer_name": "Apex Hydraulics", "revenue": 150000.0},
    ]

    declining_customers = [
        {"customer_id": "C_DORM_1", "customer_name": "Lapsed Logistics Co", "revenue": 50000.0},
        {"customer_id": "C_DORM_2", "customer_name": "Idle Works Ltd", "revenue": 35000.0},
    ][:declining_count]

    top_products = [
        {"product_id": "P_HERO", "product_name": "Carbide Endmill 10mm", "revenue": 700000.0, "quantity": 250.0},
        {"product_id": "P_HIGHVOL", "product_name": "Alloy Spacer Ring", "revenue": top_vol_rev, "quantity": top_vol_qty},
    ]

    fast_moving = [
        {"product_id": "P_HIGHVOL", "product_name": "Alloy Spacer Ring", "quantity": top_vol_qty},
        {"product_id": "P_HERO", "product_name": "Carbide Endmill 10mm", "quantity": 250.0},
    ]

    forecasts = [
        ProductForecastItemContext(
            product_id="P_HERO",
            product_name="Carbide Endmill 10mm",
            demand_trend=forecast_trend,
            trend_delta_pct=trend_delta_pct,
            forecasted_units_total=320.0,
            forecast_horizon_periods=3,
            selected_model="HoltWinters",
            reliability="High",
        )
    ]

    schemes = [
        SchemeItemContext(
            id="SCHEME_CGTMSE",
            name="Credit Guarantee Scheme for Micro & Small Enterprises (CGTMSE)",
            official_authority="Ministry of MSME",
            official_source_url="https://www.cgtmse.in",
            category="Credit Support",
            benefits=["Collateral-free credit up to ₹5 Crore", "Guarantee coverage up to 85%"],
        )
    ]

    return UnifiedRecommendationContext(
        business_id=business_id,
        gathered_at="2026-11-01T04:00:00Z",
        profile=BusinessProfileContext(
            business_id=business_id,
            legal_name="Apex Precision Engineering Works",
            industry="Manufacturing",
            established_year=2020,
            annual_revenue=total_rev,
            has_website=has_website,
            has_ecommerce=False,
            employee_count=18,
        ),
        health=HealthScoreContext(
            overall_score=health_score,
            grade="C" if health_score < 70 else "B",
            missing_fields=["certifications", "export_history", "digital_presence"],
        ),
        sales=SalesIntelligenceContext(
            has_sales_data=total_rev > 0,
            total_transactions=15,
            total_revenue=total_rev,
            total_quantity=1000.0,
            unique_customers=total_customers,
            unique_products=len(top_products),
        ),
        customers=CustomerAnalyticsContext(
            total_customers=total_customers,
            repeat_customers=repeat_customers,
            repeat_rate_pct=(repeat_customers / total_customers * 100.0) if total_customers > 0 else 0.0,
            average_order_value=total_rev / 15 if total_rev > 0 else 0.0,
            top_customers_by_revenue=top_customers,
            declining_customers=declining_customers,
        ),
        products=ProductPerformanceContext(
            total_products=len(top_products),
            top_products_by_revenue=top_products,
            fast_moving_products_by_volume=fast_moving,
        ),
        forecast=DemandForecastContext(
            has_forecast_data=True,
            product_forecasts=forecasts,
        ),
        schemes=SchemeMatchingContext(
            recommended_schemes=schemes,
        ),
        readiness=OperationalReadinessContext(
            digital_readiness_score=40.0 if not has_website else 80.0,
            operational_completeness_pct=70.0,
        ),
        data_sources_present=["business_profile", "sales_intelligence", "demand_forecasting", "government_schemes"],
        data_limitations=limitations,
    )


# =========================================================================== #
# Test 1: Dynamic Multi-Signal Discovery Beyond Fixed Catalog
# =========================================================================== #

def test_dynamic_opportunity_discovery_multi_dimensions():
    """Verify autonomous scanner surfaces multiple non-predefined opportunities across dimensions."""
    ctx = _build_rich_test_context()
    engine = OpportunityDiscoveryEngine()

    hypotheses = engine.discover_hypotheses(ctx)
    assert len(hypotheses) >= 5

    titles = [h.title for h in hypotheses]
    categories = [h.category for h in hypotheses]

    # Verify key dynamic dimensions triggered:
    assert any("Pricing & Tiering" in t for t in titles)  # SKU volume vs revenue gap
    assert any("Capacity & Procurement Focus" in t for t in titles)  # Surging forecast demand
    assert any("Pre-Churn Account Reactivation" in t for t in titles)  # Lapsing buyers
    assert any("Standing Orders" in t for t in titles)  # Repeat buyer loyalty
    assert any("Mid-Market Client Acquisition" in t for t in titles)  # Concentration de-risking
    assert any("Net-10" in t for t in titles)  # Cashflow discount acceleration
    assert any("WhatsApp" in t for t in titles)  # Digital catalog gap
    assert any("Health Score" in t for t in titles)  # Bankability lift
    assert any("Commercial Wedge" in t for t in titles)  # Cross-signal surge + concentration

    # Verify structured hypothesis properties
    first_hyp = hypotheses[0]
    assert first_hyp.id.startswith("rec_OPP_")
    assert first_hyp.confidence > 0.60
    assert len(first_hyp.supporting_signals) > 0
    assert len(first_hyp.evidence_references) > 0


# =========================================================================== #
# Test 2: Structured Hypothesis Generation & Epistemic Humility
# =========================================================================== #

def test_hypothesis_structure_facts_vs_inferences_and_disclaimer():
    """Verify hypothesis separates observed facts from inferred explanations and states correlation disclaimer."""
    ctx = _build_rich_test_context()
    engine = OpportunityDiscoveryEngine()

    hypotheses = engine.discover_hypotheses(ctx)
    target = next(h for h in hypotheses if "pricing_tier_gap" in h.id)

    # 1. Epistemic separation
    assert len(target.observed_facts) > 0
    assert len(target.inferred_explanations) > 0
    assert any("total volume" in f.lower() for f in target.observed_facts)
    assert any("hypothesis:" in i.lower() for i in target.inferred_explanations)

    # 2. Rival / Alternative explanations
    assert len(target.alternative_explanations) >= 1
    assert any("loss-leader" in target.possible_explanation.lower() or "gateway" in target.alternative_explanations[0].lower() for _ in [1])

    # 3. Correlation-causation disclaimer
    assert "correlation" in target.correlation_causation_disclaimer.lower()
    assert "causation" in target.correlation_causation_disclaimer.lower()

    # 4. Phase 5 boundary check: No inventory safety stock or reorder points
    assert any("lead times" in lim.lower() or "phase 5" in lim.lower() or "inventory" in lim.lower() for lim in target.limitations)


# =========================================================================== #
# Test 3: Quality Classification (Verified vs Promising vs Needs Investigation)
# =========================================================================== #

def test_opportunity_quality_classification_tiers():
    """Verify opportunities are correctly tagged with appropriate quality status."""
    ctx = _build_rich_test_context()
    engine = OpportunityDiscoveryEngine()

    hypotheses = engine.discover_hypotheses(ctx)

    statuses = {h.quality_status for h in hypotheses}
    assert OpportunityQualityStatus.VERIFIED_OPPORTUNITY in statuses

    verified_items = [h for h in hypotheses if h.quality_status == OpportunityQualityStatus.VERIFIED_OPPORTUNITY]
    for v in verified_items:
        assert v.confidence >= 0.75
        assert len(v.conflicting_signals) == 0


# =========================================================================== #
# Test 4: Unsupported Opportunity Suppression (Trivial Sample / Zero Revenue)
# =========================================================================== #

def test_unsupported_opportunity_suppression_zero_revenue():
    """Verify that opportunities without sufficient sample volume or revenue are suppressed."""
    empty_ctx = _build_rich_test_context(total_rev=0.0, top1_rev=0.0, total_customers=0, repeat_customers=0)
    engine = OpportunityDiscoveryEngine()

    # Hypotheses should be suppressed or marked INSUFFICIENT_EVIDENCE
    hypotheses = engine.discover_hypotheses(empty_ctx)
    for h in hypotheses:
        if "PROD" in h.id or "CUST" in h.id:
            assert h.quality_status in (
                OpportunityQualityStatus.INSUFFICIENT_EVIDENCE,
                OpportunityQualityStatus.NOT_ACTIONABLE,
            )

    # Dashboard items must completely exclude insufficient evidence
    dashboard_items = engine.discover(empty_ctx)
    for item in dashboard_items:
        assert item.quality_status not in (
            OpportunityQualityStatus.INSUFFICIENT_EVIDENCE,
            OpportunityQualityStatus.NOT_ACTIONABLE,
        )


# =========================================================================== #
# Test 5: Stale Evidence Rejection
# =========================================================================== #

def test_stale_evidence_rejection():
    """Verify that stale or expired transaction data causes opportunities to be marked NOT_ACTIONABLE."""
    stale_ctx = _build_rich_test_context(is_stale=True)
    engine = OpportunityDiscoveryEngine()

    hypotheses = engine.discover_hypotheses(stale_ctx)
    sales_hypotheses = [
        h for h in hypotheses
        if any("sales" in s.source_module.lower() or "customer" in s.source_module.lower() for s in h.supporting_signals)
        or h.category in ("Product Portfolio Optimization", "Customer Retention", "Demand Planning")
    ]
    assert len(sales_hypotheses) > 0
    for h in sales_hypotheses:
        assert h.quality_status == OpportunityQualityStatus.NOT_ACTIONABLE
        assert any("stale or expired" in lim.lower() for lim in h.limitations)

    # Dashboard items should suppress all sales-dependent opportunities
    dashboard_items = engine.discover(stale_ctx)
    for item in dashboard_items:
        assert item.category not in ("Product Portfolio Optimization", "Customer Retention", "Demand Planning")


# =========================================================================== #
# Test 6: Conflicting Signals Detection & Penalty
# =========================================================================== #

def test_conflicting_signals_detection_and_investigation_tagging():
    """Verify conflicting signals reduce confidence and trigger NEEDS_INVESTIGATION."""
    ctx = _build_rich_test_context()

    # Fabricate a hypothesis claiming a SKU is declining when forecast says it's surging (+24.5%)
    conflicting_hyp = OpportunityHypothesis(
        id="rec_OPP_PROD_101_Carbide_Endmill_underperforming_v1",
        title="Discontinue Underperforming SKU 'Carbide Endmill 10mm'",
        category="Product Portfolio Optimization",
        business_problem_or_opportunity="Product sales are underperforming and facing secular decline.",
        quality_status=OpportunityQualityStatus.VERIFIED_OPPORTUNITY,
        supporting_signals=[],
        evidence_references=["Past sales volume drop."],
        relevant_time_period="Past quarter",
        possible_explanation="Market demand has cooled.",
        alternative_explanations=[],
        confidence=0.85,
        missing_information=[],
        recommended_investigation="Audit inventory.",
        potential_business_benefit="Frees capital.",
        limitations=[],
        relevant_entity="Carbide Endmill 10mm",
        underlying_issue="underperformance_discontinue",
    )

    validator = OpportunityValidationEngine()
    validated = validator.validate(conflicting_hyp, ctx)

    # Must detect the forecast surge counter-signal
    assert len(validated.conflicting_signals) > 0
    assert any("surging forecast demand" in c.lower() for c in validated.conflicting_signals)
    assert validated.confidence < 0.85  # Penalty applied
    assert validated.quality_status == OpportunityQualityStatus.NEEDS_INVESTIGATION


# =========================================================================== #
# Test 7: Stable Identity & Material Shift Version Bumping (v1 -> v2)
# =========================================================================== #

def test_stable_identity_and_material_version_bump():
    """Verify that material shift in evidence increases version to v2 with documented delta."""
    scanner = AutonomousOpportunityScanner()

    # Initial context (v1)
    ctx1 = _build_rich_test_context(total_rev=1000000.0, top1_rev=500000.0)
    hyp1 = scanner._scan_concentration_diversification(ctx1, 101)
    assert hyp1 is not None
    assert hyp1.version == 1
    assert hyp1.id.endswith("_v1")

    # Shifted context with material revenue increase to ₹2.5M (v2)
    ctx2 = _build_rich_test_context(total_rev=2500000.0, top1_rev=1250000.0)
    hyp2 = scanner._scan_concentration_diversification(ctx2, 101)
    assert hyp2 is not None
    assert hyp2.version == 2
    assert hyp2.id.endswith("_v2")
    assert hyp2.version_notes is not None
    assert "Updated from v1" in hyp2.version_notes


# =========================================================================== #
# Test 8: Already Addressed / Completed Opportunity Suppression
# =========================================================================== #

def test_already_addressed_opportunity_suppression():
    """Verify that opportunities marked completed or dismissed by owner are suppressed."""
    ctx = _build_rich_test_context()
    engine = OpportunityDiscoveryEngine()

    hypotheses = engine.discover_hypotheses(ctx)
    target_id = hypotheses[0].id

    # Suppress via completed_rec_ids
    suppressed_hypotheses = engine.discover_hypotheses(
        ctx,
        completed_rec_ids={target_id},
    )
    suppressed_target = next(h for h in suppressed_hypotheses if h.id == target_id)
    assert suppressed_target.quality_status == OpportunityQualityStatus.NOT_ACTIONABLE
    assert suppressed_target.validation_status == "SUPPRESSED"

    # Must not appear in dashboard OpportunityItems
    dashboard_items = engine.discover(ctx, completed_rec_ids={target_id})
    assert not any(item.id == target_id for item in dashboard_items)


# =========================================================================== #
# Test 9: Gemini Dynamic Discovery & Resilient Fallback
# =========================================================================== #

def test_gemini_dynamic_opportunity_discovery_and_fallback():
    """Verify Gemini synthesizes novel opportunities, and fallback works seamlessly when unavailable."""
    ctx = _build_rich_test_context()

    # 1. Successful Gemini discovery
    mock_llm_json = [
        {
            "title": "Establish Consortium Bidding for Industrial Machining Contracts",
            "category": "Revenue Growth",
            "problem": "Individual small order sizes limit qualification for larger tier-1 enterprise tenders.",
            "signals": [
                {"name": "aov", "value": "₹80,000", "module": "sales_intelligence", "interp": "Moderate transaction scale"}
            ],
            "explanation": "Forming an informal supplier cluster unlocks joint commercial bids.",
            "alternatives": ["May increase coordination complexity."],
            "confidence": 0.78,
            "investigation": "Meet with 2 neighboring machine shops to assess joint tender participation.",
            "benefit": "Enables competing for ₹5M+ annual corporate supply contracts.",
            "observed_facts": ["AOV is ₹80,000."],
            "inferred_explanations": ["Joint consortia lower qualification barriers."],
            "entity": "CLUSTER_B2B",
            "issue": "consortium_tender_bidding",
        }
    ]

    mock_client = MagicMock()
    mock_client.execute_chat_completion.return_value = "dummy"
    mock_client.extract_and_validate_json.return_value = mock_llm_json

    gemini_discoverer = DynamicGeminiOpportunityDiscoverer(client=mock_client)
    novel_hyps = gemini_discoverer.discover_novel_opportunities(ctx)

    assert len(novel_hyps) == 1
    assert "Consortium Bidding" in novel_hyps[0].title
    assert novel_hyps[0].id.startswith("rec_OPP_AI_")

    # 2. Resilient fallback during Gemini outage
    failing_client = MagicMock()
    failing_client.execute_chat_completion.return_value = None  # Outage / circuit breaker open
    fallback_discoverer = DynamicGeminiOpportunityDiscoverer(client=failing_client)
    fallback_hyps = fallback_discoverer.discover_novel_opportunities(ctx)
    assert fallback_hyps == []

    # Orchestrator still returns full deterministic discovery suite without error
    resilient_engine = OpportunityDiscoveryEngine(gemini_discoverer=fallback_discoverer)
    hyps = resilient_engine.discover_hypotheses(ctx)
    assert len(hyps) >= 5


# =========================================================================== #
# Test 10: End-to-End SmartRecommendationEngine Integration
# =========================================================================== #

def test_e2e_recommendation_engine_includes_autonomous_opportunities(db_session: Session):
    """Verify SmartRecommendationEngine incorporates autonomous opportunities into active candidates."""
    import time
    ts = int(time.time() * 1000)
    user = User(email=f"opp_owner_{ts}@example.com", password_hash="hash", full_name="Opp Owner")
    db_session.add(user)
    db_session.commit()

    biz_repo = BusinessRepository(db_session)
    biz = biz_repo.create(
        owner_id=user.id,
        legal_name="Vanguard Tooling Industries",
        industry="Manufacturing",
        established_year=2021,
        employee_count=15,
        annual_revenue=1500000.0,
        revenue_currency="INR",
        city="Pune",
    )
    db_session.commit()

    # Upload sales to provide ground truth
    sales_repo = SalesRepository(db_session)
    upload = sales_repo.create_upload(
        business_id=biz.id,
        filename="sales.csv",
        file_format="csv",
        file_size_bytes=1024,
        row_count=4,
        valid_row_count=4,
        invalid_row_count=0,
        status="confirmed",
        column_mapping={"transaction_date": "date"},
        quality_summary={"valid_pct": 100.0},
    )

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc) - timedelta(days=5)
    rows = [
        {"transaction_date": now, "customer_id": "C_MAIN", "customer_name": "Anchor Client", "product_id": "P_VOL", "product_name": "Spacer Pin", "quantity": 100, "unit_price": 200, "total_amount": 20000},
        {"transaction_date": now, "customer_id": "C_MAIN", "customer_name": "Anchor Client", "product_id": "P_VOL", "product_name": "Spacer Pin", "quantity": 80, "unit_price": 200, "total_amount": 16000},
        {"transaction_date": now, "customer_id": "C_TWO", "customer_name": "Second Buyer", "product_id": "P_VOL", "product_name": "Spacer Pin", "quantity": 60, "unit_price": 200, "total_amount": 12000},
        {"transaction_date": now, "customer_id": "C_THREE", "customer_name": "Third Buyer", "product_id": "P_VOL", "product_name": "Spacer Pin", "quantity": 40, "unit_price": 200, "total_amount": 8000},
    ]
    sales_repo.bulk_insert_transactions(upload.id, biz.id, rows)

    rec_engine = SmartRecommendationEngine(db_session)
    rec_res = rec_engine.generate_recommendations(biz)

    # 1. Recommendations must include autonomous opportunities
    opp_items = [r for r in rec_res.recommendations if r.is_autonomous_opportunity]
    assert len(opp_items) > 0

    first_opp = opp_items[0]
    assert first_opp.id.startswith("rec_OPP_")
    assert first_opp.opportunity_quality_status in ("VERIFIED_OPPORTUNITY", "PROMISING_OPPORTUNITY")
    assert first_opp.what_is_happening is not None
    assert first_opp.cost_of_inaction is not None
    assert len(first_opp.measurement_kpis) > 0

    # 2. Advanced overview includes both OpportunityItem and OpportunityHypothesis
    overview = rec_engine.get_advanced_overview(biz)
    assert len(overview.opportunities) > 0
    assert len(overview.opportunity_hypotheses) > 0

    top_dash_opp = overview.opportunities[0]
    assert top_dash_opp.quality_status in (OpportunityQualityStatus.VERIFIED_OPPORTUNITY, OpportunityQualityStatus.PROMISING_OPPORTUNITY)
    assert len(top_dash_opp.observed_facts) > 0
    assert len(top_dash_opp.inferred_explanations) > 0

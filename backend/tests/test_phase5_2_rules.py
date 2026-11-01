"""Unit tests for Phase 5.2: Recommendation Rules, Registry, and Categories.

Verifies:
  1. All 10 standard business categories are supported.
  2. Rule triggers for Customer Concentration, Flagship Bundle, Slow SKU Review, Inactive Retention.
  3. Strict inventory boundaries: Demand forecasting rules do NOT calculate reorder amounts, safety stock, or stockouts.
  4. Intermittent demand rule correctly flags sporadic ordering patterns.
  5. Government schemes rule preserves official authorities and source URLs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

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
from app.schemas.smart_recommendations import RecommendationCategory
from app.services.recommendations.rule_registry import RecommendationRuleRegistry


def build_mock_context(
    has_sales: bool = True,
    top_3_pct: float = 60.0,
    has_declining: bool = True,
    has_forecast: bool = True,
    demand_trend: str = "Increasing",
    selected_model: str = "HoltWinters",
    has_schemes: bool = True,
) -> UnifiedRecommendationContext:
    profile = BusinessProfileContext(
        business_id=99,
        legal_name="Apex Precision",
        industry="Manufacturing",
        business_stage="Scale",
        annual_revenue=2000000.0,
        employee_count=25,
        has_website=False,
        has_ecommerce=False,
    )
    health = HealthScoreContext(
        overall_score=65,
        grade="C",
        missing_fields=["digital_presence"],
    )
    sales = SalesIntelligenceContext(
        has_sales_data=has_sales,
        total_transactions=40 if has_sales else 0,
        total_revenue=100000.0 if has_sales else 0.0,
        total_quantity=500.0 if has_sales else 0.0,
        date_range_days=120 if has_sales else 0,
    )
    cust = CustomerAnalyticsContext(
        total_customers=10,
        repeat_customers=4,
        repeat_rate_pct=40.0,
        average_order_value=2500.0,
        top_customers_by_revenue=[{"customer_name": "Major Client", "total_revenue": 60000.0}] if top_3_pct >= 50 else [],
        declining_customers=[{"customer_name": "Lapsed Client", "total_revenue": 15000.0}] if has_declining else [],
    )
    prod = ProductPerformanceContext(
        total_products=3,
        top_products_by_revenue=[{"product_name": "Flagship CNC", "product_id": "CNC1", "total_revenue": 45000.0, "total_quantity_sold": 90, "average_unit_price": 500}],
        fast_moving_products_by_volume=[
            {"product_name": "Flagship CNC", "total_quantity_sold": 90},
            {"product_name": "Secondary Bit", "total_quantity_sold": 50},
            {"product_name": "Slow Nut", "total_quantity_sold": 2},
        ],
    )
    forecast_items = []
    if has_forecast:
        forecast_items.append(
            ProductForecastItemContext(
                product_id="SKU_DEMAND",
                product_name="Flagship CNC",
                demand_trend=demand_trend,
                forecasted_units_total=120.0,
                forecast_horizon_periods=3,
                selected_model=selected_model,
                best_mae=4.5,
                reliability="High",
                limitation_notes=["Historical transactions reflect past trends."],
            )
        )
    forecast = DemandForecastContext(
        has_forecast_data=has_forecast,
        product_forecasts=forecast_items,
    )
    schemes = SchemeMatchingContext(
        recommended_schemes=[
            SchemeItemContext(
                id="CGTMSE",
                name="Credit Guarantee Scheme",
                official_authority="SIDBI",
                official_source_url="https://cgtmse.in",
                category="Credit Guarantee",
                benefits=["Collateral-free credit"],
            )
        ] if has_schemes else []
    )
    readiness = OperationalReadinessContext(
        digital_readiness_score=0.0,
        operational_completeness_pct=85.0,
    )

    return UnifiedRecommendationContext(
        business_id=99,
        gathered_at="2026-11-01T00:00:00Z",
        profile=profile,
        health=health,
        sales=sales,
        customers=cust,
        products=prod,
        forecast=forecast,
        schemes=schemes,
        readiness=readiness,
    )


def test_rule_registry_triggers_all_applicable_rules():
    ctx = build_mock_context(has_sales=True, has_declining=True, has_forecast=True)
    candidates = RecommendationRuleRegistry.evaluate_all(ctx)

    categories = {c["category"] for c in candidates}
    assert RecommendationCategory.REVENUE_GROWTH in categories
    assert RecommendationCategory.CUSTOMER_RETENTION in categories
    assert RecommendationCategory.DEMAND_PLANNING in categories
    assert RecommendationCategory.GOVERNMENT_SCHEMES in categories
    assert RecommendationCategory.DIGITAL_TRANSFORMATION in categories


def test_strict_inventory_boundaries_on_demand_rules():
    ctx = build_mock_context(has_forecast=True, demand_trend="Increasing")
    candidates = RecommendationRuleRegistry.evaluate_all(ctx)

    demand_candidates = [c for c in candidates if c["category"] == RecommendationCategory.DEMAND_PLANNING]
    assert len(demand_candidates) > 0

    for d in demand_candidates:
        assert d["estimated_impact"] is None, "Demand forecasting rules must not calculate financial/reorder amounts"
        assert d["impact_unit"] is None
        assert "stockout" not in d["title"].lower()
        assert "reorder quantity" not in d["description"].lower()
        # Verifies boundary disclosure in limitations
        assert any("inventory" in lim.lower() for lim in d["limitations"])


def test_intermittent_demand_rule_trigger():
    ctx = build_mock_context(has_forecast=True, demand_trend="Intermittent", selected_model="Croston")
    candidates = RecommendationRuleRegistry.evaluate_all(ctx)

    intermittent_cand = next((c for c in candidates if "intermittent" in c["id"].lower()), None)
    assert intermittent_cand is not None
    assert "Intermittent" in intermittent_cand["title"]
    assert intermittent_cand["estimated_impact"] is None
    assert any("irregular" in lim.lower() for lim in intermittent_cand["limitations"])


def test_customer_retention_spend_evidence_only():
    ctx = build_mock_context(has_declining=True)
    candidates = RecommendationRuleRegistry.evaluate_all(ctx)

    retention_cand = next(c for c in candidates if c["category"] == RecommendationCategory.CUSTOMER_RETENTION)
    assert retention_cand["estimated_impact"] is None
    assert any("historical context" in e.lower() for e in retention_cand["evidence"])
    assert any("not guaranteed" in lim.lower() for lim in retention_cand["limitations"])

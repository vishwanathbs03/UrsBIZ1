"""Typed Schemas for Recommendation Context Aggregation (Phase 5.1).

Defines strongly-typed schemas consolidating ground-truth intelligence from:
  1. Business Digital Twin & Profile
  2. Health Score Engine
  3. Sales Intelligence (Transactions, Revenue, Quantity, Freshness)
  4. Customer Analytics (Concentration, Inactive Repeat Buyers, AOV)
  5. Product Performance (Revenue, Volume Pareto)
  6. Demand Forecasting (Trends, Horizons, Reliability, Disclaimers)
  7. Government Schemes Matching (Verified Authorities, URLs)
  8. Operational Readiness & SWOT

Strict Zero-Hallucination Guard:
  - If data is absent, fields are explicitly None or empty.
  - Zero-demand periods are distinguished from unconfirmed gaps.
  - Duplicate sales records are excluded.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class BusinessProfileContext(BaseModel):
    """Business identity, legal structure, stage, and geographic profile."""

    business_id: int
    legal_name: str
    trade_name: Optional[str] = None
    industry: str
    business_stage: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = "India"
    annual_revenue: Optional[float] = None
    revenue_currency: str = "INR"
    employee_count: Optional[int] = None
    established_year: Optional[int] = None
    has_website: bool = False
    website_url: Optional[str] = None
    has_ecommerce: bool = False
    has_export_experience: bool = False


class HealthScoreContext(BaseModel):
    """Health score report and dimensional completeness."""

    overall_score: int = Field(ge=0, le=100)
    grade: str
    missing_fields: list[str] = Field(default_factory=list)
    facet_scores: dict[str, float] = Field(default_factory=dict)
    computed_at: Optional[str] = None


class SalesIntelligenceContext(BaseModel):
    """Empirical sales ledger summary metrics excluding duplicates."""

    has_sales_data: bool = False
    total_transactions: int = 0
    total_revenue: float = 0.0
    total_quantity: float = 0.0
    unique_customers: int = 0
    unique_products: int = 0
    first_transaction_date: Optional[str] = None
    latest_transaction_date: Optional[str] = None
    date_range_days: int = 0
    duplicate_transactions_excluded: int = 0
    data_freshness_iso: Optional[str] = None


class CustomerAnalyticsContext(BaseModel):
    """Customer purchasing behavior, concentration, and inactivity metrics."""

    total_customers: int = 0
    repeat_customers: int = 0
    repeat_rate_pct: float = 0.0
    average_order_value: float = 0.0
    top_customers_by_revenue: list[dict[str, Any]] = Field(default_factory=list)
    declining_customers: list[dict[str, Any]] = Field(default_factory=list)


class ProductPerformanceContext(BaseModel):
    """Product portfolio breakdown by revenue contribution and sales volume."""

    total_products: int = 0
    top_products_by_revenue: list[dict[str, Any]] = Field(default_factory=list)
    fast_moving_products_by_volume: list[dict[str, Any]] = Field(default_factory=list)


class ProductForecastItemContext(BaseModel):
    """Forecast summary item for an individual SKU."""

    product_id: Optional[str] = None
    product_name: str
    demand_trend: str
    trend_delta_pct: Optional[float] = None
    forecasted_units_total: float
    forecast_horizon_periods: int
    selected_model: str
    best_mae: Optional[float] = None
    reliability: str
    limitation_notes: list[str] = Field(default_factory=list)


class DemandForecastContext(BaseModel):
    """Multi-horizon predictive demand intelligence."""

    has_forecast_data: bool = False
    forecast_interval: str = "monthly"
    forecast_horizon: int = 3
    product_forecasts: list[ProductForecastItemContext] = Field(default_factory=list)


class SchemeItemContext(BaseModel):
    """Statutory scheme match details."""

    id: str
    name: str
    official_authority: str
    official_source_url: str
    category: str
    benefits: list[str] = Field(default_factory=list)
    eligibility_reason: Optional[str] = None
    documents_required: list[str] = Field(default_factory=list)


class SchemeMatchingContext(BaseModel):
    """Government schemes matched against profile parameters."""

    recommended_schemes: list[SchemeItemContext] = Field(default_factory=list)
    eligible_schemes: list[SchemeItemContext] = Field(default_factory=list)


class OperationalReadinessContext(BaseModel):
    """Operational readiness, SWOT facets, and digital maturity."""

    digital_readiness_score: float = 0.0
    operational_completeness_pct: float = 0.0
    swot_strengths_count: int = 0
    swot_weaknesses_count: int = 0


class UnifiedRecommendationContext(BaseModel):
    """Unified, strongly-typed aggregation of verified business intelligence."""

    business_id: int
    gathered_at: str
    profile: BusinessProfileContext
    health: HealthScoreContext
    sales: SalesIntelligenceContext
    customers: CustomerAnalyticsContext
    products: ProductPerformanceContext
    forecast: DemandForecastContext
    schemes: SchemeMatchingContext
    readiness: OperationalReadinessContext
    data_sources_present: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    completed_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    outcome_history: list[dict[str, Any]] = Field(default_factory=list)
    dismissed_recommendations: list[dict[str, Any]] = Field(default_factory=list)

"""Pydantic schemas for Demand Forecasting & Predictive Intelligence (Phase 4).

Models strictly separate historical observations from forecasted future demand,
include evaluation metrics, prediction intervals, and transparent data limitations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ForecastIntervalEnum(str, Enum):
    """Supported time aggregation intervals."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ForecastReliabilityEnum(str, Enum):
    """Confidence grade based on historical data volume and backtest accuracy."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INSUFFICIENT_HISTORY = "Insufficient History"


class DataLimitationStatusEnum(str, Enum):
    """Data quality and history readiness status."""
    FORECAST_AVAILABLE = "forecast_available"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INTERMITTENT_DEMAND = "intermittent_demand"
    NO_SALES_HISTORY = "no_sales_history"


class BacktestMetricItem(BaseModel):
    """Backtesting evaluation metrics evaluated on chronological holdout data."""
    model_name: str
    mae: float = Field(..., description="Mean Absolute Error on holdout test set")
    rmse: float = Field(..., description="Root Mean Squared Error on holdout test set")
    wape: Optional[float] = Field(None, description="Weighted Absolute Percentage Error (sum(|e|) / sum(actuals))")
    mape: Optional[float] = Field(None, description="Mean Absolute Percentage Error (evaluated on non-zero actuals only)")
    mase: Optional[float] = Field(None, description="Mean Absolute Scaled Error relative to naive in-sample baseline")
    holdout_periods: int = Field(..., description="Number of holdout periods used for out-of-sample testing")
    is_selected: bool = Field(False, description="Whether this model was selected for the final production forecast")


class ForecastPeriodPoint(BaseModel):
    """A single future forecast period point with uncertainty range."""
    period_index: int
    period_label: str  # e.g., "2026-W34", "2026-09"
    period_start: str  # YYYY-MM-DD
    period_end: str    # YYYY-MM-DD
    predicted_quantity: float = Field(..., ge=0.0, description="Predicted units to be sold (non-negative)")
    lower_estimate: float = Field(..., ge=0.0, description="Lower prediction bound (estimated prediction range)")
    upper_estimate: float = Field(..., ge=0.0, description="Upper prediction bound (estimated prediction range)")


class HistoricalPeriodPoint(BaseModel):
    """A single historical demand observation period with coverage classification."""
    period_label: str
    period_start: str
    period_end: str
    actual_quantity: float = Field(..., ge=0.0, description="Total physical units sold in this period")
    has_data: bool = Field(..., description="True if transactions occurred, False if period had zero sales")
    coverage_status: str = Field(
        "active",
        description="active (sales recorded), zero_recorded_sales (other business products sold), or unconfirmed_gap (no business records)",
    )


class ProductForecastSummaryItem(BaseModel):
    """Summary forecast record for a product in the demand overview table."""
    product_name: str
    product_id: Optional[str] = None
    data_status: DataLimitationStatusEnum
    selected_model: str
    reliability: ForecastReliabilityEnum
    historical_periods_count: int
    historical_units_total: float
    forecast_horizon_periods: int
    forecasted_units_total: float
    demand_trend: str  # Increasing, Decreasing, Stable, Insufficient History
    trend_delta_pct: Optional[float] = None
    best_mae: Optional[float] = None
    best_wape: Optional[float] = None
    range_type: Optional[str] = Field("Estimated Prediction Range", description="Label for prediction range")
    empirical_coverage_summary: Optional[str] = Field(None, description="Diagnostic holdout sample coverage summary, e.g. '100.0% (3/3 holdout points)'")
    empirical_coverage_pct: Optional[float] = Field(None, description="Empirical coverage percentage on holdout evaluations")
    empirical_coverage_samples: Optional[int] = Field(None, description="Number of holdout observation points evaluated")
    limitation_notes: list[str] = Field(default_factory=list)


class ProductForecastDetailResponse(BaseModel):
    """Comprehensive demand forecast for a single product with full historical and holdout details."""
    product_name: str
    product_id: Optional[str] = None
    data_status: DataLimitationStatusEnum
    selected_model: str
    reliability: ForecastReliabilityEnum
    aggregation_interval: ForecastIntervalEnum
    forecast_horizon_periods: int
    forecasted_units_total: float
    demand_trend: str
    trend_delta_pct: Optional[float] = None

    history_points: list[HistoricalPeriodPoint]
    forecast_points: list[ForecastPeriodPoint]
    backtest_metrics: list[BacktestMetricItem]

    range_type: str = Field(
        "Estimated Prediction Range",
        description="Always 'Estimated Prediction Range' - an empirical estimate, not a formal large-sample calibration",
    )
    empirical_coverage_summary: Optional[str] = Field(
        None,
        description="Diagnostic holdout sample coverage summary, e.g. '100.0% (3/3 holdout points)'",
    )
    empirical_coverage_pct: Optional[float] = Field(
        None,
        description="Empirical coverage percentage on holdout evaluations",
    )
    empirical_coverage_samples: Optional[int] = Field(
        None,
        description="Number of holdout observation points evaluated",
    )

    explanation: str
    limitations: list[str]
    provenance: dict[str, Any]


class DemandForecastOverviewResponse(BaseModel):
    """High-level demand forecasting dashboard overview across all products."""
    total_products: int
    products_with_forecast: int
    products_insufficient_history: int
    products_increasing_demand: int
    products_declining_demand: int
    products_stable_demand: int
    total_projected_demand_units: float
    forecast_horizon: str  # e.g., "Next 4 Weeks"
    aggregation_interval: ForecastIntervalEnum
    product_summaries: list[ProductForecastSummaryItem]

    dataset_span_days: int
    earliest_transaction_date: Optional[str] = None
    latest_transaction_date: Optional[str] = None
    inactivity_anchor_date: Optional[str] = None


class ForecastExplainRequest(BaseModel):
    """Request payload for plain-language AI explanation of a verified forecast."""
    product_name: str
    historical_units: float
    forecast_units: float
    forecast_horizon: str
    selected_model: str
    reliability: str
    trend: str
    best_mae: Optional[float] = None
    limitations: list[str] = Field(default_factory=list)


class ForecastExplainResponse(BaseModel):
    """AI or deterministic explanation of verified forecast results."""
    product_name: str
    explanation: str
    is_ai_generated: bool
    disclaimer: str = (
        "Forecast explanations reflect historical customer demand and do not "
        "guarantee inventory availability, production capacity, or supply chain execution."
    )

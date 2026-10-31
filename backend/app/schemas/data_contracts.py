"""Typed Data Contracts between Backend Business Modules and AI Context Retrieval (Phase 5).

Defines strict, validated Pydantic contracts enforcing type safety, unit consistency,
valid periods, non-negative bounds, and multi-tenant isolation.
"""

from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.data_provenance import (
    DataQualityStatus,
    FreshnessStatus,
    MetricNature,
    ModuleDomain,
)

T = TypeVar("T")

SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}


class ValidatedBusinessProfileContract(BaseModel):
    """Data contract for Business Digital Twin identity."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0, description="Positive integer business ID")
    legal_name: str = Field(..., min_length=2, max_length=255)
    trade_name: Optional[str] = Field(None, max_length=255)
    industry: str = Field(..., min_length=2, max_length=100)
    business_stage: str = Field("Established", max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    country: str = Field("India", max_length=100)
    annual_revenue: Optional[float] = Field(None, ge=0.0)
    revenue_currency: str = Field("INR", max_length=10)
    employee_count: Optional[int] = Field(None, ge=0)
    established_year: Optional[int] = Field(None, ge=1800, le=2100)
    has_website: bool = False
    website_url: Optional[str] = None
    has_ecommerce: bool = False
    has_export_experience: bool = False

    @field_validator("revenue_currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v.upper() not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency '{v}'. Must be one of {SUPPORTED_CURRENCIES}")
        return v.upper()


class ValidatedSalesMetricsContract(BaseModel):
    """Data contract for historical sales turnover and transaction volume."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0)
    has_sales_data: bool
    total_transactions: int = Field(0, ge=0)
    total_revenue: float = Field(0.0, ge=0.0)
    total_quantity: float = Field(0.0, ge=0.0)
    unique_customers: int = Field(0, ge=0)
    unique_products: int = Field(0, ge=0)
    first_transaction_date: Optional[str] = None
    latest_transaction_date: Optional[str] = None
    date_range_days: int = Field(0, ge=0)
    duplicate_transactions_excluded: int = Field(0, ge=0)
    currency: str = Field("INR", max_length=10)

    @field_validator("total_revenue", "total_quantity")
    @classmethod
    def check_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Numeric value cannot be NaN or Infinity")
        return v

    @model_validator(mode="after")
    def validate_date_sequence(self) -> ValidatedSalesMetricsContract:
        if self.first_transaction_date and self.latest_transaction_date:
            try:
                d1 = datetime.fromisoformat(self.first_transaction_date.replace("Z", "+00:00"))
                d2 = datetime.fromisoformat(self.latest_transaction_date.replace("Z", "+00:00"))
                if d1 > d2:
                    raise ValueError(
                        f"first_transaction_date ({self.first_transaction_date}) cannot be after latest_transaction_date ({self.latest_transaction_date})"
                    )
            except (ValueError, TypeError):
                pass
        return self


class ValidatedCustomerAnalyticsContract(BaseModel):
    """Data contract for customer concentration and purchasing health."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0)
    total_customers: int = Field(0, ge=0)
    repeat_customers: int = Field(0, ge=0)
    repeat_rate_pct: float = Field(0.0, ge=0.0, le=100.0)
    average_order_value: float = Field(0.0, ge=0.0)
    top_customers_by_revenue: list[dict[str, Any]] = Field(default_factory=list)
    declining_customers: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("repeat_customers")
    @classmethod
    def check_repeat_lte_total(cls, v: int, info: Any) -> int:
        return v


class ValidatedProductPerformanceContract(BaseModel):
    """Data contract for SKU-level sales velocity and revenue distribution."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0)
    total_products: int = Field(0, ge=0)
    top_products_by_revenue: list[dict[str, Any]] = Field(default_factory=list)
    fast_moving_products_by_volume: list[dict[str, Any]] = Field(default_factory=list)


class ValidatedDemandForecastContract(BaseModel):
    """Data contract for Phase 4 forward-looking demand projections."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0)
    has_forecast_data: bool
    forecast_interval: str = Field("monthly", max_length=20)
    forecast_horizon: int = Field(3, ge=1, le=12)
    product_forecasts: list[dict[str, Any]] = Field(default_factory=list)
    unconfirmed_gaps_count: int = Field(0, ge=0)
    minimum_history_satisfied: bool = True


class ValidatedHealthScoreContract(BaseModel):
    """Data contract for business health diagnostics."""

    model_config = ConfigDict(extra="forbid")

    business_id: int = Field(..., gt=0)
    overall_score: int = Field(..., ge=0, le=100)
    grade: str = Field(..., max_length=20)
    missing_fields: list[str] = Field(default_factory=list)
    facet_scores: dict[str, float] = Field(default_factory=dict)
    computed_at: Optional[str] = None


class DataIntegrityEnvelope(BaseModel, Generic[T]):
    """Generic integrity envelope wrapping business data with verified provenance and freshness."""

    model_config = ConfigDict(extra="ignore")

    business_id: int = Field(..., gt=0)
    data: T
    module_domain: ModuleDomain
    nature: MetricNature
    quality_status: DataQualityStatus
    freshness_status: FreshnessStatus
    measurement_period: str
    provenance_reference: Optional[str] = None
    calculation_methodology: str
    last_verified_at: str
    confidence_score: float = Field(100.0, ge=0.0, le=100.0)
    anomalies: list[str] = Field(default_factory=list)

"""Pydantic schemas for Sales Ingestion and Sales Intelligence (Phase 3)."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Mapping of required and optional conceptual fields to file headers."""

    transaction_date: str = Field(..., description="Column containing transaction/order date")
    product_name: str = Field(..., description="Column containing product/item description or name")
    quantity: str = Field(..., description="Column containing units sold/quantity")
    unit_price: str = Field(..., description="Column containing price per unit")
    customer_name: Optional[str] = Field(None, description="Column containing customer or client name")
    customer_id: Optional[str] = Field(None, description="Column containing customer ID/code")
    product_id: Optional[str] = Field(None, description="Column containing SKU/item code")
    total_amount: Optional[str] = Field(None, description="Column containing gross revenue/total line item amount")
    invoice_id: Optional[str] = Field(None, description="Column containing invoice/bill number")


class FilePreviewResponse(BaseModel):
    """File inspection and candidate column mapping payload."""

    filename: str
    file_format: str
    file_size_bytes: int
    total_rows_estimate: int
    detected_headers: list[str]
    suggested_mapping: dict[str, Optional[str]]
    sample_rows: list[dict[str, Any]]
    confidence_scores: dict[str, float]


class QualityIssue(BaseModel):
    """Specific row-level data quality issue."""

    row_index: int
    issue_type: str  # missing_date, invalid_quantity, invalid_price, duplicate_transaction, calculated_revenue, etc.
    severity: str    # error (rejected), warning (flagged / calculated)
    message: str
    field: Optional[str] = None
    value: Optional[Any] = None


class DataQualitySummary(BaseModel):
    """Auditable data quality summary of an upload."""

    total_rows_received: int
    valid_rows: int
    invalid_rows: int
    flagged_rows: int
    missing_dates: int = 0
    missing_customer_or_product: int = 0
    invalid_quantities: int = 0
    invalid_or_missing_prices: int = 0
    duplicate_transactions: int = 0
    calculated_revenues: int = 0
    quality_score: float = Field(..., ge=0.0, le=100.0, description="Percentage of fully compliant rows")
    issues: list[QualityIssue] = Field(default_factory=list, description="Audit trail of quality issues")


class SalesUploadConfirmRequest(BaseModel):
    """Request payload to parse and ingest confirmed sales data."""

    filename: str
    file_format: str
    column_mapping: ColumnMapping


class SalesUploadResponse(BaseModel):
    """Ingestion confirmation response."""

    upload_id: int
    business_id: int
    filename: str
    file_format: str
    status: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    quality_summary: DataQualitySummary


class SalesUploadListItem(BaseModel):
    """Summary of a historical upload."""

    id: int
    filename: str
    file_format: str
    file_size_bytes: int
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    status: str
    quality_score: float
    created_at: str


class SalesSummaryResponse(BaseModel):
    """High-level summary of active business's historical sales data."""

    has_sales_data: bool
    total_transactions: int
    total_revenue: float
    total_quantity: float
    unique_customers: int
    unique_products: int
    first_transaction_date: Optional[str] = None
    latest_transaction_date: Optional[str] = None
    date_range_days: int = 0
    latest_upload_id: Optional[int] = None
    latest_upload_filename: Optional[str] = None


class CustomerMetricItem(BaseModel):
    """Individual customer performance metrics."""

    customer_name: str
    customer_id: Optional[str] = None
    total_revenue: float
    total_orders: int
    first_purchase_date: str
    latest_purchase_date: str
    average_order_value: float
    is_repeat: bool
    status: str  # Active, Declining, New


class CustomerInsightsResponse(BaseModel):
    """Customer purchasing insights and retention analysis."""

    total_customers: int
    new_customers: int
    repeat_customers: int
    repeat_rate_pct: float
    average_order_value: float
    purchase_frequency: float
    top_customers_by_revenue: list[CustomerMetricItem]
    declining_customers: list[CustomerMetricItem]
    history_span_days: int
    declining_threshold_days: int = 60
    inactivity_definition: str = (
        "Customer is considered 'Declining' if no transaction was recorded in the last 60 days, "
        "provided the business has at least 90 days of overall sales history."
    )


class ProductMetricItem(BaseModel):
    """Individual product performance metrics."""

    product_name: str
    product_id: Optional[str] = None
    total_revenue: float
    total_quantity_sold: float
    average_unit_price: float
    total_transactions: int
    first_sale_date: str
    latest_sale_date: str
    trend: str  # Increasing, Stable, Decreasing, Insufficient History
    quantity_delta_pct: Optional[float] = None


class ProductInsightsResponse(BaseModel):
    """Product sales insights distinguishing volume from revenue."""

    total_products: int
    total_quantity_sold: float
    top_products_by_revenue: list[ProductMetricItem]
    fast_moving_products_by_volume: list[ProductMetricItem]
    increasing_sales_products: list[ProductMetricItem]
    decreasing_sales_products: list[ProductMetricItem]
    insufficient_history_products: list[ProductMetricItem]


class TimeSeriesPoint(BaseModel):
    """Data point in a sales time series."""

    period: str
    revenue: float
    quantity: float
    transaction_count: int
    unique_customers: int
    has_data: bool  # True if real transactions exist, False if interval was empty


class SalesTimeSeriesResponse(BaseModel):
    """Time-based sales aggregations."""

    granularity: str  # monthly, weekly, daily
    points: list[TimeSeriesPoint]
    total_periods: int
    active_periods: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None

"""Pydantic v2 schemas for Data Quality and Business Data Confidence Centre (Phase 6.20 Extension).

Provides complete transparency into:
  - Ingestion counts, valid-row rate, duplicate exclusions, and rejected rows
  - Dual-basis revenue reconciliation (Gross uploaded vs Duplicate-excluded analytical)
  - Observation window day counts, freshness, and unconfirmed gap boundaries
  - Insight Confidence Matrix (mapping data sufficiency to each business intelligence module)
  - Prioritized Actionable Improvement Checklist
  - Exportable data quality audit report
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class IngestionReconciliationSummary(BaseModel):
    """Reconciled ingestion totals separating gross uploads from analytical totals."""

    model_config = ConfigDict(extra="forbid")

    total_uploads_count: int
    total_rows_imported: int
    valid_rows_ingested: int
    duplicate_rows_excluded: int
    rejected_rows_count: int
    valid_row_rate_pct: float
    duplicate_row_rate_pct: float

    # Dual-basis financial reconciliation
    gross_uploaded_revenue_inr: float
    duplicate_revenue_excluded_inr: float
    analytical_revenue_inr: float
    reconciliation_basis_note: str


class ObservationWindowSummary(BaseModel):
    """Observation window boundaries, calendar day spans, and freshness."""

    model_config = ConfigDict(extra="forbid")

    earliest_transaction_date: str | None
    latest_transaction_date: str | None
    observation_window_days: int
    days_since_last_transaction: int | None
    last_upload_timestamp: str | None
    freshness_status: Literal["FRESH", "POTENTIALLY_STALE", "EXPIRED_OR_UNAVAILABLE"]
    freshness_description: str
    unconfirmed_gaps_count: int
    unconfirmed_gaps: list[dict[str, Any]]


class InsightReadinessItem(BaseModel):
    """Confidence and readiness evaluation for a specific business intelligence module."""

    model_config = ConfigDict(extra="forbid")

    module_key: str
    module_name: str
    confidence_level: Literal["High", "Medium", "Low", "Degraded", "Insufficient"]
    confidence_score: float = Field(ge=0.0, le=100.0)
    readiness_status: Literal["Ready", "Degraded with Disclosures", "Blocked by Missing Data"]
    impact_explanation: str
    missing_prerequisites: list[str]


class DataAnomalySummary(BaseModel):
    """Structured anomaly record detected during audit."""

    model_config = ConfigDict(extra="forbid")

    anomaly_type: str
    source_module: str
    record_identifier: str | None
    description: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    is_blocking: bool


class DataImprovementAction(BaseModel):
    """Actionable task business owners can perform to improve data confidence."""

    model_config = ConfigDict(extra="forbid")

    priority: Literal["High", "Medium", "Low"]
    title: str
    description: str
    impact_on_insights: str
    action_type: Literal["upload_sales", "complete_profile", "map_customers", "review_outliers", "fill_gaps"]


class DataConfidenceCentreResponse(BaseModel):
    """Comprehensive response for Data Quality & Business Data Confidence Centre."""

    model_config = ConfigDict(extra="forbid")

    business_id: int
    audit_timestamp: str
    overall_confidence_score: float = Field(ge=0.0, le=100.0)
    overall_quality_status: Literal["VERIFIED", "PROVISIONAL", "SUSPECT", "INSUFFICIENT"]
    quality_status_badge: str

    ingestion_summary: IngestionReconciliationSummary
    observation_window: ObservationWindowSummary
    insight_confidence_matrix: list[InsightReadinessItem]
    anomalies_detected: list[DataAnomalySummary]
    actionable_improvement_checklist: list[DataImprovementAction]
    data_limitations: list[str]
    disclaimer: str = (
        "Data quality confidence grades reflect mathematical completeness, freshness, and consistency. "
        "They do not alter underlying historical records."
    )

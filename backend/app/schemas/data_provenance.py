"""Pydantic v2 schemas for Enterprise-Grade Business Data Provenance & Freshness (Phase 5).

Covers:
  - MetricNature: ACTUAL, CALCULATED, ESTIMATED, FORECASTED
  - DataQualityStatus: VERIFIED, PROVISIONAL, SUSPECT, INSUFFICIENT
  - FreshnessStatus: FRESH, POTENTIALLY_STALE, EXPIRED_OR_UNAVAILABLE
  - DataProvenanceRecord: Granular provenance lineage for every business metric
  - FreshnessPolicy: Source-specific freshness rules across 7 core business domains
  - DataQualityAuditReport: Comprehensive audit evaluation for a business dataset
  - CrossModuleDiscrepancy: Structured cross-module consistency reconciliation
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class MetricNature(str, Enum):
    """Nature of business metric values."""

    ACTUAL = "actual"              # Empirical historical record (e.g. uploaded invoice)
    CALCULATED = "calculated"      # Deterministically derived (e.g. concentration %, margin)
    ESTIMATED = "estimated"        # Qualitative or rule-based estimation
    FORECASTED = "forecasted"      # Statistical forward projection (Phase 4 model)


class DataQualityStatus(str, Enum):
    """Quality and verification status of business data points."""

    VERIFIED = "VERIFIED"          # Corroborated with high integrity and no conflicts
    PROVISIONAL = "PROVISIONAL"    # Usable but subject to confirmation or sparse history
    SUSPECT = "SUSPECT"            # Contains known conflicts, outliers, or inconsistencies
    INSUFFICIENT = "INSUFFICIENT"  # Lacks necessary depth or mandatory fields


class FreshnessStatus(str, Enum):
    """Source-specific freshness status."""

    FRESH = "FRESH"                                # Fully current, authoritative for real-time decisions
    POTENTIALLY_STALE = "POTENTIALLY_STALE"        # Exceeded standard cadence, requires temporal note
    EXPIRED_OR_UNAVAILABLE = "EXPIRED_OR_UNAVAILABLE"  # Outdated or missing, active upload required


class ModuleDomain(str, Enum):
    """Supported business data module domains."""

    SALES = "sales"
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    BUSINESS_PROFILE = "profile"
    FINANCIAL_INDICATORS = "financials"
    DEMAND_FORECAST = "forecast"
    GOVERNMENT_SCHEMES = "schemes"
    HEALTH_SCORE = "health"


class DataProvenanceRecord(BaseModel):
    """Reusable, verifiable provenance metadata for an individual business metric."""

    model_config = ConfigDict(extra="ignore")

    metric_name: str = Field(..., description="Canonical metric identifier, e.g. 'total_revenue'")
    metric_value: Any = Field(..., description="Numeric or structured metric value")
    business_id: int = Field(..., gt=0, description="Authenticated tenant business ID")
    source_module: ModuleDomain = Field(..., description="Origin business domain module")
    source_record_ref: Optional[str] = Field(
        None,
        description="Traceable reference (e.g. 'sales_transactions:batch_10:1-150', 'businesses:202'). None if unavailable.",
    )
    measurement_period: str = Field(
        ...,
        description="Temporal horizon (e.g. '2025-01-01 to 2025-09-30', 'Next 30 Days', 'Current Assessment')",
    )
    unit: str = Field(..., description="Unit of measurement (e.g. 'INR', 'percentage', 'units', 'score')")
    currency: Optional[str] = Field("INR", description="ISO 4217 currency code if monetary")
    calculation_methodology: str = Field(
        ...,
        description="Transparent calculation formula or data ingestion pipeline reference",
    )
    last_updated_at: str = Field(..., description="UTC ISO 8601 timestamp of metric generation")
    data_quality_status: DataQualityStatus = Field(
        DataQualityStatus.VERIFIED, description="Data verification integrity grade"
    )
    nature: MetricNature = Field(
        MetricNature.ACTUAL, description="'actual' | 'calculated' | 'estimated' | 'forecasted'"
    )
    freshness_status: FreshnessStatus = Field(
        FreshnessStatus.FRESH, description="Source-specific freshness evaluation"
    )
    freshness_as_of: Optional[str] = Field(
        None, description="Timestamp of the latest recorded event in the source dataset"
    )
    confidence_score: float = Field(100.0, ge=0.0, le=100.0, description="Integrity confidence score")


class SourceFreshnessRule(BaseModel):
    """Freshness threshold definition for a specific business data source."""

    model_config = ConfigDict(extra="forbid")

    module: ModuleDomain
    fresh_threshold_days: int
    stale_threshold_days: int
    description: str


class CrossModuleDiscrepancy(BaseModel):
    """Record of conflict detected between disparate business data modules."""

    model_config = ConfigDict(extra="ignore")

    id: str
    business_id: int
    discrepancy_type: str = Field(
        ...,
        description="e.g. 'revenue_reconciliation', 'period_mismatch', 'customer_sum_overflow', 'currency_conflict'",
    )
    module_a: str
    metric_a: str
    value_a: Any
    module_b: str
    metric_b: str
    value_b: Any
    divergence_pct: Optional[float] = None
    description: str
    resolution_guidance: str
    severity: str = Field("Medium", description="'Critical' | 'High' | 'Medium' | 'Low'")


class DataQualityAnomaly(BaseModel):
    """An individual data quality anomaly detected during audit."""

    model_config = ConfigDict(extra="ignore")

    anomaly_type: str = Field(
        ...,
        description="e.g. 'missing_field', 'duplicate_record', 'invalid_date', 'negative_number', 'currency_mismatch', 'outlier_surge', 'unconfirmed_gap'",
    )
    source_module: str
    record_identifier: Optional[str] = None
    field_name: Optional[str] = None
    observed_value: Any = None
    description: str
    severity: str = Field("Medium", description="'Critical' | 'High' | 'Medium' | 'Low'")
    is_blocking: bool = False


class DataQualityAuditReport(BaseModel):
    """Aggregated data quality evaluation for a business dataset."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    audit_timestamp: str
    overall_quality_status: DataQualityStatus
    quality_score: float = Field(..., ge=0.0, le=100.0)
    anomalies_detected: list[DataQualityAnomaly] = Field(default_factory=list)
    cross_module_discrepancies: list[CrossModuleDiscrepancy] = Field(default_factory=list)
    freshness_summary: dict[str, FreshnessStatus] = Field(default_factory=dict)
    unconfirmed_gaps_count: int = 0
    duplicate_records_count: int = 0
    data_limitations: list[str] = Field(default_factory=list)

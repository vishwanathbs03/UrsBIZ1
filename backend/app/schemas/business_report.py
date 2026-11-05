"""Pydantic schemas for Reports and Evidence Export Centre (Phase 6.25).

Strict contract definitions for report catalog, configuration, preview,
generation, history, and evidence provenance.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportType(str, Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    SALES_REVENUE_PERFORMANCE = "sales_revenue_performance"
    CUSTOMER_PERFORMANCE = "customer_performance"
    PRODUCT_PERFORMANCE = "product_performance"
    DECISIONS_SUMMARY = "decisions_summary"
    ALERTS_SUMMARY = "alerts_summary"
    GOALS_PROGRESS = "goals_progress"
    DATA_QUALITY_AUDIT = "data_quality_audit"
    SCENARIO_COMPARISON = "scenario_comparison"


class ReportFormat(str, Enum):
    PDF = "PDF"
    CSV = "CSV"
    XLSX = "XLSX"


class ReportStatus(str, Enum):
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ReportCoverageStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL_DATA = "PARTIAL_DATA"
    MISSING_DATA = "MISSING_DATA"
    STALE_DATA = "STALE_DATA"


class EvidenceNature(str, Enum):
    CONFIRMED_EVENT = "CONFIRMED_EVENT"
    WARNING = "WARNING"
    ESTIMATE = "ESTIMATE"
    ASSUMPTION = "ASSUMPTION"


# --- Catalog Schemas ---

class ReportCatalogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_type: str
    category: str
    title: str
    description: str
    supported_formats: list[str] = Field(default_factory=lambda: ["PDF", "CSV", "XLSX"])
    required_data_sources: list[str] = Field(default_factory=list)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    is_available: bool = True


class ReportCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ReportCatalogItem]
    total_reports: int


# --- Table & Provenance Structures ---

class ReportTableData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    headers: list[str]
    rows: list[list[Any]]
    notes: str | None = None


class ReportProvenance(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_name: str | None = None
    calculation_method: str
    evidence_source: str
    event_nature: str = "CONFIRMED_EVENT"
    observation_window: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str


# --- Preview Schemas ---

class ReportPreviewRequest(BaseModel):
    report_type: str
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    format: str = "PDF"
    parameters: dict[str, Any] | None = None


class ReportPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_type: str
    title: str
    business_name: str
    business_id: int
    reporting_period: str
    start_date: str | None = None
    end_date: str | None = None
    coverage_status: str
    freshness_warning: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    tables: list[ReportTableData] = Field(default_factory=list)
    provenance: ReportProvenance
    ai_explanation: str | None = None
    generated_at: str


# --- Generate Schemas ---

class ReportGenerateRequest(BaseModel):
    report_type: str
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    format: str = "PDF"
    parameters: dict[str, Any] | None = None


# --- History & Details Schemas ---

class ReportHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: str
    business_id: int
    report_type: str
    title: str
    reporting_period: str | None = None
    format: str
    status: str
    file_size_bytes: int | None = None
    download_count: int = 0
    created_at: str
    summary_metrics: dict[str, Any] | None = None
    coverage_status: str | None = None


class ReportHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ReportHistoryItem]
    total: int
    page: int = 1
    page_size: int = 50


class ReportDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: str
    business_id: int
    report_type: str
    title: str
    reporting_period: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    format: str
    status: str
    file_size_bytes: int | None = None
    mime_type: str
    checksum_sha256: str | None = None
    download_count: int = 0
    parameters: dict[str, Any] | None = None
    summary_metrics: dict[str, Any] | None = None
    provenance_metadata: dict[str, Any] | None = None
    error_message: str | None = None
    is_archived: bool = False
    created_at: str
    preview: ReportPreviewResponse | None = None

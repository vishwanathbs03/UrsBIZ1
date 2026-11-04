"""Pydantic schemas for Business Goals & Progress Tracker (Prompt 6.24)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class GoalMeasurementMethod(str, Enum):
    """How the business goal is evaluated."""

    AUTOMATED_METRIC = "AUTOMATED_METRIC"
    MANUAL_REPORTED = "MANUAL_REPORTED"
    ESTIMATE = "ESTIMATE"


class GoalStatus(str, Enum):
    """Lifecycle status of a business goal."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class GoalDataAvailability(str, Enum):
    """Freshness and presence of underlying measurement data."""

    AVAILABLE = "AVAILABLE"
    MISSING_DATA = "MISSING_DATA"
    STALE_DATA = "STALE_DATA"
    PENDING_PERIOD = "PENDING_PERIOD"


class GoalMetricKey(str, Enum):
    """Supported deterministic business metrics for automated progress."""

    MONTHLY_REVENUE = "monthly_revenue"
    CUSTOMER_CONCENTRATION = "customer_concentration"
    REPEAT_CUSTOMER_RATE = "repeat_customer_rate"
    AVERAGE_ORDER_VALUE = "average_order_value"
    NEW_CUSTOMERS_COUNT = "new_customers_count"
    SALES_UPLOAD_FREQUENCY = "sales_upload_frequency"
    DIGITAL_TWIN_HEALTH_SCORE = "digital_twin_health_score"
    MANUAL = "manual"


class RelatedItemOut(BaseModel):
    """Related recommendation, decision, or action item."""

    id: str | int
    type: str  # "recommendation" | "decision" | "action_item"
    title: str
    status: str


class BusinessGoalAuditOut(BaseModel):
    """Historical audit snapshot entry for a business goal."""

    id: int
    goal_id: int | None
    business_id: int
    changed_by_user_id: int | None
    action: str
    old_status: str | None = None
    new_status: str | None = None
    measured_value: float | None = None
    target_value: float | None = None
    progress_pct: float | None = None
    notes: str | None = None
    snapshot_data: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessGoalCreate(BaseModel):
    """Request payload to create a new measurable business goal."""

    title: str = Field(..., min_length=2, max_length=200, description="Short title of the business goal")
    description: str | None = Field(None, max_length=1000, description="Detailed strategic context or objective")
    metric_key: str | None = Field(
        None,
        description="Authoritative metric key (e.g. monthly_revenue, customer_concentration, repeat_customer_rate, or manual)",
    )
    measurement_method: GoalMeasurementMethod = Field(
        default=GoalMeasurementMethod.AUTOMATED_METRIC,
        description="Whether progress is tracked by automated metric, manual declaration, or estimate",
    )
    baseline_value: float | None = Field(
        None, description="Starting benchmark value before goal execution"
    )
    target_value: float = Field(
        ..., description="Desired quantitative target value to reach or stay below"
    )
    unit: str = Field(
        default="INR", max_length=32, description="Measurement unit (e.g. INR, %, count, days)"
    )
    start_date: date | None = Field(
        None, description="Start date of the observation window"
    )
    target_date: date | None = Field(
        None, description="Target completion deadline date"
    )
    timeframe: str | None = Field(
        None, max_length=50, description="Human-readable timeframe (e.g. '30d', '90d', '1y')"
    )
    priority: str = Field(
        default="medium", max_length=20, description="Priority: low, medium, high, critical"
    )


class BusinessGoalUpdate(BaseModel):
    """Request payload to update goal parameters."""

    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=1000)
    target_value: float | None = None
    target_date: date | None = None
    priority: str | None = None
    status_notes: str | None = None


class BusinessGoalStatusUpdate(BaseModel):
    """Request payload to update goal status with optional notes."""

    status: GoalStatus
    notes: str | None = None


class BusinessGoalManualProgressUpdate(BaseModel):
    """Request payload to record owner self-reported progress."""

    current_value: float
    notes: str | None = None


class BusinessGoalOut(BaseModel):
    """Full representation of a business goal with evaluated progress and provenance."""

    id: int
    business_id: int
    title: str
    description: str | None = None
    timeframe: str | None = None
    priority: str
    start_date: date | None = None
    target_date: date | None = None

    # Measurement details
    metric_key: str | None = None
    measurement_method: GoalMeasurementMethod
    baseline_value: float | None = None
    target_value: float
    current_value: float | None = None
    progress_pct: float | None = None
    remaining_gap: float | None = None
    unit: str

    # Status & Life cycle
    status: GoalStatus
    status_notes: str | None = None

    # Data Quality & Freshness
    data_availability: GoalDataAvailability
    data_freshness_warning: str | None = None
    evidence_source: str
    is_achieved: bool
    days_remaining: int | None = None
    last_evaluated_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    # Cross-module relationships
    related_recommendations: list[RelatedItemOut] = []
    related_decisions: list[RelatedItemOut] = []
    audits: list[BusinessGoalAuditOut] = []

    model_config = ConfigDict(from_attributes=True)


class BusinessGoalListResponse(BaseModel):
    """Paginated list of business goals with summary counters."""

    items: list[BusinessGoalOut]
    total: int
    active_count: int
    completed_count: int
    at_risk_count: int
    stale_or_missing_data_count: int


class GoalAIExplanationResponse(BaseModel):
    """Non-mutating AI analysis of goal feasibility and action steps."""

    goal_id: int
    goal_title: str
    trajectory: str  # ON_TRACK, AT_RISK, BEHIND, NEEDS_DATA, ACHIEVED
    feasibility_assessment: str
    analysis: str
    suggested_actions: list[str]
    evidence_summary: str

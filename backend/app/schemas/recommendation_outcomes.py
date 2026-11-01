"""Pydantic v2 schemas for Closed-Loop Recommendation Learning & Outcome Intelligence (Phase 5).

Defines structured contracts for:
  - Outcome Tracking & Implementation Feedback
  - Deterministic Before-and-After Business Measurements with Causal Disclaimers
  - Recommendation Effectiveness Analytics with Small-Sample Safeguards
  - Recommendation Version & Decision Audit History
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class OutcomeRecordingRequest(BaseModel):
    """Payload for recording or updating recommendation implementation outcomes."""

    model_config = ConfigDict(extra="ignore")

    is_started: Optional[bool] = Field(default=None, description="Whether implementation work was initiated")
    is_completed: Optional[bool] = Field(default=None, description="Whether recommendation action was fully completed")
    is_abandoned: Optional[bool] = Field(default=None, description="Whether recommendation action was abandoned/stopped")
    started_at: Optional[str] = Field(default=None, description="ISO 8601 start date")
    completed_at: Optional[str] = Field(default=None, description="ISO 8601 completion date")
    actual_effort: Optional[str] = Field(default=None, description="Owner-reported implementation effort (Low, Medium, High)")
    owner_rating: Optional[int] = Field(default=None, ge=1, le=5, description="Utility rating (1-5 stars)")
    qualitative_feedback: Optional[str] = Field(default=None, description="Qualitative feedback or implementation learnings")
    perceived_utility: Optional[str] = Field(default=None, description="Very Useful, Useful, Neutral, or Not Useful")
    non_completion_reason: Optional[str] = Field(
        default=None,
        description="LACK_OF_TIME | LACK_OF_CAPITAL | TOO_COMPLEX | SUPPLIER_DEPENDENCY | OTHER",
    )
    still_relevant: Optional[bool] = Field(default=True, description="Whether original recommendation remains relevant")
    notes: Optional[str] = Field(default=None, description="Additional context or operational notes")


class MetricComparison(BaseModel):
    """Comparative measurement of a single business metric across symmetric time windows."""

    model_config = ConfigDict(extra="ignore")

    metric_name: str
    unit: str
    baseline_value: float
    post_value: float
    delta_absolute: float
    delta_percentage: float
    direction: str = Field(..., description="INCREASED | DECREASED | UNCHANGED")
    observation_statement: str


class BeforeAfterMeasurementResponse(BaseModel):
    """Empirical before-and-after business measurement across symmetric time windows."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    title: str
    completed_at: Optional[str] = None
    measurement_window_days: int = Field(default=30, description="Symmetric evaluation window in days (e.g. 14, 30, 60)")
    window_status: str = Field(..., description="COMPLETED_WINDOW | PARTIAL_WINDOW_IN_PROGRESS | INSUFFICIENT_BASELINE_DATA")
    elapsed_days_since_completion: int
    pre_period_start: Optional[str] = None
    pre_period_end: Optional[str] = None
    post_period_start: Optional[str] = None
    post_period_end: Optional[str] = None
    comparison_methodology: str = "symmetric_time_window_pre_post"
    data_gaps: list[str] = Field(default_factory=list)
    metrics: list[MetricComparison] = Field(default_factory=list)
    causal_disclaimer: str = Field(
        default="Observed changes during the measurement period reflect empirical correlation and not proof that the recommended action alone caused the change.",
        description="Mandatory causal boundary disclaimer",
    )
    learning_quality_tier: str = Field(default="OBSERVED_CORRELATION", description="OWNER_OPINION | ACTION_COMPLETION | OBSERVED_CORRELATION")


class OutcomeTrackingResponse(BaseModel):
    """Full outcome tracking state including implementation status, owner rating, and measurements."""

    model_config = ConfigDict(extra="ignore")

    id: int
    business_id: int
    recommendation_id: str
    is_started: bool
    is_completed: bool
    is_abandoned: bool
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    actual_effort: Optional[str] = None
    owner_rating: Optional[int] = None
    qualitative_feedback: Optional[str] = None
    perceived_utility: Optional[str] = None
    non_completion_reason: Optional[str] = None
    still_relevant: bool
    measured_outcome_summary: Optional[str] = None
    measurement: Optional[BeforeAfterMeasurementResponse] = None
    created_at: str
    updated_at: str


class CategoryEffectivenessItem(BaseModel):
    """Effectiveness metrics for a single recommendation category with small-sample safeguards."""

    model_config = ConfigDict(extra="ignore")

    category: str
    total_suggested: int
    total_accepted: int
    total_completed: int
    total_abandoned: int
    acceptance_rate_pct: float
    completion_rate_pct: float
    average_rating: Optional[float] = None
    positive_outcomes_count: int
    statistical_reliability: str = Field(..., description="Reliable | Moderate | Insufficient Sample Size")
    small_sample_warning: Optional[str] = None


class RecommendationEffectivenessResponse(BaseModel):
    """Aggregate portfolio effectiveness intelligence across historical recommendation implementations."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    total_recommendations: int
    total_accepted: int
    total_completed: int
    total_dismissed: int
    total_abandoned: int
    overall_acceptance_rate_pct: float
    overall_completion_rate_pct: float
    abandonment_reasons_breakdown: dict[str, int] = Field(default_factory=dict)
    category_effectiveness: list[CategoryEffectivenessItem] = Field(default_factory=list)
    top_performing_categories: list[str] = Field(default_factory=list)
    insufficient_evidence_categories: list[str] = Field(default_factory=list)
    small_sample_safeguard_applied: bool
    methodology_notes: list[str] = Field(default_factory=list)


class RecommendationAuditEventItem(BaseModel):
    """An immutable audit event in a recommendation's version history."""

    model_config = ConfigDict(extra="ignore")

    id: int
    recommendation_id: str
    version: int
    title: str
    category: str
    priority: str
    priority_score: int
    evidence_version: Optional[str] = None
    evidence_summary: Optional[str] = None
    event_type: str = Field(..., description="CREATED | VIEWED | ACCEPTED | IN_PROGRESS | COMPLETED | DISMISSED | SNOOZED | OUTCOME_RECORDED | FEEDBACK_SUBMITTED")
    event_notes: Optional[str] = None
    metrics_snapshot: Optional[dict[str, Any]] = None
    created_at: str


class RecommendationHistoryResponse(BaseModel):
    """Audit timeline for a single recommendation."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    current_version: int
    events: list[RecommendationAuditEventItem] = Field(default_factory=list)


class CompleteHistoryResponse(BaseModel):
    """Complete audit timeline for all recommendation actions of a business."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    total_events: int
    events: list[RecommendationAuditEventItem] = Field(default_factory=list)

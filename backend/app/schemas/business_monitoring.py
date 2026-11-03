"""Pydantic v2 schemas for Proactive AI Business Monitoring & Event-Driven Intelligence (Phase 5 & 6).

Covers:
  - EventSeverity, EventNature & MonitoringEventType enums
  - BusinessSignalItem & Feed Responses
  - Change Detection Criteria & Evidence Payloads
  - Monitoring Preferences & Update Models
  - Recommendation Refresh Log Schemas
  - Alert Status Updates, Audits, Summary, and Grounded Explanations (Prompt 6.22)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class EventSeverity(str, Enum):
    """Event severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class EventNature(str, Enum):
    """Classification of the nature of a business event (Audit Item B)."""

    CONFIRMED_EVENT = "CONFIRMED_EVENT"
    WARNING = "WARNING"
    ESTIMATE = "ESTIMATE"
    ASSUMPTION = "ASSUMPTION"


class MonitoringEventType(str, Enum):
    """Verified proactive business event types."""

    # Revenue & Financial
    REVENUE_DECLINE_DETECTED = "REVENUE_DECLINE_DETECTED"
    STATISTICAL_REVENUE_DROP = "STATISTICAL_REVENUE_DROP"
    REVENUE_GROWTH_SURGE = "REVENUE_GROWTH_SURGE"

    # Customer Dynamics
    CUSTOMER_CONCENTRATION_INCREASED = "CUSTOMER_CONCENTRATION_INCREASED"
    CUSTOMER_INACTIVITY_DETECTED = "CUSTOMER_INACTIVITY_DETECTED"
    REPEAT_PURCHASE_IMPROVED = "REPEAT_PURCHASE_IMPROVED"

    # Product Performance
    PRODUCT_PERFORMANCE_DETERIORATED = "PRODUCT_PERFORMANCE_DETERIORATED"
    PRODUCT_VELOCITY_DECELERATION = "PRODUCT_VELOCITY_DECELERATION"
    PRODUCT_MOMENTUM_SURGE = "PRODUCT_MOMENTUM_SURGE"

    # Ingestion & Data Health
    CSV_UPLOAD_FAILED = "CSV_UPLOAD_FAILED"
    SALES_DATA_MISSING = "SALES_DATA_MISSING"

    # Demand Forecasting
    DEMAND_FORECAST_CHANGED = "DEMAND_FORECAST_CHANGED"
    STALE_FORECAST = "STALE_FORECAST"

    # Business Health & Digital Readiness
    CRITICAL_READINESS_GAP_DETECTED = "CRITICAL_READINESS_GAP_DETECTED"
    HEALTH_SCORE_DECLINED = "HEALTH_SCORE_DECLINED"
    HEALTH_SCORE_IMPROVED = "HEALTH_SCORE_IMPROVED"

    # Recommendation State Changes
    RECOMMENDATION_EVIDENCE_STALE = "RECOMMENDATION_EVIDENCE_STALE"
    RESOLVED_RISK_REAPPEARED = "RESOLVED_RISK_REAPPEARED"
    ACTION_OUTCOME_MEASURED = "ACTION_OUTCOME_MEASURED"


class EventStatus(str, Enum):
    """Lifecycle status of a proactive signal event."""

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    OBSOLETE = "OBSOLETE"
    SUPERSEDED = "SUPERSEDED"


class RefreshReason(str, Enum):
    """Reasons why recommendations are refreshed by the proactive engine."""

    NEW_EVIDENCE_STRENGTHENED = "NEW_EVIDENCE_STRENGTHENED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    RISK_RESOLVED = "RISK_RESOLVED"
    OPPORTUNITY_DISAPPEARED = "OPPORTUNITY_DISAPPEARED"
    OBSOLETE = "OBSOLETE"
    RESOLVED_ISSUE_RETURNED = "RESOLVED_ISSUE_RETURNED"
    PRIORITY_ESCALATED = "PRIORITY_ESCALATED"


class BusinessSignalItem(BaseModel):
    """Structured proactive business signal for MSME owners."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    business_id: int
    event_type: str
    event_nature: str = Field(
        default="WARNING",
        description="'CONFIRMED_EVENT' | 'WARNING' | 'ESTIMATE' | 'ASSUMPTION'",
    )
    source: str
    relevant_entity: Optional[str] = None
    detected_at: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    severity: str = Field(..., description="'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFORMATIONAL'")
    priority_score: int = Field(..., ge=0, le=100)
    data_period: str
    event_version: int = 1
    title: str
    what_changed: str
    why_it_matters: str
    suggested_action: str
    confidence: float = Field(0.85, ge=0.0, le=1.0)
    is_suppressed: bool = False
    suppression_reason: Optional[str] = None
    escalation_level: int = 0
    linked_recommendation_id: Optional[str] = None
    status: str = "NEW"
    resolved_at: Optional[str] = None
    is_archived: bool = False
    archived_at: Optional[str] = None
    archive_reason: Optional[str] = None


class BusinessSignalsFeedResponse(BaseModel):
    """Proactive Business Signals & Opportunities Dashboard Feed."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    total_signals: int
    active_signals_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_and_info_count: int
    signals: list[BusinessSignalItem] = Field(default_factory=list)
    last_evaluated_at: str


class RecommendationRefreshDetail(BaseModel):
    """Details of an individual recommendation refresh action."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    refresh_reason: str
    old_priority_score: int
    new_priority_score: int
    old_status: str
    new_status: str
    explanation: str
    refreshed_at: str


class MonitoringEvaluationResponse(BaseModel):
    """Result of an incremental proactive evaluation scan."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    evaluated_at: str
    new_events_detected: int
    suppressed_events: int
    refreshed_recommendations: int
    signals: list[BusinessSignalItem] = Field(default_factory=list)
    recommendation_refreshes: list[RecommendationRefreshDetail] = Field(default_factory=list)


class MonitoringPreferencesSchema(BaseModel):
    """Owner configuration for proactive business monitoring."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    monitored_metrics: list[str]
    areas_of_interest: list[str]
    alert_frequency: str = "REALTIME"
    preferred_notification_types: list[str] = Field(default_factory=lambda: ["in_app"])
    min_severity: str = "LOW"
    cooldown_days: int = 7
    updated_at: Optional[str] = None


class MonitoringPreferencesUpdate(BaseModel):
    """Payload to update monitoring preferences."""

    model_config = ConfigDict(extra="ignore")

    monitored_metrics: Optional[list[str]] = None
    areas_of_interest: Optional[list[str]] = None
    alert_frequency: Optional[str] = Field(None, description="'REALTIME' | 'DAILY_DIGEST' | 'WEEKLY_DIGEST'")
    preferred_notification_types: Optional[list[str]] = None
    min_severity: Optional[str] = Field(None, description="'LOW' | 'MEDIUM' | 'HIGH'")
    cooldown_days: Optional[int] = Field(None, ge=1, le=30)


# --------------------------------------------------------------------------- #
# Event Centre Schemas (Prompt 6.22)                                          #
# --------------------------------------------------------------------------- #


class AlertStatusUpdate(BaseModel):
    """Payload to update an alert's lifecycle status."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ACKNOWLEDGED", "RESOLVED", "DISMISSED"]
    reason: Optional[str] = Field(None, max_length=500, description="Optional explanation for transition")


class AlertAuditHistoryItem(BaseModel):
    """Single audit entry recording status change."""

    model_config = ConfigDict(extra="ignore")

    id: int
    event_id: str
    business_id: int
    previous_status: str
    new_status: str
    changed_by_user_id: Optional[int] = None
    changed_at: str
    reason: Optional[str] = None


class AlertArchiveRequest(BaseModel):
    """Payload to archive or soft-delete an alert."""

    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(None, max_length=500, description="Reason for archiving alert")


class AlertSummaryResponse(BaseModel):
    """Aggregated counters for business alerts dashboard."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    total_alerts: int
    new_count: int
    acknowledged_count: int
    resolved_count: int
    dismissed_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_and_info_count: int
    confirmed_events_count: int
    warnings_count: int
    estimates_count: int
    assumptions_count: int
    last_evaluated_at: Optional[str] = None


class AlertExplainRequest(BaseModel):
    """Request payload to explain an alert."""

    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "kn"] = "en"


class AlertExplainResponse(BaseModel):
    """Grounded explanation of an alert."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    title: str
    severity: str
    event_nature: str
    explanation: str
    language: str
    provider_used: str
    is_fallback: bool

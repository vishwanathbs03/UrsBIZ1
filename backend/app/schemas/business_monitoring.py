"""Pydantic v2 schemas for Proactive AI Business Monitoring & Event-Driven Intelligence (Phase 5).

Covers:
  - EventSeverity & MonitoringEventType enums
  - BusinessSignalItem & Feed Responses
  - Change Detection Criteria & Evidence Payloads
  - Monitoring Preferences & Update Models
  - Recommendation Refresh Log Schemas
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class EventSeverity(str, Enum):
    """Event severity levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class MonitoringEventType(str, Enum):
    """Verified proactive business event types."""

    # Revenue & Financial
    REVENUE_DECLINE_DETECTED = "REVENUE_DECLINE_DETECTED"
    REVENUE_GROWTH_SURGE = "REVENUE_GROWTH_SURGE"

    # Customer Dynamics
    CUSTOMER_CONCENTRATION_INCREASED = "CUSTOMER_CONCENTRATION_INCREASED"
    CUSTOMER_INACTIVITY_DETECTED = "CUSTOMER_INACTIVITY_DETECTED"
    REPEAT_PURCHASE_IMPROVED = "REPEAT_PURCHASE_IMPROVED"

    # Product Performance
    PRODUCT_PERFORMANCE_DETERIORATED = "PRODUCT_PERFORMANCE_DETERIORATED"
    PRODUCT_MOMENTUM_SURGE = "PRODUCT_MOMENTUM_SURGE"

    # Demand Forecasting
    DEMAND_FORECAST_CHANGED = "DEMAND_FORECAST_CHANGED"

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

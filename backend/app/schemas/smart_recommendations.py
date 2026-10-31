"""Pydantic v2 schemas for Context-Aware Business Recommendations (Phase 5).

Defines structured schema, 10 categories, priority levels, action plans,
lifecycle status, and API envelopes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecommendationCategory(str, Enum):
    """The 10 official recommendation categories for Phase 5."""

    REVENUE_GROWTH = "Revenue Growth"
    COST_OPTIMIZATION = "Cost Optimization"
    CUSTOMER_RETENTION = "Customer Retention"
    PRODUCT_PERFORMANCE = "Product Performance"
    DEMAND_PLANNING = "Demand and Sales Planning"
    DIGITAL_TRANSFORMATION = "Digital Transformation"
    FINANCIAL_MANAGEMENT = "Financial Management"
    OPERATIONAL_EFFICIENCY = "Operational Efficiency"
    GOVERNMENT_SCHEMES = "Government Schemes and Funding"
    RISK_REDUCTION = "Risk Reduction"


class RecommendationPriority(str, Enum):
    """Deterministic priority levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RecommendationStatus(str, Enum):
    """Recommendation lifecycle states."""

    NEW = "New"
    VIEWED = "Viewed"
    ACCEPTED = "Accepted"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    DISMISSED = "Dismissed"


class ActionStep(BaseModel):
    """One concrete implementation step in an action plan."""

    model_config = ConfigDict(extra="ignore")

    step_number: int = Field(..., ge=1)
    title: str
    description: str
    timeframe: str
    resources_required: str


class ActionPlan(BaseModel):
    """Structured implementation plan for a recommendation."""

    model_config = ConfigDict(extra="ignore")

    objective: str
    steps: list[ActionStep] = Field(default_factory=list)
    suggested_timeframe: str
    success_metric: str


class SmartRecommendationItem(BaseModel):
    """Structured, data-grounded business recommendation."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique deterministic recommendation identifier")
    title: str = Field(..., description="Clear, action-oriented title")
    category: RecommendationCategory
    priority: RecommendationPriority
    priority_score: int = Field(..., ge=0, le=100, description="Deterministic priority score (0-100)")
    description: str = Field(..., description="Detailed recommendation narrative")
    business_context: str = Field(..., description="Relevant business context supporting this recommendation")
    evidence: list[str] = Field(default_factory=list, description="Verified data points and metrics")
    reasoning: str = Field(..., description="Why this recommendation was generated")
    recommended_actions: list[str] = Field(default_factory=list, description="List of immediate recommended actions")
    action_plan: Optional[ActionPlan] = Field(default=None, description="Detailed sequential execution plan")
    expected_benefit: str = Field(..., description="Expected operational or financial outcome")
    estimated_impact: Optional[float] = Field(default=None, description="Quantified benefit if calculable, else None")
    impact_unit: Optional[str] = Field(default=None, description="Unit for estimated_impact (e.g. 'INR', '%', 'units')")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence in underlying data (0-100)")
    data_quality: str = Field(..., description="'High', 'Moderate', 'Limited', or 'Insufficient'")
    limitations: list[str] = Field(default_factory=list, description="Known uncertainties or data constraints")
    source_modules: list[str] = Field(default_factory=list, description="UrsBiz modules contributing evidence")
    source_module_link: Optional[str] = Field(default=None, description="In-app deep link to evidence source")
    created_at: str = Field(..., description="ISO 8601 generation timestamp")
    status: RecommendationStatus = Field(default=RecommendationStatus.NEW)
    status_updated_at: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)

    # Enhanced 9-Pillar Business Consultant Dimensions
    what_is_happening: Optional[str] = Field(default=None, description="Diagnostic analysis of current business state")
    why_it_matters: Optional[str] = Field(default=None, description="Business severity, operational risk, or growth constraint")
    root_cause: Optional[str] = Field(default=None, description="Verified data-backed root cause explaining why this occurs")
    missed_opportunity: Optional[str] = Field(default=None, description="Value or strategic advantage currently left on the table")
    action_scenario: Optional[str] = Field(default=None, description="Projected outcome if the owner implements the recommended actions")
    cost_of_inaction: Optional[str] = Field(default=None, description="Direct cost, compounding risk, and downsides if the owner takes no action")
    measurement_kpis: list[str] = Field(default_factory=list, description="Target metrics and milestones to measure improvement")
    implementation_difficulty: str = Field(default="Tactical", description="'Quick Win' (1-7d) | 'Tactical' (8-30d) | 'Strategic' (30-90d)")
    prerequisites_and_tradeoffs: list[str] = Field(default_factory=list, description="Operational prerequisites and strategic trade-offs")
    is_autonomous_opportunity: bool = Field(default=False, description="True if dynamically discovered beyond predefined rules")
    opportunity_quality_status: Optional[str] = Field(default=None, description="VERIFIED_OPPORTUNITY | PROMISING_OPPORTUNITY | NEEDS_INVESTIGATION")
    opportunity_hypothesis_id: Optional[str] = Field(default=None, description="ID of underlying OpportunityHypothesis")


class SmartRecommendationsResponse(BaseModel):
    """Response envelope for GET /api/v1/recommendations."""

    model_config = ConfigDict(extra="ignore")

    generated_at: str
    business_id: int
    business_name: str
    total_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    recommendations: list[SmartRecommendationItem] = Field(default_factory=list)


class RecommendationStatusUpdateRequest(BaseModel):
    """Payload for PATCH /api/v1/recommendations/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: RecommendationStatus
    notes: Optional[str] = None


class RecommendationExplainRequest(BaseModel):
    """Payload for POST /api/v1/recommendations/{id}/explain."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str


class RecommendationExplainResponse(BaseModel):
    """Response for AI-powered recommendation explanation with 9-pillar executive diagnostic brief."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    title: str
    explanation: str
    is_ai_generated: bool
    practical_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # 9-Pillar Executive Diagnostic Brief
    executive_summary: Optional[str] = Field(default=None, description="Concise bottom-line assessment")
    what_is_happening: Optional[str] = Field(default=None, description="Current operational state diagnosis")
    what_is_going_wrong: Optional[str] = Field(default=None, description="Core business vulnerability or bottleneck")
    why_is_it_happening: Optional[str] = Field(default=None, description="Multi-signal root cause explanation")
    missed_opportunity: Optional[str] = Field(default=None, description="Strategic upside or revenue left on table")
    action_outcome: Optional[str] = Field(default=None, description="Projected outcome if recommendation is implemented")
    inaction_cost: Optional[str] = Field(default=None, description="Direct cost and risk of doing nothing")
    implementation_phases: list[dict[str, Any]] = Field(default_factory=list, description="Phased implementation roadmap (Days 1-7, 8-30, 31-60)")
    measurement_kpis: list[str] = Field(default_factory=list, description="Measurable milestones and tracking metrics")
    confidence_score: Optional[float] = Field(default=None, description="Confidence in underlying data (0-100)")
    data_quality_label: Optional[str] = Field(default=None, description="Data quality tier: High, Moderate, Limited, Insufficient")

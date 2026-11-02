"""Pydantic schemas for Business Decision Workbench (Phase 6.18 Extension).

Enforces strict contracts for decision option evaluation, baseline evidence
snapshots, calculated estimates, assumptions, and owner review tracking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class DecisionEvidenceItem(BaseModel):
    """An individual piece of supporting business data with source and observation window."""
    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Authoritative service producing the evidence")
    metric: str = Field(description="Name of the business metric or observation")
    value: Any = Field(description="Observed empirical value")
    unit: str = Field(default="", description="Unit of measurement (INR, %, orders, etc.)")
    observation_period: str = Field(default="", description="Date range or observation window")
    data_classification: Literal["Observed Fact", "Calculated Metric", "User-Entered", "Scenario Estimate"] = "Observed Fact"
    freshness: str = Field(default="FRESH", description="Freshness status of the data")


class DecisionEstimatedImpact(BaseModel):
    """Estimated business impact calculated only when verified inputs exist."""
    model_config = ConfigDict(extra="forbid")

    has_calculation_inputs: bool = Field(description="Whether required inputs exist to compute impact")
    revenue_delta_inr: Optional[float] = Field(default=None, description="Projected change in revenue in INR")
    revenue_delta_pct: Optional[float] = Field(default=None, description="Projected change in revenue percentage")
    margin_delta_pct: Optional[float] = Field(default=None, description="Projected change in gross margin percentage points")
    volume_delta_pct: Optional[float] = Field(default=None, description="Projected change in unit/order volume percentage")
    payback_period_days: Optional[int] = Field(default=None, description="Estimated days to break even on investment")
    calculation_method: str = Field(default="", description="Formula or method applied for projection")
    formula_applied: str = Field(default="", description="Detailed formula description")
    disclaimer: str = Field(
        default="Illustrative scenario estimate — not a guaranteed prediction.",
        description="Mandatory disclaimer for all scenario estimates",
    )


class DecisionOptionEvaluation(BaseModel):
    """A fully evaluated decision option with evidence, assumptions, risks, and estimated impact."""
    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(min_length=1, max_length=60, description="Unique option identifier")
    title: str = Field(min_length=1, max_length=200, description="Option name")
    description: str = Field(description="Action description for this option")
    supporting_evidence: list[DecisionEvidenceItem] = Field(default_factory=list, description="Relevant observed facts")
    assumptions: list[str] = Field(default_factory=list, description="Underlying assumptions made")
    missing_information: list[str] = Field(default_factory=list, description="Missing data inputs that could alter outcome")
    potential_benefits: list[str] = Field(default_factory=list, description="Qualitative and strategic benefits")
    potential_risks: list[str] = Field(default_factory=list, description="Identified execution and market risks")
    estimated_impact: DecisionEstimatedImpact = Field(description="Calculated financial projections")
    confidence: int = Field(ge=0, le=100, description="Confidence score (0-100) based on data completeness")
    limitations: list[str] = Field(default_factory=list, description="Known analytical limitations")
    recommended_additional_data: list[str] = Field(default_factory=list, description="Data that would improve assessment")


class DecisionEvaluateRequest(BaseModel):
    """Request to evaluate options for an objective."""
    model_config = ConfigDict(extra="forbid")

    decision_type: Literal[
        "offer_discount",
        "increase_price",
        "customer_focus",
        "expand_product_range",
        "reduce_expenses",
        "test_sales_channel",
        "custom",
    ] = Field(description="Category of business decision")
    objective: str = Field(min_length=5, max_length=500, description="Owner's specific business goal")
    custom_parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional custom simulation parameters (e.g. discount_pct, price_increase_pct)",
    )


class DecisionEvaluateResponse(BaseModel):
    """Response containing evaluated multi-option comparisons and AI executive summary."""
    model_config = ConfigDict(extra="forbid")

    decision_type: str
    objective: str
    baseline_snapshot: dict[str, Any]
    options: list[DecisionOptionEvaluation]
    ai_executive_summary: str
    recommended_option_id: Optional[str] = None
    data_freshness: str = "FRESH"
    evaluation_timestamp: str


class DecisionCreateRequest(BaseModel):
    """Request to save a decision evaluation into the business workspace."""
    model_config = ConfigDict(extra="forbid")

    decision_type: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=5, max_length=1000)
    baseline_snapshot: dict[str, Any] = Field(default_factory=dict)
    options: list[DecisionOptionEvaluation] = Field(default_factory=list)
    selected_option_id: Optional[str] = Field(default=None, max_length=60)
    selected_option_title: Optional[str] = Field(default=None, max_length=200)
    decision_rationale: Optional[str] = Field(default=None, max_length=2000)
    status: Literal["Draft", "Evaluating", "Decided", "Implemented", "Reviewed"] = "Draft"


class DecisionUpdateRequest(BaseModel):
    """Request to update a decision, record an option choice, or log review notes."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, max_length=200)
    objective: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Literal["Draft", "Evaluating", "Decided", "Implemented", "Reviewed"]] = None
    selected_option_id: Optional[str] = Field(default=None, max_length=60)
    selected_option_title: Optional[str] = Field(default=None, max_length=200)
    decision_rationale: Optional[str] = Field(default=None, max_length=2000)
    review_status: Optional[Literal["Pending", "Outcome_Observed", "Abandoned"]] = None
    review_notes: Optional[str] = Field(default=None, max_length=2000)
    outcome_id: Optional[int] = None


class DecisionOut(BaseModel):
    """Full serialized decision record for API delivery."""
    model_config = ConfigDict(extra="forbid")

    id: int
    business_id: int
    owner_id: int
    decision_type: str
    title: str
    objective: str
    status: str
    baseline_snapshot: dict[str, Any]
    options: list[DecisionOptionEvaluation]
    selected_option_id: Optional[str] = None
    selected_option_title: Optional[str] = None
    decision_rationale: Optional[str] = None
    decided_at: Optional[datetime] = None
    review_status: str
    review_notes: Optional[str] = None
    outcome_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DecisionListResponse(BaseModel):
    """List response of saved decisions for the active business."""
    model_config = ConfigDict(extra="forbid")

    items: list[DecisionOut]
    total: int

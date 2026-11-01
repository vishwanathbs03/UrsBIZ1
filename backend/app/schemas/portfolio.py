"""Pydantic schemas for Recommendation Portfolio Optimization & Conflict Resolution (Phase 5).

Provides structured portfolio representations:
  - Inter-recommendation dependencies (prerequisites, enablers, data dependencies)
  - Strategic and resource conflicts (trade-off analysis, evidence comparison, resolution strategy)
  - Timeframe classification (Quick Wins, Short-Term Improvements, Strategic Initiatives)
  - Suggested deterministic execution sequencing with prerequisite topological unblocking
  - Portfolio change and obsolescence detection
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.smart_recommendations import SmartRecommendationItem


class RecommendationDependency(BaseModel):
    """Represents a directional dependency relationship between two recommendations."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str = Field(..., description="ID of the dependent downstream recommendation")
    depends_on_id: str = Field(..., description="ID of the upstream prerequisite recommendation")
    dependency_type: str = Field(
        ..., description="'PREREQUISITE' | 'ENABLER' | 'DATA_DEPENDENCY'"
    )
    reason: str = Field(..., description="Business rationale explaining why this dependency exists")
    is_satisfied: bool = Field(
        default=False, description="True if prerequisite recommendation is already Completed"
    )


class RecommendationConflict(BaseModel):
    """Represents a strategic, resource, or timing contradiction between two recommendations."""

    model_config = ConfigDict(extra="ignore")

    conflict_id: str
    rec_a_id: str
    rec_a_title: str
    rec_b_id: str
    rec_b_title: str
    conflict_type: str = Field(
        ...,
        description="'RESOURCE_COMPETITION' | 'STRATEGIC_CONTRADICTION' | 'TIMING_MISMATCH'",
    )
    description: str = Field(..., description="Explanation of why these actions pull in opposite directions")
    evidence_a: list[str] = Field(default_factory=list, description="Telemetry supporting recommendation A")
    evidence_b: list[str] = Field(default_factory=list, description="Telemetry supporting recommendation B")
    trade_off_analysis: str = Field(
        ..., description="Objective analysis of upside vs downside of choosing A over B"
    )
    recommended_resolution: str = Field(
        ..., description="Recommended sequence or operational guideline to resolve the conflict"
    )
    owner_decision_required: bool = Field(
        default=True, description="True if owner strategic choice is required"
    )


class SequencedAction(BaseModel):
    """One prioritized action in the suggested chronological execution sequence."""

    model_config = ConfigDict(extra="ignore")

    sequence_order: int = Field(..., ge=1, description="Sequential execution step (1, 2, 3...)")
    stage: str = Field(
        ...,
        description="'FIRST_ACTION' | 'SUPPORTING_ACTION' | 'DEPENDENT_ACTION' | 'STRATEGIC_INITIATIVE'",
    )
    recommendation_id: str
    title: str
    category: str
    priority: str
    timeframe_label: str = Field(..., description="'Days 1-14' | 'Days 15-45' | 'Days 46-90+'")
    why_this_order: str = Field(..., description="Explicit rationale for this exact position in sequence")
    unlocks_recommendation_ids: list[str] = Field(
        default_factory=list, description="Downstream actions unblocked once this completes"
    )
    status: str = "New"


class PortfolioObsoleteItem(BaseModel):
    """Recommendation retired or rendered obsolete due to shifting empirical evidence."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    title: str
    reason_obsolete: str = Field(
        ..., description="Empirical evidence shift explaining why this action is no longer applicable"
    )
    previous_status: str


class PortfolioSequenceUpdateRequest(BaseModel):
    """Payload for updating or manually reordering execution sequence."""

    model_config = ConfigDict(extra="forbid")

    ordered_recommendation_ids: list[str] = Field(
        ..., min_length=1, description="Custom ordered list of recommendation IDs"
    )


class RecommendationPortfolioResponse(BaseModel):
    """Unified Coherent Recommendation Portfolio Response."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    business_name: str
    generated_at: str
    portfolio_health_score: int = Field(
        default=75, ge=0, le=100, description="Overall coherence score of active action portfolio"
    )
    total_active_count: int

    # Segmented Portfolio Buckets
    critical_risks: list[SmartRecommendationItem] = Field(default_factory=list)
    quick_wins: list[SmartRecommendationItem] = Field(default_factory=list)
    short_term_improvements: list[SmartRecommendationItem] = Field(default_factory=list)
    strategic_initiatives: list[SmartRecommendationItem] = Field(default_factory=list)

    # Relationships & Resolution
    dependencies: list[RecommendationDependency] = Field(default_factory=list)
    conflicts: list[RecommendationConflict] = Field(default_factory=list)
    execution_sequence: list[SequencedAction] = Field(default_factory=list)
    obsolete_recommendations: list[PortfolioObsoleteItem] = Field(default_factory=list)

    # Resource & Trade-off Overview
    resource_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregate capital, headcount, and digital complexity summary",
    )

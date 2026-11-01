"""Pydantic schemas for Personalized Business DNA & Adaptive Recommendation Intelligence (Phase 5).

Covers:
  - Business maturity evaluation (Early Stage, Growing, Established)
  - Business goal taxonomy (Revenue, Profitability, Retention, Cost, Launch, Expansion, Digital, Efficiency)
  - Known constraint types (Budget, Workforce, Digital, Data, Operational, Time, Financials)
  - Adaptive recommendation explanations (Relevance, Triggers, Maturity suitability, Constraints, Ranking rationale)
  - Personalization profile & owner configuration controls
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class BusinessMaturityLevel(str, Enum):
    """Evaluated organizational maturity stages for MSMEs."""

    EARLY_STAGE = "Early Stage"
    GROWING = "Growing"
    ESTABLISHED = "Established"


class BusinessGoalType(str, Enum):
    """Canonical owner-selectable business goals."""

    INCREASE_REVENUE = "Increase Revenue"
    IMPROVE_PROFITABILITY = "Improve Profitability"
    RETAIN_CUSTOMERS = "Retain Customers"
    REDUCE_OPERATING_COSTS = "Reduce Operating Costs"
    LAUNCH_PRODUCTS = "Launch Products"
    EXPAND_MARKETS = "Expand into New Markets"
    IMPROVE_DIGITAL_PRESENCE = "Improve Digital Presence"
    IMPROVE_OPERATIONAL_EFFICIENCY = "Improve Operational Efficiency"


class BusinessConstraintType(str, Enum):
    """Canonical known resource constraints."""

    LIMITED_BUDGET = "Limited Budget"
    SMALL_WORKFORCE = "Small Workforce"
    LIMITED_DIGITAL_CAPABILITY = "Limited Digital Capability"
    LIMITED_HISTORICAL_DATA = "Limited Historical Data"
    OPERATIONAL_LIMITATIONS = "Operational Limitations"
    TIME_CONSTRAINTS = "Time Constraints"
    MISSING_FINANCIAL_INFO = "Missing Financial Information"


class EffortLevel(str, Enum):
    """Preferred implementation effort level."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class InvestmentLevel(str, Enum):
    """Preferred financial capital investment level."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AdaptiveFeedbackType(str, Enum):
    """Owner feedback types for recommendation learning."""

    RELEVANT = "Relevant"
    NOT_RELEVANT = "Not relevant"
    ALREADY_IMPLEMENTED = "Already implemented"
    NOT_FEASIBLE = "Not feasible"
    TOO_EXPENSIVE = "Too expensive"
    NEED_MORE_INFO = "Need more information"
    NOT_ALIGNED_WITH_GOAL = "Not aligned with my current goal"


class PersonalizationExplanation(BaseModel):
    """Detailed adaptive explanation answering why a recommendation fits this business."""

    model_config = ConfigDict(extra="ignore")

    why_relevant_to_this_business: str = Field(
        ..., description="Specific business condition and industry relevance"
    )
    triggering_conditions: list[str] = Field(
        default_factory=list, description="Verified facts that triggered this candidate"
    )
    maturity_suitability: str = Field(
        ..., description="Why this recommendation is suited to current business maturity"
    )
    constraints_considered: list[str] = Field(
        default_factory=list, description="Known constraints evaluated during feasibility"
    )
    missing_information: list[str] = Field(
        default_factory=list, description="Verified data gaps that would refine this recommendation"
    )
    ranking_rationale: str = Field(
        ..., description="Explanation of why this recommendation ranks above others"
    )
    goal_alignment_score: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Match score with owner goals (0-100)"
    )
    maturity_fit_score: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Suitability score for maturity level (0-100)"
    )
    preference_score: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Score based on feedback history and focus (0-100)"
    )
    constraint_penalty: float = Field(
        default=0.0, ge=0.0, le=60.0, description="Deduction applied due to resource constraints"
    )
    is_critical_risk_override: bool = Field(
        default=False,
        description="True if recommendation is a critical risk protected from personalization demotion",
    )


class RecommendationPersonalizationProfile(BaseModel):
    """Full structured personalization profile aggregating Business DNA, goals, and constraints."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    business_name: str
    industry: str
    sub_industry: Optional[str] = None
    business_type: Optional[str] = None
    dna_archetype: str = "Pragmatic Operator"
    dna_stage: str = "Growth"
    evaluated_maturity: BusinessMaturityLevel = BusinessMaturityLevel.GROWING
    maturity_drivers: list[str] = Field(default_factory=list)
    active_goals: list[str] = Field(default_factory=list)
    active_constraints: list[str] = Field(default_factory=list)
    preferred_effort_level: str = "Medium"
    preferred_investment_level: str = "Low"
    focus_areas: list[str] = Field(default_factory=list)
    feedback_summary: dict[str, int] = Field(default_factory=dict)
    source: str = "OWNER_DECLARED"
    updated_at: str


class PersonalizationSettingsUpdate(BaseModel):
    """Owner payload for updating goals, constraints, and strategic preferences."""

    model_config = ConfigDict(extra="forbid")

    goals: list[str] = Field(
        default_factory=list, description="List of active BusinessGoalType strings"
    )
    constraints: list[str] = Field(
        default_factory=list, description="List of active BusinessConstraintType strings"
    )
    preferred_effort_level: Optional[str] = Field(
        default="Medium", description="Low, Medium, or High"
    )
    preferred_investment_level: Optional[str] = Field(
        default="Low", description="Low, Medium, or High"
    )
    focus_areas: Optional[list[str]] = Field(
        default_factory=list, description="Optional target business functions"
    )

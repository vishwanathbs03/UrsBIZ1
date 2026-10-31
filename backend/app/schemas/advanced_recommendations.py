"""Pydantic v2 schemas for Advanced AI Business Recommendation Intelligence (Phase 5).

Covers:
  - Multi-Signal Cross-Correlation Insights
  - AI Root Cause Analysis (Symptoms, Verified Factors, Plausible Causes, Unknowns)
  - Opportunity Discovery across 10 strategic categories
  - Next Best Action Prioritization & Cost of Delay
  - 3-Horizon Personalized Growth Strategy (0-30d, 31-90d, 3-12m)
  - Deterministic What-If Scenario Simulations
  - Owner Feedback & Suppression
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class CrossSignalInsight(BaseModel):
    """Insight produced by correlating multiple disparate business signals."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    severity: str = Field(..., description="'Critical' | 'High' | 'Medium' | 'Low'")
    pattern_type: str = Field(..., description="e.g. concentration_churn_risk, capacity_bottleneck")
    signals_combined: list[str] = Field(default_factory=list, description="The distinct data signals correlated")
    business_implication: str = Field(..., description="Direct business risk or opportunity")
    recommended_action: str = Field(..., description="Immediate practical mitigation or lever")
    evidence_strength: str = Field(..., description="'Strong Evidence' | 'Moderate Evidence' | 'Limited Evidence'")
    linked_recommendation_id: Optional[str] = None


class RootCauseAnalysisItem(BaseModel):
    """Diagnostic breakdown distinguishing symptoms, verified data, hypotheses, and unknowns."""

    model_config = ConfigDict(extra="ignore")

    id: str
    symptom: str = Field(..., description="Observed symptom from business metrics")
    verified_factors: list[str] = Field(default_factory=list, description="Corroborated by actual system data")
    plausible_causes: list[str] = Field(default_factory=list, description="Reasonable operational explanations")
    data_gaps_and_unknowns: list[str] = Field(
        default_factory=list, description="Gaps in data that require business owner confirmation"
    )
    urgency: str = Field(..., description="'Immediate' | 'Near-term' | 'Watch'")


class OpportunityItem(BaseModel):
    """Proactive growth opportunity surfaced from business data."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    category: str = Field(..., description="One of the 10 strategic categories")
    rationale: str = Field(..., description="Why this opportunity exists now")
    evidence_strength: str = Field(..., description="'Strong Evidence' | 'Moderate Evidence' | 'Limited Evidence'")
    feasibility: str = Field(..., description="'High' | 'Medium' | 'Low'")
    estimated_impact_description: str = Field(..., description="Clearly labeled projection")
    first_step: str = Field(..., description="Concrete zero-barrier first step")
    timeframe: str = Field(..., description="Expected timeline (e.g. '15-30 days')")


class NextBestAction(BaseModel):
    """Action prioritized for immediate execution with cost-of-delay rationale."""

    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    title: str
    category: str
    priority_score: int = Field(..., ge=0, le=100)
    priority: str = Field(..., description="'Critical' | 'High' | 'Medium' | 'Low'")
    why_now: str = Field(..., description="Why this action is prioritized above others right now")
    cost_of_delay: str = Field(..., description="Risks and lost revenue/efficiency if delayed")
    effort_level: str = Field(..., description="'Low' | 'Medium' | 'High'")
    time_to_value: str = Field(..., description="Estimated time until initial results are visible")
    first_immediate_step: str = Field(..., description="Concrete first execution step")
    source_modules: list[str] = Field(default_factory=list)


class NextBestActionResponse(BaseModel):
    """Tiered action recommendations with cost-of-delay rationale."""

    model_config = ConfigDict(extra="ignore")

    top_priority_action: Optional[NextBestAction] = None
    next_three_actions: list[NextBestAction] = Field(default_factory=list)
    long_term_initiatives: list[NextBestAction] = Field(default_factory=list)


class GrowthMilestone(BaseModel):
    """Milestone checkpoint in a horizon plan."""

    model_config = ConfigDict(extra="ignore")

    milestone: str
    target_date_window: str
    metric_to_track: str


class GrowthHorizonPlan(BaseModel):
    """Growth plan for a specific time horizon."""

    model_config = ConfigDict(extra="ignore")

    horizon: str = Field(..., description="'0-30 Days' | '31-90 Days' | '3-12 Months'")
    title: str
    focus: str
    actions: list[str] = Field(default_factory=list)
    milestones: list[GrowthMilestone] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)


class PersonalizedGrowthStrategy(BaseModel):
    """Comprehensive 3-horizon growth strategy for the business."""

    model_config = ConfigDict(extra="ignore")

    business_name: str
    industry: str
    strategy_summary: str
    is_ai_generated: bool
    horizons: list[GrowthHorizonPlan] = Field(default_factory=list)
    critical_success_factors: list[str] = Field(default_factory=list)


class ScenarioSimulationRequest(BaseModel):
    """User input for deterministic What-If business scenario explorer."""

    model_config = ConfigDict(extra="ignore")

    sales_growth_pct: float = Field(0.0, ge=-50.0, le=100.0, description="Hypothetical % change in monthly sales")
    repeat_customer_rate_improvement_pct: float = Field(
        0.0, ge=0.0, le=50.0, description="Hypothetical % improvement in repeat customer revenue"
    )
    expense_reduction_pct: float = Field(
        0.0, ge=0.0, le=30.0, description="Hypothetical % reduction in operating expenses"
    )
    concentration_reduction_pct: float = Field(
        0.0, ge=0.0, le=50.0, description="Hypothetical % reduction in top-customer dependency"
    )


class ScenarioMetricResult(BaseModel):
    """Individual projected metric comparison in simulation."""

    model_config = ConfigDict(extra="ignore")

    metric_name: str
    baseline_value: float
    projected_value: float
    delta_value: float
    unit: str
    formula_explanation: str


class ScenarioSimulationResponse(BaseModel):
    """Output of deterministic What-If simulation."""

    model_config = ConfigDict(extra="ignore")

    baseline_revenue: float
    projected_revenue: float
    estimated_gross_profit_change: float
    metrics: list[ScenarioMetricResult] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    projection_disclaimer: str = (
        "Hypothetical mathematical projection based on reported business baseline. "
        "Does not constitute guaranteed revenue, profit, or retention."
    )


class RecommendationFeedbackCreate(BaseModel):
    """Payload for submitting owner feedback on a recommendation."""

    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    feedback_type: str = Field(
        ...,
        description="'Useful' | 'Not relevant' | 'Already implemented' | 'Not feasible' | 'Need more explanation'",
    )
    outcome_notes: Optional[str] = None


class RecommendationFeedbackResponse(BaseModel):
    """Response confirming recorded feedback."""

    model_config = ConfigDict(extra="ignore")

    id: int
    business_id: int
    recommendation_id: str
    feedback_type: str
    suppress_recommendation: bool
    outcome_notes: Optional[str] = None
    created_at: str


class AdvancedRecommendationsOverviewResponse(BaseModel):
    """Aggregated response containing complete advanced recommendation intelligence."""

    model_config = ConfigDict(extra="ignore")

    business_id: int
    business_name: str
    generated_at: str
    next_best_action: NextBestActionResponse
    multi_signal_insights: list[CrossSignalInsight] = Field(default_factory=list)
    root_cause_analyses: list[RootCauseAnalysisItem] = Field(default_factory=list)
    opportunities: list[OpportunityItem] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class RecommendationAskRequest(BaseModel):
    """Payload for asking natural language questions to the AI Recommendation Consultant."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(..., min_length=2, description="Natural language business question")
    session_id: Optional[str] = Field(None, description="Optional conversational session ID")


class CalculationStep(BaseModel):
    """Specific verifiable calculation demonstrating reasoning lineage."""

    model_config = ConfigDict(extra="ignore")

    name: str
    formula: str
    result: str


class SituationalRecommendation(BaseModel):
    """Recommendation dynamically synthesized for the specific business situation."""

    model_config = ConfigDict(extra="ignore")

    title: str
    category: str
    priority: str = Field(..., description="'Critical' | 'High' | 'Medium' | 'Low'")
    situational_rationale: str
    action_steps: list[str] = Field(default_factory=list)
    timeframe: str
    cost_of_delay: str


class RecommendationAskResponse(BaseModel):
    """Comprehensive natural-language answer with evidence, calculations, gaps, and follow-ups."""

    model_config = ConfigDict(extra="ignore")

    question: str
    intent: str
    direct_answer: str
    evidence_points: list[str] = Field(default_factory=list)
    calculations: list[CalculationStep] = Field(default_factory=list)
    situational_recommendations: list[SituationalRecommendation] = Field(default_factory=list)
    data_limitations_and_gaps: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    is_ai_generated: bool
    generated_at: str

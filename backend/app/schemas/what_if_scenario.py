"""Pydantic v2 schemas for What-If Scenario Simulator (Phase 6.19 Extension).

Strict schemas for:
  - Scenario simulation requests with levers and assumptions overrides
  - Multi-case outcome projections (Base Case, Worst Case, Best Case)
  - Explicit assumption provenance and missing data disclosures
  - Scenario persistence and comparison
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ScenarioType = Literal[
    "sales_drop",
    "supplier_cost_increase",
    "customer_churn",
    "hiring_expansion",
    "price_elasticity",
    "collection_delay",
    "custom",
]

MANDATORY_SCENARIO_DISCLAIMER = "Illustrative scenario estimate — not a guaranteed prediction."


class ScenarioParameterIn(BaseModel):
    """Input levers for simulating hypothetical shocks and opportunities."""

    model_config = ConfigDict(extra="forbid")

    scenario_type: ScenarioType
    sales_volume_delta_pct: float = Field(
        default=0.0,
        ge=-100.0,
        le=500.0,
        description="Percentage change in sales volume/demand (e.g. -15.0 for a 15% drop)",
    )
    price_delta_pct: float = Field(
        default=0.0,
        ge=-90.0,
        le=500.0,
        description="Percentage change in selling price (e.g. +5.0 for a 5% increase)",
    )
    cogs_delta_pct: float = Field(
        default=0.0,
        ge=-90.0,
        le=500.0,
        description="Percentage change in cost of goods sold / supplier prices (e.g. +10.0 for 10% increase)",
    )
    opex_delta_inr: float = Field(
        default=0.0,
        description="Monthly operating expense change in INR (e.g. +45000 for hiring a new salesperson)",
    )
    dso_stretch_days: int = Field(
        default=0,
        ge=-90,
        le=180,
        description="Change in Days Sales Outstanding / collection delay (e.g. +30 for 30-day delay)",
    )
    credit_sales_ratio: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Portion of sales on credit terms (0.0 to 1.0, default 0.70). Non-credit sales are instant cash/UPI/card.",
    )
    price_elasticity_coefficient: float | None = Field(
        default=None,
        ge=-10.0,
        le=0.0,
        description="Price elasticity of demand (typically negative, e.g. -1.2). If None, calculated from volume & price parameters.",
    )
    lost_customer_id: str | None = Field(
        default=None,
        description="Identifier of a specific customer at risk of churning",
    )
    lost_customer_revenue_inr: float | None = Field(
        default=None,
        ge=0.0,
        description="Explicit revenue of churned customer, if overriding automated calculation",
    )
    assumptions_overrides: dict[str, float] | None = Field(
        default=None,
        description="Optional overrides for baseline benchmarks (e.g. gross_margin_pct, cash_balance_inr)",
    )


class AssumptionItem(BaseModel):
    """Individual assumption with transparency into its source and data classification."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | str
    unit: str
    source: Literal[
        "Observed Fact",
        "Industry Benchmark",
        "User Override",
        "Planning Assumption (Editable)",
    ]
    note: str


class ScenarioCaseResult(BaseModel):
    """Projected financial metrics for a single scenario branch (Base, Worst, or Best)."""

    model_config = ConfigDict(extra="forbid")

    case_label: Literal["Base Case", "Conservative / Worst Case", "Optimistic / Best Case"]
    projected_revenue_inr: float
    revenue_delta_inr: float
    revenue_delta_pct: float
    projected_cogs_inr: float
    projected_gross_profit_inr: float
    gross_profit_delta_inr: float
    gross_margin_pct: float
    projected_opex_inr: float
    projected_operating_profit_inr: float
    operating_profit_delta_inr: float
    cash_runway_days_estimated: int | None
    cash_runway_days_delta: int | None
    break_even_revenue_inr: float | None


class MitigationAction(BaseModel):
    """Actionable mitigation step to hedge against scenario risks."""

    model_config = ConfigDict(extra="forbid")

    title: str
    impact: str
    timeframe: str
    feasibility: Literal["High", "Medium", "Low"]


class SimulationResult(BaseModel):
    """Complete multi-case simulation payload."""

    model_config = ConfigDict(extra="forbid")

    scenario_type: ScenarioType
    title: str
    baseline_metrics: dict[str, Any]
    assumptions_applied: list[AssumptionItem]
    missing_data_disclosures: list[str]
    cases: list[ScenarioCaseResult]
    ai_executive_summary: str
    vulnerabilities_exposed: list[str]
    mitigation_actions: list[MitigationAction]
    disclaimer: str = MANDATORY_SCENARIO_DISCLAIMER


class ScenarioSimulateRequest(BaseModel):
    """Request body for POST /api/v1/scenarios/simulate."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Hypothetical Scenario", min_length=1, max_length=200)
    parameters: ScenarioParameterIn


class ScenarioSaveRequest(BaseModel):
    """Request body for saving a simulated scenario."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    scenario_type: ScenarioType
    description: str | None = Field(default=None, max_length=2000)
    parameters: ScenarioParameterIn
    tags: list[str] | None = Field(default=None, max_length=10)


class ScenarioUpdateRequest(BaseModel):
    """Request body for updating a saved scenario."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    parameters: ScenarioParameterIn | None = None
    tags: list[str] | None = None


class ScenarioOut(BaseModel):
    """Output representation of a saved scenario."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    business_id: int
    owner_id: int
    title: str
    scenario_type: str
    description: str | None
    baseline_metrics: dict[str, Any]
    parameters: dict[str, Any]
    projection_result: dict[str, Any]
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime


class ScenarioListResponse(BaseModel):
    """List response envelope."""

    model_config = ConfigDict(extra="forbid")

    items: list[ScenarioOut]
    total: int


class ScenarioCompareRequest(BaseModel):
    """Request body for comparing multiple saved scenarios."""

    model_config = ConfigDict(extra="forbid")

    scenario_ids: list[int] = Field(min_length=2, max_length=3)


class ScenarioComparisonItem(BaseModel):
    """Side-by-side comparison summary for one scenario."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    scenario_type: str
    base_case_revenue_delta_inr: float
    base_case_revenue_delta_pct: float
    base_case_profit_delta_inr: float
    base_case_runway_delta_days: int | None
    top_vulnerability: str
    created_at: datetime


class ScenarioCompareResponse(BaseModel):
    """Side-by-side comparison response."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[ScenarioComparisonItem]
    comparison_summary: str
    disclaimer: str = MANDATORY_SCENARIO_DISCLAIMER

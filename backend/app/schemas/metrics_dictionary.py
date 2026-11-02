"""Pydantic v2 schemas for Business Metrics Dictionary and Calculation Explorer (Phase 6.21 Extension).

Ensures 100% calculation transparency across UrsBiz:
  - Formal definitions and business interpretations
  - Mathematical formulas and measurement units
  - Observation period rules and exclusion criteria (e.g. duplicate exclusion)
  - Known limitations and industry benchmarks
  - Step-by-step arithmetic calculation explorer for active business data
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

MetricCategory = Literal["financial", "sales", "customer", "operations", "data_integrity"]


class MetricVariable(BaseModel):
    """Input variable required by the mathematical formula."""

    model_config = ConfigDict(extra="forbid")

    name: str
    symbol: str
    description: str
    source_table: str
    data_classification: Literal["Observed Fact", "Calculated Metric", "User-Entered", "Benchmark Assumption"]


class CalculationStep(BaseModel):
    """Individual mathematical operation in step-by-step formula execution."""

    model_config = ConfigDict(extra="forbid")

    step_number: int
    step_title: str
    description: str
    formula_snippet: str
    input_values: dict[str, Any]
    output_value: Any


class MetricDefinition(BaseModel):
    """Canonical dictionary entry defining a business metric."""

    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    category: MetricCategory
    formal_definition: str
    business_interpretation: str
    formula: str
    unit: str
    observation_period_rule: str
    exclusion_rules: list[str]
    known_limitations: list[str]
    industry_benchmarks: dict[str, str]
    input_variables: list[MetricVariable]


class MetricExplorerResult(BaseModel):
    """Dynamic step-by-step calculation trace for the active business."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    title: str
    category: str
    business_id: int
    current_value: float | int | str | None
    formatted_current_value: str
    unit: str
    formula: str
    has_live_data: bool
    data_classification: str
    data_freshness: str
    steps: list[CalculationStep]
    provenance_note: str
    disclaimer: str = (
        "Calculation Explorer displays deterministic step-by-step arithmetic based on verified business records. "
        "Formulas are evaluated without AI hallucination."
    )


class MetricDictionaryResponse(BaseModel):
    """Complete Metrics Dictionary listing."""

    model_config = ConfigDict(extra="forbid")

    metrics: list[MetricDefinition]
    total: int
    categories: list[str]
    version: str = "2026.1"

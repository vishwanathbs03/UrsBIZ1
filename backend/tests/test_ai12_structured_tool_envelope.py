"""Tests for SPRINT AI-12 — StructuredToolEnvelope derivation.

Five tests covering the five most common tool results
(health_score, kpi, finance, schemes_sprint16,
predictive_sprint14). The factory ``envelope_from_tool_result``
is a pure derivation — single-metric payloads lift metric +
value, multi-metric payloads return ``metric=None``.
"""
from __future__ import annotations

from app.services.ai.reasoning.structured_envelope import (
    StructuredToolEnvelope,
    envelope_from_tool_result,
)
from app.services.ai.reasoning.tool_selector import ToolResult


def _result(payload):
    return ToolResult(service_name="x", status="ok", payload=payload)


class TestStructuredToolEnvelope:

    def test_health_score_lifts_metric_and_value(self) -> None:
        env = envelope_from_tool_result(
            "health_score",
            _result({"score": 72, "unit": "/100"}),
            owner_id=42,
        )
        assert env.metric == "score"
        assert env.value == 72
        assert env.unit == "/100"
        assert env.calculation_id == "health_score_42"

    def test_finance_lifts_amount_and_formula(self) -> None:
        env = envelope_from_tool_result(
            "finance",
            _result({"amount": 1500.0, "unit": "INR", "formula": "x*0.1"}),
            owner_id=7,
        )
        assert env.metric == "amount"
        assert env.value == 1500.0
        assert env.unit == "INR"
        assert env.calculation_id == "finance_7"

    def test_multi_metric_returns_none_metric(self) -> None:
        env = envelope_from_tool_result(
            "schemes_sprint16",
            _result({"schemes": [{"a": 1}, {"b": 2}]}),
            owner_id=None,
        )
        # multi-metric → metric/value are None by design
        assert env.metric is None
        assert env.value is None
        # Without owner_id the calculation_id collapses to the tool name.
        assert env.calculation_id == "schemes_sprint16"

    def test_assumptions_and_limitations_extracted(self) -> None:
        env = envelope_from_tool_result(
            "predictive_sprint14",
            _result({
                "value": 1.5,
                "unit": "%",
                "assumptions": ["cost stable"],
                "limitations": ["demand may shift"],
            }),
            owner_id=1,
        )
        assert env.assumptions == ("cost stable",)
        assert env.limitations == ("demand may shift",)

    def test_input_evidence_ids_passed_through(self) -> None:
        env = envelope_from_tool_result(
            "kpi",
            _result({"value": 50, "unit": "INR"}),
            input_evidence_ids=("kpi_x", "kpi_y"),
            owner_id=3,
        )
        assert env.input_evidence_ids == ("kpi_x", "kpi_y")
        assert env.calculation_id == "kpi_3"

    def test_to_dict_serialises_all_fields(self) -> None:
        env = envelope_from_tool_result(
            "health_score",
            _result({"score": 80, "unit": "/100"}),
            owner_id=4,
        )
        d = env.to_dict()
        for k in (
            "tool_name", "metric", "value", "unit", "formula",
            "input_evidence_ids", "calculation_id",
            "assumptions", "limitations",
        ):
            assert k in d
        assert d["tool_name"] == "health_score"

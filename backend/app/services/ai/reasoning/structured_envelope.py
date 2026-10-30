"""StructuredToolEnvelope — SPRINT AI-12 Universal Reasoning Layer.

The envelope is a uniform per-tool output shape with the eight
fields the AI-12 brief enumerates:

  * ``tool_name`` — matches ``ToolResult.service_name``.
  * ``metric`` — best-effort single-metric label (e.g. ``"health_score"``, ``"gross_margin"``).
  * ``value`` — the metric's single value, or ``None`` when the
    tool returned a multi-fact payload.
  * ``unit`` — ``"%``, ``"INR"``, ``"raw"`` etc.
  * ``formula`` — a one-line formula string when the tool is
    calculation-derived; otherwise empty.
  * ``input_evidence_ids`` — evidence IDs the tool consumed.
  * ``calculation_id`` — stable identifier for the deterministic
    computation (matches ``recommendation_id`` when the tool is
    a recommendation engine, or ``"<tool>_<owner_id>"`` when
    it's a profile-level service).
  * ``assumptions`` / ``limitations`` — explicit disclosures.
  * ``raw_payload`` — the original ``ToolResult.payload`` so
    downstream consumers can recover the full shape.

The envelope is derived deterministically from the existing
``ToolResult.payload`` — no tool-executor change is needed. The
AI-12 brief is explicit: "Start with the four that AI-12 will
likely need: Finance / Forecast / Schemes / Benchmark"; we
extend coverage to all 19 tools via the introspective factory
``envelope_from_tool_result``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai.reasoning.tool_selector import ToolResult


# Tools whose ``payload`` shape is single-metric-key / value /
# unit (we recognise metric + unit + formula heuristically by
# known-key scan). Everything else is multi-fact; those surfaces
# a thin envelope (``metric=None, value=None``) so the renderer
# never fabricates a single number.
_SINGLE_METRIC_TOOLS = {
    "health_score": "score",
    "kpi": "value",
    "finance": "amount",
    "compliance": "score",
    "readiness": "overall_score",
    "predictive_sprint14": "value",
}

_FORMULA_BY_TOOL: dict[str, str] = {
    "health_score": "weighted_sum across 6 components (Profile 30 + Business Info 15 + Products 15 + Team 10 + Financial 20 + Online Presence 10)",
    "finance": "deterministic FinanceService pipeline (aggregator → ROI → projection → summary)",
    "predictive_sprint14": "Sprint 14 predictive pipeline (revenue + growth + future-risk)",
}


def envelope_from_tool_result(
    tool_name: str,
    result: "ToolResult",
    *,
    input_evidence_ids: tuple[str, ...] = (),
    owner_id: int | None = None,
) -> "StructuredToolEnvelope":
    """Derive a StructuredToolEnvelope from a ToolResult.

    Pure function — same inputs ⇒ same outputs. Multi-metric
    payloads (e.g. ``schemes_sprint16``, ``compare_recommendations``)
    return ``metric=None`` + ``value=None`` so the renderer
    cannot accidentally lift a wrong key.

    Side-effect free. No LLM access. No I/O.
    """
    metric: str | None = None
    value: Any = None
    unit: str | None = None
    formula: str = ""
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    raw_payload: Any = None

    payload = result.payload
    if isinstance(payload, dict):
        raw_payload = payload
        metric_key = _SINGLE_METRIC_TOOLS.get(tool_name)
        if metric_key and metric_key in payload:
            metric = metric_key
            value = payload.get(metric_key)
            unit = payload.get("unit") or payload.get("units") or None
            formula = _FORMULA_BY_TOOL.get(tool_name, "") or payload.get("formula", "") or ""
        # Extract common disclosure fields if the engine supplied
        # them. ``assumptions`` and ``limitations`` are tolerant
        # of missing keys — both default to empty tuple.
        if isinstance(payload.get("assumptions"), (list, tuple)):
            assumptions = tuple(str(a) for a in payload["assumptions"])
        if isinstance(payload.get("limitations"), (list, tuple)):
            limitations = tuple(str(l) for l in payload["limitations"])
    else:
        raw_payload = payload

    # Always record calculation_id even when metric is None —
    # downstream traceability wants a stable identifier per tool call.
    if owner_id is not None:
        calculation_id = f"{tool_name}_{owner_id}"
    else:
        calculation_id = tool_name

    return StructuredToolEnvelope(
        tool_name=tool_name,
        metric=metric,
        value=value,
        unit=unit,
        formula=formula,
        input_evidence_ids=tuple(input_evidence_ids),
        calculation_id=calculation_id,
        assumptions=assumptions,
        limitations=limitations,
        raw_payload=raw_payload,
    )


@dataclass(frozen=True)
class StructuredToolEnvelope:
    """Uniform per-tool output envelope — SPRINT AI-12.

    See module docstring for the full contract. The dataclass
    is frozen; ``to_dict()`` is the JSON-serialisable view
    consumed by the wire projection.
    """

    tool_name: str
    metric: str | None = None
    value: Any = None
    unit: str | None = None
    formula: str = ""
    input_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    calculation_id: str | None = None
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    raw_payload: Any = None

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "formula": self.formula,
            "input_evidence_ids": list(self.input_evidence_ids),
            "calculation_id": self.calculation_id,
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
        }

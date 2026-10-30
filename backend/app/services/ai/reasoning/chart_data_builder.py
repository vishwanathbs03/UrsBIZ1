"""Sprint AI-15 — chart data builder.

Given a :class:`VisualizationPlan` and the deterministic inputs
(envelopes + evidence graph + assistant context), return a
:class:`ChartPayload` with the chart-ready data shape + full
provenance. Pure function. The LLM has no path into the builder.

The builder NEVER invents values. When the deterministic source
cannot produce non-empty data, the builder returns a
:class:`ChartPayload` with ``empty_reason`` set so the renderer
can show the brief-mandated "Not enough business data to show
this visualization." notice instead of an empty chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Wire shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChartPayload:
    """Chart-ready payload + provenance.

    Attributes
    ----------
    chart_kind
        The :class:`ChartKind` literal.
    data
        Chart-ready dict the renderer consumes. Values are
        scalars or short lists/objects. Empty ``{}`` when the
        builder could not resolve data.
    source_evidence_ids
        Evidence IDs the chart reads from.
    calculation_ids
        CalculationNode IDs the chart reads from.
    assumptions
        Scenario / forecast assumptions the chart relies on.
    limitations
        Known limitations.
    confidence
        Server-owned 0..1. ``min`` over source confidences.
    empty_reason
        Non-empty when ``data`` is ``{}``. Renderer surfaces
        this as the "Not enough business data" notice.
    missing_fields
        Field names the planner tried but could not resolve.
    """

    chart_kind: Any  # ChartKind; kept Any to avoid import cycle
    data: dict = field(default_factory=dict)
    source_evidence_ids: tuple[str, ...] = ()
    calculation_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: float = 0.0
    empty_reason: str = ""
    missing_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """JSON-safe wire representation."""
        kind = self.chart_kind
        kind_value = getattr(kind, "value", str(kind))
        return {
            "chart_kind": kind_value,
            "data": dict(self.data),
            "source_evidence_ids": list(self.source_evidence_ids),
            "calculation_ids": list(self.calculation_ids),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "confidence": float(self.confidence),
            "empty_reason": str(self.empty_reason or ""),
            "missing_fields": list(self.missing_fields),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_EMPTY_REASON = "Not enough business data to show this visualization."


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if obj is not None else default


def _coerce_number(value: Any) -> float | None:
    """Return a float when the value is numeric, else None.

    The builder never invents a number — if the envelope value is
    missing or non-numeric, we return ``None`` so the caller can
    decide whether to render a chart at all.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # bool is technically int but never a chart input
    if isinstance(value, (int, float)):
        f = float(value)
        if f != f:  # NaN guard
            return None
        return f
    if isinstance(value, str):
        try:
            f = float(value.replace(",", "").strip())
            return f
        except (TypeError, ValueError):
            return None
    return None


def _by_metric(envelopes: tuple) -> dict[str, tuple]:
    """Index envelopes by metric for O(1) lookup."""
    out: dict[str, list] = {}
    for env in envelopes or ():
        m = _get(env, "metric", None)
        if not m:
            continue
        out.setdefault(str(m), []).append(env)
    return {k: tuple(v) for k, v in out.items()}


def _first(by: dict, *metrics: str):
    for m in metrics:
        items = by.get(m, ())
        if items:
            return items[0]
    return None


def _provenance(envelope: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(source_evidence_ids, calculation_ids)`` for an envelope."""
    if envelope is None:
        return (), ()
    src = tuple(str(x) for x in (_get(envelope, "input_evidence_ids", ()) or ()))
    calc_id = _get(envelope, "calculation_id", "")
    calc = tuple([str(calc_id)]) if calc_id else ()
    return src, calc


def _confidence(envelope: Any, default: float = 1.0) -> float:
    try:
        c = float(_get(envelope, "confidence", default) or default)
    except (TypeError, ValueError):
        c = default
    if c < 0.0:
        c = 0.0
    if c > 1.0:
        c = 1.0
    return c


def _empty(
    chart_kind: Any,
    *,
    envelope: Any = None,
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
    missing_fields: tuple[str, ...] = (),
    empty_reason: str = _EMPTY_REASON,
) -> ChartPayload:
    src, calc = _provenance(envelope)
    conf = _confidence(envelope, 0.0)
    return ChartPayload(
        chart_kind=chart_kind,
        data={},
        source_evidence_ids=src,
        calculation_ids=calc,
        assumptions=assumptions,
        limitations=limitations,
        confidence=conf,
        empty_reason=empty_reason,
        missing_fields=missing_fields,
    )


# ---------------------------------------------------------------------------
# Per-chart-kind builders
# ---------------------------------------------------------------------------


def _build_kpi(by: dict, context: Any) -> ChartPayload:
    """Single-value headline. Reads from `amount` / `score` / `value`."""
    env = _first(by, "amount", "score", "value")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "KPI"),
            missing_fields=("amount", "score", "value"),
        )
    value = _coerce_number(_get(env, "value", None))
    if value is None:
        return _empty(
            _get(_module_chart_kinds(), "KPI"),
            envelope=env,
            missing_fields=("amount", "score", "value"),
        )
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "KPI"),
        data={
            "label": str(_get(env, "metric", "metric")),
            "value": value,
            "unit": str(_get(env, "unit", "") or ""),
            "title": "Key metric",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(env),
    )


def _build_progress(by: dict, context: Any) -> ChartPayload:
    """current vs target."""
    growth = _first(by, "growth")
    if growth is None:
        # Fall back to scenario envelope (it carries a baseline).
        growth = _first(by, "scenario")
    if growth is None:
        return _empty(
            _get(_module_chart_kinds(), "PROGRESS"),
            missing_fields=("growth.current", "growth.target"),
        )
    value = _get(growth, "value", None)
    current = None
    target = None
    if isinstance(value, dict):
        current = _coerce_number(value.get("current"))
        target = _coerce_number(value.get("target"))
    if current is None or target is None:
        return _empty(
            _get(_module_chart_kinds(), "PROGRESS"),
            envelope=growth,
            missing_fields=("current", "target"),
        )
    src, calc = _provenance(growth)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "PROGRESS"),
        data={
            "label": "Revenue target",
            "current": current,
            "target": target,
            "unit": str(_get(growth, "unit", "INR") or "INR"),
            "title": "Revenue progress",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(growth),
    )


def _build_comparison(by: dict, context: Any) -> ChartPayload:
    env = _first(by, "compare")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "COMPARISON"),
            missing_fields=("compare.left", "compare.right"),
        )
    value = _get(env, "value", None)
    left = None
    right = None
    if isinstance(value, dict):
        left = value.get("left")
        right = value.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        return _empty(
            _get(_module_chart_kinds(), "COMPARISON"),
            envelope=env,
            missing_fields=("left", "right"),
        )
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "COMPARISON"),
        data={
            "left": dict(left),
            "right": dict(right),
            "title": "Strategy comparison",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(env),
    )


def _build_trend(by: dict, context: Any) -> ChartPayload:
    env = _first(by, "forecast")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "TREND"),
            missing_fields=("forecast.series", "forecast.points"),
        )
    value = _get(env, "value", None)
    points = None
    if isinstance(value, dict):
        raw = value.get("series") or value.get("points") or value.get("forecast")
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            points = []
            for p in raw:
                if isinstance(p, dict) and "x" in p and "y" in p:
                    y = _coerce_number(p.get("y"))
                    if y is None:
                        continue
                    points.append({"x": str(p["x"]), "y": y})
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    y = _coerce_number(p[1])
                    if y is None:
                        continue
                    points.append({"x": str(p[0]), "y": y})
    if not points or len(points) < 2:
        return _empty(
            _get(_module_chart_kinds(), "TREND"),
            envelope=env,
            missing_fields=("series", "points"),
            limitations=(
                "Trend requires ≥2 time-series points; the engine "
                "never invents trend points.",
            ),
        )
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "TREND"),
        data={
            "label": "Revenue trend",
            "points": points,
            "unit": str(_get(env, "unit", "INR") or "INR"),
            "title": "Revenue trend",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        assumptions=tuple(
            str(a) for a in (_get(env, "assumptions", ()) or ())
        ),
        confidence=_confidence(env),
    )


def _build_scenario(by: dict, context: Any) -> ChartPayload:
    env = _first(by, "scenario")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "SCENARIO"),
            missing_fields=("scenario.baseline", "scenario.changed_input"),
        )
    value = _get(env, "value", None)
    baseline = None
    changed = None
    effect = None
    if isinstance(value, dict):
        baseline = _coerce_number(value.get("baseline"))
        changed = _coerce_number(
            value.get("changed_input") or value.get("delta")
        )
        effect = _coerce_number(value.get("estimated_effect") or value.get("output"))
    if baseline is None or changed is None or effect is None:
        return _empty(
            _get(_module_chart_kinds(), "SCENARIO"),
            envelope=env,
            missing_fields=("baseline", "changed_input", "estimated_effect"),
        )
    src, calc = _provenance(env)
    conf = min(_confidence(env, 0.7), 0.7)  # scenarios never high confidence
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "SCENARIO"),
        data={
            "baseline": baseline,
            "changed_input": changed,
            "estimated_effect": effect,
            "unit": str(_get(env, "unit", "") or ""),
            "label": "Scenario estimate",
            "title": "Scenario estimate",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        assumptions=tuple(
            str(a) for a in (_get(env, "assumptions", ()) or ())
        ),
        limitations=(
            "Treated as a scenario, not a guaranteed prediction.",
        ),
        confidence=conf,
    )


def _build_risk(by: dict, context: Any) -> ChartPayload:
    env = _first(by, "risks")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "RISK"),
            missing_fields=("risks.severity", "risks.label"),
        )
    value = _get(env, "value", None)
    segments: list[dict] = []
    if isinstance(value, dict):
        # Expected shape: {"items": [{"label", "severity"}, ...]} or
        # {"risks": [{"label", "severity"}, ...]}.
        items = value.get("items") or value.get("risks")
        if isinstance(items, (list, tuple)):
            for r in items:
                if not isinstance(r, dict):
                    continue
                label = str(r.get("label") or r.get("title") or "risk")
                severity = str(r.get("severity") or r.get("level") or "")
                tone = (
                    "danger"
                    if severity.lower() in ("high", "critical")
                    else "warn"
                    if severity.lower() in ("medium", "moderate")
                    else "info"
                )
                # Server owns the value — we use a deterministic 1/2/3
                # bucket weight rather than the LLM's number.
                weight = (
                    3
                    if tone == "danger"
                    else 2
                    if tone == "warn"
                    else 1
                )
                segments.append(
                    {
                        "label": label,
                        "value": weight,
                        "tone": tone,
                    }
                )
    if not segments:
        return _empty(
            _get(_module_chart_kinds(), "RISK"),
            envelope=env,
            missing_fields=("risks.items",),
        )
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "RISK"),
        data={
            "segments": segments,
            "title": "Risk distribution",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(env),
    )


def _build_composition(by: dict, context: Any) -> ChartPayload:
    """Supplier concentration. Source: risks envelope with a
    `concentration` sub-field OR context.supplier_dependencies."""
    env = _first(by, "risks")
    slices: list[dict] = []
    if env is not None:
        value = _get(env, "value", None)
        if isinstance(value, dict):
            conc = value.get("concentration") or value.get("supplier_share")
            if isinstance(conc, (list, tuple)):
                for c in conc:
                    if not isinstance(c, dict):
                        continue
                    label = str(c.get("label") or c.get("supplier") or "")
                    share = _coerce_number(c.get("share") or c.get("value"))
                    if not label or share is None:
                        continue
                    slices.append({"label": label, "value": share})
    if not slices and context is not None:
        deps = _get(context, "supplier_dependencies", ()) or ()
        for d in deps:
            if not isinstance(d, dict):
                continue
            label = str(d.get("label") or d.get("supplier") or "")
            share = _coerce_number(d.get("share") or d.get("value"))
            if not label or share is None:
                continue
            slices.append({"label": label, "value": share})
    if not slices:
        return _empty(
            _get(_module_chart_kinds(), "COMPOSITION"),
            envelope=env,
            missing_fields=("supplier_dependencies", "concentration"),
        )
    # Cap to top 5 + "Other" so the donut stays readable.
    slices.sort(key=lambda s: s["value"], reverse=True)
    if len(slices) > 5:
        top = slices[:5]
        other_value = sum(s["value"] for s in slices[5:])
        top.append({"label": "Other", "value": other_value})
        slices = top
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "COMPOSITION"),
        data={
            "slices": slices,
            "title": "Supplier concentration",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(env),
    )


def _build_readiness(by: dict, context: Any) -> ChartPayload:
    """Multidimensional readiness."""
    env = _first(by, "overall_score", "score")
    if env is None:
        return _empty(
            _get(_module_chart_kinds(), "READINESS"),
            missing_fields=("overall_score", "score"),
        )
    value = _get(env, "value", None)
    axes: list[dict] = []
    if isinstance(value, dict):
        # Expected shape: {"axes": [{"label", "value", "max"}, ...]}
        # or flat dict with numeric sub-axes.
        raw_axes = value.get("axes")
        if isinstance(raw_axes, (list, tuple)):
            for a in raw_axes:
                if not isinstance(a, dict):
                    continue
                label = str(a.get("label") or "")
                v = _coerce_number(a.get("value"))
                mx = _coerce_number(a.get("max"))
                if not label or v is None:
                    continue
                axes.append(
                    {
                        "label": label,
                        "value": v,
                        "max": float(mx) if mx is not None else 100.0,
                    }
                )
        else:
            # Fall back: flat dict of {axis_name: 0..100}.
            for k, v in value.items():
                if k in ("axes", "overall_score"):
                    continue
                num = _coerce_number(v)
                if num is None:
                    continue
                axes.append(
                    {
                        "label": str(k),
                        "value": num,
                        "max": 100.0,
                    }
                )
    if not axes:
        return _empty(
            _get(_module_chart_kinds(), "READINESS"),
            envelope=env,
            missing_fields=("axes",),
        )
    src, calc = _provenance(env)
    return ChartPayload(
        chart_kind=_get(_module_chart_kinds(), "READINESS"),
        data={
            "axes": axes,
            "title": "Readiness",
        },
        source_evidence_ids=src,
        calculation_ids=calc,
        confidence=_confidence(env),
    )


# ---------------------------------------------------------------------------
# Module-level helper to avoid circular imports
# ---------------------------------------------------------------------------


def _module_chart_kinds():
    """Lazy import to avoid a hard dependency at module top."""
    from app.services.ai.reasoning.visualization_planner import ChartKind

    return ChartKind


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_BUILDERS = {
    "kpi": _build_kpi,
    "progress": _build_progress,
    "comparison": _build_comparison,
    "trend": _build_trend,
    "scenario": _build_scenario,
    "risk": _build_risk,
    "composition": _build_composition,
    "readiness": _build_readiness,
}


def build(
    plan: Any,
    *,
    envelopes: tuple = (),
    evidence_graph: Any | None = None,
    context: Any | None = None,
) -> ChartPayload:
    """Build the chart-ready payload for one :class:`VisualizationPlan`.

    Pure. Same inputs ⇒ same output. The renderer MUST hide the
    chart when ``empty_reason`` is set; never display an empty
    chart.

    The ``evidence_graph`` parameter is accepted for symmetry with
    the planner but is not directly read by the builders — they
    consume the envelopes + context, which is the same
    information the AI-14 evidence graph indexes.
    """
    chart_kind_value = _get(plan, "chart_kind", None)
    if chart_kind_value is None:
        return _empty(None, empty_reason="No chart_kind on plan.")
    # Normalise — accept ChartKind, str, or anything with `.value`.
    key = getattr(chart_kind_value, "value", chart_kind_value)
    key = str(key)
    builder = _BUILDERS.get(key)
    if builder is None:
        return _empty(
            chart_kind_value,
            empty_reason=f"Unknown chart_kind: {key!r}",
        )
    by = _by_metric(envelopes)
    payload = builder(by, context)
    # Carry the planner's provenance + confidence floor
    # (never bump above source).
    planner_src = tuple(str(x) for x in _get(plan, "source_evidence_ids", ()) or ())
    planner_calc = tuple(str(x) for x in _get(plan, "calculation_ids", ()) or ())
    planner_assumptions = tuple(
        str(x) for x in _get(plan, "assumptions", ()) or ()
    )
    planner_limitations = tuple(
        str(x) for x in _get(plan, "limitations", ()) or ()
    )
    planner_conf = _confidence(plan, payload.confidence)

    return ChartPayload(
        chart_kind=payload.chart_kind,
        data=payload.data,
        source_evidence_ids=planner_src or payload.source_evidence_ids,
        calculation_ids=planner_calc or payload.calculation_ids,
        assumptions=payload.assumptions or planner_assumptions,
        limitations=payload.limitations or planner_limitations,
        confidence=min(planner_conf, payload.confidence or planner_conf),
        empty_reason=payload.empty_reason,
        missing_fields=payload.missing_fields,
    )


__all__ = ["ChartPayload", "build"]

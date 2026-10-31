"""Sprint AI-15 — server-owned trust summary for the "Why this
answer?" disclosure.

This module assembles the five disclosure sections the brief
demands:

  1. Evidence       — business facts consulted.
  2. Calculations   — numeric outputs with formula + source.
  3. Assumptions    — declared assumptions.
  4. Uncertainty    — unknowns + low-confidence items.
  5. Alternatives   — alternate interpretations considered.

Plus three operational fields:

  * ``tools_used``        — whitelist tools invoked.
  * ``tool_failures``     — tool status="error" / "skipped" with reasons.
  * ``confidence_change`` — one-word label.
  * ``quality_warning``   — AI-15 low-quality one-liner when needed.

The function is pure. The LLM has no path into this disclosure.
No chain-of-thought strings are ever emitted.
"""

from __future__ import annotations

from typing import Any

# Regex guard — never expose these phrases in the disclosure.
# (Defense-in-depth; the renderer should still scrub.)
_CHAIN_OF_THOUGHT_TOKENS = (
    "chain of thought",
    "step-by-step reasoning",
    "as an ai",
    "as a language model",
    "internal monologue",
)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if obj is not None else default


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _confidence_change_label(
    *,
    contradiction_severity: str,
    unsupported_count: int,
    needs_warning: bool,
    sparse: bool,
) -> str:
    """Return one of the stable labels the brief enumerates."""
    if contradiction_severity == "high":
        return "reduced: contradiction"
    if needs_warning:
        return "reduced: low quality"
    if unsupported_count > 0 or sparse:
        return "reduced: sparse data"
    return "stable"


def _scrub(text: str) -> str:
    """Replace any chain-of-thought phrases with a neutral marker.

    Case-insensitive. Preserves the rest of the string.
    """
    if not text:
        return text
    out = str(text)
    low = out.lower()
    for tok in _CHAIN_OF_THOUGHT_TOKENS:
        idx = low.find(tok)
        while idx != -1:
            out = out[:idx] + "[redacted]" + out[idx + len(tok):]
            low = out.lower()
            idx = low.find(tok)
    return out


def build_trust_summary(
    *,
    assistant_context: Any | None = None,
    envelopes: tuple = (),
    evidence_graph: Any | None = None,
    contradiction_report: Any | None = None,
    answer_quality: Any | None = None,
    visualization_plans: tuple = (),
    tool_traces: tuple = (),
) -> dict:
    """Pure. Assemble the disclosure payload.

    All values are JSON-serialisable. The renderer can read this
    directly without any further server work.
    """
    evidence_lines: list[str] = []
    calc_lines: list[str] = []
    assumption_lines: list[str] = []
    uncertainty_lines: list[str] = []
    alternative_lines: list[str] = []

    # --- Evidence (profile fields the engine consulted) ---------------
    if assistant_context is not None:
        for fname in (
            "legal_name",
            "industry",
            "location",
            "annual_revenue_inr",
            "target_revenue_inr",
            "employee_count",
            "business_type",
            "established_year",
            "overall_business_score",
            "band",
        ):
            v = _get(assistant_context, fname, None)
            if v is None:
                continue
            evidence_lines.append(f"{fname}={v}")

    # --- Calculations + Assumptions + Uncertainty (from envelopes) -----
    for env in envelopes or ():
        tool = str(_get(env, "tool_name", "") or "")
        metric = str(_get(env, "metric", "") or "")
        value = _get(env, "value", None)
        unit = str(_get(env, "unit", "") or "")
        formula = str(_get(env, "formula", "") or "")
        calc_id = str(_get(env, "calculation_id", "") or "")
        if formula and value is not None:
            calc_lines.append(
                f"{tool}.{metric}={value} {unit}".strip()
                + (f" (formula={formula})" if formula else "")
                + (f" [{calc_id}]" if calc_id else "")
            )
        for a in _coerce_str_list(_get(env, "assumptions", ())):
            assumption_lines.append(f"{tool}: {a}")
        for lim in _coerce_str_list(_get(env, "limitations", ())):
            uncertainty_lines.append(f"{tool}: {lim}")

    # --- Uncertainty (contradictions + unsupported claims) --------------
    contradiction_severity = str(
        _get(contradiction_report, "severity", "none") or "none"
    )
    if contradiction_severity in ("medium", "high"):
        items = _get(contradiction_report, "items", ()) or ()
        for it in items:
            if isinstance(it, dict):
                label = str(it.get("label") or it.get("field") or "conflict")
                note = str(it.get("note") or "")
                uncertainty_lines.append(
                    f"contradiction: {label}{(': ' + note) if note else ''}"
                )
            else:
                uncertainty_lines.append(f"contradiction: {it}")

    unsupported_count = 0
    if evidence_graph is not None:
        unsupported_count = int(
            _get(evidence_graph, "unsupported_claim_count", 0) or 0
        )
        if unsupported_count > 0:
            uncertainty_lines.append(
                f"{unsupported_count} claim(s) could not be verified"
            )
        fabricated = int(
            _get(evidence_graph, "fabricated_source_count", 0) or 0
        )
        if fabricated > 0:
            uncertainty_lines.append(
                f"{fabricated} external source(s) failed the URL guard"
            )

    # --- Alternatives (capability flags + viz kinds) -------------------
    seen: set[str] = set()
    for vp in visualization_plans or ():
        kind = _get(vp, "chart_kind", None)
        if kind is None:
            continue
        kind_value = getattr(kind, "value", kind)
        label = f"chart={kind_value}"
        if label not in seen:
            alternative_lines.append(label)
            seen.add(label)
    if not alternative_lines:
        alternative_lines.append("text answer only (no chart selected)")

    # --- Quality warning ------------------------------------------------
    needs_warning = bool(_get(answer_quality, "needs_warning", False))
    warning_message = _scrub(
        str(_get(answer_quality, "warning_message", "") or "")
    )
    quality_warning = warning_message if needs_warning else None

    # --- Tool traces ----------------------------------------------------
    tools_used: list[str] = []
    tool_failures: list[dict] = []
    for trace in tool_traces or ():
        if not isinstance(trace, dict):
            continue
        name = str(trace.get("tool") or trace.get("name") or "")
        status = str(trace.get("status") or "").lower()
        if name and status == "ok":
            if name not in tools_used:
                tools_used.append(name)
        elif name and status in ("error", "skipped"):
            tool_failures.append(
                {
                    "tool": name,
                    "status": status,
                    "error": str(
                        trace.get("error") or trace.get("reason") or ""
                    ),
                }
            )

    # Pull tool names from envelopes when no traces were provided.
    if not tools_used:
        for env in envelopes or ():
            tool = str(_get(env, "tool_name", "") or "")
            if tool and tool not in tools_used:
                tools_used.append(tool)

    # --- Confidence change label ---------------------------------------
    sparse = len(evidence_lines) <= 1
    confidence_change = _confidence_change_label(
        contradiction_severity=contradiction_severity,
        unsupported_count=unsupported_count,
        needs_warning=needs_warning,
        sparse=sparse,
    )

    # --- Final scrub ----------------------------------------------------
    def _scrub_list(items: list[str]) -> list[str]:
        return [_scrub(x) for x in items if x]

    return {
        "evidence": _scrub_list(evidence_lines),
        "calculations": _scrub_list(calc_lines),
        "assumptions": _scrub_list(assumption_lines),
        "uncertainty": _scrub_list(uncertainty_lines),
        "alternatives": _scrub_list(alternative_lines),
        "tools_used": list(tools_used),
        "tool_failures": [
            {
                "tool": _scrub(str(f.get("tool", ""))),
                "status": str(f.get("status", "")),
                "error": _scrub(str(f.get("error", ""))),
            }
            for f in tool_failures
        ],
        "confidence_change": str(confidence_change),
        "quality_warning": quality_warning,
    }


__all__ = ["build_trust_summary"]

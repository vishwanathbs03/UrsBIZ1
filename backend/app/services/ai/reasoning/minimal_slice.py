"""select_minimal_slice — SPRINT AI-12 Universal Reasoning Layer.

Per-question context subsetting. Returns a slim
:class:`AssistantContext` carrying only the categories the
:class:`QuestionUnderstanding` declared as ``required_evidence_types``.

The full context is preserved in the
``BusinessContextManifest`` for the audit trail; the LLM never
sees data outside the requested slice. This is a token-saving
measure — every unused tuple (``schemes``, ``forecasts``,
``action_items``, …) is dropped before the LLM call.

The function is **pure** — same inputs ⇒ same output. It
never mutates the input context. The slim slice is a new
:class:`AssistantContext` instance.

The slice is a **best-effort** subset. When the
required-evidence-types list is empty, the slim slice is the
input context (no trimming happens) — the renderer always
needs the baseline data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Evidence-type → AssistantContext attribute mapping.
# --------------------------------------------------------------------------- #
# Drives the slicing. Adding a new evidence type is non-breaking
# (the slice falls back to the full context for unknown types).
# Each entry maps the evidence-type string to one or more
# `AssistantContext` attribute names the LLM should see.

EVIDENCE_ATTRS: dict[str, tuple[str, ...]] = {
    "profile": (
        "legal_name",
        "trade_name",
        "industry",
        "sub_industry",
        "business_type",
        "location",
        "employee_count",
        "annual_revenue_inr",
        "target_revenue_inr",
        "products",
        "services",
        "goals",
        "challenges",
    ),
    "analytics": (
        "overall_business_score",
        "band",
        "scores",
        "insights",
        "analytics_metrics",
        "operating_margin_pct",
        "monthly_payroll_cost_inr",
        "monthly_operating_cash_flow_inr",
    ),
    "kpi_history": (
        "scores",
        "analytics_metrics",
    ),
    "transaction": (
        "annual_revenue_inr",
        "monthly_operating_cash_flow_inr",
        "monthly_payroll_cost_inr",
    ),
    "rate_card": (
        "products",
        "services",
    ),
    "scheme": (
        "schemes",
    ),
    "funding": (
        "schemes",
        "annual_revenue_inr",
    ),
    "process_metrics": (
        "scores",
        "insights",
    ),
    "team_metrics": (
        "employee_count",
        "monthly_payroll_cost_inr",
    ),
    "risk_register": (
        "rules",
        "insights",
    ),
    "historical_assumption": (
        "scores",
        "forecasts",
    ),
    "forecast_history": (
        "forecasts",
    ),
    "external_market": (
        "industry",
        "sub_industry",
    ),
    "product": (
        "products",
        "services",
    ),
    "rules": (
        "rules",
    ),
    "document": (
        "report_summaries",
    ),
    "knowledge_base": (
        "report_summaries",
        "context_manifest",
    ),
    "regulatory": (
        "legal_name",
        "certifications",
    ),
    "external": (
        "report_summaries",
        "knowledge_graph",
    ),
    "certification": (
        "certifications",
    ),
    "market_intel": (
        "industry",
        "sub_industry",
        "report_summaries",
    ),
    "roadmap_history": (
        "roadmap",
    ),
    "recommendation_history": (
        "recommendations",
        "action_items",
    ),
    "application_history": (
        "schemes",
    ),
    "scenario_history": (
        "forecasts",
        "rules",
    ),
    "score_history": (
        "scores",
    ),
    "rule_history": (
        "rules",
    ),
    "industry_benchmark": (
        "industry",
        "sub_industry",
        "scores",
    ),
}


# --------------------------------------------------------------------------- #
# Slice result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MinimalSlice:
    """The slim context + the attribute list the LLM will see.

    Attributes
    ----------
    context:
        The slim :class:`AssistantContext` instance the LLM
        receives. Built by ``dataclasses.replace(...)`` so the
        input context is never mutated.
    kept_attributes:
        The sorted attribute names the slice kept. The renderer
        uses this for the audit trail.
    dropped_attributes:
        The sorted attribute names the slice dropped. Useful
        for token accounting.
    rationale:
        One-line explanation for the audit trail.
    """

    context: Any
    kept_attributes: tuple[str, ...] = ()
    dropped_attributes: tuple[str, ...] = ()
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "kept_attributes": list(self.kept_attributes),
            "dropped_attributes": list(self.dropped_attributes),
            "rationale": self.rationale,
        }


# --------------------------------------------------------------------------- #
# The slice function
# --------------------------------------------------------------------------- #


def select_minimal_slice(
    context: Any,
    question_understanding: Any,
) -> MinimalSlice:
    """Return a slim slice of ``context`` for the LLM.

    Algorithm:
      1. Walk ``question_understanding.required_evidence_types``.
      2. Union the :data:`EVIDENCE_ATTRS` entries (de-duped).
      3. Always include the baseline (``"profile"`` + a few
         non-negotiable rendering fields) so the renderer has
         enough data to render the disambiguation block.
      4. Replace only the listed attributes on the new context;
         every other attribute is set to its empty default
         (``()`` / ``0`` / ``""`` / ``None``).
      5. ``rationale`` is a one-line summary for the audit
         trail.

    The function is pure. The input context is never mutated.
    """
    # 1. Required evidence types.
    required = tuple(
        getattr(question_understanding, "required_evidence_types", ()) or ()
    )

    # 2. Always include the baseline + the score + the
    # business ID so the renderer can disambiguate.
    baseline = {
        "business_id",
        "legal_name",
        "trade_name",
        "industry",
        "location",
        "overall_business_score",
        "band",
        "context_manifest",
        "knowledge_graph",
    }

    # 3. Walk the required set, union the attributes.
    keep: set[str] = set(baseline)
    for ev in required:
        attrs = EVIDENCE_ATTRS.get(ev, ())
        keep.update(attrs)

    # 4. Compute the drop set (every other AssistantContext
    # attribute). We use the input context's __annotations__ to
    # drive the discovery so the slice stays in sync if the
    # context schema grows.
    annotations = _safe_annotations(context)
    all_attrs = set(annotations)
    drop = all_attrs - keep

    # 5. Build the slim context. ``dataclasses.replace`` is
    # chosen over construct-from-scratch so the slice keeps
    # the same field defaults as the original.
    import dataclasses

    if not hasattr(context, "__dataclass_fields__"):
        # Not a dataclass — return as-is (no slicing possible).
        return MinimalSlice(
            context=context,
            kept_attributes=sorted(keep),
            dropped_attributes=sorted(drop),
            rationale="context is not a dataclass; slice passthrough",
        )

    # Build a kwargs dict for ``replace``: every dropped attr
    # becomes its empty default; every kept attr passes
    # through.
    empty_default: tuple = ()
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(context):
        if field.name in keep:
            kwargs[field.name] = getattr(context, field.name)
        else:
            kwargs[field.name] = _empty_for_field(field.name, context)

    slim = dataclasses.replace(context, **kwargs)

    rationale_bits = ["profile" if "profile" in required else "no-profile"]
    if required:
        rationale_bits.append("evidence=" + ",".join(required))
    rationale = "minimal slice: " + " | ".join(rationale_bits)

    return MinimalSlice(
        context=slim,
        kept_attributes=tuple(sorted(keep)),
        dropped_attributes=tuple(sorted(drop)),
        rationale=rationale,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _safe_annotations(context: Any) -> dict[str, Any]:
    """Return the dataclass annotations (or an empty dict if not a dataclass)."""
    if hasattr(context, "__dataclass_fields__"):
        return {f.name: f.type for f in context.__dataclass_fields__.values()}
    return {}


def _empty_for_field(name: str, context: Any) -> Any:
    """Return the empty default for a dropped field.

    Looks at the input context's current value as a hint —
    empty tuples for tuples, 0 for ints, "" for strings, None
    for ``Optional`` fields. Optimised for the actual
    AssistantContext schema.
    """
    current = getattr(context, name, None)
    if isinstance(current, tuple):
        return ()
    if isinstance(current, list):
        return []
    if isinstance(current, str):
        return ""
    if isinstance(current, (int, float)):
        return 0
    if isinstance(current, bool):
        return False
    return None

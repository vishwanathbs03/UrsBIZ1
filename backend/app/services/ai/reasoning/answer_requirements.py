"""Sprint AI-14 — Universal Answer Intelligence: ``AnswerRequirements``.

The dataclass in this module is a deterministic declaration of *what
the final answer needs*. It is the first half of the AI-14 answer-
intelligence layer: before any LLM call, the engine reads the
``QuestionUnderstanding`` (capability + business_dependency + the
AI-12 ``requires_*`` booleans), the ``EvidenceRequirements`` plan,
the ``ToolPlan``, and the executed ``StructuredToolEnvelope``s,
and emits an ``AnswerRequirements`` document. The composer reads
that document to pick sections; the renderer reads it to decide
whether the user wants hero-direct-answer or fuller report.

Why a new dataclass instead of re-using ``QuestionUnderstanding``?

``QuestionUnderstanding`` describes the *prompt*. ``AnswerRequirements``
describes the *answer*. The two correlate but they are not the same:
a comparison question ("Compare supplier diversification with
inventory buffering") has a comparison-shaped answer; a missing-
data question ("Can we afford to hire 10 employees?") has a
"what I am missing" shaped answer; a recommendation question has
a recommendation-shaped answer. Both could share the same capability
tuple. AI-14 needs the answer-shape layer separately.

Design contract — preserved across the codebase:

  * Frozen dataclass. Safe-default for every field (no ``None``
    surprises on legacy rows).
  * Pure function ``derive_answer_requirements`` — same inputs
    produce the same output (tested in
    ``tests/test_ai14_answer_requirements.py``).
  * Never asks the LLM. The rule-set is documented inline so
    any future maintainer can audit "why did this field flip
    True?".
  * Reuses AI-12's ``requires_*`` booleans instead of re-inventing
    them. Adds a thin answer-shape layer on top.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Entity / metric / time-horizon / output-format vocabularies.
#
# These are intentionally tiny keyword sets — the derivation rule
# is "best-effort regex extraction". A failure to extract is
# simply ``()`` or ``""``; the LLM never sees an empty list and
# mistakes it for missing data, because the dataclass itself has
# a stable default for every field.
# --------------------------------------------------------------------------- #

# Metric keywords we look for in the literal user prompt. Adding
# a new keyword here is non-breaking (it widens the matching
# surface; it does not narrow it).
_METRIC_KEYWORDS: tuple[str, ...] = (
    "revenue",
    "ebitda",
    "margin",
    "score",
    "growth",
    "profit",
    "cash flow",
    "cash",
    "inventory",
    "payroll",
    "salary",
    "expense",
    "cost",
    "tax",
    "gst",
    "interest",
    "loan",
    "debt",
    "capex",
    "working capital",
    "turnover",
    "roi",
    "irr",
    "cac",
    "ltv",
)

# Time-horizon regex anchors. The first match wins.
_TIME_HORIZON_RE = re.compile(
    r"\b(?:next\s+)?(?P<num>\d+)\s+(?P<unit>day|week|month|quarter|year)s?\b|"
    r"\b(?:this|next|the)\s+(?P<rel>month|quarter|year)\b",
    re.IGNORECASE,
)

# Output-format regex. Default is "narrative" — the model writes
# paragraphs, not a table.
_OUTPUT_FORMAT_RE = re.compile(
    r"\b(?:as\s+(?:a\s+)?|in\s+(?:a\s+)?|give\s+me\s+(?:a\s+)?|show\s+me\s+(?:a\s+)?)"
    r"(?P<fmt>table|list|steps?|bullets?|narrative|paragraph)\b",
    re.IGNORECASE,
)

# Comparison regex anchors — used to flip ``needs_comparison``.
_COMPARISON_RE = re.compile(
    r"\b(?:compare|comparison|vs\.?|versus|or\s+better|which\s+is\s+better)\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# The 16-field frozen dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AnswerRequirements:
    """Deterministic declaration of what the answer must contain.

    Every field defaults to a safe empty value (``False``,
    ``()``, or ``""``) so legacy rows that pre-date AI-14
    deserialise unchanged when the field is omitted.

    Boolean flags — the answer-shape directives:

        needs_direct_answer
            Always ``True`` for AI-14; the UX mandates a
            hero-direct-answer line at the top of every reply.
        needs_business_evidence
            True when the question references the user's business
            (or the QU ``business_dependency`` is ``"optional"``
            / ``"required"``).
        needs_calculation
            True when the question implies arithmetic, OR any
            envelope returned a metric+value+unit.
        needs_external_information
            True when the question references external (non-
            business) information, OR any envelope was produced
            by the ``knowledge_retrieval`` tool.
        needs_recommendation
            True when the capability tuple contains a
            recommendation literal.
        needs_scenario
            True when the QU ``requires_scenario_analysis`` is
            True (the AI-12 scenario branch already proves the
            flag is reliable).
        needs_comparison
            True when the capability tuple contains a comparison
            literal OR the literal question matches a comparison
            keyword.
        needs_risk_analysis
            True when the capability tuple contains a risk
            literal.
        needs_missing_data
            True when the question asks for a fact that is NOT
            in the profile (``context.profile.lacks(...)``).
        needs_assumptions
            True when any envelope carries non-empty
            ``assumptions`` OR the QU ``answer_mode == "scenario"``.
        needs_visualization
            True when the QU ``requires_forecast`` is True OR
            the QU ``answer_mode`` is in the scenario/comparison
            family. (The frontend renders a simple hero-
            conclusion chip; richer visualisation is a follow-up
            sprint.)
        requested_charts
            SPRINT AI-15 — list of ``ChartKind`` strings the
            planner would emit for this prompt. Empty when no
            chart materially improves comprehension. The
            ``needs_visualization`` boolean is derived as
            ``bool(requested_charts)``.

    Best-effort extracted directives:

        requested_entities
            Noun phrases the user mentioned. Best-effort; not
            authoritative.
        requested_metrics
            Metric keywords the user mentioned (revenue, EBITDA,
            margin, score, etc.).
        requested_time_horizon
            Free-form time-horizon string ("next 6 months",
            "this quarter", ...).
        requested_output_format
            One of "table" / "list" / "steps" / "narrative".

    Audit trail:

        rationale
            One-line English summary for the audit log.
    """

    # Answer-shape booleans (defaults — every value False / empty
    # except ``needs_direct_answer``).
    needs_direct_answer: bool = True
    needs_business_evidence: bool = False
    needs_calculation: bool = False
    needs_external_information: bool = False
    needs_recommendation: bool = False
    needs_scenario: bool = False
    needs_comparison: bool = False
    needs_risk_analysis: bool = False
    needs_missing_data: bool = False
    needs_assumptions: bool = False
    needs_visualization: bool = False

    # Extracted directives.
    requested_entities: tuple[str, ...] = field(default_factory=tuple)
    requested_metrics: tuple[str, ...] = field(default_factory=tuple)
    requested_time_horizon: str = ""
    requested_output_format: str = "narrative"

    # SPRINT AI-15 — chart kinds the planner would emit. Empty
    # tuple = no chart. Wire-compat: legacy AI-14 rows that omit
    # this key deserialize with the default empty tuple.
    requested_charts: tuple[str, ...] = field(default_factory=tuple)

    # Audit trail.
    rationale: str = ""

    # ------------------------------------------------------------------ #
    # SPRINT AI-14 FINAL HARDENING — brief vocabulary aliases.
    # The brief names the same concepts differently (e.g.
    # ``required_capabilities`` vs ``capability``,
    # ``calculations_required`` vs ``needs_calculation``,
    # ``external_sources_required`` vs
    # ``needs_external_information``). These fields mirror the
    # canonical values so the wire envelope exposes BOTH
    # vocabularies without breaking the canonical names above.
    # ------------------------------------------------------------------ #

    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    """Capability literals the answer MUST surface (derived from
    the QU capability tuple)."""
    required_evidence_types: tuple[str, ...] = field(default_factory=tuple)
    """Evidence-type strings the answer MUST cite (derived from
    the QU required-evidence-types, plus the answer-shape flags)."""
    required_tools: tuple[str, ...] = field(default_factory=tuple)
    """Tool names the answer MUST invoke (derived from envelopes
    that fired and the QU required-tools)."""
    calculations_required: bool = False
    """True iff the answer MUST carry a calculation (alias for
    ``needs_calculation``; exposed under both names for wire
    compatibility with brief vocabulary)."""
    visualization_required: bool = False
    """True iff the answer MUST carry a visualization (alias for
    ``needs_visualization``)."""
    requested_answer_sections: tuple[str, ...] = field(default_factory=tuple)
    """Section titles the dynamic composer should emit for this
    answer (derived from the ``needs_*`` flags)."""
    uncertainty_required: bool = False
    """True iff the answer MUST surface an uncertainty disclosure
    (contradiction / missing-data / unsupported-claim branch)."""
    external_sources_required: bool = False
    """True iff the answer MUST cite external sources (alias for
    ``needs_external_information``)."""

    # ------------------------------------------------------------------ #
    # Wire projection
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict view (wire shape).

        Tuples become lists — wire payloads are always JSON
        arrays, not Python tuples.

        Both vocabularies are exposed:
          * the canonical ``needs_*`` / ``requested_*`` names
            that AI-14 shipped, and
          * the brief's vocabulary aliases (``required_capabilities``,
            ``calculations_required``, ``external_sources_required``,
            ...) so the wire envelope speaks BOTH the codebase's
            contract and the brief's contract simultaneously.
        """
        return {
            # Canonical AI-14 vocabulary.
            "needs_direct_answer": self.needs_direct_answer,
            "needs_business_evidence": self.needs_business_evidence,
            "needs_calculation": self.needs_calculation,
            "needs_external_information": self.needs_external_information,
            "needs_recommendation": self.needs_recommendation,
            "needs_scenario": self.needs_scenario,
            "needs_comparison": self.needs_comparison,
            "needs_risk_analysis": self.needs_risk_analysis,
            "needs_missing_data": self.needs_missing_data,
            "needs_assumptions": self.needs_assumptions,
            "needs_visualization": self.needs_visualization,
            "requested_entities": list(self.requested_entities),
            "requested_metrics": list(self.requested_metrics),
            "requested_time_horizon": self.requested_time_horizon,
            "requested_output_format": self.requested_output_format,
            # SPRINT AI-15 — list of ChartKind values.
            "requested_charts": list(self.requested_charts),
            # Brief vocabulary aliases.
            "required_capabilities": list(self.required_capabilities),
            "required_evidence_types": list(self.required_evidence_types),
            "required_tools": list(self.required_tools),
            "calculations_required": self.calculations_required,
            "visualization_required": self.visualization_required,
            "requested_answer_sections": list(self.requested_answer_sections),
            "uncertainty_required": self.uncertainty_required,
            "external_sources_required": self.external_sources_required,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnswerRequirements":
        """Reconstruct from a wire dict (lists → tuples)."""
        kwargs: dict[str, Any] = dict(payload or {})
        # Coerce lists back to tuples.
        for fld in (
            "requested_entities",
            "requested_metrics",
            "requested_charts",
            "required_capabilities",
            "required_evidence_types",
            "required_tools",
            "requested_answer_sections",
        ):
            v = kwargs.get(fld, ())
            kwargs[fld] = tuple(v) if isinstance(v, list) else v or ()
        # String defaults.
        for fld in ("requested_time_horizon", "requested_output_format", "rationale"):
            kwargs.setdefault(fld, "" if fld != "requested_output_format" else "narrative")
        # Boolean defaults.
        kwargs.setdefault("needs_direct_answer", True)
        for fld in (
            "needs_business_evidence",
            "needs_calculation",
            "needs_external_information",
            "needs_recommendation",
            "needs_scenario",
            "needs_comparison",
            "needs_risk_analysis",
            "needs_missing_data",
            "needs_assumptions",
            "needs_visualization",
            "calculations_required",
            "visualization_required",
            "uncertainty_required",
            "external_sources_required",
        ):
            kwargs.setdefault(fld, False)
        return cls(**kwargs)


# --------------------------------------------------------------------------- #
# Derivation rule-set
# --------------------------------------------------------------------------- #


def _extract_metrics(literal: str) -> tuple[str, ...]:
    """Best-effort metric extraction."""
    if not literal:
        return ()
    lowered = literal.lower()
    found: list[str] = []
    seen: set[str] = set()
    for kw in _METRIC_KEYWORDS:
        if kw in lowered and kw not in seen:
            seen.add(kw)
            found.append(kw)
    return tuple(found)


def _extract_time_horizon(literal: str) -> str:
    """Return the first time-horizon match, or ``""``."""
    if not literal:
        return ""
    m = _TIME_HORIZON_RE.search(literal)
    if not m:
        return ""
    if m.group("num") and m.group("unit"):
        return f"{m.group('num')} {m.group('unit')}{'' if m.group('num') == '1' else 's'}"
    if m.group("rel"):
        return m.group("rel").lower()
    return ""


def _extract_output_format(literal: str) -> str:
    """Return the first output-format match, default ``"narrative"``."""
    if not literal:
        return "narrative"
    m = _OUTPUT_FORMAT_RE.search(literal)
    if not m:
        return "narrative"
    fmt = m.group("fmt").lower()
    # Normalise: "step" / "steps" → "steps"; "bullet" / "bullets" → "list"
    if fmt in ("step", "steps"):
        return "steps"
    if fmt in ("bullet", "bullets"):
        return "list"
    return fmt


def _capability_matches(capability: tuple[str, ...] | list[str], *needles: str) -> bool:
    """True iff any ``needle`` appears (case-insensitive substring) in any capability literal."""
    if not capability:
        return False
    needles_upper = tuple(n.upper() for n in needles)
    for cap in capability:
        if not cap:
            continue
        cu = str(cap).upper()
        if any(n in cu for n in needles_upper):
            return True
    return False


def derive_answer_requirements(
    *,
    question_understanding: Any,
    evidence_requirements: Any = None,
    tool_plan: Any = None,
    envelopes: tuple[Any, ...] | list[Any] = (),
    context: Any = None,
) -> AnswerRequirements:
    """Pure derivation of ``AnswerRequirements``.

    Parameters
    ----------
    question_understanding
        An ``app.services.ai.reasoning.question_understanding
        .QuestionUnderstanding`` instance (or any duck-typed
        object exposing ``capability``, ``business_dependency``,
        ``literal_question``, ``requires_calculation``,
        ``requires_scenario_analysis``, ``requires_forecast``,
        ``requires_external_information``, ``answer_mode``,
        ``unknowns``).
    evidence_requirements, tool_plan
        Currently informational — the rule-set uses the QU
        booleans which are already the canonical source of
        truth. Both parameters are accepted so the call site
        can mirror the AI-12 evidence / tool-plan signature
        without an extra shim layer.
    envelopes
        Iterable of ``StructuredToolEnvelope``. When at least
        one envelope carries a numeric (``value`` + ``unit``),
        the derivation flips ``needs_calculation`` on.
    context
        The ``AssistantContext``. Currently used only to
        probe for "is this field missing from the profile?"
        (the ``needs_missing_data`` heuristic).

    Returns
    -------
    AnswerRequirements
        A frozen dataclass the renderer / composer can read.
    """
    qu = question_understanding
    literal = getattr(qu, "literal_question", "") or ""
    capability = tuple(getattr(qu, "capability", ()) or ())
    business_dependency = str(getattr(qu, "business_dependency", "none") or "none")
    requires_calculation = bool(getattr(qu, "requires_calculation", False))
    requires_scenario_analysis = bool(getattr(qu, "requires_scenario_analysis", False))
    requires_forecast = bool(getattr(qu, "requires_forecast", False))
    requires_external_information = bool(
        getattr(qu, "requires_external_information", False)
    )
    answer_mode = str(getattr(qu, "answer_mode", "general_knowledge") or "general_knowledge")
    unknowns = tuple(getattr(qu, "unknowns", ()) or ())

    # Envelopes — derive needs_calculation / needs_external_information
    # from the deterministic side, too.
    envelope_tuple = tuple(envelopes or ())
    any_calc_envelope = any(
        getattr(env, "metric", None) is not None and getattr(env, "value", None) is not None
        for env in envelope_tuple
    )
    any_knowledge_envelope = any(
        getattr(env, "tool_name", "") == "knowledge_retrieval"
        for env in envelope_tuple
    )
    any_assumption_envelope = any(
        bool(getattr(env, "assumptions", ()))
        for env in envelope_tuple
    )

    # needs_comparison — capability OR literal regex.
    comparison_via_capability = _capability_matches(capability, "COMPARISON", "COMPARE")
    comparison_via_literal = bool(_COMPARISON_RE.search(literal))

    # needs_missing_data — if the QU unknowns list references a
    # field the context.profile does not have (best-effort: look
    # at profile attributes that are 0 / "" / "unknown" / "Not
    # set"). The check is permissive: any unknown name that
    # maps to a known profile attribute in the default state
    # flips the flag on. False positives are cheap (the renderer
    # shows an honest "what I am missing" section); false
    # negatives (saying we know something we don't) are expensive.
    needs_missing_data = _probe_missing_data(unknowns=unknowns, context=context)

    # Compose the boolean directives.
    needs_business_evidence = business_dependency in ("optional", "required")
    needs_calculation = requires_calculation or any_calc_envelope
    needs_external_information = (
        requires_external_information or any_knowledge_envelope
    )
    needs_recommendation = _capability_matches(capability, "RECOMMENDATION")
    needs_scenario = requires_scenario_analysis
    needs_comparison = comparison_via_capability or comparison_via_literal
    needs_risk_analysis = _capability_matches(capability, "RISK")
    needs_assumptions = any_assumption_envelope or answer_mode == "scenario"
    needs_visualization = (
        requires_forecast
        or answer_mode in ("scenario", "comparison")
    )

    # SPRINT AI-15 — derive the requested chart kinds
    # deterministically. The planner re-derives these independently;
    # we mirror them here so the renderer can read the wire
    # envelope without re-running the planner.
    requested_charts = _derive_requested_charts(
        capability=capability,
        requires_calculation=requires_calculation,
        requires_scenario_analysis=requires_scenario_analysis,
        requires_forecast=requires_forecast,
        envelope_tuple=envelope_tuple,
    )

    # Extracted directives.
    metrics = _extract_metrics(literal)
    horizon = _extract_time_horizon(literal)
    out_fmt = _extract_output_format(literal)
    entities = ()  # future sprint — for now, the LLM owns entity extraction

    # Rationale — one-line English summary.
    flags_on: list[str] = []
    for name, val in (
        ("business_evidence", needs_business_evidence),
        ("calculation", needs_calculation),
        ("external", needs_external_information),
        ("recommendation", needs_recommendation),
        ("scenario", needs_scenario),
        ("comparison", needs_comparison),
        ("risk", needs_risk_analysis),
        ("missing_data", needs_missing_data),
        ("assumptions", needs_assumptions),
        ("visualization", needs_visualization),
    ):
        if val:
            flags_on.append(name)
    rationale = (
        f"capability={','.join(capability) or 'none'}; "
        f"deps={business_dependency}; flags={','.join(flags_on) or 'none'}; "
        f"mode={answer_mode}; metrics={','.join(metrics) or 'none'}; "
        f"horizon={horizon or 'none'}; fmt={out_fmt}"
    )

    # ------------------------------------------------------------------ #
    # SPRINT AI-14 FINAL HARDENING — brief-vocab derivation.
    #
    # The brief lists specific field names that must be present
    # on the wire envelope (``required_capabilities``,
    # ``required_evidence_types``, ``required_tools``,
    # ``calculations_required``, ``visualization_required``,
    # ``requested_answer_sections``, ``uncertainty_required``,
    # ``external_sources_required``). They are pure projections
    # of the canonical ``needs_*`` flags already derived above
    # — the derivation is purely deterministic and the LLM is
    # NEVER involved.
    # ------------------------------------------------------------------ #

    # required_capabilities — the capability literals the answer
    # must surface. Empty when the QU had no capabilities.
    required_capabilities = tuple(capability) if capability else ()

    # required_evidence_types — best-effort projection from QU
    # ``requires_*`` booleans + answer_mode. The values are the
    # standard short strings the renderer + frontend can key off
    # without re-running the planner.
    req_evidence: list[str] = []
    if needs_business_evidence:
        req_evidence.append("profile")
    if needs_calculation:
        req_evidence.append("calculation")
    if needs_recommendation:
        req_evidence.append("recommendation")
    if needs_risk_analysis:
        req_evidence.append("risk")
    if needs_scenario:
        req_evidence.append("scenario")
    if needs_comparison:
        req_evidence.append("comparison")
    if needs_external_information:
        req_evidence.append("external")
    if needs_missing_data:
        req_evidence.append("missing_data")
    if needs_assumptions:
        req_evidence.append("assumption")
    required_evidence_types = tuple(req_evidence)

    # required_tools — the tool names whose envelopes fired.
    # Deterministic; never LLM-authored.
    required_tools = tuple(
        sorted({
            str(getattr(env, "tool_name", "") or "")
            for env in envelope_tuple
            if getattr(env, "tool_name", None)
        })
    )

    # Brief aliases — direct projections.
    calculations_required = needs_calculation
    visualization_required = needs_visualization
    external_sources_required = needs_external_information
    uncertainty_required = (
        needs_missing_data
        or bool(unknowns)
        or answer_mode == "scenario"
    )

    # requested_answer_sections — the section titles the
    # dynamic composer should emit. Order matters: hero first,
    # then the supports, then uncertainty / next-actions at the
    # tail. Each title is a stable string the renderer can
    # match on (see ``dynamic_section_selector``).
    sections: list[str] = []
    if needs_business_evidence:
        sections.append("key_evidence")
    if needs_calculation:
        sections.append("calculation")
    if needs_recommendation:
        sections.append("recommendation")
    if needs_scenario:
        sections.append("scenario")
    if needs_comparison:
        sections.append("comparison")
    if needs_risk_analysis:
        sections.append("risk")
    if needs_external_information:
        sections.append("external_sources")
    if needs_assumptions:
        sections.append("assumptions")
    if uncertainty_required:
        sections.append("uncertainty")
    if needs_visualization:
        sections.append("visualization")
    requested_answer_sections = tuple(sections)

    return AnswerRequirements(
        needs_direct_answer=True,  # always — UX contract
        needs_business_evidence=needs_business_evidence,
        needs_calculation=needs_calculation,
        needs_external_information=needs_external_information,
        needs_recommendation=needs_recommendation,
        needs_scenario=needs_scenario,
        needs_comparison=needs_comparison,
        needs_risk_analysis=needs_risk_analysis,
        needs_missing_data=needs_missing_data,
        needs_assumptions=needs_assumptions,
        needs_visualization=needs_visualization,
        requested_entities=entities,
        requested_metrics=metrics,
        requested_time_horizon=horizon,
        requested_output_format=out_fmt,
        # SPRINT AI-15 — chart kinds the planner would emit.
        requested_charts=requested_charts,
        # Brief vocabulary aliases.
        required_capabilities=required_capabilities,
        required_evidence_types=required_evidence_types,
        required_tools=required_tools,
        calculations_required=calculations_required,
        visualization_required=visualization_required,
        requested_answer_sections=requested_answer_sections,
        uncertainty_required=uncertainty_required,
        external_sources_required=external_sources_required,
        rationale=rationale,
    )


def _derive_requested_charts(
    *,
    capability: tuple[str, ...],
    requires_calculation: bool,
    requires_scenario_analysis: bool,
    requires_forecast: bool,
    envelope_tuple: tuple[Any, ...],
) -> tuple[str, ...]:
    """Best-effort, deterministic derivation of requested chart kinds.

    Mirrors the planner's decision table but never imports the
    planner — keeping this module independent of the AI-15 viz
    modules avoids a circular import at derivation time.
    """
    by_metric: dict[str, int] = {}
    for env in envelope_tuple:
        m = getattr(env, "metric", None)
        if not m:
            continue
        by_metric[str(m)] = by_metric.get(str(m), 0) + 1

    kinds: list[str] = []

    def _has(*metrics: str) -> bool:
        return any(m in by_metric for m in metrics)

    if _has("growth", "scenario") and requires_calculation:
        kinds.append("progress")

    if _has("compare"):
        kinds.append("comparison")

    if requires_forecast and _has("forecast"):
        kinds.append("trend")

    if requires_scenario_analysis or _has("scenario", "scenario_delta"):
        kinds.append("scenario")

    if _capability_matches(capability, "RISK") and _has("risks"):
        kinds.append("risk")

    if _has("risks", "overall_score"):
        kinds.append("readiness")

    if requires_calculation and _has("amount", "score", "value"):
        # KPI is a fallback headline; only emit when no richer chart
        # already qualifies.
        if not kinds:
            kinds.append("kpi")

    return tuple(kinds)


def _probe_missing_data(*, unknowns: tuple[str, ...], context: Any) -> bool:
    """Best-effort probe for ``needs_missing_data``.

    Walks the QU ``unknowns`` list and, for each unknown name,
    checks whether the context profile carries a populated
    value. Profile attributes that are ``0`` / ``""`` /
    ``"unknown"`` / ``"Not set"`` are treated as missing.

    The probe is intentionally permissive — a single hit flips
    the flag on. The renderer renders an honest "what I am
    missing" section; a false positive is cheap, a false
    negative is expensive.
    """
    if not unknowns:
        return False
    if context is None:
        # Without a context, we cannot probe; be honest and say
        # "we don't know if it's missing". Returning False keeps
        # the renderer quiet; the LLM will surface uncertainty.
        return False
    # Map unknowns → profile attribute names. The mapping is
    # explicit so the rule is auditable.
    _UNKNOWN_TO_ATTR: dict[str, str] = {
        "monthly_payroll_cost_inr": "monthly_payroll_cost_inr",
        "monthly_operating_cash_flow_inr": "monthly_operating_cash_flow_inr",
        "operating_margin_pct": "operating_margin_pct",
        "annual_revenue_inr": "annual_revenue_inr",
        "target_revenue_inr": "target_revenue_inr",
        "products": "products",
        "services": "services",
        "certifications": "certifications",
        "supplier_dependencies": "supplier_dependencies",
        "customer_dependencies": "customer_dependencies",
        "employee_count": "employee_count",
        "location": "location",
    }
    for u in unknowns:
        attr = _UNKNOWN_TO_ATTR.get(u, "")
        if not attr:
            # Unknown unknowns name → not in our map; be honest.
            return True
        val = getattr(context, attr, None)
        if val in (0, 0.0, "", "unknown", "Not set", None, (), []):
            return True
    return False
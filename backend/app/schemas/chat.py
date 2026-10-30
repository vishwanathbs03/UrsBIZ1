"""Pydantic schemas for the chat persistence endpoints (Sprint 7 Part 3).

The endpoint surface is:

  POST   /api/v1/chat                 create a new conversation
  GET    /api/v1/chat                 list the user's conversations
  GET    /api/v1/chat/{id}            fetch a conversation + messages
  DELETE /api/v1/chat/{id}            delete a conversation
  POST   /api/v1/chat/{id}/message    append a user message, get a reply

All response models use :class:`pydantic.BaseModel` with
``model_config = ConfigDict(extra="forbid")`` so an upstream
refactor that adds a new field fails loudly at the API boundary
instead of silently shipping a shape the UI does not know how to
render.

Every schema is **owner-scoped** at the endpoint layer — a
conversation belongs to the authenticated user, and a request for
another user's conversation returns 404, never 403, so the
resource's existence is not leaked.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Conversation source — what the assistant reply drew on
# --------------------------------------------------------------------------- #


class ChatSource(BaseModel):
    """One source the assistant reply leaned on."""

    model_config = ConfigDict(extra="forbid")

    topic: Literal[
        "Twin",
        "Recommendations",
        "Roadmap",
        "Insights",
        "Rules",
        "Business DNA",
        "Export",
        # Sprint 7 Part 4 — knowledge retrieval sources.
        "Knowledge",
        "Rule",
        "Recommendation",
        "GovernmentScheme",
        "Glossary",
    ]
    detail: str = Field(min_length=1, max_length=500)


# --------------------------------------------------------------------------- #
# H7.8C — provenance envelope
# --------------------------------------------------------------------------- #


class ChatEvidenceReference(BaseModel):
    """One pointer back to an upstream service that produced a fact.

    The model cites these IDs in its response; the registry
    resolves them against the live upstream payloads.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    kind: Literal[
        "score",
        "recommendation",
        "rule",
        "insight",
        "scheme",
        "forecast",
        "action",
        "dna",
    ] = "score"
    label: str = Field(default="", max_length=200)


class ChatGroundedFinding(BaseModel):
    """One short bullet the model surfaced."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(default="", max_length=400)
    evidence_refs: list[str] = Field(default_factory=list)


class ChatGroundedRecommendation(BaseModel):
    """A recommendation the model authored in grounded mode.

    H7.8C — ``recommendation_id`` MUST resolve to an
    ``EvidenceKind.RECOMMENDATION`` entry in the registry.
    The legacy ``priority`` / ``score_gain`` fields are kept
    as the *resolved* values from the registry — the model
    never authors them.
    """

    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=200)
    rationale: str = Field(default="", max_length=500)
    priority: Literal["Critical", "High", "Medium", "Low"] | None = None
    score_gain: int | None = Field(default=None, ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list)


class ChatGroundedPlanItem(BaseModel):
    """A week-by-week task inside the 30-day plan."""

    model_config = ConfigDict(extra="forbid")

    week: Literal[1, 2, 3, 4]
    task: str = Field(min_length=1, max_length=240)
    recommendation_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class ChatGroundedSchemeMatch(BaseModel):
    """A scheme the model flagged as a profile match.

    The match score and eligibility determination are NEVER
    authored by the model. They come from the registry.
    """

    model_config = ConfigDict(extra="forbid")

    scheme_ref: str = Field(min_length=1, max_length=120)
    match_explanation: str = Field(default="", max_length=400)
    profile_match_score: int | None = Field(default=None, ge=0, le=100)
    authority: str = Field(default="", max_length=200)
    evidence_refs: list[str] = Field(default_factory=list)


class ChatGroundedResponse(BaseModel):
    """The structured payload from a real grounded-mode LLM call."""

    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(default="", max_length=600)
    key_findings: list[ChatGroundedFinding] = Field(default_factory=list)
    recommendations: list[ChatGroundedRecommendation] = Field(default_factory=list)
    thirty_day_plan: list[ChatGroundedPlanItem] = Field(default_factory=list)
    scheme_matches: list[ChatGroundedSchemeMatch] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100, default=0)
    server_grounding_score: int = Field(ge=0, le=100, default=0)
    evidence_references: list[ChatEvidenceReference] = Field(default_factory=list)

    # SPRINT AI-3 — claim-aware response payload, nested under
    # the existing grounded_payload envelope so the wire stays
    # backward-compatible. ``None`` for legacy rows that pre-date
    # AI-3; the deterministic fallback ALWAYS populates it.
    claim_aware: dict | None = None

    # SPRINT AI-4 — server-side Claim Auditor trace, nested
    # under the same envelope. ``None`` for legacy rows; the
    # deterministic fallback ALWAYS populates it.
    claim_audit: dict | None = None


# --------------------------------------------------------------------------- #
# SPRINT AI-4 — claim audit wire schema
# --------------------------------------------------------------------------- #


class ChatClaimAuditRecord(BaseModel):
    """One record in the AI-4 ``ClaimAuditReport.records`` list.

    Mirrors :class:`app.services.ai.providers.claim_auditor.
    ClaimAuditRecord`. The 9 attribute axes the brief mandates
    are all explicit fields; the trace never persists full
    prose — only ``text_preview`` (≤120 chars).
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=40)
    claim_type: Literal[
        "FACT",
        "CALCULATION",
        "INFERENCE",
        "RECOMMENDATION",
        "SCENARIO",
        "EXTERNAL_FACT",
        "UNKNOWN",
    ] = "UNKNOWN"
    text_preview: str = Field(default="", max_length=200)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_exists: bool
    evidence_supports: bool
    numeric_match: bool
    is_inference: bool
    has_assumptions: bool
    is_hypothetical: bool
    requires_verification: bool
    validated: bool
    confidence: int = Field(ge=0, le=100, default=0)
    rejection_reason: str = Field(default="", max_length=200)
    soft_corrected: bool = False


class ChatClaimAuditTrace(BaseModel):
    """SPRINT AI-4 — the auditor's verdict on the chat reply.

    ``rejected`` is True iff the auditor triggered any
    hard-rejection condition. ``rejection_reason`` is the
    stable label of the rule that fired. ``soft_corrections``
    counts how many claims the auditor rewrote without
    rejecting the whole answer.
    """

    model_config = ConfigDict(extra="forbid")

    rejected: bool
    rejection_reason: str = Field(default="", max_length=200)
    soft_corrections: int = Field(ge=0, default=0)
    records: list[ChatClaimAuditRecord] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# SPRINT AI-5 — Business Scenario Copilot wire schema
# ---------------------------------------------------------------------------


class ChatScenarioAnalysis(BaseModel):
    """SPRINT AI-5 — the 10-field "what if" envelope.

    The shape matches the brief exactly: every field is a
    bullet-list serialised as a ``list[str]`` (or a single
    ``str`` for the calculation method, confidence, and
    scenario name). The disclaimer is always the canonical
    "Illustrative scenario — not a prediction." string so
    the wire cannot accidentally drop the label.

    ``present`` is a server-side helper flag — always
    ``True`` on a non-None envelope. The frontend can use
    it to gate the card render without checking the
    discriminating fields.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_name: str = Field(default="", max_length=200)
    baseline: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    calculation_method: str = Field(default="", max_length=2000)
    estimated_effects: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    sensitivity: list[str] = Field(default_factory=list)
    confidence: str = Field(default="unknown", max_length=20)
    disclaimer: str = Field(
        default="Illustrative scenario — not a prediction.", max_length=200
    )
    present: bool = True


# --------------------------------------------------------------------------- #
# SPRINT AI-3 — claim-aware response wire schema
# --------------------------------------------------------------------------- #


class ChatClaimEvidenceRef(BaseModel):
    """Pointer back to an evidence registry entry a claim cites.

    ``audit_log`` is a list of structured records the numeric
    checker emits when it mutates a claim's text. Each entry
    preserves the original literal so the audit trail is
    faithful. Empty list when no conflict was repaired.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=2000)
    claim_type: Literal[
        "FACT",
        "CALCULATION",
        "INFERENCE",
        "RECOMMENDATION",
        "SCENARIO",
        "EXTERNAL_FACT",
        "UNKNOWN",
    ] = "UNKNOWN"
    evidence_references: list[str] = Field(default_factory=list)
    confidence: int | None = Field(default=None, ge=0, le=100)
    audit_log: list[dict] = Field(default_factory=list)
    user_provided: bool = False


class ChatClaimRecommendation(BaseModel):
    """One LLM-authored action recommendation."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=240)
    reason: str = Field(default="", max_length=600)
    recommendation_id: str = Field(default="", max_length=120)
    evidence_references: list[str] = Field(default_factory=list)
    category: str = Field(default="", max_length=80)
    priority: str = Field(default="", max_length=20)
    estimated_score_gain: int | None = Field(default=None, ge=0, le=100)
    estimated_timeline: str = Field(default="", max_length=80)


class ChatClaimCalculation(BaseModel):
    """One derived figure the LLM surfaced."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    result: float = 0.0
    unit: str = Field(default="", max_length=40)
    source: Literal[
        "URSBIZ_ENGINE",
        "MODEL_SCENARIO",
        "USER_INPUT",
    ] = "URSBIZ_ENGINE"
    expression: str = Field(default="", max_length=400)
    inputs: dict = Field(default_factory=dict)
    evidence_references: list[str] = Field(default_factory=list)


class ChatClaimScenario(BaseModel):
    """One illustrative scenario the LLM authored."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=600)
    assumptions: list[str] = Field(default_factory=list)
    revenue_impact: str = Field(default="", max_length=200)
    score_impact: str = Field(default="", max_length=200)
    confidence: int | None = Field(default=None, ge=0, le=100)
    evidence_references: list[str] = Field(default_factory=list)


class ChatClaimUnknown(BaseModel):
    """One knowledge gap the LLM surfaced."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=400)
    impact: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    rationale: str = Field(default="", max_length=400)
    clarification_prompt: str = Field(default="", max_length=400)


class ChatClaimAwareResponse(BaseModel):
    """SPRINT AI-3 — the validated claim-aware response envelope.

    Optional on every chat reply. ``None`` when the LLM didn't
    fill the new schema (the existing ``ChatGroundedResponse``
    surface carries the wire content). The deterministic
    fallback builds a non-None envelope from ``AssistantContext``
    so EVERY chat reply has a structured payload.

    ``server_confidence`` and ``server_confidence_rationale``
    are server-stamped; the LLM cannot author them.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(default="", max_length=2000)
    claims: list[ChatClaimEvidenceRef] = Field(default_factory=list)
    recommendations: list[ChatClaimRecommendation] = Field(default_factory=list)
    calculations: list[ChatClaimCalculation] = Field(default_factory=list)
    scenarios: list[ChatClaimScenario] = Field(default_factory=list)
    unknowns: list[ChatClaimUnknown] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    narrative: str = Field(default="", max_length=4000)

    server_confidence: int | None = Field(default=None, ge=0, le=100)
    server_confidence_rationale: str = Field(default="", max_length=500)
    numeric_conflicts: list[dict] = Field(default_factory=list)
    server_audit: dict = Field(default_factory=dict)

    # SPRINT AI-4 — the server-side claim auditor's trace is
    # nested inside the same envelope so legacy clients that
    # only know about ``claims`` / ``recommendations`` keep
    # parsing while the new AI-4 surface is available on the
    # top-level ``chat_message.claim_audit`` field.
    claim_audit: dict | None = None

    # SPRINT AI-5 — Business Scenario Copilot envelope. The
    # structured 10-field "what if" envelope follows the same
    # pattern as the AI-4 trace: mirrored on the top-level
    # ``chat_message.scenario_analysis`` field so the frontend
    # card renders without drilling into ``generation.*``.
    scenario_analysis: dict | None = None


class ChatGenerationMeta(BaseModel):
    """The full provenance envelope persisted with every assistant turn.

    See :class:`app.services.ai.providers.base.GenerationMeta`
    for the canonical definition. This is the wire mirror.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    runtime_provider: str = Field(default="", max_length=80)
    """H7.8C — the runtime provider that actually answered the
    request. Equal to ``provider`` for the deterministic
    fallback path; equal to ``provider`` for any real call.
    The field is differentiated from ``provider`` so the wire
    payload can carry it even when the configured provider name
    and the runtime provider name diverge. Defaults to ``""``
    for legacy rows that pre-date H7.8C."""
    mode: Literal["grounded", "open"] = "grounded"
    fallback_used: bool
    fallback_reason: Literal[
        "provider_unavailable",
        "timeout",
        "rate_limited",
        "provider_error",
        "http_4xx",
        "http_5xx",
        "malformed_response",
        "empty_response",
        "schema_invalid",
        "grounding_invalid",
        "not_configured",
        "open_mode_provider_failure",
    ] | None = None
    generation_method: Literal["generative", "deterministic"]
    schema_validated: bool = False
    grounding_validated: bool = False
    server_grounding_score: int = Field(ge=0, le=100, default=0)
    evidence_count: int = Field(ge=0, default=0)
    confidence: int | None = Field(default=None, ge=0, le=100)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    generated_at: str = Field(min_length=1, max_length=80)
    prompt_truncated: bool = False
    provider_latency_ms: int | None = Field(default=None, ge=0)
    grounded_payload: ChatGroundedResponse | None = None
    business_evidence_validated: bool = False
    context_manifest: dict | None = None

    # AI-1 — universal-assistant audit trail fields. Mirrors
    # of the GenerationMeta dataclass fields. Each new field
    # has a safe default so legacy rows deserialize cleanly.
    # The Pydantic ``extra="forbid"`` config would otherwise
    # reject these when the persistence layer emits them.
    deterministic_services_used: list[str] = Field(default_factory=list)
    calculations_used: list[str] = Field(default_factory=list)
    question_understanding: dict | None = None
    tool_calls: list[dict] = Field(default_factory=list)
    claim_categories_used: list[str] = Field(default_factory=list)

    # SPRINT AI-3 — Claim-aware response audit fields mirrored
    # from the GenerationMeta dataclass. Defaults are safe
    # empties so legacy rows that pre-date the column
    # deserialize without complaint.
    claim_aware_validated: bool = False
    numeric_conflicts_count: int = Field(default=0, ge=0)
    server_confidence: int | None = Field(default=None, ge=0, le=100)
    server_confidence_rationale: str = Field(default="", max_length=500)

    # SPRINT AI-4 — server-side Claim Auditor audit fields
    # mirrored from the GenerationMeta dataclass. Defaults are
    # safe empties so legacy rows that pre-date the AI-4 column
    # deserialize without complaint. The frontend's "Why am I
    # seeing this?" disclosure panel reads ``claim_audit``;
    # the two booleans are flat mirrors for the trust badge.
    claim_audit: dict | None = None
    claim_audit_rejected: bool = False
    claim_audit_soft_corrections: int = Field(default=0, ge=0)

    # SPRINT AI-5 — Business Scenario Copilot envelope. The
    # structured 10-field "what if" envelope from the brief;
    # default None so legacy rows that pre-date AI-5 still
    # deserialize. The frontend ``ScenarioAnalysisCard`` reads
    # this top-level field so the chat route renders the card
    # without drilling into ``generation.*``.
    scenario_analysis: dict | None = None

    # SPRINT AI-6 — Trust-first visual UI. The first 1-3
    # sentences of the assistant's prose, server-extracted and
    # ready for the frontend to render as the "Direct Answer"
    # 10-second-read header. ``None`` when the assistant didn't
    # produce extractable prose, or for legacy rows that
    # pre-date AI-6; the frontend projector falls back to
    # ``consultant.body`` / ``content`` in that case.
    direct_answer: str | None = None

    # SPRINT AI-7 — Missing-data intelligence. Structured list
    # of ``MissingDataObject`` dicts the proactive detector
    # (step 3.7 of ``ConversationService.append_message``) emits
    # BEFORE the provider call. Each dict carries ``field``,
    # ``importance``, ``reason``, ``affects``, ``suggested_source``.
    # Default empty list so legacy rows that pre-date AI-7 still
    # deserialize. The frontend ``MissingInfoCard`` renders the
    # 4-section card when the list is non-empty.
    missing_data: list[dict] = Field(default_factory=list)

    # SPRINT AI-8 — Controlled Business Tool Router.
    # Validated + sanitised + evidence-stamped results from
    # the optional 2nd-turn tool-loop. Same shape and
    # additive-compat default (``[]``) as the wire mirror
    # on the outer ``ChatMessageOut``.
    llm_tool_results: list[dict] = Field(default_factory=list)

    # SPRINT AI-10 — Explain My Answer. Per-recommendation
    # decision traces stamped on every assistant turn. The
    # dict is shaped ``{recommendation_id:
    # DecisionTrace.to_dict()}`` — six sections (evidence,
    # calculations, decision_factors, assumptions,
    # uncertainty, alternatives) plus confidence +
    # confidence_label. ``None`` for legacy rows that pre-date
    # AI-10; the deterministic fallback ALWAYS populates a
    # trace per recommendation in the turn.
    explanation: dict | None = None

    # SPRINT AI-11 — Universal Business-Aware Assistant hardening.
    # ``capability`` is the multi-label tuple describing what
    # capabilities the prompt required (one or more of
    # GENERAL_KNOWLEDGE / BUSINESS_FACT / BUSINESS_ANALYSIS /
    # CALCULATION / RECOMMENDATION / SCENARIO / FORECAST /
    # COMPARISON / FINANCIAL / OPERATIONAL / RISK /
    # GOVERNMENT_SCHEME / EXPORT / ROADMAP /
    # EXTERNAL_INFORMATION / MIXED / UNKNOWN).
    # ``business_dependency`` is the three-valued literal
    # ``"none"`` / ``"optional"`` / ``"required"``. Both default
    # to safe empty list / ``"none"`` so every pre-AI-11 row
    # deserialises unchanged. The field is appended at the END
    # so legacy ``ChatGenerationMeta(**legacy_data)`` calls
    # keep working.
    capability: list[str] = Field(default_factory=list)
    business_dependency: str = "none"

    # SPRINT AI-12 — Universal Reasoning Layer wire projection.
    # Five additive fields. All default-safe (``None`` / ``[]``)
    # so legacy rows that pre-date AI-12 deserialize cleanly.
    tool_plan: dict | None = None
    """SPRINT AI-12 — :class:`ToolPlan.to_dict()` mirror.
    Carries ``required`` / ``optional`` / ``parallelizable`` /
    ``sequential`` / ``rationale``. ``None`` for legacy rows
    that pre-date AI-12."""

    evidence_requirements: dict | None = None
    """SPRINT AI-12 — :class:`EvidenceRequirements.to_dict()`
    mirror. Carries ``required`` / ``optional`` /
    ``rationale``. ``None`` for legacy rows."""

    contradiction_report: dict | None = None
    """SPRINT AI-12 — :class:`ContradictionReport.to_dict()`
    mirror. Carries ``severity`` (``none / low / medium /
    high``), ``items`` (list of contradiction dicts), and
    ``rationale``. ``None`` for legacy rows."""

    answer_quality: dict | None = None
    """SPRINT AI-12 — :class:`AnswerQuality.to_dict()` mirror.
    Carries the 8 axis scores (relevance, evidence, numeric,
    completeness, uncertainty, actionability, consistency,
    format), ``total``, ``weakest_axis``, ``needs_retry``,
    and ``rationale``. ``None`` for legacy rows."""

    structured_tool_envelopes: list[dict] = Field(default_factory=list)
    """SPRINT AI-12 — ``StructuredToolEnvelope.to_dict()``
    mirror, one per tool the dispatcher invoked. Carries
    ``tool_name``, ``metric``, ``value``, ``unit``, ``formula``,
    ``input_evidence_ids``, ``calculation_id``, ``assumptions``,
    ``limitations``. Empty list for legacy rows."""

    answer_mode: str = "general_knowledge"
    """SPRINT AI-12 — capability-aware shape signal. One of the
    eight ``AnswerMode`` literals. Drives the frontend's
    answer-shape renderer (capability-aware visual
    follow-up, out of scope for AI-12)."""

    # SPRINT AI-13 — Production Orchestration wire fields.
    # All three are default-safe so legacy rows that pre-date
    # AI-13 round-trip unchanged.
    tool_execution_traces: list[dict] = Field(default_factory=list)
    """SPRINT AI-13 — one ``ToolExecutionTrace.to_dict()`` per
    executed tool. Each entry carries ``tool_name``,
    ``selected``, ``executed``, ``success``, ``latency_ms``,
    ``result_available``, ``evidence_ids``, ``failure_reason``,
    ``error_category``. Empty list for legacy rows or kill-
    switch-disabled paths."""

    partial_failure_disclosure: str | None = None
    """SPRINT AI-13 — one-line sentence the partial-failure
    handler built. ``None`` when every tool succeeded. Drives
    the inline disclosure block the assistant inserts into
    the answer body."""

    confidence_penalty: int = 0
    """SPRINT AI-13 — integer 0..40 penalty the partial-failure
    handler computed. ``0`` when every tool succeeded. Drives
    the deterministic confidence reduction the UI surfaces."""

    # SPRINT AI-14 — Universal Answer Intelligence + Evidence Graph.
    # Six additive wire mirrors on ``ChatGenerationMeta`` so the
    # frontend can render the AI-14 disclosure (hero direct answer,
    # evidence graph, calculation lineage, missing-data state,
    # unsupported-claim badge, fabricated-source count) without
    # re-parsing the full ``grounded_payload``. All six are
    # default-safe so legacy rows that pre-date AI-14 round-trip
    # unchanged.
    answer_requirements: dict | None = None
    """SPRINT AI-14 — ``AnswerRequirements.to_dict()`` payload:
    the 16-field dataclass describing what the final answer
    needs (16 ``needs_*`` flags + requested entities / metrics /
    time horizon / output format + rationale). Drives the
    hero-direct-answer + max-3-supports composer on the
    frontend. ``None`` for legacy rows."""

    evidence_graph: dict | None = None
    """SPRINT AI-14 — ``AnswerEvidenceGraph.to_dict()`` payload:
    per-claim lineage with nodes (profile / tool / calc /
    external / assumption), edges (supports / derived_from /
    assumes / contradicts), claims, calculations, assumptions,
    external sources, unsupported / fabricated counters, and
    contradiction severity. ``None`` when the engine did not
    run."""

    calculation_lineage: list[dict] = Field(default_factory=list)
    """SPRINT AI-14 — wire list of ``CalculationNode.to_dict()``
    dicts, one per mintable envelope. Empty list when the
    dispatcher ran no calc-capable tool. Each entry carries
    ``calculation_id``, ``name``, ``inputs``, ``formula``,
    ``output``, ``unit``, ``source_evidence_ids``,
    ``tool_name``, ``confidence``."""

    missing_data_state: dict | None = None
    """SPRINT AI-14 — ``missing_data_state(...)`` dict of
    {known, derived, estimated, unknown} claim buckets the
    renderer reads for the "What I know / What I am missing"
    disclosure. ``None`` when the engine did not run."""

    unsupported_claim_count: int = 0
    """SPRINT AI-14 — integer count of ClaimNodes the engine
    flagged ``validation_status == "unsupported"``. Drives the
    "Unsupported claim" badge on the trust bar. ``0`` for
    legacy rows or deterministic-fallback short-circuit."""

    fabricated_source_count: int = 0
    """SPRINT AI-14 — integer count of ``ExternalSourceNode``
    entries whose URL fails the URL guard (authority < 0.5 or
    untrusted domain). ``0`` by default — the AI-14
    ``_TRUSTED_URLS`` allow-list is deliberately empty."""

    # SPRINT AI-15 — Intelligent Visualization + Trust-First UX.
    # Three additive wire mirrors. ``visualization_plans`` powers
    # the chart slots inside TrustFirstResponse (KPI /
    # Progress / Comparison / Trend / Scenario / Risk /
    # Composition / Readiness). ``quality_warning`` drives the
    # concise low-quality warning strip the brief mandates.
    # ``trust_summary`` powers the "Why this answer?" disclosure
    # panel (Evidence / Calculations / Assumptions / Uncertainty
    # / Alternatives). All default-safe so pre-AI-15 rows that
    # pre-date this sprint round-trip unchanged.
    visualization_plans: list[dict] = Field(default_factory=list)
    """SPRINT AI-15 — mirror of
    ``generation.visualization_plans``. List of
    ``VisualizationPlan.to_dict()`` payloads. Empty when the
    planner emits no plans; the renderer falls back to prose."""

    quality_warning: dict | None = None
    """SPRINT AI-15 — mirror of ``generation.quality_warning``.
    ``{"needs_warning": bool, "warning_message": str}`` the
    validator stamps. ``None`` for legacy rows."""

    trust_summary: dict | None = None
    """SPRINT AI-15 — mirror of ``generation.trust_summary``.
    ``build_trust_summary(...)`` payload with the 5 disclosure
    sections plus tools_used / tool_failures / confidence_change.
    ``None`` when the engine did not compute one."""

    # SPRINT AI-16 — Verified External Knowledge + Freshness Layer.
    # Five additive wire mirrors for the AI-16 envelope. Each
    # defaults to a safe empty / None so pre-AI-16 rows that
    # pre-date this sprint round-trip unchanged.
    external_claims: list[dict] = Field(default_factory=list)
    """SPRINT AI-16 — mirror of ``generation.external_claims``.
    List of ``ClassifiedClaim.to_dict()`` payloads the engine
    produced. Each carries ``text``, ``kind``
    (``external_fact`` / ``internal_business`` / ``calculated`` /
    ``scenario`` / ``assumption`` / ``unknown``), ``authority``,
    ``is_verified``, ``notes``, and a ``source`` dict with
    provenance. Empty when no external claims were used."""

    freshness_warnings: list[dict] = Field(default_factory=list)
    """SPRINT AI-16 — mirror of
    ``generation.freshness_warnings``. List of
    ``ExternalSource.to_dict()`` payloads for sources whose
    freshness is AGING / STALE / UNKNOWN. Empty when every
    source is FRESH."""

    scheme_card: dict | None = None
    """SPRINT AI-16 — mirror of ``generation.scheme_card``.
    ``SchemeAnswerCard.to_dict()`` payload with the 10
    brief-mandated fields (official_name, authority, benefit,
    eligibility, documents, application_link, last_verified,
    match_reason, missing_info, final_authority_disclaimer).
    ``None`` for non-scheme prompts."""

    external_answer: dict | None = None
    """SPRINT AI-16 — mirror of ``generation.external_answer``.
    ``ExternalAnswerEnvelope.to_dict()`` payload for concise
    definition-style replies. ``None`` for prompts that the
    full 10-section consultant format serves better."""

    mixed_answer: dict | None = None
    """SPRINT AI-16 — mirror of ``generation.mixed_answer``.
    ``MixedAnswerBlocks`` payload with the four blocks
    (external / business / gap / conclusion) the
    :class:`MixedQuestionSeparator` emits. ``None`` when the
    question was not mixed."""

    # SPRINT AI-17 — Bounded Quality Repair + Claim Lifecycle.
    # Eight additive wire mirrors. Default to safe
    # (empty / None / False) so legacy rows deserialize
    # unchanged.
    failure_classification: str = "none"
    """SPRINT AI-17 — mirror of ``generation.failure_classification``.
    One of the nine
    :data:`app.services.ai.knowledge.ai17_quality_failure_classifier.FAILURE_CLASSES`.
    ``"none"`` for legacy rows."""

    repair_applied: list[str] = Field(default_factory=list)
    """SPRINT AI-17 — mirror of ``generation.repair_applied``.
    List of repair names the deterministic repair dispatcher
    ran. Empty when no repair was needed."""

    retry_attempted: bool = False
    """SPRINT AI-17 — mirror of ``generation.retry_attempted``.
    ``True`` when the bounded retry gate fired the (single,
    terminal) retry. ``False`` for legacy rows."""

    retry_succeeded: bool | None = None
    """SPRINT AI-17 — mirror of ``generation.retry_succeeded``.
    Outcome of the retry. ``None`` when ``retry_attempted``
    is ``False``."""

    numeric_corrections: list[dict] = Field(default_factory=list)
    """SPRINT AI-17 — mirror of ``generation.numeric_corrections``.
    List of :class:`NumericCorrectionAudit.to_dict()` rows.
    Empty when no numeric corrections were made."""

    claim_lifecycle: dict | None = None
    """SPRINT AI-17 — mirror of ``generation.claim_lifecycle``.
    :meth:`ClaimLifecycleStore.to_dict()` payload from the
    AI-17 repair pass. ``None`` for legacy rows."""

    bounded_repair_version: str = ""
    """SPRINT AI-17 — schema version of the AI-17 pipeline.
    Empty when the module did not run."""

    language: str = "en"
    """Language used for generation ('en' | 'kn')."""


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #


class ChatMessageOut(BaseModel):
    """One message in a conversation. Returned by GET /chat/{id}.

    H7.8C — assistant responses now expose the full provenance
    envelope at the TOP level of the message payload, not only
    nested inside ``generation``. Every brief-mandated field
    (provider, model, runtime provider, grounding score,
    evidence references, assumptions, limitations, fallback
    active, mode, confidence) is now a top-level field on this
    model so the frontend can render the trust disclosure without
    drilling into ``generation.*``.

    Backward compatibility
    -----------------------

    * All new fields are **optional** (defaulting to safe
      empties) so older clients that only read ``id``,
      ``role``, ``content`` still parse the response.
    * The ``generation`` block is preserved unchanged for any
      client that already reads it.
    * User turns and legacy rows that pre-date the
      ``generation_meta_json`` column return the new fields as
      empty / ``None`` — exactly the same contract v1 had.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    role: Literal["user", "assistant"]
    kind: str = ""
    content: str = Field(min_length=1)
    sources: list[ChatSource] = Field(default_factory=list)
    created_at: datetime

    # H7.8A P2 — per-message fallback flag. The frontend uses this to
    # decide whether to render the bubble with the
    # "Calculated by UrsBiz rule engine" trust label (True) or the
    # "Generated explanation" label (False, only when a real LLM
    # answered). Defaults to False so user messages and older rows
    # remain valid.
    fallback_used: bool = False

    # H7.8C — full provenance envelope for assistant turns. None
    # on user turns and on legacy rows that pre-date the
    # ``generation_meta_json`` column.
    generation: ChatGenerationMeta | None = None

    # ---- H7.8C — top-level provenance fields ------------------------- #
    #
    # Every field below is a flat mirror of the matching
    # ``generation.*`` value. The frontend trust disclosure
    # (provider name, model, grounding score, evidence count,
    # assumptions, limitations, mode, confidence, fallback
    # active) is now reachable without parsing the
    # ``generation`` block.
    #
    # The mirrors are NEVER derived from a hidden source — they
    # are read from the same ``GenerationMeta`` the assistant
    # layer stamps on every reply. If a mirror disagrees with
    # ``generation.*`` the renderer should prefer ``generation``
    # (the structured envelope is the authoritative source).

    provider: str = Field(default="", max_length=80)
    """The model-side ``provider`` field. ``"deterministic-fallback"``
    when the deterministic fallback answered; ``"openai_compatible"``
    / ``"ollama"`` when a real provider answered."""

    model: str = Field(default="", max_length=120)
    """The model identifier the provider stamped on the response."""

    runtime_provider: str = Field(default="", max_length=80)
    """H7.8C — the runtime provider that actually answered the
    request. Equal to ``provider`` for the deterministic
    fallback path; equal to ``provider`` for any real call
    (the value is differentiated from ``provider`` so the
    frontend can render the "trusted runtime" badge
    separately from the "configured provider" label)."""

    grounding_score: int = Field(default=0, ge=0, le=100)
    """The server-computed grounding score (0–100). Mirrors
    ``generation.server_grounding_score``. The deterministic
    fallback always reports 100 (grounded by construction);
    a real provider's score reflects how many data sources
    the answer cited."""

    evidence_references: list[str] = Field(default_factory=list)
    """Mirrors ``generation.evidence_references`` — the list
    of Evidence Registry IDs the answer cited."""

    assumptions: list[str] = Field(default_factory=list)
    """Mirrors ``generation.assumptions`` — the assumptions the
    provider / fallback surfaced with the answer."""

    limitations: list[str] = Field(default_factory=list)
    """Mirrors ``generation.limitations`` — the limitations the
    provider / fallback surfaced with the answer."""

    fallback_active: bool = False
    """H7.8C — same semantic as ``fallback_used`` but exposed
    under the brief-mandated name. Always equals ``fallback_used``
    on this message (kept as a separate field so the frontend
    can branch on either name)."""

    mode: Literal["grounded", "open"] | None = None
    """The mode the assistant ran under. ``None`` for user turns
    and for legacy rows that pre-date the column."""

    language: str = "en"
    """The language the message was generated in ('en' | 'kn')."""

    confidence: int | None = Field(default=None, ge=0, le=100)
    """Mirrors ``generation.confidence`` — the provider's
    self-reported confidence (0–100). ``None`` when the
    provider did not emit one (the deterministic fallback
    fills it with the configured value)."""

    # AI-1 — universal-assistant audit trail mirrors. Each
    # field mirrors the matching ``generation.*`` value so
    # the frontend trust disclosure can render the dispatch
    # + claim-category + understanding audit without parsing
    # the structured envelope. All default to safe empties.
    deterministic_services_used: list[str] = Field(default_factory=list)
    """Mirrors ``generation.deterministic_services_used`` —
    the deterministic engines the ToolDispatcher invoked
    during this turn."""

    calculations_used: list[str] = Field(default_factory=list)
    """Mirrors ``generation.calculations_used`` — the
    deterministic calc names whose authoritative output the
    LLM was shown."""

    question_understanding: dict | None = None
    """Mirrors ``generation.question_understanding`` — the
    Stage 1 QuestionUnderstanding dict the universal-assistant
    layer produced for this turn. ``None`` when no
    understanding was produced (legacy callers)."""

    tool_calls: list[dict] = Field(default_factory=list)
    """Mirrors ``generation.tool_calls`` — the ToolCall
    tuples the dispatcher selected, as a list of dicts."""

    claim_categories_used: list[str] = Field(default_factory=list)
    """Mirrors ``generation.claim_categories_used`` — the
    claim-category labels the validator observed on the
    LLM's prose (FACT/CALCULATION/INFERENCE/RECOMMENDATION/
    SCENARIO/EXTERNAL_FACT/UNKNOWN)."""

    # SPRINT AI-3 — claim-aware response mirrors. Every
    # chat reply (real LLM or fallback) carries a non-None
    # ``claim_aware_response``; the server stamps the
    # ``server_confidence`` value via the deterministic
    # calculator.
    claim_aware_response: ChatClaimAwareResponse | None = None
    """SPRINT AI-3 — the validated claim-aware envelope.
    ``None`` only on legacy rows that pre-date the column."""

    server_confidence: int | None = Field(default=None, ge=0, le=100)
    """SPRINT AI-3 — server-computed confidence, 0..100.
    The LLM's self-reported confidence (in
    ``generation.grounded_payload["confidence"]``) is
    recorded but never overrides this value."""

    server_confidence_rationale: str = Field(default="", max_length=500)
    """SPRINT AI-3 — one-line English summary of the top
    three contributors to ``server_confidence``."""

    numeric_conflicts_count: int = Field(default=0, ge=0)
    """SPRINT AI-3 — count of NumericConflict records the
    numeric checker emitted on this turn. Zero when the
    LLM didn't fill claim_aware or when no conflicts fired."""

    claim_aware_validated: bool = False
    """SPRINT AI-3 — True iff the AI-3 layer successfully
    parsed and validated the LLM's claim_aware payload
    (or the fallback built one from AssistantContext)."""

    claim_audit: dict | None = None
    """SPRINT AI-4 — the full ``ClaimAuditReport.to_dict()``
    payload. None for legacy rows that pre-date AI-4; the
    deterministic fallback ALWAYS populates it."""

    claim_audit_rejected: bool = False
    """SPRINT AI-4 — True iff the AI-4 auditor triggered any
    hard-rejection condition. The frontend renders an
    "Answer withheld — reason" stub when this flag is True."""

    claim_audit_soft_corrections: int = Field(default=0, ge=0)
    """SPRINT AI-4 — count of claims the auditor rewrote
    without rejecting the whole answer. Zero when no
    soft-correction was applied."""

    claim_audit_trace: ChatClaimAuditTrace | None = None
    """SPRINT AI-4 — typed mirror of the AI-4 auditor trace.
    ``None`` for legacy rows that pre-date AI-4; the
    deterministic fallback ALWAYS populates it. The raw
    dict form is also exposed via ``claim_audit`` for
    backends that introspect the audit JSON."""

    scenario_analysis: dict | None = None
    """SPRINT AI-5 — the structured 10-field "what if" envelope
    from the Business Scenario Copilot. ``None`` for non-scenario
    prompts (the LLM route runs unchanged) and for legacy rows
    that pre-date AI-5. The frontend ``ScenarioAnalysisCard``
    renders this directly above the assistant body when it is
    non-None. The ``scenario_analysis`` field is the raw dict
    shape from ``ScenarioAnalysis.to_dict()``; a typed mirror
    is also exposed via ``scenario_analysis_typed``."""

    scenario_analysis_typed: ChatScenarioAnalysis | None = None
    """SPRINT AI-5 — Pydantic-typed mirror of the envelope.
    Always ``None`` for non-scenario prompts and legacy rows;
    the deterministic fallback for "what if" prompts ALWAYS
    populates it. Carries ``extra="forbid"`` so no unknown
    fields surface on the wire."""

    direct_answer: str | None = None
    """SPRINT AI-6 — Trust-first visual UI. The first 1-3
    sentences of the assistant's prose, server-extracted and
    ready for the frontend to render as the "Direct Answer"
    10-second-read header. ``None`` when the assistant didn't
    produce extractable prose, or for legacy rows that
    pre-date AI-6; the frontend projector falls back to
    ``consultant.body`` / ``content`` in that case. Mirrors
    ``generation.direct_answer`` so the frontend can read it
    without parsing the structured envelope."""

    missing_data: list[dict] = Field(default_factory=list)
    """SPRINT AI-7 — Missing-data intelligence. Structured list
    of ``MissingDataObject`` dicts the proactive detector surfaces
    BEFORE the provider call. Each dict carries ``field``,
    ``importance`` (``LOW | MEDIUM | HIGH``), ``reason``,
    ``affects`` (list[str]), ``suggested_source``. The frontend
    ``MissingInfoCard`` renders the 4-section "What I can tell /
    What I am missing / Why it matters / Next step" layout when
    the list is non-empty. Default empty list so legacy rows that
    pre-date AI-7 still deserialize; the AI-6 prose
    ``MissingInfoBody`` fallback renders unchanged in that case."""

    llm_tool_results: list[dict] = Field(default_factory=list)
    """SPRINT AI-8 — Controlled Business Tool Router. Validated
    + sanitised + evidence-stamped results from the optional
    2nd-turn tool-loop. Each dict carries ``tool`` (whitelist
    name), ``status`` (``"ok" | "skipped" | "error"``),
    ``evidence_ids`` (list[str]), ``payload`` (dict),
    ``duration_ms`` (int), ``error`` (str | None). Empty list
    when the LLM did NOT request any tools (legacy rows +
    first-turn LLMs that never emit ``tool_calls``); the
    frontend ``ReasoningTrace`` falls back to the existing
    rendering. Field appended at the END to preserve the
    additive-compat pattern of every AI-N sprint."""

    llm_tool_results: list[dict] = Field(default_factory=list)
    """SPRINT AI-8 — Controlled Business Tool Router. Validated
    + sanitised + evidence-stamped tool-loop results from the
    optional 2nd-turn provider call. Each dict carries
    ``tool`` (whitelist name), ``status`` (``"ok" | "skipped"
    | "error"``), ``evidence_ids`` (list[str]), ``payload``
    (dict), ``duration_ms`` (int), ``error`` (str | None). Empty
    list when the LLM did NOT request any tools (legacy rows
    + first-turn LLMs that never emit ``tool_calls``); the
    frontend ``ReasoningTrace`` falls back to the existing
    rendering. Field appended at the END to preserve the
    additive-compat pattern of every AI-N sprint."""

    explanation: dict | None = None
    """SPRINT AI-10 — Explain My Answer. Top-level mirror of
    ``generation.explanation`` — per-recommendation decision
    traces keyed by ``recommendation_id``. Each value is a
    dict with six sections (evidence, calculations,
    decision_factors, assumptions, uncertainty,
    alternatives) plus confidence + confidence_label.
    ``None`` for legacy rows that pre-date AI-10; the
    frontend ``ExplanationPanel`` reads this field
    directly. Trace strings are derived from structured
    provenance metadata — no LLM chain-of-thought is
    ever exposed."""

    capability: list[str] = Field(default_factory=list)
    """SPRINT AI-11 — Universal Business-Aware Assistant
    hardening. Top-level mirror of
    ``generation.capability``. Multi-label tuple describing
    what capabilities the prompt required. Defaults to an
    empty list so every pre-AI-11 row deserialises
    unchanged. Field appended at the END to preserve the
    additive-compat pattern of every AI-N sprint."""

    business_dependency: str = "none"
    """SPRINT AI-11 — Top-level mirror of
    ``generation.business_dependency``. Three-valued
    literal — one of ``"none"`` / ``"optional"`` /
    ``"required"``. Defaults to ``"none"`` so every
    pre-AI-11 row deserialises unchanged. Field appended at
    the END to preserve the additive-compat pattern of every
    AI-N sprint."""

    # SPRINT AI-12 — Universal Reasoning Layer wire mirrors.
    # Each field is a flat mirror of the matching
    # ``generation.*`` value so the frontend can render the
    # universal-reasoning audit without parsing the structured
    # envelope. All default to safe empties.
    tool_plan: dict | None = None
    """SPRINT AI-12 — top-level mirror of ``generation.tool_plan``.
    Carries ``required`` / ``optional`` / ``parallelizable`` /
    ``sequential`` / ``rationale``. ``None`` for legacy rows
    that pre-date AI-12."""

    evidence_requirements: dict | None = None
    """SPRINT AI-12 — top-level mirror of
    ``generation.evidence_requirements``. Carries
    ``required`` / ``optional`` / ``rationale``. ``None`` for
    legacy rows."""

    contradiction_report: dict | None = None
    """SPRINT AI-12 — top-level mirror of
    ``generation.contradiction_report``. Carries
    ``severity`` / ``items`` / ``rationale``. ``None`` for
    legacy rows."""

    answer_quality: dict | None = None
    """SPRINT AI-12 — top-level mirror of
    ``generation.answer_quality``. Carries the 8 axis scores,
    ``total``, ``weakest_axis``, ``needs_retry``. ``None``
    for legacy rows."""

    structured_tool_envelopes: list[dict] = Field(default_factory=list)
    """SPRINT AI-12 — top-level mirror of
    ``generation.structured_tool_envelopes``. Empty list for
    legacy rows."""

    answer_mode: str = "general_knowledge"
    """SPRINT AI-12 — top-level mirror of
    ``generation.answer_mode``. The capability-aware shape
    signal. Default ``"general_knowledge"`` keeps legacy
    rows valid."""

    # SPRINT AI-13 — top-level mirrors of the AI-13 wire
    # fields. All default-safe so legacy rows that pre-date
    # AI-13 round-trip unchanged.
    tool_execution_traces: list[dict] = Field(default_factory=list)
    """SPRINT AI-13 — top-level mirror of
    ``generation.tool_execution_traces``. One trace per
    executed tool. Empty list for legacy rows."""

    partial_failure_disclosure: str | None = None
    """SPRINT AI-13 — top-level mirror of
    ``generation.partial_failure_disclosure``. The one-line
    sentence the partial-failure handler built. ``None``
    when every tool succeeded."""

    confidence_penalty: int = 0
    """SPRINT AI-13 — top-level mirror of
    ``generation.confidence_penalty``. Integer 0..40
    deterministic penalty from the partial-failure handler."""

    # SPRINT AI-14 — Universal Answer Intelligence + Evidence
    # Graph. The envelope exposes 6 additive wire mirrors so the
    # frontend can render the trust bar + lineage disclosure in
    # a single TypeScript destructure. The first two
    # (``answer_requirements`` + ``evidence_graph``) are the
    # largest JSON shapes (16-field + multi-tuple dataclasses)
    # so they live at the top level; the remaining four are
    # short scalars/lists so they sit alongside the legacy
    # AI-13 top-level mirrors. All default-safe so legacy rows
    # that pre-date AI-14 round-trip unchanged.
    answer_requirements: dict | None = None
    """SPRINT AI-14 — top-level mirror of
    ``generation.answer_requirements``. ``AnswerRequirements
    .to_dict()`` payload. Drives the dynamic answer composer
    + hero-direct-answer + max-3-supports UX. ``None`` for
    legacy rows."""

    evidence_graph: dict | None = None
    """SPRINT AI-14 — top-level mirror of
    ``generation.evidence_graph``. ``AnswerEvidenceGraph
    .to_dict()`` payload. Powers the per-claim lineage
    disclosure + evidence-graph summary the frontend renders
    inside the existing technical-provenance panel. ``None``
    when the engine did not run."""

    calculation_lineage: list[dict] = Field(default_factory=list)
    """SPRINT AI-14 — top-level mirror of
    ``generation.calculation_lineage``. Per-envelope
    ``CalculationNode.to_dict()`` payloads (inputs / formula /
    output / unit / source / calculation_id). Empty list for
    legacy rows or non-calculation prompts."""

    missing_data_state: dict | None = None
    """SPRINT AI-14 — top-level mirror of
    ``generation.missing_data_state``. Buckets the graph's
    claims into ``{known, derived, estimated, unknown}`` so the
    frontend can render an honest "what I am missing" panel.
    ``None`` when the engine did not compute one."""

    unsupported_claim_count: int = 0
    """SPRINT AI-14 — top-level mirror of
    ``generation.unsupported_claim_count``. Integer count of
    claims the engine could not validate against the evidence
    graph. ``0`` for legacy rows and for fully-grounded
    responses."""

    fabricated_source_count: int = 0
    """SPRINT AI-14 — top-level mirror of
    ``generation.fabricated_source_count``. Integer count of
    external-source nodes that failed the URL-guard heuristic
    (authority < 0.5 or unregistered URL). ``0`` for legacy
    rows and for canonical sources."""

    # SPRINT AI-15 — three top-level mirrors of the AI-15 wire
    # envelope. ``visualization_plans`` powers the chart slots
    # inside TrustFirstResponse. ``quality_warning`` powers the
    # concise low-quality warning strip. ``trust_summary``
    # powers the "Why this answer?" disclosure panel. All
    # default-safe so pre-AI-15 rows that pre-date this sprint
    # round-trip unchanged.
    visualization_plans: list[dict] = Field(default_factory=list)
    """SPRINT AI-15 — top-level mirror of
    ``generation.visualization_plans``. List of
    ``VisualizationPlan.to_dict()`` payloads. Empty when the
    planner emits no plans; the renderer falls back to prose."""

    quality_warning: dict | None = None
    """SPRINT AI-15 — top-level mirror of
    ``generation.quality_warning``. Drives the concise
    low-quality warning strip the brief mandates (``None`` for
    legacy rows)."""

    trust_summary: dict | None = None
    """SPRINT AI-15 — top-level mirror of
    ``generation.trust_summary``. Powers the "Why this
    answer?" disclosure panel. ``None`` for legacy rows."""

    # SPRINT AI-16 — top-level mirrors of the AI-16 envelope.
    # Default-safe so legacy rows deserialize unchanged.
    external_claims: list[dict] = Field(default_factory=list)
    """SPRINT AI-16 — top-level mirror of
    ``generation.external_claims``. List of
    ``ClassifiedClaim.to_dict()`` payloads."""

    freshness_warnings: list[dict] = Field(default_factory=list)
    """SPRINT AI-16 — top-level mirror of
    ``generation.freshness_warnings``. List of AGING / STALE /
    UNKNOWN external sources."""

    scheme_card: dict | None = None
    """SPRINT AI-16 — top-level mirror of
    ``generation.scheme_card``. ``SchemeAnswerCard.to_dict()``
    payload."""

    external_answer: dict | None = None
    """SPRINT AI-16 — top-level mirror of
    ``generation.external_answer``.
    ``ExternalAnswerEnvelope.to_dict()`` payload."""

    mixed_answer: dict | None = None
    """SPRINT AI-16 — top-level mirror of
    ``generation.mixed_answer``. ``MixedAnswerBlocks`` payload
    for mixed questions."""

    # SPRINT AI-17 — top-level mirrors of the AI-17 envelope.
    # Default-safe so legacy rows deserialize unchanged.
    failure_classification: str = "none"
    """SPRINT AI-17 — top-level mirror of
    ``generation.failure_classification``."""

    repair_applied: list[str] = Field(default_factory=list)
    """SPRINT AI-17 — top-level mirror of
    ``generation.repair_applied``."""

    retry_attempted: bool = False
    """SPRINT AI-17 — top-level mirror of
    ``generation.retry_attempted``."""

    retry_succeeded: bool | None = None
    """SPRINT AI-17 — top-level mirror of
    ``generation.retry_succeeded``."""

    numeric_corrections: list[dict] = Field(default_factory=list)
    """SPRINT AI-17 — top-level mirror of
    ``generation.numeric_corrections``."""

    claim_lifecycle: dict | None = None
    """SPRINT AI-17 — top-level mirror of
    ``generation.claim_lifecycle``."""

    bounded_repair_version: str = ""
    """SPRINT AI-17 — top-level mirror of
    ``generation.bounded_repair_version``."""


# --------------------------------------------------------------------------- #
# Conversation
# --------------------------------------------------------------------------- #


class ChatSessionSummary(BaseModel):
    """A conversation as it appears in the sidebar / list endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    summary: str
    message_count: int = Field(ge=0)
    last_model: str = ""
    fallback_used: bool
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(BaseModel):
    """A conversation with every message inline."""

    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    summary: str
    message_count: int = Field(ge=0)
    last_model: str = ""
    fallback_used: bool
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Request envelopes
# --------------------------------------------------------------------------- #


class ChatSessionCreateRequest(BaseModel):
    """Body for POST /chat (create a new conversation)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=120)


class ChatMessageCreateRequest(BaseModel):
    """Body for POST /chat/{id}/message (append a user message)."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    # H7.8C — the hybrid mode. ``grounded`` is the default
    # (evidence-bounded); ``open`` is permissive.
    mode: Literal["grounded", "open"] = "grounded"
    language: Literal["en", "kn"] = "en"


# --------------------------------------------------------------------------- #
# Response envelopes
# --------------------------------------------------------------------------- #


class ChatMessageAppendResponse(BaseModel):
    """Reply body for POST /chat/{id}/message."""

    model_config = ConfigDict(extra="forbid")

    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    session: ChatSessionDetail


class ChatSessionListResponse(BaseModel):
    """Reply body for GET /chat."""

    model_config = ConfigDict(extra="forbid")

    sessions: list[ChatSessionSummary]
    count: int = Field(ge=0)


class ChatDeleteResponse(BaseModel):
    """Reply body for DELETE /chat/{id}."""

    model_config = ConfigDict(extra="forbid")

    deleted: bool
    id: int


# --------------------------------------------------------------------------- #
# H7.8C — provider status endpoint
# --------------------------------------------------------------------------- #


class ChatProviderStatusResponse(BaseModel):
    """Reply body for GET /chat/provider-status.

    The endpoint never exposes the API key, the auth header,
    or the full upstream base URL. The renderer only needs the
    provider *name*, the configured *model*, whether the
    provider is reachable *now*, and the list of supported
    *modes* — enough for the header dot and the mode toggle.

    H7.9R+ — ``reason`` carries a frontend-safe string that
    explains *why* the boolean is what it is. The frontend
    branches on it to render "Provider unavailable" vs
    "Missing API key" vs "Reachable" without parsing logs.
    """

    model_config = ConfigDict(extra="forbid")

    configured_provider: str = Field(min_length=1, max_length=80)
    runtime_provider: str = Field(min_length=1, max_length=80)
    model: str = Field(default="", max_length=120)
    available: bool
    schema_required: bool
    fallback_active: bool
    reason: Literal[
        "reachable",
        "missing_api_key",
        "missing_base_url",
        "ping_failed",
        "placeholder",
        "provider_unconfigured",
    ] = "provider_unconfigured"
    modes: list[Literal["grounded", "open"]] = Field(default_factory=list)
    default_mode: Literal["grounded", "open"] = "grounded"
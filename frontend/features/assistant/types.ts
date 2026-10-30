/**
 * Types for the AI Business Assistant UI (Sprint 7 Part 1).
 *
 * Frontend only. The assistant is a deterministic
 * composer that reads the existing Twin, Recommendations,
 * Roadmap, Rules, and Decision payloads and joins them into
 * a chat-shaped view. There is no LLM call — every response
 * is built locally from fields the upstream payloads already
 * carry.
 *
 * Type families:
 *   - ChatMessage / Conversation        user-facing chat model
 *   - AssistantContext                  the side-panel data
 *   - AssistantResponse                 the deterministic answer
 *   - SuggestedQuestion                 the question chips
 *   - QueryKind                         the intent classifier
 */

// --------------------------------------------------------------------------- //
// Query kind — the deterministic intent classifier picks one of these for
// every user prompt (or suggested-question click). The builder then walks
// the relevant upstream payload and assembles the response.
// --------------------------------------------------------------------------- //

export type QueryKind =
  | "improve_business"
  | "low_score"
  | "what_first"
  | "export_opportunities"
  | "business_dna"
  | "explain_roadmap"
  | "explain_recommendations"
  | "explain_insights"
  | "explain_rules"
  | "general_overview"
  | "growth_strategy"
  | "digital_transformation"
  | "finance"
  | "gst"
  | "government_schemes"
  | "marketing"
  | "operations"
  | "hiring"
  | "compliance"
  | "risk"
  | "scaling"
  | "decision_hire"
  | "decision_expand"
  | "decision_loan"
  | "action_plan"
  | "growth_target"
  | "product_help"
  | "fallback";

// --------------------------------------------------------------------------- //
// Suggested question
// --------------------------------------------------------------------------- //

export interface SuggestedQuestion {
  /** Stable id used as a React key + click handler arg. */
  id: string;
  /** The question shown on the chip. */
  text: string;
  /**
   * The query kind the chip routes to. Lets the chip
   * author pair copy with the deterministic builder
   * that should answer it.
   */
  kind: QueryKind;
}

// --------------------------------------------------------------------------- //
// Chat model
// --------------------------------------------------------------------------- //

export type ChatRole = "user" | "assistant";

export interface ChatSource {
  /** One-word topic the response drew on. */
  topic:
    | "Twin"
    | "Recommendations"
    | "Roadmap"
    | "Insights"
    | "Rules"
    | "Business DNA"
    | "Export";
  /** One-sentence gloss shown when the user expands the source list. */
  detail: string;
}

export interface ChatMessage {
  /** Local id, generated client-side. */
  id: string;
  role: ChatRole;
  /**
   * For user messages: the literal prompt.
   * For assistant messages: the rendered markdown-ish text (plain
   * text with line breaks — the renderer splits on `\n\n` for
   * paragraphs and on `\n- ` for bullet lists).
   */
  content: string;
  /** ISO timestamp captured at message creation. */
  createdAt: string;
  /** Which upstream payloads the assistant drew on, in order. */
  sources?: ChatSource[];
  /** The intent that produced the assistant's answer. */
  kind?: QueryKind;
  /** Sprint H4 — McKinsey-grade structured payload. */
  consultant?: ConsultantResponse;
  /**
   * H7.8A P2 — per-message fallback flag.
   *
   * For the client-side deterministic consultant the answer is
   * always rule-engine derived (no LLM), so the UI MUST render
   * "Calculated by UrsBiz rule engine". For backend chat
   * sessions (ChatMessageOut), the flag is supplied by the
   * server and the same rule applies.
   *
   * Default: `true` for the client deterministic consultant
   * because every response it produces is rule-engine derived.
   */
  fallback_used?: boolean;
  /**
   * H7.8C — per-message GenerationMeta envelope from the
   * backend. Provides the trust label source-of-truth:
   * provider, model, mode, fallback_reason, evidence_count,
   * schema_validated, grounding_validated, latency, etc.
   *
   * Absent for messages created by the client-side
   * deterministic consultant (no server round-trip).
   */
  generation?: ChatGenerationMeta;
  /**
   * Sprint AI-5 — Business Scenario Copilot envelope. The
   * structured 10-field "what if" envelope from the backend
   * (mirrored at the top level of ChatMessageOut). The
   * frontend ``ScenarioAnalysisCard`` renders this directly
   * above the assistant body when it is non-null. The card
   * is hidden entirely when this field is missing or
   * ``present === false``.
   *
   * Tolerance: every field is optional so legacy rows that
   * pre-date AI-5 still type-check.
   */
  scenario_analysis?: {
    scenario_name?: string;
    baseline?: string[];
    changes?: string[];
    assumptions?: string[];
    calculation_method?: string;
    estimated_effects?: string[];
    risks?: string[];
    unknowns?: string[];
    sensitivity?: string[];
    confidence?: string;
    disclaimer?: string;
    present?: boolean;
  };
  /**
   * Sprint AI-6 — Trust-first visual UI.
   *
   * Server-stamped first 1-3 sentences from the assistant's
   * full prose. The frontend ``TrustFirstResponse`` shell
   * renders this as the "Direct Answer" — the 10-second read
   * the user sees before any disclosure. ``undefined`` (the
   * default) means the projector must derive the answer
   * locally from ``consultant.body`` or ``content`` via
   * ``resolveDirectAnswer``.
   */
  direct_answer?: string | null;
  /**
   * Sprint AI-7 — Missing-data intelligence.
   *
   * Structured list of ``MissingDataObject`` rows the backend
   * proactive detector (step 3.7 of the chat pipeline) +
   * reactive enrichment pass (step 5.8) emitted BEFORE the
   * brief's "I can't calculate X" LLM surface. Each row
   * carries the field name, importance tier, the reason it
   * matters, the analysis dimensions it affects, and a
   * suggested source for the user.
   *
   * The ``MissingInfoCard`` component renders the 4-section
   * "What I can tell / What I am missing / Why it matters /
   * Next step" layout whenever this list is non-empty. When
   * absent or empty (legacy rows + intents without a
   * required-field map), the AI-6 prose fallback path renders
   * unchanged.
   */
  missing_data?: MissingDataObject[];
  /**
   * Sprint AI-8 — Controlled Business Tool Router.
   *
   * The sanitized, server-stamped results of the 2-turn LLM
   * tool loop. Each entry is the router's verdict for one
   * tool the LLM REQUESTED in its 1st-turn payload
   * (``tool_calls``). The deterministic engines ran the
   * tool, the router validated + sanitised the output, and
   * the LLM was given the verified facts as a 2nd-turn input.
   *
   * Each entry carries:
   *   - ``tool``         — the whitelisted tool name (e.g.
   *                        ``"calculate_revenue_growth"``).
   *   - ``status``       — ``"ok"`` (succeeded), ``"skipped"``
   *                        (e.g. timed out), or ``"error"``
   *                        (router rejected: unknown tool,
   *                        invalid args, wrong intent, etc.).
   *   - ``evidence_ids`` — stable IDs the assistant will cite.
   *   - ``payload``      — sanitised JSON payload (free-form;
   *                        per-tool shape).
   *   - ``duration_ms``  — round-trip latency in ms.
   *   - ``error``        — rejection reason for the LLM's 2nd
   *                        turn when status !== "ok".
   *
   * The shell renders a single-line "Used tools" pill row
   * inside the technical provenance disclosure (green dot
   * for ``ok``, red for ``error``, grey for ``skipped``).
   * Absent or empty list (legacy rows + intents that did
   * not trigger the tool loop) renders nothing.
   */
  llm_tool_results?: LLMToolResult[];
  /**
   * Sprint AI-10 — Explain My Answer.
   *
   * Per-recommendation decision traces keyed by
   * ``recommendation_id``. Each value carries six sections
   * (evidence, calculations, decision_factors, assumptions,
   * uncertainty, alternatives) plus confidence +
   * confidence_label. Every string in the trace comes from
   * structured provenance metadata — no LLM chain-of-thought
   * is ever exposed.
   *
   * The ``ExplanationPanelStack`` renders one collapsible
   * accordion per recommendation. Absent or empty (legacy rows
   * + turns with no recommendations) renders nothing — the
   * panel is hidden entirely.
   */
  explanation?: ChatExplanation;
  /**
   * Sprint AI-13 — top-level mirror of
   * ``generation.tool_execution_traces``. Each entry is the
   * JSON-serialised shape of ``ToolExecutionTrace``
   * (``tool_name``, ``selected``, ``executed``, ``success``,
   * ``latency_ms``, ``result_available``, ``evidence_ids``,
   * ``failure_reason``, ``error_category``). The
   * ``TrustFirstResponse`` shell renders these in the
   * technical-provenance disclosure as a colour-coded pill
   * row. Empty array when no tools ran or the kill-switch
   * was off.
   */
  tool_execution_traces?: Record<string, unknown>[];
  /**
   * Sprint AI-13 — one-line sentence describing which tools
   * failed (e.g. ``"predictive_sprint14 timed out, so the
   * predictive_sprint14 portion could not be verified"``).
   * null when every tool succeeded.
   */
  partial_failure_disclosure?: string | null;
  /**
   * Sprint AI-13 — integer 0..40 confidence penalty the
   * partial-failure handler computed. 0 when every tool
   * succeeded. The frontend's trust badge uses this to
   * downgrade the label when > 0.
   */
  confidence_penalty?: number;
  /**
   * Sprint AI-14 — top-level mirror of
   * ``generation.answer_requirements``. Drives the dynamic
   * answer composer + hero-direct-answer + max-3-supports UX.
   */
  answer_requirements?: Record<string, unknown> | null;
  /**
   * Sprint AI-14 — top-level mirror of
   * ``generation.evidence_graph``. Powers the per-claim lineage
   * disclosure + evidence-graph summary inside the existing
   * technical-provenance panel.
   */
  evidence_graph?: Record<string, unknown> | null;
  /**
   * Sprint AI-15 — top-level mirror of
   * ``generation.visualization_plans``. The server-owned
   * VisualizationPlan list the planner emitted for this turn.
   * Each entry carries ``chart_kind``, ``title``, ``purpose``,
   * ``recommended_display``, ``explanation``,
   * ``source_evidence_ids``, ``calculation_ids``,
   * ``assumptions``, ``limitations``, ``confidence``, plus the
   * builder-emitted ``data`` + ``empty_reason``. The frontend
   * ``VisualizationCard`` renders one block per plan (capped
   * to MAX_VIZ_BLOCKS=1). Empty array when the planner emits
   * no plans (the renderer falls back to prose).
   */
  visualization_plans?: VisualizationPlan[];
  /**
   * Sprint AI-15 — top-level mirror of
   * ``generation.quality_warning``. Drives the concise
   * low-quality warning strip the brief mandates. ``null``
   * when the validator did not compute one.
   */
  quality_warning?: {
    needs_warning?: boolean;
    warning_message?: string;
  } | null;
  /**
   * Sprint AI-15 — top-level mirror of
   * ``generation.trust_summary``. Powers the "Why this
   * answer?" disclosure panel (Evidence / Calculations /
   * Assumptions / Uncertainty / Alternatives + tools_used /
   * tool_failures / confidence_change). ``null`` when the
   * engine did not compute one.
   */
  trust_summary?: TrustSummary | null;
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.scheme_card``. The conservative scheme
   * advisory card the engine emits only when the QU capability
   * contains GOVERNMENT_SCHEME / EXPORT and a scheme ID can
   * be selected from the literal question. The
   * ``SchemeAnswerCardView`` component renders this directly
   * above the assistant body. The slot is hidden when this is
   * ``null`` or ``undefined``.
   */
  scheme_card?: SchemeAnswerCard | null;
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.external_answer``. The concise external-only
   * reply envelope the engine emits when the prompt is purely
   * external (e.g. "What is EBITDA?"). The renderer surfaces
   * this as a single inline block. Hidden when ``null``.
   */
  external_answer?: ExternalClaim | null;
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.mixed_answer``. The 7-section decomposition
   * the engine emits only when the QU answer_mode is "mixed"
   * (general + business capabilities crossed). The
   * ``MixedSections`` component renders this as a compact
   * inline block. Hidden when ``null`` or
   * ``is_mixed === false``.
   */
  mixed_answer?: MixedAnswer | null;
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.external_claims``. Every external-source
   * claim the engine cited in this turn. Surfaced inside the
   * technical-provenance disclosure. Empty array when the
   * turn used no external sources.
   */
  external_claims?: ExternalClaim[];
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.freshness_warnings``. The list of external
   * sources whose freshness bucket is AGING / STALE / UNKNOWN.
   * The ``FreshnessWarningsList`` component renders this as
   * a single inline amber notice. Hidden when empty.
   */
  freshness_warnings?: FreshnessWarning[];
}

/**
 * Sprint AI-15 — wire shape of a single VisualizationPlan the
 * server emitted. Mirrors the backend
 * :class:`VisualizationPlan.to_dict()` payload.
 */
export interface VisualizationPlan {
  chart_kind:
    | "kpi"
    | "progress"
    | "comparison"
    | "trend"
    | "scenario"
    | "risk"
    | "composition"
    | "readiness";
  title: string;
  purpose: string;
  recommended_display: string;
  explanation: string;
  source_evidence_ids: string[];
  calculation_ids: string[];
  assumptions: string[];
  limitations: string[];
  confidence: number;
  /** Optional unit the chart renderer applies (e.g. "INR", "%"). */
  unit?: string | null;
  data?: Record<string, unknown>;
  empty_reason?: string;
  missing_fields?: string[];
}

/**
 * Sprint AI-15 — wire shape of the disclosure payload the
 * server builds. Mirrors the backend
 * :class:`build_trust_summary(...)` return value.
 */
export interface TrustSummary {
  evidence: string[];
  calculations: string[];
  assumptions: string[];
  uncertainty: string[];
  alternatives: string[];
  tools_used: string[];
  tool_failures: Array<{ tool: string; status: string; error: string }>;
  confidence_change: string;
  quality_warning: string | null;
}

// --------------------------------------------------------------------------- //
// Sprint AI-16 — Mixed Question Answer Composition + Scheme Card.
// --------------------------------------------------------------------------- //
//
// The brief mandates three structured payloads the renderer mounts
// in addition to the existing AI-6 TrustFirstResponse shell:
//
//   * SchemeAnswerCard — 13-field advisory card with conservative
//     eligibility language. Mounted when the QU capability contains
//     GOVERNMENT_SCHEME / EXPORT and the literal question names a
//     specific scheme (or falls back to Udyam).
//   * MixedAnswer — 7-section decomposition (general_explanation,
//     business_interpretation, calculation, recommendation,
//     schemes, uncertainty, next_action). Mounted only when the
//     QU answer_mode == "mixed" OR the capability tuple contains
//     MIXED.
//   * ExternalClaim + FreshnessWarning — single-row + list payloads
//     the engine stamps onto every external-source answer. The
//     renderer surfaces the freshness list as an inline amber
//     notice.
//
// Every field below is optional so legacy rows + non-scheme /
// non-mixed prompts type-check unchanged. The renderer MUST hide
// any slot whose payload is null / empty.

/**
 * Sprint AI-16 — wire shape of a single government-scheme
 * advisory card. Mirrors the backend
 * :class:`SchemeAnswerCard.to_dict()` payload (13 fields).
 *
 * The card is the single canonical answer for a scheme prompt —
 * the engine must not append a paragraph-style "you are eligible"
 * narrative that could override the conservative language. The
 * ``match_disposition`` drives one of four brief-mandated
 * renderer phrases:
 *
 *   - "Likely match based on available data."
 *   - "Appears eligible based on available data."
 *   - "Requires verification to confirm eligibility."
 *   - "Insufficient information to determine eligibility."
 */
export interface SchemeAnswerCard {
  scheme_id: string;
  official_name: string;
  authority: string;
  benefit_description: string[];
  eligibility: string[];
  required_documents: string[];
  application_link: string;
  /** ISO date the external source was last verified. */
  last_verified_date: string;
  why_business_may_match: string[];
  missing_eligibility_info: string[];
  final_authority_disclaimer: string;
  match_disposition: "potential_match" | "gap_unknown" | "conflict";
  source?: ExternalClaim | null;
  claim_kind?: string;
  /** 0..1 — the source authority weight (e.g. .gov.in = 1.0). */
  authority_weight?: number;
}

/**
 * Sprint AI-16 — one row of a mixed answer.
 *
 * Mirrors the backend :class:`MixedSection.to_dict()` payload.
 * Each section renders as its own labelled card below the
 * DirectAnswer hero. ``source_kind`` drives the inline
 * "From external source" badge — the renderer never shows the
 * badge for ``"internal"``.
 */
export interface MixedSection {
  /** One of SECTION_KEYS — drives the renderer's section order. */
  key:
    | "general_explanation"
    | "business_interpretation"
    | "calculation"
    | "recommendation"
    | "schemes"
    | "uncertainty"
    | "next_action";
  title: string;
  body_lines: string[];
  source_kind: "internal" | "external" | "mixed";
  evidence_ids: string[];
  confidence: number;
}

/**
 * Sprint AI-16 — top-level wrapper the renderer mounts as the
 * consolidated body of a mixed answer.
 *
 * Mirrors the backend
 * :class:`MixedSectionsResult.to_dict()` payload. ``is_mixed``
 * is the renderer gate: when false, the renderer hides the
 * entire MixedSections block. ``rationale`` is a short
 * server-side explanation that the technical-provenance
 * disclosure surfaces verbatim.
 */
export interface MixedAnswer {
  sections: MixedSection[];
  is_mixed: boolean;
  rationale: string;
}

/**
 * Sprint AI-16 — one row of an external-source claim the
 * assistant surfaced. The renderer displays these inside the
 * existing technical-provenance panel.
 *
 * Mirrors the backend :class:`ClassifiedClaim.to_dict()`
 * payload plus the enclosing ``ExternalSource.to_dict()`` shape
 * for the ``source`` field. Loose shape — the backend may
 * evolve the payload and the renderer tolerates new fields.
 */
export interface ExternalClaim {
  id?: string;
  text?: string;
  kind?: string;
  confidence?: number;
  source?: Record<string, unknown> | null;
  // ClassifiedClaim + ExternalSource free-form fields.
  [key: string]: unknown;
}

/**
 * Sprint AI-16 — one row of the freshness-warning list. The
 * renderer surfaces the list as a single amber-bordered
 * inline notice ("This answer used N sources past their safe
 * window — re-verify before relying on them.").
 *
 * Mirrors an :class:`ExternalSource.to_dict()` payload whose
 * freshness bucket is AGING / STALE / UNKNOWN.
 */
export interface FreshnessWarning {
  id?: string;
  url?: string;
  title?: string;
  freshness?: "fresh" | "aging" | "stale" | "unknown";
  last_verified?: string;
  publisher?: string;
  [key: string]: unknown;
}

/**
 * Sprint AI-7 — one row the assistant surfaced as "missing".
 *
 * Wire shape mirrors the backend ``MissingDataObject``
 * dataclass — exactly the brief's contract:
 *
 *   {"field": str,
 *    "importance": "LOW" | "MEDIUM" | "HIGH",
 *    "reason": str,
 *    "affects": str[],
 *    "suggested_source": str}
 *
 * All fields except ``field`` + ``importance`` are optional
 * for backward compatibility with rows emitted by the LLM
 * reactive enrichment path (which omits ``affects``).
 */
export interface MissingDataObject {
  /** Snake_case identifier the renderer displays verbatim. */
  field: string;
  /** Tier that drives the chip colour + icon in the card. */
  importance: "LOW" | "MEDIUM" | "HIGH";
  /** One-line "why this matters" — the "Why it matters" sub-section aggregates these. */
  reason?: string;
  /** Analysis dimensions that depend on this field. */
  affects?: string[];
  /** Human-readable hint the card renders under "Source:". */
  suggested_source?: string;
}

/**
 * Sprint AI-8 — wire mirror of the backend's
 * ``LLMToolResult`` schema. One entry per whitelisted tool
 * the LLM requested in its 1st-turn payload. See the doc on
 * ``ChatMessage.llm_tool_results`` above for the full
 * narrative; this interface is the per-row shape.
 *
 * Field naming matches the backend wire exactly so the
 * provenance row can render the rejection reason
 * (``error``) verbatim for the LLM's 2nd turn.
 */
export interface LLMToolResult {
  /** The whitelisted tool name (e.g. ``"calculate_revenue_growth"``). */
  tool: string;
  /** Router verdict — drives the pill dot colour. */
  status: "ok" | "skipped" | "error";
  /** Stable evidence IDs the assistant cites. */
  evidence_ids: string[];
  /** Sanitised, server-stamped JSON payload (free-form; per-tool shape). */
  payload: Record<string, unknown>;
  /** Round-trip latency in milliseconds. */
  duration_ms: number;
  /** Rejection reason for status !== "ok". */
  error?: string | null;
}

/**
 * H7.8C — wire mirror of the backend's
 * ``ChatGenerationMeta`` schema. Three-state badge logic
 * (grounded-generative / open-generative / fallback) is
 * derived from this struct, never from text heuristics.
 */
export interface ChatGenerationMeta {
  provider: string;
  model: string;
  mode: "grounded" | "open";
  fallback_used: boolean;
  fallback_reason?:
    | "provider_unavailable"
    | "timeout"
    | "rate_limited"
    | "quota_exhausted"
    | "auth_failed"
    | "config_error"
    | "circuit_open"
    | "offline_snapshot"
    | "primary_provider_unavailable"
    | "provider_error"
    | "http_4xx"
    | "http_5xx"
    | "malformed_response"
    | "empty_response"
    | "schema_invalid"
    | "grounding_invalid"
    | "not_configured"
    | "open_mode_provider_failure"
    | null;
  generation_method: "generative" | "deterministic" | "offline_snapshot";
  schema_validated: boolean;
  grounding_validated: boolean;
  server_grounding_score: number;
  evidence_count: number;
  confidence: number | null;
  assumptions: string[];
  limitations: string[];
  evidence_references: string[];
  generated_at: string;
  prompt_truncated: boolean;
  provider_latency_ms: number | null;
  grounded_payload?: ChatGroundedResponse | null;
  business_evidence_validated?: boolean;
  context_manifest?: {
    business_context_used: string[];
    records_used: number;
    prompt_truncated: boolean;
  } | null;
  /**
   * Sprint AI-11 — Universal Business-Aware Assistant hardening.
   * Multi-label capability classification (general knowledge /
   * business fact / calculation / scenario / risk / etc.).
   * Frontend may surface a small icon row in the trust bar.
   */
  capability?: string[];
  /** Sprint AI-11 — whether the prompt requires the business
   *  profile (none / optional / required). */
  business_dependency?: "none" | "optional" | "required";
  /** Sprint AI-12 — Universal Reasoning Layer ToolPlan
   *  payload. May be null when the planner did not run. */
  tool_plan?: Record<string, unknown> | null;
  /** Sprint AI-12 — structured envelopes per executed tool. */
  structured_tool_envelopes?: Record<string, unknown>[];
  /** Sprint AI-12 — EvidenceRequirements the planner emitted. */
  evidence_requirements?: Record<string, unknown> | null;
  /** Sprint AI-12 — ContradictionReport the detector emitted. */
  contradiction_report?: Record<string, unknown> | null;
  /** Sprint AI-12 — AnswerQuality the validator emitted. */
  answer_quality?: Record<string, unknown> | null;
  /** Sprint AI-12 — the answer shell literal the composer
   *  chose (general_knowledge / business_analysis / etc.). */
  answer_mode?: string;
  /** Sprint AI-13 — per-tool execution trace records. */
  tool_execution_traces?: Record<string, unknown>[];
  /** Sprint AI-13 — one-line partial-failure sentence. */
  partial_failure_disclosure?: string | null;
  /** Sprint AI-13 — integer 0..40 confidence penalty. */
  confidence_penalty?: number;
  /** Sprint AI-14 — AnswerRequirements.to_dict() payload.
   *  16-field dataclass describing what the answer needs
   *  (16 needs_* flags + requested entities / metrics /
   *  time horizon / output format + rationale). Drives the
   *  hero-direct-answer + max-3-supports composer. */
  answer_requirements?: Record<string, unknown> | null;
  /** Sprint AI-14 — AnswerEvidenceGraph.to_dict() payload.
   *  Per-claim lineage (nodes / edges / claims / calculations
   *  / assumptions / external sources + unsupported / fabricated
   *  counters + contradiction severity). */
  evidence_graph?: Record<string, unknown> | null;
  /** Sprint AI-14 — wire list of CalculationNode.to_dict() dicts.
   *  Empty list when the dispatcher ran no calc-capable tool. */
  calculation_lineage?: Record<string, unknown>[];
  /** Sprint AI-14 — missing-data state dict with
   *  {known, derived, estimated, unknown} claim buckets. */
  missing_data_state?: Record<string, unknown> | null;
  /** Sprint AI-14 — count of ClaimNodes the engine flagged
   *  validation_status == "unsupported". Drives the
   *  "Unsupported claim" badge. */
  unsupported_claim_count?: number;
  /** Sprint AI-14 — count of ExternalSourceNode entries whose
   *  URL fails the URL guard. */
  fabricated_source_count?: number;
  /** Sprint AI-15 — server-owned VisualizationPlan list.
   *  Empty array when the planner emits no plans. */
  visualization_plans?: VisualizationPlan[];
  /** Sprint AI-15 — concise low-quality warning strip payload. */
  quality_warning?: {
    needs_warning?: boolean;
    warning_message?: string;
  } | null;
  /** Sprint AI-15 — "Why this answer?" disclosure payload. */
  trust_summary?: TrustSummary | null;
  /**
   * Sprint AI-16 — top-level mirror of
   * ``generation.scheme_card``. Same shape as the
   * ``ChatMessage`` top-level field.
   */
  scheme_card?: SchemeAnswerCard | null;
  /** Sprint AI-16 — top-level mirror of
   * ``generation.external_answer``. The concise external-only
   * reply envelope. Same shape as the ``ChatMessage``
   * top-level field. */
  external_answer?: ExternalClaim | null;
  /** Sprint AI-16 — top-level mirror of
   * ``generation.mixed_answer``. The 7-section decomposition
   * payload. Same shape as the ``ChatMessage`` top-level
   * field. */
  mixed_answer?: MixedAnswer | null;
  /** Sprint AI-16 — top-level mirror of
   * ``generation.external_claims``. Wire list of
   * ``ClassifiedClaim.to_dict()`` dicts. Empty when the turn
   * cited no external sources. */
  external_claims?: ExternalClaim[];
  /** Sprint AI-16 — top-level mirror of
   * ``generation.freshness_warnings``. Wire list of
   * ``ExternalSource.to_dict()`` dicts whose freshness bucket
   * is AGING / STALE / UNKNOWN. Empty when every source was
   * FRESH. */
  freshness_warnings?: FreshnessWarning[];
}

export interface ChatGroundedEvidenceReference {
  id: string;
  kind: string;
  label: string;
}

export interface ChatGroundedFinding {
  title: string;
  detail: string;
  evidence_refs: string[];
}

export interface ChatGroundedRecommendation {
  recommendation_id: string;
  title: string;
  rationale: string;
  evidence_refs: string[];
}

export interface ChatGroundedPlanItem {
  week: number;
  task: string;
  recommendation_ref: string | null;
  evidence_refs: string[];
}

export interface ChatGroundedSchemeMatch {
  scheme_ref: string;
  match_explanation: string;
  evidence_refs: string[];
}

export interface ChatGroundedResponse {
  executive_summary: string;
  key_findings: ChatGroundedFinding[];
  recommendations: ChatGroundedRecommendation[];
  thirty_day_plan: ChatGroundedPlanItem[];
  scheme_matches: ChatGroundedSchemeMatch[];
  assumptions: string[];
  limitations: string[];
  confidence: number;
  evidence_references: ChatGroundedEvidenceReference[];
  server_grounding_score: number;
  business_facts?: string[];
  situation_assessment?: string;
  reasoning?: string;
  root_causes?: string[];
  priority_matrix?: Array<{
    action: string;
    impact: string;
    effort: string;
    priority_category: string;
  }>;
  roi_estimate?: string;
  risks?: string[];
}

/**
 * SPRINT AI-10 — Explain My Answer. Per-recommendation
 * decision trace. Six sections (evidence, calculations,
 * decision_factors, assumptions, uncertainty, alternatives)
 * plus confidence + confidence_label.
 *
 * Every string in the trace comes from structured provenance
 * metadata — no LLM chain-of-thought is ever exposed. The
 * `ExplanationPanel` renders each section as a collapsible
 * block; the `confidence_label` is a literal ("High — supported
 * by current business evidence." etc.) the backend stamps.
 */
export interface TraceEvidenceItem {
  id: string;
  label: string;
  value: string;
}

export interface TraceCalculationItem {
  name: string;
  formula: string;
  inputs: Record<string, number | string>;
  result: string;
}

export interface TraceDecisionFactor {
  factor: string;
  source: string;
}

export interface TraceAssumption {
  text: string;
  source: string;
}

export interface TraceUncertainty {
  text: string;
  source: string;
}

export interface TraceAlternative {
  id: string;
  title: string;
  relation: "blocks" | "is_blocked_by" | "related_to";
}

export interface DecisionTrace {
  recommendation_id: string;
  evidence: TraceEvidenceItem[];
  calculations: TraceCalculationItem[];
  decision_factors: TraceDecisionFactor[];
  assumptions: TraceAssumption[];
  uncertainty: TraceUncertainty[];
  alternatives: TraceAlternative[];
  confidence: number;
  confidence_label: string;
}

export type ChatExplanation = Record<string, DecisionTrace>;

/**
 * H7.8C — provider status response from
 * ``GET /api/v1/chat/provider-status``. Used by
 * AssistantHeader to render the green/red dot indicator.
 */
export interface ChatProviderStatus {
  configured_provider: string;
  runtime_provider: string;
  model: string;
  available: boolean;
  schema_required: boolean;
  fallback_active: boolean;
  modes: Array<"grounded" | "open">;
  default_mode: "grounded" | "open";
}

export interface Conversation {
  /** Local id. */
  id: string;
  /** All messages in chronological order. */
  messages: ChatMessage[];
  /** ISO timestamp of the most recent message, or null when empty. */
  lastMessageAt: string | null;
}

// --------------------------------------------------------------------------- //
// Context panel — the data the side panel renders
// --------------------------------------------------------------------------- //

export interface AssistantContextScore {
  /** 0..100 composite from the Twin. */
  value: number;
  /** Human-readable band — "Foundation", "Developing", "Established", "Leading". */
  band: string;
}

export interface AssistantContextDna {
  /** Archetype label (e.g. "The Foundation Builder"). */
  archetype: string;
  /** 0..100 DNA match score. */
  match: number;
}

export interface AssistantContextRecommendations {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface AssistantContextRoadmap {
  totalItems: number;
  /** Average completion_percentage across all items, 0..100. */
  avgCompletion: number;
  /** Most-advanced phase actually populated (Immediate / Short-Term / Medium-Term / Long-Term). */
  currentPhase: string;
  /** Total estimated duration string from the roadmap summary. */
  totalDuration: string;
}

export interface AssistantContext {
  score: AssistantContextScore;
  dna: AssistantContextDna;
  recommendations: AssistantContextRecommendations;
  roadmap: AssistantContextRoadmap;
  /** True if at least one of the five upstream payloads is missing
   *  or empty. The view surfaces an "analysis incomplete" hint. */
  incomplete: boolean;
  /**
   * Sprint AI-6 — extended context fields for evidence
   * normalization. Each is optional; the TrustFirstResponse
   * shell falls back to a humanized label when missing.
   */
  /** Annual revenue in INR (rupees). */
  annualRevenueInr?: number | null;
  /** Employee count as a string. */
  employeeCount?: string | null;
  /** Primary supplier share (0-100). */
  primarySupplierShare?: number | null;
}

// --------------------------------------------------------------------------- //
// Consultant response (Sprint H4)                                            //
// --------------------------------------------------------------------------- //

/**
 * A structured "McKinsey-grade" consultant answer. Every reply
 * is rendered from this shape so the page can compose the 6
 * collapsible sections (Summary, Findings, Recommendations,
 * Impact, Action Plan, Next Questions) deterministically.
 */
export interface ConsultantSection {
  /** Section key. UI uses this to decide which card renders this block. */
  key:
    | "summary"
    | "findings"
    | "recommendations"
    | "impact"
    | "action_plan"
    | "next_questions"
    | "decision";
  /** Section heading shown to the user. */
  title: string;
  /** Short helper line under the heading. */
  caption?: string;
  /**
   * Short prose lines (will render as paragraphs). May be empty
   * when the section is purely a card (e.g. action_plan uses
   * `weeks` instead).
   */
  lines?: string[];
  /** Bullet list under this section. */
  bullets?: ConsultantBullet[];
  /** Free-form markdown-ish body (used by "summary"). */
  body?: string;
  /** Action plan weeks (only for key="action_plan"). */
  weeks?: ActionWeek[];
  /** Decision card payload (only for key="decision"). */
  decision?: DecisionCardPayload;
}

export interface ConsultantBullet {
  id?: string;
  title: string;
  subtitle?: string;
  /** Right-hand badge tone. */
  tone?: "primary" | "success" | "warn" | "danger" | "info" | "violet";
  /** Free-form metadata line. */
  meta?: string;
  /** Optional impact numbers (e.g. "+3 pts", "30% ROI"). */
  impact?: string;
  /** Optional difficulty label (e.g. "Easy", "Moderate"). */
  difficulty?: string;
  /** Optional time required (e.g. "2 weeks"). */
  time?: string;
  /** Optional confidence (0-100). */
  confidence?: number;
  /** Optional "risk if ignored" line. */
  riskIfIgnored?: string;
}

export interface ActionWeek {
  /** Display label, e.g. "Week 1". Legacy alias for `weekLabel`. */
  week: string;
  /** Bullet-list steps inside the week. Legacy alias for `actions`. */
  steps: string[];
  /** 1-based week index. New in H4.2-P1. */
  weekNumber: number;
  /** Heading shown above the steps, e.g. "Week 1 — Discover". */
  weekLabel: string;
  /** Single-line objective for the week, e.g. "Audit digital footprint". */
  objective: string;
  /** Same data as `steps` under a more explicit name. */
  actions: string[];
}

export interface DecisionCardPayload {
  question: string;
  verdict: "YES" | "WAIT" | "NO";
  verdictTone: "success" | "warn" | "danger";
  headline: string;
  why: string;
  risks: string[];
  roi: string;
  timeline: string;
  /** 0..100 deterministic confidence. */
  confidence: number;
}

export interface ConsultantResponse {
  /** Greeting / one-line opener reflecting the user's profile. */
  greeting: string;
  /** Inquiry topic, used by the follow-ups generator. */
  topic: string;
  /** All upstream payload topics the orchestrator drew on. */
  sources: ChatSource[];
  /** Six ordered sections that render the answer. */
  sections: ConsultantSection[];
  /** Plain-text fallback body for legacy callers / export. */
  body: string;
  /** Assistant intent for analytics. */
  kind: QueryKind;
}

// --------------------------------------------------------------------------- //
// Assistant response (the deterministic builder's return shape)
// --------------------------------------------------------------------------- //

export interface AssistantResponse {
  /** Plain-text body. Rendered as paragraphs on `\n\n`, as bullets on `\n- `. */
  body: string;
  /** Source list — shown under the body so the user can see where
   *  the answer came from. Always non-empty. */
  sources: ChatSource[];
  /** Intent that produced the answer. */
  kind: QueryKind;
  /** Optional structured consultant payload (Sprint H4). When the
   *  renderer sees this it prefers the card layout to the prose. */
  consultant?: ConsultantResponse;
}

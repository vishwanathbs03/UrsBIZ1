"use client";

/**
 * Frontend service for the Sprint 7 Part 3 conversation
 * persistence endpoints.
 *
 *   POST   /api/v1/chat                  createSession
 *   GET    /api/v1/chat                  listSessions
 *   GET    /api/v1/chat/{id}             getSession
 *   DELETE /api/v1/chat/{id}             deleteSession
 *   POST   /api/v1/chat/{id}/message     appendMessage
 *   GET    /api/v1/chat/provider-status  fetchProviderStatus  (H7.8C)
 *
 * Every call goes through the shared `apiClient` so the
 * cookie-based auth and JSON encoding stay in one place.
 */

import { apiClient, ApiError } from "./api-client";
import type { LLMToolResult, MissingDataObject } from "@/features/assistant/types";

export interface ChatSource {
  topic: string;
  detail: string;
}

export interface ChatGenerationMeta {
  provider: string;
  model: string;
  mode: "grounded" | "open";
  fallback_used: boolean;
  fallback_reason: string | null;
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
  grounded_payload?: Record<string, unknown> | null;
  /**
   * Sprint AI-11 — Universal Business-Aware Assistant hardening.
   * Multi-label classification of what capabilities the
   * prompt requires (general knowledge / business fact /
   * calculation / scenario / risk / etc.). Frontend may
   * surface this as an icon row in the trust badge.
   */
  capability?: string[];
  /**
   * Sprint AI-11 — whether the prompt requires the business
   * profile (none / optional / required). Frontend may use
   * this to switch the trust badge shape.
   */
  business_dependency?: "none" | "optional" | "required";
  /**
   * Sprint AI-12 — Universal Reasoning Layer. The AI-12
   * ToolPlan payload (required/optional/parallelizable/
   * sequential + rationale). Frontend may render this in a
   * collapsible "Reasoning plan" disclosure.
   */
  tool_plan?: Record<string, unknown> | null;
  /**
   * Sprint AI-12 — structured envelopes per executed tool.
   * Each entry is the JSON-serialised shape of
   * StructuredToolEnvelope (tool_name, metric, value, unit,
   * formula, input_evidence_ids, calculation_id, assumptions,
   * limitations, raw_payload).
   */
  structured_tool_envelopes?: Record<string, unknown>[];
  /**
   * Sprint AI-12 — EvidenceRequirements the planner emitted
   * (profile / analytics / kpi_history / etc.).
   */
  evidence_requirements?: Record<string, unknown> | null;
  /**
   * Sprint AI-12 — ContradictionReport the detector emitted
   * (severity + per-conflict records). null when no
   * contradiction was detected.
   */
  contradiction_report?: Record<string, unknown> | null;
  /**
   * Sprint AI-12 — AnswerQuality the validator emitted
   * (8-axis 0..10 score + needs_retry). null when the
   * validator did not run (deterministic-fallback path).
   */
  answer_quality?: Record<string, unknown> | null;
  /**
   * Sprint AI-12 — the answer shell literal the composer
   * chose (general_knowledge / business_analysis / calculation
   * / scenario / comparison / scheme / external / mixed).
   */
  answer_mode?: string;
  /**
   * Sprint AI-13 — per-tool execution trace records. Each
   * entry is the JSON-serialised shape of ToolExecutionTrace
   * (tool_name, selected, executed, success, latency_ms,
   * result_available, evidence_ids, failure_reason,
   * error_category). Empty array when no tools ran.
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
   * Sprint AI-14 — AnswerRequirements.to_dict() payload.
   * 16-field dataclass describing what the answer needs.
   */
  answer_requirements?: Record<string, unknown> | null;
  /**
   * Sprint AI-14 — AnswerEvidenceGraph.to_dict() payload.
   * Per-claim lineage (nodes / edges / claims / calculations
   * / assumptions / external sources + counters + severity).
   */
  evidence_graph?: Record<string, unknown> | null;
  /** Sprint AI-14 — CalculationNode.to_dict() list. */
  calculation_lineage?: Record<string, unknown>[];
  /** Sprint AI-14 — {known, derived, estimated, unknown} dict. */
  missing_data_state?: Record<string, unknown> | null;
  /** Sprint AI-14 — count of unsupported ClaimNodes. */
  unsupported_claim_count?: number;
  /** Sprint AI-14 — count of fabricated ExternalSourceNodes. */
  fabricated_source_count?: number;
}

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

export interface ChatMessageOut {
  id: number;
  role: "user" | "assistant";
  kind: string;
  content: string;
  sources: ChatSource[];
  created_at: string;
  /**
   * Per-message trust-label flag.
   *
   *  - `true`  → the assistant turn came from the deterministic
   *              fallback / placeholder provider. The UI MUST
   *              render "Calculated by UrsBiz rule engine".
   *  - `false` → the assistant turn came from a real
   *              OpenAI-compatible / Ollama response. The UI
   *              MAY render "Generated explanation".
   */
  fallback_used: boolean;
  /**
   * H7.8C — the full provenance envelope. Present for
   * every assistant turn (whether generative or fallback).
   * The MessageBubble uses this to render the three-state
   * trust badge (grounded / open / fallback) and the
   * TrustMeta disclosure panel.
   */
  generation?: ChatGenerationMeta | null;
  /**
   * Sprint AI-5 — Business Scenario Copilot envelope.
   * Present when the assistant turn answered a "what if"
   * prompt. The ScenarioAnalysisCard renders this as a
   * top-level card above the body.
   */
  scenario_analysis?: Record<string, unknown> | null;
  /**
   * Sprint AI-6 — Trust-first visual UI. Server-stamped
   * first 1-3 sentences from the assistant's full prose.
   * The TrustFirstResponse shell renders this as the
   * 10-second read at the top of every assistant message.
   */
  direct_answer?: string | null;
  /**
   * Sprint AI-7 — Missing-data intelligence. Structured list
   * of ``MissingDataObject`` rows the proactive detector +
   * reactive enrichment pass emitted. The ``MissingInfoCard``
   * reads this top-level field directly; absent / empty
   * triggers the AI-6 prose fallback path.
   */
  missing_data?: MissingDataObject[];
  /**
   * Sprint AI-8 — Controlled Business Tool Router. The
   * sanitised, server-stamped results of the 2-turn LLM tool
   * loop. One entry per whitelisted tool the LLM REQUESTED.
   * The technical-provenance disclosure inside
   * ``TrustFirstResponse`` renders a "Used tools" pill row
   * when this list is non-empty. Absent / empty list
   * (legacy rows + intents that did not trigger the tool
   * loop) renders nothing.
   */
  llm_tool_results?: LLMToolResult[];
  /**
   * Sprint AI-13 — top-level mirror of
   * ``generation.tool_execution_traces``. The MessageBubble
   * may render this as a "Tools consulted" disclosure row
   * without having to descend into the ``generation``
   * envelope. Empty array when no tools ran or the
   * kill-switch is off.
   */
  tool_execution_traces?: Record<string, unknown>[];
  /**
   * Sprint AI-13 — top-level mirror of
   * ``generation.partial_failure_disclosure``. The trust
   * badge uses this to surface a one-line "partial answer"
   * indicator when at least one tool failed. null when
   * every tool succeeded.
   */
  partial_failure_disclosure?: string | null;
  /**
   * Sprint AI-13 — top-level mirror of
   * ``generation.confidence_penalty``. The trust badge may
   * downgrade its label when this is > 0.
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
   * ``generation.visualization_plans``. Each entry carries
   * the server-owned chart kind + title + provenance.
   */
  visualization_plans?: Record<string, unknown>[];
  /**
   * Sprint AI-15 — top-level mirror of
   * ``generation.quality_warning``. Drives the low-quality
   * warning strip.
   */
  quality_warning?: {
    needs_warning?: boolean;
    warning_message?: string;
  } | null;
  /**
   * Sprint AI-15 — top-level mirror of
   * ``generation.trust_summary``. Powers the "Why this
   * answer?" disclosure panel.
   */
  trust_summary?: Record<string, unknown> | null;
}

export interface ChatSessionSummary {
  id: number;
  title: string;
  summary: string;
  message_count: number;
  last_model: string;
  fallback_used: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessageOut[];
}

export interface ChatMessageAppendResponse {
  user_message: ChatMessageOut;
  assistant_message: ChatMessageOut;
  session: ChatSessionDetail;
}

export const chatService = {
  async listSessions(): Promise<ChatSessionSummary[]> {
    const payload = await apiClient.get<{ sessions: ChatSessionSummary[]; count: number }>(
      "/api/v1/chat"
    );
    return payload.sessions;
  },

  async getSession(sessionId: number): Promise<ChatSessionDetail> {
    return apiClient.get<ChatSessionDetail>(`/api/v1/chat/${sessionId}`);
  },

  async createSession(title = ""): Promise<ChatSessionDetail> {
    return apiClient.post<ChatSessionDetail>("/api/v1/chat", { title });
  },

  async deleteSession(sessionId: number): Promise<{ deleted: boolean; id: number }> {
    return apiClient.delete<{ deleted: boolean; id: number }>(
      `/api/v1/chat/${sessionId}`
    );
  },

  /**
   * Append a user message to a chat session. Returns the
   * pair (user + assistant) plus the updated session.
   *
   * H7.8C — the ``mode`` flag selects grounded vs open
   * dispatch server-side. The default is ``"grounded"``
   * (the evidence-bounded path).
   */
  async appendMessage(
    sessionId: number,
    content: string,
    opts: { mode?: "grounded" | "open"; language?: "en" | "kn" } = {},
  ): Promise<ChatMessageAppendResponse> {
    return apiClient.post<ChatMessageAppendResponse>(
      `/api/v1/chat/${sessionId}/message`,
      {
        content,
        mode: opts.mode ?? "grounded",
        language: opts.language ?? "en",
      },
      { timeoutMs: 150000 },
    );
  },

  /**
   * H7.8C — provider status fetch. Returns the configured
   * provider, runtime provider, model, availability, and
   * the configured mode list. The endpoint is auth-gated
   * and never exposes secrets, full URLs, or API keys.
   */
  async fetchProviderStatus(): Promise<ChatProviderStatus> {
    return apiClient.get<ChatProviderStatus>("/api/v1/chat/provider-status");
  },
};

export { ApiError };

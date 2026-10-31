# UrsBiz AI Assistance Architecture — End-to-End Flow

**Generated:** 2026-08-13
**Scope:** AI-1 → AI-18 + H7.8C
**Companion source files:**
- `backend/app/services/chat/conversation_service.py`
- `backend/app/services/ai/providers/service.py` (`AssistantProviderService.generate()`)
- `backend/app/services/ai/reasoning/pipeline.py` (8-stage ReasoningPipeline)
- `backend/app/services/ai/reasoning/reasoning_engine.py` (`BusinessReasoningEngine`)
- `backend/app/services/ai/reasoning/tool_selector.py` (`ToolDispatcher`, `ToolSelector`)

---

## 1. Top-level call chain (one prompt, end to end)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js — features/assistant/)                              │
│  AssistantView  ──HTTP POST──▶  /api/v1/chat/sessions/{id}/messages    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  API LAYER  (FastAPI — api/v1/endpoints/chat.py)                        │
│  ChatMessagesAPI.append_message()                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONVERSATION SERVICE  (chat/conversation_service.py)       [SPRINT H7] │
│  · rolling-history context window (last 8 turns)                        │
│  · session summary regeneration (≤500 chars)                            │
│  · auto-title from first 80 chars                                      │
│  · persists assistant message verbatim                                  │
│  · wires AI-7 missing-data detector / enricher (steps 3.7 / 5.8)       │
│  · AI-12 3 gates (steps 3.9 / 4.5 / 5.5b)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ASSISTANT PROVIDER SERVICE  (ai/providers/service.py)       [SPRINT    │
│  AssistantProviderService.generate()                              H7.8C] │
│  the single thin façade — owns no business logic                        │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
   ┌──────────────────────────────┴──────────────────────────────┐
   ▼                                                              ▼
┌──────────────────────────┐                       ┌──────────────────────────┐
│  CONTEXT BUILDER         │                       │  PROVIDER FACTORY        │
│  AssistantContextBuilder │                       │  ProviderFactory.build() │
│  [SPRINT H7]             │                       │  Ollama / OpenAI-comp /  │
│                          │                       │  DeterministicFallback   │
│  reads 5 upstream         │                      │  [H7.9R+ circuit breaker│
│  payloads:                │                      │   with multi-tier fail]  │
│   · Business Twin         │                      └────────────┬─────────────┘
│   · Recommendations       │                                   │
│   · Insights / Risks      │                                   ▼
│   · Forecasts / Schemes   │                       ┌──────────────────────────┐
│                          │                       │  PROVIDER                │
│  produces:                │                       │  Provider.complete(req)   │
│   AssistantContext        │                       │  · 15s HARD CALL TIMEOUT │
│   (canonical shape)       │                       │  · retry-with-backoff    │
│   + context_manifest      │                       │  · returns AssistantResp. │
└──────────────┬─────────────┘                       └────────────┬─────────────┘
               │                                                │
               ▼                                                │
┌─────────────────────────────────────────────────────────────────┐
│  PRE-LLM REASONING LAYER  (ai/reasoning/*)         [SPRINT AI-1]│
│  Runs inside a try/except — failures fall back to pre-AI-1      │
│  prompt surface, never break the chat request.                  │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │ Stage 1 — QUESTION UNDERSTANDING         │  [AI-1]           │
│  │ question_understanding.py                │                   │
│  │   · capability (multi-label tuple)        │                  │
│  │   · business_dependency (none/optional/   │                  │
│  │     required)                             │                  │
│  │   · answer_mode (16-category enum)        │                  │
│  │   · required_tools / required_evidence    │                  │
│  │   · is_business_specific (auto-flip flag) │                  │
│  │   · unknowns / calculations_required      │                  │
│  └──────────────┬────────────────────────────┘                  │
│                 │                                                │
│                 ▼                                                │
│  ┌─────────────────────────────────────────┐                    │
│  │ Stage 4 — REASONING ENGINE PLAN          │  [AI-1 / H8.11]  │
│  │ reasoning_engine.py → pipeline.py        │                   │
│  │ 8-stage internal pipeline:               │                   │
│  │   1. Understand Intent                   │                   │
│  │   2. Select Evidence                     │                   │
│  │   3. Analyze Context                     │                   │
│  │   4. Generate Hypothesis                 │                   │
│  │   5. Validate Hypothesis                 │                   │
│  │   6. Produce Recommendation              │                   │
│  │   7. Estimate Confidence                 │                   │
│  │   8. Return Sanitised Conclusions        │                   │
│  │                                          │                   │
│  │ Emits ReasoningPlan:                     │                   │
│  │   · intent / subgraph_node_ids           │                   │
│  │   · hypotheses / evidence_priorities     │                   │
│  │   · confidence / trace                   │                   │
│  │   · applicable_deterministic_services    │                   │
│  │   · calculations_required                │                   │
│  │   · tool_plan + evidence_requirements    │  [AI-12]         │
│  └──────────────┬────────────────────────────┘                  │
│                 │                                                │
│                 ▼                                                │
│  ┌─────────────────────────────────────────┐                    │
│  │ Evidence Retriever                       │  [H8.11]         │
│  │ evidence_retriever.py                    │                   │
│  │   · EvidenceRegistry(context)             │                  │
│  │   · ranks entries by intent + plan        │                  │
│  │   · returns ranked_evidence               │                  │
│  └──────────────┬────────────────────────────┘                  │
│                 │                                                │
│                 ▼                                                │
│  ┌─────────────────────────────────────────┐                    │
│  │ Stage 5 — TOOL DISPATCH                  │  [AI-2 / AI-12]  │
│  │ tool_selector.py                          │                   │
│  │   ToolDispatcher.dispatch_with_plan()     │                  │
│  │                                          │                   │
│  │ 16 real deterministic engine wrappers:   │                   │
│  │   health_score, score, recommendation,   │                   │
│  │   schemes_sprint16, finance, forecast,   │                   │
│  │   insight, rule, risk, dna, action,      │                   │
│  │   export, knowledge_retrieval, …         │                   │
│  │                                          │                   │
│  │ Returns DispatchOutcome:                  │                  │
│  │   · plan (ToolPlan)                       │                  │
│  │   · results (tool_results tuple)          │                  │
│  │   · envelopes (StructuredToolEnvelope[])  │                  │
│  │   · traces (ToolExecutionTrace[])         │                  │
│  │   · contradiction_report / evidence_req.  │                  │
│  └──────────────┬────────────────────────────┘                  │
│                 │                                                │
└─────────────────┼────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  PROMPT BUILDER  (ai/providers/prompt_builder.py)                │
│  Renders the structured prompt:                                  │
│   · system preamble       (with mode: grounded/open)              │
│   · === BUSINESS CONTEXT ===  (manifest + ranked_evidence)         │
│   · === REASONING TRACE ===  (from BusinessReasoningEngine)       │
│   · === HISTORY ===                                                 │
│   · === USER MESSAGE ===                                             │
│  mode flips to "open" automatically when prompt is purely          │
│  educational AND not business-specific (Stage 1 auto-flip).        │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
              (request → Provider.complete → AssistantResponse.body)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  GROUNDED-MODE FINALISER  (service._generate_grounded)  [H7.8C]  │
│  Runs only when the provider returned successfully.               │
│                                                                   │
│  ① Schema parse (parse_model_output)               [H7.3]         │
│      failure → fallback(reason="schema_invalid")                  │
│  ② Grounding validator (GroundingValidator)        [H7.8C]       │
│      score < threshold → fallback(reason="grounding_invalid")     │
│  ③ AI-3 claim-aware pipeline:                     [AI-3]          │
│      · ClaimValidator       (9-axis claim audit)                   │
│      · NumericConsistencyChecker                                       │
│      · ConfidenceCalculator (server-owned confidence)              │
│  ④ AI-4 ClaimAuditor                             [AI-4]          │
│      · 9 attribute axes · hard/soft rejection                              │
│      · rejection → answer withheld, UI shows reason                 │
│  ⑤ AI-12 tool-plan + envelopes + traces + contradiction_report     │
│  ⑥ AI-13 partial-failure stamp + confidence_penalty               │
│  ⑦ AI-14 answer requirements + evidence graph                      │
│      · calculation_lineage · unsupported_claim_count              │
│      · fabricated_source_count                                     │
│  ⑧ AI-15 visualization plans + chart payloads + trust summary    │
│  ⑨ AI-5 10-field structured envelope (executive_summary,          │
│     key_findings, recommendations, thirty_day_plan, …)             │
│                                                                   │
│  GenerationMeta carries every AI-N stamp + every audit row.        │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  CIRCUIT BREAKER + HARD TIMEOUT  (providers/circuit_breaker.py)  │
│  [SPRINT H7.9R]                                                    │
│  All exceptions above funnel through this wrapper:                  │
│   · ProviderQuotaError / RateLimit / Auth → fallback_chain         │
│   · Hard timeout (15s wall-clock) → fallback_chain(reason=timeout) │
│   · 5xx / 4xx / unavailable / schema_invalid → fallback_chain       │
│                                                                   │
│  Fallback chain:                                                  │
│   Tier 1 — Primary provider (Gemini / OpenAI-compat / Ollama)      │
│   Tier 2 — Secondary provider (if configured)                      │
│   Tier 3 — Deterministic Rule Engine                                │
│   Tier 4 — Offline Demo Snapshot (Acme flagship only)               │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  WIRE PAYLOAD  (GenerationMeta → ChatMessageAppend)               │
│  Carries to the frontend:                                          │
│   · body (Markdown rendered chat body)                              │
│   · answer_mode / capability / business_dependency                   │
│   · deterministic_services_used / calculations_used                 │
│   · tool_execution_traces / partial_failure_disclosure              │
│   · confidence_penalty / server_confidence / rationale               │
│   · structured_tool_envelopes / tool_plan                            │
│   · claim_audit / claim_audit_rejected / soft_corrections             │
│   · claim_aware_validated / claim_aware (raw LLM payload)             │
│   · numeric_conflicts_count / unsupported_claim_count                │
│   · fabricated_source_count / calculation_lineage                    │
│   · evidence_graph / missing_data_state / answer_requirements        │
│   · visualization_plans / quality_warning / trust_summary            │
│   · evidence_references / assumptions / limitations                   │
│   · context_manifest / context_manifest records_used                  │
│   · mode (grounded|open) / fallback_used / fallback_reason            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. The 8-stage internal pipeline (`ReasoningPipeline.pre_llm_plan`)

```
                  USER PROMPT
                      │
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 1  Understand Intent              │  ReasoningStageResult
   │  (keyword scan: "grow" → growth)          │
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 2  Select Evidence                │  ReasoningStageResult
   │  (count recommendations + rules)          │
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 3  Analyze Context                │  ReasoningStageResult
   │  (baseline business score)                │
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 4  Generate Hypothesis            │  Hypothesis
   │  ("Supply chain concentration limits      │
   │   margin expansion.")                     │
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 5  Validate Hypothesis            │  ReasoningStageResult
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 6  Produce Recommendation         │  ReasoningStageResult
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 7  Estimate Confidence            │  → 0..100 float
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │  Stage 8  Return Sanitised Conclusions    │  ConclusionSanitizer
   │  (never expose internal trace)             │
   └──────────────────────────────────────────┘
```

The trace bundles the stages into a `ReasoningTrace` that the prompt
builder surfaces as a `=== REASONING TRACE ===` block before the
LLM call. The trace never leaks into the user-visible body.

---

## 3. Cross-cutting concerns (every request)

```
┌─────────────────────────────────────────────────────────────────┐
│  CROSS-CUTTING LAYERS                                            │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  ClaimAuditor  [AI-4]                    │                   │
│  │  · 9 attribute axes                       │                  │
│  │  · hard reject / soft correct             │                  │
│  │  · runs AFTER numeric_checker              │                  │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  GroundingValidator  [H7.8C]              │                   │
│  │  · every evidence_ref must exist in       │                  │
│  │    EvidenceRegistry built from context    │                  │
│  │  · threshold configurable via Settings    │                  │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  EvidenceGraph  [AI-14]                   │                   │
│  │  · per-claim lineage                       │                  │
│  │  · unsupported_claim_count                 │                  │
│  │  · fabricated_source_count                 │                  │
│  │  · contradiction_report                    │                  │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  TrustSummary  [AI-15]                    │                   │
│  │  · 3-state trust badge                    │                   │
│  │    (verified / partial / low)              │                  │
│  │  · quality_warning flag                   │                  │
│  │  · visualization_plans (charts)           │                  │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  AI-7 Missing Data Detector  [AI-7]       │                   │
│  │  · runs BEFORE provider (step 3.7)        │                  │
│  │  · enrichment pass AFTER (step 5.8)       │                  │
│  │  · drives MissingInfoCard in UI            │                  │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │  AI-18 Evaluation Harness  [AI-18]        │                   │
│  │  · 108 prompts × 17 categories             │                  │
│  │  · 14 measured metrics                     │                  │
│  │  · golden set + adversarial + followup     │                  │
│  │  · 8 data-quality profiles                  │                  │
│  │  · 9 failure scenarios                     │                  │
│  │  · production_path_fraction = 1.000        │                  │
│  └─────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Sprint-by-sprint capability ladder

```
AI-1   Universal business AI assistant
       └─ capability + business_dependency + tool dispatcher
AI-3   Claim-aware response contract
       └─ ClaimValidator + NumericConsistencyChecker + ConfidenceCalculator
AI-4   ClaimAuditor (9 attribute axes)
       └─ hard reject / soft correct
AI-5   Business Scenario Copilot
       └─ 10-field structured envelope (executive_summary, …)
H7.8C  Hybrid grounded/open AI assistant
       └─ EvidenceRegistry + GroundingValidator + 3-state trust badge
H7.9R  Multi-tier failover + circuit breaker
       └─ 15s hard call timeout, retry-with-backoff
AI-7   Missing data intelligence
       └─ MissingDataDetector + MissingInfoCard
AI-8   LLM tool-loop (bounded at 2 turns)
       └─ router.route_all() → 2nd-turn explanation
AI-11  Multi-label capability tuple
       └─ universal question classification
AI-12  Universal Reasoning Layer
       └─ ToolPlan + StructuredToolEnvelope + ToolExecutionTrace
AI-13  Per-tool observability + partial-failure disclosure
       └─ confidence_penalty + tool_execution_traces
AI-14  Universal Answer Intelligence + Evidence Graph
       └─ answer_requirements + evidence_graph + calculation_lineage
AI-15  Visualization + trust envelope
       └─ visualization_plans + chart_data + trust_summary
AI-16  Mixed question separator + scheme answer card
       └─ (frontend wire components)
AI-17  Bounded retry gate + claim lifecycle
       └─ quality_failure_classifier + numeric_correction_auditor
AI-18  Universal AI Evaluation Harness
       └─ 108 prompts × 14 metrics, production_path_fraction = 1.000
```

---

## 5. Key invariants the architecture enforces

1. **Server-owned.** `server_confidence`, `claim_audit_rejected`,
   `unsupported_claim_count`, `fabricated_source_count` are derived
   server-side. The LLM's own self-reported confidence is never
   trusted.
2. **Server-authority on adversarial.** Prompt-injection, fake
   evidence IDs, false facts, conflicting numbers, evidence-override
   are all refused (`contradiction_handling = 1.000` measured).
3. **No silent truncation.** Hard caps in `_MAX_LIST_LEN` (16) and
   `_MAX_TEXT_LEN` (2000) protect the API from runaway outputs.
4. **Graceful degradation.** Every stage is wrapped in try/except;
   a Stage 1-8 failure falls back to the pre-AI-1 prompt surface,
   never breaks the chat request.
5. **No "100% accuracy" claims.** AI-18 reports measured values
   only — `unnecessary_tool_execution = 0.538` is honestly reported
   even though it's a less flattering number.
6. **Deterministic fallback always produces a body.** Every
   failure scenario in the harness produces a non-empty
   `body` via the deterministic path (`fallback_correctness = 1.000`).
7. **Multi-tier failover.** Primary → Secondary → Deterministic
   Rule Engine → Offline Demo Snapshot. The user always sees a
   reply.

---

## 6. Reproducing the flow

```bash
# Inspect the canonical pipeline
cat backend/app/services/ai/providers/service.py | grep -n "def generate\|def _generate_"
cat backend/app/services/ai/reasoning/pipeline.py | grep -n "def _stage_\|def pre_llm_plan"

# Drive the full harness end-to-end
python scripts/debug/run_ai18_harness.py

# Run the regression suite
cd backend && python -m pytest tests/
```

---

## 7. Sprint manifest

| Sprint | Module(s) added                                                                                   | Capability unlocked                              |
| ------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| H7     | `chat/conversation_service.py` · `providers/context_builder.py` · `providers/factory.py`           | Session-aware chat + provider factory            |
| H7.3   | `providers/response_schema.py` · `parse_model_output`                                              | JSON contract + parse-fail fallback              |
| H7.8C  | `providers/evidence_registry.py` · `providers/grounding_validator.py`                             | Evidence-bound audit + 3-state trust badge       |
| H7.9R  | `providers/circuit_breaker.py` · `_call_with_hard_timeout`                                         | Multi-tier failover + 15s hard call timeout      |
| AI-1   | `reasoning/question_understanding.py` · `reasoning/pipeline.py` · `reasoning/tool_selector.py`     | Universal capability + 8-stage pipeline + tools  |
| AI-2   | `reasoning/tool_selector.py` (16 real engine wrappers)                                            | Real deterministic engines, no more stubs        |
| AI-3   | `providers/claim_parser.py` · `providers/claim_validator.py` · `providers/numeric_checker.py` · `providers/confidence_calculator.py` | Claim-aware response contract + server confidence |
| AI-4   | `providers/claim_auditor.py`                                                                       | 9-attribute-axis audit + hard/soft rejection     |
| AI-5   | `reasoning/answer_composer.py`                                                                     | 10-field structured envelope                     |
| AI-7   | `missing_data/detector.py` · `enrich_missing_data_from_prose.py`                                  | MissingDataCard on the wire                      |
| AI-8   | `tool_router/router.py` · `_maybe_run_tool_loop`                                                   | Bounded 2-turn LLM tool-loop                     |
| AI-11  | `reasoning/question_understanding.py` (multi-label)                                                | Capability tuple on the wire                     |
| AI-12  | `reasoning/tool_plan.py` · `reasoning/structured_envelope.py` · `reasoning/tool_execution_trace.py` | ToolPlan + StructuredToolEnvelope + Trace        |
| AI-13  | `reasoning/ai13_dispatch_adapter.py`                                                               | partial_failure_disclosure + confidence_penalty  |
| AI-14  | `reasoning/answer_requirements.py` · `reasoning/evidence_graph.py` · `reasoning/calculation_lineage.py` | Answer Intelligence + Evidence Graph             |
| AI-15  | `reasoning/visualization_planner.py` · `reasoning/chart_data_builder.py` · `reasoning/trust_summary.py` | Chart payloads + 3-state trust envelope          |
| AI-17  | `reasoning/bounded_retry_gate.py` · `reasoning/claim_lifecycle.py` · `reasoning/confidence_penalty_calculator.py` · `reasoning/quality_failure_classifier.py` · `reasoning/deterministic_answer_repairer.py` · `reasoning/numeric_correction_auditor.py` | Quality classifier + repairer + numeric correction |
| AI-18  | `evaluation/*` (8 modules) · `tests/test_ai18_evaluation_harness.py`                              | 14 measured metrics + production-path coverage   |
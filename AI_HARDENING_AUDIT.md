# AI Architecture Hardening — Audit Report

> **Date:** 2026-08-11
> **Scope:** Audit of the existing AI-1 → AI-10 implementation
> at `D:\MSME\UrsAi\backend` against the 22-section
> "AI Architecture Hardening — Universal Business-Aware Assistant"
> brief.
>
> **Verdict:** The architecture is **already universal** in the
> key acceptance-criterion sense (no code path rejects a valid
> question because it isn't one of the six legacy intents). The
> remaining work is small, additive, and risk-bounded.

---

## 1. Request-flow trace

`POST /api/v1/chat/{session_id}/message`
→ `app/api/v1/endpoints/chat.py:458 append_message`
→ `ConversationService.append_message(...)`
→ `AssistantProviderService.generate(...)`
→ `_generate_grounded(...)` or `_generate_open(...)`
→ `DeterministicFallbackProvider.complete(...)` (failure path)
→ `AssistantResponse` → wire projection
→ `ChatMessageAppendResponse.model_validate(...)`

### 1.1 `ConversationService.append_message` step map
(`backend/app/services/chat/conversation_service.py:179`)

| Step | Lines | What it does | Sprint |
|---|---|---|---|
| 1 | 212 | Insert user message row | legacy |
| 2 | 220 | Compose rolling history | legacy |
| 3 | 224 | `self._assistant.build_context(...)` | AI-1 |
| 3.5 | 235 | `_maybe_build_scenario_analysis(context, prompt)` — ScenarioDetector + ScenarioAnalyzer | AI-5 |
| 3.7 | 248 | `classify_intent(content)` → `detect_missing_data(context, intent)` (proactive) | AI-7 |
| 4 | 257 | Knowledge-retrieval call when wired | legacy |
| 5 | 274 | `self._assistant.generate(...)` (the orchestrator) | AI-1 / AI-2 |
| 5.5 | 289 | `_stamp_scenario_analysis(...)` | AI-5 |
| 5.7 | 303 | `_extract_direct_answer(...)` + `_stamp_direct_answer(...)` | AI-6 |
| 5.8 | 319 | `enrich_missing_data_from_prose(...)` + `_stamp_missing_data(...)` | AI-7 |
| 5.10 | 340 | `_stamp_llm_tool_results(...)` | AI-8 |
| 5.11 | 366 | `_stamp_explanation(...)` — `build_trace(...)` per rec | AI-10 |
| 6 | 387 | Persist assistant message | legacy |
| 7 | (later) | Refresh session title / last_model | legacy |

### 1.2 `AssistantProviderService.generate` stage map
(`backend/app/services/ai/providers/service.py:296`)

| Stage | Lines | What it does | Sprint |
|---|---|---|---|
| 1 | 342 | `understand_question(prompt, context)` → `QuestionUnderstanding` | AI-1 |
| 4 | 354 | `self._reasoning_engine.plan(...)` → `ReasoningPlan` | H8.11 / AI-1 |
| registry | 364 | `EvidenceRegistry(context)` | H7.8C / AI-1 |
| 7 | 365 | `self._evidence_retriever.rank(...)` | H8.11 / AI-1 |
| 5 | 376 | `self._tool_dispatcher.dispatch(...)` | AI-1 / AI-2 |
| mode-flip | 402 | internal `_effective_mode` flips to "open" for purely-educational prompts | AI-1 |
| 8 | 412 | `self._prompt_builder.build(...)` | H7.8C / AI-1 |
| LLM | (later) | `_call_with_hard_timeout` + circuit breaker | H8.10 |
| tool loop | 596 | `_maybe_run_tool_loop(...)` (2nd turn) | AI-8 |
| parse | (later) | `parse_model_output(...)` | H7.8C |
| validators | (later) | `GroundingValidator` (grounded) or `OpenResponseValidator` (open) | H7.8C |
| AI-3 chain | (later) | `parse_claim_aware_payload` → `ClaimValidator` → `NumericConsistencyChecker` → `ConfidenceCalculator` | AI-3 |
| AI-4 audit | (later) | `ClaimAuditor.audit(...)` (9 axes, hard-rejection, soft-correct) | AI-4 |
| fallback | 1561 | `DeterministicFallbackProvider.complete(...)` | H7.8C / AI-3 |

### 1.3 Where the deterministic fallback runs
(`backend/app/services/ai/providers/base.py:942`)

`DeterministicFallbackProvider.complete` builds a complete
`AssistantResponse` directly from `AssistantContext` (no LLM).
It calls `claim_fallback.build_fallback_claim_aware(request)` to
populate `claim_aware` with `server_confidence=100`,
`numeric_match=True`, `validated=True`. The fallback NEVER
inspects `QuestionIntent` to decide what to render — it inspects
`AssistantContext.recommendations`, `.scores`, `.schemes`, etc.,
which exist regardless of how the prompt was classified.

---

## 2. Hardened-question audit — does any path reject?

Searched for any rejection logic tied to `QuestionIntent` /
"one of six" / "unsupported question" / "I don't recognize".

| File | Line | Snippet | Verdict |
|---|---|---|---|
| `app/services/ai/providers/intent_router.py` | 58 | `QuestionIntent` enum | Routing hint, never a reject key |
| `app/services/chat/conversation_service.py` | 248 | `classify_intent(content)` → `QuestionIntent.GENERAL` (default fallback) | Always falls back to GENERAL; never raises |
| `app/services/ai/reasoning/question_understanding.py` | 657 | `topic=topic` (default "general") | No reject path |
| `app/services/ai/providers/service.py` | 402-410 | Auto-flip `_effective_mode` to "open" for educational prompts | Permissive, not restrictive |

**Result:** No code path rejects a question because it's not one of
the six flagship intents. AI-1 already turned `QuestionIntent`
into an optimization hint. AI-7 added a fallback (`QuestionIntent.GENERAL`)
so unknown prompts still reach the orchestrator.

**Acceptance criterion §19 — already satisfied.**

---

## 3. `QuestionUnderstanding` shape audit

(`backend/app/services/ai/reasoning/question_understanding.py:166`)

| Field | Type | Status |
|---|---|---|
| `literal_question` | `str` | ✅ |
| `user_intent` | `str` | ✅ |
| `topic` | `Literal[finance, marketing, operations, hiring, export, strategy, education, risk, scenario, general]` | ✅ — coarse topic |
| `is_business_specific` | `bool` | ✅ |
| `is_purely_educational` | `bool` | ✅ — drives `effective_mode` flip |
| `needs_calculations` | `tuple[str, ...]` | ✅ |
| `needs_deterministic_services` | `tuple[str, ...]` | ✅ |
| `unknowns` | `tuple[str, ...]` | ✅ |
| `relevant_existing_intents` | `tuple[QuestionIntent, ...]` | ✅ — preserves six legacy values |
| `sentiment` | `str` | ✅ |
| `complexity` | `Literal[simple, moderate, strategic, scenario]` | ✅ |
| `parsed_at` | `str` | ✅ |

### Gap vs brief §4 / §5

| Brief asks | Current state | Action |
|---|---|---|
| "GENERAL_KNOWLEDGE / BUSINESS_FACT / BUSINESS_ANALYSIS / CALCULATION / RECOMMENDATION / SCENARIO / FORECAST / COMPARISON / FINANCIAL / OPERATIONAL / RISK / GOVERNMENT_SCHEME / EXPORT / ROADMAP / EXTERNAL_INFORMATION / MIXED / UNKNOWN" capability set | None. Has only coarse `topic` (10 literals) + `complexity` (4). | **Add `capability: tuple[Capability, ...]`** (multi-label) — capability names mirror brief §4. |
| `business_dependency: NONE \| OPTIONAL \| REQUIRED` | Partial. `is_business_specific` is binary, not three-valued. | **Add `business_dependency: BusinessDependency` literal** derived from `is_business_specific` + `is_purely_educational` + keyword cues. |

### What's already covered
The orchestrator (assistant.service.generate) and the prompt builder
already use `is_purely_educational` and `is_business_specific` to:
- flip `_effective_mode` (line 402-410)
- decide evidence lookup (line 412 prompt builder)
- select tools (tool_selector)

So the *behavior* is universal; only the **wire projection** is
missing the new fields. Adding them is additive (default empty
tuple / "NONE") — no legacy breakage.

---

## 4. Orchestrator audit — is there a single orchestrator?

**Yes.** `AssistantProviderService.generate(...)` is the single
orchestrator. It runs Stages 1, 4, 5, 7, 8 (QuestionUnderstanding
→ ReasoningEngine → EvidenceRegistry → EvidenceRetriever →
ToolDispatcher → PromptBuilder) before the LLM call. Every stage
is wrapped in try/except so a failure degrades to the pre-AI-1
prompt surface — never a rejection.

The brief's suggested class names
(`understand_question / reasoning_engine / evidence_retriever / tool_selector / tool_dispatcher / answer_generator / claim_auditor / confidence_calculator / decision_trace_builder`)
**already exist** under different module paths:

| Brief | Existing equivalent |
|---|---|
| `understand_question` | `app.services.ai.reasoning.question_understanding.understand_question` |
| `reasoning_engine.plan` | `app.services.ai.reasoning.pipeline.BusinessReasoningEngine.plan` |
| `evidence_retriever.retrieve` | `app.services.ai.reasoning.evidence_retriever.rank` (renamed slightly) |
| `tool_selector.select` | `app.services.ai.reasoning.tool_selector.ToolSelector.select` |
| `tool_dispatcher.dispatch` | `app.services.ai.reasoning.tool_selector.ToolDispatcher.dispatch` |
| `answer_generator.generate` | `app.services.ai.providers.service._generate_grounded / _generate_open` |
| `claim_auditor.audit` | `app.services.ai.providers.claim_auditor.ClaimAuditor.audit` |
| `confidence_calculator.calculate` | `app.services.ai.providers.confidence_calculator.ConfidenceCalculator.compute` |
| `decision_trace_builder.build` | `app.services.ai.trace.builder.build_trace(...)` |

**Verdict:** No duplicate orchestrator is needed. The brief's
section 6 is satisfied by the existing pipeline.

---

## 5. Test-matrix gap analysis (brief §21)

Existing coverage (sprint-specific):

| Existing test file | Coverage |
|---|---|
| `test_ai1_30_question_sweep.py` | 30+ prompts across flagship, non-flagship, scenario, education, out-of-scope, open-mode — asserts no "I don't recognize this intent" |
| `test_ai1_question_understanding.py` | Topic / complexity / needs_calculations / is_business_specific |
| `test_ai5_scenario_copilot.py` | Scenario 10-field envelope |
| `test_ai6_direct_answer.py` | Extraction (first-3-sentences, etc.) |
| `test_ai7_missing_data.py` | Missing data detection + reactive enrichment |
| `test_ai8_tool_router.py` | Tool router validation, sanitisation, evidence IDs |
| `test_ai9_adversarial_suite.py` | 10 categories (A–J), 61 tests |
| `test_ai10_explain_my_answer.py` | 14 trace invariants |

### Gaps vs brief §21

| Brief asks | Current | Gap |
|---|---|---|
| GENERAL_KNOWLEDGE | "What is working capital?" covered (test_ai1_30_question_sweep.py:165) | partial — needs explicit capability assertion |
| BUSINESS_FACT | partial — flagship variants only | need explicit "How many employees do I have?" |
| BUSINESS_ANALYSIS | partial | need explicit "Why is my health score only 68?" |
| CALCULATION | partial | need explicit "What is my revenue growth percentage?" |
| RECOMMENDATION | partial | need explicit "How can I reduce my biggest business risk?" |
| SCENARIO | covered | ✅ |
| FORECAST | partial | need explicit forecast test |
| COMPARISON | not covered | **gap** |
| FINANCIAL | partial | need explicit financial question |
| GOVERNMENT_SCHEME | partial | need explicit "Are there schemes that can help me buy machinery?" |
| RISK | partial | need explicit risk question |
| MIXED | partial ("Explain my health score" + "What is working capital?") | need explicit "Explain working capital and tell me whether it is a problem for my business" |
| MISSING_DATA | covered | ✅ |
| UNKNOWN | partial | need explicit unknown question |
| EXTERNAL_INFORMATION | partial | need explicit external question |
| Legacy flagship intent | covered (5 in sweep) | ✅ |
| Non-flagship question | covered | ✅ |
| Malformed user input | partial | need explicit malformed prompt test |
| Prompt injection | covered (AI-9 category H) | ✅ |
| Unsupported numeric claim | covered (AI-4 hard-rejection) | ✅ |
| Contradictory business data | partial | need explicit test |
| Missing tool | partial | need explicit test |
| Tool failure | partial | need explicit test |
| LLM failure | partial | need explicit test |
| Schema failure | partial | need explicit test |
| Grounding failure | covered (AI-3 / AI-4) | ✅ |
| Scenario with missing data | partial | need explicit test |
| Open mode | covered | ✅ |
| Grounded mode | covered | ✅ |

---

## 6. Brief criterion → implementation status

| § | Requirement | Status | Action |
|---|---|---|---|
| 1 | Audit before modifying | ✅ this document | — |
| 2 | Universal orchestration graph | ✅ already present | none |
| 3 | Preserve legacy `QuestionIntent` as optimization hint | ✅ since AI-1 | none |
| 4 | `QuestionUnderstanding` capability classification | ⚠ partial (10 topics, no capability tuple) | **add `capability` field** |
| 5 | `business_dependency: NONE/OPTIONAL/REQUIRED` | ⚠ partial (only `is_business_specific` binary) | **add `business_dependency` field** |
| 6 | Single orchestrator | ✅ `AssistantProviderService.generate` | none |
| 7 | Universal question tests | ⚠ partial — flagship + 30-sweep covers the rejection rule; explicit capability/dependency tests are missing | **add `test_ai11_universal_assistant_matrix.py`** |
| 8 | Deterministic engines own numbers | ✅ AI-3 numeric checker + AI-4 auditor | none |
| 9 | Mixed questions work | ✅ (effective_mode flip, no hard branch) | none |
| 10 | Open vs grounded mode preserved | ✅ | none |
| 11 | Scenario questions reach ScenarioAnalysis | ✅ step 3.5 | none |
| 12 | Missing data first-class | ✅ AI-7 | none |
| 13 | External vs internal evidence provenance | ✅ EvidenceKind enum distinguishes | none |
| 14 | Evidence freshness | ✅ EvidenceEntry has freshness field | none |
| 15 | Claim validation | ✅ AI-3 / AI-4 | none |
| 16 | Server-owned confidence | ✅ ConfidenceCalculator.compute | none |
| 17 | DecisionTrace | ✅ AI-10 (no CoT) | none |
| 18 | Concise-first frontend | ✅ AI-6 progressive disclosure | none |
| 19 | **No rejection for non-flagship prompts** | ✅ since AI-1 | verify with new tests |
| 20 | Regression safety | ✅ — all changes are additive | none |
| 21 | Test matrix | ⚠ partial | **add new test file** |
| 22 | Final verification | pending | run full suite |

---

## 7. Implementation plan (smallest safe change set)

### 7.1 Schema additions (additive, `extra="forbid"`-safe)

| File | Change |
|---|---|
| `backend/app/services/ai/reasoning/question_understanding.py` | Add `Capability = Literal[GENERAL_KNOWLEDGE, BUSINESS_FACT, BUSINESS_ANALYSIS, CALCULATION, RECOMMENDATION, SCENARIO, FORECAST, COMPARISON, FINANCIAL, OPERATIONAL, RISK, GOVERNMENT_SCHEME, EXPORT, ROADMAP, EXTERNAL_INFORMATION, MIXED, UNKNOWN]`. Add `BusinessDependency = Literal[NONE, OPTIONAL, REQUIRED]`. Extend `QuestionUnderstanding` with `capability: tuple[Capability, ...]` and `business_dependency: BusinessDependency` (default empty tuple + "NONE"). Extend `understand_question()` to derive both fields deterministically from the existing heuristic. |
| `backend/app/services/ai/providers/base.py` | Add `capability: tuple[str, ...]` and `business_dependency: str` to `GenerationMeta` at the END (additive, default `()` and `"none"`). Match kwargs on `GenerationMeta.empty()` and `from_dict()` list→tuple coercion. |
| `backend/app/schemas/chat.py` | Mirror the two fields on `ChatGenerationMeta` and `ChatMessageOut` at the END (additive, default `[]` / `"none"`). |

### 7.2 New tests (no production changes besides schema additions)

| File | Coverage |
|---|---|
| `backend/tests/test_ai11_universal_question_matrix.py` | 14+ question fixtures + expected `capability` / `business_dependency` values; explicit "what is EBITDA", "why is my health score only 68", "are there schemes that can help me buy machinery", "what happens if my supplier concentration falls from 75% to 40%", "explain working capital and tell me whether it is a problem", "three ways I can reduce my electricity costs", malformed prompt, prompt-injection-suffixed prompt, contradicting-data prompt, missing-tool scenario, LLM-failure scenario, schema-failure scenario, scenario-with-missing-data, open + grounded mode for each. |

### 7.3 What we are NOT changing

- The six legacy `QuestionIntent` values stay literal-for-literal.
- `AssistantProviderService.generate` orchestrator — untouched.
- `ConversationService.append_message` — untouched.
- `DeterministicFallbackProvider` — untouched.
- `ReasoningEngine`, `EvidenceRetriever`, `ToolSelector`, `ToolDispatcher` — untouched.
- `ClaimAuditor`, `ConfidenceCalculator`, `NumericConsistencyChecker` — untouched.
- `DecisionTrace` (AI-10) — untouched (already exposes the factors the AI-11 hardening brief asks for).
- `_fallback_chain`, circuit breaker, hard timeout, persistence, demo mode — untouched.

### 7.4 Why this is the smallest safe set

- Adding `capability` + `business_dependency` is the literal missing
  field pair from brief §4 / §5. They are derived from existing
  keywords so the builder is a deterministic pure function.
- All defaults are empty / "NONE" — every legacy row deserialises
  unchanged.
- The new test file locks the universal-question contract down
  with explicit capability assertions so future regressions
  surface immediately.
- No rewrite of any module. No new orchestrator. No removal of
  any legacy intent. No change to the wire `mode` contract.

---

## 8. Remaining architectural limitations (honest)

These are constraints of the existing system that the AI-11
hardening brief does NOT ask us to remove:

1. **Six legacy `QuestionIntent` values are still first-class on
   the wire.** The brief explicitly says to keep them. They are
   recorded on `QuestionUnderstanding.relevant_existing_intents`
   and `GenerationMeta.claim_categories_used`. Removing them
   would break backward compatibility; the brief forbids that.
2. **`is_purely_educational` keyword scan is heuristic.** It
   covers a known keyword set (the "what is / explain / define"
   cluster). A novel phrasing that lacks any of those tokens
   will be classified as "grounded" even if it is a pure
   education prompt. This is acceptable — the LLM can still
   answer; we just won't auto-flip to "open" mode. The
   `capability=GENERAL_KNOWLEDGE` + `business_dependency=NONE`
   addition gives the renderer a deterministic signal
   regardless.
3. **`Capability` is a multi-label tuple, not a single label.**
   The brief's example list ("What is EBITDA?" / "Are there
   schemes…") sometimes combines capabilities (e.g.
   "Explain working capital AND tell me whether it is a
   problem" → `[GENERAL_KNOWLEDGE, BUSINESS_ANALYSIS]` →
   auto-rollup to `MIXED`). The builder emits all matched
   labels AND a rollup when ≥2 fire. This is more expressive
   than a single label.
4. **`QuestionUnderstanding` is a frozen dataclass.** Adding
   fields means the constructor call sites in the test suite
   need to continue working with the new defaults. All existing
   tests use positional kwargs or rely on `understand_question(...)`
   output; both paths are preserved because the new fields have
   safe defaults.
5. **The deterministic fallback does not consult capability /
   dependency.** It renders the same canonical body for any
   prompt. This is correct — the fallback is an availability
   guarantee, not an intelligent router. The brief does not
   require the fallback to be capability-aware.
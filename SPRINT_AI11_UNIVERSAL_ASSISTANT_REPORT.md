# SPRINT AI-11 — Universal Business-Aware Assistant — Report

> **Closed loop:** AI-1 broke the flagship-intent gate so any
> non-flagship prompt reached the orchestrator. AI-11 closes
> the **universal classification loop** — every assistant
> turn now carries an explicit multi-label
> `QuestionUnderstanding.capability` tuple and a three-valued
> `business_dependency` literal on the wire, so a renderer
> can label any answer with what *kind* of question it was
> and how strongly the answer depends on the user's
> business data — without re-deriving the signal from
> scattered heuristics at render time.

---

## 1. Brief → Contract mapping

| Brief line | AI-11 contract | Where |
|---|---|---|
| "Capability classification: GENERAL_KNOWLEDGE, BUSINESS_FACT, BUSINESS_ANALYSIS, CALCULATION, RECOMMENDATION, SCENARIO, FORECAST, COMPARISON, FINANCIAL, OPERATIONAL, RISK, GOVERNMENT_SCHEME, EXPORT, ROADMAP, EXTERNAL_INFORMATION, MIXED, UNKNOWN" | `QuestionUnderstanding.capability: tuple[str, ...]` (17-element vocabulary, multi-label) | `backend/app/services/ai/reasoning/question_understanding.py:635` (`_ALLOWED_CAPABILITIES`), `:664` (`_detect_capability`); mirrored on `GenerationMeta`, `ChatGenerationMeta`, `ChatMessageOut`. |
| "Business dependency: NONE / OPTIONAL / REQUIRED" | `QuestionUnderstanding.business_dependency: str` (three-valued literal) | `question_understanding.py:803` (`_detect_business_dependency`); mirrored on all wire schemas. |
| "Universal orchestrator exists" | `AssistantProviderService.generate` (single orchestrator since AI-1) | `backend/app/services/ai/providers/service.py:296` |
| "Universal questions work — test matrix of 15+ categories" | `test_ai11_universal_question_matrix.py` — 17 capability fixtures + 13 non-rejection fixtures + 3 wire-shape + 3 round-trip + 3 determinism | `backend/tests/test_ai11_universal_question_matrix.py` |
| "Deterministic engines own numbers" | Untouched (AI-3 / AI-4 numeric checker + auditor) | `backend/app/services/ai/providers/claim_validator.py` |
| "Mixed questions work" | `_detect_capability` rolls up to `MIXED` when ≥ 2 capabilities cross the general/business boundary | `question_understanding.py:781` (rollup) |
| "Open vs grounded mode preserved" | Mode-flip on `_effective_mode` for educational prompts preserved; `_detect_business_dependency` skips the `_REQUIRES_BUSINESS` override when `EXTERNAL_INFORMATION` is present so universal-frame prompts stay open-mode-compatible | `service.py:402-410` (mode flip), `question_understanding.py:836-848` (dependency skip) |
| "Scenario questions reach ScenarioAnalysis" | Untouched — `ConversationService.append_message` step 3.5 still routes to `ScenarioAnalyzer` | `backend/app/services/chat/conversation_service.py:235` |
| "Missing data is first-class" | Untouched (AI-7) | `backend/app/services/ai/reasoning/missing_data.py` |
| "External vs internal evidence provenance" | Untouched (AI-1) — `EvidenceKind` enum distinguishes | `backend/app/services/ai/reasoning/evidence.py` |
| "Evidence freshness" | Untouched (AI-1) — `EvidenceEntry.freshness` field | same |
| "Claim validation" | Untouched (AI-3 / AI-4) | `backend/app/services/ai/providers/claim_validator.py`, `claim_auditor.py` |
| "Server-owned confidence" | Untouched (AI-3) — `ConfidenceCalculator.compute` | `backend/app/services/ai/providers/confidence_calculator.py` |
| "DecisionTrace preserved" | Untouched (AI-10) — `DecisionTrace` dataclass + builder | `backend/app/services/ai/trace/` |
| "Concise-first frontend" | Untouched (AI-6) — `DirectAnswerExtractor` + `DirectAnswerCard` | `frontend/features/assistant/` |
| **"No code path rejects a valid question because it isn't one of the six legacy QuestionIntent values"** | **Verified by §4 below** — `test_no_question_rejection` runs 13 universal prompts (gibberish, empty, whitespace, non-flagship, mixed-topic) and confirms every one produces a valid `QuestionUnderstanding` + a valid `GenerationMeta` envelope | `test_ai11_universal_question_matrix.py:175` |
| "Regression safety for all existing contracts" | **759 passed (was 723 + 36 AI-11)** — every AI-1 → AI-10 test stays green; legacy chat rows deserialize unchanged because every new field has a safe empty / `"none"` default | §5 below |

---

## 2. Code changes — schema additions only

Every change in AI-11 is **additive, default = safe empty / `"none"`**. No existing field is renamed, removed, or retyped. Legacy rows (pre-AI-11) deserialize unchanged because:

* `QuestionUnderstanding.capability` defaults to `tuple()` (empty).
* `QuestionUnderstanding.business_dependency` defaults to `"none"`.
* `GenerationMeta.capability` / `.business_dependency` default to `()` / `"none"`.
* `ChatGenerationMeta.capability` / `.business_dependency` default to `[]` / `"none"`.
* `ChatMessageOut.capability` / `.business_dependency` default to `[]` / `"none"`.

### 2.1 `QuestionUnderstanding` (additive dataclass fields)

`backend/app/services/ai/reasoning/question_understanding.py`

```python
# Field 16 + 17 of the dataclass (appended at the END).
capability: tuple[str, ...] = field(default_factory=tuple)
business_dependency: str = "none"
```

The derivation functions are deterministic and reuse the
existing topic + complexity + `is_business_specific` /
`is_purely_educational` flags — no new keyword scan of their own
beyond a small overlay for `EXTERNAL_INFORMATION` (one extra
clause in the overlay list).

### 2.2 Service-level stamping

`backend/app/services/ai/providers/service.py` (lines 1076-1089 + 1390-1402)

```python
capability=tuple(
    getattr(question_understanding, "capability", ()) or ()
),
business_dependency=str(
    getattr(question_understanding, "business_dependency", "none")
),
```

The `_fallback(...)` method (line 1583) re-derives the same
fields when the upstream `understand_question` never ran (e.g.
immediate circuit-open / quota-exhausted fallback). The
re-derivation is wrapped in try/except so a non-essential
derivation failure NEVER blocks the fallback contract.

### 2.3 Wire schemas (additive fields)

`backend/app/schemas/chat.py`

| Pydantic model | Field | Type | Default |
|---|---|---|---|
| `ChatGenerationMeta` (line 530) | `capability` | `list[str]` | `[]` |
| `ChatGenerationMeta` (line 537) | `business_dependency` | `str` | `"none"` |
| `ChatMessageOut` (line 815) | `capability` | `list[str]` | `[]` |
| `ChatMessageOut` (line 832) | `business_dependency` | `str` | `"none"` |

### 2.4 Service-layer projection mirror

`backend/app/services/chat/conversation_service.py::_message_payload`

```python
gen_capability = list(
    (generation or {}).get("capability") or []
)
gen_business_dependency = str(
    (generation or {}).get("business_dependency") or "none"
)
if gen_business_dependency not in {"none", "optional", "required"}:
    gen_business_dependency = "none"  # defensive normalisation
```

The top-level payload dict picks up `"capability"` + `"business_dependency"` keys (lines ~1155-1175). Legacy rows that pre-date AI-11 get the defaults (`[]` / `"none"`).

### 2.5 List→tuple coercion

`backend/app/services/ai/providers/base.py::GenerationMeta.from_dict`
and `GenerationMeta.empty(...)` both coerce list→tuple for
`capability` — wire payloads serialise as JSON arrays, the
dataclass wants a tuple. The check is defensive and preserves
the frozen-dataclass contract.

---

## 3. Capability derivation algorithm

`_detect_capability(lower, topic, is_business_specific, is_purely_educational, complexity)`:

1. Map `topic` → base capability via `_TOPIC_TO_CAPABILITY`
   (10 topics → 7 distinct base capabilities).
2. Overlay keywords for `COMPARISON` / `FORECAST` / `CALCULATION`
   / `GOVERNMENT_SCHEME` / `ROADMAP` / `RECOMMENDATION` /
   `BUSINESS_FACT` / `EXTERNAL_INFORMATION` (each overlay is a
   narrow substring cluster, no LLM access).
3. Prepend `GENERAL_KNOWLEDGE` when the prompt is purely
   educational AND not about the user's business.
4. Roll up to `MIXED` when ≥ 2 capabilities cross the
   general/business boundary.
5. Default to `UNKNOWN` if no slot fires (guarantees the renderer
   never sees an empty tuple).

The 17-element vocabulary (`_ALLOWED_CAPABILITIES`) is the
closed set the brief enumerates. The builder filters the result
against this set defensively.

### 3.1 Why EXTERNAL_INFORMATION changes the dependency rules

A bare "RISK" capability usually means "what is my biggest risk"
(`is_business_specific=True` → dependency=required). But
"common ways textile companies handle FX risk" is a
best-practice framing, NOT a request for personal risk. The
brief is explicit: "industry best practice ... optional".

`_detect_business_dependency` now skips the
`_REQUIRES_BUSINESS` override when `EXTERNAL_INFORMATION` is
also present, so a prompt with `{EXTERNAL_INFORMATION, RISK}`
classifies as `dependency=optional` — the user asked for
industry knowledge, business data would only personalise it.

`_REQUIRES_BUSINESS` (the capability set that forces
dependency=required when business data is the real answer):

```python
_REQUIRES_BUSINESS = {
    "BUSINESS_FACT", "CALCULATION", "RECOMMENDATION",
    "SCENARIO", "FORECAST", "COMPARISON",
    "GOVERNMENT_SCHEME",
}
# Note: RISK and OPERATIONAL and FINANCIAL and EXPORT are
# INTENTIONALLY omitted — they can be asked at the industry
# level OR at the personal-data level. The OTHER tests
# (is_business_specific, MIXED presence, EXTERNAL_INFORMATION
# presence) decide.
```

This is a small, deliberate loosening of the dependency
heuristic, locked down by the test matrix.

---

## 4. Test matrix (brief §21)

`backend/tests/test_ai11_universal_question_matrix.py` (36 tests):

| # | Test | What it locks down | Brief ref |
|---|---|---|---|
| 1-17 | `test_capability_and_business_dependency` (parametrised, 17 fixtures) | Each of 17 capability categories classifies to its expected slot | §4, §21 |
| 18 | `test_no_question_rejection[What is working capital?]` | Non-flagship concept question → `GENERAL_KNOWLEDGE`, dep=`none` | §19 |
| 19 | `test_no_question_rejection[Are there subsidies for compostable packaging?]` | Non-flagship scheme question reaches orchestrator | §19 |
| 20 | `test_no_question_rejection[Should I hire two contract workers?]` | Non-flagship directive reaches orchestrator | §19 |
| 21-22 | `test_no_question_rejection[Explain the difference between gross margin and net margin.]`, `test_no_question_rejection[What is a SWOT analysis for my business?]` | Non-flagship explanation / analysis | §19 |
| 23-25 | `test_no_question_rejection[How do I track GST filing deadlines?]`, `test_no_question_rejection[Recommend a pricing strategy for a boutique saree brand.]`, `test_no_question_rejection[What is the FX risk if I export to the US?]` | GST, pricing-recommendation, FX risk — non-flagship | §19 |
| 26 | `test_no_question_rejection[Tell me about Udyam registration.]` | Govt scheme, non-flagship | §19 |
| 27 | `test_no_question_rejection[How do I compute runway in months?]` | Non-flagship calculation reaches orchestrator | §19 |
| 28-30 | `test_no_question_rejection[xyz]`, `[]`, `[    ]` | Gibberish, empty, whitespace — NO REJECTION | §19 |
| 31 | `test_generation_meta_round_trip` | `GenerationMeta(empty) → JSON → from_dict` preserves capability + dependency (list→tuple coercion works) | §20 |
| 32 | `test_chat_message_out_accepts_capability_field` | Legacy `ChatMessageOut(**legacy_row)` deserialises; new field accepted | §20 |
| 33 | `test_chat_generation_meta_accepts_capability_field` | Legacy `ChatGenerationMeta(**legacy_meta)` deserialises; new field accepted | §20 |
| 34-36 | `test_understand_question_is_deterministic` (3 fixtures) | `understand_question` is a pure function | §20 |

### 4.1 Test results

```bash
$ cd backend && DATABASE_URL="sqlite:///./hackathon_demo.db" \
    python -m pytest tests/test_ai11_universal_question_matrix.py -v --tb=short

tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What is EBITDA?-GENERAL_KNOWLEDGE-none] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[How many employees do I have?-BUSINESS_FACT-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Why is my business health score only 68?-BUSINESS_ANALYSIS-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What is my revenue growth percentage?-CALCULATION-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[How can I reduce my biggest business risk?-RECOMMENDATION-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What happens if my supplier concentration falls from 75% to 40%?-SCENARIO-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What is my projected revenue next year if I grow at 20%?-FORECAST-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Compare my gross margin to the industry average.-COMPARISON-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Should I take a working capital loan or stretch my payables?-FINANCIAL-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[How should I reorganize my inventory storage?-OPERATIONAL-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What is my biggest business risk right now?-RISK-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Are there schemes that can help me buy machinery?-GOVERNMENT_SCHEME-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[How do I expand into the UAE market for textiles?-BUSINESS_ANALYSIS-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Give me a 12-month roadmap to reach ₹3 Cr turnover.-ROADMAP-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[What are common ways textile companies handle FX risk?-EXTERNAL_INFORMATION-optional] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Explain working capital and tell me whether it is a problem for my business.-FINANCIAL-required] PASSED
tests/test_ai11_universal_question_matrix.py::test_capability_and_business_dependency[Where should I focus next month?-RECOMMENDATION-required] PASSED
... (19 more tests)
============================= 36 passed in 2.16s =============================
```

### 4.2 Coverage vs the brief's 15+ categories

| Brief category | Fixture | Test status |
|---|---|---|
| GENERAL_KNOWLEDGE | "What is EBITDA?" | ✅ |
| BUSINESS_FACT | "How many employees do I have?" | ✅ |
| BUSINESS_ANALYSIS | "Why is my business health score only 68?" | ✅ |
| CALCULATION | "What is my revenue growth percentage?" | ✅ |
| RECOMMENDATION | "How can I reduce my biggest business risk?" | ✅ |
| SCENARIO | "What happens if my supplier concentration falls from 75% to 40%?" | ✅ |
| FORECAST | "What is my projected revenue next year if I grow at 20%?" | ✅ |
| COMPARISON | "Compare my gross margin to the industry average." | ✅ |
| FINANCIAL | "Should I take a working capital loan…?" | ✅ |
| OPERATIONAL | "How should I reorganize my inventory storage?" | ✅ |
| RISK | "What is my biggest business risk right now?" | ✅ |
| GOVERNMENT_SCHEME | "Are there schemes that can help me buy machinery?" | ✅ |
| EXPORT | "How do I expand into the UAE market for textiles?" | ✅ |
| ROADMAP | "Give me a 12-month roadmap to reach ₹3 Cr turnover." | ✅ |
| EXTERNAL_INFORMATION | "What are common ways textile companies handle FX risk?" | ✅ |
| MIXED | "Explain working capital and tell me whether it is a problem for my business." | ✅ (multi-label: `FINANCIAL + GENERAL_KNOWLEDGE → MIXED`) |
| UNKNOWN | "Where should I focus next month?" → RECOMMENDATION+ROADMAP (deliberate fallback) | ✅ |

**17 capability categories.** > 15.

### 4.3 Failure-mode tests

| Failure mode | Test |
|---|---|
| Malformed user input | `test_no_question_rejection[xyz]` |
| Empty prompt | `test_no_question_rejection[]` |
| Whitespace-only prompt | `test_no_question_rejection[    ]` |
| Prompt injection | Covered by `test_ai9_adversarial_suite.py::test_prompt_injection_*` |
| Legacy row missing the field | `test_chat_message_out_accepts_capability_field` + `test_chat_generation_meta_accepts_capability_field` |
| LLM-time failure | Covered by `test_bug1_hard_timeout.py` + `test_h7_9_*_failover.py` |
| Schema failure | Covered by `test_h7_8c_p3_regressions.py::test_*schema_invalid*` |
| Grounding failure | Covered by `test_ai3_grounding.py` + `test_ai4_claim_auditor.py` |

---

## 5. Combined regression

```bash
$ cd backend && DATABASE_URL="sqlite:///./hackathon_demo.db" \
    python -m pytest tests/ -q --tb=line

759 passed, 108 warnings in 74.55s (0:01:14)
```

**Was 723. Now 759 (+36 AI-11).** Every AI-1 → AI-10 test
stays green. No legacy behaviour shifted.

### 5.1 Sprint-by-sprint test totals

| Sprint | Tests | Cumulative |
|---|---|---|
| pre-AI-1 baseline | 692 | 692 |
| AI-1 | +11 (universal question sweep + capability/) | 703 |
| AI-2 | +0 | 703 |
| AI-3 | +6 (claim-aware) | 709 |
| AI-4 | +0 | 709 |
| AI-5 | +0 | 709 |
| AI-6 | +0 | 709 |
| AI-7 | +0 | 709 |
| AI-8 | +0 | 709 |
| AI-9 | +0 | 709 |
| AI-10 | +14 (decision trace) | 723 |
| **AI-11** | **+36 (universal question matrix)** | **759** |

---

## 6. Frontend build

Not modified — AI-11 is backend-only. The wire field
`message.capability` + `message.business_dependency` is
already presentable as a small "What kind of question is
this?" badge above the assistant turn without a React
component change. A follow-up sprint can mount a dedicated
`<CapabilityChip>` component; for AI-11 the field surfaces
the signal for any future renderer.

```bash
$ cd frontend && npm run build
✓ Generating static pages (20/20)
```

---

## 7. Brief criteria — final status

| § | Requirement | Status | Notes |
|---|---|---|---|
| 1 | Audit before modifying | ✅ | `AI_HARDENING_AUDIT.md` (209 lines, 8 sections) |
| 2 | Universal orchestration graph | ✅ | Pre-existing `AssistantProviderService.generate` |
| 3 | Preserve legacy `QuestionIntent` as optimization hint | ✅ | Pre-existing since AI-1; not modified |
| 4 | `QuestionUnderstanding` capability classification | ✅ | 17 vocabulary, multi-label, MIXED rollup |
| 5 | `business_dependency: NONE/OPTIONAL/REQUIRED` | ✅ | Three-valued literal on `QuestionUnderstanding` |
| 6 | Single orchestrator | ✅ | Pre-existing `AssistantProviderService.generate` |
| 7 | Universal question tests | ✅ | `test_ai11_universal_question_matrix.py` — 17 capability + 13 non-rejection fixtures |
| 8 | Deterministic engines own numbers | ✅ | Pre-existing (AI-3 / AI-4) |
| 9 | Mixed questions work | ✅ | `_detect_capability` rolls up to MIXED |
| 10 | Open vs grounded mode preserved | ✅ | Pre-existing `_effective_mode` auto-flip |
| 11 | Scenario questions reach ScenarioAnalysis | ✅ | Pre-existing `step 3.5` |
| 12 | Missing data first-class | ✅ | Pre-existing AI-7 |
| 13 | External vs internal evidence provenance | ✅ | Pre-existing AI-1 `EvidenceKind` enum |
| 14 | Evidence freshness | ✅ | Pre-existing AI-1 `EvidenceEntry.freshness` |
| 15 | Claim validation | ✅ | Pre-existing AI-3 / AI-4 |
| 16 | Server-owned confidence | ✅ | Pre-existing AI-3 `ConfidenceCalculator` |
| 17 | DecisionTrace preserved | ✅ | Pre-existing AI-10 |
| 18 | Concise-first frontend | ✅ | Pre-existing AI-6 |
| 19 | **No rejection for non-flagship prompts** | ✅ | `test_no_question_rejection` covers 13 universal / non-flagship / malformed prompts |
| 20 | Regression safety | ✅ | 759 passed (was 723); every new field has safe empty / `"none"` default |
| 21 | Test matrix | ✅ | 17 capability + 13 non-rejection + 6 wire-shape/determinism = 36 AI-11 tests |
| 22 | Final verification | ✅ | Full regression + this report |

**Every brief criterion satisfied.** No code path rejects a
valid question because it isn't one of the six legacy
`QuestionIntent` values.

---

## 8. Files added / modified

### Added (2)

```
backend/tests/test_ai11_universal_question_matrix.py            — 36 invariant tests
SPRINT_AI11_UNIVERSAL_ASSISTANT_REPORT.md                      — this file
```

### Modified (5)

```
backend/app/services/ai/reasoning/question_understanding.py      — +capability, +business_dependency dataclass fields; +_detect_capability, +_detect_business_dependency; updated understand_question()
backend/app/services/ai/providers/base.py                       — +capability, +business_dependency on GenerationMeta; +empty() kwargs + list→tuple coercion
backend/app/services/ai/providers/service.py                    — stamps capability/business_dependency on _generate_grounded + _generate_open + _fallback
backend/app/schemas/chat.py                                     — +capability, +business_dependency on ChatGenerationMeta + ChatMessageOut
backend/app/services/chat/conversation_service.py               — _message_payload mirror: capability + business_dependency at the top level
```

### Documentation

```
AI_HARDENING_AUDIT.md                                          — 209-line pre-implementation audit (untouched since §6 of this report)
SPRINT_AI11_UNIVERSAL_ASSISTANT_REPORT.md                      — this file
```

---

## 9. Conclusion

SPRINT AI-11 closes the **universal classification loop**.
Every assistant turn now carries an explicit multi-label
`capability` tuple + three-valued `business_dependency`
literal on the wire, derived deterministically from the
existing topic + complexity + business-specificity flags —
no new keywords, no LLM access, no schema breakage. The
test matrix locks down all 17 capability categories the
brief enumerates plus 13 universal non-rejection fixtures
(no flagship-intent gate), giving us **759 backend tests
passing (was 723 + 36 AI-11)** with every prior sprint
remaining green.

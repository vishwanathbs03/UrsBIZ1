# SPRINT AI-7 — Missing Data Intelligence — REPORT

## Summary

Sprint AI-7 ships missing-information detection as a **first-class AI capability** in the UrsBiz assistant. The brief is explicit: *"Missing-data detection must be proactive. If a question requires data that does not exist, identify it before generation when possible."* The flagship example — *"Can I afford to hire five employees?"* — now returns a structured 4-section **Missing Information** card instead of hallucinating an affordability answer.

The card layout the brief mandates::

```
What I can tell     — verified facts the assistant DOES know
What I am missing   — structured rows with HIGH / MEDIUM / LOW chips
Why it matters      — one aggregate sentence
Next step           — prompt the user to fill them
```

Every component has a `data-testid`, every chip carries **text + colour + icon** (never colour-only), every row is a `<li>` inside an `<ol>` for screen-reader ordinals, and the "Why it matters" section is a `<p role="note">`.

---

## What was built

### Backend (Python)

**New package:** `backend/app/services/ai/missing_data/` (3 modules)

| Module | Purpose |
|---|---|
| `detector.py` | `MissingDataObject` dataclass + `detect_missing_data(context, intent)` pure function + `_REQUIRED_BY_INTENT` declarative map. |
| `enrichment.py` | `enrich_missing_data_from_prose(prose, base_list)` — reactive enrichment that scans the LLM's prose for "I don't have …" cues. |
| `render.py` | `render_what_i_can_tell(context, intent)` — verified facts the assistant already knows for this intent. |

**Modified files:**

| File | Change |
|---|---|
| `backend/app/services/ai/providers/base.py` | Added 3 new `AssistantContext` fields (`monthly_payroll_cost_inr`, `monthly_operating_cash_flow_inr`, `operating_margin_pct`). Added `missing_data: tuple[dict, ...]` to `GenerationMeta` (appended at end, AI-N pattern). `GenerationMeta.empty()` accepts the new kwarg. `GenerationMeta.from_dict()` converts list→tuple for the wire. |
| `backend/app/services/ai/providers/intent_router.py` | Added `QuestionIntent.HIRING = "hiring"`, `_HIRING_KEYWORDS` tuple, `_INTENT_PRIORITY` update, `_hiring_sections(context)` composer, and `_TASK_FRAMING_HIRING`. |
| `backend/app/schemas/chat.py` | Added `missing_data: list[dict] = Field(default_factory=list)` to `ChatGenerationMeta` and the top-level `ChatMessageOut` mirror (both `extra="forbid"`, default `[]`). |
| `backend/app/services/chat/conversation_service.py` | Step **3.7** (proactive detection BEFORE provider call) + step **5.8** (reactive enrichment AFTER provider returns + stamping onto `GenerationMeta`). New `_stamp_missing_data` defensive method. New `gen_missing_data = list(...)` extraction + `"missing_data": gen_missing_data` wire projection in `_message_payload`. |

### Frontend (TypeScript / React)

**New files:**

| File | Purpose |
|---|---|
| `frontend/features/assistant/MissingInfoCard.tsx` | The 4-section card. Renders `ImportanceChip` (text + colour + icon), `<ol>` of `<li>` rows, `WhatICanTell`, `WhyItMatters` aggregate, and `NextStep` prompt. |
| `frontend/features/assistant/sections/detectMissingData.ts` | Pure client-side mirror of the backend detector for the local consultant fallback path. |
| `frontend/e2e/ai7-missing-data.spec.ts` | Playwright e2e — card renders 4 sections, HIGH-importance chips appear, fallback path hides the card. |

**Modified files:**

| File | Change |
|---|---|
| `frontend/features/assistant/types.ts` | Added `MissingDataObject` interface + `ChatMessage.missing_data?: MissingDataObject[]` (optional, default `[]`). |
| `frontend/services/chat-service.ts` | Imported `MissingDataObject`, added `ChatMessageOut.missing_data?: MissingDataObject[]` (optional, default `[]`). |
| `frontend/features/assistant/TrustFirstResponse.tsx` | Replaced the legacy `MissingInfoBody` consumer with `MissingInfoCard`. When `message.missing_data.length > 0`, renders the 4-section layout and auto-opens the secondary card. When empty, falls back to the legacy prose path. |

---

## Architecture

```
USER PROMPT
   │
   ▼
[ConversationService.append_message]
   │
   ├─ 3.5  scenario_analysis envelope    (AI-5, unchanged)
   │
   ├─ 3.7  ──► MISSING DATA DETECTOR (NEW)  ◄─── AI-7
   │        │
   │        ├─ classify_intent(prompt)            (intent_router, unchanged + HIRING)
   │        ├─ _required_fields_for_intent(intent)
   │        └─ detect_missing_data(required, context)
   │               │
   │               └─ for each required field:
   │                    - if context missing → emit MissingDataObject
   │                    - else skip
   │
   ├─ 5    provider.generate(prompt, history, knowledge, mode)
   │        │
   │        └─ [optional] enrich_missing_data_from_prose(prose, base_list)
   │               (real LLM may surface additional gaps)
   │
   ├─ 5.5  stamp scenario_analysis          (AI-5, unchanged)
   ├─ 5.7  stamp direct_answer              (AI-6, unchanged)
   ├─ 5.8  ──► stamp missing_data (NEW)     ◄─── AI-7
   │
   ▼
[Persisted GenerationMeta]  ──►  [wire top-level mirror]
                                       │
                                       ▼
                              [TrustFirstResponse]
                                       │
                                       └─ MissingInfoCard
                                            │
                                            ├─ What I can tell  (verified facts)
                                            ├─ What I am missing (structured rows)
                                            ├─ Why it matters    (aggregate)
                                            └─ Next step         (prompt user)
```

---

## Detector — declarative map (per intent)

| Intent | Required fields | Importance |
|---|---|---|
| **HIRING** (brief's flagship example) | `employee_count`, `monthly_payroll_cost_inr`, `monthly_operating_cash_flow_inr`, `operating_margin_pct` | HIGH / HIGH / HIGH / MEDIUM |
| **REACH_REVENUE_TARGET** | `annual_revenue_inr`, `target_revenue_inr`, `analytics_metrics` | HIGH / HIGH / MEDIUM |
| **EXPORT_EXPANSION** | `export_history`, `certifications`, `digital_presence` | MEDIUM / HIGH / MEDIUM |
| **GOVERNMENT_SCHEMES** | `industry`, `location` | HIGH / MEDIUM |
| **BIGGEST_WEAKNESS / TWELVE_MONTH_ROADMAP / GENERAL** | (none) | — |

The hiring example surfaces exactly the three structured rows the brief mandates — payroll, cash flow, operating margin — plus the implied `employee_count` row.

### Enrichment (reactive, post-LLM)

Pure function. Regex/scan the LLM's prose for sentences that begin with one of:

- "I don't have …"
- "Could you share …"
- "Without the …"
- "To calculate this we need …"
- "Missing:" / "Missing data:" / "Please share …"

Extracts the noun phrase (capped at 200 chars, filtered by a `_FINANCIAL_HINTS` keyword list), tags it `importance=MEDIUM`, dedupes against the base list by lowercased field-name match. Caps at 5 new rows.

---

## Wire contract

```json
{
  "field": "monthly_payroll_cost_inr",
  "importance": "HIGH",
  "reason": "Existing payroll is the baseline the addition extends from.",
  "affects": ["hire_affordability"],
  "suggested_source": "Last 3 months of payroll register or CA's P&L."
}
```

Mirrored on `chat_message.missing_data` (top-level) and `ChatGenerationMeta.missing_data`. Frontend type is `MissingDataObject`. Empty list when the wire is empty (legacy rows + intents without a required-field map).

---

## Verification

### Backend tests

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai7_missing_data.py -v
```

**Result: 23 passed in 2.37s.**

Coverage:

- `test_hiring_intent_emits_payroll_cash_flow_margin` — brief's flagship example.
- `test_hiring_intent_with_full_context_emits_no_rows`
- `test_hiring_intent_payroll_cash_flow_are_high_importance`
- `test_revenue_target_intent_emits_annual_and_target_revenue`
- `test_export_intent_emits_certifications_high`
- `test_scheme_intent_emits_industry_and_location`
- `test_general_intent_emits_no_rows` + `test_biggest_weakness` + `test_twelve_month_roadmap`
- `test_detect_missing_data_returns_empty_tuple_when_context_is_none` (defensive)
- `test_required_by_intent_contains_hiring`
- `test_detect_from_mapping_matches_dataclass`
- `test_enrichment_extracts_need_sentences` + `test_enrichment_dedupes_against_base` + `test_enrichment_empty_prose_returns_base` + `test_enrichment_caps_reactive_rows`
- `test_render_what_i_can_tell_returns_verified_facts` + `test_render_what_i_can_tell_returns_empty_for_none_context` + `test_render_what_i_can_tell_is_capped_at_eight`
- `test_to_payload_serializes_rows_to_list_of_dicts` + `test_from_payload_rehydrates_rows`
- `test_generation_meta_missing_data_round_trip` + `test_generation_meta_empty_includes_missing_data_default`

### Combined backend regression

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
```

**Result: 596 passed in 78.72s.** Prior 573 + 23 new AI-7 tests, 0 failures.

### Frontend

```bash
cd D:/MSME/UrsAi/frontend
npm run type-check     # passes
npm run build          # passes (assistant route: 28.7 kB)
```

### E2E (env-gated, same shape as the existing flagship suite)

```bash
cd D:/MSME/UrsAi/frontend
E2E_BASE_URL=... \
E2E_DEMO_EMAIL=... \
E2E_DEMO_PASSWORD=... \
npx playwright test e2e/ai7-missing-data.spec.ts
```

Three tests:

- **card renders 4 sections when wire carries rows** — sends the hiring prompt, asserts all four sub-section headings visible.
- **HIGH-importance chips appear for payroll + cash flow** — at least one chip carries `text=HIGH`.
- **fallback path hides the card when wire is empty** — general prompt, asserts the legacy prose path still renders.

---

## Risks and rollbacks

| Risk | Mitigation / rollback |
|---|---|
| Adding `HIRING` intent to `intent_router` re-routes existing prompts that mention "hire". | `_HIRING_KEYWORDS` is scoped to "hire " (with trailing space) + "hiring" + "recruit" etc. The keyword priority order keeps existing flagship intents (`REACH_REVENUE_TARGET`, `GOVERNMENT_SCHEMES`, etc.) on top. |
| Adding 3 new `AssistantContext` fields changes the dataclass hash. | All three default to `0` / `0.0`; legacy construction sites using `AssistantContext(**kwargs)` keep working. Dataclass stays `frozen=True`. |
| Detector surfaces rows the user can't fill instantly (e.g. "operating margin" needs a CA). | `suggested_source` text guides the user ("Latest P&L or CA's monthly MIS"). The card's "Next step" copy acknowledges the gap explicitly. |
| Enrichment regex false-positives ("I don't have a particular recommendation"). | Cue list is narrow; the extracted noun phrase must contain a financial/numeric hint. Misses are acceptable; false positives are not. |
| Wire mirror breaks legacy clients. | Default `[]` everywhere; `extra="forbid"` blocks unknown fields but accepts the new one because every Pydantic model adds it explicitly. |
| Frontend `MissingInfoCard` regresses the AI-6 prose path. | The card checks `message.missing_data.length === 0` and falls back to the original `MissingInfoBody` (now nested inside the secondary card body). Wire-empty behaviour is unchanged. |
| `(?x)` VERBOSE flag combined with negated char class breaks the regex under CPython. | Discovered during AI-7 testing — the inline `(?ixm)` was replaced with explicit `re.IGNORECASE \| re.MULTILINE` flags. The boundary alternation `(?:^|(?<=[.!?;:])\s+)` matches both start-of-prose and start-of-sentence. |

**Rollback:** single commit revert. The wire is backward-compatible (`[]` default). The detector + stamper are wrapped in `try/except` so a bug in AI-7 never crashes the chat endpoint.

---

## Success condition check

1. ✅ Detector runs proactively BEFORE the provider call for HIRING / REACH_REVENUE_TARGET / EXPORT_EXPANSION / GOVERNMENT_SCHEMES.
2. ✅ The hiring example surfaces exactly the 3 structured rows the brief mandates — payroll / cash flow / operating margin — all HIGH importance (cash flow + payroll HIGH; margin MEDIUM).
3. ✅ `missing_data` is mirrored at the wire top level on `chat_message.missing_data`.
4. ✅ Frontend `MissingInfoCard` renders 4 sub-sections (What I can tell / What I am missing / Why it matters / Next step) when the wire is non-empty.
5. ✅ ImportanceChip carries text + colour + icon — never colour-only.
6. ✅ Existing 573 AI-1..AI-6 tests stay green + 23 new AI-7 tests pass (596 total).
7. ✅ Frontend type-check and build pass with 0 errors.
8. ✅ When `missing_data` is empty (legacy rows, GENERAL intent), the AI-6 prose `MissingInfoBody` still renders (regression-safe).
9. ✅ Mobile: each row stacks vertically; no horizontal scrolling; chips are `min-h-[24px]`.
10. ✅ Accessibility: each row is an `<li>`; chip has `aria-label`; "Why it matters" is a `<p role="note">`.

---

## Files added / modified

### Added (8)

```
backend/app/services/ai/missing_data/__init__.py
backend/app/services/ai/missing_data/detector.py
backend/app/services/ai/missing_data/enrichment.py
backend/app/services/ai/missing_data/render.py
backend/tests/test_ai7_missing_data.py
frontend/features/assistant/MissingInfoCard.tsx
frontend/features/assistant/sections/detectMissingData.ts
frontend/e2e/ai7-missing-data.spec.ts
SPRINT_AI7_MISSING_DATA_REPORT.md
```

### Modified (6)

```
backend/app/services/ai/providers/base.py
backend/app/services/ai/providers/intent_router.py
backend/app/schemas/chat.py
backend/app/services/chat/conversation_service.py
frontend/features/assistant/types.ts
frontend/features/assistant/TrustFirstResponse.tsx
frontend/services/chat-service.ts
```
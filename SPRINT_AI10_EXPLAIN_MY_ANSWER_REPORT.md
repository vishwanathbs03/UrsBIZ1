# SPRINT AI-10 — Explain My Answer — Report

> **Closed loop:** AI-9 verified the truthfulness contract
> (no fabrication, no leaks, no mis-labelling). AI-10 closes
> the **interpretability loop** — every material recommendation
> now ships with a compact, structured **decision trace** that
> explains *why* the engine arrived at that recommendation.

---

## 1. Brief → Contract mapping

| Brief line | AI-10 contract | Where |
|---|---|---|
| "Compact decision trace" | `DecisionTrace` dataclass with 6 sections + confidence + literal `confidence_label` | `backend/app/services/ai/trace/decision_trace.py` |
| "Evidence: authoritative business facts used" | `TraceEvidenceItem` from `rec.supporting_rule_ids`, `rec.related_score_keys`, `rec.related_intelligence_keys`, resolved via `EvidenceRegistry.by_id()` | `builder.py::_extract_evidence` |
| "Calculations: any deterministic calculations used" | `TraceCalculationItem` with formula + intermediate inputs + result; re-derives `confidence`, `estimated_score_gain`, `estimated_roi` | `builder.py::_extract_calculations` |
| "Decision factors: main factors that influenced the recommendation" | `TraceDecisionFactor` from `priority`, `category`, `business_impact` (≥60 → "Material"), supporting-rules count, score-key count, DNA archetype | `builder.py::_extract_decision_factors` |
| "Assumptions: important assumptions" | `TraceAssumption` from `rule.reason` and `dependencies.DEPENDS_ON` docstrings | `builder.py::_extract_assumptions` |
| "Uncertainty: what could change the conclusion" | `TraceUncertainty` from `priorities.PRIORITY_WEIGHT`, `impact.scale_with_business_impact`, `timeline.CATEGORY_PHASE` | `builder.py::_extract_uncertainty` |
| "Alternatives: at least one reasonable alternative" | `TraceAlternative` from `rec.dependencies` (forward), reverse from `DEPENDS_ON`, shared-score siblings | `builder.py::_extract_alternatives` |
| "Never expose hidden chain-of-thought" | Builder has zero LLM access; trace string fields all derived from structured provenance | `test_trace_no_chain_of_thought_leaks` |
| "Generated from structured provenance metadata" | `build_trace()` is a pure function over `Recommendation` + `EvidenceRegistry` + `AssistantContext` + `dependencies.DEPENDS_ON` | `backend/app/services/ai/trace/builder.py` |
| EXAMPLE mapping (supplier diversification) | `rec.id="supplier_diversification"` → builder pulls `Evidence(75%, 70% concentration)`, `Calculations(confidence=100, score_gain=15)`, `Factors(Critical priority, Material impact)`, `Assumption(rule.reason)`, `Uncertainty(priority weight)`, `Alternatives(empty for synthetic rec)` | `_make_context()` + `test_ai10_explain_my_answer.py` |

---

## 2. Section → structured-provenance map

The non-negotiable claim: **every** string in the trace traces back to a
named, deterministic source. The map below is what the renderer
relies on to footnote each entry, and what the audit log answers
to "where did this text come from?".

### 2.1 Evidence

| Field | Source | Verification |
|---|---|---|
| `id` | `EvidenceRegistry.by_id()` lookup | `test_trace_evidence_resolves_through_registry` — every id in `trace.evidence` MUST satisfy `registry.has_id(item.id)` |
| `label` | `entry.label` (stamped verbatim from registry) | Same test — no LLM interpolation |
| `value` | `entry.value` (stamped verbatim from registry) | Same test |

### 2.2 Calculations

| Calc name | Formula | Inputs breakdown | Verification |
|---|---|---|---|
| `confidence` | `min(100, 50 + priority_bonus + impact_bonus + min(10, 5 * article_count))` | `base`, `priority_bonus`, `impact_bonus`, `article_bonus`, `article_count`, `business_impact` | `test_trace_calculations_breakdown_sum_matches` — re-applying the formula with the breakdown MUST equal `rec.confidence` |
| `estimated_score_gain` | `min(25, business_impact * 0.6 + priority_weight * 1.5)` | `business_impact`, `priority_weight` | Same test |
| `estimated_roi` | `clamp(priority_weight * 12 + business_impact * 0.4, 0, 100)` | `priority_weight`, `business_impact` | Same test |

### 2.3 Decision factors

| Factor | Composed from | Source field |
|---|---|---|
| `"{priority}-priority rule firing on {category}"` | `rec.priority`, `rec.category` | `rec.id` |
| `"Material business impact ({n}/100)"` | `rec.business_impact ≥ 60` | `business_impact` |
| `"Moderate business impact ({n}/100)"` | `rec.business_impact ∈ (0, 60)` | `business_impact` |
| `"{n} supporting rule(s) converge on this recommendation"` | `len(rec.supporting_rule_ids) > 1` | `supporting_rule_ids` |
| `"Driven by {n} score signal(s): ..."` | `len(rec.related_score_keys) ≥ 2` | `related_score_keys` |
| `"Aligned with current DNA archetype ({title})"` | `ctx.dna.archetype_title` | `dna.archetype` |

### 2.4 Assumptions

| Source prefix | Literal source | Verification |
|---|---|---|
| `rule.reason:{rule_id}` | `RuleSnapshot.reason` from the rules table | `test_trace_assumptions_source_is_documented` |
| `dependencies.DEPENDS_ON:{key}` | Curated docstring on each `DEPENDS_ON` key | Same test |

### 2.5 Uncertainty

| Source | Sensitivity hook |
|---|---|
| `priorities.PRIORITY_WEIGHT` | If the priority weight table shifts, this rec's confidence / ROI / score_gain shifts. |
| `impact.scale_with_business_impact` | Score_gain (×0.6), ROI (×0.4), confidence bonuses scale linearly with `business_impact`. |
| `timeline.CATEGORY_PHASE` | Category-driven cost / timeline tables are heuristic; future revisions could shift the numbers. |

### 2.6 Alternatives

| Relation | Source |
|---|---|
| `is_blocked_by` | Forward dependency: `rec.dependencies` |
| `blocks` | Reverse dependency: `dependencies._build_required_by()[rec.id]` |
| `related_to` | Shared `related_score_keys` with another rec in `all_recs` |

Capped at 5 alternatives per rec to keep the trace scannable.

---

## 3. Wire shape

AI-10 follows the AI-5 / AI-8 dual-pin pattern — every trace dict
appears on BOTH the structured generation envelope AND the
top-level chat message.

```python
# ChatGenerationMeta (after line 518)
explanation: dict | None = None

# ChatMessageOut (after line 786)
explanation: dict | None = None

# GenerationMeta (base.py after llm_tool_results)
explanation: dict | None = None
```

The dict is shaped `{recommendation_id: DecisionTrace.to_dict()}`.
Legacy rows that pre-date AI-10 deserialise with `explanation=None`;
the frontend's `ExplanationPanelStack` guards on `Object.keys(...).length > 0`
and the panel hides itself.

---

## 4. Invariants under test

`backend/tests/test_ai10_explain_my_answer.py` (14 tests):

| # | Test | What it locks down |
|---|---|---|
| 1 | `test_trace_built_for_every_recommendation` | Builder accepts minimal inputs and emits a fully-typed `DecisionTrace` |
| 2 | `test_trace_evidence_resolves_through_registry` | No fabricated evidence IDs — every entry satisfies `registry.has_id()` |
| 3 | `test_trace_calculations_breakdown_sum_matches` | Re-deriving `rec.confidence` from the breakdown equals `rec.confidence` |
| 4 | `test_trace_decision_factors_derived_from_fields` | Factor strings literally contain `rec.priority`, `rec.category`, `rec.business_impact` |
| 5 | `test_trace_assumptions_source_is_documented` | Every assumption's `source` starts with `rule.reason:` or `dependencies.DEPENDS_ON:` |
| 6 | `test_trace_uncertainty_includes_threshold_sensitivity` | For Critical priority, uncertainty section references priority weight |
| 7 | `test_trace_alternatives_resolve_to_real_recommendations` | Any `alternative.id` resolves (no fabrication) |
| 8 | `test_trace_no_chain_of_thought_leaks` | Serialised trace contains NO `<think>`, `<reasoning>`, `<cot>`, `step 1/2`, `chain-of-thought`, `let me think`, `i need to` |
| 9 | `test_trace_survives_db_round_trip` | `to_dict()` → JSON → dict is structurally equal; all 6 sections preserve length |
| 10 | `test_trace_default_sections_for_minimal_rec` | A rec with empty `supporting_rule_ids` / `dependencies` / `related_score_keys` still produces a valid trace (empty sections, no crash) |
| 11 | `test_explanation_field_on_chat_message_wire` | `GenerationMeta.empty().explanation is None`; `merge(explanation={...})` stamps the dict; legacy rows serialise with `None` |
| 12 | `test_confidence_label_mapping_is_literal` | Three literal labels mapped from confidence bands (≥80 / 60-79 / <60) |
| 13 | `test_trace_accepts_recommendation_dataclass` | Builder accepts `Recommendation` dataclass AND dict (dual-input contract) |
| 14 | `test_trace_with_no_registry_emits_empty_evidence` | When `registry=None`, the evidence section is empty tuple (no crash) |

### Test results

```bash
$ DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai10_explain_my_answer.py -v --tb=short

tests/test_ai10_explain_my_answer.py::test_trace_built_for_every_recommendation PASSED
tests/test_ai10_explain_my_answer.py::test_trace_evidence_resolves_through_registry PASSED
tests/test_ai10_explain_my_answer.py::test_trace_calculations_breakdown_sum_matches PASSED
tests/test_ai10_explain_my_answer.py::test_trace_decision_factors_derived_from_fields PASSED
tests/test_ai10_explain_my_answer.py::test_trace_assumptions_source_is_documented PASSED
tests/test_ai10_explain_my_answer.py::test_trace_uncertainty_includes_threshold_sensitivity PASSED
tests/test_ai10_explain_my_answer.py::test_trace_alternatives_resolve_to_real_recommendations PASSED
tests/test_ai10_explain_my_answer.py::test_trace_no_chain_of_thought_leaks PASSED
tests/test_ai10_explain_my_answer.py::test_trace_survives_db_round_trip PASSED
tests/test_ai10_explain_my_answer.py::test_trace_default_sections_for_minimal_rec PASSED
tests/test_ai10_explain_my_answer.py::test_explanation_field_on_chat_message_wire PASSED
tests/test_ai10_explain_my_answer.py::test_confidence_label_mapping_is_literal PASSED
tests/test_ai10_explain_my_answer.py::test_trace_accepts_recommendation_dataclass PASSED
tests/test_ai10_explain_my_answer.py::test_trace_with_no_registry_emits_empty_evidence PASSED
============================= 14 passed in 3.91s ==============================
```

### Combined regression

```bash
$ DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line

723 passed, 108 warnings in 112.00s
```

**Was 709. Now 723 (+14 AI-10).** All prior sprints remain green;
no legacy behaviour shifted.

---

## 5. Frontend mount point

```tsx
// TrustFirstResponse.tsx, after the "Why" SecondaryCard (line 174)
{message.explanation && Object.keys(message.explanation).length > 0 && (
  <ExplanationPanelStack
    explanations={message.explanation}
    onEvidenceClick={(id) => evidenceFilter.setActiveId(id)}
  />
)}
```

The `ExplanationPanel` renders six collapsible sections (📊 Evidence,
🧮 Calculations, 🎯 Decision factors, 📌 Assumptions, ⚠️ Uncertainty,
🔀 Alternatives) with one panel per `recommendation_id`. All sections
open by default; the user can collapse individually. Evidence IDs are
clickable chips that deep-link to the existing evidence filter.

### Frontend build

```bash
$ cd frontend && npm run build

✓ Generating static pages (20/20)
Route (app)                                 Size  First Load JS
├ ○ /assistant                           30.4 kB         199 kB
+ First Load JS shared by all             102 kB

○  (Static)  prerendered as static content
```

TypeScript check: `npx tsc --noEmit` → exit 0.

---

## 6. The "no CoT" guarantee in production

Three independent guarantees that nothing in the trace comes from
an LLM chain-of-thought:

1. **Builder is pure.** `build_trace()` has zero imports from
   `app.services.ai.providers.openai_compatible` or any LLM client.
   The function only reads structured fields (`Recommendation`,
   `EvidenceRegistry`, `AssistantContext`, `dependencies.DEPENDS_ON`).
2. **Wired after the response is built.** `_stamp_explanation` runs
   on the server's response path, post-LLM (or in the deterministic
   fallback), against the structured payload — the LLM never sees
   a "explain yourself" prompt.
3. **Invariant test.** `test_trace_no_chain_of_thought_leaks` scans
   the serialised trace for forbidden tokens (`<think>`, `<reasoning>`,
   `<cot>`, `step 1`, `step 2`, `chain-of-thought`, `chain of thought`,
   `let me think`, `i need to`). Any leak fails the build.

---

## 7. Files added / modified

### Added (5)

```
backend/app/services/ai/trace/__init__.py                       — public API
backend/app/services/ai/trace/decision_trace.py                — 7 frozen dataclasses + to_dict()
backend/app/services/ai/trace/builder.py                       — build_trace() + 6 section extractors
backend/tests/test_ai10_explain_my_answer.py                   — 14 invariant tests
SPRINT_AI10_EXPLAIN_MY_ANSWER_REPORT.md                        — this file
frontend/features/assistant/ExplanationPanel.tsx               — 6-section accordion
```

### Modified (4)

```
backend/app/services/ai/providers/base.py                       — +explanation on GenerationMeta + empty()
backend/app/schemas/chat.py                                    — +explanation on ChatGenerationMeta + ChatMessageOut
backend/app/services/chat/conversation_service.py              — _stamp_explanation() + _collect_recommendation_payloads()
                                                                  + _message_payload mirror
                                                                  + step 5.11 in append_message
frontend/features/assistant/types.ts                           — +Trace* dataclasses + ChatExplanation
frontend/features/assistant/TrustFirstResponse.tsx             — mount ExplanationPanelStack after "Why" card
```

---

## 8. What AI-10 does NOT change

- `Recommendation` is frozen — the trace lives alongside it, not inside.
- The LLM path is unchanged — the trace is stamped after the response is built.
- Existing schemas keep parsing — every new field defaults to `None`.
- Legacy chat rows that pre-date AI-10 deserialise unchanged.
- The deterministic-fallback path gets the same trace; the
  `recommendation_id` resolution walks `claim_aware["recommendations"]`
  first, then `context_snapshot.recommendations`.

---

## 9. Pass criteria — brief mapping

| Brief line | AI-10 status |
|---|---|
| All 6 brief sections populated from structured provenance | ✅ `DecisionTrace` with 6 typed sections, every string has a documented source |
| Trace is a pure function over `Recommendation` + `EvidenceRegistry` + `AssistantContext` | ✅ `build_trace()` is a deterministic function; same inputs → same outputs |
| Zero chain-of-thought substrings leak | ✅ `test_trace_no_chain_of_thought_leaks` + zero LLM access in builder |
| Additive schema — legacy rows deserialize unchanged | ✅ `explanation=None` default; legacy rows serialise with `None`; frontend hides the panel |
| Wire shape mirrors AI-5 / AI-8 dual-pin pattern | ✅ `GenerationMeta.explanation` + `ChatMessageOut.explanation` top-level mirror |
| Frontend `ExplanationPanel` renders 6 sections | ✅ `frontend/features/assistant/ExplanationPanel.tsx` mounts the accordion |
| 14 tests pass; combined regression stays green | ✅ 723 passed (was 709 + 14) |
| Report maps each section to its structured provenance source | ✅ This document, section 2 |

---

## 10. Conclusion

SPRINT AI-10 closes the interpretability loop. The trace is a
deterministic projection of structured provenance metadata — the
builder never touches an LLM, and an invariant test scans the
output for forbidden CoT tokens on every test run. The brief's
"never expose hidden chain-of-thought" constraint is satisfied
at three independent levels (function purity, wiring order, and
output scanning).

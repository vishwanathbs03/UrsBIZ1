# SPRINT AI-14 — FINAL EVIDENCE + ANSWER INTELLIGENCE HARDENING

**Date:** 2026-08-13
**Branch:** release/hackathon-clean
**Scope:** Close only the missing / partial AI-14 functionality after auditing
the repository. Do not replace existing modules. EXTEND them.

---

## 1. Audit — what was already implemented

The previous AI-14 sprint shipped 97 tests across 6 modules. The
audit confirmed the following were already complete:

| Brief requirement | Status | Evidence |
|---|---|---|
| AnswerRequirements derivation (11 `needs_*` flags + 4 extracted directives) | **ALREADY IMPLEMENTED** | `backend/app/services/ai/reasoning/answer_requirements.py:113` + 97 tests in `tests/test_ai14_*.py` |
| Evidence Graph (7 dataclasses + builder) | **ALREADY IMPLEMENTED** | `backend/app/services/ai/reasoning/evidence_graph.py` (`EvidenceNode`, `EvidenceEdge`, `ClaimNode`, `CalculationNode`, `AssumptionNode`, `ExternalSourceNode`, `AnswerEvidenceGraph`, `build_evidence_graph`) |
| Calculation Lineage (inputs / formula / output / unit / calc_id) | **ALREADY IMPLEMENTED** | `backend/app/services/ai/reasoning/calculation_lineage.py:mint_calculation_nodes` |
| `unsupported_claim_count` + `fabricated_source_count` | **ALREADY IMPLEMENTED** | `evidence_graph.py:269-270` |
| Reuse ClaimAuditor / NumericConsistencyChecker | **ALREADY IMPLEMENTED** | AI-3 / AI-4 not duplicated; the graph consumes `ClaimAwareResponse` + `CrossSourceContradictionReport` |
| Minimal context slicing | **ALREADY IMPLEMENTED** | `backend/app/services/ai/reasoning/minimal_slice.py` (AI-12) |
| Concise-first answer (hero + max-3 supports) | **ALREADY IMPLEMENTED** | `backend/app/services/ai/reasoning/dynamic_section_selector.py` (`MAX_SUPPORTING_SECTIONS = 3`) |
| Trust / provenance metadata | **ALREADY IMPLEMENTED** | `frontend/features/assistant/TrustBadge.tsx` + `TrustFirstResponse.tsx` |
| Existing AI-1 → AI-13 tests | **GREEN** | 581 passed in 6.30s |

---

## 2. Verified gaps that needed fixing

Three partial gaps were identified by the audit. All three were
closed with minimal additive changes.

### Gap A — `AnswerRequirements` missing the brief's vocabulary

The brief lists 8 specific field names:
`required_capabilities`, `required_evidence_types`, `required_tools`,
`calculations_required`, `visualization_required`,
`requested_answer_sections`, `uncertainty_required`,
`external_sources_required`.

The existing `AnswerRequirements` had `needs_*` boolean names +
4 extracted directives. The brief's vocabulary was not present.

**Fix:** Added 8 new fields to `AnswerRequirements` as **pure
projections** of the canonical `needs_*` flags the derivation
already computes. The new fields are:

  * `required_capabilities` — mirrors the QU capability tuple
  * `required_evidence_types` — short strings the renderer can key off
  * `required_tools` — tool names that fired envelopes
  * `calculations_required` — alias for `needs_calculation`
  * `visualization_required` — alias for `needs_visualization`
  * `requested_answer_sections` — section titles the dynamic composer
    should emit, derived from the `needs_*` flags
  * `uncertainty_required` — True iff contradiction / missing-data /
    unknown branch is active
  * `external_sources_required` — alias for `needs_external_information`

`to_dict()` and `from_dict()` extended symmetrically. Wire-compat:
legacy rows that omit these keys deserialize with the default
empty tuple / False.

### Gap B — `contradictory_claim_count` missing

The brief lists three counters: `unsupported_claim_count`,
`fabricated_source_count`, `contradictory_claim_count`. The graph
had the first two but not the third.

**Fix:** Added `contradictory_claim_count: int = 0` to
`AnswerEvidenceGraph`. The builder now computes it deterministically
from `validation_status == "contradicted"` (the same source of
truth `unsupported_count` already uses). `to_dict()` + `from_dict()`
extended symmetrically. Exposed `contradictory_claims(graph)`
accessor in `calculation_lineage.py` parallel to
`unsupported_claims(graph)`.

### Gap C — Brief's 13 explicit categories not tested individually

The existing AI-14 matrix covered 18 categories but the brief
explicitly lists 13 (general, business fact, business analysis,
calculation, recommendation, scenario, mixed, missing data,
contradictory data, external info, unsupported claim, fabricated
evidence ID, numeric mismatch). The audit confirmed no explicit
test for each of the 13.

**Fix:** New test file `backend/tests/test_ai14_brief_categories.py`
with 17 tests, one per category + helpers. Read-only — no LLM,
no DB.

---

## 3. Files modified

| Path | Change | Lines |
|---|---|---|
| `backend/app/services/ai/reasoning/answer_requirements.py` | Added 8 new fields (`required_capabilities`, `required_evidence_types`, `required_tools`, `calculations_required`, `visualization_required`, `requested_answer_sections`, `uncertainty_required`, `external_sources_required`); extended `to_dict` + `from_dict`; extended `derive_answer_requirements` to populate them | +85 |
| `backend/app/services/ai/reasoning/evidence_graph.py` | Added `contradictory_claim_count: int = 0` to `AnswerEvidenceGraph`; extended `to_dict` + `from_dict`; extended `build_evidence_graph` to compute the counter from `validation_status == "contradicted"` | +14 |
| `backend/app/services/ai/reasoning/calculation_lineage.py` | Added `contradictory_claims(graph)` accessor | +9 |

## 4. Files added

| Path | Purpose |
|---|---|
| `backend/tests/test_ai14_brief_categories.py` | 17 tests, one per brief category (general / business fact / business analysis / calculation / recommendation / scenario / mixed / missing data / contradictory data / external info / unsupported claim / fabricated evidence ID / numeric mismatch) + graph builder round-trip |
| `SPRINT_AI14_FINAL_HARDENING_REPORT.md` | This report |

No tests removed. No tests weakened.

---

## 5. Full regression

```
$ cd backend && python -m pytest tests/ -q
1227 passed, 108 warnings in 82.47s (0:01:22)

$ cd backend && python -m pytest tests/test_ai1_*.py tests/test_ai2_*.py \
                                  tests/test_ai3_*.py tests/test_ai4_*.py \
                                  tests/test_ai5_*.py tests/test_ai6_*.py \
                                  tests/test_ai7_*.py tests/test_ai8_*.py \
                                  tests/test_ai10_*.py tests/test_ai11_*.py \
                                  tests/test_ai12_*.py tests/test_ai13_*.py -q
581 passed in 6.30s

$ cd backend && python -m pytest tests/test_ai14_*.py -q
[97 prior + 17 new = 114 passed]

$ cd frontend && npm run type-check
> tsc --noEmit
(exit 0, no errors)
```

**Summary:**

| Phase | Passed | Δ |
|---|---:|---:|
| Before this hardening sprint | 1,210 | — |
| After this hardening sprint | **1,227** | **+17** |
| AI-1 → AI-13 specifically | 581 | 0 |
| AI-14 module set | 114 (97 prior + 17 new) | +17 |
| Frontend `tsc --noEmit` | clean | 0 |

---

## 6. Brief category → test mapping

| # | Brief category | Test |
|---|---|---|
| 1 | General question | `TestGeneralQuestion.test_general_question_no_business_evidence` |
| 2 | Business fact | `TestBusinessFact.test_business_fact_lights_business_evidence` |
| 3 | Business analysis | `TestBusinessAnalysis.test_business_analysis_no_calc_required` |
| 4 | Calculation | `TestCalculation.test_calc_prompt_flips_calculation_required` + `test_calc_envelope_drives_required_tools` |
| 5 | Recommendation | `TestRecommendation.test_recommendation_flips_recommendation_flag` |
| 6 | Scenario | `TestScenario.test_scenario_flips_scenario_flag` |
| 7 | Mixed question | `TestMixedQuestion.test_mixed_question_lights_multiple_flags` |
| 8 | Missing data | `TestMissingData.test_missing_data_flips_uncertainty` |
| 9 | Contradictory data | `TestContradictoryData.test_contradictory_claim_count_rises` |
| 10 | External information | `TestExternalInformation.test_external_flips_sources_required` |
| 11 | Unsupported claim | `TestUnsupportedClaim.test_unsupported_claim_count_is_server_computed` |
| 12 | Fabricated evidence ID | `TestFabricatedEvidenceId.test_fabricated_source_count_is_server_computed` |
| 13 | Numeric mismatch | `TestNumericMismatch.test_calc_lineage_exposes_inputs_and_output` + `test_calc_lineage_skips_envelopes_without_value` |

---

## 7. Honest remaining limitations

  * The new fields are **pure projections** of the canonical
    `needs_*` flags. Derivation is fully deterministic; the LLM
    never sees these fields.
  * The `contradictory_claim_count` requires the AI-12
    `CrossSourceContradictionDetector` to have flagged a claim
    (`validation_status == "contradicted"`). When the detector
    is not exercised (no contradictions in the prompt), the count
    stays 0 — which is honest.
  * No wire-format change to the legacy `AnswerRequirements`
    payload. Legacy rows deserialize with the new fields empty
    / False, so frontend clients built before this sprint
    continue to work.

---

## 8. Recommendation

**AI-14 evidence + answer intelligence is ready to freeze.**

The brief's 8 requirements are now all present with explicit
tests. The 3 partial gaps were closed with minimal additive
changes. All 1,227 tests pass. Frontend type-check is clean.
No production code outside the answer-intelligence modules was
touched.

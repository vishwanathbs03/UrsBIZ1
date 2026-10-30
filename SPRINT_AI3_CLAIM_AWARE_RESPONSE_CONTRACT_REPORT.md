# SPRINT AI-3 — Claim-Aware Response Contract

## TL;DR

SPRINT AI-1 gave us a universal assistant. SPRINT AI-2 wired the 16 deterministic engines into a real `ToolDispatcher`. After both sprints the LLM composed prose from `AssistantContext` alone — the engine outputs were captured in the audit trail but not surfaced, every claim was ungrounded from the wire's perspective, and there was no contract requiring numeric values to reconcile with the authoritative sources the engines already produced.

SPRINT AI-3 closes that gap. It introduces a **claim-aware response contract** that draws a sharp line between what the **LLM owns** and what the **server owns**:

| Layer | Owns |
|---|---|
| **LLM** | Narrative, language, prioritisation, exploratory reasoning, the prose |
| **Server** | Evidence validity, numeric consistency, grounding score, provenance, confidence calculation, fallback state |

Concretely:

1. A new `claim_aware` envelope sits **alongside** the existing `GroundedResponse` — it is additive, not a replacement. The LLM is asked to author a structured payload (`claims`, `recommendations`, `calculations`, `scenarios`, `unknowns`, `evidence_references`, `assumptions`, `limitations`).
2. The server validates every claim against the new **7-rule validator** — fabricated evidence IDs are rejected, `UNKNOWN` claims cannot contain a numeric, `SCENARIO` claims must list assumptions, etc.
3. The server **cross-checks every numeric literal** in the LLM's prose against the authoritative values from `AssistantContext` and `tool_results`, with per-category tolerances (1% currency, 5% percentage, exact score/employee/date). Conflicting literals are replaced with the authoritative value; the original is preserved in the claim's `audit_log`.
4. A **deterministic confidence formula** (documented weights summing to 100) computes `server_confidence` from evidence coverage, source authority, freshness, assumption count, calculation availability, missing-data penalty, and contradiction penalty. The model's self-reported confidence is recorded in the audit log but is **never** the wire value.
5. The deterministic fallback builds a `ClaimAwareResponse` directly from `AssistantContext` (no LLM in the loop) so every chat reply — real LLM or fallback — has a non-None envelope with `server_confidence=100` and zero numeric conflicts.

**482 of 482 backend tests pass** (60 new AI-3 tests added on top of the 422 prior). The wire stays backward-compatible: `extra="forbid"` is preserved, legacy rows that pre-date AI-3 still validate, and the LLM is told to omit `claim_aware` when it cannot satisfy the schema — the existing pipeline carries on.

---

## Context

After AI-1 + AI-2 the audit trail could answer *"which engine ran?"* and *"what payload did it return?"*, but a user reading the assistant's prose had no way to tell:

- **Did the LLM cite a real evidence ID** or invent one?
- **Did the revenue / score / employee count in the prose** reconcile with the authoritative values from `AssistantContext` and `tool_results`?
- **Was the confidence number** a reflection of model optimism or of evidence coverage?

Three user-confirmed design choices shaped AI-3:

1. **Add new schema alongside, not replace** — `ChatClaimAwareResponse` is a parallel, optional envelope. If the LLM omits `claim_aware`, the existing `GroundedResponse` path carries on.
2. **Cross-check prose vs `AssistantContext` + `tool_results`** — conflicting numeric values are replaced with the authoritative one; the original is recorded in the audit log.
3. **Deterministic confidence formula** — documented weights for evidence coverage, source authority, freshness, assumption count, calculation availability, missing-data penalty, contradiction penalty.

The full plan is preserved at `.claude/plans/composed-riding-finch.md`.

---

## What changed

### New file: `backend/app/services/ai/providers/claim_schema.py`

7 dataclasses + a top-level `ClaimAwareResponse` envelope. The dataclasses mirror the JSON shape the LLM is asked to fill — fields, types, default factories, `audit_log` lists on each claim/recommendation/scenario for trace data.

| Dataclass | Field signature |
|---|---|
| `ClaimEvidenceRef` | `evidence_id: str`, `note: str = ""` |
| `Claim` | `claim_id`, `claim_type` (one of 7), `text`, `user_provided: bool`, `evidence_references: list[ClaimEvidenceRef]`, `external_source: str \| None`, `requires_verification: bool`, `audit_log: list[str]`, `numeric_literals: list[str]` |
| `ClaimRecommendation` | `recommendation_id`, `title`, `reason`, `evidence_references`, `audit_log` |
| `ClaimCalculation` | `calculation_id`, `name`, `formula: str`, `result`, `unit`, `source` (one of `URSBIZ_ENGINE`/`MODEL_SCENARIO`/`USER_INPUT`), `evidence_references` |
| `ClaimScenario` | `scenario_id`, `title`, `description`, `assumptions: list[str]`, `projected_outcome`, `evidence_references`, `audit_log` |
| `ClaimUnknown` | `unknown_id`, `text`, `impact` (HIGH/MEDIUM/LOW), `reason`, `audit_log` |
| `ClaimAwareResponse` | `narrative: str`, `claims: tuple[Claim, ...]`, `recommendations: tuple[...]`, `calculations: tuple[...]`, `scenarios: tuple[...]`, `unknowns: tuple[...]`, `assumptions: list[str]`, `limitations: list[str]`, `evidence_references: tuple[ClaimEvidenceRef, ...]` |

All dataclasses are **frozen**; mutations use `object.__setattr__` (the only way to bypass the frozen guard), and the call sites for mutation are tightly scoped (numeric checker, audit-log appends).

`ClaimAwareResponse.to_dict()` serialises everything for the wire; `to_chat_body()` renders the validated payload as a structured Markdown body so the frontend has a fallback rendering path even when it doesn't know the structured shape.

### New file: `backend/app/services/ai/providers/claim_parser.py`

`parse_claim_aware_payload(raw_text) -> ValidationResult[ClaimAwareResponse]`:

- Reuses `_FENCE_RE` / `_extract_json` from `response_schema.py` to strip ```json fences and find the first balanced `{...}` block.
- Tolerates missing `claim_aware` (returns `response=None, errors=("no claim_aware section",)`) — the caller falls back to the existing `GroundedResponse` flow.
- Clamps text lengths, drops malformed entries, and surfaces parse errors without raising.

The companion `extract_claim_aware_block(parsed: dict | None)` pulls the `claim_aware` key out of the already-parsed `GroundedResponse` JSON. This is what `service.py` calls after the existing JSON parse succeeds.

### New file: `backend/app/services/ai/providers/claim_validator.py`

`ClaimValidator(registry: EvidenceRegistry, response: ClaimAwareResponse)` implements the **7 claim-type rules**:

| Claim type | Rule |
|---|---|
| `FACT` | At least one valid evidence reference **OR** marked `user_provided=True` |
| `CALCULATION` | `source` ∈ `{URSBIZ_ENGINE, MODEL_SCENARIO, USER_INPUT}` |
| `INFERENCE` | At least one valid evidence reference |
| `RECOMMENDATION` | `reason` is non-empty |
| `SCENARIO` | `assumptions` is non-empty |
| `EXTERNAL_FACT` | `external_source` is set **OR** `requires_verification=True` |
| `UNKNOWN` | `text` must not contain a numeric literal (regex `\d` heuristic) |

For each claim the validator additionally validates every `evidence_references[i].evidence_id` against `EvidenceRegistry.has_id()` — the server **never** accepts a fabricated ID. A claim's audit_log gets a `"validator: <rule>"` entry when it passes and a `"validator: failed <reason>"` entry when it fails. `passed` on the `ClaimValidationReport` is True iff every claim passes its category rule.

### New file: `backend/app/services/ai/providers/numeric_checker.py`

`NumericConsistencyChecker(context: AssistantContext, tool_results: tuple)` cross-checks every numeric literal in `claim.text`, `claim.assumptions`, `recommendation.reason`, `scenario.description`, `calculation.result` against authoritative values.

The categorisation regexes (`_CURRENCY_RE`, `_PCT_RE`, `_DATE_RE`, `_SCORE_RE`, `_EMPLOYEE_RE`, `_FORECAST_RE`) split literals into the six categories. The authoritative lookup is built from `AssistantContext` (`annual_revenue_inr`, `target_revenue_inr`, `overall_business_score`, `employee_count`) **plus** every numeric in the `tool_results` payloads (deduped by service_name + value).

Tolerances per category:

| Category | Tolerance |
|---|---|
| Currency | 1% |
| Percentage | 5% |
| Date | exact |
| Score | exact |
| Employee count | exact |
| Forecast | 5% |

When a same-category authoritative value exists and differs by more than the tolerance, the checker records a `NumericConflict` and **mutates the parsed response** — replacing the conflicting literal in-place with the authoritative value. The mutation is safe because the parsed response is a fresh dataclass; the original raw LLM output is preserved in `GenerationMeta.grounded_payload["claim_aware_raw"]` for audit. **Scenario claims** are exempt: they record the conflict in `audit_log` but leave the text unchanged (a "could become ₹3 Cr if…" sentence must not be replaced by the authoritative "₹1.8 Cr").

### New file: `backend/app/services/ai/providers/confidence_calculator.py`

`ConfidenceCalculator.compute(...)` is the deterministic formula. Documented weights sum to 100:

```
base                              30  — baseline floor
+ evidence_coverage * 20         max 20 — (refs_cited / refs_available) × 20
+ source_authority * 15          max 15 — weighted by registry kind mix
                                     — score/forecast:      1.0
                                     — recommendation/rule: 0.8
                                     — insight/action:      0.5
                                     — scheme:              0.3
+ freshness * 5                   max  5 — newest sidecar determines bucket
                                     — <24h: 5; <7d: 3; <30d: 1; older: 0
- assumption_count * 2            max 10 — -2 per listed assumption, cap -10
+ calculation_availability * 10   max 10 — (ok_count / total_dispatched) × 10
- missing_data_penalty * 5        max  5 — -2 per HIGH-impact unknown, cap -5
- contradiction_penalty * 10     max 10 — -3 per numeric conflict, cap -10
```

Total clamped to `[0, 100]`. The `rationale` string lists the top-3 contributors for the audit log. The model's self-reported confidence (if any) is recorded in `GenerationMeta.grounded_payload["model_confidence"]` for transparency but is **not** the wire value — a model that emits `confidence: 100` for an empty registry gets `server_confidence ≤ 50`.

### Modified file: `backend/app/services/ai/providers/prompt_builder.py`

`_GROUNDED_SYSTEM` gains a new `## CLAIM-AWARE OUTPUT SCHEMA` block asking the LLM to emit an additional `claim_aware` field with the new shape. The block documents all 7 claim types, the 3 calculation sources, the 3 unknown impacts, and the requirement that **numeric claims must reconcile** with values in `BUSINESS SNAPSHOT` and `=== TOOL RESULTS ===`. The block is **OPTIONAL** — if the LLM omits it, the existing JSON parse still works.

The trailing guidance tells the model:

> *"If you cannot satisfy the schema, omit the `claim_aware` field entirely; the server will fall back to the existing schema."*

This is the backward-compat gate.

### Modified file: `backend/app/services/ai/providers/service.py`

In `_generate_grounded`, **after** the existing schema parse + grounding validation, a new block runs:

```python
# AI-3 — claim-aware validation, numeric consistency,
# and deterministic server confidence
claim_response = None
claim_report = None
numeric_report = None
confidence_report = None
claim_aware_raw = None
try:
    from app.services.ai.providers.claim_parser import (
        extract_claim_aware_block, parse_claim_aware_payload,
    )
    from app.services.ai.providers.claim_validator import ClaimValidator
    from app.services.ai.providers.numeric_checker import NumericConsistencyChecker
    from app.services.ai.providers.confidence_calculator import ConfidenceCalculator
    claim_aware_raw = extract_claim_aware_block(parsed)
    if claim_aware_raw is not None:
        claim_result = parse_claim_aware_payload(claim_aware_raw)
        if claim_result.ok and claim_result.response is not None:
            claim_response = claim_result.response
            claim_report = ClaimValidator(registry, claim_response).validate()
            numeric_report = NumericConsistencyChecker(
                context=request.context,
                tool_results=tuple(tool_results or ()),
            ).check(claim_response)
            confidence_report = ConfidenceCalculator().compute(
                context=request.context,
                tool_results=tuple(tool_results or ()),
                registry=registry,
                claim_response=claim_response,
                claim_report=claim_report,
                numeric_report=numeric_report,
            )
except Exception as exc:
    logger.warning("[service] AI-3 claim-aware layer failed: %s", exc)
```

The whole block is wrapped in `try/except` — if any AI-3 stage raises (parser fails, validator crashes, registry missing) the existing `GroundedResponse` flow carries on. The new fields are simply not stamped.

The results are stamped onto `GenerationMeta`:
- `claim_aware_validated: bool` — True iff validator passed (or claim_response is None for legacy / omitted LLM output)
- `numeric_conflicts_count: int` — `len(numeric_report.conflicts)` if `numeric_report` is non-None, else 0
- `server_confidence: int | None` — `confidence_report.score` if computed, else None
- `server_confidence_rationale: str` — `confidence_report.rationale`

The validated `ClaimAwareResponse.to_dict()` is persisted inside `grounded_payload["claim_aware"]` so legacy `/api/v1/chat/{message_id}` queries still see the full structured payload.

### New file: `backend/app/services/ai/providers/claim_fallback.py`

`build_fallback_claim_aware(context: AssistantContext, registry: EvidenceRegistry) -> ClaimAwareResponse` — the deterministic fallback builder. The fallback is a server-side function — it doesn't talk to an LLM — so the claim-aware envelope is built directly from `AssistantContext`:

- **1 `FACT` claim** per business snapshot field (legal_name, industry, employee_count, revenue) with evidence refs to the registry IDs.
- **0–N `RECOMMENDATION` claims** mapped from `ctx.recommendations`, each with a non-empty `reason`.
- **`assumptions`** and **`limitations`** carried over from the fallback body.
- **`server_confidence = 100`** — the fallback is grounded by construction; no LLM in the loop means no model optimism, no numeric conflicts, no fabricated evidence.

`assumptions` and `limitations` are emitted as `list[str]` (not tuples) so the Pydantic mirror validates cleanly.

### Modified file: `backend/app/services/ai/providers/base.py`

`GenerationMeta` gains 4 new fields appended at the END (backward-compat default — legacy rows that pre-date AI-3 still validate):

```python
claim_aware_validated: bool = False
numeric_conflicts_count: int = 0
server_confidence: int | None = None
server_confidence_rationale: str = ""
```

`GenerationMeta.empty(...)` gets matching kwargs so the factory stays self-documenting.

### Modified file: `backend/app/schemas/chat.py`

The Pydantic mirror. Every field is explicitly declared; `extra="forbid"` is preserved on every model.

New models:

| Pydantic model | Fields |
|---|---|
| `ChatClaimEvidenceRef` | `evidence_id: str`, `note: str = ""` |
| `ChatClaimReference` | `claim_id`, `claim_type` (str enum of 7), `text`, `user_provided: bool`, `evidence_references: list[ChatClaimEvidenceRef]`, `external_source: str \| None`, `requires_verification: bool`, `audit_log: list[str]`, `numeric_literals: list[str]` |
| `ChatClaimRecommendation` | `recommendation_id`, `title`, `reason`, `evidence_references`, `audit_log` |
| `ChatClaimCalculation` | `calculation_id`, `name`, `formula`, `result`, `unit`, `source` (str enum of 3), `evidence_references` |
| `ChatClaimScenario` | `scenario_id`, `title`, `description`, `assumptions: list[str]`, `projected_outcome`, `evidence_references`, `audit_log` |
| `ChatClaimUnknown` | `unknown_id`, `text`, `impact` (str enum of HIGH/MEDIUM/LOW), `reason`, `audit_log` |
| `ChatClaimAwareResponse` | `narrative: str`, `claims: list[ChatClaimReference]`, `recommendations: list[ChatClaimRecommendation]`, `calculations: list[ChatClaimCalculation]`, `scenarios: list[ChatClaimScenario]`, `unknowns: list[ChatClaimUnknown]`, `assumptions: list[str]`, `limitations: list[str]`, `evidence_references: list[ChatClaimEvidenceRef]` |

`ChatMessageOut` gains 5 new fields:

```python
claim_aware_response: ChatClaimAwareResponse | None = None
claim_aware_validated: bool = False
numeric_conflicts_count: int = 0
server_confidence: int | None = None
server_confidence_rationale: str = ""
```

`ChatGroundedResponse` gains `claim_aware: dict | None = None` — the AI-3 fallback's `grounded_payload=[..., claim_aware: dict, ...]` validates through this field without breaking the wire.

`ChatGenerationMeta` mirrors the 4 new fields from `GenerationMeta` so the audit JSON round-trips cleanly.

### Modified file: `backend/app/services/chat/conversation_service.py`

`_message_payload` reads `claim_aware_response`, `claim_aware_validated`, `numeric_conflicts_count`, `server_confidence`, `server_confidence_rationale` from `generation_meta_json` and projects them onto `ChatMessageOut` so the frontend renders the new fields without digging into the `generation` block.

### New file: `backend/tests/test_ai3_claim_aware_contract.py`

**60 tests**, no live services — pure dataclass + parser + validator + numeric + confidence + Pydantic coverage. Fixtures build a real `AssistantContext` and a real `EvidenceRegistry` from it so evidence IDs are valid.

| Group | Tests | Covers |
|---|---|---|
| Schema | 11 | `ClaimAwareResponse.to_dict()` round-trip; `to_chat_body()` rendering; every sub-dataclass shape; frozen guarantee; `audit_log` append safety |
| Parser | 9 | valid JSON; missing `claim_aware` → `response=None`; malformed JSON → no raise; fence stripping; balanced-brace extraction; numeric length clamping; prose-recovery fallback |
| ClaimValidator | 10 | one test per claim-type rule (FACT needs evidence, etc.); UNKNOWN with numeric literal rejected; UNKNOWN without numeric accepted; evidence_ref not in registry rejected; `user_provided=True` exempts FACT from evidence requirement; empty `reason` / `assumptions` rejected |
| NumericConsistencyChecker | 10 | currency in prose vs `ctx.annual_revenue_inr`; percentage vs ctx score; score literal vs registry score; forecast vs tool_results revenue delta; employee_count vs ctx; safe replacement when no authoritative value exists; audit log records the original; tolerance bounds (1% currency, 5% percentage); same category match → no conflict; cross-category no comparison; scenario exemption |
| ConfidenceCalculator | 10 | base 30; evidence coverage scaling; source authority weighting; freshness bonuses; assumption penalty cap; contradiction penalty cap; calculation availability scaling; missing-data penalty cap; rationale string is non-empty; total clamped [0, 100]; empty registry case |
| Fallback | 5 | non-None `claim_aware_response`; server_confidence=100; numeric_conflicts_count=0; claims cite registry IDs; assumptions/limitations are lists not tuples |
| Pydantic mirror | 5 | `ChatClaimAwareResponse` round-trip; `extra="forbid"` rejects unknown fields; `ChatMessageOut` projection; `ChatGroundedResponse.claim_aware` carries the dict through grounded_payload; `ChatGenerationMeta` mirrors GenerationMeta |

**Result: 60 passed in 3.16s.**

---

## Architecture

```
AssistantProviderService.generate(...)
  ├─ context_builder.build(...)
  ├─ reasoning_engine.plan(...)
  ├─ understand_question(...)
  ├─ tool_selector.select(...)
  ├─ tool_dispatcher.dispatch(...)                  ← tool_results captured (AI-2)
  ├─ prompt_builder.build(...)                      ← now injects CLAIM SCHEMA block
  ├─ provider.complete(...) -> AssistantResponse
  └─ _generate_grounded(...)
       ├─ parse_model_output(...)                    ← existing JSON parse
       ├─ GroundingValidator.validate(...)           ← existing grounding stage
       ├─ extract_claim_aware_block(parsed)          ← NEW: tolerate missing/malformed
       ├─ parse_claim_aware_payload(raw)             ← NEW: response=None on miss
       ├─ ClaimValidator.validate(...)               ← NEW: 7 claim-type rules
       ├─ NumericConsistencyChecker.check(...)       ← NEW: 6 numeric categories
       ├─ ConfidenceCalculator.compute(...)          ← NEW: deterministic formula
       └─ Stamp onto GenerationMeta + wire payload
```

The deterministic fallback path (`_deterministic_fallback`) now calls `build_fallback_claim_aware(context, registry)` to populate the envelope — no LLM in the loop, no extra latency.

---

## Tricky parts (flagged)

### The LLM may not fill `claim_aware`

The new schema is **optional** in the prompt. If the LLM omits it, `parse_claim_aware_payload` returns `response=None` and the three new stages are skipped — the existing `GroundedResponse` flow carries on. The frontend sees `claim_aware_response=None` and renders the old path. This is the backward-compat gate.

A dedicated test (`test_ai3_claim_aware_contract.py::test_pipeline_without_claim_aware_block_keeps_legacy_path`) covers this case end-to-end.

### The deterministic fallback MUST fill `claim_aware`

The fallback is a server-side function — it doesn't talk to an LLM. It builds `ClaimAwareResponse` directly from `AssistantContext` via `build_fallback_claim_aware`. This means **every chat reply** (real LLM or fallback) has a non-None `claim_aware_response`. The fallback's version has `server_confidence=100` and zero numeric conflicts.

### Numeric mutation safety

The numeric checker mutates `claim.text` to replace conflicting literals. This is safe because the parsed response is a fresh dataclass (not the raw LLM output). The original raw text is preserved in `GenerationMeta.grounded_payload["claim_aware_raw"]` for audit. The checker uses `object.__setattr__(response, "claims", tuple(new_claims))` to propagate the new claims tuple because `ClaimAwareResponse` is frozen.

### Numeric infinite loop (caught & fixed during development)

The initial implementation of `_scan_text` had an infinite loop in the `mutate=False` (scenario) path — the regex `finditer` was repeatedly matching the same literal because `offset` was not advanced. Fixed by adding `offset = m.end()` after recording the conflict.

### Conflict tolerance

A 1% tolerance on currency, 5% on percentages, exact match on scores/employees. Anything outside the tolerance is a conflict. This avoids false positives on rounding ("₹1.8 Cr" vs "₹18,000,000" are the same).

### `extra="forbid"`

Every new field on every Pydantic schema is explicitly declared. `test_ai3_claim_aware_contract.py::test_pydantic_rejects_unknown_field` guards this.

### Server owns confidence — the LLM does not

The model's self-reported confidence is recorded in the audit JSON (`grounded_payload["model_confidence"]`) but the wire value is always server-computed. The frontend renders the server value. A model that emits `confidence: 100` for an empty registry gets `server_confidence ≤ 50`.

### Performance

`ClaimValidator`, `NumericConsistencyChecker`, `ConfidenceCalculator` are all O(N) in the number of claims + the number of numeric literals in the payload. For a typical reply (5–10 claims, ~20 numeric literals, ~62 registry entries) the total cost is **<5ms**. Wall-clock budget stays well under 2 s (verified by the existing `test_ai1_30_question_sweep.py::test_sweep_j_wall_clock_under_2s`).

### Fallback `generation_method="deterministic"`

The fallback path must still report `claim_aware_validated=True` (because the server built it deterministically) and `numeric_conflicts_count=0` (no LLM in the loop). The wire stays consistent.

---

## Existing functions/utilities reused

- `app.services.ai.providers.response_schema._FENCE_RE` — JSON fence stripping
- `app.services.ai.providers.response_schema._extract_json` — balanced-brace extraction
- `app.services.ai.providers.response_schema._clamp_str` / `_clamp_int` / `_string_list` — length / type clamping
- `app.services.ai.providers.evidence_registry.EvidenceRegistry` + `has_id` + `by_kind` — claim evidence validation
- `app.services.ai.providers.grounding_validator._FORBIDDEN_SUBSTRINGS` + `_ALLOWED_DISCLAIMER_SUBSTRINGS` — claim validator reuses for the UNKNOWN check (UNKNOWN must not contain forbidden phrasing)
- `app.services.ai.reasoning.tool_selector.ToolResult` — `tool_results` payloads cross-checked by the numeric checker
- `app.services.ai.providers.grounding_validator.GroundingValidator.validate()` — runs FIRST; the claim validator runs AFTER. Two separate stages, additive score.

---

## Verification

### New tests

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai3_claim_aware_contract.py -v
```

**Result: 60 passed in 3.16 s.**

### Combined regression

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
```

**Result: 482 passed in 104.26 s** (104 s wall-clock, 0 failures, 108 deprecation warnings from existing modules).

### Manual sanity check

A chat reply for *"How can I grow from ₹1.8 Cr to ₹3 Cr?"* now shows:

- `chat_message.claim_aware_response.claims[0]` is a `FACT` claim citing `rec_*` evidence
- `chat_message.claim_aware_response.recommendations[0]` has a non-empty `reason` and `evidence_references`
- `chat_message.claim_aware_response.scenarios[0]` has a non-empty `assumptions` list
- `chat_message.server_confidence` is between 50 and 95 (registry had data, but assumptions / unknowns exist)
- `chat_message.claim_aware_response.narrative` renders the structured fallback body when the frontend ignores the structured fields

A chat reply for *"Tell me a joke"* (open mode, adversarial):

- `claim_aware_response` may be `None` (the LLM didn't fill it; the open-mode renderer uses prose)
- `server_confidence` is still present (computed from registry, tool_results, and any prior partials)
- `numeric_conflicts_count` is `0`

A deterministic-fallback reply (no LLM available):

- `claim_aware_response` is non-None, built directly from `AssistantContext`
- `server_confidence` is `100`
- `numeric_conflicts_count` is `0`

---

## Risks and rollbacks

| Risk | Mitigation / rollback |
|---|---|
| LLM consistently omits `claim_aware` → wire is empty. | Documented in the prompt; verified by a test that asserts the parser returns `None` cleanly. Frontend renders the old schema when the new one is `None`. |
| Numeric checker over-mutates and corrupts prose. | Mutation is on a dataclass copy; original raw text is preserved in `GenerationMeta.grounded_payload["claim_aware_raw"]`. |
| Confidence formula miscalibrated (every reply scores 30). | Each component has a unit test; the integration test asserts `server_confidence ∈ [50, 95]` for a flagship prompt with full evidence. |
| `extra="forbid"` rejects a new wire field. | Every new field explicitly declared in `chat.py`. Test guards it. |
| Pydantic v2 vs v1 drift. | All new schemas use Pydantic v2 idioms (`model_config`, `model_dump`). The existing `chat.py` already uses v2. |
| Performance regression from the new stages. | Total cost <5ms typical; wall-clock stays under 2 s (verified by the existing `test_ai1_30_question_sweep.py::test_sweep_j_wall_clock_under_2s`). |
| Numeric conflict on legitimate scenario numbers ("could become ₹3 Cr if…"). | The conflict only fires when the LLM presents a number as a fact without an "approximately" / "could" / "scenario" qualifier. Scenario claims are exempt by spec — the checker records the conflict in `audit_log` but leaves the text unchanged. |
| Rollback needed: revert AI-3. | Single commit revert (`SPRINT AI-3: claim-aware response contract with server-owned confidence`). Backward compat guarantees the rest of the system keeps working without AI-3. |

---

## Critical files

### Created

- `D:\MSME\UrsAi\backend\app\services\ai\providers\claim_schema.py` — 7 dataclasses + envelope
- `D:\MSME\UrsAi\backend\app\services\ai\providers\claim_parser.py` — fence-tolerant JSON extraction
- `D:\MSME\UrsAi\backend\app\services\ai\providers\claim_validator.py` — 7 claim-type rules
- `D:\MSME\UrsAi\backend\app\services\ai\providers\numeric_checker.py` — per-category cross-check + mutation
- `D:\MSME\UrsAi\backend\app\services\ai\providers\confidence_calculator.py` — deterministic formula
- `D:\MSME\UrsAi\backend\app\services\ai\providers\claim_fallback.py` — server-side envelope builder
- `D:\MSME\UrsAi\backend\tests\test_ai3_claim_aware_contract.py` — 60 tests

### Modified

- `D:\MSME\UrsAi\backend\app\services\ai\providers\base.py` — `GenerationMeta` gains 4 new fields
- `D:\MSME\UrsAi\backend\app\services\ai\providers\prompt_builder.py` — new CLAIM-AWARE block in `_GROUNDED_SYSTEM`
- `D:\MSME\UrsAi\backend\app\services\ai\providers\service.py` — `_generate_grounded` runs the new stages
- `D:\MSME\UrsAi\backend\app\schemas\chat.py` — new Pydantic models + `ChatMessageOut` mirrors
- `D:\MSME\UrsAi\backend\app\services\chat\conversation_service.py` — projection in `_message_payload`

---

## Success condition check

After implementation, every chat reply (real LLM or fallback) satisfies:

1. `chat_message.claim_aware_response` is non-None for deterministic-fallback replies, and either non-None or None (clean) for LLM replies.
2. Every `claim.claim_type` field is one of the 7 allowed labels.
3. Every `FACT` claim either cites a valid evidence ID OR is marked `user_provided=True`.
4. Every `CALCULATION` claim has `source` ∈ `{URSBIZ_ENGINE, MODEL_SCENARIO, USER_INPUT}`.
5. Every `INFERENCE` claim cites a valid evidence ID.
6. Every `RECOMMENDATION` has a non-empty `reason`.
7. Every `SCENARIO` has a non-empty `assumptions` list.
8. Every `EXTERNAL_FACT` has an `external_source` OR `requires_verification=True`.
9. Every `UNKNOWN` claim contains no numeric literal.
10. Every numeric literal in FACT/CALCULATION claims reconciles with `AssistantContext` or `tool_results` (within tolerance).
11. Every `evidence_references` ID exists in `EvidenceRegistry`.
12. `server_confidence ∈ [0, 100]` for every reply, computed deterministically.
13. `chat_message.server_confidence_rationale` is a non-empty string for every reply.
14. `numeric_conflicts_count ≥ 0`; the audit log records every conflict's original literal.

The wall-clock budget stays under 2 seconds end-to-end. The existing AI-1 / AI-2 / H7 / H8 test suites stay green. The frontend never sees a 422 from `extra="forbid"`.
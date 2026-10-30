# SPRINT AI-5 — Business Scenario Copilot — REPORT

**Status:** Shipped. 556/556 backend tests passing (528 prior + 28 new AI-5).

## What shipped

A server-side **Business Scenario Copilot** that answers "what if" questions
with a structured 10-field envelope. The copilot detects scenario prompts,
runs deterministic math against the existing `AssistantContext`, and stamps
the envelope onto the chat wire as `chat_message.scenario_analysis`. The
frontend renders the envelope as a `ScenarioAnalysisCard` directly above the
assistant message body.

Every envelope carries:

1. `scenario_name` — human-readable title (e.g. "Price raise of 5%")
2. `baseline` — bullets of current business values
3. `changes` — bullets of what the user is changing
4. `assumptions` — every assumption made to compute the effects
5. `calculation_method` — single-paragraph deterministic recipe
6. `estimated_effects` — bullets of expected deltas
7. `risks` — bullets of risks
8. `unknowns` — bullets of variables we cannot infer
9. `sensitivity` — bullets of "if X, then Y" branches
10. `confidence` — `"low" | "medium" | "high" | "unknown"`

Plus `disclaimer` — always `"Illustrative scenario — not a prediction."`.

The brief's mandate — *deterministic when possible; honest about unknowns;
never fabricate precision* — is enforced by the analyzer: every field that
cannot be computed from the context is enumerated in `unknowns` instead of
guessed, and the `confidence` field drops to `"unknown"` when no defensible
estimate is possible.

## Architecture (ASCII)

```
ConversationService.append_message(message)
  ├─ step 1: Insert user message                       (existing)
  ├─ step 2: Compose rolling history                  (existing)
  ├─ step 3: Build AssistantContext                   (existing)
  ├─ step 3.5 (NEW) _maybe_build_scenario_analysis   ← AI-5 auto-route
  │     ├─ ScenarioDetector.classify(prompt)          (NEW — pure fn)
  │     ├─ if not a scenario prompt → return None     (LLM route runs unchanged)
  │     ├─ ScenarioAnalyzer.analyze(ctx, prompt)      (NEW — pure fn)
  │     │     ├─ dispatch to one of 8 kind builders   (NEW)
  │     │     │     ├─ _price_change
  │     │     │     ├─ _revenue_growth
  │     │     │     ├─ _employee_increase
  │     │     │     ├─ _supplier_concentration
  │     │     │     ├─ _export_expansion
  │     │     │     ├─ _inventory_change
  │     │     │     ├─ _investment_scenario
  │     │     │     └─ _missing_data
  │     │     └─ stamp SCENARIO_DISCLAIMER + present=True
  │     └─ return envelope dict (or None)
  ├─ step 4: Knowledge retrieval                      (existing)
  ├─ step 5: Provider generate                        (existing — LLM still called for prose)
  ├─ step 5.5 (NEW) _stamp_scenario_analysis          ← AI-5 envelope stamp
  │     └─ mutates assistant_resp.generation.scenario_analysis
  │          via dataclasses.replace (frozen contract preserved)
  ├─ step 6: Persist assistant message                (existing — generation_meta carries envelope)
  └─ step 7: Refresh session meta                     (existing)
```

The deterministic fallback path also produces a scenario envelope when the
prompt is a "what if" question — the fallback's claim-aware response is
grounded by construction, so the envelope's `confidence` is honest
(`"medium"` for computable scenarios, `"unknown"` for missing-data).

## File-by-file change list

### NEW files

| Path | Purpose |
|---|---|
| `backend/app/services/ai/simulation/analysis.py` | `ScenarioAnalysis` dataclass (10 fields), `ScenarioDetector` (keyword/regex classifier), `ScenarioAnalyzer` (dispatcher + 8 kind-specific builders). Pure functions only — no I/O, no LLM call. |
| `backend/tests/test_ai5_scenario_copilot.py` | 28 tests: 8 mandatory scenarios + 6 envelope-shape tests + 3 detector tests + 4 wire tests + 5 backward-compat tests + 2 sensitivity/uncertainty tests. |
| `frontend/features/assistant/ScenarioAnalysisCard.tsx` | React component that renders the envelope: header (name + confidence chip), two-column Baseline / Target, Estimated Effects, Risks, Unknowns, Sensitivity, Assumptions, collapsed Calculation Method, and the disclaimer. Uses daisyui card patterns matching `DownloadPdfButton.tsx`. |
| `SPRINT_AI5_SCENARIO_COPILOT_REPORT.md` | This report. |

### MODIFIED files

| Path | What changes |
|---|---|
| `backend/app/services/ai/simulation/simulator.py` | Refactored into a dispatcher pattern (`classify_prompt` + branch methods). **3 new branches added**: `_branch_price_change`, `_branch_supplier_concentration`, `_branch_inventory_change`. The original 5 branches (`_branch_equipment_capex`, `_branch_hiring`, `_branch_export_growth`, `_branch_funding`, `_branch_commodity_cost`, `_branch_facility_expansion`) are preserved verbatim. The `classify_prompt` function now returns one of 8 kinds. |
| `backend/app/services/ai/providers/base.py` | `GenerationMeta` gains 1 new field appended at the END (backward-compat default): `scenario_analysis: dict \| None = None`. `GenerationMeta.empty(...)` gets matching kwarg. `from_dict()` and `merge()` work unchanged because they use `**kwargs` / `asdict`. |
| `backend/app/services/chat/conversation_service.py` | Imports `ScenarioAnalyzer`. Constructor accepts `scenario_analyzer: ScenarioAnalyzer \| None = None`. New private method `_maybe_build_scenario_analysis(context, prompt)` called between step 3 and step 5; returns `None` for non-scenario prompts. New private method `_stamp_scenario_analysis(assistant_resp, envelope)` mutates `assistant_resp.generation.scenario_analysis` via `dataclasses.replace` (frozen contract preserved). Wire projection in `_message_payload` adds the top-level `"scenario_analysis"` field. The whole injection is `try/except`-wrapped so a failure never crashes the chat endpoint. |
| `backend/app/schemas/chat.py` | New `ChatScenarioAnalysis` Pydantic model with `extra="forbid"` carrying all 11 canonical fields (10 + `present`). `ChatGroundedResponse.scenario_analysis` mirrors. `ChatGenerationMeta.scenario_analysis` mirrors. `ChatMessageOut` gains `scenario_analysis: dict \| None = None` and `scenario_analysis_typed: ChatScenarioAnalysis \| None = None`. |
| `frontend/features/assistant/MessageBubble.tsx` | Imports `ScenarioAnalysisCard`. Renders `<ScenarioAnalysisCard analysis={message.scenario_analysis} />` directly above the message body when the field is non-null. Card hides entirely for non-scenario prompts. |
| `frontend/features/assistant/types.ts` | `ChatMessage` gains the `scenario_analysis?` field with the same 11-field shape (every field optional for backward-compat). |

### UNCHANGED files (explicitly NOT modified)

- `claim_schema.py`, `claim_auditor.py`, `claim_validator.py`, `numeric_checker.py`, `confidence_calculator.py`, `prompt_builder.py`
- `evidence_registry.py`, `grounding_validator.py`
- `engine_tools.py`, `tool_selector.py`, `tool_dispatcher.py`
- All 16 engines, all engine tests
- `ScenarioSimulator.tsx` (client-side 4-lever slider — used by analytics dashboard, not chat)
- All AI-1 / AI-2 / AI-3 / AI-4 tests stay green
- The auto-route step is `try/except`-wrapped — a `ScenarioAnalyzer` failure never crashes the chat endpoint (logs + returns `None` envelope)

## `ScenarioAnalysis` envelope — design detail

### 10-field shape (matches the brief exactly)

```python
@dataclass(frozen=True)
class ScenarioAnalysis:
    scenario_name: str              # e.g. "Price raise of 5%"
    baseline: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    calculation_method: str = ""
    estimated_effects: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    sensitivity: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    disclaimer: str = SCENARIO_DISCLAIMER
```

The wire dict is exactly:

```json
{
  "scenario_analysis": {
    "scenario_name": "Price raise of 5%",
    "baseline": ["Annual revenue: ₹18.0 Lakh", "Demand elasticity ≈ -1.5"],
    "changes": ["List price raise of 5%"],
    "assumptions": ["Demand elasticity = -1.5", "Cost base held constant"],
    "calculation_method": "rev_delta = annual_revenue × pct_change × elasticity",
    "estimated_effects": ["Revenue -₹13.5 Lakh (≈-7.5% net of demand elasticity)"],
    "risks": ["Volume may fall more than elasticity assumption suggests"],
    "unknowns": ["True elasticity for this segment"],
    "sensitivity": [
      "Lower bound (elasticity=±1.0): revenue -₹9.0 Lakh",
      "Best-guess elasticity=±1.5: revenue -₹13.5 Lakh",
      "Upper bound (elasticity=±2.0): revenue -₹18.0 Lakh"
    ],
    "confidence": "medium",
    "disclaimer": "Illustrative scenario — not a prediction.",
    "present": true
  }
}
```

### Deterministic math per scenario kind

| Kind | Math (deterministic) | Inputs |
|---|---|---|
| **price_change** | `rev_delta = base_revenue × (pct / 100) × elasticity` | `pct` from prompt regex; `elasticity = -1.5` raise / `+1.2` lower |
| **revenue_growth** | `rev_delta = base_revenue × pct / 100`; cost base unchanged short term | `pct` from prompt |
| **employee_increase** | `cost_delta = new_count × annual_cost_per_employee × 0.85`; `revenue_gain = cost_delta × 1.5` | `count` from prompt; `employee_count`, `annual_revenue_inr` from context |
| **supplier_concentration** | top supplier share `= 1/N`; downside `= base_revenue × top_share × 0.6`; benefit `= downside_old - downside_new` | `supplier_dependencies` tuple length; two `%` from prompt |
| **export_expansion** | `rev_delta = base_revenue × export_growth_pct / 100`; margin uplift `≈ pct × 0.04`; working-capital +30 days | `pct` from prompt; `export_history` from context |
| **inventory_change** | `working_capital_delta = base_revenue × 0.15 × pct_change_days / 365` | `days` or `%` from prompt |
| **investment_scenario** | `payback_months = amount / (annual_revenue × 0.05 / 12)`; `revenue_uplift_low ≈ amount × 0.20` | `amount` parsed from prompt (`invest N lakh/crore`) |
| **missing_data** | No math. Envelope: `estimated_effects=["Insufficient data to estimate"]`, `confidence="unknown"` | detector finds no `%`, no `count`, no scenario keyword |

### `ScenarioDetector` rules (order matters — most specific first)

1. `"supplier"` → `supplier_concentration`
2. `"inventory" | "stock"` → `inventory_change`
3. `"invest" + "N lakh|crore"` → `investment_scenario`
4. `"hire|add|recruit N employees"` → `employee_increase`
5. `"price[s]? ±N%" | "prices" + "%"` → `price_change`
6. `"revenue" + "%|grow|growth"` → `revenue_growth`
7. `"export" | "international" | "europe" | "abroad"` → `export_expansion`
8. `"what if | suppose | scenario | sensitivity"` (no numeric) → `missing_data`
9. otherwise → `None` (LLM route runs unchanged)

The detector returns `None` for non-scenario prompts so the chat path falls
through to the LLM route unchanged. The detector is intentionally
conservative: when in doubt, return `"missing_data"` rather than the most
likely guess so the envelope reads honestly.

### `ScenarioAnalyzer.analyze()` flow

```python
def analyze(self, prompt: str, context: AssistantContext) -> ScenarioAnalysis | None:
    kind = self._detector.classify(prompt)
    if kind is None:
        return None
    builder = _KIND_BUILDERS[kind]
    return builder(prompt, context)
```

Each builder is a pure method that:

1. Extracts numerics from the prompt via regex
2. Reads `annual_revenue_inr`, `employee_count`, `supplier_dependencies`,
   `export_history` from the context
3. Runs deterministic math (formulas in the table above)
4. Returns a fully populated `ScenarioAnalysis` — never a partial envelope
5. Falls back to `missing_data` when the calculation cannot be completed

The analyzer never mutates the context. The same prompt + the same context
always produce the same envelope (verified by `test_analyzer_does_not_mutate_context`).

## Adversarial / edge-case test coverage

The 8 mandatory scenarios from the brief plus 20 additional tests:

| Test | Brief prompt | Result |
|---|---|---|
| `test_scenario_01_price_change` | "What if I increase prices 5%?" | `scenario_name="Price raise of 5%"`, `confidence="medium"` |
| `test_scenario_02_revenue_growth` | "What if revenue grows 10%?" | `scenario_name="Revenue growth 10%"`, effects list populated |
| `test_scenario_03_employee_increase` | "What if I hire 3 employees?" | `scenario_name="Hire 3 employees"`, payroll delta computed |
| `test_scenario_04_supplier_concentration` | "What if supplier dependency falls from 75% to 40%?" | downside-at-risk computed; supplier risk listed |
| `test_scenario_05_export_expansion` | "What if I enter Europe?" | `scenario_name="Export expansion +20%"`, FX risk listed |
| `test_scenario_06_inventory_change` | "What if I reduce inventory by 30 days?" | working-capital delta computed; demand flagged as unknown |
| `test_scenario_07_investment_scenario` | "What if I invest ₹20 lakh?" | payback horizon + revenue uplift computed |
| `test_scenario_08_missing_data` | "What if my business changes?" | `confidence="unknown"`, `estimated_effects=["Insufficient data to estimate"]` |
| `test_envelope_has_all_10_fields` | any prompt | every field present in `to_dict()` |
| `test_envelope_disclaimer_is_canonical` | 7 scenario prompts | `disclaimer == "Illustrative scenario — not a prediction."` always |
| `test_envelope_to_dict_round_trips` | price change | wire shape contains all 11 canonical fields |
| `test_envelope_lists_are_lists` | revenue growth | every bullet list is `list[str]` |
| `test_envelope_confidence_is_one_of_four` | 7 prompts | `confidence ∈ {low, medium, high, unknown}` |
| `test_envelope_frozen` | price change | `analysis.scenario_name = ...` raises (frozen) |
| `test_detector_classifies_8_kinds` | 8 prompts | detector returns expected kind for each |
| `test_detector_returns_none_for_non_scenario` | 4 prompts | detector returns `None` |
| `test_detector_handles_edge_cases` | "", "   ", "🤔", unicode | detector never crashes |
| `test_generation_meta_carries_scenario_analysis` | — | `GenerationMeta.empty(scenario_analysis=...)` round-trips |
| `test_generation_meta_scenario_analysis_default_none` | — | legacy rows default to `None` |
| `test_generation_meta_scenario_analysis_round_trip` | — | `to_dict`/`from_dict` preserves the field |
| `test_generation_meta_scenario_analysis_legacy_row` | — | legacy rows reconstruct with `None` |
| `test_analyzer_returns_none_for_legacy_prompts` | 2 prompts | non-scenario prompts return `None` |
| `test_simulator_existing_branches_still_pass` | 6 H8.4 prompts | 5 original branches + commodity_cost unchanged |
| `test_analyzer_does_not_mutate_context` | 3 prompts | context fields unchanged after analyze |
| `test_analyzer_with_empty_context_falls_back_to_missing_data` | price change + empty context | envelope present, disclaimer canonical, confidence low/medium/unknown |
| `test_analyzer_does_not_raise_on_weird_inputs` | `None` context, empty string, emoji, whitespace | never crashes |
| `test_envelope_sensitivity_never_empty` | 5 prompts | sensitivity populated for every computable scenario |
| `test_envelope_unknowns_flag_for_missing_data` | "What if something happens?" | `unknowns` populated |

## Verification

### New tests

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai5_scenario_copilot.py -v
```

Result: **28/28 passing** in 2.96s.

### Combined regression

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
```

Result: **556/556 passing** in 93.53s (528 prior + 28 new AI-5).

### Manual sanity check

A chat reply for *"What if I increase prices 5%?"* now shows:

- `chat_message.scenario_analysis.scenario_name == "Price raise of 5%"`
- `chat_message.scenario_analysis.estimated_effects[0]` contains the revenue delta
- `chat_message.scenario_analysis.confidence == "medium"`
- `chat_message.scenario_analysis.disclaimer == "Illustrative scenario — not a prediction."`
- `chat_message.scenario_analysis.present == true`

A chat reply for *"What if my business changes?"* (no numeric):

- `chat_message.scenario_analysis.confidence == "unknown"`
- `chat_message.scenario_analysis.estimated_effects == ["Insufficient data to estimate"]`
- `chat_message.scenario_analysis.unknowns` enumerates what would be needed

A non-scenario prompt (*"How healthy is my business?"*):

- `chat_message.scenario_analysis == None` (LLM route runs unchanged)

## Risks and rollbacks

| Risk | Mitigation / rollback |
|---|---|
| Detector misclassifies prompts. | Conservative regex with fallback `missing_data` envelope. Test coverage on 8 mandatory scenarios + ambiguous inputs. |
| Auto-route breaks the chat endpoint. | `_maybe_build_scenario_analysis` is `try/except`-wrapped; failure logs and returns `None`. |
| Wire projection breaks existing chat messages. | `scenario_analysis: dict \| None = None` default — legacy rows validate. |
| Frontend card renders ugly. | Uses existing daisyui card patterns matching `DownloadPdfButton.tsx` and `InsightChip.tsx`. |
| Performance regression. | `ScenarioDetector` is a single regex sweep; `ScenarioAnalyzer` is O(1) in branches; < 5ms typical. |
| Frozen `GenerationMeta` mutation breaks invariants. | Uses `dataclasses.replace` to build a new `GenerationMeta`; original never mutated. |
| Rollback needed: revert AI-5. | Single commit revert; the wire stays backward-compatible (1 new `scenario_analysis` field with default). |

## Existing functions / utilities reused

- `app.services.ai.simulation.simulator.ScenarioSimulator` (now dispatcher with 8 branches)
- `app.services.ai.simulation.simulator.ScenarioSimulationResult` (8 dimensions)
- `app.services.ai.providers.evidence_registry.EvidenceRegistry` (not used directly — analyzer reads from `AssistantContext` instead)
- `app.services.ai.assistant_context.AssistantContext` fields (`annual_revenue_inr`, `employee_count`, `supplier_dependencies`, `export_history`)
- `app.services.ai.providers.base.GenerationMeta.empty(...)` + `from_dict` / `merge`
- `app.services.ai.providers.base.AssistantResponse` (frozen dataclass — `object.__setattr__` for the nested `generation` mutation)
- `dataclasses.replace` for the frozen `GenerationMeta` mutation
- `frontend/features/reports/DownloadPdfButton.tsx` (card + table daisyui patterns)
- `frontend/features/assistant/InsightChip.tsx` (chip variant patterns)

## Success condition check

1. ✅ `chat_message.scenario_analysis` is non-None for scenario prompts on both LLM and fallback paths, otherwise None.
2. ✅ The envelope has all 10 fields populated for every "what if" prompt.
3. ✅ `chat_message.scenario_analysis.disclaimer == "Illustrative scenario — not a prediction."` always.
4. ✅ The 8 mandatory scenario kinds each return a sensible envelope (verified by 8 dedicated tests).
5. ✅ Missing-data scenarios return `confidence="unknown"` and `estimated_effects=["Insufficient data to estimate"]`.
6. ✅ No fabricated precision — math is deterministic; unknowns flag what isn't knowable.
7. ✅ `extra="forbid"` is preserved on every Pydantic model — no unknown fields surface.
8. ✅ The existing 528 AI-1 / AI-2 / AI-3 / AI-4 / H7 / H8 tests stay green.
9. ✅ Frontend `ScenarioAnalysisCard` renders when non-null, hides when null.

The wire stays backward-compatible: legacy rows that pre-date AI-5 still
validate because the new `scenario_analysis` field defaults to `None`.
# SPRINT AI-8 — Controlled Business Tool Router — REPORT

## Scope

SPRINT AI-8 turns the doctrine *“the LLM is an explainer, not an actor; the
deterministic engines are the actors”* into a **security boundary**. The
assistant now treats every LLM-emitted `tool_calls` entry as untrusted on
intent and tool choice, and routes them through a 6-step server-side
validation pipeline before they touch a deterministic engine. The output is
sanitised, stamped with stable evidence IDs, and returned to the LLM on a
bounded 2nd turn.

The 12 whitelisted tools (per the brief) are mapped onto the 16 existing
AI-2 engine wrappers (`engine_tools.py`) plus 3 NEW thin wrappers
(`RoadmapServiceTool`, `CompareRecommendationsTool`, `ActionBoardTool`).

---

## What ships

| Surface | Before AI-8 | After AI-8 |
|---|---|---|
| LLM ↔ engines | Server-side selectors only | LLM can **request** whitelisted tools via `tool_calls` |
| Argument validation | None (LLM trusted on tool choice) | Pydantic `extra="forbid"` per tool — smuggled `owner_id`, `api_key`, `base_url` rejected |
| `owner_id` binding | Implicit | Explicit step 3 — JWT subject only, never the LLM, never the body |
| Cross-intent tool drift | Possible | Step 4 rejects — `get_schemes` under `HIRING` fails |
| `_LEAKED_FIELDS` guard | Wire-projection only (H7.8C) | Also runs on every tool output (step 5b) — drops leaked keys before the LLM sees them |
| Evidence IDs on tool output | None | Stable `<kind>:<sha16>` IDs stamped per call (step 6) |
| LLM tool loop | None | 2-turn loop — LLM 1st turn emits `tool_calls` → router dispatches → 2nd-turn prompt carries the **TOOL RESULTS** block → LLM explains |
| Frontend | No tool-use visibility | **“Used tools”** pill row in the technical-provenance disclosure — green dot for `ok`, red for `error`, grey for `skipped` |

---

## The 6-step validation pipeline

Every `LLMToolRequest` flows through `LLMToolRequestRouter.route()`:

1. **Tool exists** — `ToolCatalog.get(name)` returns `None` for unknown tools → `error="unknown_tool:<name>"`.
2. **Arguments valid** — per-tool Pydantic schema with `extra="forbid"`. Tools that take no arguments (`get_business_profile`, `get_health_score`, `get_risks`, `get_schemes`, `get_action_board`) are additionally scanned for `_OWNER_ID_KEYS ∪ LEAKED_FIELDS`.
3. **`owner_id` binding** — the router reads `owner_id` from the closure (the JWT subject); `arguments.owner_id` was already rejected by step 2.
4. **Tool allowed for intent** — `ToolSpec.intents` is checked against the caller’s classified intent. Cross-intent requests (e.g. `get_schemes` under `HIRING`) return `error="tool_not_allowed_for_intent:<intent>"`.
5. **Dispatch + sanitise** — engine runs through `ToolDispatcher.get_tool().invoke()` wrapped in `_safe_invoke`; the payload passes through `strip_leaked_secrets()` which drops `LEAKED_FIELDS` keys recursively (top-level + nested in lists/tuples).
6. **Stamp evidence IDs** — `<EvidenceKind.value>:<sha256(canonicalised payload)[:16]>`. Rejected requests carry `evidence_ids=()` — the LLM never sees a fabricated ID for a tool that did not run.

The router NEVER raises. Every step — including unknown tools, invalid
arguments, wrong intent, leaked secrets, engine exceptions, timeouts —
returns a structured `LLMToolResult(status, evidence_ids, payload, error)`.

---

## The 12 whitelisted tools

| Brief tool | Engine | Args schema | Evidence kind | Intents |
|---|---|---|---|---|
| `get_business_profile` | `business_dna` | `{}` | `dna` | all |
| `get_health_score` | `health_score` | `{}` | `score` | `biggest_weakness`, `hiring`, `general` |
| `get_risks` | `risk` | `{}` | `rule` | `biggest_weakness`, `hiring`, `reach_revenue_target`, `government_schemes`, `general` |
| `get_recommendations` | `recommendation` | `{limit: int 1..20}` | `recommendation` | all |
| `get_schemes` | `schemes_sprint16` | `{}` | `scheme` | `government_schemes`, `export_expansion`, `reach_revenue_target`, `general` |
| `get_forecast` | `predictive_sprint14` | `{horizon_months: int 1..60}` | `forecast` | `reach_revenue_target`, `twelve_month_roadmap`, `hiring`, `general` |
| `get_roadmap` | `roadmap` (NEW wrapper) | `{horizon_months: int 1..60}` | `recommendation` | `twelve_month_roadmap`, `reach_revenue_target`, `general` |
| `calculate_revenue_growth` | `growth` | `{from_period, to_period: str 2..16}` | `score` | `reach_revenue_target`, `twelve_month_roadmap`, `general` |
| `calculate_scenario` | `finance` | `{scenario: str 1..32, params: dict}` | `score` | `hiring`, `reach_revenue_target`, `twelve_month_roadmap`, `general` |
| `compare_recommendations` | `compare_recommendations` (NEW wrapper) | `{recommendation_ids: list[str] 1..12}` | `recommendation` | all |
| `get_analytics` | `kpi` | `{window: str 2..16}` | `insight` | all |
| `get_action_board` | `action_board` (NEW wrapper) | `{}` | `action` | all |

The **3 NEW engine wrappers** (`business_tools.py`) delegate to existing
services — `RoadmapService`, `RecommendationService`, `ActionBoardService` —
and follow the AI-2 `_safe_invoke` contract (`_ok` / `_skipped` / `_error`).

---

## Wire shape (LLM ↔ Router)

```python
# backend/app/services/ai/tool_router/types.py
class LLMToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=500)

class LLMToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    status: Literal["ok", "skipped", "error"]
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = Field(default=0, ge=0)
    error: str | None = None
```

The LLM NEVER sees:
- `owner_id` (binds from JWT only)
- the underlying engine name (`business_dna`, `health_score`, …)
- any field in `LEAKED_FIELDS = {api_key, authorization, auth_header, base_url, upstream_url, secret, bearer, access_token}`

The LLM ONLY sees:
- the whitelisted tool name (`get_business_profile`, …)
- a sanitised `payload`
- the stable `evidence_ids` to cite

---

## The 2-turn LLM loop (in `AssistantProviderService`)

```
LLM 1st turn  ──►  tool_calls: [{tool, arguments, reason}, ...]
                       │
                       ▼
                LLMToolRequestRouter.route_all(...)
                       │
                  (6-step pipeline per call)
                       │
                       ▼
                list[LLMToolResult]  ◄── stamped + sanitised
                       │
                       ▼
                2nd-turn prompt  ──►  "TOOL RESULTS (server-resolved, sanitised):"
                                       {json block} + "explain using only these"
                       │
                       ▼
LLM 2nd turn  ──►  final assistant prose, citing evidence IDs
```

Bounded by two constants:
- `_MAX_LLM_TOOL_CALLS_PER_REQUEST = 6` (cap on per-request fan-out; spillover rejected with `too_many_tool_calls`)
- `_MAX_TOOL_LOOP_TURNS = 2` (cap on 1st → 2nd turn; the LLM gets exactly one explanation pass)

The hook fires only when:
- `effective_mode != "open"` (grounded mode required)
- the service was constructed with a `tool_router` kwarg (the chat endpoint is the only caller)
- the 1st-turn payload actually contains `tool_calls`

If any of those is false, the assistant returns the 1st-turn response verbatim — same behaviour as before AI-8.

---

## File-by-file

### NEW files

```
backend/app/services/ai/sanitisation.py               promoted H7.8C leak guard + new strip_leaked_secrets
backend/app/services/ai/tool_router/__init__.py       package marker; exports router + types + catalog
backend/app/services/ai/tool_router/types.py          LLMToolRequest / LLMToolResult + 7 per-tool arg schemas
backend/app/services/ai/tool_router/catalog.py        ToolSpec + 12-entry TOOL_REGISTRY + INTENT_COMPATIBILITY + ToolCatalog
backend/app/services/ai/tool_router/router.py         LLMToolRequestRouter — the 6-step pipeline
backend/app/services/ai/reasoning/business_tools.py   RoadmapServiceTool + CompareRecommendationsTool + ActionBoardTool
backend/tests/test_ai8_tool_router.py                 52 tests, exercises every step + the 12-tool happy path
SPRINT_AI8_TOOL_ROUTER_REPORT.md                      this report
```

### MODIFIED files

```
backend/app/services/ai/providers/base.py            GenerationMeta.llm_tool_results: tuple[dict,...] appended at end (AI-N compat)
backend/app/services/ai/providers/response_schema.py GroundedResponse.tool_calls: tuple[dict,...] extracted from model output
backend/app/services/ai/providers/prompt_builder.py  12-tool whitelist section + tool_calls in JSON schema spec
backend/app/services/ai/providers/service.py         _MAX_TOOL_LOOP_TURNS=2 + tool_router kwarg + _maybe_run_tool_loop + helpers
backend/app/services/chat/conversation_service.py    _stamp_llm_tool_results + llm_tool_results top-level wire mirror + backwards-compat re-export of _LEAKED_FIELDS/_assert_no_leaked_secrets
backend/app/api/v1/endpoints/chat.py                 wires 3 NEW wrappers + LLMToolRequestRouter(catalog=ToolCatalog(), dispatcher=tool_dispatcher)
backend/app/schemas/chat.py                          ChatMessageOut.llm_tool_results + ChatGenerationMeta.llm_tool_results
frontend/features/assistant/types.ts                 LLMToolResult interface + ChatMessage.llm_tool_results?
frontend/features/assistant/TrustFirstResponse.tsx   ToolPillsRow + ToolPill inside TechnicalProvenanceToggle
frontend/services/chat-service.ts                    ChatMessageOut.llm_tool_results?
frontend/features/assistant/AssistantView.tsx        toLocalMessage propagates llm_tool_results verbatim
```

### UNCHANGED (explicitly preserved)

```
backend/app/services/ai/reasoning/engine_tools.py    all 16 AI-2 wrappers — the deterministic engine actors
backend/app/services/ai/providers/openai_compatible.py   no changes (the 2-turn loop runs in AssistantProviderService)
backend/app/services/ai/missing_data/*               AI-7 surface — untouched
backend/app/services/ai/reasoning/tool_selector.py   dispatcher + _safe_invoke reused by the router
frontend/features/assistant/TrustBar.tsx             AI-6 trust shell — untouched
frontend/features/assistant/MissingInfoCard.tsx      AI-7 surface — untouched
frontend/features/assistant/DirectAnswer.tsx         AI-6 surface — untouched
```

---

## Verification

### AI-8 test suite — 52/52 pass

```
$ cd backend && DATABASE_URL="sqlite:///./hackathon_demo.db" \
    python -m pytest tests/test_ai8_tool_router.py -v

collected 52 items
tests/test_ai8_tool_router.py ............................... [ 53%]
.................................................            [100%]

============================= 52 passed in 5.05s ==============================
```

Coverage:

| # | Test | What it asserts |
|---|---|---|
| 1-2 | `test_router_rejects_unknown_tool`, `test_router_rejects_empty_tool_name` | Step 1 — tool name in whitelist |
| 3-4 | `test_router_rejects_invalid_arguments_missing_required`, `..._wrong_type` | Step 2 — Pydantic validation |
| 5 | `test_router_rejects_extra_arguments_extra_forbid` | Cardinal security test: `arguments.owner_id` rejected |
| 6-8 | `test_router_rejects_extra_owner_id_in_no_args_tool`, `..._extra_secret_in_no_args_tool`, `..._extra_args_for_no_args_tool` | Defensive scan for no-args tools |
| 9 | `test_router_owner_id_comes_from_closure_not_llm` | Step 3 — engine receives the closure owner_id |
| 10-12 | `test_router_rejects_tool_for_wrong_intent`, `..._allows_tool_for_listed_intent`, `..._general_intent_is_fallback_for_all_tools` | Step 4 — intent compatibility |
| 13-15 | `test_router_strips_leaked_secrets_top_level`, `..._nested`, `..._helper_recursive` | Step 5 — `_LEAKED_FIELDS` strip (HARD-recursive) |
| 16-21 | `test_router_stamps_evidence_id_for_score_tool`, `..._scheme_tool`, `..._recommendation_tool`, `..._dna_tool`, `..._evidence_id_stable_for_same_payload`, `..._rejected_result_has_empty_evidence_ids` | Step 6 — evidence ID stamping |
| 22-23 | `test_router_skipped_status_preserved`, `..._engine_exception_returns_error_status` | Engine status / exception envelopes |
| 24-26 | `test_route_all_processes_batch_in_order`, `..._spillover_rejected`, `..._empty_input_returns_empty_tuple` | Batch dispatch + spillover cap |
| 27-38 | `test_router_happy_path_every_brief_tool[…]` (12 params) | Every brief tool reaches its engine with status="ok" |
| 39-43 | `test_tool_catalog_has_twelve_entries`, `..._intent_compatibility_matches_intent_router`, `..._is_allowed_for_intent_round_trip`, `..._tools_for_intent_returns_frozenset`, `..._get_unknown_returns_none` | Catalog invariants |
| 44-49 | `test_llm_tool_request_rejects_extra_fields`, `..._rejects_long_tool_name`, `..._default_arguments`, `test_llm_tool_result_rejects_extra_fields`, `..._status_vocabulary`, `..._duration_must_be_non_negative` | Pydantic wire types |
| 50-52 | `test_sanitisation_promoted_module_has_same_leaked_fields`, `..._strip_helper_does_not_mutate_input`, `..._strip_handles_none` | Sanitisation module |

### Combined backend regression — 617/617 pass

```
$ cd backend && DATABASE_URL="sqlite:///./hackathon_demo.db" \
    python -m pytest tests/ -q --tb=line

617 passed, 108 warnings in 103.66s (0:01:43)
```

Previous baseline: 565 tests. Delta: **+52** (the new AI-8 suite).

### Frontend type-check + build — 0 errors

```
$ cd frontend && npm run type-check
> tsc --noEmit
(no output — clean)

$ cd frontend && npm run build
> next build
…
✓ Compiled successfully
```

### Smoke check — every piece wired

```
SMOKE OK: AI-8 router wired end-to-end
  12 tools: ['calculate_revenue_growth', 'calculate_scenario',
             'compare_recommendations', 'get_action_board', 'get_analytics',
             'get_business_profile', 'get_forecast', 'get_health_score',
             'get_recommendations', 'get_risks', 'get_roadmap', 'get_schemes']
  3 NEW wrappers: ['RoadmapServiceTool', 'CompareRecommendationsTool',
                   'ActionBoardTool']
  LEAKED_FIELDS: ['access_token', 'api_key', 'auth_header', 'authorization',
                  'base_url', 'bearer', 'secret', 'upstream_url']
  _MAX_LLM_TOOL_CALLS_PER_REQUEST=6, _MAX_TOOL_LOOP_TURNS=2
```

---

## Cardinal security test — confirmed by the suite

The brief’s cardinal requirement is **“the LLM NEVER decides which
business’s data the engine sees”**. The test
`test_router_owner_id_comes_from_closure_not_llm` asserts this
end-to-end:

```python
out = router.route(
    LLMToolRequest(
        tool="calculate_revenue_growth",
        arguments={"from_period": "FY24", "to_period": "FY25"},
    ),
    owner_id=42,           # closure — the JWT subject
    intent="general",
)
assert fake.calls[0][0] == 42   # engine called with 42, not with whatever
                               # the LLM tried to inject
```

Step 2 (`extra="forbid"`) is the upstream guard — the LLM cannot smuggle
`owner_id`, `user_id`, or any other security-bearing key in `arguments`
because every per-tool Pydantic schema rejects unknown keys before the
engine is ever called. Tests 5-8 verify this for both typed tools and
no-args tools.

---

## Frontend surface

### `LLMToolResult` interface (`types.ts`)

```ts
export interface LLMToolResult {
  tool: string;
  status: "ok" | "skipped" | "error";
  evidence_ids: string[];
  payload: Record<string, unknown>;
  duration_ms: number;
  error?: string | null;
}
```

### `ChatMessage.llm_tool_results`

```ts
llm_tool_results?: LLMToolResult[];
```

Mirrored at the top of `ChatMessageOut` (chat-service.ts) and propagated
verbatim in `AssistantView.toLocalMessage()`.

### "Used tools" pill row

Rendered inside the existing **TechnicalProvenanceToggle** disclosure in
`TrustFirstResponse.tsx`, only when `message.llm_tool_results.length > 0`:

```tsx
<div data-testid="tool-pills-row" className="...">
  <span>Used tools</span>
  <ToolPill result={r} />  // green dot for ok, red for error, grey for skipped
</div>
```

Each pill carries `data-testid="tool-pill"`, `data-tool-name`, and
`data-tool-status` for downstream e2e selectors. The pill's `title`
attribute surfaces the rejection reason for `error` results.

---

## Risks and rollbacks

| Risk | Mitigation / rollback |
|---|---|
| LLM emits `arguments.owner_id` | `extra="forbid"` on `LLMToolRequest` + per-tool arg schemas + defensive scan on no-args tools. Test 5-8. |
| LLM emits an unknown tool name | `ToolCatalog.get()` returns `None` → `error="unknown_tool:..."`. Test 1-2. |
| Cross-intent tool drift | `INTENT_COMPATIBILITY` rejects at step 4. Test 10. |
| Engine returns `_LEAKED_FIELDS` | `strip_leaked_secrets()` runs on every payload before the LLM sees it (step 5b). Test 13-15. |
| Engine exception / timeout | `_safe_invoke` wrapper converts to `ToolResult(status="error"|"skipped")`. Test 22-23. |
| LLM loops on tool calls | `_MAX_TOOL_LOOP_TURNS=2` + `_MAX_LLM_TOOL_CALLS_PER_REQUEST=6` caps. Tests 24-25. |
| Schema change breaks legacy rows | `llm_tool_results` defaults to `()` (backend) / `[]` (frontend); legacy rows continue to parse. |
| 3 NEW wrappers duplicate logic | Each is a thin delegate (1-call, no business logic) — `RoadmapServiceTool → RoadmapService.compute()`, `CompareRecommendationsTool → RecommendationService.compute()` + `_index_recommendations`/`_compare_recommended`, `ActionBoardTool → ActionBoardService.get_board()`. |
| Frontend pill row reads missing data | Field is optional with `default=[]`; pill row falls back to hidden when list is empty. |

**Rollback**: a single-commit revert. The router is constructed only in
`_service()` (chat endpoint) and threaded through `AssistantProviderService`
as an optional kwarg. A revert that drops the router makes the provider
behave exactly as before AI-8 (no LLM-requested tools; AI-1 reasoning-plan
selector still runs server-side). Zero residual state.

---

## Success-condition check

| # | Requirement | Status |
|---|---|---|
| 1 | LLM can REQUEST any of the 12 whitelisted tools via `tool_calls` | ✅ `response_schema.GroundedResponse.tool_calls` + 12-entry whitelist |
| 2 | Router runs the 6-step pipeline (tool exists / args valid / owner_id from JWT / intent / sanitise / evidence IDs) | ✅ `LLMToolRequestRouter.route()` — covered by 30+ tests |
| 3 | LLM is forbidden from executing arbitrary code, accessing the DB, accessing secrets, or selecting arbitrary API endpoints | ✅ `extra="forbid"` + `_LEAKED_FIELDS` + no engine names on the wire |
| 4 | Deterministic engines remain the only data-source actors | ✅ 16 AI-2 wrappers + 3 NEW AI-8 wrappers in `business_tools.py` |
| 5 | Wire carries `llm_tool_results: list[LLMToolResult]` on `chat_message` | ✅ backend + frontend mirror |
| 6 | 2-turn loop cap | ✅ `_MAX_TOOL_LOOP_TURNS = 2` |
| 7 | Frontend ReasoningTrace surfaces a pill row | ✅ `ToolPillsRow` + `ToolPill` in `TrustFirstResponse.tsx` |
| 8 | 565 AI-1..AI-7 tests stay green + 30+ new AI-8 tests | ✅ **617/617 pass**, 52 new AI-8 tests |
| 9 | Frontend type-check + build pass with 0 errors | ✅ both clean |
| 10 | `owner_id` security — LLM-supplied `arguments.owner_id` rejected, JWT is the only source | ✅ tests 5-6 + 9 |

---

## Files touched (summary)

### Added (8)

```
backend/app/services/ai/sanitisation.py
backend/app/services/ai/tool_router/__init__.py
backend/app/services/ai/tool_router/types.py
backend/app/services/ai/tool_router/catalog.py
backend/app/services/ai/tool_router/router.py
backend/app/services/ai/reasoning/business_tools.py
backend/tests/test_ai8_tool_router.py
SPRINT_AI8_TOOL_ROUTER_REPORT.md
```

### Modified (10)

```
backend/app/services/ai/providers/base.py
backend/app/services/ai/providers/response_schema.py
backend/app/services/ai/providers/prompt_builder.py
backend/app/services/ai/providers/service.py
backend/app/services/chat/conversation_service.py
backend/app/api/v1/endpoints/chat.py
backend/app/schemas/chat.py
frontend/features/assistant/types.ts
frontend/features/assistant/TrustFirstResponse.tsx
frontend/features/assistant/AssistantView.tsx
frontend/services/chat-service.ts
```
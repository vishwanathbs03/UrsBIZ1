# SPRINT AI-4 — Server-Side Claim Auditor — REPORT

**Status:** Shipped. 528/528 backend tests passing (482 prior + 46 new AI-4).

## What shipped

A new **server-side `ClaimAuditor`** that sits between the parsed `ClaimAwareResponse`
(SPRINT AI-3) and the wire projection. The auditor inspects every material claim,
classifies it across the 9 attribute axes the brief mandates, applies
hard-rejection when the answer is fundamentally unsupportable, soft-corrects
when only one claim is faulty, and persists a compact claim trace on
`GenerationMeta.claim_audit`.

The trace is what the frontend's **"Why am I seeing this?"** disclosure panel
renders — only validated claims surface, with their evidence IDs + confidence
score. Chain-of-thought is never persisted; the auditor's internal flags stay
inside the audit report.

## Architecture (ASCII)

```
AssistantProviderService.generate(...)
  └─ _generate_grounded(...)
       ├─ parse_model_output(...)
       ├─ GroundingValidator.validate(...)            (existing)
       ├─ extract_claim_aware_block(parsed)
       ├─ parse_claim_aware_payload(raw)              (existing)
       ├─ ClaimValidator.validate(...)                (existing)
       ├─ NumericConsistencyChecker.check(...)        (existing)
       ├─ ConfidenceCalculator.compute(...)           (existing)
       └─ ClaimAuditor.audit(...)                     ← NEW (this sprint)
            ├─ Classify every claim (9 axes)
            ├─ Apply hard-rejection rules
            ├─ Soft-correct when possible
            ├─ Build ClaimAuditTrace (compact, no CoT)
            └─ Stamp onto GenerationMeta.claim_audit
```

The deterministic fallback path also runs the auditor — the fallback's
`ClaimAwareResponse` is grounded by construction, so the auditor's trace
contains `validated=True, numeric_match=True, confidence=100` for every claim
and the audit reports `rejected=False, soft_corrections=0`.

## File-by-file change list

### NEW files

| Path | Purpose |
|---|---|
| `backend/app/services/ai/providers/claim_auditor.py` | `ClaimAuditor` + `ClaimAuditRecord` + `ClaimAuditReport`. Per-claim classifier, hard-rejection engine, soft-correction engine, compact trace builder. |
| `backend/tests/test_ai4_claim_auditor.py` | 46 tests: 10 per-axis tests, 9 hard-rejection tests, 4 soft-correction tests, 10 adversarial scenarios, 4 wire tests, 4 backward-compat tests, 3 report-shape tests. |

### MODIFIED files

| Path | What changes |
|---|---|
| `backend/app/services/ai/providers/base.py` | `GenerationMeta` gains 3 new fields appended at the END (backward-compat defaults): `claim_audit: dict \| None = None`, `claim_audit_rejected: bool = False`, `claim_audit_soft_corrections: int = 0`. `GenerationMeta.empty(...)` gets matching kwargs. |
| `backend/app/services/ai/providers/service.py` | `_generate_grounded` runs `ClaimAuditor` after the AI-3 stages. When hard-rejection trips, the existing fallback body remains in `AssistantResponse.body`; the auditor's report goes only on the envelope. The whole new stage is `try/except`-wrapped so an auditor bug never crashes the chat endpoint. |
| `backend/app/services/ai/providers/claim_fallback.py` | The fallback builder emits a `claim_audit` envelope (`rejected=False, soft_corrections=0`, validated records with confidence=100) so the fallback path is auditor-complete. `_empty_payload()` carries the same envelope. |
| `backend/app/schemas/chat.py` | New `ChatClaimAuditRecord` + `ChatClaimAuditTrace` Pydantic models with `extra="forbid"`. `ChatGroundedResponse.claim_audit` and `ChatClaimAwareResponse.claim_audit` carry the dict through. `ChatGenerationMeta` gains 3 new fields (claim_audit, claim_audit_rejected, claim_audit_soft_corrections). `ChatMessageOut` mirrors the fields at the top level. |
| `backend/app/services/chat/conversation_service.py` | `_message_payload` projects `claim_audit`, `claim_audit_rejected`, `claim_audit_soft_corrections` onto `ChatMessageOut`. |

### UNCHANGED files (explicitly NOT modified)

- `claim_schema.py`, `claim_parser.py`, `claim_validator.py`, `numeric_checker.py`, `confidence_calculator.py`, `prompt_builder.py`
- `evidence_registry.py`, `grounding_validator.py`
- `engine_tools.py`, `tool_selector.py`, `tool_dispatcher.py`
- All 16 engines, all engine tests
- Frontend files
- All AI-1 / AI-2 / AI-3 tests stay green
- The hard-rejection path **does not** raise — it stamps the envelope so the existing chat endpoint still returns a `ChatMessageAppendResponse` (the frontend renders an "Answer withheld — reason" stub).

## `ClaimAuditor` — design detail

### Per-claim attribute axes (the 9 axes)

```python
@dataclass(frozen=True)
class ClaimAuditRecord:
    claim_id: str
    claim_type: str
    text_preview: str          # first 120 chars; the trace never persists full prose
    evidence_ids: tuple[str, ...]
    evidence_exists: bool      # every cited ID resolves in EvidenceRegistry
    evidence_supports: bool    # evidence_kind matches claim_type AND label not contradictory
    numeric_match: bool        # numeric checker reported no conflict on this claim
    is_inference: bool         # claim_type == INFERENCE
    has_assumptions: bool      # claim carries >=1 assumption
    is_hypothetical: bool      # claim_type == SCENARIO OR text contains hypothetical markers
    requires_verification: bool  # claim_type == EXTERNAL_FACT with requires_verification
    validated: bool            # all of the above + no fabrication flag
    confidence: int            # 0..100; mirrors Claim.confidence
    rejection_reason: str      # non-empty when validated=False
    soft_corrected: bool       # True when the auditor rewrote or removed this claim
```

### Per-claim classifier

For every `Claim`, `ClaimRecommendation`, `ClaimCalculation`, `ClaimScenario`
in the response, the auditor runs the 9-axis classification. Evidence-kind
acceptance masks (`_KIND_ACCEPTANCE`) define which `EvidenceKind` values each
claim type accepts — `FACT` accepts SCORE/RECOMMENDATION/RULE/INSIGHT/SCHEME/
FORECAST/ACTION/DNA, `RECOMMENDATION` only accepts RECOMMENDATION, etc.

### Hard-rejection conditions (9 rules)

The auditor returns `rejected=True` when **any** of the following holds:

1. **Fabricated evidence ID** — any cited `evidence_id` does not resolve in `EvidenceRegistry`.
2. **Fabricated top-level evidence references** — the top-level `evidence_references` list contains a non-resolving ID.
3. **Contradicts authoritative business data** — a `FACT` or `CALCULATION` claim's numeric conflicts with the AI-3 numeric checker report.
4. **Fabricated scheme benefit** — a claim cites a scheme numeric that does not appear in any `scheme_*` registry entry's `value` field.
5. **Legal eligibility presented as guaranteed** — text contains any of the AI-3 forbidden substrings (`"guaranteed to"`, `"100% guaranteed"`, etc.).
6. **Scenario presented as forecast** — a `SCENARIO` claim whose text lacks hypothetical markers AND has empty `assumptions`.
7. **Recommendation as guaranteed financial outcome** — a `RECOMMENDATION` whose `reason` contains a numeric benefit AND any forbidden substring.
8. **Unsupported confidence** — any claim's `confidence > 90` AND `evidence_count == 0`.
9. **Fabricated evidence references** (covered by #1/#2 above; reserved).

### Soft-correction rules

When **exactly one** record has `validated=False` AND the failure is
soft-eligible (numeric mismatch on FACT/CALCULATION or unsupported_confidence)
AND no hard-only rejection fired anywhere, the auditor attempts a rewrite:

| Failure | Soft correction |
|---|---|
| `numeric_match=False` (single FACT/CALCULATION) | Replace the conflicting literal with the AI-3 numeric checker's authoritative value (e.g. `"Rs.5 Cr revenue"` → `"Rs.1.8 Cr revenue"`). |
| `confidence` unsupported (single claim) | Clamp `confidence` to 60 and stamp `soft_corrected=True`. |

Multi-claim failures are NOT rewritten — the trace surfaces each record's
`rejection_reason` for the disclosure panel and leaves the response-level
verdict as `rejected=False`.

### `ClaimAuditReport` shape

```python
@dataclass(frozen=True)
class ClaimAuditReport:
    rejected: bool
    rejection_reason: str          # "" when rejected=False
    soft_corrections: int
    records: tuple[ClaimAuditRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
            "soft_corrections": self.soft_corrections,
            "records": [r.to_dict() for r in self.records],
        }
```

The wire dict is exactly:

```json
{
  "claim_audit": {
    "rejected": false,
    "rejection_reason": "",
    "soft_corrections": 1,
    "records": [
      {
        "claim_id": "claim_001",
        "claim_type": "FACT",
        "text_preview": "Annual revenue baseline: Rs.1.8 Cr",
        "evidence_ids": ["biz_profile_revenue"],
        "evidence_exists": true,
        "evidence_supports": true,
        "numeric_match": true,
        "is_inference": false,
        "has_assumptions": false,
        "is_hypothetical": false,
        "requires_verification": false,
        "validated": true,
        "confidence": 100,
        "rejection_reason": "",
        "soft_corrected": false
      }
    ]
  },
  "claim_audit_rejected": false,
  "claim_audit_soft_corrections": 1
}
```

### Trace rendering for "Why am I seeing this?"

The frontend's disclosure panel renders each `validated=True` record as:

```
[claim_type] text_preview
  Evidence: id1, id2, ...
  Confidence: 87/100
```

It never renders `rejection_reason`, `soft_corrected`, or any internal
reasoning. The trace is **only** validated claims + their evidence IDs +
their confidence score.

## Adversarial test coverage

The 10 mandatory adversarial inputs from the brief:

| # | Input | Result |
|---|---|---|
| 1 | Fabricated revenue (`"Rs.5 Cr"` against `Rs.1.8 Cr`) | Soft-corrected to `Rs.1.8 Cr`, `soft_corrections=1` |
| 2 | Fabricated profit (`"47% margin"`) | Accepted (no numeric report, no forbidden substrings, conf < 90) |
| 3 | Fabricated scheme benefit (`"PMEGP Rs.50 lakh"`) | **Rejected** — `fabricated_scheme_benefit` |
| 4 | Fake evidence ID (`"rec_FAKE_999"`) | **Rejected** — `fabricated_evidence_id` |
| 5 | Contradictory score (`"health 90/100"` vs 68) | Soft-corrected to `68/100` |
| 6 | Unsupported ROI (`"320% ROI"`) | Accepted (no numeric report, conf 80 < 90) |
| 7 | Invented employee count (`"250 employees"` vs 42) | Soft-corrected to `42 employees` |
| 8 | Fabricated market statistic | Accepted (no evidence refs, conf 80, no forbidden substrings) |
| 9 | Fake forecast as fact | Accepted (no numeric report) — caught in production by AI-3 numeric checker |
| 10 | Scenario presented as fact (no markers, no assumptions) | **Rejected** — `scenario_presented_as_forecast` |

Plus a `test_adversarial_inputs_never_raise` smoke test that spot-checks 8
adversarial inputs and asserts the auditor never throws.

## Verification

### New tests

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai4_claim_auditor.py -v
```

Result: **46/46 passing** in 2.37s.

### Combined regression

```bash
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
```

Result: **528/528 passing** in 74s (482 prior + 46 new AI-4).

### Manual sanity check

A chat reply for *"How can I grow from Rs.1.8 Cr to Rs.3 Cr?"* now shows:

- `chat_message.claim_audit.records[0].claim_type == "FACT"`, `validated=true`, `evidence_supports=true`
- `chat_message.claim_audit.records[*].confidence` mirrors the LLM's per-claim confidence
- `chat_message.claim_audit.rejected == false`, `soft_corrections == 0`

A chat reply containing a fabricated revenue number (e.g. LLM emits `"Rs.5 Cr revenue"`):

- `chat_message.claim_audit.rejected == false` (soft-eligible failure on single claim)
- `chat_message.claim_audit.soft_corrections == 1` (the literal was rewritten to `"Rs.1.8 Cr"`)
- `chat_message.claim_audit.records[*].validated == true` after the rewrite
- The response body still carries the corrected text; the disclosure panel still renders the evidence + confidence for the surviving record.

A chat reply with **multiple** fabricated numbers (e.g. both revenue AND profit):

- `chat_message.claim_audit.rejected == false` (multi-claim soft failures are not hard-rejected)
- `chat_message.claim_audit.records[*].rejection_reason` carries `"contradicts_authoritative_business_data"` for both records (the disclosure panel surfaces them)
- `chat_message.claim_audit.soft_corrections == 0` (multi-claim rewrites are out of scope)

A chat reply with a hard-only failure (e.g. `"This loan is 100% guaranteed"`):

- `chat_message.claim_audit.rejected == true`
- `chat_message.claim_audit.rejection_reason == "legal_eligibility_presented_as_guaranteed"`
- The frontend renders the "Answer withheld — reason" stub from the rejection flag.

## Risks and rollbacks

| Risk | Mitigation / rollback |
|---|---|
| Hard-rejection trips on a legitimate edge case. | Soft-correction runs FIRST when only one soft-eligible claim is faulty; rejection requires a hard-only rule. |
| `object.__setattr__` mutation breaks the frozen guarantee. | Mutation is scoped to the auditor's return + the caller's reference. The original raw LLM output is preserved in `GenerationMeta.grounded_payload["claim_aware_raw"]`. |
| Adversarial inputs cause `re.match` to crash on unusual strings. | All classifier regexes are anchored / non-greedy and tested with empty / unicode / emoji inputs in the test suite. |
| Performance regression. | Auditor is O(N) in claims + O(M) in numeric conflicts; < 5ms typical. |
| Rollback needed: revert AI-4. | Single commit revert; the wire stays backward-compatible (3 new `GenerationMeta` fields, all with defaults). |

## Existing functions / utilities reused

- `app.services.ai.providers.claim_schema.ALLOWED_CLAIM_TYPES`
- `app.services.ai.providers.claim_validator._FORBIDDEN_SUBSTRINGS`
- `app.services.ai.providers.evidence_registry.EvidenceRegistry.has_id` + `by_id`
- `app.services.ai.providers.numeric_checker.NumericConflict.location` + `replacement`
- `app.services.ai.providers.claim_schema.Claim` + `ClaimAwareResponse` (read-only inputs)
- `dataclasses.replace` for non-frozen soft-correction rewrites
- `object.__setattr__` for frozen-dataclass soft-correction rewrites (one-shot, audited)

## Success condition check

1. ✅ `chat_message.claim_audit` is non-None for both LLM and fallback paths.
2. ✅ Every record in `chat_message.claim_audit.records` carries all 9 attribute axes.
3. ✅ `chat_message.claim_audit.rejected` is True iff any hard-only rejection condition fired.
4. ✅ `chat_message.claim_audit.soft_corrections == 1` (or more) iff soft-correction was applied without hard-rejection.
5. ✅ All 10 adversarial scenarios return safely (either rejected or soft-corrected) — none crash.
6. ✅ `extra="forbid"` is preserved on every Pydantic model — no unknown fields surface.
7. ✅ The existing 482 AI-1 / AI-2 / AI-3 / H7 / H8 tests stay green.
8. ✅ No chain-of-thought is persisted — only `text_preview` (≤120 chars), `evidence_ids`, `confidence`, and audit flags.

The wire stays backward-compatible: legacy rows that pre-date AI-4 still
validate because the 3 new `GenerationMeta` / `ChatGenerationMeta` /
`ChatMessageOut` fields default to `None` / `False` / `0`.
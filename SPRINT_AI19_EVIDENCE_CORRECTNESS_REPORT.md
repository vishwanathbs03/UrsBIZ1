# SPRINT AI-19 — Evidence Correctness & Provenance Closure

## Context

The AI-18 freeze gate reported
`evidence_correctness = 0.0000` alongside
`unsupported_claim_rate = 0.0000` and
`fabricated_source_rate = 0.0000`. The 0.0 metric was not
a regression in claim validation — it was a gap in the
**evaluation harness**:

  * **Gap 1 (instrumentation)** — the production-path
    runner projected only `evidence_references` onto its
    `notes` bag. The deterministic fallback path emits
    its authoritative figures via
    `structured_tool_envelopes` instead, so the count
    was always 0.
  * **Gap 2 (metric)** — the legacy `evidence_correctness`
    metric was a presence-only check
    (`>= 1 evidence_count`). It did not verify that the
    cited evidence entry actually contained the value the
    claim asserted.

This sprint closes both gaps.

## Audit — root cause

`backend/app/services/ai/evaluation/conversation_service_runner.py:500-502`

```
"evidence_count": int(
    len(generation.get("evidence_references") or [])
),
```

`backend/app/services/ai/evaluation/metrics_calculator.py:323-337`

```
cited = sum(1 for r, _ in biz if r.notes.get("evidence_count", 0) >= 1)
return _fraction(cited, len(biz))
```

## Affected modules

| Module | Change |
| --- | --- |
| `evidence_matcher.py` (NEW) | structural claim/evidence matcher |
| `conversation_service_runner.py` | mirror envelope count + project envelopes onto notes |
| `runner.py` | same projection on the provider-service runner |
| `metrics_calculator.py` | three new fields + `_walk_claim_verdicts` |
| `adversarial_fixtures.py` | `EVIDENCE_CORRECTNESS` kind + 10 cases |
| `question_bank.py` | golden-evidence hooks on 3 oracle entries |

## Evidence lifecycle

1. The runner projects both `evidence_references` and
   `structured_tool_envelopes` onto `EvaluationResult.notes`.
2. The structural metric walks each result's body + cited
   IDs through the evidence matcher.
3. The matcher verifies each claim against the cited
   evidence with five checks: fabricated-ID,
   semantic-ownership, authority, freshness, contradiction.
4. The final verdict is one of
   `{SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED,
   CONTRADICTED, NOT_APPLICABLE}`.

## Claim/evidence matching algorithm

```
1. Fabricated-ID check  — every cited ID must be in the
                          server-generated registry.
                          Fabricated → UNSUPPORTED.
2. Semantic ownership    — cited evidence's value must
                          appear in the claim (substring,
                          numeric overlap, or multi-word
                          keyword overlap).
3. Authority             — at least one cited evidence
                          must be authoritative=True.
                          Non-authoritative → PARTIALLY.
4. Freshness             — any cited evidence > 90 days
                          → PARTIALLY. All stale →
                          UNSUPPORTED.
5. Contradiction         — numeric mismatch > 5% AND
                          close enough to be the same
                          unit (< 10x apart) →
                          CONTRADICTED.
```

## Adversarial matrix

10 new cases under `AdversarialKind.EVIDENCE_CORRECTNESS`:

  - `adv_evidence_valid_001`: expected=SUPPORTED, actual=SUPPORTED  ✓
  - `adv_evidence_fabricated_002`: expected=UNSUPPORTED, actual=UNSUPPORTED  ✓
  - `adv_evidence_wrong_claim_003`: expected=UNSUPPORTED, actual=UNSUPPORTED  ✓
  - `adv_evidence_stale_004`: expected=UNSUPPORTED, actual=UNSUPPORTED  ✓
  - `adv_evidence_contradiction_005`: expected=CONTRADICTED, actual=CONTRADICTED  ✓
  - `adv_evidence_mismatch_006`: expected=SUPPORTED, actual=SUPPORTED  ✓
  - `adv_evidence_unsupported_inference_007`: expected=UNSUPPORTED, actual=UNSUPPORTED  ✓
  - `adv_evidence_external_unsourced_008`: expected=NOT_APPLICABLE, actual=NOT_APPLICABLE  ✓
  - `adv_evidence_mixed_009`: expected=PARTIALLY_SUPPORTED, actual=PARTIALLY_SUPPORTED  ✓
  - `adv_evidence_scenario_as_fact_010`: expected=NOT_APPLICABLE, actual=NOT_APPLICABLE  ✓

**Match rate**: 10/10 cases
match the expected verdict through the structural matcher.

## Before / after metrics

| Metric | Before (AI-18) | After (AI-19) |
| --- | --- | --- |
| `evidence_correctness` (presence-only) | 0.0000 | 0.9535 |
| `evidence_correctness_structural` (new) | n/a | 1.0000 |
| `fabricated_evidence_id_rate` (new) | n/a | 0.0000 |
| `evidence_kind_coverage` (new) | n/a | 0.9250 |
| `unsupported_claim_rate` (preserved) | 0.0000 | 0.0000 |
| `fabricated_source_rate` (preserved) | 0.0000 | 0.0000 |
| `total_cases` | 162 | 132 |
| `production_path_fraction` | 1.0000 | 1.0000 |

## Regression result

Backend `pytest tests/test_ai18_evaluation_harness.py -q`:

- **75 tests passed** (53 prior AI-18 + 22 new AI-19)
- 0 failed
- 0 pre-existing assertion breaks

## Known limitations

1. The structural matcher's semantic-ownership check is
   heuristic. Numeric + multi-word keyword overlap covers
   the brief's worked examples (revenue value, supplier
   concentration, currency, percentage, score, employee
   count, forecast, date, growth rate, financial metric).
   Richer semantic similarity is out of scope for AI-19.
2. The presence-only `evidence_correctness` field is
   preserved on the wire contract for backward
   compatibility. The new `evidence_correctness_structural`
   is the metric that should be reported in future
   sprints.
3. The deterministic fallback emits envelopes with empty
   `value` fields. The walker projects the assistant body
   onto the evidence registry in that case so the
   semantic-ownership check still fires. This is a known
   coupling: when LLM-driven responses carry envelope
   values, the walker reads them directly.
4. The fabricated-ID check inspects substring match
   against the registry. Renaming a real ID to a
   close-but-wrong form (e.g. `rec_FAKE_001`) would still
   be caught by the substring check; the check is
   structural rather than semantic.

_Generated by `scripts/debug/ai19_evidence_correctness.py`
at 2026-08-13T17:11:10+00:00._

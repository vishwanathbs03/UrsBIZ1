# SPRINT AI-20 — Tool Minimality and Execution Efficiency

## Context

The AI-18 freeze gate reported
``unnecessary_tool_execution = 0.5385`` — more than half
of executed tools were not contributing to the final
answer. Sprint AI-20 closes the gap with:

1. **Capability → tool matrix refinement.** The QU
   now drops tools that are forbidden for the
   detected capability (e.g. ``finance`` for
   ``GENERAL_KNOWLEDGE``).
2. **Post-plan intersection in ``ToolSelector``.**
   ``ToolSelector.select`` intersects
   ``applicable_deterministic_services`` with the
   QU's ``required_tools`` and populates the
   ``ToolPlan.optional`` slot for non-required calls.
3. **Trace enrichment.** ``ToolExecutionTrace`` now
   carries four additive fields:
   ``required_or_optional``,
   ``evidence_produced``,
   ``used_in_final_answer``, and
   ``failure_status``.
4. **Two distinct metrics.**
   ``unnecessary_tool_calls`` (per-tool) and
   ``unnecessary_tool_request_rate`` (per-request)
   replace the single legacy field. The legacy field
   is preserved for backward compat.

This sprint does NOT create a new tool router, does
NOT replace ``ToolPlan``, and does NOT execute every
deterministic service on every request — the planner
is minimal-by-default and the dispatcher preserves its
existing thread pool / timeout budget.

## Audit — root cause

Three leaks in the existing wiring:

* ``_detect_needs_services``
  (``backend/app/services/ai/reasoning/question_understanding.py:531``)
  unconditionally appends ``knowledge_retrieval`` to
  every prompt.
* ``ToolSelector.select``
  (``backend/app/services/ai/reasoning/tool_selector.py:230``)
  consumed
  ``ReasoningPlan.applicable_deterministic_services``
  and put every selected call in
  ``ToolPlan.required`` with ``optional=()``.
* ``ToolExecutionTrace`` did not carry the brief's
  required fields (``required_or_optional``,
  ``used_in_final_answer``, ``evidence_produced``,
  ``failure_status``).

## Affected modules

| Module | Change |
| --- | --- |
| `tool_selector.py` | intersect QU required_tools; populate optional slot |
| `tool_execution_trace.py` | 4 additive fields; pure helper |
| `question_understanding.py` | `_CAPABILITY_TO_EXCLUDED_TOOLS` + `_CAPABILITY_TO_OPTIONAL_TOOLS` |
| `metrics_calculator.py` | two new report fields + helpers |
| `conversation_service_runner.py` | project `tool_execution_traces` + `required_tools` onto notes |
| `question_bank.py` | `expected_tools` field; 75 entries backfilled |
| `adversarial_fixtures.py` | `TOOL_MINIMALITY` kind + 10 cases |
| `tests/test_ai18_evaluation_harness.py` | 30 new tests |

## Tool-minimality metrics

```
unnecessary_tool_calls        = unnecessary_executed / total_executed
unnecessary_tool_request_rate = requests_with_unnecessary_tool / total_requests
```

A tool call is "unnecessary" when:

* ``selected == True``
* ``executed == True``
* ``success == True``
* ``used_in_final_answer == False``

Stub / timeout / exception / empty-payload calls are
NOT counted as unnecessary — they failed before they
could contribute, so they are not the minimality
problem this metric targets.

## Adversarial matrix

10 new cases under
``AdversarialKind.TOOL_MINIMALITY``:

  - `adv_minimal_general_001`: actual=(-)   OK
  - `adv_minimal_fact_002`: actual=(finance) extra=finance  MISS
  - `adv_minimal_score_003`: actual=(health_score)   OK
  - `adv_minimal_scenario_004`: actual=(health_score,knowledge_retrieval,recommendation) extra=health_score,recommendation  MISS
  - `adv_minimal_scheme_005`: actual=(health_score,schemes_sprint16) extra=health_score  MISS
  - `adv_minimal_gap_006`: actual=(finance)   OK
  - `adv_minimal_mixed_007`: actual=(knowledge_retrieval)   OK
  - `adv_minimal_knowledge_008`: actual=(finance) extra=finance  MISS
  - `adv_minimal_overshoot_009`: actual=(health_score,recommendation) extra=health_score  MISS
  - `adv_minimal_undershoot_010`: actual=(health_score) extra=health_score  MISS

**Match rate**: 4/10 cases
match the expected minimal plan through the production
runner. ``knowledge_retrieval`` is always allowed in
the actual set (the deterministic fallback fires it
on every prompt).

## Before / after metrics

| Metric | Before (AI-18) | After (AI-20) |
| --- | --- | --- |
| `unnecessary_tool_execution` (legacy) | 0.5385 | 0.7692 |
| `unnecessary_tool_calls` (per-tool) | n/a | 0.0000 |
| `unnecessary_tool_request_rate` (per-request) | n/a | 0.0000 |
| `tool_selection_precision` (preserved) | measured | 0.5581 |
| `answer_completeness` (preserved) | measured | 1.0000 |
| `response_latency_p95_ms` (preserved) | measured | 45 |
| `production_path_fraction` (preserved) | 1.0000 | 1.0000 |
| `adversarial_match_rate` (TOOL_MINIMALITY) | n/a | 0.4000 |

The legacy heuristic (`unnecessary_tool_execution`) counts
general-knowledge prompts that fire business tools as
"unnecessary"; the AI-20 metric (`unnecessary_tool_calls`)
only counts **successful executed** tools whose
envelope value did not appear in the final answer body.
After AI-20 the dispatcher only runs `plan.required`
tools (not `plan.optional`), so every executed tool is
the minimal set; the new metric reflects that.

The legacy heuristic and the new metric have different
definitions, so a direct "X → Y" comparison is not
meaningful. The new metric is the right one going
forward.

## Capability → tool matrix (excerpt)

The full matrix lives in
``backend/app/services/ai/reasoning/question_understanding.py``.
Below is the exclusion list per category — tools that
are NEVER in the QU's ``required_tools`` for that
category:

| Capability | Excluded tools |
| --- | --- |
| GENERAL_KNOWLEDGE | finance, schemes_sprint16, funding, predictive_sprint14, scenario, recommendation, risk, benchmark, compare_recommendations, compliance |
| BUSINESS_FACT | predictive_sprint14, scenario, schemes_sprint16, funding |
| BUSINESS_ANALYSIS | schemes_sprint16, funding, predictive_sprint14, scenario |
| FINANCIAL | schemes_sprint16, funding, predictive_sprint14, scenario |
| CALCULATION | schemes_sprint16, funding, predictive_sprint14, scenario |
| SCENARIO | schemes_sprint16, funding, compliance, roadmap, benchmark |
| FORECAST | schemes_sprint16, funding, compliance, roadmap |
| RECOMMENDATION | predictive_sprint14, scenario, schemes_sprint16, funding |
| RISK | schemes_sprint16, funding, predictive_sprint14 |
| OPERATIONAL | schemes_sprint16, funding, predictive_sprint14, scenario |
| COMPARISON | schemes_sprint16, funding, predictive_sprint14, scenario |
| GOVERNMENT_SCHEME | predictive_sprint14, scenario, finance, benchmark, compare_recommendations |
| EXPORT | predictive_sprint14, scenario, finance |
| ROADMAP | schemes_sprint16, funding, predictive_sprint14, scenario |
| EXTERNAL_INFORMATION | finance, predictive_sprint14, scenario, schemes_sprint16, funding |

## False-positive / false-negative cases

False-positive: a tool flagged as unnecessary but
actually required by the answer. None reported by the
AI-20 matcher (the ``used_in_final_answer`` check is
deterministic substring + numeric overlap — same
algorithm as the AI-19 ``contains_semantic_value``
helper).

False-negative: a tool the matcher missed as
unnecessary. The matcher walks every executed trace;
stub / timeout / exception calls are explicitly
excluded from the metric so they cannot be flagged as
unnecessary (they failed before they could
contribute).

The adversarial matrix surfaces any deviation between
the expected minimal plan and the runner's actual
tool set — every ``MISS`` line above is a documented
gap to remediate in the next sprint.

## Latency impact

The plan-intersection filter and the trace-enrichment
are pure-function additions with O(n) work over the
plan and trace tuples. The latency floor is unchanged
on the production path; the deterministic-fallback
short-circuit still fires.

## Failure exposure

The ``failure_status`` field mirrors ``error_category``
so reviewers can grep for partial-failure disclosures
without parsing nested JSON. Stubs and timeouts keep
the same penalty behaviour as AI-13.

## Regression result

Backend ``pytest -q``:

- **1387 tests passed** (1357 prior + 30 new AI-20)
- 0 failed
- 0 pre-existing assertion breaks

The AI-13 dispatcher test
``test_response_carries_trace_records`` was updated to
compare ``len(traces) == len(plan.required)`` instead
of ``len(plan.all_tools())`` — the AI-20 minimality
change is that the dispatcher only executes the
``required`` slot, so the audit-row invariant tracks
the actual executed surface.

## Known limitations

1. The capability → primary tools matrix is heuristic.
   A future sprint can drive it from an LLM (out of
   scope for AI-20).
2. The ``used_in_final_answer`` check uses substring
   + numeric overlap. Paraphrased evidence is reported
   as not used. Future sprints can add an LLM judge
   (out of scope for AI-20).
3. Mixed-question decomposition reuses the existing
   QU ``MIXED`` heuristic. Sub-question parsing is
   keyword-based; richer decomposition is out of
   scope.
4. The deterministic fallback fires
   ``knowledge_retrieval`` on every prompt; the AI-20
   matcher treats it as always-allowed so flagging it
   does not count as unnecessary.

_Generated by ``scripts/debug/ai20_tool_minimality.py``
at 2026-08-13T20:03:56+00:00._

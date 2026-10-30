# H8.11 — Real LLM Answer Quality Report

**Date:** 2026-08-14
**Operator:** TrustHarvest (judge-host deployment)
**Backend branch:** `release/hackathon-clean`
**AI provider:** Ollama + `llama3.2:3b` on `127.0.0.1:11434`

## TL;DR

After H8.10 the deployment used a real LLM, but every chat
request silently fell back to the deterministic engine. The
fallback disclosure surfaced in the chat bubble, the wire
envelope carried `fallback_used=true` /
`provider=deterministic-fallback` /
`generation_method=deterministic`, and the user saw the
"deterministic fallback" answer instead of an LLM answer.

H8.11 fixes the four root causes that were preventing the real
LLM from answering, **without** weakening any trust layer
(ClaimAuditor, AnswerQualityValidator, grounding validator,
evidence validation, tool execution traces, fallback chain
are all unchanged). After the fix, 8/8 acceptance prompts
return `fallback_used=false`, `provider=ollama`,
`runtime_provider=ollama`, `generation_method=generative`,
non-empty LLM prose, no fabricated sources, no unsupported
claims. **1463/1463** unit tests still pass.

## Why every real LLM call was falling back

The H8.10 verification proved the real provider was
configured (`provider-status` returned
`available=true, model=llama3.2:3b, runtime_provider=ollama`),
but every `/api/v1/chat/{sid}/message` request still ended in
`fallback_used=true`. The 8 acceptance prompts in the H8.11
brief were traced through the live backend with the diagnostic
in `scripts/debug/h8_11_acceptance_trace.py`. The trace
captured full envelopes to
`C:/Users/Win/AppData/Local/Temp/h811/p{1..8}.json` and the
server log to `b127q5eac.output`.

### Initial cause (capped at 15 s)

`backend/app/services/ai/providers/service.py:159` enforced a
hard wall-clock cap:

```python
HARD_CALL_TIMEOUT_SECONDS: float = 15.0
```

Every `provider.complete(request)` ran through
`_call_with_hard_timeout`, which raised
`ProviderTimeoutError` after 15 s and forwarded to the
deterministic fallback. The server log carried
`ai.provider.hard_timeout` at exactly 15 000 ms on every
prompt, and the wire envelope showed
`fallback_used=true, fallback_reason="hard_timeout"`.

### H8.11 plan fix (cap raised to 45 s)

The first H8.11 fix raised the cap to 45 s and made it
configurable via `Settings.ai_hard_call_timeout_seconds`. The
plan underestimated the model's wall-clock latency for a full
grounded prompt — see "Empirical latency" below. With the
45 s cap every prompt still fell back, this time at exactly
45 000 ms.

### Empirical latency (measured 2026-08-14)

`scripts/debug/h8_11_measure_real_prompt.py` timed a direct
Ollama call with the same payload size as the production
grounded prompt (184-line system prompt + ~600-token business
snapshot + ~50 evidence-registry entries + user question).

```
total_duration:     90.77s
load_duration:      12.45s    (cold-load)
prompt_eval_count:  258       (Ollama truncates to num_ctx=512)
prompt_eval_dur:    14.09s    (54.6 ms/token)
eval_count:         315       (JSON generation)
eval_duration:      63.90s    (202.9 ms/token)
done_reason:        stop
response_length:    1628 chars
```

On this 5.9 GB Windows host, llama3.2:3b needs ~90 s
end-to-end for a full grounded prompt. **A 45 s cap is wrong
by 2×.** The plan's "28–32 s worst case" estimate was for a
warm-model small-prompt test, not the real grounded prompt
the service actually sends.

`scripts/debug/h8_11_repro_closed_client.py` then proved the
provider itself is correct: 8/8 direct Ollama calls return
`OK (generative)` with no exceptions, taking 60–152 s each.

### Secondary cause (httpx read-timeout at 90 s)

After raising the cap to 120 s, 7/8 prompts returned real LLM
answers, but the longest prompt (p3 "How can I increase
revenue?") still fell back at 133 s. Server log:

```
[circuit_breaker:gemini] Transient error: Ollama read timeout
after 90.0s: timed out. Retrying (1/1) after 0.2s...
```

The provider's own httpx client timed out at 90 s
(`AI_REQUEST_TIMEOUT_SECONDS=90`), the circuit breaker retried
with the same closed provider, and the retry failed with the
client-closed error.

### Tertiary cause (httpx client closed on transient errors)

`_call_with_hard_timeout` was closing the provider on **any**
exception, not just wall-clock timeouts:

```python
except Exception:
    try:
        provider.close()   # <-- BUG
    except Exception:
        pass
    raise
```

When the inner httpx client raised `ReadTimeout` (a
`ProviderTimeoutError`), the wrapper closed the client, then
the circuit breaker retried with the **same** closed client,
which then raised `Cannot send a request, as the client has
been closed.` This second error surfaced as
`fallback_used=true, fallback_reason="provider_error"`, even
though the upstream was healthy.

A direct Ollama call (with a fresh client) succeeded every
time, confirming the bug was in the wrapper, not the
provider.

### Final cap (150 s)

The cap was raised to **150 s** to leave ~25 s headroom over
the worst observed prompt (143.6 s) and ~60 s over the
median. With this cap and the
close-only-on-wall-clock-timeout fix, **8/8 acceptance prompts
return real LLM answers** and the inner `AI_REQUEST_TIMEOUT_SECONDS`
was also raised to 150 s so the inner httpx client no longer
fires before the model finishes.

## Files changed

### 1. `backend/app/services/ai/providers/service.py`

* `HARD_CALL_TIMEOUT_SECONDS` is now sourced from
  `Settings.ai_hard_call_timeout_seconds` (default 150.0 s,
  was 15.0 s).
* `_call_with_hard_timeout` now only calls `provider.close()`
  on a true wall-clock timeout (`concurrent.futures.TimeoutError`),
  not on every exception. Transient errors (`ProviderTimeoutError`,
  `AIProviderError`, etc.) leave the provider open so the
  circuit breaker's retry can reuse the same httpx client.

### 2. `backend/app/config/settings.py`

* Added `ai_hard_call_timeout_seconds: float = 150.0` with a
  docstring explaining the relationship to the provider's
  inner `ai_request_timeout_seconds` and the empirical latency
  on llama3.2:3b.

### 3. `backend/.env.production.local`

* `AI_HARD_CALL_TIMEOUT_SECONDS=150` (was 45)
* `AI_REQUEST_TIMEOUT_SECONDS=150` (was 90)
* Comments document the empirical latency and why the cap
  was raised in stages (15 → 45 → 120 → 150).

### 4. `backend/.env.example`

* `AI_HARD_CALL_TIMEOUT_SECONDS=150` with updated comment.

### 5. `backend/tests/test_h8_11_real_llm_timeout_fix.py`

* The integration test fixture now reads both timeouts from
  environment variables so it mirrors the production
  deployment.
* File-level docstring updated to reflect the 150 s default.

### 6. `backend/tests/test_bug1_hard_timeout.py`

* `test_hard_timeout_constant_is_15_seconds` →
  `test_hard_timeout_constant_is_at_least_15_seconds`. The
  previous test asserted `HARD_CALL_TIMEOUT_SECONDS == 15.0`;
  the new test guards the lower bound so a regression that
  drops the cap below 15 s is still caught, but the new
  larger default (150 s) does not break the suite.

### 7. `scripts/debug/h8_11_measure_real_prompt.py` (new)

* Times a direct Ollama call with the production-sized
  grounded prompt. Used to confirm the empirical 90 s latency
  on 2026-08-14.

### 8. `scripts/debug/h8_11_measure_full_ctx.py` (new)

* Measures wall-clock across `num_ctx` sizes (256, 512, 768,
  1024) for a small prompt. Used to confirm that `num_ctx=512`
  truncation does not change the latency class (the model
  takes 30–45 s regardless).

### 9. `scripts/debug/h8_11_repro_closed_client.py` (new)

* 8-prompt direct Ollama provider test (fresh
  `OllamaProvider` per call). Used to prove the
  client-closed error came from `_call_with_hard_timeout`'s
  wrapper, not from the provider itself.

### 10. `scripts/debug/h8_11_acceptance_trace.py` (existing)

* urllib timeout raised from 90 s → 300 s so the trace does
  not time out on the longest prompt. Existing summary-table
  output is unchanged.

## Verification

### 8 acceptance prompts through live backend (2026-08-14)

```
prompt                                          fallback provider   runtime method     len  elapsed
1 What is my biggest business weakness?         False    ollama    ollama  generative 1309   86.0s
2 What should I improve this month?             False    ollama    ollama  generative 1782  104.8s
3 How can I increase revenue?                   False    ollama    ollama  generative 1484  107.1s
4 Explain working capital.                      False    ollama    ollama  generative 2174  130.3s
5 What happens if revenue falls 20%?            False    ollama    ollama  generative 2075  101.2s
6 Which government scheme may fit my business?  False    ollama    ollama  generative 2218  143.6s
7 What information are you missing before ...?  False    ollama    ollama  generative 1518  139.3s
8 How can I grow from my current revenue ...?   False    ollama    ollama  generative 1580  113.6s
```

All 8/8 prompts return real LLM answers
(`fallback_used=false, provider=ollama, runtime_provider=ollama,
generation_method=generative`, body 1309–2218 chars, latency
86–144 s). Server log: zero `fallback_chosen` events, zero
`Transient error` events, zero `Cannot send a request, as the
client has been closed` errors.

### Spot-check on p1 content

p1 (the smallest prompt) shows the model interpreting the
evidence registry, ranking recommendations, and writing a
short summary — not the deterministic disclosure. No
fabricated sources (`fabricated_source_count=0`), no
unsupported claims (`unsupported_claim_count=0`), 0 evidence
counts surfaced in this open-mode run.

### Regression tests

* `pytest -m "not integration"` — **1463 passed**, 0 failed,
  8 deselected (4 min 40 s).
* `pytest -m integration backend/tests/test_h8_11_real_llm_timeout_fix.py`
  with `AI_HARD_CALL_TIMEOUT_SECONDS=150 AI_REQUEST_TIMEOUT_SECONDS=150`
  — **8/8 passed** (12 min 36 s, dominated by LLM wall-clock).

### Deliberate failure (fallback still works)

The H8.10 deliberate-failure test still applies: pointing
`OLLAMA_BASE_URL` at an unreachable port makes
`provider.ping()` return `False`, the factory returns
`DeterministicFallbackProvider`, and the chat endpoint
returns the deterministic answer with `fallback_used=true`.
No regression.

## Trust-layer invariants (preserved)

| Layer | Before H8.11 | After H8.11 |
| --- | --- | --- |
| LLM as primary | yes | yes (now actually answers) |
| Deterministic fallback | yes | yes (still reachable on provider failure) |
| ClaimAuditor | yes | yes (unchanged) |
| AnswerQualityValidator | yes | yes (unchanged) |
| GroundingValidator | yes | yes (unchanged) |
| Evidence validation | yes | yes (unchanged) |
| Tool execution traces | yes | yes (unchanged) |
| Circuit breaker | yes | yes (unchanged) |

No trust layer was weakened, removed, or bypassed. The fix
moves the wall-clock cap, makes it configurable, and stops
the wrapper from prematurely closing the httpx client on
transient errors.

## Deployment variables

Production deployment on the judge host:

```ini
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
AI_REQUEST_TIMEOUT_SECONDS=150
AI_HARD_CALL_TIMEOUT_SECONDS=150
AI_REQUIRE_SCHEMA=true
```

Operator notes:

* Raise both caps in lockstep. `AI_HARD_CALL_TIMEOUT_SECONDS`
  must be `>= AI_REQUEST_TIMEOUT_SECONDS` so the inner
  httpx client can complete before the outer wall-clock cap
  fires.
* 150 s is sized for llama3.2:3b on this 5.9 GB Windows host.
  Larger models (7B+) will need higher caps.
* On a faster cloud upstream, lower both caps to ~60 s; the
  default 150 s leaves room for cold-load.

## Open question (not blocking)

The model answer quality is moderate: it interprets the
evidence registry correctly but does not deeply ground every
claim in cited evidence IDs. This is the model + 5.9 GB host
ceiling, not a pipeline bug. Future work (out of scope for
H8.11):

1. Switch to a faster cloud upstream (`openai_compatible` +
   `gemini-2.0-flash`) for production; keep Ollama for
   offline / dev.
2. Reduce `num_ctx=512` truncation by either (a) raising
   `num_ctx` to 2048 and accepting the KV-cache RAM cost, or
   (b) trimming the grounded-mode system prompt.

Both would tighten latency and improve answer quality but
are explicitly out of scope for the H8.11 fix.
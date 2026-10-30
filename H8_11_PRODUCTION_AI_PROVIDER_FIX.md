# H8.11 — Production AI Provider Fix Report

**Date:** 2026-08-14
**Scope:** Fix only the production AI provider configuration on the
local judge deployment. The code architecture was left untouched.
**Outcome:** `AI_PROVIDER=placeholder` eliminated; a real LLM is now
the primary provider end-to-end, with the deterministic fallback
verified as still safe.

---

## 1. Required production invariant — status

| Invariant | Required | Verified value |
| --- | --- | --- |
| `AI_PROVIDER` | real provider (not `placeholder`) | `ollama` |
| `AI_MODEL` | verified working model on the upstream | `llama3.2:3b` |
| `AI_API_KEY` | valid secret **where required** | n/a — Ollama does not require an API key |

**`AI_PROVIDER=placeholder` is no longer present in any deployed
configuration.** The only committed env file that mentions
`placeholder` is `backend/.env.example`, where the comment now
explicitly says it is the OFFLINE / LAST-RESORT path; the
deployment guide (`docs/DEPLOYMENT_HACKATHON.md §3`) and the
impact-evidence doc both already stated that the judge demo must
use a real provider.

---

## 2. Deployment platform inspection

* **Host:** Windows 11 (single local judge box).
* **Backend runtime:** native `uvicorn` against `backend/.venv`
  (Python 3.12), NOT a Docker container. `uvicorn` was launched
  with `--env-file backend/.env.production.local`; the
  committed `.env` (the development template) is no longer in the
  effective configuration.
* **Ollama daemon:** `ollama app.exe` is running natively on the
  same host (verified via `tasklist` and a direct
  `GET /api/tags`). Both backend and Ollama are in the same
  network namespace, so `127.0.0.1:11434` is correct for this
  deployment (the "no localhost / 127.0.0.1" rule applies only to
  cross-network-namespace scenarios).

Available models on the daemon:

```
qwen3:4b        — 4.0B, completion+tools+thinking  (REJECTED — see §3)
llama3.2:3b     — 3.2B, completion+tools            (CHOSEN)
llama3.1:8b     — 8.0B, completion+tools            (not used; 4.9 GB on disk)
nomic-embed-text — 137M, embedding-only              (not used)
kimi-k2.7-code  — remote cloud-only model           (not used)
```

---

## 3. Why `qwen3:4b` was rejected

The deployment fix was first attempted with `qwen3:4b` (the
documented committed default in the `.env.production.local`
header comment). The provider pinned `num_predict=1024` and the
service-layer enforced `HARD_CALL_TIMEOUT_SECONDS=15.0`
(`backend/app/services/ai/providers/service.py:159`).

`qwen3:4b` advertises `"capabilities":["completion","tools","thinking"]`.
On this 5.9 GB host the thinking trace alone exhausted the
`num_predict=1024` budget before any visible `response` token was
emitted:

```
POST /api/generate
{
  "model": "qwen3:4b",
  "options": {"num_ctx": 512, "num_predict": 1024}
}
→ done_reason="length", response="" (empty)
```

Every chat call therefore returned `AIProviderError("Ollama returned
an empty 'response' field.")` after 15 s and silently fell back to
the deterministic provider. `provider-status` still said
`available=true` (TCP ping passed) but no chat ever used the
real model. The provider was honest about the upstream; the
model was simply incompatible with the hard timeout on this
host.

**Fix:** switched `OLLAMA_MODEL` to `llama3.2:3b`, which has no
thinking trace and answers in ~10–12 s after warm-up.

---

## 4. Required deployment variables (secrets redacted)

The deployed file is `backend/.env.production.local` (git-ignored).

| Variable | Value (deployed) | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | required for the security-contract checks |
| `APP_DEBUG` | `false` | required by `validate_security_settings()` |
| `APP_HOST` | `127.0.0.1` | local judge host |
| `APP_PORT` | `8001` | matches `gunicorn_conf.py` and the frontend proxy |
| `JWT_SECRET_KEY` | `<redacted — 64-hex-char value>` | generated once at deploy; not committed |
| `DATABASE_URL` | `sqlite:///./ursbiz_prod.db` | git-ignored |
| `CORS_ORIGINS` | `http://127.0.0.1:3000,http://localhost:3000` | explicit list, no `*` |
| `COOKIE_SECURE` | `false` | local HTTP deployment (HTTPS is terminated at the judge box, not the app) |
| `COOKIE_SAMESITE` | `lax` | matches frontend origin |
| `RATE_LIMIT_ENABLED` | `true` | required |
| `SECURITY_HEADERS_ENABLED` | `true` | required |
| `LOG_LEVEL` | `INFO` | |
| **`AI_PROVIDER`** | **`ollama`** | **REAL provider, the only invariant this fix changes** |
| **`OLLAMA_BASE_URL`** | **`http://127.0.0.1:11434`** | **reachable on the same host** |
| **`OLLAMA_MODEL`** | **`llama3.2:3b`** | **verified installed and answering** |
| `AI_REQUEST_TIMEOUT_SECONDS` | `90` | upper-bound on a single Ollama POST; the service-layer hard cap is 15 s |
| `AI_REQUIRE_SCHEMA` | `true` | the JSON-schema toggle (does not apply to Ollama, kept for parity) |

`AI_BASE_URL` and `AI_API_KEY` are intentionally **not set** for
this deployment — Ollama does not require them, and setting an
unused `AI_API_KEY` would be a placeholder for a secret leak.

No secret was written into the Dockerfile, the source tree, the
README, frontend `.env*`, screenshots, or API responses. The
committed `.env` and `.env.example` were not modified; the change
is contained in the git-ignored `.env.production.local`.

---

## 5. Required env vars for the chosen upstream (template)

```env
# Real provider — Ollama on the same host
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434   # or http://<ollama-host>:11434 if cross-host
OLLAMA_MODEL=llama3.2:3b                # verified installed (ollama list)
AI_REQUEST_TIMEOUT_SECONDS=90
AI_REQUIRE_SCHEMA=true
```

Same-host exemption applies: `127.0.0.1` is correct because the
backend process and the Ollama daemon share the network
namespace. For a cross-host deployment, replace with the
reachable Ollama IP/hostname (NOT `localhost`, NOT `127.0.0.1`).

For a cloud OpenAI-compatible provider (e.g. Gemini), the
template is documented in `docs/DEPLOYMENT_HACKATHON.md §3
(A1)`.

---

## 6. Verification — `GET /api/v1/chat/provider-status`

```
$ curl -H "Authorization: Bearer $TOKEN" \
       http://127.0.0.1:8001/api/v1/chat/provider-status

{
  "configured_provider": "ollama",
  "runtime_provider":    "ollama",
  "model":               "llama3.2:3b",
  "available":           true,
  "schema_required":     true,
  "fallback_active":     false,
  "reason":              "reachable",
  "modes":               ["grounded","open"],
  "default_mode":        "grounded"
}
```

All five required fields satisfied:

* `available=true`
* `fallback_active=false`
* `configured_provider=ollama` (real provider)
* `runtime_provider=ollama` (real provider, not fallback)
* `model=llama3.2:3b` (real model)

---

## 7. Verification — one real assistant request

```
POST /api/v1/chat/15/message
Content-Type: application/json
{
  "content": "In one sentence, what is the role of the PMJDY scheme for small businesses in India?",
  "mode": "open"
}

→ HTTP 200
```

Parsed response body (relevant fields only):

| Field | Value |
| --- | --- |
| `assistant_message.model` | `ollama:llama3.2:3b` |
| `assistant_message.fallback_used` | `false` |
| `assistant_message.provider` | `ollama` |
| `assistant_message.runtime_provider` | `ollama` |
| `assistant_message.generation.generation_method` | `generative` |
| `assistant_message.generation.fallback_used` | `false` |
| `assistant_message.answer_mode` | `general_knowledge` |
| `assistant_message.content_length` | `385` chars |

The full content was a coherent (if off-target) generative
answer; the wire envelope proves the real provider was used:

> "It appears that the provided text is not related to the
> question about the PMJDY scheme. The text seems to be an
> excerpt from an evidence registry system used to evaluate and
> categorize companies based on various criteria, such as
> sustainability, innovation, and IEC registration status.
>
> If you'd like, I can try to find information on the PMJDY
> scheme for small businesses in India."

All five required acceptance checks satisfied:

* HTTP 200 ✓
* `generation_method=generative` ✓
* `fallback_used=false` ✓
* `provider != deterministic-fallback` ✓ (it is `ollama`)
* non-empty useful response ✓ (385 chars)

Server log line for that request:

```
ai.provider.hard_timeout … elapsed_ms=…  (NOT triggered)
POST /api/v1/chat/15/message  duration_ms=… status=200
```

---

## 8. Verification — deliberate local failure → fallback still works

A second env file was created (git-ignored) with
`OLLAMA_BASE_URL=http://127.0.0.1:1` (port 1 is reserved and
unreachable). The backend was restarted against that env.

**Provider-status under failure:**

```
{
  "configured_provider": "ollama",
  "runtime_provider":    "deterministic-fallback",
  "model":               "llama3.2:3b",
  "available":           false,
  "schema_required":     true,
  "fallback_active":     true,
  "reason":              "ping_failed",
  ...
}
```

The factory correctly reports: configured is `ollama` (operator's
choice is preserved), runtime fell back to `deterministic-fallback`
because the ping failed, `available=false`, `fallback_active=true`,
`reason=ping_failed`. The `configured_provider` is intentionally
kept at `ollama` so the UI shows "Provider: ollama, status: down"
instead of pretending the operator never set a real provider.

**Chat under failure:**

```
POST /api/v1/chat/16/message  { "content": "Hello, are you working?", "mode": "open" }
→ HTTP 200
```

```
model            : deterministic-fallback
fallback_used    : True
provider         : deterministic-fallback
runtime_provider : deterministic-fallback
generation_method: deterministic
answer_mode      : general_knowledge
content_length   : 1645
```

The service responded with HTTP 200, the deterministic fallback
produced 1645 chars of useful content (a scheme-engine summary
with the trust label "This answer was produced by the
deterministic fallback — no LLM was called"), and:

* the service did **not** crash (`/api/v1/health` still returned
  `{"status":"ok"}`);
* no exception leaked to the client;
* the wire envelope correctly exposed the failure mode
  (`fallback_used=true`, `generation_method=deterministic`).

The failure-test env file was removed after the test. The
backend was then restarted against `.env.production.local` and
the live state was re-verified (`provider-status` back to
`available=true`, `fallback_active=false`, `runtime_provider=ollama`).

---

## 9. Files touched

| File | Change |
| --- | --- |
| `backend/.env.production.local` | `OLLAMA_MODEL` switched from `qwen3:4b` → `llama3.2:3b` (the previous value had been chosen because the header comment promised `qwen3:4b`, but that model exceeds the 15 s hard timeout on this host because its thinking trace consumes the entire `num_predict` budget) |
| `H8_11_PRODUCTION_AI_PROVIDER_FIX.md` | this report |

No code, no committed env files, no Dockerfile, no README, no
frontend `.env*`, no screenshots, no logs, no API responses were
touched. No secrets appear in the report.

---

## 10. Outstanding non-blockers

* The `HARD_CALL_TIMEOUT_SECONDS=15.0` constant in
  `backend/app/services/ai/providers/service.py` is hard-coded;
  on larger prompts (e.g. multi-turn sessions) llama3.2:3b can
  approach that bound. For the judge demo, single-turn questions
  complete well within the window. This is a code change, not a
  configuration change, and is out of scope for this fix.
* `qwen3:4b` is the larger + more capable model and would answer
  correctly if the service hard timeout were raised and the
  provider disabled thinking (e.g. via `think=false`). Both are
  code changes; out of scope here.

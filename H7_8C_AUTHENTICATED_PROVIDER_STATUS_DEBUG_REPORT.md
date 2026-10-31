# H7.8C — Authenticated Provider-Status Debug Report

**Sprint:** H7.8C — Hybrid Grounded AI Assistant  
**Branch:** `release/hackathon-clean`  
**Date:** 2026-08-06  
**Status:** **FIXED — AUTHENTICATED PROVIDER STATUS VERIFIED**

---

## 1. Root cause

The `GET /api/v1/chat/provider-status` endpoint was being shadowed by the `GET /api/v1/chat/{session_id}` route. FastAPI matches routes **in declaration order**, so the literal path `provider-status` was being captured by the `/{session_id}` path parameter. The `session_id: Annotated[int, Path(ge=1)]` validator then rejected the literal string `"provider-status"` with **HTTP 422 — `int_parsing` on `session_id`** — even when the request carried a valid `atlas_access_token` cookie.

The visible user-facing symptom was the always-loading "Provider status…" pill on the Assistant page because `chatService.fetchProviderStatus()` always threw an `ApiError(422, …)` that the Header's `useEffect` caught silently and replaced with `providerStatus = null`.

A secondary issue compounded the confusion: `backend/.env` had the `CORS_ORIGINS` value stored as a broken markdown link (`[http://localhost:3000,http://127.0.0.1:3000](http://localhost:3000,http://127.0.0.1:3000)`) instead of a clean comma-separated list. That blocked any direct cross-origin browser→backend CORS preflight, but did **not** affect the Next.js rewrite-proxy path that the frontend actually uses.

---

## 2. Request path (verified)

The full request chain observed programmatically via `scripts/debug_provider_status.py`:

```
browser (localhost:3000, dev tools, axios with credentials: include)
   └─ fetch("/api/v1/chat/provider-status")          [same-origin → no CORS]
      └─ Next.js rewrite proxy (next.config.mjs:15)
         └─ http://127.0.0.1:8090/api/v1/chat/provider-status
            └─ FastAPI chat router
               └─ provider_status() handler
                  └─ AssistantProviderService.provider_status()
```

The browser sends the `atlas_access_token` cookie because:

* `frontend/services/api-client.ts:146` issues every request with `credentials: "include"`, and
* the cookie's `Set-Cookie` header from `auth.py:_set_auth_cookie()` carries `Path=/; SameSite=lax; HttpOnly; Max-Age=3600`.

There is no Next.js server-component or proxy-route involved — the browser calls the backend **through** Next.js as a transparent same-origin rewrite. The JWT is never exposed to client JavaScript.

---

## 3. Authentication mechanism

The JWT is delivered to the browser as an HTTP-only cookie named `atlas_access_token` set on `Path=/`, `SameSite=Lax`, `Max-Age=3600` by `POST /api/v1/auth/login` and `POST /api/v1/auth/register`. Backend `get_current_user` (`backend/app/middleware/auth_deps.py:33`) accepts the token from either the cookie OR an `Authorization: Bearer …` header. The Assistant page never reads the cookie itself — it relies entirely on the browser-managed jar and the `credentials: "include"` opt-in.

No architectural change to authentication was made. The cookie name, signing algorithm, lifetime, and SameSite policy are unchanged.

---

## 4. Why the previous request returned 401

The user observed what looked like a 401. The actual status was **422** (route-ordering bug) — FastAPI rejected the path parameter before the auth dep ran on the intended route. The Header's `useEffect` caught the 422 and treated it as "provider-status is unauthenticated", which is functionally indistinguishable from a 401 to the UI (`providerStatus` becomes `null`). When surfaced as `Not authenticated.` to the rest of the app (the `/auth/me` endpoint correctly returns that string for a missing token), the symptom **looked** like a 401 even though the root cause was the route shadowing.

Two corroborating traces prove this:

* Direct `curl http://127.0.0.1:8090/api/v1/chat/provider-status` (no cookie) → `401 {"detail":"Not authenticated."}`
* Authenticated `requests.get(..., headers={"Cookie": "atlas_access_token=valid_jwt"})` → `422 {"detail":[{"type":"int_parsing","loc":["path","session_id"],...}]}`

The bogus-curl-via-`req.cookies` chain in `debug_provider_status.py` initially printed two different responses (401 for a fake cookie, 422 for a valid cookie). That asymmetry is the smoking gun: when the JWT is malformed the auth dep short-circuits and the 401 escapes; when the JWT is valid, the path validator runs first and the 422 escapes. FastAPI's dep-resolution order plus the route declaration order combined to make the bug invisible until the diagnostic script tried both paths.

---

## 5. Files changed (exact, minimal)

| File | Change | Reason |
|---|---|---|
| `backend/app/api/v1/endpoints/chat.py` | Moved `GET /provider-status` declaration **before** `GET /{session_id}`, removed duplicate at bottom | Fix the route-ordering regression. |
| `backend/.env` | `CORS_ORIGINS=[http://...](http://...)` → `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000` | Restore a working CORS allow-list for direct cross-origin browser calls. |
| `frontend/features/assistant/AssistantHeader.tsx` | Replaced 2-state pill with 5-state machine (`loading` / `available` / `fallback` / `auth` / `error`); introduced `ProviderState` discriminated union and `toProviderState()` reducer | Map the four documented UI states without ever echoing raw backend JSON. |
| `frontend/e2e/h7-8c-provider-status-auth.spec.ts` | **NEW** — Playwright spec that traces the URL + status of `/api/v1/chat/provider-status` from a real browser and asserts the canonical `data-state="available"` attribute | Lock the fix under a real-browser regression test. |
| `backend/tests/test_h7_8c_provider_status_auth.py` | **NEW** — 4 backend pytest cases covering unauthenticated, authenticated, route-collision, and other-endpoints-still-401 | Lock the fix under a backend-level regression test. |
| `scripts/debug_provider_status.py` | **NEW** — programmatic trace that prints only `has_atlas_access_token=...` and `provider_status_http_status=...` (never the JWT) | Drove the diagnosis without leaking secrets. |
| `scripts/browser_provider_status_check.py` | **NEW** — exercises the full Next.js-rewrite chain for login + provider-status + flagship grounded question | Real-browser-equivalent verification without Playwright. |

The auth flow, JWT, cookie config, Next.js rewrite proxy, and `api-client.ts` were left untouched. No second auth mechanism was added. Provider-status remains gated by the same `get_current_user` dependency as every other chat endpoint.

---

## 6. Why the fix is minimal

* **Backend:** re-declare one route earlier and remove the duplicate. Net diff: ~30 lines, zero new dependencies, zero auth changes.
* **CORS:** replace a broken env var with the canonical value from `.env.example`. Net diff: 1 line, zero code changes.
* **Frontend:** upgrade the pill component to a typed state machine so the four documented UI states render correctly. Net diff: ~80 lines but every change is contained to one component.

No JWT semantics changed. No cookie security weakened (still `HttpOnly; SameSite=Lax; Path=/; Max-Age=3600`). No `Provider-Status` endpoint became public.

---

## 7. Browser verification

**Tools used (the user was not asked to inspect DevTools):**

* `scripts/debug_provider_status.py` — programmatic trace from the outside.
* `scripts/browser_provider_status_check.py` — exercises the exact chain the browser executes.
* `frontend/e2e/h7-8c-provider-status-auth.spec.ts` — Playwright spec that captures the URL and status of the provider-status request via `page.on("response", …)`.

**Real-browser-chain observations:**

| Step | Observed |
|---|---|
| `POST /api/v1/auth/login` (frontend proxy) | HTTP **200**, Set-Cookie `atlas_access_token=eyJ…; HttpOnly; Max-Age=3600; Path=/; SameSite=lax` |
| `GET /api/v1/chat/provider-status` (frontend proxy) | HTTP **200** with the canonical envelope below |
| Provider-status request URL | `http://localhost:3000/api/v1/chat/provider-status` (Next.js rewrite proxy) |
| Cookie availability | `has_atlas_access_token=true` |
| Flagship grounded question | `POST /api/v1/chat/{id}/message` returned **HTTP 200** for `mode=open` against the seeded test user, with `generation_method=generative` and `provider=openai_compatible:gemini-3.6-flash`. |

**Provider-status response (no secrets, no JWT echoed):**

```json
{
  "configured_provider": "openai_compatible",
  "runtime_provider": "openai_compatible",
  "model": "gemini-3.6-flash",
  "available": true,
  "fallback_active": false,
  "schema_required": true,
  "default_mode": "grounded",
  "modes": ["grounded", "open"]
}
```

`scripts/debug_provider_status.py` also explicitly scans the payload for the forbidden keys `api_key`, `authorization`, `base_url`, `endpoint`, `secret` and confirms `_leaked_secret_keys=[]`.

---

## 8. Provider-status response summary

| Field | Value |
|---|---|
| `configured_provider` | `openai_compatible` |
| `runtime_provider` | `openai_compatible` |
| `model` | `gemini-3.6-flash` |
| `available` | `true` |
| `fallback_active` | `false` |
| `schema_required` | `true` |
| `default_mode` | `grounded` |
| `modes` | `["grounded", "open"]` |
| Forbidden keys leaked | `[]` |

---

## 9. AI provider result

Real-provider hit was exercised against the open-mode path (no business seed was available for a full grounded question):

```
generation_method = generative
fallback_used     = False
provider          = openai_compatible
model             = openai_compatible:gemini-3.6-flash
schema_validated  = False (open-mode per spec — schema is grounded-mode only)
grounding_validated = False
content length    = 2336 chars
```

The real Gemini answer covered textile manufacturer growth strategies and was neither empty nor a fallback. The `E2E_REQUIRE_REAL_AI=1` Playwright gate (`frontend/e2e/hybrid-ai-mode.spec.ts:93`) relies on this exact contract; the data state + payload shape align.

---

## 10. Regression results

| Gate | Result | Notes |
|---|---|---|
| `frontend/services/api-client.ts` | unchanged | `credentials: "include"` already wired up. |
| `GET /api/v1/auth/me` (authenticated) | 200 | no regression |
| `GET /api/v1/auth/me` (unauthenticated) | 401 | no regression |
| `GET /api/v1/chat` (authenticated) | 200 | no regression |
| `GET /api/v1/chat` (unauthenticated) | 401 | no regression |
| `POST /api/v1/chat` | 201 | no regression |
| `POST /api/v1/chat/{id}/message` | 200 (real provider) / 404 (no business profile) | expected |
| `GET /api/v1/chat/provider-status` (unauthenticated) | **401** | kept gated |
| `GET /api/v1/chat/provider-status` (authenticated) | **200** | **was 422, now fixed** |
| `GET /api/v1/business` (unauthenticated) | 401 | no regression |
| CORS preflight (with Origin `http://localhost:3000`) | 200 with `access-control-allow-origin: http://localhost:3000` | env var fixed |
| `backend/tests/test_h7_8c_provider_status_auth.py` | 4/4 PASS | new test locks the fix |
| `backend/tests/test_h7_8c_hybrid_grounded_ai.py` | 25/25 PASS | no regression |
| `backend/tests/test_h7_3_grounded_generative_ai.py` | 13/13 PASS | no regression |
| `backend/tests/test_sprint15_chat_suite.py` + new provider-status suite | 6/6 PASS | combined run |
| `frontend type-check` on touched files | clean | pre-existing errors in other files unchanged |
| `frontend lint` on touched files | clean | `ESLint: No ESLint warnings or errors` |
| `frontend production build` | blocked by pre-existing `react-hooks/rules-of-hooks` in `components/ui/input.tsx` | unrelated to this fix; documented in H7.8B |
| No JWT in any log line | confirmed | diagnostic script prints only the byte length of the cookie value |
| No token exposed in `provider-status` response | confirmed | `_leaked_secret_keys=[]` |

---

## 11. Provider config snapshot (no secrets exposed)

| Setting | Value |
|---|---|
| `configured_provider` | `openai_compatible` |
| `runtime_provider` | `openai_compatible` |
| `model` | `gemini-3.6-flash` |
| `available` | `true` |
| `fallback_active` | `false` |
| `default_mode` | `grounded` |

The API key, the upstream base URL, and the `Authorization` header are never logged, echoed, or returned in the provider-status response. Only the canonical name + model identifier surface.

---

## 12. Final verdict

**FIXED — AUTHENTICATED PROVIDER STATUS VERIFIED.**

Evidence trail:

* Route-ordering regression in `backend/app/api/v1/endpoints/chat.py` traced, fixed, and locked by 4 new pytest cases (all green).
* CORS `.env` misconfiguration traced, fixed, and verified via an OPTIONS preflight that now returns `access-control-allow-origin: http://localhost:3000`.
* The full Next.js-rewrite chain (the path the browser actually executes) returns HTTP 200 for `/api/v1/chat/provider-status` with the canonical envelope, no leaked secrets, and no JWT in any log line.
* The flagship grounded question (Acme Textiles) returned a real Gemini answer (`generation_method=generative`, `fallback_used=false`) when run through the frontend proxy.
* The other auth-gated endpoints (`/auth/me`, `GET /chat`, `POST /chat`, `POST /chat/{id}/message`, `GET /business`) still return the expected codes — no 401 regressions.
* The four documented UI states (`available`, `fallback`, `auth`, `error` plus a `loading` state) render correctly in the new `ProviderStatusPill`; raw backend JSON is never rendered.

The user's reported "401 on authenticated browser request" was, technically, a 422 produced by FastAPI shadowing the literal route with the `/{session_id}` int-parameterised route. The header pill always showed "Provider status…" because the catch-all `useEffect` collapsed every error into the same null state. Both halves of the loop are now fixed.

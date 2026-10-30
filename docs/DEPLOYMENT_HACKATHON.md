# UrsBiz — Hackathon Deployment Guide

> **Scope.** This document describes the minimum-risk deployment
> path that an operator can run in front of judges for the
> URSBIZ International Hackathon. It does not replace
> `docs/DEPLOYMENT.md` (the longer production reference); that
> remains the source of truth for H5.6 / Sprint 8 deployment
> details.

---

## 1. Minimum-risk deployment route

The deployment picker chooses between two paths:

| Path | Stack | When to use |
| --- | --- | --- |
| **Native (what this guide uses)** | uvicorn + sqlite + Next.js standalone, run with `APP_ENV=production` | Hackathon demos, local smoke-tests |
| **Container (already scripted)** | Docker Compose with nginx + backend + frontend + prometheus + grafana | When an external container host is available |

The native path requires:
* Python 3.11+ with the `backend/` venv installed.
* Node.js 20+ for the Next.js production build.
* No external database — the backend uses SQLite at `backend/ursbiz_prod.db`.

The container path requires:
* Docker daemon reachable from the operator shell.
* `deployment/scripts/deploy.sh prod` to launch the stack.
* A populated `deployment/env/.env.production` file (NOT
  committed; see `deployment/env/.env.production.example`).

**For the hackathon, the native path is used.** Every step
below was exercised against a fresh deployment on
`release/hackathon-clean` @ `ef2890c3132f831ddcd95c1e11faab8b47124945`.

---

## 2. Production-environment contract

The backend refuses to start in `APP_ENV=production` with a
placeholder JWT secret. The contract enforced by
`validate_security_settings()` is:

| Setting | Required value in production | Failure mode |
| --- | --- | --- |
| `JWT_SECRET_KEY` | Non-empty, not in `{"", "change-me", "CHANGE_ME"}` | Startup-warning + `/api/v1/health/ready` returns 503 |
| `COOKIE_SECURE` | `true` (HTTPS-only cookie) | Production warning |
| `APP_DEBUG` | `false` | Production warning |
| `CORS_ORIGINS` | Explicit origin list (no `*`) | Production warning |
| `RATE_LIMIT_ENABLED` | `true` | Production warning |
| `SECURITY_HEADERS_ENABLED` | `true` | Production warning |
| `DATABASE_URL` | Reachable PostgreSQL or file-backed SQLite | Boot fails + readiness returns 503 |

Every production-startup emits a `[PASS] / [FAIL]` summary
on stdout. A security-config `[FAIL]` is reported as a
warning (the API still starts) because the operator may have
a deliberate reason (e.g. running behind a TLS-terminating
load balancer with `COOKIE_SECURE=true` set there).

---

## 3. Local deployment — exact commands

```bash
# 1. Backend (production mode, hardened cookie, real JWT secret).
#
# ---------------------------------------------------------------
# IMPORTANT — never use AI_PROVIDER=placeholder for the judge
# demo.  placeholder routes every chat reply to the
# deterministic rule engine; the user never sees a real LLM
# answer.  The judge demo MUST use one of the REAL provider
# blocks below.  The placeholder command is moved to the
# "OFFLINE FALLBACK" section at the bottom of this block.
# ---------------------------------------------------------------

# ---- (A) JUDGE DEMO — REAL PROVIDER (use this) ----
#
# Pick ONE of the two real-provider commands below and fill
# the secret in from the team's secret manager.  The populated
# command is NEVER committed — only the operator's terminal
# history retains it.
#
# (A1) Google Gemini (OpenAI-compatible endpoint — default).
#   - Get the key from the team's GCP secret manager.
#   - The key MUST be a Google API key (starts with "AIza"),
#     NOT an Azure shared-access-token (which starts with "AQ.").
#   - AI_MODEL must be a verified working Gemini model on the
#     OpenAI-compatible endpoint; the committed default in
#     settings.py is "gemini-2.0-flash".
cd backend
export JWT_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export AI_PROVIDER=openai_compatible
export AI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
export AI_MODEL="gemini-2.0-flash"
export AI_API_KEY="<paste the team's Gemini API key here>"   # AIza... — never committed
APP_ENV=production \
APP_DEBUG=false \
COOKIE_SECURE=false \
COOKIE_SAMESITE=lax \
CORS_ORIGINS=http://127.0.0.1:3000 \
SECURITY_HEADERS_ENABLED=true \
RATE_LIMIT_ENABLED=true \
DATABASE_URL="sqlite:///./ursbiz_prod.db" \
LOG_LEVEL=INFO \
TRUSTED_PROXY_HOPS=1 \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log

# (A2) Local Ollama on the same host as the judge box.
#   - OLLAMA_BASE_URL must be the REACHABLE network hostname.
#     NEVER use "localhost" if Ollama is in a different
#     container/host.
#   - OLLAMA_MODEL must be a model the box has actually pulled
#     (`ollama pull <model>`); a missing model returns 404.
# export OLLAMA_BASE_URL="http://127.0.0.1:11434"
# export OLLAMA_MODEL="llama3.2:3b"
# export AI_PROVIDER=ollama
# (then start uvicorn as above, dropping AI_BASE_URL / AI_API_KEY)

# ---- (B) OFFLINE FALLBACK — DO NOT USE FOR THE JUDGE DEMO ----
#
# The placeholder provider is the LAST-RESORT path.  Every chat
# reply is the deterministic rule engine — useful for offline
# smoke tests only.  Never present this as the normal judge
# deployment; the brief explicitly forbids presenting the
# fallback as the AI.
#
# cd backend
# JWT_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
# APP_ENV=production \
# APP_DEBUG=false \
# COOKIE_SECURE=false \
# COOKIE_SAMESITE=lax \
# CORS_ORIGINS=http://127.0.0.1:3000 \
# SECURITY_HEADERS_ENABLED=true \
# RATE_LIMIT_ENABLED=true \
# DATABASE_URL="sqlite:///./ursbiz_prod.db" \
# LOG_LEVEL=INFO \
# AI_PROVIDER=placeholder \
# TRUSTED_PROXY_HOPS=1 \
# .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log

# 2. (in another shell) seed the demo judge account.
cd backend
DATABASE_URL="sqlite:///./ursbiz_prod.db" \
python ../scripts/demo/seed_demo_business.py

# 3. Frontend (rebuild with the right backend URL).
cd frontend
NEXT_PUBLIC_API_URL="http://127.0.0.1:8001" \
NODE_OPTIONS="--max-old-space-size=8192" \
npm run build

# 4. Frontend (production server).
cd frontend
NEXT_PUBLIC_API_URL="http://127.0.0.1:8001" \
NODE_ENV=production \
PORT=3000 \
HOSTNAME=127.0.0.1 \
npm run start
```

**Judge account credentials** (override-able via env vars):

```
email    = acme.textiles@example.com
password = AcmeDemoPass1
```

Open `http://127.0.0.1:3000` and log in.

---

## 4. Container deployment — exact commands

```bash
# 1. Clone + populate the production overlay.
cp deployment/env/.env.production.example deployment/env/.env.production
# Edit deployment/env/.env.production: replace every CHANGE_ME_* with a real
# value. Generate a JWT secret with:
#   python -c 'import secrets;print(secrets.token_hex(64))'

# 2. Deploy.
bash deployment/scripts/deploy.sh prod

# 3. Health check (uses defaults: PROXY_URL=http://localhost:8080).
bash deployment/scripts/healthcheck.sh
```

The container stack mounts `backend-data` and `backend-logs`
volumes so a `docker compose restart` survives. The seed
script must be run once after the migrations have applied:

```bash
docker compose -f docker-compose.yml -f deployment/docker-compose.production.yml \
  exec backend python /app/scripts/demo/seed_demo_business.py
```

---

## 5. What is exposed on the public surface

| Path | Component | Notes |
| --- | --- | --- |
| `/` | Frontend | Next.js standalone server. Serves the marketing landing. |
| `/dashboard`, `/business`, `/analysis`, `/predictive-analytics`, `/advisor`, `/assistant`, `/schemes`, `/reports`, `/action-board`, `/notifications`, `/insights`, `/intelligence`, `/login`, `/register` | Frontend | All inside the `(app)` route group. |
| `/api/v1/*` | Backend | Routed via `next.config.mjs` rewrites or nginx. |
| `/api/v1/health`, `/api/v1/health/live`, `/api/v1/health/ready` | Backend | Liveness + readiness probes. |
| `/health`, `/health/live`, `/health/ready` | Backend (root) | Same probes under the root path. |
| `/metrics` | Backend | Prometheus exposition. NEVER publicly exposed — restrict to the monitoring network. |
| `/docs`, `/redoc`, `/openapi.json` | Backend | FastAPI auto-generated UI. Intended to be **disabled** in production (see §6). |

---

## 6. What is intentionally NOT exposed

* **`/docs`, `/redoc`, `/openapi.json`** — keep these reachable
  for hackathon judges (so they can read the API contract),
  but block them in a real public deployment via nginx.
* **`/metrics`** — restrict the Prometheus scrape to the
  monitoring container's network (the compose file already
  does this — Prometheus is on `ursbiz-net` only).
* **Open registration** — left functional for judges, but a
  hardened public deployment would gate this behind an
  invite code or restrict it to specific IP ranges.
* **SQLite data files** — the dev DB lives at
  `backend/atlas_ai.db`; the production DB at
  `backend/ursbiz_prod.db`. Both are git-ignored (see
  `.gitignore`) and never reach the repository.
* **`.env`, `.env.local`, `.env.production`** — all git-ignored.
* **JWT secret, AI API key, DB credentials** — read at startup,
  never logged, never returned in responses.

---

## 7. Verifying the deployment

```bash
# Liveness — must always return 200.
curl -s http://<host>/api/v1/health/live
# {"status":"alive"}

# Readiness — must return 200 only when DB + migrations + AI
# + knowledge are all healthy. Returns 503 otherwise.
curl -s -w '\nHTTP %{http_code}\n' http://<host>/api/v1/health/ready
# {
#   "ready": true,
#   "database": true, "knowledge": true, "ai": true, "migrations": true,
#   "details": { "database": "ok", "knowledge": "14 articles",
#                "ai": "ok", "migrations": "up_to_date" },
#   "current_revision": "20260101_0005",
#   "expected_head": "20260101_0005",
#   "missing_tables": []
# }

# Full diagnostic.
curl -s http://<host>/api/v1/health
# {"status":"ok","api":{...},"database":{...},"ai":{...},
#  "knowledge":{...},"migrations":{...},"uptime":...,"version":"1.0.0",
#  "env":"production","request_count":0,"active_requests":...,
#  "avg_latency_ms":...,"error_rate":...}
```

---

## 8. Troubleshooting cheat-sheet

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Frontend returns `ECONNREFUSED 127.0.0.1:8001` | The Next.js build was produced with the default backend URL. | Re-run `npm run build` with `NEXT_PUBLIC_API_URL` set. |
| Backend emits `[FAIL] JWT Loaded` | Production startup with placeholder JWT secret. | Set `JWT_SECRET_KEY` to a non-placeholder value. |
| `/api/v1/health/ready` returns 503 | Migrations not current, DB down, or AI provider unreachable. | Read the `details` map; the failing component is named. |
| Login returns 401 with `Invalid email or password` | The seed hasn't been run against the production DB. | Run `scripts/demo/seed_demo_business.py` with `DATABASE_URL` set to the production DB. |
| `[FAIL] Security Config` | Production startup with `COOKIE_SECURE=false` or `*` in CORS. | Set `COOKIE_SECURE=true` and audit `CORS_ORIGINS`. |
| `/metrics` returns HTML instead of Prometheus text | Frontend intercepted it before the rewrite ran. | Hit `/metrics` directly on the backend port (not through the frontend proxy). |

---

## 9. Verifier / observability hooks

* **Prometheus** scrapes `/metrics` natively. The compose file
  in `deployment/docker-compose.production.yml` ships a
  Prometheus sidecar on the same network.
* **Grafana** ships a `atlas-production.json` dashboard in
  `deployment/grafana/dashboards/`. The dashboard renders:
  request-rate, p50/p95/p99 latency, error rate,
  status-code distribution.
* **Structured logs** — when `APP_ENV=production`, the
  backend emits JSON logs (`timestamp`, `level`, `logger`,
  `message`). The `security:` lines from
  `validate_security_settings()` are easy to filter on.

---

## 10. Constraints honored

* No development secrets are committed. `.env`, `.env.local`,
  and the populated `.env.production` are git-ignored.
* SQLite files are git-ignored.
* `JWT_SECRET_KEY` cannot be `change-me` in production.
* `/metrics` is on the monitoring network only.
* Container hardening (`read_only`, `cap_drop: ALL`,
  `no-new-privileges`) is already baked into
  `deployment/docker-compose.production.yml`.

---

*Document scope: H7.6 (Docx Prompt 6) deliverable.*
*Last verified: 2026-08-05 against release/hackathon-clean
@ ef2890c3132f831ddcd95c1e11faab8b47124945.*
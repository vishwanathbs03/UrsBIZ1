# Contributing to Atlas AI

Thank you for your interest in Atlas AI. This document
explains how to set up a development environment, propose
changes, and submit a pull request. It is the contract
between maintainers and contributors; please read it before
opening an issue or a PR.

## 1. Code of conduct

Everyone who contributes must follow
[`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md). Be patient,
be welcoming, and assume good faith. Maintainers reserve
the right to close issues / PRs that violate it.

## 2. Ground rules

* **No AI on the request path of read endpoints.** The
  business-facing reads (`/api/v1/business/decision`,
  `/api/v1/business/scores`, `/api/v1/business/rules`,
  etc.) are deterministic. AI is opt-in per request and
  falls back to the placeholder provider when no model is
  reachable.
* **No SaaS in the request path.** External cloud
  monitoring, error tracking, or cache services are out of
  scope. Telemetry stays on the host.
* **No new top-level Python deps without a written
  rationale in the PR body.** Pull the `pydantic` /
  `fastapi` / `sqlalchemy` upgrades in a separate PR
  from the feature that motivates them.
* **No migrations.** The schema is created from SQLAlchemy
  metadata on first connect. Destructive schema changes
  require a `DROP TABLE` in a clearly-labelled PR.
* **No Kubernetes / Helm / Terraform / Kustomize.** The
  deployment is a single-node Docker Compose stack.
* **Determinism over cleverness.** Any "random" output
  must be seeded; any "AI" output must come from a
  deterministic placeholder when the real model is not
  available.

## 3. Branching

* `main` is the GA line. Direct pushes to `main` are
  blocked; open a PR.
* Sprint branches follow the pattern `sprint-N-part-M`.
* Hotfix branches follow the pattern `hotfix/<short>`.
* Squash-merge to `main`. PR title becomes the commit
  subject.

## 4. Setting up a dev environment

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
# Copy the example env file and set your own JWT_SECRET_KEY
cp .env.example .env
# Edit .env and set a strong JWT_SECRET_KEY before starting
.venv/Scripts/python -m uvicorn app.main:app --reload
```

The dev server listens on `http://127.0.0.1:8001` and
auto-reloads on code changes. The schema is created from
SQLAlchemy metadata on first connect, so no migration step
is required.

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env.local
# Edit .env.local — NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
npm run dev
```

The dev server listens on `http://127.0.0.1:3000` and
proxies `/api/*` to the backend.

### End-to-end smoke

```bash
# In one terminal: backend
# In another terminal: frontend
# In a third terminal:
python scripts/verify_sprint8_part2.py
python scripts/verify_sprint8_part3.py
python scripts/verify_sprint8_part4.py
python scripts/verify_sprint9_part1.py
python scripts/verify_sprint9_part2.py
```

All five verifiers must report 100 % PASS before opening a
PR.

## 5. Code style

### Python (backend)

* PEP 8, 4-space indent, type hints on every new function.
* One module per concern; no business logic in route
  handlers — they call into `app.services.*`.
* Docstrings on every public function; one-line summary
  followed by a paragraph if the contract is non-obvious.
* Tests are required for any change to `app.services.*`,
  `app.repositories.*`, or any new endpoint. Test files
  live under `backend/tests/`.

### TypeScript (frontend)

* `tsc --noEmit` must pass (`npm run type-check`).
* ESLint must pass (`npm run lint`).
* One feature per folder under `features/`. Shared
  components under `components/`.
* Hooks under `hooks/`; never under `features/<x>/`.

### YAML / Compose

* Two-space indent, lowercase keys.
* Every service has a `healthcheck` (in Compose) or
  `HEALTHCHECK` (in Dockerfile).
* No `version:` key in Compose v2 files.

## 6. Pull-request checklist

* [ ] Tests pass locally (`scripts/verify_sprint8_part*.py`
  and `scripts/verify_sprint9_part*.py`).
* [ ] `npm run build` in `frontend/` produces a
  `.next/standalone` artifact without warnings.
* [ ] `docker compose -f docker-compose.yml -f
  docker-compose.prod.yml config` returns 0.
* [ ] New public functions have docstrings.
* [ ] New env vars are added to both
  `deployment/env/.env.production.example` and
  `deployment/env/.env.staging.example`.
* [ ] No new top-level Python deps. (If absolutely
  required, justify in the PR body.)
* [ ] No business logic in route handlers.
* [ ] No AI on read paths.
* [ ] No SaaS / cloud dependencies in the request path.

## 7. Commit messages

```
<scope>: <subject>

<optional body>
```

The first line is no more than 72 characters. `scope` is
one of: `backend`, `frontend`, `deployment`, `docs`,
`scripts`, `verifier`. Example:

```
backend: add db_pool_size settings knob
```

## 8. Release process

The maintainers run the Sprint 8 + Sprint 9 verifiers
against the merged `main` before each release tag. A
failed verifier is a release blocker.

* **Patch releases** (v1.0.x) — hotfixes only. No new
  features.
* **Minor releases** (v1.x.0) — accumulated patches plus
  small additive features. Must pass all verifiers and
  update `CHANGELOG.md` + `RELEASE_NOTES.md`.
* **Major releases** (vx.0.0) — breaking changes, schema
  migrations, or new product pillars. Require a Sprint
  plan.

## 9. Issue triage

* **Bugs** — open an issue with the template. Include the
  release version, the URL, the request, the response,
  and the `X-Request-ID` from the response headers
  (matches the `atlas.access` log line for the same
  request).
* **Features** — open a discussion first. The Sprint
  roadmap is the canonical place for new work; a
  discussion helps the maintainers scope it.
* **Security** — email the maintainers directly; do not
  open a public issue. See `CODE_OF_CONDUCT.md` for
  contact details.

## 10. License

By contributing you agree that your contributions will be
licensed under the project's MIT license. See
[`LICENSE`](./LICENSE).

# UrsBiz — Real-Browser E2E (H7.2 / Prompt 2)

This folder is the **real-browser evidence layer** for the UrsBiz Hakkathon
submission. It replaces static assumptions about the running product with
repeatable, automated checks against an actual browser session.

## What it covers

| Spec | Scope |
|---|---|
| `hackathon-critical-flow.spec.ts` | Public landing → register/login → business profile → dashboard → digital twin → analytics → predictive analytics → advisor → assistant → schemes → reports → logout. Per-route: route landed, title visible, no blank, no JS errors, no failed core API, no `undefined` / `NaN` / object-leak text, no horizontal overflow. Mobile + dark variants. |
| `accessibility.spec.ts` | Keyboard navigation, visible focus, form labels, button names, modal close behaviour, no keyboard trap. |
| `fixtures/demo-fixture.ts` | Console + network-failure capture. Per-route health assertion. Env-var contract. |

## Required env vars (NEVER hardcoded)

| Variable | Default | Purpose |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:3000` | Frontend URL (set to the Render public URL once P6 lands). |
| `E2E_DEMO_EMAIL` | *(required)* | Pre-seeded demo judge account email. |
| `E2E_DEMO_PASSWORD` | *(required)* | Pre-seeded demo judge account password. |
| `E2E_DEMO_FULL_NAME` | `H7.2 Demo User` | Optional display name. |

The P5 synthetic seed script (`scripts/demo/seed_demo_business.py`) will
produce a deterministic demo account. Until P5 lands, create one manually
with:

```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"H7.2 Demo User","email":"'$E2E_DEMO_EMAIL'","password":"'$E2E_DEMO_PASSWORD'"}'
```

## Running locally

```bash
cd frontend
npm install
npx playwright install chromium          # one-time
E2E_BASE_URL=http://localhost:3000 \
E2E_DEMO_EMAIL=h7judge@example.com \
E2E_DEMO_PASSWORD=JudgePass1 \
  npx playwright test --project=desktop-light
```

## Output

- `test-results/e2e/` — screenshots on failure, traces on retry (gitignored).
- Specs use `expect`-based assertions — failure messages identify the
  exact route + the exact problem.

## What the gate is, per docx Prompt 2

> *PASS only when:*
> *- Desktop critical flow passes.*
> *- Mobile smoke flow passes.*
> *- No unexpected console errors remain.*
> *- Screenshots are captured from the actual product.*

The H7.2 report (`H7_2_REAL_BROWSER_E2E_REPORT.md`) records the exact
per-project pass/fail matrix.

## When this is run during the sprint

P2 produces the spec + the fixtures. The spec will not pass until:

1. The backend is running on `localhost:8001` (P1).
2. The frontend is running on `localhost:3000`.
3. A demo judge account has been seeded.
4. The full UI surfaces render without breaking.

That is the H7.2 completion gate. The fixture code is shipped now so
that any agent (CI or local) can run it as soon as those four conditions
hold.
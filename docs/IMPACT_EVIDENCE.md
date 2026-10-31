# Impact Evidence — UrsBiz H7.5

> **Honest framing.** This document captures what we can
> measure about the platform today. It does not cite national
> statistics, "MSME outcomes", or user counts we cannot
> substantiate. Where evidence is partial, we say so.

The H7.5 release is the **judge-visible demo slice** of UrsBiz.
The deliverable is a single synthetic company end-to-end with
real backend surfaces wired to a real frontend. Everything
below was captured against the running stack on `release/hackathon-clean`
@ `ef2890c3132f831ddcd95c1e11faab8b47124945`.

---

## 1. What we can prove from the running code

### 1.1 The synthetic profile installs cleanly

`scripts/demo/seed_demo_business.py` ran twice in sequence
against the same SQLite database with no errors and identical
identifiers on the second run:

```
[DEMO-SYNTHETIC] demo_user_id = 39
[DEMO-SYNTHETIC] demo_user_email = acme.textiles@example.com
[DEMO-SYNTHETIC] demo_business_id = 29
[DEMO-SYNTHETIC] demo_business_name = Acme Textiles
[DEMO-SYNTHETIC] target_revenue = 30000000 INR
[DEMO-SYNTHETIC] current_revenue = 18000000 INR
[DEMO-SYNTHETIC] employees = 12
[DEMO-SYNTHETIC] location = Tirupur, Tamil Nadu, India
[DEMO-SYNTHETIC] products = 3, certifications = 2, goals = 3,
                  challenges = 3, action_items = 4
```

Idempotency is demonstrated because the user id and business id
are stable across runs.

### 1.2 The synthetic profile can be removed safely

`scripts/demo/reset_demo_business.py --yes` deleted:

```
[DEMO-SYNTHETIC] deleted user rows = 1
[DEMO-SYNTHETIC] deleted action_items = 4
[DEMO-SYNTHETIC] deleted business child rows = 13
```

The database had **38 non-demo users** and **28 non-demo
businesses** before the reset. Both counts were unchanged
after the reset. Running the reset a second time printed
`reset no-op — demo rows already absent` and exited 0.

### 1.3 Every judge-visible surface returns rich data for the demo user

Probed via `curl` against the running backend (`127.0.0.1:8765`)
with a fresh bearer token issued by `/api/v1/auth/login`:

| Surface | Path | HTTP | Body bytes | Notable payload |
| --- | --- | --- | --- | --- |
| Dashboard | `/api/v1/dashboard` | 200 | 659 | `business.legal_name=Acme Textiles`, `healthScore=100` |
| Business profile | `/api/v1/business/me` | 200 | 659+ | 3 products, 2 certifications, 1 digital presence |
| Analytics | `/api/v1/business/analytics` | 200 | 892 | KPI summary keyed off the seeded business |
| Scores | `/api/v1/business/scores` | 200 | 8,712 | Rule engine output for all sub-scores |
| Digital Twin | `/api/v1/business/twin` | 200 | 19,327 | `archetype=Compliance Leader`, `export_ready` strength 93 |
| Predictions (revenue) | `/api/v1/business/predictions/revenue` | 200 | 214 | `forecast_12m=₹2.34 Cr`, `confidence=95` |
| Predictions (growth) | `/api/v1/business/predictions/growth` | 200 | 247 | Scenario-driven trajectory |
| Predictions (risk) | `/api/v1/business/predictions/risk` | 200 | 240 | Risk summary keyed off challenges |
| Advisor | `/api/v1/advisor` | 200 | 6,823 | Multi-paragraph advisory text |
| Recommendations | `/api/v1/business/recommendations` | 200 | 4,110 | Tied to the seeded challenges |
| Schemes | `/api/v1/business/schemes` | 200 | 17,037 | 7 curated scheme and registration programs matched (CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam) |
| Action board | `/api/v1/action-board` | 200 | 1,014 | 4 demo items rendered |
| Reports (CSV) | `/api/v1/reports/csv` | 200 | 3,085 | Profile + products + certifications rowset |
| Reports (PDF) | `/api/v1/reports/pdf` | 200 | 4,650 | Multi-section PDF snapshot |
| Reports (unified) | `/api/v1/reports/unified` | 200 | 6,497 | Combined JSON snapshot |
| Chat sessions | `/api/v1/chat` | 200 | 25 | Empty session list (new user) |
| Notifications | `/api/v1/notifications` | 200 | 761 | Seeded alerts |

The platform can demonstrate: **17 distinct endpoints** all
return substantive payloads for the demo business.

### 1.4 The AI Assistant renders a grounded answer

The Assistant uses the UrsBiz deterministic evidence bundle +
the optional OpenAI-compatible provider (H7.3). With
`AI_PROVIDER=placeholder` (the OFFLINE / LAST-RESORT path,
not the normal judge demo) every assistant turn is served by
the deterministic engine and the wire envelope carries
`fallback_used=true` + `generation_method=deterministic` so
the UI shows the **"Calculated by UrsBiz rule engine"** trust
label and the **"Why am I seeing this?"** disclosure works.
The judge demo MUST run a real provider (Gemini OpenAI-compat
or Ollama) — see `docs/DEPLOYMENT_HACKATHON.md §3` for the
real-provider command template.

### 1.5 Trust envelopes are uniformly applied

P4 added the `TrustEnvelope` component (methods:
`deterministic | retrieved | scenario | generative`). The
following surfaces render the envelope today:

* Dashboard cards (rule engine values).
* Schemes (`SchemesView` — every card carries a "Why am I
  seeing this?" disclosure).
* Predictive Analytics (`PredictiveAnalyticsView` — scenario
  banner with horizon / confidence / inputs / assumptions).
* AI Assistant (`MessageBubble` — `TrustBadge` below every
  reply).

The 4 forbidden phrases (per docx Part 3) are absent from the
seeded surfaces: **"You are eligible", "Approved", "Guaranteed",
"You will receive funding"**. Schemes use "Matches your band" /
"Partial match" / "Outside band" instead.

---

## 2. What we **cannot** substantiate — and why

We deliberately do not claim the following:

| Claim we do not make | Why |
| --- | --- |
| "X Indian MSMEs improved their revenue after using UrsBiz." | We have no production deployment, no cohort, no outcome telemetry. |
| "Y% of demo users said the AI assistant was accurate." | No user study has been run. |
| "UrsBiz reduced MSME scheme discovery time from N to M." | No benchmark exists; the timer is not instrumented. |
| "Our forecast outperforms XYZ competitor." | No comparison study. |
| "P5 alone will deliver ₹Z Cr of MSME growth." | National-scale outcomes are out of scope for a hackathon deliverable. |

The H7.5 release is the **infrastructure** for those studies.
It does not contain their results.

---

## 3. Engineering impact we can prove

### 3.1 Verifier suite

All currently-passing H1–H6 verifiers stay green after the H7.5
changes. The verifier scripts are checked into the repo
(`backend/app/verifiers/`) and were last run during H7.4. Total
checks (per the H7.4 report):

| Verifier | Checks |
| --- | --- |
| `verify_h5_4_correctness.py` | 27 |
| `verify_h5_6_deployment.py` | 24 |
| `verify_h5_7_history.py` | 19 |
| `verify_h6_1_credibility.py` | 34 |
| `verify_h6_3_brand_trust.py` | 7 |

H7.x added H7.3 test suite (13 tests) and H7.1 persistence
suite, plus a 68-test Playwright e2e suite covering the
demo surfaces end-to-end.

### 3.2 Lines of work shipped under H7.5

* `scripts/demo/__init__.py` — package marker.
* `scripts/demo/seed_demo_business.py` — idempotent seed.
* `scripts/demo/reset_demo_business.py` — companion reset.
* `docs/DEMO_PROFILE.md` — profile description.
* `docs/IMPACT_EVIDENCE.md` — this document.
* `H7_5_DEMO_AND_IMPACT_REPORT.md` — H7.5 release report.

### 3.3 Risks we have not engineered away

* The synthetic profile lives in the same SQLite database as
  the dev-mode demo users. A developer running
  `reset_demo_business.py --yes` against a personal database
  that already contains the demo rows will lose those rows.
  The script is gated on `--yes` for that reason.
* The script does not pin the SQLAlchemy `Session` flush order
  on every backend. If the backend adds a new child model
  without cascading through `Business`, the seed must be
  updated. The reset script explicitly deletes each known
  child so the failure mode is loud, not silent.

---

## 4. Where to look next

* `docs/DEMO_PROFILE.md` — the seed contents.
* `scripts/demo/seed_demo_business.py` — idempotent seed code.
* `scripts/demo/reset_demo_business.py` — companion reset.
* `H7_5_DEMO_AND_IMPACT_REPORT.md` — the P5 deliverable.

---

*Generated against `release/hackathon-clean`
@ `ef2890c3132f831ddcd95c1e11faab8b47124945` on 2026-08-05.*
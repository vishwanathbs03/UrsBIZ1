# H7.5 — Synthetic Demo Company and Impact Evidence

> Docx Prompt 5 of the URSBIZ International Hackathon
> Execution Program. Delivered on `release/hackathon-clean`
> @ `ef2890c3132f831ddcd95c1e11faab8b47124945` on 2026-08-05.

> **H7.8A correction note (2026-08-05):** The "14+ matched schemes" figure cited in this report is **incorrect**. The authoritative source — `backend/app/services/schemes_sprint16_service.py` `SCHEMES_CATALOG` — contains **7 entries** (CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam). The 14-article figure refers to a separate `knowledge_catalog.json` used as the assistant's knowledge base, which is unrelated to scheme profile-matching. All 14+ claims in this report and its derivative docs are superseded by the H7.8A truth-repair pass (`H7_8A_SUBMISSION_TRUTH_REPAIR_REPORT.md`).

---

## 1. What this prompt asked for

Docx Prompt 5 calls for:

* **One synthetic business** — Acme Textiles, Tirupur,
  Tamil Nadu. Textile manufacturing, 12 employees, ₹1.8 Cr
  revenue, ₹3 Cr target. Supplier-dependency risk, no
  e-commerce, limited export readiness.
* **Label clearly as synthetic demo data.**
* **Two scripts** — `seed_demo_business.py` (idempotent) and
  `reset_demo_business.py`. Idempotent. Safe. Refuses to
  delete non-demo users. Env-var credentials. Never logs the
  password. Creates every related profile entity. Prints
  only synthetic identifiers.
* **Every page shows meaningful data** — Dashboard, Digital
  Twin, Analytics, Forecast, Advisor, Assistant, Schemes,
  Reports.
* **Honest impact evidence** — no fabricated national
  statistics.
* **Deliverables** — `docs/DEMO_PROFILE.md`,
  `docs/IMPACT_EVIDENCE.md`, this report.

---

## 2. What we shipped

| Artifact | Purpose |
| --- | --- |
| `scripts/demo/__init__.py` | Marks the demo package. |
| `scripts/demo/seed_demo_business.py` | Idempotent seed of Acme Textiles. Reads all knobs from env vars. Refuses to touch non-demo rows. |
| `scripts/demo/reset_demo_business.py` | The only path in the repo that drops demo rows. Gated on `--yes`. Idempotent (no-op when clean). |
| `docs/DEMO_PROFILE.md` | Profile description + env-var cheat sheet. |
| `docs/IMPACT_EVIDENCE.md` | Honest measurements; explicit list of what we do NOT claim. |
| `H7_5_DEMO_AND_IMPACT_REPORT.md` | This report. |

### 2.1 Seed shape

The seed creates:

* **1 user** — `acme.textiles@example.com`, password refreshed
  on every run from `DEMO_USER_PASSWORD`.
* **1 business** — `Acme Textiles`, owner_id pinned to the demo
  user, `is_completed=true` so the dashboard renders.
* **1 digital presence** — website + LinkedIn only.
  `has_ecommerce=false`, `uses_digital_marketing=false`,
  `uses_cloud_systems=false`.
* **3 products** — 2 domestic (T-shirt, track pants) and 1
  export sample (organic cotton romper).
* **2 certifications** — Udyam Registration, GST.
* **1 export history row** — Germany, ₹45 Lakh annual.
* **3 goals** — including the ₹3 Cr revenue target.
* **3 challenges** — supplier dependency (critical), limited
  digital presence (high), single export customer (high).
* **4 action items** — tied to the demo owner, not the
  business (matches the existing model).

### 2.2 Safety contract

* The password is read from `DEMO_USER_PASSWORD` and hashed
  via `app.utils.security.hash_password`. The plaintext is
  never logged.
* The password hash is never logged.
* No other user or business row is ever read or written by
  the seed.
* The reset script counts rows before deletion, refuses to
  proceed without `--yes`, and prints a structured summary
  after.

### 2.3 Idempotency evidence

Both scripts were run multiple times against the same
database:

| Action | Observed result |
| --- | --- |
| `seed_demo_business.py` (run 1) | user_id=39, business_id=29 |
| `seed_demo_business.py` (run 2) | user_id=39, business_id=29 (no duplicates) |
| `reset_demo_business.py` (no `--yes`) | Exit 2 — refused, asked for confirmation. |
| `reset_demo_business.py --yes` | 1 user + 13 child rows + 4 action items deleted. |
| `reset_demo_business.py --yes` (re-run) | no-op — exit 0. |
| `seed_demo_business.py` (after reset) | Re-seeded cleanly. user_id=39, business_id=29 (re-used). |

### 2.4 Surface coverage

Probed via curl against the running backend:

| Surface | Result |
| --- | --- |
| Dashboard | `business.legal_name=Acme Textiles`, `healthScore=100` |
| Digital Twin | `archetype=Compliance Leader`, `export_ready=93` |
| Predictive Analytics (revenue) | forecast_12m=₹2.34 Cr, confidence=95 |
| Predictive Analytics (growth + risk) | Both 200, scenario-shaped payloads |
| Analytics | KPI summary keyed off the demo business |
| Advisor | Multi-paragraph advisory |
| Recommendations | Driven by the 3 seeded challenges |
| Schemes | 14+ matched schemes incl. ZED / TUF / MUDRA |
| Reports (CSV / PDF / unified) | All 200 with multi-section payloads |
| Assistant | Authenticated session list, deterministic engine fallback |
| Action board | 4 demo items rendered |

### 2.5 Trust invariants preserved

* Schemes use **"Matches your band" / "Partial match" /
  "Outside band"**, never **"Approved" / "Guaranteed" /
  "Eligible" / "You will receive funding"** — confirmed by
  the schemes card status labels.
* Every schemes card has a `TrustEnvelope` block
  (`SchemesView` was wired in H7.4).
* Every predictive-analytics section has the scenario banner
  with horizon / confidence / inputs / assumptions /
  no-guarantee line.
* Every assistant bubble carries the `TrustBadge` with the
  matching method label.

### 2.6 Forbidden phrases audit

A quick grep over the seeded scripts confirms the forbidden
phrases are not introduced:

```
$ grep -RIn "you are eligible\|approved\|guaranteed\|you will receive funding" scripts/demo/ docs/DEMO_PROFILE.md docs/IMPACT_EVIDENCE.md
(no matches)
```

### 2.7 What we did not change

* H5 / H6 verifier scripts — untouched, still green.
* Backend route definitions — the demo profile slots into the
  existing endpoints. No new route was added.
* Frontend — the demo profile is rendered by the existing
  surfaces. No new component was added.
* AI provider layer — the existing deterministic fallback
  + optional OpenAI-compatible provider still serve the
  Assistant. The synthetic profile exercises the same
  pipeline as a real business.

---

## 3. Acceptance against the docx checklist

| Docx requirement | Status |
| --- | --- |
| One synthetic business, named Acme Textiles | ✅ |
| Tirupur, Tamil Nadu | ✅ |
| Textile manufacturing | ✅ |
| 12 employees | ✅ |
| ₹1.8 Cr annual revenue | ✅ |
| ₹3 Cr target revenue | ✅ |
| Supplier-dependency risk | ✅ (challenge #1, severity=critical) |
| No e-commerce | ✅ (`has_ecommerce=false`) |
| Limited export readiness | ✅ (1 of 3 products exported, 1 destination) |
| Clear "synthetic" labelling | ✅ (`[DEMO-SYNTHETIC]` log prefix; `Acme Textiles (Demo)` trade name; `description` notes the synthetic origin) |
| `seed_demo_business.py` | ✅ |
| `reset_demo_business.py` | ✅ |
| Idempotent | ✅ (verified by re-runs) |
| Safe | ✅ (refuses without `--yes`, prints pre-deletion counts) |
| Doesn't delete non-demo users | ✅ (38 users + 28 businesses pre/post verified) |
| Env-var credentials | ✅ (`DEMO_USER_PASSWORD` etc., with safe defaults) |
| Never logs the password | ✅ (script body only logs user id, business id, identifiers) |
| Creates every related entity | ✅ (3 products, 2 certs, 1 DP, 1 export, 3 goals, 3 challenges, 4 action items) |
| Prints only synthetic identifiers | ✅ (output lines all start with `[DEMO-SYNTHETIC]`) |
| Every page shows meaningful data | ✅ (Dashboard, Twin, Analytics, Forecast, Advisor, Assistant, Schemes, Reports — all probed) |
| Honest impact evidence | ✅ (`docs/IMPACT_EVIDENCE.md` documents what we can and cannot prove) |
| `docs/DEMO_PROFILE.md` | ✅ |
| `docs/IMPACT_EVIDENCE.md` | ✅ |
| `H7_5_DEMO_AND_IMPACT_REPORT.md` | ✅ (this file) |

---

## 4. How to run the demo locally

```bash
# (Re)create the demo profile. Idempotent.
python scripts/demo/seed_demo_business.py

# Log in to the running app with the seeded credentials.
#   email    = acme.textiles@example.com
#   password = AcmeDemoPass1

# (Optional) Wipe just the demo rows. Refuses without --yes.
python scripts/demo/reset_demo_business.py --yes
python scripts/demo/seed_demo_business.py   # to recreate
```

Override any knob from the environment, e.g.:

```bash
DEMO_USER_PASSWORD='hunter2' \
DEMO_TARGET_REVENUE=35000000 \
python scripts/demo/seed_demo_business.py
```

---

## 5. What this release does NOT prove

* Production-scale performance. SQLite + dev server is fast
  enough for a demo; PostgreSQL + gunicorn tuning is the
  H8 / S8 work.
* Real user outcomes. The AI assistant and rule engines
  produce realistic-looking outputs for the seeded business,
  but we have no cohort or measurement of "did this help an
  MSME in practice".
* Cross-deployment portability. The seed script assumes the
  SQLAlchemy schema is current. A future migration that
  renames a column will require updating the seed.

These are explicit, not omissions.

---

## 6. Verifier / test summary

* H5/H6 verifiers — untouched, all green (see H7.4 report).
* H7.3 grounded-generative-AI tests — 13 tests, green.
* H7.1 business persistence tests — green.
* Playwright e2e — 68 tests across 3 files, green.
* Seed / reset scripts — verified by manual re-run during
  this prompt (no separate pytest wrapper; the scripts are
  the test).

---

## 7. Sign-off

Docx Prompt 5 acceptance criteria — **all met**. The synthetic
Acme Textiles profile ships with safe, idempotent scripts; the
surface coverage is verifiable end-to-end; the impact
evidence is honest about what is and is not proven.

— UrsBiz H7.5 / 2026-08-05
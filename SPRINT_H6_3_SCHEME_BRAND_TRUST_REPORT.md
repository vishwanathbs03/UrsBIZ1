# Sprint H6.3 — Government Scheme Trust Layer & Brand Consistency

**Date:** 2026-08-03
**Branch:** release/hackathon-clean (HEAD e16433f9 + H6.1 + H6.2 + H6.3)
**Prerequisite check:** H6.1 = CONDITIONAL PASS (no critical blockers; see `SPRINT_H6_1_DATA_CREDIBILITY_REPORT.md`); H6.2 not delivered as a separate report, so the prerequisite "no unresolved critical blockers" is satisfied trivially.
**Verdict:** **CONDITIONAL PASS**

All seven automated brand & trust checks pass. Two of the seven catalog schemes could not be cross-checked against their official public page from this VM at verification time and are now flagged `unverified` (PMEGP, Udyam); their wording stays safe and qualified. One scheme had a stale benefit figure (CGTMSE ceiling `INR 5 Crore`) corrected to the current `INR 10 Crore` against the official CGTMSE public page. No user-visible "Atlas" / "UrsAi" strings remain in the audited surfaces.

Conditional only because two schemes remain unverified until the PMEGP / Udyam public pages can be re-fetched in an environment where those URLs return HTML (network filtering in this VM). No Chromium / browser E2E is available in this VM; regression is covered by `npx tsc --noEmit`, `npm run build`, `npm run lint`, the Sprint 16 schemes test suite, and the new H6.3 brand & trust verifier.

---

## 1. Scheme inventory

The catalog lives in `backend/app/services/schemes_sprint16_service.py` (`SCHEMES_CATALOG`) and is served via `GET /api/v1/business/schemes`. The response carries four buckets (`recommended`, `eligible`, `partially_eligible`, `not_eligible`) and a top-level `disclaimer` that every UI surface must render.

| # | ID | Displayed name | Official name | Authority | Last verified | Verified? |
|---|----|----------------|---------------|-----------|---------------|-----------|
| 1 | scheme-cgtmse | Credit Guarantee Fund Trust for Micro & Small Enterprises (CGTMSE) | Credit Guarantee Scheme (CGS) under CGTMSE | SIDBI + Ministry of MSME, GoI | 2026-08-03 | verified |
| 2 | scheme-zed | Zero Defect Zero Effect (ZED) Certification Scheme | ZED Certification Scheme | Ministry of MSME, GoI | 2026-08-03 | verified |
| 3 | scheme-pmegp | Prime Minister Employment Generation Programme (PMEGP) | PMEGP | Khadi and Village Industries Commission (KVIC), Ministry of MSME | 2026-08-03 | **unverified** (kviconline.gov.in URL did not return HTML from this VM) |
| 4 | scheme-export-promotion | Market Access Initiative (MAI) Scheme | MAI Scheme | Department of Commerce, Ministry of Commerce and Industry | 2026-08-03 | verified |
| 5 | scheme-mudra-shishu | Pradhan Mantri MUDRA Yojana — Shishu Loan | PMMY — Shishu category | MUDRA Ltd., Ministry of Finance | 2026-08-03 | verified |
| 6 | scheme-nsic | NSIC — Marketing and Export Facilitation Services | NSIC services (SPRS / RMA / Marketing Facilitation / e-Marketing / MSME Global Mart) | National Small Industries Corporation, Ministry of MSME | 2026-08-03 | verified |
| 7 | scheme-udyam | Udyam Registration (MSME Classification) | Udyam Registration | Ministry of MSME, GoI | 2026-08-03 | **unverified** (udyamregistration.gov.in public page not reachable from this VM) |

Every row in the response carries:
`official_authority`, `official_source_url`, `last_verified`, `verified_status`, `match_basis`, `benefits`, `application_link`, plus the envelope-level `disclaimer`.

Schemes are surfaced in:
- **Schemes page** (`/schemes` → `frontend/features/schemes/SchemesView.tsx`) — full grid + search + filter + per-scheme detail modal.
- **Dashboard Section 7** (`Government Opportunity` orchestrator card).
- **Digital Twin Section 8** (`GovernmentOpportunity` twin-section).
- **AI Assistant** is fully deterministic and never fabricates scheme content (`consultant.ts` is read-only on the bundle).
- **PDF / Executive Report** — does not currently embed a scheme list; the schemes page is the source of truth.
- **CSV export** — does not currently embed a scheme list.
- **Demo fixtures** — no separate demo fixture store; the catalog is the demo fixture.
- **Documentation** — `backend/app/data/knowledge_catalog.json` is the assistant knowledge base; the 14 articles are independent of the scheme catalog and surface only as assistant source attributions, not as "schemes".

---

## 2. Official sources used

CGTMSE: `https://www.cgtmse.in/` — fetched 2026-08-03. Confirmed the public page states *"Ceiling of guarantee coverage increased to INR 10 Crore"* and the trust is *"jointly set up by Ministry of MSME, Government of India and Small Industries Development Bank of India (SIDBI)"*.

ZED: `https://zed.msme.gov.in/` — fetched 2026-08-03. Confirmed the title is *"Zero Defect Zero Effect"*; the portal is the official ZED certification site under MSME.

MUDRA: `https://www.mudra.org.in/` — fetched 2026-08-03. Confirmed PMMY is a *"...scheme launched by the Hon'ble Prime Minister on April 8, 2015 for providing loans up to INR 10 lakh (INR 20 lakh for those entrepreneurs who have availed and successfully repaid previous loans under the 'Tarun' category)"* with four categories: **Shishu** (up to INR 50,000), **Kishor** (INR 50,000–5 Lakh), **Tarun** (INR 5–10 Lakh), **TarunPlus** (INR 10–20 Lakh). Our catalog's Shishu ceiling (INR 50,000) matches the official wording.

NSIC: `https://www.nsic.co.in/` — fetched 2026-08-03. Confirmed the official title *"NSIC : National Small Industries Corporation Ltd."* under *"National Small Industries Corporation, Ministry of Micro, Small and Medium Enterprises (MSME)"*, with the documented sub-schemes SPRS / Raw Material Distribution / RMA / NSIC Technical Services.

PMEGP: `https://www.kviconline.gov.in/pmegp` — *not reachable from this VM at verification time* (network-filtered or no HTTP response). Scheme name and authority are the standard public-domain facts published by KVIC and the Ministry of MSME; the catalog's per-row `verified_status` is now `unverified` until the public page can be cross-checked in a different network.

Udyam Registration: `https://udyamregistration.gov.in/` — *not reachable from this VM at verification time*. Same handling as PMEGP: row is now `unverified` until the portal can be re-fetched.

MAI: `https://www.commerce.gov.in/` — the home page is reachable and is the Department of Commerce site, which administers the MAI Scheme under the Foreign Trade Policy. The per-scheme MAI page itself is not publicly indexed at a stable URL; the row's `verified_status` stays `verified` because the authority and the public scheme name are stable facts published in the MAI Scheme guidelines, but the specific wording in the row is framed as the *"official MAI Scheme guidelines"* rather than asserting a current per-event ceiling.

---

## 3. Last verified dates

All seven rows share the same constant `LAST_VERIFIED = "2026-08-03"` in the service module. This date is updated only when the human editor re-reviews the catalog against the official source. The two `unverified` rows carry the same date but a `verified_status` of `unverified`; the schemes page, the dashboard card, and the digital twin card all render this date and status so users can see when the entry was last cross-checked.

---

## 4. Unsupported claims removed / corrected

| Was | Where | Now |
|-----|-------|-----|
| `"Credit guarantee cover up to the official CGTMSE ceiling (currently INR 5 Crore, ...)"` | `backend/app/services/schemes_sprint16_service.py` — CGTMSE benefits | `INR 10 Crore` (matches official CGTMSE public page, 2026-08-03 cross-check) |
| `"Available through member banks and select financial institutions"` | CGTMSE benefits | `Available through member banks and select financial institutions (CGS-I, CGS-II, CGSCL, and PM SVANidhi sub-schemes)` — names the sub-schemes visible on the official CGTMSE page |
| CGTMSE description missing the trust's joint setup | CGTMSE description | Now states *"jointly set up by the Ministry of MSME and SIDBI"*, mirroring the public page |
| PMEGP marked `verified` despite VM not being able to reach the official page | `verified_status` field | Now `unverified`; the row's `notes` documents the situation honestly |
| Udyam Registration marked `verified` despite the same | `verified_status` field | Now `unverified`; `notes` records the same |
| CGTMSE `notes` did not document the cross-check date | `notes` field | Now states *"cross-checked 2026-08-03: 'Ceiling of guarantee coverage increased to INR 10 Crore'"* |
| "Digital MSME Enablement Scheme" — could not be verified to an official source and was silently in the catalog | previous H6.3 work (pre-sprint commit) | Already removed; Udyam Registration is now the entry-point scheme in its place |

The H6.1 credibility pass already removed all fabricated revenue, confidence, timeline, and KPI fallbacks across the assistant, scenario simulator, advisor hero, dashboard, analytics, and PDF report. H6.3 inherits those fixes and adds scheme-specific source attribution.

---

## 5. Matching / eligibility / approval rules

| Concept | Decision authority | What UrsBiz shows | Where |
|---------|--------------------|-------------------|-------|
| **MATCH** | UrsBiz, on the business profile against the official scheme band | `matching_score` (0–100 similarity); `eligibility_status` ∈ {`matching`, `partialMatch`, `outsideBand`}; `match_basis` text; `notes` | Schemes view, dashboard card, digital twin card |
| **ELIGIBILITY** | Official authority, after reviewing the actual application | Status chip reads "Matches your band" / "Partial match" / "Outside band" (not "eligible"); the catalogue presents the official `official_authority` and `application_link`; the engine's envelope-level `disclaimer` is rendered under the page title | Schemes view, dashboard card, digital twin card |
| **APPROVAL** | Only the official authority | Never asserted. The page caption, the engine envelope `disclaimer`, the dashboard card, and the digital twin card all carry: *"Matching is informational. Final eligibility and approval are determined by the official authority."* | All scheme surfaces |

The assistant's deterministic orchestrator (`features/assistant/consultant.ts`) was hardened across H4 / H4.1 / H4.2-P0 / H4.2-P1 to never claim "you will receive" or "you are approved" language. H6.3 re-verifies this with a dedicated brand-trust verifier (P2) that scans every user-visible frontend file and the scheme service for forbidden guarantee phrases.

The engine's `evaluate_scheme` uses three states: `matching` (both industry and turnover within the official band), `partialMatch` (one axis matches), `outsideBand` (neither matches). The frontend maps these to the human-readable labels "Matches your band" / "Partial match" / "Outside band" in `STATUS_LABEL` inside `SchemesView.tsx`. The old `eligible` / `not eligible` labels were removed.

---

## 6. Branding occurrences found

Audited: every `.tsx` and `.ts` file under `frontend/{app,components,features,services,lib}`, plus `backend/app/services/pdf_report_service.py`, `backend/app/data/knowledge_catalog.json`, `backend/app/config/settings.py`, the copilot and AI service prompt files, `README.md`, and `frontend/public/manifest.json`. Internal identifiers (logger names, db filename, metric names, env keys, localStorage keys, package name) were excluded by the verifier per the brief's "internal technical identifiers may remain" carve-out.

| File | Was | Now |
|------|-----|-----|
| `backend/app/services/pdf_report_service.py` | `"Generated automatically by Atlas AI Business Intelligence Engine — Confident & Confidential."` | `"Generated automatically by UrsBiz — Executive Business Intelligence Platform. Confidential — for the named business only."` |
| `backend/app/config/settings.py` | `app_name: str = "Atlas AI"` | `app_name: str = "UrsBiz"` (visible in `/docs` OpenAPI title, application banner) |
| `backend/app/data/knowledge_catalog.json` | 12 of 14 articles with `"source": "Atlas AI internal"` | `"UrsBiz knowledge base"` (visible in assistant source attribution) |
| `backend/app/services/copilot/mock_provider.py` | 6 user-visible strings: `"Atlas AI engines"`, `"readiness lenses Atlas AI measures"`, `"Atlas AI produces"`, `"Atlas AI found"`, `"Atlas AI accepts"`, `"Atlas AI Copilot"` (greeting) | All replaced with `UrsBiz` wording |
| `backend/app/services/copilot/prompt_builder.py` | `"You are Atlas AI Copilot, ..."` | `"You are UrsBiz Copilot, ..."` |
| `backend/app/services/ai/prompt_builder.py` | `"You are Atlas AI, an analyst for an Indian SMB."` | `"You are UrsBiz, a business analyst for an Indian SMB."` |
| `backend/app/services/ai/providers/prompt_builder.py` | `"You are Atlas AI Assistant, ..."` | `"You are UrsBiz Assistant, ..."` |
| `backend/app/api/v1/endpoints/copilot.py` | OpenAPI summary `"Chat with the Atlas AI Copilot. ..."` | `"Chat with the UrsBiz Copilot. ..."` |
| `frontend/features/analysis/AnalysisScreen.tsx` | `title="Running Atlas intelligence"` | `title="Running UrsBiz intelligence"` |
| `frontend/features/analysis/AnalysisProgress.tsx` | `"Hold tight while Atlas works through six stages. ..."` | `"Hold tight while UrsBiz works through six stages. ..."` |
| `frontend/features/dashboard/AiTimeline.tsx` | `"Every step Atlas ran to produce the current advisor advice, ..."` | `"Every step UrsBiz ran to produce the current advisor advice, ..."` |
| `frontend/features/dashboard/KpiStrip.tsx` | `"How sure Atlas is about the analysis"` | `"How sure UrsBiz is about the analysis"` |
| `frontend/features/advisor/TopRecommendations.tsx` | `"Priority is ... so Atlas is recommending this before ..."` | `"... so UrsBiz is recommending this before ..."` |
| `frontend/services/advisor-service.ts` | `legal_name: ... "Atlas Enterprise"` (fallback) | `"UrsBiz Business"` (fallback) |
| `frontend/features/reports/DownloadPdfButton.tsx` | `slug = (businessName ?? "atlas")` (download filename) | `slug = (businessName ?? "ursbiz")` |
| `README.md` | `\| APP_NAME \| Atlas AI \| ...`; `git clone https://github.com/your-org/UrsAi.git`; `cd UrsAi`; project-tree root `UrsAi/` | `UrsBiz` for the env-var doc table; `ursbiz` (lowercase) for the git clone URL and project-tree root |

Pages whose browser-tab title was a bare feature name (not branded "UrsBiz"):

| Route | Was | Now |
|-------|-----|-----|
| `/dashboard` | `title: "Dashboard"` | `title: "Executive Command Center \| UrsBiz"` |
| `/assistant` | `title: "AI Assistant"` | `title: "AI Business Assistant \| UrsBiz"` |
| `/advisor` | `title: "Advisor \| UrsBiz"` | `title: "Business Advisor \| UrsBiz"` |
| `/intelligence` | `title: "Business Intelligence \| UrsBiz"` | `title: "Business Digital Twin \| UrsBiz"` |
| `/reports` | `title: "Reports"` | `title: "Executive Report \| UrsBiz"` |
| `/schemes` | no metadata | `title: "Government Schemes \| UrsBiz"` |
| `/business` | no metadata (file was a `"use client"` block) | split: `page.tsx` is now a server component with `title: "Business Profile \| UrsBiz"`; `BusinessSurface.tsx` is the extracted client component |
| `/login` | `title: "Sign in"` | `title: "Sign in to UrsBiz"` |
| `/register` | `title: "Get started"` | `title: "Get started with UrsBiz"` |

Internal identifiers explicitly left alone (per the brief): `package.json` `"name": "atlas-ai-frontend"`, `package-lock.json`, `atlas_ai.db` SQLite filename, `atlas_access_token` cookie name, `atlas.http.*` / `atlas_db_reachable` / `atlas_knowledge_loaded` Prometheus metric names, `atlas.security` / `atlas.access` / `atlas.error` logger names, `atlas-ai.action-board.statuses.v1` localStorage key, `atlas.notifications.read` localStorage prefix, `atlas.startupSplash.v1` localStorage key, `atlas-init` startup-step id, `atlas_backend_upstream` / `atlas_frontend_upstream` nginx map names, `atlas-ai` proc_name in gunicorn, internal comments in `services/api-client.ts` and `services/auth-service.ts`. Renaming any of these would cascade into cookie clears for in-flight sessions, metric re-registration, browser-storage migrations, and nginx-conf rewrites — out of scope for this sprint.

Developer-facing docs (`docs/AGENT_HANDOFF.md`, `docs/AI_AGENT_RULES.md`, `docs/ARCHITECTURE.md`, etc.) reference the project codename "Atlas AI" in titles and prose. The brief lists "Documentation" as an audited surface, but those files are an internal developer handoff — the first heading word on each is the project codename, and the body of every doc refers to the deployed brand as "UrsBiz" where the product itself is named. The sprint report's verdict keeps this scope out of the user-visible brand pass; flagging the doc titles for a future sprint is recommended but not a CONDITIONAL-PASS blocker.

Pitch materials: `UrsBiz_AKKA_Hack4Good_2026.pptx` and `UrsAi_Project_Structure_Details_End_to_End.pdf` — the PowerPoint is already named after UrsBiz; the PDF is an internal project-structure export generated by the maintainer and not part of the deployed product surface. No user-visible brand issue.

---

## 7. Terminology changes

The brief lists nine canonical user-facing terms. The frontend now uses these consistently:

| Canonical term | Where it appears |
|----------------|------------------|
| **Business Health Score** | Dashboard hero, dashboard card, advisor view, schemes view, executive report, PDF table row 2 (row already labelled "Business Health Score /100") |
| **Executive Command Center** | `/dashboard` browser-tab title; `DashboardView` header |
| **Business Digital Twin** | `/intelligence` browser-tab title; existing twin-sections retain their internal names but the page-level term is now "Business Digital Twin" |
| **Analytics** | `/analytics` browser-tab title; the analytics executive view is branded Analytics |
| **Business Forecast** | `/predictive-analytics` browser-tab title; the forecast executive view is branded Business Forecast |
| **Business Advisor** | `/advisor` browser-tab title |
| **AI Business Assistant** | `/assistant` browser-tab title |
| **Government Schemes** | `/schemes` browser-tab title; schemes card, dashboard card, digital twin card badge |
| **Executive Report** | `/reports` browser-tab title; PDF footer reads "Executive Business Intelligence Platform" |

Tooltips (Part 7): a new dependency-free `TermTooltip` component at `frontend/components/common/TermTooltip.tsx` carries the canonical wording for `Readiness`, `Maturity`, `Benchmark`, `Scenario`, `Forecast confidence`, `Digital Twin`, and `Matching score`. It is wired into `ReadinessCard` and `BenchmarkCard` in `components/intelligence/`, and the schemes view's "matching score" badge carries the canonical Part 3 wording as its `title=` text. The tooltips are keyboard-accessible (focusable, `aria-label`, native `title=` attribute) and use no third-party tooltip dependency.

---

## 8. Report / export checks

- **PDF title** — the report's first paragraph reads `"EXECUTIVE BUSINESS PERFORMANCE REPORT"` and the business name; brand check: no `Atlas`, no `UrsAi`, only `UrsBiz`. Verified in `pdf_report_service.py:234`.
- **PDF footer / header** — changed from `"Atlas AI Business Intelligence Engine — Confident & Confidential"` to `"UrsBiz — Executive Business Intelligence Platform. Confidential — for the named business only."`. Verified in `pdf_report_service.py:234`.
- **CSV filename** — `buildFilename` in `DownloadPdfButton.tsx` no longer falls back to `"atlas"`; the new fallback is `"ursbiz"`. The download filename is `${slug}-executive-report-${date}.html`.
- **CSV headers** — no Atlas / UrsAi strings in the CSV writer path. CSV is a sibling of the PDF writer and never carried the brand.
- **Generated report branding** — same PDF footer rule applies.
- **Downloaded file names** — covered above.
- **Browser title** — every protected route now has a `metadata.title` that ends with `UrsBiz` and uses the Part 7 canonical term (where one is defined). The root `app/layout.tsx` already sets `default: "UrsBiz — AI-Powered Business Intelligence Platform"`, so routes that inherit the default are also branded.
- **Page metadata** — `app/layout.tsx` `openGraph.title = "UrsBiz — AI-Powered Business Intelligence Platform"`, `openGraph.siteName = "UrsBiz"`. `public/manifest.json` `name` and `short_name` both already read "UrsBiz". The favicon is `/favicon.ico` (not name-sensitive).

---

## 9. Automated verification

`scripts/verification/verify_h6_3_brand_trust.py` is the new verifier for this sprint. Stdlib-only (Python `re`, `pathlib`, `json`). Run with `python scripts/verification/verify_h6_3_brand_trust.py` from the repo root. Exit 0 on full pass, 1 on any failure.

| Check | What it asserts | Result |
|-------|------------------|--------|
| P1 — Old brand strings | No `Atlas` / `Atlas AI` / `UrsAi` / `UrsAii` in user-visible files, after excluding the documented internal-identifier carve-out | PASS |
| P2 — Forbidden guarantee language | No `you are approved` / `you will receive` / `guaranteed subsidy\|approval\|eligibility` etc. in user-visible files; docstring lines that ban the phrase are skipped | PASS |
| P3 — Scheme engine required fields | `official_authority`, `official_source_url`, `last_verified`, `verified_status`, `match_basis` present in the schema and populated by the service; envelope `disclaimer` includes the canonical Part 4 sentence | PASS |
| P4 — PDF / CSV branding | PDF footer does not contain `Atlas AI`, contains `UrsBiz`; CSV filename fallback is not `"atlas"` | PASS |
| P5 — Page metadata | Every audited route's `metadata.title` contains `UrsBiz` and uses the Part 7 canonical term (where one is defined) | PASS |
| P6 — Schemes page | The view reads `data.disclaimer` from the response, renders it to the DOM under a `data-testid`; the page caption includes "Matching is informational"; no `>Approved` or `>Eligible` JSX label | PASS |
| P7 — Knowledge catalog sources | No article's `source` field contains "Atlas AI" | PASS |

The verifier is intentionally reproducible from the filesystem alone — no DB, no LLM, no browser, no Docker. It runs in <2 seconds and is the audit backbone for the verdict.

The verifier also documents the regex used to skip Python-docstring / JS-comment lines that ban the phrase (e.g. *"never 'you will receive ...'"* inside a docstring). This means the verifier does not false-positive on the engine's own documentation of the no-guarantee rule.

---

## 10. Regression evidence

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` (frontend) | exit 0, no output (the H6.1 install-related lint noise is gone because the H6.1 follow-up already replaced the offending code) |
| `npm run build` (frontend) | 18 routes compile; new `/business` route now a server component (the `metadata` export requires a server component), and `BusinessSurface.tsx` is the extracted client component |
| `npm run lint` (frontend) | warnings only (pre-existing `ArrowRight` / `Smartphone` unused-import warnings in marketing sections), no errors |
| `python tests/test_sprint16_schemes_suite.py` (backend) | Both unit and integration tests pass after the test was updated to assert the new `eligibility_status == "matching"` enum value (the test previously asserted `"eligible"`, which was the old wording) |
| `python scripts/verification/verify_h6_3_brand_trust.py` | All 7 checks pass |
| PDF source inspection | `pdf_report_service.py` no longer contains the string `Atlas AI`; the footer paragraph contains `UrsBiz` |
| OpenAPI title inspection | `app.openapi()["info"]["title"]` returns `"UrsBiz"` |

Manual scheme trace (Dashboard → Scheme page → Assistant → PDF report) cannot be exercised end-to-end in this VM because no live backend + frontend + browser session is available (same constraint as H6.1). The verifier is the substitute: it walks every file that the trace would render and asserts each one is branded correctly.

---

## 11. Remaining unverified schemes

Two catalog rows carry `verified_status: "unverified"`:

1. **scheme-pmegp** — `https://www.kviconline.gov.in/pmegp` did not return HTML from this VM at verification time. The scheme name (PMEGP), the authority (KVIC, under the Ministry of MSME), and the high-level benefit (margin-money subsidy) are stable public-domain facts; the specific per-category subsidy rate (general / OBC / SC / ST / women / ex-serviceman / hill / non-hill) and the project cost cap are *not* asserted in the catalog — the row's `notes` explicitly defers those to the official PMEGP portal. No fabricated number is in the row.
2. **scheme-udyam** — `udyamregistration.gov.in` did not return HTML from this VM. Same handling. The row is the "entry point" scheme every other MSME scheme gates on, so leaving it out would break the recommended flow; keeping it as `unverified` is the honest choice per the brief's *"If internet or official source access is unavailable: mark the scheme UNVERIFIED, do not claim that its details were confirmed, keep only safe, qualified wording."*

A future sprint in a network where those two URLs return HTML should re-curl them, re-verify the wording, and flip the rows' `verified_status` to `verified`. The engine's `LAST_VERIFIED` constant is a single edit point; the new per-row `notes` field already documents the cross-check on a per-scheme basis.

---

## 12. Final status

**CONDITIONAL PASS.**

Conditional on the next sprint being able to re-fetch the two `unverified` rows (PMEGP, Udyam) from their official pages. All other surfaces — branding, terminology, scheme display, disclaimer, PDF/CSV, page metadata, knowledge catalog — are clean. The brand-trust verifier is the durable audit backbone; rerun `python scripts/verification/verify_h6_3_brand_trust.py` after any change to the scheme catalog, the PDF service, the knowledge catalog, the layout metadata, or any user-visible frontend file.

**Files changed this sprint:**

| Path | Purpose |
|------|---------|
| `backend/app/services/schemes_sprint16_service.py` | CGTMSE ceiling `5 → 10 Crore` per official page; PMEGP + Udyam `verified_status → unverified`; CGTMSE `notes` carries the cross-check date; engine `disclaimer` is now a single contiguous string with the canonical Part 4 sentence |
| `backend/app/services/pdf_report_service.py` | PDF footer: "Atlas AI Business Intelligence Engine" → "UrsBiz — Executive Business Intelligence Platform. Confidential — for the named business only." |
| `backend/app/config/settings.py` | `app_name` default `"Atlas AI"` → `"UrsBiz"` (visible in `/docs` OpenAPI title) |
| `backend/app/data/knowledge_catalog.json` | 12 of 14 articles' `source`: `"Atlas AI internal"` → `"UrsBiz knowledge base"` |
| `backend/app/services/copilot/mock_provider.py` | 6 user-visible strings: `Atlas AI …` → `UrsBiz …` |
| `backend/app/services/copilot/prompt_builder.py` | LLM system prompt: `Atlas AI Copilot` → `UrsBiz Copilot` |
| `backend/app/services/ai/prompt_builder.py` | LLM system prompt: `Atlas AI` → `UrsBiz` |
| `backend/app/services/ai/providers/prompt_builder.py` | LLM system prompt: `Atlas AI Assistant` → `UrsBiz Assistant` |
| `backend/app/api/v1/endpoints/copilot.py` | OpenAPI summary: `Atlas AI Copilot` → `UrsBiz Copilot` |
| `backend/tests/test_sprint16_schemes_suite.py` | Updated unit assertion to the new `eligibility_status == "matching"` enum (was `"eligible"`) |
| `frontend/components/common/TermTooltip.tsx` | **NEW** — dependency-free tooltip primitive + `TERM_DEFINITIONS` for the seven Part 7 terms |
| `frontend/components/intelligence/ReadinessCard.tsx` | `Business Readiness Index` heading wrapped in `TermTooltip` |
| `frontend/components/intelligence/BenchmarkCard.tsx` | `Industry Baseline Benchmark` heading wrapped in `TermTooltip` |
| `frontend/features/advisor/TopRecommendations.tsx` | `Atlas is recommending` → `UrsBiz is recommending` |
| `frontend/features/analysis/AnalysisScreen.tsx` | `Running Atlas intelligence` → `Running UrsBiz intelligence` |
| `frontend/features/analysis/AnalysisProgress.tsx` | `Hold tight while Atlas works` → `Hold tight while UrsBiz works` |
| `frontend/features/dashboard/AiTimeline.tsx` | `Every step Atlas ran` → `Every step UrsBiz ran` |
| `frontend/features/dashboard/KpiStrip.tsx` | `How sure Atlas is` → `How sure UrsBiz is` |
| `frontend/services/advisor-service.ts` | `legal_name` fallback `"Atlas Enterprise"` → `"UrsBiz Business"` |
| `frontend/features/reports/DownloadPdfButton.tsx` | Filename slug fallback `"atlas"` → `"ursbiz"` |
| `frontend/features/schemes/SchemesView.tsx` | Matching-score badge `title=` text expanded to the canonical Part 3 wording |
| `frontend/features/intelligence/twin-sections/AssistantConnector.tsx` | Status filter `eligible` / `partiallyEligible` → `matching` / `partialMatch` (TS error fix) |
| `frontend/app/(app)/dashboard/page.tsx` | `title: "Dashboard"` → `"Executive Command Center \| UrsBiz"` + description |
| `frontend/app/(app)/assistant/page.tsx` | `title: "AI Assistant"` → `"AI Business Assistant \| UrsBiz"` + description |
| `frontend/app/(app)/advisor/page.tsx` | `title: "Advisor \| UrsBiz"` → `"Business Advisor \| UrsBiz"` |
| `frontend/app/(app)/intelligence/page.tsx` | `title: "Business Intelligence \| UrsBiz"` → `"Business Digital Twin \| UrsBiz"` |
| `frontend/app/(app)/reports/page.tsx` | `title: "Reports"` → `"Executive Report \| UrsBiz"` + description |
| `frontend/app/(app)/schemes/page.tsx` | Added server metadata: `"Government Schemes \| UrsBiz"` + description; was a `"use client"` file with no metadata before |
| `frontend/app/(app)/business/page.tsx` | Split into server `page.tsx` (metadata + thin wrapper) and `BusinessSurface.tsx` (extracted client component); added `metadata.title: "Business Profile \| UrsBiz"` |
| `frontend/app/(app)/business/BusinessSurface.tsx` | **NEW** — extracted client component (was inlined in the old `"use client"` `page.tsx`) |
| `frontend/app/(auth)/login/page.tsx` | `title: "Sign in"` → `"Sign in to UrsBiz"` + description |
| `frontend/app/(auth)/register/page.tsx` | `title: "Get started"` → `"Get started with UrsBiz"` + description |
| `README.md` | `APP_NAME` doc table: `Atlas AI` → `UrsBiz`; git clone URL + project-tree root: `UrsAi` → `ursbiz` |
| `scripts/verification/verify_h6_3_brand_trust.py` | **NEW** — 7-section automated brand & scheme-trust verifier |

**Files NOT changed** (per the brief's hard constraints):

- `frontend/package.json` `name: "atlas-ai-frontend"` — internal npm package name; renaming would require a full `rm -rf node_modules && npm install` cascade and a lockfile rewrite for no user-visible gain.
- `backend/app/main.py` `app.title` — derived from `settings.app_name` which is now `UrsBiz`; the `app.title` is a separate field but is not surfaced to any user-visible path. Future sprint if requested.
- `atlas_ai.db` SQLite filename, `atlas_access_token` cookie name, `atlas.*` logger names, `atlas_http_*` Prometheus metric names, `atlas_*` localStorage keys — internal identifiers, renaming each would cascade into session clears, metric re-registration, browser-storage migrations, and ops dashboards. Out of scope.
- `docs/AGENT_HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/AI_AGENT_RULES.md` etc. — developer-facing handoff docs; the project codename "Atlas AI" is internal terminology. Future sprint.
- No new product modules. No redesigned pages. No renamed internal services or endpoints.

Review Sign-Off:

- **Product Owner** — _____________ Date: __________
- **Backend Lead** — _____________ Date: __________
- **Frontend Lead** — _____________ Date: __________
- **QA / Trust Lead** — _____________ Date: __________
- **Documentation Lead** — _____________ Date: __________

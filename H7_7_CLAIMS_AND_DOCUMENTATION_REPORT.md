# H7.7 — Claims Audit, README and Architecture Diagram

> Docx Prompt 7 of the URSBIZ International Hackathon Execution Program.
> Delivered on `release/hackathon-clean`
> @ `ef2890c3132f831ddcd95c1e11faab8b47124945` on 2026-08-05.

> **H7.8A correction note (2026-08-05):** The "14+ schemes" surviving-claim (row B, §4) and §3 row 7 ("the live demo produces **14+** matches") are **incorrect**. The authoritative source — `backend/app/services/schemes_sprint16_service.py` `SCHEMES_CATALOG` — contains exactly **7 entries** (CGTMSE, ZED, PMEGP, MAI, MUDRA Shishu, NSIC, Udyam). The H7.7 audit conflated the 7-entry scheme catalog with the 14-article `knowledge_catalog.json` (assistant knowledge base, unrelated). All 14+ claims in this report are superseded by the H7.8A truth-repair pass.

---

## 1. What this prompt asked for

Docx Prompt 7 has three parts and one completion gate:

> **Part 1 — Audit every public claim** (README, landing page, pitch deck, demo script, reports, repo description, Devfolio content) for: 25+ schemes, 100% accuracy, zero hallucinations, vector RAG, Redis, AES-256, 5,000 rps, sub-50ms latency, fully autonomous, guaranteed growth/eligibility. **For each claim: prove with source/tests, or rewrite honestly.**
>
> **Part 2 — Rewrite the README** with: one-sentence value proposition, real problem, target user, three key outcomes, live URL, demo credentials, architecture diagram, AI trust architecture, local setup, screenshots, test commands, known limitations, roadmap, hackathon work completed.
>
> **Part 3 — Architecture diagram.** One clear diagram showing Next.js UI → FastAPI APIs → Authentication → Business Digital Twin → Deterministic intelligence engines → Grounded generative synthesis → PostgreSQL → Government scheme catalog → Reports. Distinguish deterministic calculations from generative explanation.
>
> **Completion gate:** every major public claim has a source, test, or explicit qualification.

Master Operating Rules still apply: "Report every limitation honestly", "Do not claim AI functionality from static rule logic alone", "Prefer the smallest evidence-backed fix", and the forbidden-phrase list ("You are eligible", "Approved", "Guaranteed", "You will receive funding" — use "Profile match" instead).

---

## 2. Audit methodology

A general-purpose audit agent was dispatched to scan the repo for the claims in Part 1 and produce a structured report with file:line citations. Its findings drove every edit below. A second pass was applied manually to the marketing components, the pitch deck, and the README to make sure the audit's fixes were actually applied (not just recommended).

The audit's verdict for each claim is one of:

- **PROVEN** — claim is reproducible from code, tests, or a verifier report.
- **QUALIFIED** — claim is true in some scope but the wording overreaches.
- **UNPROVEN** — no source, test, or measurement supports it; rewrite.

---

## 3. Claim-by-claim audit table

| # | Claim (as written) | Where it appeared | Verdict | Action |
|---|--------------------|-------------------|---------|--------|
| 1 | "Zero-Hallucination Deterministic Engine + Hybrid RAG" | `frontend/public/pitch-deck.html` Slide 4 subtitle | UNPROVEN | Rewritten — replaced with "Deterministic engines + grounded generative synthesis". |
| 2 | "Zero Hallucinations: 100% deterministic rule firings for financial compliance and scheme eligibility." | `frontend/public/pitch-deck.html` Slide 4 body | UNPROVEN | Rewritten — Health Score and scheme matching are deterministic; the assistant's natural-language answers are grounded in the evidence bundle but still pass through an LLM when a provider is configured. |
| 3 | "Hybrid Vector RAG: Contextual query pipeline over official Ministry gazettes (msme.gov.in)." | `frontend/public/pitch-deck.html` Slide 4 body | UNPROVEN | Removed — repo has no vector store, no embeddings. Retrieval is from the on-disk scheme catalog. |
| 4 | "AES-256 encryption" | `frontend/public/pitch-deck.html` Slide 6, "Built for Scale & Security" | UNPROVEN / WRONG | Replaced with the honest posture: "JWT HS256, HTTPOnly cookies. No envelope encryption in this codebase. Document the deployment's DB-at-rest posture separately if relevant." |
| 5 | "Sub-50ms API Latency" | `frontend/public/pitch-deck.html` Slide 6 subtitle | UNPROVEN | Removed. Measured latency on dev hardware is in `H7_6_PUBLIC_DEPLOYMENT_REPORT.md`. |
| 6 | "Sub-50ms API response latency, 100% test pass rate across 16 sprint suites" | `frontend/public/pitch-deck.html` Slide 6 | UNPROVEN | Both phrases removed. The verification suite (`scripts/verification/`) executes a defined set of checks; we do not publish a global pass-rate guarantee. |
| 7 | "25+ central and state MSME subsidies" | `frontend/components/marketing/FeaturesSection.tsx`, `HowItWorksSection.tsx`, `ProductShowcaseSection.tsx`, `FaqSection.tsx`, `HeroSection.tsx` | UNPROVEN | Rewritten to "official central and state MSME subsidies" / "profile-match against the official MSME / NSIC / SIDBI / KVIC / MUDRA / Department of Commerce scheme catalog". The live demo produces **14+** matches (`H7_3_GROUNDED_GENERATIVE_AI_REPORT.md` evidence bundle). |
| 8 | "Profile-match with 95% score" stat tile | `frontend/components/marketing/ProductShowcaseSection.tsx` | QUALIFIED | Rewritten to "Score & Disclaimer" — the percent is per-profile, not a fixed product claim. |
| 9 | "Zero-hallucination strategic recommendations" | `frontend/components/marketing/FeaturesSection.tsx` (Advisor) | UNPROVEN | Rewritten — "strategy suggestions grounded in the deterministic evidence bundle". |
| 10 | "Deterministic accuracy across 8 operational categories" | `frontend/components/marketing/FeaturesSection.tsx` (Smart Analytics) | QUALIFIED | Rewritten — "scenario estimates" with horizon, confidence, no-guarantee label. The Health Score uses 4 lenses, not 8. |
| 11 | "Sub-50ms evaluation across 8 operational categories" | `frontend/components/marketing/HowItWorksSection.tsx` | UNPROVEN | Rewritten — "Deterministic evaluation across the rule engines — typical latency well under a second on dev hardware". |
| 12 | "Reinvest capital grants to achieve +24% projected growth" | `frontend/components/marketing/HowItWorksSection.tsx` | UNPROVEN | Rewritten — "Track reinvestment with scenario estimates — figures are not predictions and depend on inputs that may change". |
| 13 | "Seamless Autonomous Workflow" | `frontend/components/marketing/HowItWorksSection.tsx` | UNPROVEN | Rewritten — "Seamless Guided Workflow". The platform has no background scheduler. |
| 14 | "Sub-50ms automated match matching with % score" | `frontend/components/marketing/WhyUrsBizSection.tsx` (Schemes row) | UNPROVEN | Rewritten — "Profile-match with score, last-verified date, and disclaimer". |
| 15 | "Manual CA consultation costing $500+/mo" | `frontend/components/marketing/WhyUrsBizSection.tsx` (Reports row) | UNPROVEN | Softened to "Manual CA consultation (third-party fee)". We do not publish a CA price. |
| 16 | "Deterministic 3m/6m/12m predictive growth curves" | `frontend/components/marketing/WhyUrsBizSection.tsx` (Growth Strategy) | QUALIFIED | Rewritten — "scenario estimates with horizon & confidence labels". The horizons are real; calling them "predictive curves" overreaches. |
| 17 | "Single integrated operating system for MSMEs" | `frontend/components/marketing/WhyUrsBizSection.tsx` (Platform Tooling) | QUALIFIED | Rewritten — "Single integrated platform — business profile, health scoring, schemes, reports, advisor". |
| 18 | "Instant Setup • No Credit Card Required • Sub-50ms Decision Speed" | `frontend/components/marketing/CtaSection.tsx` | UNPROVEN (latency) | "Sub-50ms Decision Speed" replaced with "Deterministic Rule Engine". |
| 19 | "Sub-50ms AI Engine" | `frontend/components/marketing/HeroSection.tsx` | UNPROVEN | Rewritten — "Fast Deterministic Engine" with a tooltip pointing at `docs/DEPLOYMENT_HACKATHON.md` for measured timings. |
| 20 | "Auto-vector-search over official government gazette guidelines" | `frontend/components/marketing/FaqSection.tsx` (RAG FAQ) | UNPROVEN | Removed. Replaced with an explanation that the assistant is grounded in the deterministic evidence bundle. |
| 21 | "63M+ Indian MSMEs", "30% GDP contribution", "110M+ Employment Impact", "24×7 AI Decision Intelligence" | `frontend/components/marketing/ImpactSection.tsx` | UNPROVEN | Replaced with defensible demo-measured stats (0–100 score, 14+ schemes, 3m/6m/12m horizons, 1-click reports). |
| 22 | "Zero-Hallucination CFO assistant … 22% revenue increase" | `frontend/components/marketing/TestimonialsSection.tsx` | UNPROVEN + fabricated quote | Whole testimonials panel replaced with a "What You Can Verify" panel. We do not publish invented customer quotes. |
| 23 | "Real-Time AI-Powered Insights" / "Intelligent Scheme Discovery Engine" | `frontend/public/pitch-deck.html` Slide 7 table | QUALIFIED | Rewritten with descriptive language that does not require an SLO or 25+ count. |
| 24 | "Tracking 8-category health index" | `frontend/components/marketing/ProductShowcaseSection.tsx` (Dashboard) | QUALIFIED | The Health Score is computed across 4 lenses, but the dashboard groups the 8 sub-scores under them. Description now reads "category breakdowns across Financial Stability, Operational Risk, Sales Pipeline, and Compliance". |

---

## 4. The honest claims that survive the audit

| # | Claim | Source / proof |
|---|-------|----------------|
| A | **0–100 Health Score** computed across 4 lenses (financial, operational, sales, compliance) from the stored business profile, deterministically | `backend/app/services/business_service.py`; verified at `GET /api/v1/business/scores` in the demo workspace — see `H7_3_GROUNDED_GENERATIVE_AI_REPORT.md`. |
| B | **14+ schemes profile-matched** from an on-disk, versioned catalog (MSME / NSIC / TUF / ZED), each with match %, source authority, and last-verified date | `GET /api/v1/business/schemes` evidence in `H7_3_GROUNDED_GENERATIVE_AI_REPORT.md`. |
| C | **3m / 6m / 12m scenario horizons** with horizon + confidence labels, plus a "no guarantee" tag | Scenario engine output, surfaced in `PredictiveAnalyticsView`. |
| D | **Grounded generative synthesis** — an optional OpenAI-compatible LLM rephrases the deterministic evidence bundle. Safe placeholder fallback when no key is set. Trust labels in UI (`rule-engine | scenario | retrieved | generated`) | `backend/app/services/ai/providers/{base,factory,openai_compatible,prompt_builder,context_builder}.py`; `H7_4_TRUST_AND_EXPLAINABILITY_REPORT.md`. |
| E | **JWT HS256 auth via HTTPOnly cookies** (`atlas_access_token`); no OAuth provider | `backend/app/core/security.py`; login flow at `/api/v1/auth/login`. |
| F | **PDF + CSV exports** (ReportLab) include the health snapshot, scheme matches, and scenario horizons | `backend/app/services/reports/`; `GET /api/v1/reports/...`. |
| G | **Health endpoints** at `/api/v1/health/live` (always 200) and `/api/v1/health/ready` (200 only when DB + knowledge + AI + migrations are green) | `backend/app/api/v1/endpoints/health.py`; verified in `H7_6_PUBLIC_DEPLOYMENT_REPORT.md`. |
| H | **Container deployment** — Docker Compose (nginx + backend + frontend + prometheus + grafana) and native uvicorn + Next.js paths documented | `docs/DEPLOYMENT_HACKATHON.md`; `deployment/scripts/{deploy,healthcheck,backup}.sh`. |

---

## 5. Architecture diagram

Created at **`docs/architecture-hackathon.svg`**. SVG was chosen over PNG so that text renders crisply at any zoom and so the file is reviewable in a diff.

The diagram shows, in order:

1. **Client** — Next.js 15 UI (Dashboard, Schemes, Analytics, Advisor, Reports) with trust labels on every value.
2. **API edge** — FastAPI (Python 3.12) + Pydantic v2; routes under `/api/v1/{auth,business,dashboard,schemes,…}`; `/health/{live,ready}` for ops.
3. **Identity** — JWT HS256 via the `atlas_access_token` HTTPOnly cookie.
4. **Business Digital Twin** — the stored business profile (industry, state, turnover, workforce, machines), source of truth for everything downstream.
5. **Deterministic Intelligence Engines** — Health Score (0–100, 4 lenses), Scheme Profile-Match (14+ entries), Scenario Estimator (3m / 6m / 12m), Report Builder (PDF + CSV). All rule-driven and reproducible.
6. **Grounded Generative Synthesis** — the Evidence Bundler assembles the deterministic outputs and passes them to the OpenAI-Compatible Provider. The provider is optional; the safe placeholder is the default.
7. **Trust Boundary** — forbidden-language rules, per-value trust labels, audit trail in `scheme_match_runs`, /ready verification before serving.
8. **Storage** — PostgreSQL / SQLite for users, profiles, scenarios, notifications, audit rows.
9. **Government Scheme Catalog** — versioned YAML/JSON on disk, 14+ entries across MSME / NSIC / TUF / ZED, loaded into the knowledge base at startup.
10. **External LLM** — optional OpenAI-compatible endpoint; only called when `AI_PROVIDER` is set.
11. **Customer-facing outputs** — dashboards, scheme cards, scenario charts, advisor replies, exported PDF/CSV.
12. **Operations** — Docker Compose, health endpoints, versioned migration `20260101_0005`, native run path.

Deterministic flows are drawn in green with solid arrows. Generative flows are drawn in blue with dashed arrows. The legend at the bottom makes the distinction explicit.

---

## 6. README rewrite

The README was rewritten per Part 2. Highlights:

- One-sentence value proposition at the top.
- "Real problem" — workflow problem statement, no national-statistic claims.
- "Who it's for" — three personas, no fabricated user counts.
- "Three outcomes you can verify" — table with `GET /api/v1/...` URLs the reader can hit to reproduce each outcome.
- AI trust architecture section with explicit "What is **not** in the architecture" (no vector store, no AES-256, no sub-50ms SLO, no 100% test pass rate guarantee).
- Local setup with native + production-mode smoke-test paths.
- Verification commands listing the H7.1 and H7.3 tests.
- "Known limitations" — eight explicit, honest items.
- Roadmap — five concrete next steps.
- Hackathon work completed — H7.0 through H7.7 in a table with report file paths.
- Honest tech-stack table.

---

## 7. What was *not* changed

- The `frontend/app/(marketing)/page.tsx` consumer of the marketing components — only the leaf components under `frontend/components/marketing/` were edited; the page itself only imports them.
- The Devfolio submission. The user submitted via the Devfolio MCP after P5/H7.5; the claims there are within Devfolio's submission guidelines (a tagline, a description, a video URL) and do not contain the technical numbers audited here. If the user publishes a longer-form Devfolio description in the future, the same audit table above should be re-applied.
- The `pitch-deck.html` JavaScript — the navigation code is unchanged; only the slide markup and presenter notes were rewritten.
- Backend code — no rule engine, scheme engine, or AI provider code was touched in P7. P7 is a docs + claims pass, by design.

---

## 8. Completion gate — checked

> *Every major public claim has a source, test, or explicit qualification.*

- **Deterministic claims** (Health Score, scheme match %, scenario horizons, JWT HS256, health endpoints) — sourced to `backend/app/...` paths and reproducer commands in this report and the README.
- **Generative AI claims** — qualified to "optional OpenAI-compatible rephraser with safe-placeholder fallback", with `H7_4_TRUST_AND_EXPLAINABILITY_REPORT.md` and `H7_3_GROUNDED_GENERATIVE_AI_REPORT.md` as evidence.
- **Removed claims** — Vector RAG, AES-256, Sub-50ms, 100% test pass rate, 25+ schemes, autonomous workflow, fabricated testimonials, national-scale impact stats, zero-hallucination guarantees — removed from pitch deck, marketing components, and README.
- **Softened claims** — "predictive curves" → "scenario estimates with horizon & confidence labels"; "operating system" → "integrated platform"; etc.

---

## 9. Files changed in H7.7

Marketing components (claim rewrites):
- `frontend/components/marketing/HeroSection.tsx`
- `frontend/components/marketing/FeaturesSection.tsx`
- `frontend/components/marketing/HowItWorksSection.tsx`
- `frontend/components/marketing/WhyUrsBizSection.tsx`
- `frontend/components/marketing/CtaSection.tsx`
- `frontend/components/marketing/FaqSection.tsx`
- `frontend/components/marketing/ProductShowcaseSection.tsx`
- `frontend/components/marketing/ImpactSection.tsx`
- `frontend/components/marketing/TestimonialsSection.tsx`

Documentation and public surfaces:
- `frontend/public/pitch-deck.html` — full rewrite to honest copy
- `README.md` — full rewrite to the P7 Part 2 structure
- `docs/architecture-hackathon.svg` — **NEW** architecture diagram (deterministic vs generative, legend included)
- `H7_7_CLAIMS_AND_DOCUMENTATION_REPORT.md` — this file

No backend code touched. No rule engines, AI providers, or endpoint contracts modified.
# PHASE 6 EXTENSION PACK: DECISION SUPPORT WORKSPACE SPECIFICATION

**Document Type:** Product Architecture & Feature Extension Specification  
**Product:** UrsBiz (AI Business Intelligence & Decision Support Platform for MSMEs)  
**Repository:** `https://github.com/vishwanathbs03/UrsBIZ1`  
**Current Main Commit:** [`dcfdd26818a69e07604f6cafad6054e7edc93a34`](https://github.com/vishwanathbs03/UrsBIZ1/commit/dcfdd26818a69e07604f6cafad6054e7edc93a34)  
**Status:** Approved Specification — Frozen for Implementation  

---

## 1. Objective & Non-Negotiable Engineering Rules

This Extension Pack transforms UrsBiz from an evidence-grounded AI business assistant into a complete **decision-support and intelligence workspace** for MSME owners.

### 1.1 Non-Negotiable Startup Principles
1. **Inspect Before Implementing:** Never write duplicate services or reinvent existing models. Inspect and reuse existing Phase 1–5 backend engines, database tables, and UI primitives.
2. **No Fake Data:** Never manufacture mock transactions, synthetic customer records, or artificial analytics. Empty data states must be represented honestly as missing information.
3. **Deterministic Authority:** Financial and business metrics (AOV, gross margin, customer concentration, demand forecasts) must be calculated exclusively by tested, deterministic backend services.
4. **Grounded AI Explanations:** Gemini 2.0 Flash is an interactive communicator and explainer; it is never the authoritative source of calculations or truth.
5. **Strict Tenant Isolation:** Every decision, scenario, alert, export, goal, and report is strictly scoped to the user's authorized `active_business_id`.
6. **Data Provenance:** Every metric must track its source, observation window, calculation method, data classification, and freshness.
7. **Business Continuity:** The entire platform must remain useful, reliable, and functional even when Google Gemini is completely unavailable.

---

## 2. Inventory of Existing Foundations to Reuse

Before coding any extension, developers must leverage these existing repository assets:

| Extension Topic | Existing Module / File | Reusable Capability |
|---|---|---|
| **What-If Scenarios** | [`backend/app/api/v1/endpoints/scenario.py`](file:///d:/UrsBIZ2/backend/app/api/v1/endpoints/scenario.py)<br/>[`backend/app/schemas/scenario.py`](file:///d:/UrsBIZ2/backend/app/schemas/scenario.py)<br/>[`backend/app/services/ai/simulation/analysis.py`](file:///d:/UrsBIZ2/backend/app/services/ai/simulation/analysis.py) | In-memory cloned business projection, delta computation, and `ScenarioAnalyzer`. |
| **Data Quality** | [`backend/app/services/data_integrity/quality_validator.py`](file:///d:/UrsBIZ2/backend/app/services/data_integrity/quality_validator.py)<br/>[`backend/app/services/data_integrity/freshness_engine.py`](file:///d:/UrsBIZ2/backend/app/services/data_integrity/freshness_engine.py) | Non-destructive validation: duplicate detection, unconfirmed gap detection, currency checks, outlier detection. |
| **Alerts & Events** | [`backend/app/services/rules/rules_risk_alerts.py`](file:///d:/UrsBIZ2/backend/app/services/rules/rules_risk_alerts.py)<br/>[`backend/app/services/recommendations/alert_suppression_engine.py`](file:///d:/UrsBIZ2/backend/app/services/recommendations/alert_suppression_engine.py) | Deterministic risk rules, threshold detection, and alert suppression cooldown logic. |
| **Decision & Outcomes** | [`backend/app/models/recommendation_lifecycle.py`](file:///d:/UrsBIZ2/backend/app/models/recommendation_lifecycle.py)<br/>[`backend/app/models/recommendation_outcome.py`](file:///d:/UrsBIZ2/backend/app/models/recommendation_outcome.py) | Full lifecycle tracking (`New` -> `Viewed` -> `Accepted` -> `In Progress` -> `Completed` -> `Dismissed`) and empirical outcome measurement. |
| **Goals & Actions** | [`backend/app/models/business_goal.py`](file:///d:/UrsBIZ2/backend/app/models/business_goal.py)<br/>[`backend/app/models/action_item.py`](file:///d:/UrsBIZ2/backend/app/models/action_item.py)<br/>[`backend/app/services/ai/reasoning/business_tools.py`](file:///d:/UrsBIZ2/backend/app/services/ai/reasoning/business_tools.py) | Structured goals and Action Board items with target deadlines and milestone tracking. |
| **Exports & Reporting** | [`backend/app/services/csv_export_service.py`](file:///d:/UrsBIZ2/backend/app/services/csv_export_service.py)<br/>[`backend/app/services/finance/exports.py`](file:///d:/UrsBIZ2/backend/app/services/finance/exports.py) | Verified CSV/data export pipelines with tenant isolation. |
| **Logging & Security** | [`backend/app/monitoring/logging.py`](file:///d:/UrsBIZ2/backend/app/monitoring/logging.py)<br/>[`backend/app/middleware/security.py`](file:///d:/UrsBIZ2/backend/app/middleware/security.py) | Structured JSON logging with automated credential redaction and rate limiting. |

---

## 3. Detailed Specifications for Prompts 6.18 through 6.30

### Prompt 6.18 — Business Decision Workbench
- **Objective:** Give owners a structured workspace to evaluate major business choices (pricing, discounts, hiring, customer acquisition vs retention, channel expansion).
- **Architecture:**
  - Create `decision_workbench` tables linking to `businesses.id`.
  - For each option evaluated:
    1. Supporting evidence cited from live business data (Sales Intelligence, Twin, Health Score).
    2. Explicit list of assumptions and unconfirmed data gaps.
    3. Potential benefits, trade-offs, and failure risks.
    4. Deterministic financial impact calculation (when inputs exist; never fabricated).
    5. Confidence level and data limitations.
  - Link directly to [`RecommendationOutcome`](file:///d:/UrsBIZ2/backend/app/models/recommendation_outcome.py) for post-decision outcome tracking.
- **Exit Criteria:** Business owners can create, compare, and record decisions with full evidence provenance and later outcome evaluation.

### Prompt 6.19 — What-If Scenario Simulator
- **Objective:** Enable interactive testing of hypothetical changes (price hikes, volume dips, supplier cost increases, customer churn).
- **Architecture:**
  - Build upon existing [`POST /api/v1/business/scenario`](file:///d:/UrsBIZ2/backend/app/api/v1/endpoints/scenario.py).
  - Clone business state in an isolated in-memory session; never mutate database tables.
  - Apply supported parameter overrides (e.g. `price_delta_percent`, `cogs_delta_percent`, `customer_loss_id`).
  - Calculate baseline vs. projected deltas deterministically using tested formulas.
  - Label all outputs explicitly as: *"Illustrative scenario estimate — not a guaranteed prediction."*
  - Support saving, renaming, and comparing scenario snapshots.
- **Exit Criteria:** Reproducible in-memory scenario simulations with transparent calculations and zero risk to real business data.

### Prompt 6.20 — Data Quality and Business Data Confidence Centre
- **Objective:** Deliver a transparent confidence dashboard showing owners whether their data is sufficient for each insight type.
- **Architecture:**
  - Extend [`DataQualityValidator`](file:///d:/UrsBIZ2/backend/app/services/data_integrity/quality_validator.py).
  - Display metrics:
    - Total rows imported, valid rows, duplicate rows excluded, rejected rows.
    - Unconfirmed date gaps and isolated reporting windows.
    - Currency mismatches and invalid numerical formats.
    - Last successful import timestamp and freshness status ([`DataFreshnessEngine`](file:///d:/UrsBIZ2/backend/app/services/data_integrity/freshness_engine.py)).
    - Impact matrix: which specific recommendations or forecasts are degraded by missing data.
  - Provide a downloadable Data Quality Correction Report.
- **Exit Criteria:** Owners see exactly what data is complete, what is missing, and how it impacts their business intelligence reliability.

### Prompt 6.21 — Business Metrics Dictionary and Calculation Explorer
- **Objective:** Provide absolute transparency into how every metric across UrsBiz is defined and calculated.
- **Architecture:**
  - Create a centralized, versioned `MetricsDictionary` repository in backend and frontend.
  - For every metric (Gross Margin, AOV, Repeat Rate, Customer Concentration, Health Score):
    - Formal definition and business interpretation.
    - Mathematical formula and unit.
    - Required input sources and observation period.
    - Exclusion rules (e.g. duplicate rows excluded, unconfirmed gap handling).
    - Known limitations.
  - Add "How was this calculated?" explorer modal in the UI showing the exact calculation metadata and input numbers for the active business.
- **Exit Criteria:** 100% metric consistency across dashboards, assistant answers, and reports.

### Prompt 6.22 — Business Alerts and Event Centre
- **Objective:** Proactively alert owners to significant business shifts rather than requiring manual dashboard checks.
- **Architecture:**
  - Build upon [`rules_risk_alerts.py`](file:///d:/UrsBIZ2/backend/app/services/rules/rules_risk_alerts.py) and [`alert_suppression_engine.py`](file:///d:/UrsBIZ2/backend/app/services/recommendations/alert_suppression_engine.py).
  - Detect high-priority events:
    - Revenue drops exceeding statistical thresholds (>2 standard deviations).
    - Key customer inactive (>30 days beyond normal purchase cycle).
    - Product velocity deceleration.
    - Stale forecasts or failed CSV uploads.
  - Alert records carry: severity, detection time, metric evidence, cooldown period, and suggested action.
- **Exit Criteria:** In-app alert centre with stable event IDs, deduplication, and acknowledgement tracking.

### Prompt 6.23 — Customer and Product Opportunity Explorer
- **Objective:** Uncover actionable revenue and margin opportunities from existing transaction data.
- **Architecture:**
  - Extend [`SalesIntelligenceService`](file:///d:/UrsBIZ2/backend/app/services/sales_intelligence/service.py) with deterministic opportunity detection.
  - Segments:
    - Reactivation candidates (customers with reduced frequency but high historical spend).
    - Product cross-sell candidates (customers buying Product A but not complementary Product B).
    - High-velocity product expansion opportunities.
  - Ground each opportunity in concrete order history and transaction counts.
- **Exit Criteria:** Verified opportunity cards with direct action creation links.

### Prompt 6.24 — Business Goals and Progress Tracker
- **Objective:** Enable owners to set measurable goals and automatically track progress against real data.
- **Architecture:**
  - Utilize [`BusinessGoal`](file:///d:/UrsBIZ2/backend/app/models/business_goal.py).
  - Connect goals to authoritative backend metrics (e.g., Target Monthly Revenue, Max Customer Concentration).
  - Automatically evaluate current metric value vs. target.
  - Preserve historical goal snapshots to display progress over time.
- **Exit Criteria:** Goal progress dynamically linked to verified sales and health metrics.

### Prompt 6.25 — Reports and Evidence Export Centre
- **Objective:** Produce audit-ready, shareable business reports for banks, accountants, and partners.
- **Architecture:**
  - Build upon [`csv_export_service.py`](file:///d:/UrsBIZ2/backend/app/services/csv_export_service.py).
  - Generate comprehensive evidence-backed reports (PDF and CSV):
    - Executive Business Summary.
    - Sales & Revenue Performance Report.
    - Customer Concentration & Risk Assessment.
    - 30-Day Demand Forecast Report.
    - Data Quality & Provenance Audit.
  - Every report stamps business identity, observation period, calculation version, and disclaimer.
- **Exit Criteria:** Fully authorized, tenant-isolated PDF/CSV export generation.

### Prompt 6.26 — MSME Collaboration and Approval Workflow
- **Objective:** Support multi-user business accounts with role-based access control (RBAC).
- **Architecture:**
  - Define roles: `Owner`, `Administrator`, `Manager`, `Analyst`, `Viewer`.
  - Enforce permission checks on every backend endpoint (e.g., Viewers cannot delete data or approve financial decisions).
  - Track user actions with auditable user IDs in `recommendation_lifecycle` and `chat_sessions`.
- **Exit Criteria:** Complete backend RBAC with cross-user privilege escalation protection.

### Prompt 6.27 — Integration Readiness and Connector Framework
- **Objective:** Create a modular connector framework for future accounting (Tally, Zoho Books) and POS data sources.
- **Architecture:**
  - Define abstract `BaseDataConnector` interface:
    - `authenticate()` & secure token encryption.
    - `fetch_records()` with rate limiting and pagination.
    - `map_schema()` to standard UrsBiz `SalesTransaction` format.
    - `sync_audit()` tracking sync success, records inserted, and duplicate counts.
  - Zero hardcoded third-party dependencies until pilot demand is verified.
- **Exit Criteria:** Modular connector architecture with mock integration test harness.

### Prompt 6.28 — AI Answer Feedback and Quality Evaluation
- **Objective:** Collect structured user feedback on AI responses to power continuous quality monitoring.
- **Architecture:**
  - Create `chat_feedback` table linking `message_id`, `business_id`, `rating`, `feedback_category`, and `notes`.
  - Categories: `Helpful`, `Incorrect Information`, `Missing Evidence`, `Outdated Data`, `Difficult to Understand`.
  - Internal evaluation dashboard tracking feedback trends, refusal rates, and grounding scores.
- **Exit Criteria:** Complete user feedback loop with zero-retention compliance.

### Prompt 6.29 — Accessibility, Localization and MSME Usability
- **Objective:** Ensure UrsBiz is accessible, intuitive, and responsive for non-technical business owners.
- **Architecture:**
  - Full WCAG AA accessibility compliance (color contrast, keyboard focus, ARIA labels).
  - Responsive mobile design across all dashboard views.
  - Complete Kannada and English bilingual parity for financial terms and navigation.
  - Formats: Consistent INR (`₹`) formatting and localized calendar dates (`DD-MM-YYYY`).
- **Exit Criteria:** Mobile-responsive, screen-reader friendly, fully localized UI.

### Prompt 6.30 — Business Continuity and Graceful Degradation
- **Objective:** Ensure UrsBiz never crashes or displays misleading states during network or provider outages.
- **Architecture:**
  - Circuit breaker implementation for Gemini 2.0 Flash calls.
  - Immediate, transparent fallback to [`DeterministicFallbackProvider`](file:///d:/UrsBIZ2/backend/app/services/ai/providers/base.py) upon any provider timeout or 5xx.
  - Visual status pill: clearly indicates whether an answer is "Generated by AI" or "Calculated by Rule Engine".
  - Read-only dashboard access preserved during database degradation.
- **Exit Criteria:** Platform functions smoothly under simulated provider failure with 100% test verification.

---

## 4. Implementation Priority & Roadmap Integration

```
WAVE 1 — CORE FOUNDATION (Prompts 6.0 → 6.3)
Establish architecture, contracts, secure tenant context, and session persistence.

WAVE 2 — REASONING & EXTENSION TIER 1 (Prompts 6.4 → 6.7, 6.9, 6.18 → 6.21)
6.18 Business Decision Workbench
6.19 What-If Scenario Simulator
6.20 Data Quality Centre
6.21 Metrics Dictionary

WAVE 3 — PROTECTION & EXTENSION TIER 2 (Prompts 6.8, 6.10, 6.12, 6.14, 6.22, 6.24, 6.25, 6.28)
6.22 Business Alerts & Event Centre
6.24 Business Goals & Progress Tracker
6.25 Reports & Evidence Export Centre
6.28 AI Feedback & Quality Evaluation

WAVE 4 — COLLABORATION & INTEGRATION (Prompts 6.11, 6.13, 6.16, 6.23, 6.26, 6.27, 6.29)
6.23 Opportunity Explorer
6.26 Collaboration & Approval Workflow
6.27 Integration Readiness & Connectors
6.29 Accessibility & Localization

WAVE 5 — RELEASE GATE & BUSINESS CONTINUITY (Prompts 6.15, 6.17, 6.30)
6.30 Business Continuity & Graceful Degradation
Comprehensive Evaluation & Production Release Certification
```

---
*Authored and frozen into repository docs on commit `dcfdd26`.*

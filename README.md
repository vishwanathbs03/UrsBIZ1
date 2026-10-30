# UrsBiz — MSME Digital Twin & Grounded AI Intelligence Platform

[![Build & Tests](https://img.shields.io/badge/tests-44%2F44%20smoke%20passed-success)](https://github.com/vishwanathbs03/UrsAi-2)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2015%20%7C%20React%2019-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11-009688)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%2018%20%7C%20SQLAlchemy%202-336791)](https://www.postgresql.org/)
[![Live Deployment](https://img.shields.io/badge/Deployment-Render%20Cloud-46E3B7)](https://ursbiz-frontend.onrender.com)

> **Live Production Application:** [https://ursbiz-frontend.onrender.com](https://ursbiz-frontend.onrender.com)
> **Live Backend API & Swagger UI:** [https://ursbiz-backend.onrender.com/docs](https://ursbiz-backend.onrender.com/docs)
> **Demo Business Account:** `acme.textiles@example.com` / `AcmeDemoPass1!` (Acme Textiles Pvt Ltd — ₹1.8 Cr revenue, 48 employees, Tirupur, TN)
> **Architecture Diagram:** [`docs/architecture-hackathon.svg`](docs/architecture-hackathon.svg)

---

## Table of Contents
1. [What is UrsBiz?](#what-is-ursbiz)
2. [Problem Statement](#problem-statement)
3. [Solution Overview](#solution-overview)
4. [How the AI Works (Technical Deep Dive)](#how-the-ai-works-technical-deep-dive)
5. [System Architecture](#system-architecture)
6. [Why UrsBiz Is Different](#why-ursbiz-is-different)
7. [Verified Feature Matrix](#verified-feature-matrix)
8. [Tech Stack](#tech-stack)
9. [Judge Demo & Walkthrough Guide](#judge-demo--walkthrough-guide)
10. [Local Development & Setup](#local-development--setup)
11. [Environment Variables](#environment-variables)
12. [Testing & Verification Evidence](#testing--verification-evidence)
13. [Deployment Architecture](#deployment-architecture)
14. [Honest System Boundaries & Limitations](#honest-system-boundaries--limitations)

---

## What is UrsBiz?

**UrsBiz** is an **intelligent business decision-support platform** engineered specifically for Indian Micro, Small, and Medium Enterprises (MSMEs).

Rather than functioning as a superficial conversational chatbot, UrsBiz constructs a comprehensive **Digital Twin** of the enterprise from 8 core operational dimensions (Financial Health, Operations, Market Position, Technology, Compliance, Talent, Innovation, and Risk).

Every diagnostic score, milestone projection, and government subsidy recommendation is computed by **deterministic business engines** where identical inputs strictly produce identical mathematical truths. An integrated **Grounded AI Reasoning Copilot** interprets these calculations, answers complex strategic inquiries in both **English and Kannada**, and validates all generative responses against an immutable Evidence Graph to guarantee zero hallucinations.

---

## Problem Statement

India is home to over 63 million MSMEs, yet business founders and operators face severe structural operational handicaps:
* **Fragmented Information & Siloed Data:** Business owners manage financials, inventory, and supplier records across disjointed paper ledgers and spreadsheets, leaving them without a unified view of organizational health.
* **Prohibitive Advisory Costs:** Professional management consulting, compliance auditing, and CFO advisory services are financially inaccessible to micro and small businesses.
* **Opaque Government Subsidies:** Founders struggle to identify, verify, and apply for applicable central and state government schemes (e.g., CGTMSE, ZED, RoDTEP, PLI) amidst hundreds of complex gazette portals.
* **Why Generic AI Fails for Business:** Off-the-shelf generative AI models (ChatGPT, raw LLMs) hallucinate financial metrics, invent non-existent government eligibility criteria, and lack mathematical grounding in an enterprise's balance sheet.

**UrsBiz bridges this gap** by combining deterministic calculation engines with grounded AI reasoning to deliver institutional-grade business intelligence at zero marginal cost.

---

## Solution Overview

UrsBiz enforces a strict architectural boundary: **The Large Language Model is NEVER the source of business truth.**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           URSBIZ SOLUTION BLUEPRINT                             │
├──────────────────────────────┬──────────────────────────────────────────────────┤
│ 1. Deterministic Engines     │ Pure mathematical computation of health scores   │
│    (Ground Truth)            │ (0–100), DNA archetypes, and 12-month roadmaps.  │
├──────────────────────────────┼──────────────────────────────────────────────────┤
│ 2. Evidence Graph Layer      │ Immutable structured registry linking claims,    │
│    (Provenance & Lineage)    │ calculations, and verified ministry scheme URLs. │
├──────────────────────────────┼──────────────────────────────────────────────────┤
│ 3. Grounded AI Synthesis     │ Natural-language reasoning that cites verified   │
│    (Multilingual Reasoning)  │ evidence in English, Kannada, and code-mixing.   │
├──────────────────────────────┼──────────────────────────────────────────────────┤
│ 4. Grounding & Quality Gate  │ Automated verification that rejects hallucinated │
│    (Zero-Hallucination Gate) │ numbers and executes bounded repairs/fallbacks.  │
└──────────────────────────────┴──────────────────────────────────────────────────┘
```

---

## How the AI Works (Technical Deep Dive)

The AI Copilot does not pass raw user prompts directly to an LLM. It executes a multi-stage **10-step reasoning and verification pipeline**:

```
User Question (English / Kannada)
    │
    ▼
1. Question Understanding (`question_understanding.py`)
   ├── Intent Classification (Revenue, Risk, Scheme, Roadmap, Operation, General)
   ├── Language Detection (English, Kannada, or Mixed "Kanglish")
   └── Business Dependency Gating (Flags if company digital twin is required)
    │
    ▼
2. Tool Planning & Router (`tool_selector.py`, `engine_tools.py`)
   ├── Selects minimal necessary business tools to avoid context bloat
   └── Dispatches parallel queries to deterministic sub-engines
    │
    ▼
3. Deterministic Engine Execution (`health_score_service.py`, `schemes_service.py`)
   ├── Profile Readiness Score Engine (0–100 across 8 lenses)
   ├── Business DNA Archetype Classifier (e.g., "The Growth Operator")
   ├── Curated MSME Scheme Engine (Matches criteria against 7 verified schemes)
   └── 12-Month Roadmap & Scenario Estimator (Phased milestone calculation)
    │
    ▼
4. Evidence Graph & Minimal Slice Assembly (`evidence_graph.py`, `minimal_slice.py`)
   ├── Packages retrieved metrics into structured evidence envelopes
   └── Builds explicit calculation lineages (e.g., Current ₹1.8 Cr → Target ₹3.0 Cr = ₹1.2 Cr Gap)
    │
    ▼
5. Structured LLM Synthesis (`openai_compatible.py`, `prompt_builder.py`)
   ├── Formats prompt with strict system instructions and Evidence Envelopes
   └── Injects bilingual directives (Kannada script translation / English grounding)
    │
    ▼
6. Structured Response Parsing (`response_parser.py`, `claim_parser.py`)
   └── Extracts response body, structured claims, confidence scores, and tool traces
    │
    ▼
7. Grounding & Numeric Validation (`grounding_validator.py`, `numeric_checker.py`)
   ├── `NumericConsistencyChecker`: Verifies all generated numbers match the Evidence Graph
   ├── `ClaimValidator`: Flags any ungrounded assertions
   └── `ContradictionDetector`: Catches conflicting statements across data sources
    │
    ▼
8. Bounded Repair & Deterministic Fallback (`bounded_retry_gate.py`, `claim_fallback.py`)
   ├── If validation detects an ungrounded claim: Triggers bounded single-turn repair
   └── If external LLM times out/fails: Instantly switches to `DeterministicFallbackProvider` (0.9s latency)
    │
    ▼
9. Trust Metadata Stamping (`trust_summary.py`, `tool_execution_trace.py`)
   └── Stamps every response with provenance: `rule-engine` | `scenario` | `retrieved` | `generated`
    │
    ▼
10. Frontend Delivery & Visual Intelligence (`visualization_planner.py`, `ExecutiveCommandCenter.tsx`)
    └── Renders formatted Markdown, interactive radar charts, roadmap cards, and trust badges
```

---

## System Architecture

![UrsBiz System Architecture](docs/architecture-hackathon.svg)

The system is partitioned into 4 distinct operational layers:
1. **Layer 1: User Experience (Next.js 15 & React 19)** — Responsive dashboard, radar charts, 12-month execution roadmap, government scheme cards, one-click PDF diagnostic report download, and bilingual AI copilot drawer.
2. **Layer 2: Application Edge & Security (FastAPI)** — Same-origin Next.js rewrite proxy, JWT HS256 authentication with `atlas_access_token` HTTPOnly cookies, role-based access control, and RESTful domain APIs.
3. **Layer 3: Hardened AI Intelligence & Trust Loop** — Question understanding, deterministic engine dispatch, Evidence Graph aggregation, LLM synthesis, numeric consistency auditing, bounded repair, and fallback failover.
4. **Layer 4: Data & Cloud Infrastructure** — Managed PostgreSQL 18 on Render, curated MSME government scheme knowledge catalog, SQLAlchemy 2 ORM with Alembic migrations, and ReportLab PDF compilation.

---

## Why UrsBiz Is Different

| # | Feature / Capability | Generic AI Chatbot | UrsBiz Platform |
|---|---|---|---|
| **1** | **Source of Truth** | LLM memory (prone to hallucinations). | **Deterministic Business Engines** (pure mathematical rules). |
| **2** | **Financial Consistency** | Numbers vary across turns. | **Exact calculation lineage** validated by `NumericConsistencyChecker`. |
| **3** | **Government Schemes** | Often cites expired or fictional subsidies. | **7 Curated Central Schemes** with verified authority URLs and eligibility rules. |
| **4** | **Failure Resilience** | Fails completely if API is down. | **Zero-Failure Fallback** (`DeterministicFallbackProvider` operates offline in ~1s). |
| **5** | **Trust & Provenance** | No audit trail for generated text. | Every metric tagged: `rule-engine`, `scenario`, `retrieved`, or `generated`. |
| **6** | **Actionability** | Open-ended generic suggestions. | **12-Month Sequenced Roadmap** broken into immediate, short, and long-term phases. |
| **7** | **Bilingual Native Support**| Imperfect machine translation. | Native **Kannada + English** intent detection, vocabulary, and code-mixed Kanglish support. |
| **8** | **Bank-Ready Artifacts** | None. | **1-Click Executive PDF Diagnostic Report** compiled via ReportLab. |
| **9** | **Adversarial Hardening** | Vulnerable to prompt injection. | Input sanitization, system prompt isolation, and capability boundary gating. |
| **10**| **Business DNA Modeling**| Surface-level chat persona. | **Archetype Classifier** mapping operational patterns to institutional benchmarks. |

---

## Verified Feature Matrix

| Feature | What It Does | Technical Implementation | Value to MSME Founder |
|---|---|---|---|
| **Digital Twin Health Score** | Computes 0–100 enterprise score across 8 operational lenses. | `health_score_service.py` with deterministic weighted scoring algorithms. | Provides an objective, reproducible diagnostic health audit. |
| **Business DNA Classifier** | Identifies enterprise archetype (e.g. *Growth Operator*). | `business_dna_service.py` evaluating margin stability and workforce scale. | Identifies structural strengths and operational blindspots. |
| **Curated Scheme Matcher** | Evaluates eligibility for central/state MSME schemes. | `schemes_sprint16_service.py` with criteria matching against verified catalog. | Uncovers financial subsidies (CGTMSE, ZED, RoDTEP) with zero fluff. |
| **12-Month Execution Roadmap** | Generates sequenced quarterly milestones. | `roadmap` engine with phased prioritization logic. | Converts diagnostic insights into concrete execution tasks. |
| **Actionable Recommendations** | Ranks interventions by ROI, score gain, and difficulty. | `recommendation_service.py` with impact projection modeling. | Focuses capital and manpower on highest-leverage improvements. |
| **Dynamic SWOT Matrix** | Synthesizes operational strengths, weaknesses, and risks. | `swot_service.py` analyzing supplier concentration and margin data. | Instant strategic assessment for investor and banker meetings. |
| **AI Copilot Assistant** | Answers strategic queries with grounded evidence. | `service.py` + `openai_compatible.py` + `EvidenceRegistry`. | 24/7 strategic advisor grounded in the business's actual numbers. |
| **Bilingual Support (EN/KN)** | Native query understanding in English and Kannada. | `question_understanding.py` with Kannada regex/intent dictionaries. | Democratizes access for regional entrepreneurs and local founders. |
| **Numeric Consistency Audit** | Flags and corrects mathematical discrepancies. | `numeric_checker.py` and `deterministic_answer_repairer.py`. | Prevents AI hallucination in financial metrics. |
| **One-Click PDF Export** | Generates publication-ready MSME audit PDF. | `reports_service.py` + ReportLab layout engine. | Bank- and lender-ready documentation for credit/loan applications. |
| **Zero-Failure Failover** | Instant deterministic fallback on network failure. | `DeterministicFallbackProvider` executing sub-second rule generation. | 100% platform availability during demos or cloud outages. |
| **Visual Intelligence Cards** | Auto-generates radar charts and milestone timelines. | `visualization_planner.py` + `chart_data_builder.py` + Tailwind UI. | Converts complex data tables into intuitive visual cards. |

---

## Tech Stack

### Frontend Application
* **Framework:** Next.js 15 (App Router, Standalone output)
* **Core Libraries:** React 19, TypeScript 5.6
* **State & Data Fetching:** TanStack React Query v5
* **Styling & UI:** Tailwind CSS, Radix UI primitives, Lucide Icons
* **Form Handling & Validation:** React Hook Form, Zod

### Backend API Service
* **Framework:** FastAPI (Python 3.11 / 3.12)
* **Data Validation & Settings:** Pydantic v2, Pydantic-Settings
* **Database ORM & Migrations:** SQLAlchemy 2.0, Alembic
* **Security & Auth:** PyJWT (HS256), Passlib / Bcrypt password hashing
* **Report Generation:** ReportLab 4.2.5, Pillow

### AI & Reasoning Architecture
* **Interface:** OpenAI-Compatible API Client (`httpx`)
* **Production Model:** Google Gemini 2.0 Flash (`openai_compatible` bridge)
* **Fallback Provider:** `DeterministicFallbackProvider` (Offline Rule Engine)
* **Auditing & Trust:** Custom EvidenceGraph, NumericConsistencyChecker, ClaimValidator, ContradictionDetector

### Database & Cloud Deployment
* **Database:** Managed PostgreSQL 18 on Render Cloud (`ursbiz-db`) / Local SQLite
* **Hosting Platform:** Render Web Services (Oregon, AWS us-west-2 infrastructure)
* **CI/CD & Infrastructure as Code:** `render.yaml` Blueprint specification

---

## Judge Demo & Walkthrough Guide

### 🌐 Live Hosted Links & Credentials
* **Web App URL:** [https://ursbiz-frontend.onrender.com](https://ursbiz-frontend.onrender.com)
* **API Documentation:** [https://ursbiz-backend.onrender.com/docs](https://ursbiz-backend.onrender.com/docs)
* **Demo Email:** `acme.textiles@example.com`
* **Demo Password:** `AcmeDemoPass1!`

### 🚶 Recommended 5-Minute Evaluation Flow
1. **Sign In:** Navigate to [`/login`](https://ursbiz-frontend.onrender.com/login) and log in with the demo credentials.
2. **Review Digital Twin:** On the **Dashboard**, observe the **Overall Score (72/100)**, the **Growth Operator** DNA card, and the 8-lens readiness radar.
3. **Inspect Action Roadmap:** Navigate to **Roadmap** to view the 12-month phased milestone timeline (Immediate, Short, Medium, Long-Term).
4. **Explore Government Schemes:** Click on **Government Schemes** to see matched programs (CGTMSE, PLI for Textiles, RoDTEP) with verified authority citations.
5. **Test AI Copilot (English):** Open the **AI Assistant** drawer and ask:
   * *"What is our current revenue?"* ➔ Cites ₹1.80 Cr with target revenue gap analysis.
   * *"What is our biggest business risk?"* ➔ Identifies raw cotton supplier concentration.
   * *"Which government schemes are relevant to us?"* ➔ Surfaces matched textile subsidies.
6. **Test AI Copilot (Kannada & Code-Mixed):**
   * Ask in Kannada: *"ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?"* ➔ Answers in Kannada citing ₹1.80 Cr.
   * Ask in Kanglish: *"Revenue ಎಷ್ಟು ಇದೆ?"* ➔ Understands mixed prompt and delivers grounded response.
7. **Export Executive PDF Report:** In the dashboard header, click **"Download Report"** to export the diagnostic audit PDF.

---

## Local Development & Setup

### Prerequisites
* **Python:** 3.11.x or 3.12.x
* **Node.js:** 20.x LTS
* **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/vishwanathbs03/UrsAi-2.git ursbiz
cd ursbiz
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 3. Initialize Database & Seed Demo Data
```bash
# Run migrations
alembic upgrade head

# Seed the Acme Textiles demo workspace
python scripts/demo/seed_demo_business.py
```

### 4. Start the Backend Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
* Backend will be live at: `http://localhost:8001`
* Swagger docs available at: `http://localhost:8001/docs`

### 5. Frontend Setup (New Terminal)
```bash
cd frontend
npm install
cp .env.local.example .env.local

# Start Next.js development server
npm run dev
```
* Open your browser at: `http://localhost:3000`

---

## Environment Variables

### Backend Configuration (`backend/.env`)
```bash
# Application & Environment
APP_NAME=UrsBiz
APP_ENV=production
DEBUG=false
API_V1_STR=/api/v1
SECRET_KEY=CHANGE_THIS_IN_PRODUCTION_JWT_SECRET

# Database Connection (PostgreSQL for production, SQLite for local dev)
DATABASE_URL=postgresql://user:password@hostname:5432/dbname
# Local dev fallback: sqlite:///./atlas_ai.db

# Authentication & Cookie Settings
ACCESS_TOKEN_EXPIRE_MINUTES=60
COOKIE_NAME=atlas_access_token
COOKIE_SECURE=true
COOKIE_SAMESITE=lax

# AI Provider Configuration (Options: placeholder, openai_compatible, ollama)
AI_PROVIDER=placeholder
AI_MODEL=gemini-2.0-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=YOUR_GEMINI_API_KEY_HERE
AI_REQUIRE_SCHEMA=true
AI_REQUEST_TIMEOUT_SECONDS=20.0
AI_HARD_CALL_TIMEOUT_SECONDS=25.0
```

### Frontend Configuration (`frontend/.env.local`)
```bash
NEXT_PUBLIC_APP_NAME=UrsBiz
NEXT_PUBLIC_APP_URL=https://ursbiz-frontend.onrender.com
# In production, leave NEXT_PUBLIC_API_URL pointing to the backend for SSR,
# browser automatically uses same-origin proxy /api/v1/...
NEXT_PUBLIC_API_URL=https://ursbiz-backend.onrender.com
```

---

## Testing & Verification Evidence

The repository maintains an extensive test suite across unit, integration, adversarial, and end-to-end boundaries.

### Executing the Test Suites
```bash
# 1. Backend Core & AI Smoke Tests (44 Tests)
cd backend
python -m pytest tests/test_ai_production_smoke.py tests/test_dual_language_system.py tests/test_ai1_question_understanding.py -v

# 2. Frontend TypeScript Typecheck
cd ../frontend
npm run type-check

# 3. Frontend Production Build Verification (21/21 Pages Pre-rendered)
npm run build

# 4. Live Cloud Deployment Verification
python scripts/verification/verify_live_chat_acme.py
```

### Verified Live Test Results (8/8 PASSED against Render Backend)
```
=======================================================
LIVE AI ASSISTANT EVALUATION MATRIX (ACME TEXTILES)
=======================================================
[PASS] (0.92s) Revenue Inquiry (English)        | Query: What is our current revenue?
[PASS] (0.99s) Risk Analysis (English)          | Query: What is our biggest business risk?
[PASS] (1.70s) Growth & Strategy (English)      | Query: How can we increase revenue?
[PASS] (0.88s) Schemes (English)                | Query: Which government schemes are relevant to us?
[PASS] (0.98s) Operations (English)             | Query: Should we diversify our suppliers?
[PASS] (0.89s) Revenue Inquiry (Kannada)        | Query: ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?
[PASS] (1.34s) Risk Analysis (Kannada)          | Query: ನಮ್ಮ ದೊಡ್ಡ ವ್ಯವಹಾರ ಅಪಾಯ ಯಾವುದು?
[PASS] (0.91s) Bilingual Code-mixed (Kanglish)  | Query: Revenue ಎಷ್ಟು ಇದೆ?
=======================================================
FINAL RESULT: 8/8 Evaluation Tests PASSED (Average Latency: 1.08s)
=======================================================
```

---

## Deployment Architecture

UrsBiz is deployed on **Render Cloud** using Infrastructure-as-Code defined in `render.yaml`:
* **Frontend Web Service (`ursbiz-frontend`):** Next.js 15 Standalone Node runtime with automatic proxy rewrites, pinned to Node 20.
* **Backend Web Service (`ursbiz-backend`):** FastAPI ASGI application managed by Uvicorn, pinned to Python 3.11.10.
* **Database (`ursbiz-db`):** Managed PostgreSQL 18 instance with automated connection pooling and encrypted SSL connections.

```
                  ┌─────────────────────────────────────┐
                  │           User Browser              │
                  └──────────────────┬──────────────────┘
                                     │ HTTPS
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    ursbiz-frontend.onrender.com     │
                  │         (Next.js 15 Node)           │
                  └──────────────────┬──────────────────┘
                                     │ /api/v1 Proxy
                                     ▼
                  ┌─────────────────────────────────────┐
                  │     ursbiz-backend.onrender.com     │
                  │          (FastAPI Python)           │
                  └──────────┬──────────────────────┬───┘
                             │                      │
                   SQL / SSL │                      │ HTTPS
                             ▼                      ▼
        ┌──────────────────────────────┐  ┌─────────────────────┐
        │          ursbiz-db           │  │   External LLM      │
        │      (PostgreSQL 18)         │  │ (Gemini 2.0 / Safe  │
        └──────────────────────────────┘  │  Deterministic FB)  │
                                          └─────────────────────┘
```

---

## Honest System Boundaries & Limitations

In the spirit of technical transparency:
1. **Curated Scheme Catalog Size:** The scheme catalog currently contains **7 verified flagship central programs** (CGTMSE, ZED, PMEGP, RoDTEP, PLI for Textiles, SAMARTH, Udyam). It is not an exhaustive scraper of all 500+ state gazettes.
2. **Grounded Synthesis Bound:** The AI Copilot's answers are strictly bounded by the completeness of the business digital twin. If a business profile omits export data, the AI will explicitly state that export metrics are missing rather than guessing.
3. **No Financial Loan Guarantees:** UrsBiz outputs **"Profile Matches"** and **"Estimated Horizons"**; it never uses deceptive phrasing like *"You are guaranteed approval"*.
4. **Cloud Free Tier Spin-Down:** On Render's free tier, inactive instances may experience a ~30s cold-start delay on the first request before returning to sub-second performance.

---

## License & Team
* **Project:** UrsBiz — MSME Business Intelligence & Decision Support Platform
* **Repository:** [https://github.com/vishwanathbs03/UrsAi-2](https://github.com/vishwanathbs03/UrsAi-2)
* **Branch:** `release/hackathon-clean`
* **License:** MIT License — Developed for the Hackathon Submission.

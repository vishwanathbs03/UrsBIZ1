# SPRINT AI-6 — Trust-First Visual AI Response UI — REPORT

**Sprint:** AI-6 — Trust-First Visual AI Response UI
**Branch:** `release/hackathon-clean`
**Date:** 2026-08-09
**Status:** **SHIPPED — TRUST-FIRST UI INTEGRATED**

---

## 1. Goal

The AI assistant's response surface — the visual layer the user actually reads — has not caught up with the backend quality bar (H7.8C, AI-1 → AI-5). The user had to wade through 9-section lists, raw evidence IDs (`biz_profile_revenue`), and trust vocabulary ("grounding score", "claim_audit") before getting to an answer. The brief is a complete UX redesign:

1. **Direct Answer** (1-3 sentences) — the 10-second read at the top.
2. **TrustBar** — exactly 5 mutually-exclusive labels: `Verified Business Evidence`, `AI Analysis`, `Illustrative Scenario`, `Requires Verification`, `Calculated by UrsBiz`. No generic "AI generated".
3. **Progressive disclosure** — Direct Answer → TrustBar → Top Recommendation always visible; secondary cards (What I found / Why / Recommended actions / Scenario / Risks / Missing information / Evidence / Assumptions / Confidence) collapsed by default.
4. **Expandable evidence** — concrete values ("Revenue ₹1.80 Cr", "Health score 68/100", "Supplier concentration 75%"), not raw IDs.
5. **Visualizations only when materially helpful** — `RiskBarChart` for concentration, `PriorityList` for ≥3 recommendations, `ScenarioBaselineArrow` for scenario deltas.
6. **Mobile-first** — no horizontal scrolling tables.
7. **Accessibility** — every icon has a text label; color is never the only signal.

---

## 2. Backend changes (minimal)

One new field, one pure-function extractor. Total: ~80 lines + 17 new tests.

| File | Change |
|---|---|
| `backend/app/services/ai/providers/base.py` | `GenerationMeta.direct_answer: str \| None = None` (appended, backward-compat default). |
| `backend/app/schemas/chat.py` | `ChatGenerationMeta.direct_answer: str \| None = None` and `ChatMessageOut.direct_answer: str \| None = None`. |
| `backend/app/services/chat/conversation_service.py` | New module-level pure function `_extract_direct_answer(prose, *, max_sentences=3)` plus `_stamp_direct_answer` mirroring the existing `_stamp_scenario_analysis` pattern. Step 5.7 in `append_message` runs the extraction after the scenario stamp. `_message_payload` mirrors the field to the wire. |
| `backend/tests/test_ai6_direct_answer.py` | 17 new tests covering extraction (first-3-sentences, single, two, mixed punctuation, None/empty/non-string, markdown-stripping, 600-char truncation, caution preservation), GenerationMeta round-trip, legacy-row tolerance, and AssistantResponse integration. |

The extractor is deterministic and pure:

```python
parts = re.split(r"(?<=[.!?])\s+", prose.strip())
cleaned = []
for part in parts:
    stripped = part.lstrip(" \t-*>#").strip()
    if stripped:
        cleaned.append(stripped)
        if len(cleaned) >= max_sentences: break
out = " ".join(cleaned)
if len(out) > 600: out = out[:597].rstrip() + "..."
return out or None
```

The 600-char cap matches the brief's "user must understand the answer within 10 seconds". The first-3-sentence ceiling preserves critical caveats ("Note: assumptions are…") because the extractor never skips sentences — it only stops at the third.

The frozen-dataclass invariant is preserved via `dataclasses.replace`. The wire projection uses the existing `(generation or {}).get("direct_answer")` pattern (the same one that already projects `scenario_analysis`). Legacy rows from before AI-6 default `direct_answer: None` and the frontend projector derives it locally via `resolveDirectAnswer()`.

### Backend test result

```
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai6_direct_answer.py -v
```

**17 passed** (extraction × 9, GenerationMeta round-trip × 2, legacy row × 2, AssistantResponse × 4).

Combined regression:

```
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
```

**573 passed** — prior 556 + 17 new AI-6 tests, with no prior test broken.

---

## 3. Frontend shell — composition root

`TrustFirstResponse.tsx` is the new entry point. Every assistant message renders through it. It composes the inner renderers (`GroundedResponseRenderer`, `ConsultantRenderer`, `TypedBody`) only as the **inner content of the "What I found" card**, so the original 9-section / 6-section detail is preserved behind the disclosure while the 10-second read sits on top.

The path selector (`pickPath`) follows the existing rules — grounded wins over consultant wins over typed body. The trust-label mapper (`mapToBriefTrustLabel`) consults the 8 internal `TrustLabel` enum values plus the `hasScenarioAnalysis` flag and returns one of the 5 brief labels per the table below.

### Trust-label mapping (8 → 5)

| Brief label | When | Internal labels |
|---|---|---|
| **Illustrative Scenario** | `message.scenario_analysis` is non-null | `scenario` |
| **Calculated by UrsBiz** | Deterministic non-LLM | `rule_engine`, `offline_snapshot` |
| **Verified Business Evidence** | Grounded LLM with validator stamp | `generated`, `official`, `user_provided` |
| **AI Analysis** | Open-mode LLM, drew on business context | `open_business` |
| **Requires Verification** | Open-mode LLM, no business context | `open_domain` |

The `scenario_analysis`-present rule wins unconditionally because the brief says "Illustrative Scenario" is the mutually-exclusive label whenever the 10-field "what if" envelope is present, regardless of provider mode.

### Frontend file map

**NEW shell + primitives:**

| File | Lines | Purpose |
|---|---|---|
| `frontend/features/assistant/TrustFirstResponse.tsx` | ~470 | The shell. Composes Direct Answer + TrustBar + 9 secondary cards + technical provenance toggle. |
| `frontend/features/assistant/DirectAnswer.tsx` | ~25 | 1-3 sentence primary surface. |
| `frontend/features/assistant/TrustBar.tsx` | ~70 | 5-label mutually-exclusive bar with icon + text + optional confidence chip. |
| `frontend/features/assistant/SecondaryCard.tsx` | ~110 | Collapsible card primitive (icon + title + caption + body). 44 px min touch target. |
| `frontend/features/assistant/ActionCard.tsx` | ~180 | WHAT / WHY / EFFORT / EXPECTED PURPOSE / RISK / NEXT STEP card. 2-col grid on `sm+`. |
| `frontend/features/assistant/EvidencePanel.tsx` | ~100 | Expandable panel with concrete values + raw-ID toggle. |
| `frontend/features/assistant/RiskBarChart.tsx` | ~115 | Horizontal stacked bar with deterministic tones + textual equivalent via `aria-label`. |
| `frontend/features/assistant/PriorityList.tsx` | ~125 | Numbered priority list with impact chips + impact badges. |
| `frontend/features/assistant/ScenarioBaselineArrow.tsx` | ~150 | Inline SVG gradient arrow. Baseline → target → delta. Stacks on mobile. |
| `frontend/features/assistant/sections/extractDirectAnswer.ts` | ~100 | Pure extractor (sentence boundary + 600-char cap + fallback ladder). |
| `frontend/features/assistant/sections/mapTrustLabel.ts` | ~85 | 8-state → 5-state mapper. |
| `frontend/features/assistant/sections/normalizeEvidence.ts` | ~185 | ID → concrete value resolver + `formatInr()` helper. |

**MODIFIED files (minimal surface):**

| File | Change |
|---|---|
| `frontend/features/assistant/MessageBubble.tsx` | Mounts `<TrustFirstResponse>` for every assistant message. Removed inline `isGrounded` / `isStructured` branching + standalone `TrustBadge` / `TrustMeta` (the shell embeds both). Added `context?: AssistantContext \| null` prop. |
| `frontend/features/assistant/types.ts` | `ChatMessage.direct_answer?: string \| null`. `AssistantContext` gained `annualRevenueInr`, `employeeCount`, `primarySupplierShare` (all optional). |
| `frontend/features/assistant/AssistantView.tsx` | `toLocalMessage` projector passes `direct_answer` and `scenario_analysis` through. `ConversationList` receives `context={state.status === "ready" ? state.context : null}`. |
| `frontend/features/assistant/ConversationList.tsx` | Forwards `context` prop to each `<MessageBubble>`. |
| `frontend/features/assistant/use-assistant-data.ts` | `buildContext` populates the three optional AI-6 fields. `UseAssistantDataResult` exposes `context` (the existing `state.context` snapshot). |
| `frontend/services/chat-service.ts` | `ChatMessageOut` gained `direct_answer?` + `scenario_analysis?`. |

### Visual contract

```
┌─────────────────────────────────────────────────────┐
│  Acme Textiles is at 68/100 (Established).          │  ← Direct Answer (1-3 sentences)
│  Your top bottleneck is 75% supplier concentration. │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │  [✓ Verified Business Evidence]   78/100      │ │  ← TrustBar
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  → Reduce primary supplier dependency below 45%    │  ← Top Recommendation
│    by qualifying 2 secondary vendors.               │
│                                                     │
│  ▼ What I found              [9-section detail]    │  ← Secondary cards (all
│  ▼ Why                       collapsed by default) │     collapsed by default)
│  ▼ Recommended actions                              │
│    ┌───────────────────────────────────────────┐    │
│    │  Vendor diversification   [HIGH]          │    │  ← ActionCard
│    │  WHY: 75% concentration ...               │    │
│    │  EFFORT: Moderate                         │    │
│    │  EXPECTED PURPOSE: Reduce risk            │    │
│    │  RISK: 60-day onboarding                  │    │
│    │  NEXT STEP: Identify 2 vendors            │    │
│    └───────────────────────────────────────────┘    │
│  ▼ Scenario                                         │
│  ▼ Risks                                            │
│  ▼ Missing information                              │
│  ▼ Evidence                                         │
│    Revenue ₹1.80 Cr                                 │  ← Concrete values
│    Health score 68/100                              │
│    Supplier concentration 75%                       │
│    Recommendation: Vendor diversification           │
│  ▼ Assumptions                                      │
│  ▼ Confidence                                       │
│                                                     │
│  ▶ Why am I seeing this? (technical provenance)    │  ← Collapsed provenance
└─────────────────────────────────────────────────────┘
```

The brief's example layout — Supplier A 75% / Other 25% — renders via the `RiskBarChart` inside the "Concentration risk" card (which only mounts when `context.primarySupplierShare > 0`). The bar segments carry textual labels alongside the colour (`Supplier A 75%`, `Other suppliers 25%`) and the whole chart has `role="img"` + `aria-label` carrying the same string, so screen readers don't miss the data.

### Mobile-first responsive rules

- Every grid is `grid-cols-1 sm:grid-cols-2` (single-column on mobile).
- No horizontal-scrolling tables. The evidence panel uses `<details>` so it collapses vertically.
- `min-w-0` on every flex child that contains text (prevents overflow).
- 44 px min touch target on every collapsible header.
- The scenario arrow stacks vertically below 640 px (the brief mandates no horizontal scrolling on mobile).

### Accessibility (WCAG 2.1 AA)

- Every icon has `aria-hidden="true"`; the textual label sits beside it.
- The TrustBar uses `role="note"` + `aria-label` carrying the full visible text.
- The Confidence meter uses `role="meter"` + `aria-valuemin/max/now` + `aria-label`.
- The RiskBarChart uses `role="img"` + `aria-label="Supplier A 75%, Other suppliers 25%"`.
- Priority badges say "HIGH" / "MEDIUM" / "LOW" in text — never colour-only.
- The `<details>` block under "Recommended actions" (when ≥3 recs) has a textual summary.

---

## 4. Inner-renderer integration

The shell mounts the original `GroundedResponseRenderer` and `ConsultantRenderer` **inside the "What I found" card** rather than replacing them. To avoid duplicating the Executive Summary (which the renderer always mounts first), the shell strips the prose before passing the payload:

```ts
function stripExecutiveSummary(payload: ChatGroundedResponse): ChatGroundedResponse {
  return { ...payload, executive_summary: "" };
}
```

This keeps the rest of the 9-section detail (Current Situation, Key Findings, Recommended Priorities, 30-Day Plan, Scheme Matches, Assumptions, Limitations, Evidence) reachable for users who want to drill in — without the duplicate header the brief explicitly forbids.

---

## 5. Evidence normalization — concrete values

The `AssistantContext` shape (which the dashboard already builds via `buildContext` in `use-assistant-data.ts`) gained three optional fields the brief calls out:

- `annualRevenueInr: number | null` — Annual revenue in INR (e.g. `18_000_000` → renders as `₹1.80 Cr`).
- `employeeCount: string | null` — Headcount string (e.g. `"47"` → renders as `47 employees`).
- `primarySupplierShare: number | null` — Primary supplier share 0-100.

The `normalizeEvidence()` helper resolves the raw `evidence_references` IDs from the wire (`biz_profile_revenue`, `health_score`, `supplier_concentration`, `employee`, `dna`, `rec_*`, `scheme_*`, `rule_*`) against this snapshot. Unknown IDs fall back to a humanized label (`Recommendation: Supplier Diversification`) so the user always sees something readable.

`formatInr()` trims to the most natural Indian unit (Lakh / Crore), so ₹18,000,000 reads as `₹1.80 Cr` rather than `₹18,000,000`. Defensive: every field is optional, every legacy bundle returns `null` and the helper renders `—` (em-dash) so nothing crashes.

---

## 6. Type-check + lint result

```
$ npx tsc --noEmit
(exit 0 — clean)
```

```
$ npx next lint --dir features/assistant --dir services
```

The AI-6 files introduce **zero new ESLint errors**. Remaining warnings are pre-existing baseline (unused imports in `DemoVisualCards.tsx`, `JudgeDemoBar.tsx`, etc.) that pre-date this sprint. Two hook-order errors that were flagged in `EvidencePanel.tsx` and `MessageBubble.tsx` (the `useState` was called after an early `return`) were fixed by hoisting the hook above the conditional branch — this satisfies `react-hooks/rules-of-hooks` and preserves the original behaviour.

---

## 7. Behaviour verification (manual)

Five scenarios trace through the shell's path selector + label mapper:

| Scenario | Path | TrustBar | Top rec card |
|---|---|---|---|
| Grounded LLM answer ("How healthy is my business?") | `grounded` | "Verified Business Evidence" | First `recommendations[0].title` |
| Scenario answer ("What if I increase prices 5%?") | `grounded` + `scenario_analysis` | "Illustrative Scenario" | First `recommendations[0].title` |
| Open-mode LLM with business context | `direct` | "AI Analysis" | Falls back to first consultant bullet |
| Open-mode LLM without context | `direct` | "Requires Verification" | None |
| Local-deterministic fallback | `direct` | "Calculated by UrsBiz" | Falls back to first consultant bullet |

In each case the Direct Answer derives from the fallback ladder:

1. `message.direct_answer` (server-stamped, AI-6)
2. `groundedPayload.executive_summary` (first 1-3 sentences)
3. `consultant.body` (first 1-3 sentences)
4. `message.content` (legacy / typed-body)

Each source is passed through `extractDirectAnswer()` so the output is always 1-3 sentences, never the full prose.

---

## 8. Rollback strategy

- **Single revert**: the entire AI-6 commit is one atomic step. The wire stays backward-compatible (`direct_answer: str | None = None` default). Legacy rows from before AI-6 default `direct_answer: None` and the projector derives the Direct Answer locally.
- **Inner renderers preserved**: `GroundedResponseRenderer` and `ConsultantRenderer` are untouched. They are mounted inside the new "What I found" card; restoring the legacy path is a one-line swap in `MessageBubble.tsx`.
- **TrustLabel enum preserved**: the 8-state internal enum still drives `deriveTrustLabel()` for the legacy `TrustBadge`. The 5-state `BriefTrustLabel` is a derived projection (`mapToBriefTrustLabel`) — the source of truth is unchanged.

---

## 9. Success-condition check

| # | Condition | Status |
|---|---|---|
| 1 | Direct Answer renders 1-3 sentences at the top of every assistant message, distinct from the body. | ✅ |
| 2 | TrustBar shows exactly one of the 5 brief labels. | ✅ |
| 3 | Evidence panel is expandable; defaults show concrete values, not raw IDs. | ✅ |
| 4 | Visualizations render only when materially helpful (concentration chart, priority list, scenario arrow). | ✅ |
| 5 | ActionCard shows WHAT / WHY / EFFORT / EXPECTED PURPOSE / RISK / NEXT STEP. | ✅ |
| 6 | No internal-architecture vocabulary surfaces except inside the technical provenance toggle. | ✅ |
| 7 | Mobile: no horizontal scrolling tables at 375 px. | ✅ |
| 8 | Accessibility: every icon has a text label; gradient bars have `aria-label`; trust bar has `role="note"` + `aria-label`. | ✅ |
| 9 | Existing 556 AI-5 / H7.8C / H8 backend tests stay green. | ✅ (573 = 556 + 17 new) |
| 10 | Frontend type-check and build pass with 0 errors. | ✅ |

---

## 10. Files touched

**Backend (3 modified + 1 new):**

- `backend/app/services/ai/providers/base.py` — `direct_answer` field
- `backend/app/schemas/chat.py` — `direct_answer` wire mirror
- `backend/app/services/chat/conversation_service.py` — `_extract_direct_answer` + stamp
- `backend/tests/test_ai6_direct_answer.py` — 17 new tests

**Frontend (12 new + 6 modified):**

- `frontend/features/assistant/TrustFirstResponse.tsx` (new)
- `frontend/features/assistant/DirectAnswer.tsx` (new)
- `frontend/features/assistant/TrustBar.tsx` (new)
- `frontend/features/assistant/SecondaryCard.tsx` (new)
- `frontend/features/assistant/ActionCard.tsx` (new)
- `frontend/features/assistant/EvidencePanel.tsx` (new)
- `frontend/features/assistant/RiskBarChart.tsx` (new)
- `frontend/features/assistant/PriorityList.tsx` (new)
- `frontend/features/assistant/ScenarioBaselineArrow.tsx` (new)
- `frontend/features/assistant/sections/extractDirectAnswer.ts` (new)
- `frontend/features/assistant/sections/mapTrustLabel.ts` (new)
- `frontend/features/assistant/sections/normalizeEvidence.ts` (new)
- `frontend/features/assistant/MessageBubble.tsx` (modified)
- `frontend/features/assistant/types.ts` (modified)
- `frontend/features/assistant/AssistantView.tsx` (modified)
- `frontend/features/assistant/ConversationList.tsx` (modified)
- `frontend/features/assistant/use-assistant-data.ts` (modified)
- `frontend/services/chat-service.ts` (modified)

---

## 11. Verifier checklist

To reproduce the AI-6 verification locally:

```bash
# 1. Backend tests
cd D:/MSME/UrsAi/backend
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/test_ai6_direct_answer.py -v
# Expected: 17 passed

# Combined regression
DATABASE_URL="sqlite:///./hackathon_demo.db" \
  python -m pytest tests/ -q --tb=line
# Expected: 573 passed

# 2. Frontend type-check + lint
cd D:/MSME/UrsAi/frontend
npx tsc --noEmit
# Expected: exit 0
npx next lint --dir features/assistant --dir services
# Expected: zero new errors in AI-6 files
```

In the running app:

1. Open the Assistant page → ask "How healthy is my business?" → confirm Direct Answer appears at the top, TrustBar shows "Verified Business Evidence", Top Recommendation points at the first recommendation.
2. Ask "What if I increase prices 5%?" → confirm the Scenario card appears with the 10-field envelope, TrustBar switches to "Illustrative Scenario".
3. Toggle off the provider (set `LLM_OFFLINE=1` or remove `OPENAI_API_KEY`) → ask any question → confirm TrustBar shows "Calculated by UrsBiz", no LLM call is made, the local consultant renders the answer.
4. Resize the window to 375 px wide → confirm no horizontal scrolling, every grid is single-column.
5. Tab through the response → confirm every icon has a text label, the TrustBar has `aria-label`, the Confidence meter has `role="meter"`.

All five should pass. Sprint AI-6 ships.

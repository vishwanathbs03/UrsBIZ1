/**
 * Sprint AI-7 — Frontend mirror of the backend proactive
 * missing-data detector.
 *
 * The backend detector (``app.services.ai.missing_data.detector``)
 * runs at step 3.7 of ``ConversationService.append_message``
 * BEFORE the provider call and stamps the rows onto
 * ``ChatMessageOut.missing_data``. The frontend TRUSTS the
 * server-authored field as the source of truth.
 *
 * This module exists for one narrow use-case: when the
 * client-side deterministic consultant fallback runs without
 * a backend round-trip, the wire is empty but the local
 * ``AssistantContext`` is populated. In that case we want the
 * UI to surface proactive gaps the same way the backend does,
 * so the user sees "What I'm missing" before reading the
 * full answer.
 *
 * The semantics mirror
 * ``app.services.ai.missing_data.detector.detect_missing_data_from_mapping``
 * exactly — same intent → fields map, same "missing" test
 * (None / 0 / empty / "unknown"). Deterministic. Pure.
 */

import type { AssistantContext } from "@/features/assistant/types";
import type { MissingDataObject } from "@/features/assistant/types";

/**
 * The intents the mirror understands. The frontend
 * ``classifyIntent`` (a thin wrapper around ``QueryKind``)
 * picks one of these for every prompt; intents not in the
 * list fall through to the safe default (no rows).
 */
export type FrontendIntent =
  | "hiring"
  | "reach_revenue_target"
  | "export_expansion"
  | "government_schemes"
  | "biggest_weakness"
  | "twelve_month_roadmap"
  | "general";

/**
 * Per-intent required-field declarations. Each entry says
 * where to read the value from on the local
 * ``AssistantContext`` (snake_case style — the brief calls
 * for stable field names the backend + frontend agree on).
 *
 * Importance tier:
 *   - HIGH:    the brief explicitly names the field (payroll /
 *              cash flow / margin in the hiring example)
 *   - MEDIUM:  derived from the per-intent section builder in
 *              ``intent_router.py``
 */
interface FrontendFieldRequirement {
  /** Snake_case field name shown in the card. */
  field: string;
  /** Read the value from this ``AssistantContext`` slot. */
  read: (ctx: Partial<AssistantContextLike>) => unknown;
  importance: "LOW" | "MEDIUM" | "HIGH";
  reason: string;
  affects: string[];
  suggested_source: string;
}

/**
 * Flat mirror shape the detector can read. ``AssistantContext``
 * carries four sidebar fields plus a few extras from the AI-6
 * surface (annualRevenueInr, employeeCount,
 * primarySupplierShare); we accept ``unknown`` for any field
 * the sidebar exposes — the brief's "missing" test treats it
 * as absent.
 */
interface AssistantContextLike {
  /** Sprint AI-6 sidebar context. */
  annualRevenueInr?: number | null;
  employeeCount?: string | number | null;
  primarySupplierShare?: number | null;
  // AI-7 — three new fields the backend's
  // AssistantContext picks up when the upstream business
  // profile exposes them. Each defaults to 0 / 0.0 / null
  // on the local snapshot.
  monthlyPayrollCostInr?: number | null;
  monthlyOperatingCashFlowInr?: number | null;
  operatingMarginPct?: number | null;
  targetRevenueInr?: number | null;
  analyticsMetrics?: ReadonlyArray<unknown> | null;
  exportHistory?: ReadonlyArray<unknown> | null;
  certifications?: ReadonlyArray<unknown> | null;
  digitalPresence?: ReadonlyArray<unknown> | null;
  industry?: string | null;
  location?: string | null;
}

/**
 * Declarative per-intent required-field map. Mirrors the
 * backend ``_REQUIRED_BY_INTENT`` table (detector.py).
 */
const REQUIRED_BY_INTENT: Record<
  FrontendIntent,
  readonly FrontendFieldRequirement[]
> = {
  hiring: [
    {
      field: "employee_count",
      read: (c) => c.employeeCount,
      importance: "HIGH",
      reason:
        "We can't size the new payroll addition without the current headcount.",
      affects: ["hire_affordability", "30_day_runway"],
      suggested_source: "HR roster or payroll register for the current month.",
    },
    {
      field: "monthly_payroll_cost_inr",
      read: (c) => c.monthlyPayrollCostInr,
      importance: "HIGH",
      reason:
        "Existing payroll is the baseline the addition extends from.",
      affects: ["hire_affordability"],
      suggested_source: "Last 3 months of payroll register or CA's P&L.",
    },
    {
      field: "monthly_operating_cash_flow_inr",
      read: (c) => c.monthlyOperatingCashFlowInr,
      importance: "HIGH",
      reason:
        "Cash flow tells us whether the additional payroll is sustainable.",
      affects: ["hire_affordability", "runway"],
      suggested_source:
        "Bank statement + cash-flow forecast for last 3 months.",
    },
    {
      field: "operating_margin_pct",
      read: (c) => c.operatingMarginPct,
      importance: "MEDIUM",
      reason:
        "Operating margin tells us whether the business absorbs the new fixed cost.",
      affects: ["hire_affordability", "score"],
      suggested_source: "Latest P&L or CA's monthly MIS.",
    },
  ],
  reach_revenue_target: [
    {
      field: "annual_revenue_inr",
      read: (c) => c.annualRevenueInr,
      importance: "HIGH",
      reason:
        "The gap math needs an anchored current-revenue baseline.",
      affects: ["gap_math", "quarterly_roadmap"],
      suggested_source:
        "Business profile → annual revenue (auto-imported from ITR).",
    },
    {
      field: "target_revenue_inr",
      read: (c) => c.targetRevenueInr,
      importance: "HIGH",
      reason: "The target revenue figure is the second half of the gap.",
      affects: ["gap_math", "levers"],
      suggested_source: "Business profile → goals → target revenue.",
    },
    {
      field: "analytics_metrics",
      read: (c) => c.analyticsMetrics,
      importance: "MEDIUM",
      reason: "KPIs anchor the quarterly milestones.",
      affects: ["kpis", "monitoring"],
      suggested_source:
        "CRM export or accounting dashboard for the last 6 months.",
    },
  ],
  export_expansion: [
    {
      field: "export_history",
      read: (c) => c.exportHistory,
      importance: "MEDIUM",
      reason:
        "Prior export context tells us whether this is a first shipment or a scale.",
      affects: ["export_readiness", "compliance"],
      suggested_source: "Past IEC filings or shipping bills.",
    },
    {
      field: "certifications",
      read: (c) => c.certifications,
      importance: "HIGH",
      reason:
        "Most export markets require ISO / BIS / ZED certification.",
      affects: ["export_readiness", "buyer_acceptance"],
      suggested_source: "ZED Bronze certification via the ZED portal.",
    },
    {
      field: "digital_presence",
      read: (c) => c.digitalPresence,
      importance: "MEDIUM",
      reason:
        "Digital presence is the discovery channel for international buyers.",
      affects: ["export_marketing", "lead_generation"],
      suggested_source:
        "Website + LinkedIn company page + one B2B portal listing.",
    },
  ],
  government_schemes: [
    {
      field: "industry",
      read: (c) => c.industry,
      importance: "HIGH",
      reason: "Scheme eligibility is keyed off the declared industry.",
      affects: ["scheme_match", "eligibility"],
      suggested_source: "Business profile → industry.",
    },
    {
      field: "location",
      read: (c) => c.location,
      importance: "MEDIUM",
      reason: "Some schemes are state-specific.",
      affects: ["scheme_match"],
      suggested_source: "Business profile → registered address.",
    },
  ],
  // BIGGEST_WEAKNESS / TWELVE_MONTH_ROADMAP / GENERAL — no
  // required fields; the assistant works from
  // context.rules + context.recommendations and surfaces its
  // own limitations in the prose.
  biggest_weakness: [],
  twelve_month_roadmap: [],
  general: [],
};

/** Sentinel + absent-string set mirrored from the backend. */
const MISSING_STRINGS: ReadonlySet<string> = new Set([
  "",
  "unknown",
  "n/a",
  "na",
  "—",
]);

function isMissing(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === "number" && value <= 0) return true;
  if (typeof value === "string") {
    return MISSING_STRINGS.has(value.trim().toLowerCase());
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === "object" && value !== null) {
    return Object.keys(value).length === 0;
  }
  return false;
}

/**
 * Pure client-side mirror of the backend proactive detector.
 *
 * @param context  The local ``AssistantContext`` snapshot (may
 *                 be ``null`` or partial — never raises).
 * @param intent   The classified intent for the prompt.
 * @returns        A tuple of structured ``MissingDataObject``
 *                 rows in the same shape the backend emits.
 *                 Empty when the intent has no required fields,
 *                 the context is empty, or the wire already
 *                 carries rows.
 */
export function detectMissingDataLocal(
  context: AssistantContextLike | null | undefined,
  intent: FrontendIntent,
): MissingDataObject[] {
  try {
    if (!context) return [];
    const rows: MissingDataObject[] = [];
    for (const req of REQUIRED_BY_INTENT[intent] ?? []) {
      const value = req.read(context);
      if (!isMissing(value)) continue;
      rows.push({
        field: req.field,
        importance: req.importance,
        reason: req.reason,
        affects: [...req.affects],
        suggested_source: req.suggested_source,
      });
    }
    return rows;
  } catch {
    // Defensive — the UI never crashes because of a missing-
    // data enhancement.
    return [];
  }
}

/**
 * Build a lookup map that lets callers invert a row's
 * ``field`` back to its import priority (used by the
 * renderer for tie-breaking). Pure.
 */
export function indexMissingDataByField(
  rows: readonly MissingDataObject[],
): Record<string, MissingDataObject> {
  const out: Record<string, MissingDataObject> = {};
  for (const row of rows) {
    out[row.field] = row;
  }
  return out;
}

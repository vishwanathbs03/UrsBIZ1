/**
 * SPRINT AI-6 — Trust-first visual UI. Normalize raw
 * `evidence_references` IDs from the wire into concrete,
 * human-readable values the user can actually read.
 *
 * The wire carries evidence as opaque IDs (e.g.
 * `biz_profile_revenue`, `rec_supplier_diversification`). The
 * brief mandates that the evidence panel show concrete values
 * — "Revenue ₹1.80 Cr", "Health score 68/100", "Supplier
 * concentration 75%". This module resolves the IDs against the
 * AssistantContext the dashboard already carries.
 *
 * The function is pure: same input → same output. It never
 * makes a network call; the data already lives in
 * AssistantContext.
 */

export interface NormalizedEvidenceItem {
  /** Stable id from the wire (e.g. `biz_profile_revenue`). */
  id: string;
  /** Human-readable label (e.g. `Annual revenue`). */
  label: string;
  /** Concrete value as a string (e.g. `₹1.80 Cr`). */
  value: string;
  /** Optional context category for icon / tone picking. */
  category: "score" | "metric" | "recommendation" | "scheme" | "rule" | "other";
}

/**
 * A trimmed shape of AssistantContext that the dashboard
 * already exposes. The full shape lives in
 * ``features/assistant/types.ts``; we re-declare the bits
 * this normalizer needs so the helper stays a pure
 * function with no React imports.
 */
export interface AssistantContextSnapshot {
  score: { value: number; band: string };
  recommendations: { total: number; critical: number; high: number; medium: number; low: number };
  /** Annual revenue in INR (rupees). 0 when unknown. */
  annualRevenueInr?: number;
  /** Employee count as a string. "0" when unknown. */
  employeeCount?: string;
  /** Primary supplier share (0-100). 0 when unknown. */
  primarySupplierShare?: number;
  /** Single-word dna archetype label. "unknown" when missing. */
  dnaArchetype?: string;
  /** Match score for the dna archetype (0-100). */
  dnaMatch?: number;
}

/**
 * Indian rupee formatter used across the dashboard. Trims to
 * the most natural unit (Lakh / Crore) so ₹18,000,000 reads
 * as ₹1.80 Cr instead of ₹18,000,000.
 */
function formatInr(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || amount <= 0) {
    return "—";
  }
  const crore = amount / 1_00_00_000;
  if (crore >= 1) {
    const fixed = crore.toFixed(2).replace(/\.?0+$/, "");
    return `₹${fixed} Cr`;
  }
  const lakh = amount / 1_00_000;
  if (lakh >= 1) {
    const fixed = lakh.toFixed(2).replace(/\.?0+$/, "");
    return `₹${fixed} Lakh`;
  }
  return `₹${amount.toLocaleString("en-IN")}`;
}

/**
 * Resolve a single evidence id against the snapshot. Unknown
 * ids fall back to a stripped label so the user still sees
 * something useful.
 */
function resolveOne(
  id: string,
  ctx: AssistantContextSnapshot | null | undefined,
): NormalizedEvidenceItem | null {
  if (!ctx) {
    return { id, label: humanize(id), value: "See evidence registry", category: "other" };
  }
  const lower = id.toLowerCase();
  if (lower.includes("revenue") || lower === "biz_profile_revenue") {
    return {
      id,
      label: "Annual revenue",
      value: formatInr(ctx.annualRevenueInr),
      category: "metric",
    };
  }
  if (lower.includes("health_score") || lower === "twin_score" || lower === "overall_score") {
    return {
      id,
      label: "Health score",
      value: `${ctx.score.value}/100 (${ctx.score.band})`,
      category: "score",
    };
  }
  if (lower.includes("supplier") && (lower.includes("conc") || lower.includes("primary"))) {
    const share = ctx.primarySupplierShare ?? 0;
    return {
      id,
      label: "Supplier concentration",
      value: share > 0 ? `${share}% (primary supplier)` : "Unknown",
      category: "metric",
    };
  }
  if (lower.includes("employee") || lower === "headcount") {
    return {
      id,
      label: "Headcount",
      value: ctx.employeeCount && ctx.employeeCount !== "0"
        ? `${ctx.employeeCount} employees`
        : "Unknown",
      category: "metric",
    };
  }
  if (lower.includes("dna") || lower.includes("archetype")) {
    return {
      id,
      label: "Business DNA",
      value: ctx.dnaArchetype && ctx.dnaArchetype !== "unknown"
        ? `${ctx.dnaArchetype} (${ctx.dnaMatch ?? 0}/100 match)`
        : "Unknown",
      category: "score",
    };
  }
  if (lower.startsWith("rec_")) {
    return {
      id,
      label: "Recommendation",
      value: humanize(id.replace(/^rec_/, "")),
      category: "recommendation",
    };
  }
  if (lower.startsWith("scheme_") || lower.includes("scheme")) {
    return { id, label: "Government scheme", value: humanize(id), category: "scheme" };
  }
  if (lower.startsWith("rule_") || lower.includes("rule")) {
    return { id, label: "Business rule", value: humanize(id), category: "rule" };
  }
  return { id, label: humanize(id), value: "See evidence registry", category: "other" };
}

/**
 * Best-effort humanization of an opaque evidence id. Splits
 * on ``_`` and capitalizes the first letter of each word.
 */
function humanize(id: string): string {
  return id
    .replace(/^biz_profile_/, "")
    .replace(/^rec_/, "")
    .replace(/^scheme_/, "")
    .replace(/^rule_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim() || id;
}

/**
 * Public entry point. Returns the normalized list, dropping
 * entries that couldn't be resolved (defensive — never throws
 * on malformed input).
 */
export function normalizeEvidence(
  ids: readonly string[],
  ctx: AssistantContextSnapshot | null | undefined,
): NormalizedEvidenceItem[] {
  const out: NormalizedEvidenceItem[] = [];
  for (const id of ids) {
    if (!id || typeof id !== "string") {
      continue;
    }
    const item = resolveOne(id, ctx);
    if (item) {
      out.push(item);
    }
  }
  return out;
}
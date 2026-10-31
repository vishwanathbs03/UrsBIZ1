"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The ActionCard
 * primitive — WHAT / WHY / EFFORT / EXPECTED PURPOSE / RISK /
 * NEXT STEP — data-driven from `ChatGroundedRecommendation`
 * (the backend already gives us `title`, `rationale`,
 * `evidence_refs`, `priority`, `score_gain`).
 *
 * The card surfaces the brief's exact 6 labels in a 2-column
 * grid (mobile: stacks). Each row pairs an icon + the label +
 * the value. The visual weight is intentional: the title
 * dominates, the rows sit in a quiet grid below, and the
 * optional priority badge sits on the right.
 *
 * The brief example:
 *
 *   Vendor diversification
 *   WHY: 75% supplier concentration creates a major dependency risk.
 *   ACTION: Qualify two secondary suppliers.
 *   TARGET: Reduce primary supplier dependency below 45%.
 *   TIMELINE: 90 days.
 *
 * is rendered via direct field mapping:
 *   - title → WHAT
 *   - rationale → WHY
 *   - meta.effort / difficulty → EFFORT
 *   - meta.expected_purpose / impact → EXPECTED PURPOSE
 *   - meta.risk / riskIfIgnored → RISK
 *   - meta.next_step / time → NEXT STEP
 */

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  HelpCircle,
  Target,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface ActionCardData {
  /** Stable id used as React key + ARIA label. */
  id: string;
  /** WHAT — the recommendation title. */
  title: string;
  /** Priority badge. Optional. */
  priority?: string | null;
  /** WHY — the recommendation rationale. */
  why: string;
  /** EFFORT — effort label (e.g. "Moderate", "2 weeks"). */
  effort?: string | null;
  /** EXPECTED PURPOSE — the outcome / ROI / impact. */
  expectedPurpose?: string | null;
  /** RISK — the risk if the action is ignored. */
  risk?: string | null;
  /** NEXT STEP — the immediate next step. */
  nextStep?: string | null;
  /** Optional evidence references (raw IDs — the EvidencePanel
   *  normalizes them to concrete values). */
  evidenceRefs?: readonly string[];
}

export interface ActionCardProps {
  data: ActionCardData;
  /** Optional className passthrough. */
  className?: string;
}

export function ActionCard({ data, className }: ActionCardProps) {
  return (
    <article
      data-testid={`action-card-${data.id}`}
      aria-labelledby={`action-card-${data.id}-title`}
      className={cn(
        "rounded-2xl border border-border/60 bg-card p-3 shadow-sm sm:p-4",
        className,
      )}
    >
      <header className="flex items-start justify-between gap-2">
        <h3
          id={`action-card-${data.id}-title`}
          className="font-display text-base font-semibold leading-tight text-foreground"
        >
          {data.title}
        </h3>
        {data.priority ? (
          <PriorityBadge value={data.priority} />
        ) : null}
      </header>
      <dl className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Row icon={HelpCircle} label="Why" value={data.why} />
        {data.effort ? (
          <Row icon={Activity} label="Effort" value={data.effort} />
        ) : null}
        {data.expectedPurpose ? (
          <Row icon={Target} label="Expected purpose" value={data.expectedPurpose} />
        ) : null}
        {data.risk ? (
          <Row icon={AlertTriangle} label="Risk" value={data.risk} tone="danger" />
        ) : null}
        {data.nextStep ? (
          <Row icon={ArrowRight} label="Next step" value={data.nextStep} />
        ) : null}
      </dl>
    </article>
  );
}

function Row({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "default" | "danger";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-background/40 p-2",
        tone === "danger"
          ? "border-rose-200/60 dark:border-rose-500/20"
          : "border-border/40",
      )}
    >
      <dt className="mb-0.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3" aria-hidden />
        {label}
      </dt>
      <dd
        className={cn(
          "text-xs leading-relaxed",
          tone === "danger" ? "text-rose-700 dark:text-rose-300" : "text-foreground/90",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function PriorityBadge({ value }: { value: string }) {
  const tone = priorityTone(value);
  return (
    <span
      aria-label={`Priority ${value}`}
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        tone,
      )}
    >
      {value}
    </span>
  );
}

function priorityTone(value: string): string {
  const v = value.toLowerCase();
  if (v.includes("critical")) {
    return "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  }
  if (v.includes("high")) {
    return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  if (v.includes("medium") || v.includes("med")) {
    return "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300";
  }
  if (v.includes("low")) {
    return "border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-300";
  }
  return "border-border bg-secondary text-foreground/80";
}

export default ActionCard;

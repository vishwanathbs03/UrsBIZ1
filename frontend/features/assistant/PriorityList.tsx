"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The PriorityList —
 * a numbered priority list with impact badges. Used when the
 * brief calls for surfacing 3+ recommendations in a single
 * visual surface.
 *
 * The brief example:
 *
 *   1. Vendor diversification     HIGH   +12
 *   2. Improve invoice cycles      MED    +7
 *   3. Apply TReDS onboarding      LOW    +4
 *
 * Each row pairs a numeric badge (1, 2, 3 ...) with the
 * recommendation title, a priority chip (HIGH / MED / LOW),
 * and an optional impact delta ("+12"). The priority chip
 * carries the textual label by design — the brief mandates
 * that color is never the only signal.
 *
 * The list is rendered as a `<ol>` so assistive tech reads the
 * number automatically. The numeric badges are decorative
 * (`aria-hidden`) — the semantic order is the order of the
 * `<ol>`.
 */

import { cn } from "@/lib/utils";

export interface PriorityListItem {
  /** Stable id used as React key + ARIA label. */
  id: string;
  /** WHAT — the recommendation title. */
  title: string;
  /** Priority label (e.g. "High", "Medium", "Low"). */
  priority?: string | null;
  /** Optional impact score (e.g. "+12", "+8%"). */
  score?: string | null;
  /** Optional supporting evidence ids — surfaced as tone dots. */
  evidenceRefs?: readonly string[];
}

export interface PriorityListProps {
  items: readonly PriorityListItem[];
  /** Optional title shown above the list. */
  title?: string;
  /** Optional className passthrough. */
  className?: string;
}

export function PriorityList({ items, title, className }: PriorityListProps) {
  const safe = items.length > 0 ? items : [];
  if (safe.length === 0) {
    return null;
  }
  return (
    <div
      data-testid="priority-list"
      aria-label={
        title ?? `Priority list with ${safe.length} ${safe.length === 1 ? "item" : "items"}`
      }
      className={cn("space-y-2", className)}
    >
      {title ? (
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h4>
      ) : null}
      <ol className="space-y-1.5">
        {safe.map((item, i) => (
          <li
            key={item.id}
            className="flex items-start gap-2 rounded-md border border-border/40 bg-background/40 px-2 py-1.5"
          >
            <span
              aria-hidden="true"
              className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-[10px] font-semibold text-primary"
            >
              {i + 1}
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-xs font-medium text-foreground/90">
                {item.title}
              </span>
              {item.evidenceRefs && item.evidenceRefs.length > 0 ? (
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  {item.evidenceRefs.length} evidence point
                  {item.evidenceRefs.length === 1 ? "" : "s"}
                </span>
              ) : null}
            </span>
            {item.priority ? (
              <PriorityChip value={item.priority} />
            ) : null}
            {item.score ? (
              <span className="shrink-0 rounded-full border border-border/60 bg-secondary/60 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-foreground/80">
                {item.score}
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

function PriorityChip({ value }: { value: string }) {
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

export default PriorityList;

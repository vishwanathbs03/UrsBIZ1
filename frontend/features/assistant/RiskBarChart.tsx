"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The RiskBarChart —
 * the brief's "Supplier A 75% / Other 25%" horizontal stacked
 * bar. Each segment is labelled inline with the value so the
 * brief's accessibility requirement ("All visual indicators
 * must have textual equivalents") is satisfied.
 *
 * The component supports 1..N segments. Each segment gets a
 * fill color from the deterministic palette below so the chart
 * is consistent across sessions. The chart is rendered with
 * `role="img"` + `aria-label` carrying the full text
 * equivalent ("Supplier A 75%, Other suppliers 25%") so screen
 * readers don't miss the data.
 */

import { cn } from "@/lib/utils";

export interface RiskBarSegment {
  /** Label shown beside the bar. */
  label: string;
  /** 0-100 percentage. Must sum to 100 across segments. */
  value: number;
  /** Optional tone ("danger" / "warn" / "info" / "default"). */
  tone?: "danger" | "warn" | "info" | "default";
}

export interface RiskBarChartProps {
  segments: readonly RiskBarSegment[];
  /** Optional title shown above the bar. */
  title?: string;
  /** Optional className passthrough. */
  className?: string;
}

export function RiskBarChart({
  segments,
  title,
  className,
}: RiskBarChartProps) {
  const safe = segments.length > 0 ? segments : [];
  const total = safe.reduce((sum, s) => sum + Math.max(0, s.value), 0);
  const ariaLabel = safe
    .map((s) => `${s.label} ${Math.round(s.value)}%`)
    .join(", ");
  return (
    <div
      data-testid="risk-bar-chart"
      aria-label={ariaLabel}
      className={cn("space-y-2", className)}
    >
      {title ? (
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h4>
      ) : null}
      <div
        role="img"
        aria-label={ariaLabel}
        className="flex h-3 w-full overflow-hidden rounded-full border border-border/60 bg-muted"
      >
        {safe.map((seg, i) => {
          const pct = total > 0 ? (Math.max(0, seg.value) / total) * 100 : 0;
          if (pct <= 0) {
            return null;
          }
          return (
            <div
              key={`${seg.label}-${i}`}
              style={{ width: `${pct}%` }}
              className={cn("h-full", toneClass(seg.tone))}
            />
          );
        })}
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {safe.map((seg, i) => (
          <li
            key={`${seg.label}-legend-${i}`}
            className="flex items-center gap-1.5"
          >
            <span
              aria-hidden="true"
              className={cn(
                "inline-block size-2.5 shrink-0 rounded-sm",
                toneClass(seg.tone),
              )}
            />
            <span className="font-medium text-foreground/90">{seg.label}</span>
            <span className="text-muted-foreground tabular-nums">
              {Math.round(seg.value)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function toneClass(tone: RiskBarSegment["tone"]): string {
  switch (tone) {
    case "danger":
      return "bg-rose-500 dark:bg-rose-400";
    case "warn":
      return "bg-amber-500 dark:bg-amber-400";
    case "info":
      return "bg-sky-500 dark:bg-sky-400";
    default:
      return "bg-emerald-500 dark:bg-emerald-400";
  }
}

export default RiskBarChart;

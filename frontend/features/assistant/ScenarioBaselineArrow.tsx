"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The
 * ScenarioBaselineArrow — the brief's "Baseline → Target →
 * Difference" horizontal arrow used for scenario matrices.
 *
 * The brief example:
 *
 *   Revenue target: ₹1.80 Cr ───────────────► ₹3.00 Cr
 *
 * The component renders the baseline value on the left, a
 * gradient arrow in the middle, the target value on the right,
 * and the delta underneath as a tonal chip. The chip is
 * colored by sign (positive = emerald, negative = rose) and
 * carries a textual prefix so the color is never the only
 * signal — the brief mandates text equivalents for color.
 *
 * The arrow is a single SVG with a coloured gradient stroke
 * so the visual is crisp at any size. Below 640px the layout
 * stacks vertically (baseline above, arrow, target, delta)
 * because the brief mandates no horizontal scrolling.
 */

import { TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ScenarioBaselineArrowProps {
  /** Baseline label and value. */
  baseline: { label: string; value: string };
  /** Target label and value. */
  target: { label: string; value: string };
  /** Optional delta label (e.g. "+₹1.20 Cr (+66%)"). */
  delta?: string | null;
  /** Optional aria-label override. */
  ariaLabel?: string;
  /** Optional className passthrough. */
  className?: string;
}

export function ScenarioBaselineArrow({
  baseline,
  target,
  delta,
  ariaLabel,
  className,
}: ScenarioBaselineArrowProps) {
  const tone = deltaTone(delta);
  return (
    <div
      data-testid="scenario-baseline-arrow"
      aria-label={ariaLabel ?? `${baseline.value} to ${target.value}`}
      className={cn(
        "flex flex-col items-stretch gap-2 rounded-xl border border-border/60 bg-card p-3 sm:flex-row sm:items-center sm:gap-3",
        className,
      )}
    >
      <div className="flex flex-1 flex-col">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {baseline.label}
        </span>
        <span className="font-display text-base font-semibold tabular-nums text-foreground">
          {baseline.value}
        </span>
      </div>
      <Arrow
        className="hidden shrink-0 text-primary sm:block"
        aria-hidden="true"
      />
      <Arrow
        className="block shrink-0 -rotate-90 self-center text-primary sm:hidden"
        aria-hidden="true"
      />
      <div className="flex flex-1 flex-col sm:items-end">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {target.label}
        </span>
        <span className="font-display text-base font-semibold tabular-nums text-foreground">
          {target.value}
        </span>
      </div>
      {delta ? (
        <span
          className={cn(
            "inline-flex items-center gap-1 self-start rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums sm:self-auto",
            tone,
          )}
        >
          {tone.startsWith("border-emerald") ? (
            <TrendingUp className="size-3" aria-hidden="true" />
          ) : (
            <TrendingDown className="size-3" aria-hidden="true" />
          )}
          <span>{delta}</span>
        </span>
      ) : null}
    </div>
  );
}

function Arrow({ className, ...rest }: React.SVGAttributes<SVGElement>) {
  return (
    <svg
      width="60"
      height="14"
      viewBox="0 0 60 14"
      fill="none"
      className={className}
      {...rest}
    >
      <defs>
        <linearGradient id="scenario-arrow-gradient" x1="0" x2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.2" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="1" />
        </linearGradient>
      </defs>
      <line
        x1="0"
        y1="7"
        x2="56"
        y2="7"
        stroke="url(#scenario-arrow-gradient)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <polyline
        points="50,2 56,7 50,12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function deltaTone(delta: string | null | undefined): string {
  if (!delta) {
    return "border-border bg-secondary text-foreground/80";
  }
  if (delta.trim().startsWith("+")) {
    return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  }
  if (delta.trim().startsWith("-")) {
    return "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  }
  return "border-border bg-secondary text-foreground/80";
}

export default ScenarioBaselineArrow;

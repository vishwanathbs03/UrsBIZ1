"use client";

import React from "react";
import { ArrowDownRight, ArrowUpRight, Minus, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";

export interface MetricCardProps {
  /** Metric category or eyebrow. */
  badge?: string;
  /** Primary label of the metric. */
  title: string;
  /** Primary numeric or string value. */
  value: number | string;
  /** Optional prefix (e.g. "₹", "$"). */
  prefix?: string;
  /** Optional suffix (e.g. "%", " Cr", " employees"). */
  suffix?: string;
  /** Subtitle or explanatory context. */
  caption?: string;
  /** Trend delta percentage or difference (e.g. +12.5 or -4.2). */
  trendDelta?: number;
  /** Explicit trend direction if not inferred from trendDelta. */
  trendDirection?: "up" | "down" | "neutral";
  /** Trend label (e.g. "vs previous quarter"). */
  trendLabel?: string;
  /** Icon displayed in the top-right corner. */
  icon?: React.ReactNode;
  /** Deterministic lineage badge tag. */
  provenance?: "rule-engine" | "retrieved" | "scenario" | "calculated";
  /** Accent glow color on hover (defaults to blue). */
  accentColor?: "blue" | "cyan" | "emerald" | "amber" | "violet";
  className?: string;
  onClick?: () => void;
}

export function MetricCard({
  badge,
  title,
  value,
  prefix = "",
  suffix = "",
  caption,
  trendDelta,
  trendDirection,
  trendLabel = "vs last period",
  icon,
  provenance = "rule-engine",
  accentColor = "blue",
  className,
  onClick,
}: MetricCardProps) {
  // Infer trend direction if not explicitly supplied
  const direction =
    trendDirection ??
    (trendDelta != null ? (trendDelta > 0 ? "up" : trendDelta < 0 ? "down" : "neutral") : null);

  const accentStyles = {
    blue: "hover:border-blue-500/50 hover:shadow-[0_0_20px_-3px_rgba(59,130,246,0.35)]",
    cyan: "hover:border-cyan-500/50 hover:shadow-[0_0_20px_-3px_rgba(6,182,212,0.35)]",
    emerald: "hover:border-emerald-500/50 hover:shadow-[0_0_20px_-3px_rgba(16,185,129,0.35)]",
    amber: "hover:border-amber-500/50 hover:shadow-[0_0_20px_-3px_rgba(245,158,11,0.35)]",
    violet: "hover:border-violet-500/50 hover:shadow-[0_0_20px_-3px_rgba(139,92,246,0.35)]",
  }[accentColor];

  const isNumeric = typeof value === "number";

  return (
    <div
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      className={cn(
        "shadow-soft group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border/80 bg-card/90 p-5 backdrop-blur-md transition-all duration-300",
        "hover:-translate-y-1",
        accentStyles,
        onClick &&
          "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
        className,
      )}
    >
      {/* Top ambient glow bar */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-transparent opacity-70 transition-opacity group-hover:opacity-100"
      />

      {/* Header row: Badge, Title & Icon */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          {badge && (
            <span className="inline-flex w-fit items-center rounded-full border border-border/80 bg-secondary/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {badge}
            </span>
          )}
          <h3 className="truncate text-xs font-semibold uppercase tracking-wider text-muted-foreground transition-colors group-hover:text-foreground">
            {title}
          </h3>
        </div>
        {icon && (
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-secondary/60 text-muted-foreground transition-all group-hover:border-accent/40 group-hover:bg-primary/10 group-hover:text-accent">
            {icon}
          </div>
        )}
      </div>

      {/* Big Value Row */}
      <div className="my-3 flex items-baseline gap-1">
        {prefix && <span className="text-xl font-bold text-muted-foreground">{prefix}</span>}
        <div className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
          {isNumeric ? <AnimatedCounter value={value as number} /> : <span>{value}</span>}
        </div>
        {suffix && <span className="text-sm font-semibold text-muted-foreground">{suffix}</span>}
      </div>

      {/* Footer row: Trend & Lineage tag */}
      <div className="flex items-center justify-between gap-2 border-t border-border/60 pt-3 text-xs">
        {direction ? (
          <div className="flex items-center gap-1.5 truncate font-medium">
            {direction === "up" && (
              <span className="inline-flex items-center gap-0.5 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-400">
                <ArrowUpRight className="size-3.5" aria-hidden="true" />
                {trendDelta != null ? `${Math.abs(trendDelta)}%` : ""}
              </span>
            )}
            {direction === "down" && (
              <span className="inline-flex items-center gap-0.5 rounded-md border border-rose-500/20 bg-rose-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-rose-400">
                <ArrowDownRight className="size-3.5" aria-hidden="true" />
                {trendDelta != null ? `${Math.abs(trendDelta)}%` : ""}
              </span>
            )}
            {direction === "neutral" && (
              <span className="inline-flex items-center gap-0.5 rounded-md border border-border bg-secondary px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
                <Minus className="size-3.5" aria-hidden="true" />
              </span>
            )}
            {trendLabel && (
              <span className="truncate text-[11px] text-muted-foreground">{trendLabel}</span>
            )}
          </div>
        ) : caption ? (
          <p className="truncate text-[11px] text-muted-foreground">{caption}</p>
        ) : (
          <div />
        )}

        {provenance && (
          <span
            title="Calculated deterministically by the UrsBiz core engine"
            className="inline-flex shrink-0 items-center gap-1 text-[10px] font-medium text-muted-foreground/80"
          >
            <ShieldCheck className="size-3 text-emerald-400" aria-hidden="true" />
            <span className="hidden sm:inline">Engine Verified</span>
          </span>
        )}
      </div>
    </div>
  );
}

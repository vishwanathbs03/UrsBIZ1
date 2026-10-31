"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface ChartCardProps {
  /** Title of the chart card. */
  title: string;
  /** Eyebrow or badge label. */
  badge?: string;
  /** Subtitle or explanatory note. */
  description?: string;
  /** Right-aligned action controls (e.g., time range buttons or legend). */
  action?: React.ReactNode;
  /** Bottom legend or metadata footer. */
  footer?: React.ReactNode;
  /** Main chart body. */
  children: React.ReactNode;
  className?: string;
}

/**
 * Standard Dark Neon ChartCard container for analytics, trends, and radar distributions.
 */
export function ChartCard({
  title,
  badge,
  description,
  action,
  footer,
  children,
  className,
}: ChartCardProps) {
  return (
    <div
      className={cn(
        "shadow-soft group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border/80 bg-card/90 p-5 backdrop-blur-md transition-all duration-300",
        "hover:border-primary/40 hover:shadow-[0_4px_24px_-4px_rgba(37,99,235,0.15)]",
        className,
      )}
    >
      {/* Top Header */}
      <div className="flex flex-col gap-3 border-b border-border/60 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          {badge && (
            <span className="inline-flex w-fit items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">
              {badge}
            </span>
          )}
          <h3 className="text-base font-bold tracking-tight text-foreground sm:text-lg">{title}</h3>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
      </div>

      {/* Chart Canvas Slot */}
      <div className="my-4 flex min-h-[220px] flex-1 items-center justify-center">{children}</div>

      {/* Bottom Footer / Legend */}
      {footer && (
        <div className="border-t border-border/60 pt-3 text-xs text-muted-foreground">{footer}</div>
      )}
    </div>
  );
}

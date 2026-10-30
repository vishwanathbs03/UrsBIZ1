import React from "react";
import { cn } from "@/lib/utils";

export interface LoadingSkeletonProps {
  className?: string;
  rows?: number;
  variant?: "card" | "text" | "metric" | "chart";
}

/**
 * Reusable Dark Neon LoadingSkeleton component.
 * Employs slate-based surface and smooth shimmer wave.
 */
export function LoadingSkeleton({ className, rows = 3, variant = "text" }: LoadingSkeletonProps) {
  if (variant === "metric") {
    return (
      <div
        role="status"
        aria-label="Loading metric..."
        className={cn(
          "animate-pulse space-y-4 rounded-xl border border-border/70 bg-card/70 p-5 backdrop-blur-md",
          className,
        )}
      >
        <div className="flex items-center justify-between">
          <div className="shimmer h-3 w-20 rounded-md bg-secondary/80" />
          <div className="shimmer size-8 rounded-lg bg-secondary/80" />
        </div>
        <div className="shimmer h-8 w-32 rounded-lg bg-secondary/90" />
        <div className="shimmer h-3 w-40 rounded-md bg-secondary/60" />
      </div>
    );
  }

  if (variant === "chart") {
    return (
      <div
        role="status"
        aria-label="Loading chart data..."
        className={cn(
          "animate-pulse space-y-6 rounded-xl border border-border/70 bg-card/70 p-5 backdrop-blur-md",
          className,
        )}
      >
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="shimmer h-4 w-36 rounded-md bg-secondary/90" />
            <div className="shimmer h-3 w-48 rounded-md bg-secondary/60" />
          </div>
          <div className="shimmer h-6 w-24 rounded-full bg-secondary/70" />
        </div>
        <div className="flex h-48 w-full items-end gap-3 rounded-lg bg-secondary/40 p-4">
          <div className="shimmer h-1/3 flex-1 rounded bg-secondary/80" />
          <div className="shimmer h-2/3 flex-1 rounded bg-secondary/80" />
          <div className="shimmer h-1/2 flex-1 rounded bg-secondary/80" />
          <div className="shimmer h-3/4 flex-1 rounded bg-secondary/80" />
          <div className="shimmer h-full flex-1 rounded bg-primary/30" />
        </div>
      </div>
    );
  }

  if (variant === "card") {
    return (
      <div
        role="status"
        aria-label="Loading content..."
        className={cn(
          "animate-pulse space-y-4 rounded-xl border border-border/70 bg-card/70 p-5 backdrop-blur-md",
          className,
        )}
      >
        <div className="shimmer h-4 w-1/3 rounded-md bg-secondary/90" />
        <div className="space-y-2.5">
          <div className="shimmer h-3 w-full rounded-md bg-secondary/70" />
          <div className="shimmer h-3 w-5/6 rounded-md bg-secondary/70" />
          <div className="shimmer h-3 w-2/3 rounded-md bg-secondary/60" />
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-label="Loading..."
      className={cn("animate-pulse space-y-2.5", className)}
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          style={{ width: `${Math.max(45, 100 - i * 15)}%` }}
          className="shimmer h-3.5 rounded-md bg-secondary/80"
        />
      ))}
    </div>
  );
}

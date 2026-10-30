"use client";

import React from "react";
import { Award, ChevronRight, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { Button } from "@/components/ui/button";

export interface RecommendationCardProps {
  id?: string;
  title: string;
  description: string;
  priority?: "critical" | "high" | "medium" | "low" | string;
  priorityScore?: number;
  category?: string;
  impact?: string;
  effort?: string;
  scoreGain?: number;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * Reusable Dark Neon RecommendationCard component for strategic recommendations.
 */
export function RecommendationCard({
  title,
  description,
  priority = "medium",
  priorityScore,
  category,
  impact,
  effort,
  scoreGain,
  actionLabel,
  onAction,
  className,
}: RecommendationCardProps) {
  const tone = levelToTone(priority);

  return (
    <div
      className={cn(
        "group relative flex flex-col justify-between rounded-xl border border-border/80 bg-card/80 p-4 backdrop-blur-md transition-all duration-300",
        "hover:border-primary/50 hover:bg-card hover:shadow-[0_4px_20px_-4px_rgba(37,99,235,0.2)]",
        className,
      )}
    >
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-semibold leading-snug text-foreground transition-colors group-hover:text-accent">
            {title}
          </h4>
          <LevelBadge level={priority} tone={tone} />
        </div>

        <p className="text-xs leading-relaxed text-muted-foreground">{description}</p>
      </div>

      <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3 text-[11px]">
        <div className="flex flex-wrap items-center gap-2.5 text-muted-foreground">
          {priorityScore != null && (
            <span className="inline-flex items-center gap-1 font-medium">
              <Zap className="size-3 text-amber-400" aria-hidden="true" />
              Score: <strong className="text-foreground">{priorityScore}/100</strong>
            </span>
          )}
          {category && (
            <span className="inline-flex items-center gap-1 font-medium">
              <Award className="size-3 text-accent" aria-hidden="true" />
              <strong className="text-foreground">{category}</strong>
            </span>
          )}
          {impact && <span>Impact: {impact}</span>}
          {effort && <span>Effort: {effort}</span>}
          {scoreGain != null && scoreGain > 0 && (
            <span className="font-semibold text-emerald-400">+{scoreGain} pts</span>
          )}
        </div>

        {actionLabel && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onAction}
            className="h-7 gap-1 px-2 text-xs text-accent hover:bg-primary/20 hover:text-white"
          >
            <span>{actionLabel}</span>
            <ChevronRight className="size-3" aria-hidden="true" />
          </Button>
        )}
      </div>
    </div>
  );
}

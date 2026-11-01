"use client";

import { useState } from "react";
import {
  Calendar,
  CheckCircle2,
  Compass,
  Milestone,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonalizedGrowthStrategy } from "@/types/smart-recommendations";

interface GrowthStrategyRoadmapProps {
  strategy?: PersonalizedGrowthStrategy | null;
}

export function GrowthStrategyRoadmap({ strategy }: GrowthStrategyRoadmapProps) {
  const [selectedHorizon, setSelectedHorizon] = useState<number>(0);

  if (!strategy || !strategy.horizons || strategy.horizons.length === 0) {
    return null;
  }

  const current = strategy.horizons[selectedHorizon] || strategy.horizons[0];

  return (
    <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <Compass className="size-4 text-primary" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">
              Architecture Layer 3: Personalized 3-Horizon Growth Strategy
            </h3>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Sequential growth execution plan aligned with verified MSME business stage and operational readiness.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {strategy.is_ai_generated ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-xs font-semibold text-violet-300">
              <Sparkles className="size-3" /> Gemini Reasoning Layer
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
              Deterministic Strategic Synthesis
            </span>
          )}
        </div>
      </div>

      {/* Strategic Executive Summary */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3.5 text-xs leading-relaxed text-foreground/90">
        <span className="font-semibold text-primary">Executive Strategic Brief: </span>
        {strategy.strategy_summary}
      </div>

      {/* Horizon Selector Tabs */}
      <div className="grid grid-cols-3 gap-2">
        {strategy.horizons.map((h, idx) => (
          <button
            key={h.horizon}
            onClick={() => setSelectedHorizon(idx)}
            className={cn(
              "flex flex-col items-start p-3 rounded-lg border text-left transition-all",
              selectedHorizon === idx
                ? "border-primary bg-primary/10 shadow-sm"
                : "border-border/60 bg-secondary/20 hover:bg-secondary/40 text-muted-foreground"
            )}
          >
            <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
              Horizon {idx + 1}
            </span>
            <span className="text-sm font-bold text-foreground mt-0.5">
              {h.horizon}
            </span>
            <span className="text-[11px] text-muted-foreground mt-1 line-clamp-1">
              {h.title}
            </span>
          </button>
        ))}
      </div>

      {/* Current Horizon Detail Card */}
      <div className="rounded-lg border border-border/80 bg-secondary/15 p-4 space-y-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded bg-primary/15 border border-primary/30 px-2 py-0.5 text-xs font-bold text-primary">
              {current.horizon} Focus
            </span>
            <h4 className="text-base font-bold text-foreground">{current.title}</h4>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
            {current.focus}
          </p>
        </div>

        {/* Strategic Actions */}
        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-foreground">
            Target Execution Actions
          </span>
          <div className="grid gap-2 sm:grid-cols-2">
            {current.actions.map((act, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded bg-background/70 border border-border/60 p-2.5 text-xs text-foreground/90"
              >
                <CheckCircle2 className="size-3.5 text-primary shrink-0 mt-0.5" />
                <span>{act}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Milestones & KPIs */}
        <div className="grid gap-4 sm:grid-cols-2 border-t border-border/50 pt-3">
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-foreground">
              <Milestone className="size-3.5 text-amber-400" />
              <span>Target Milestones</span>
            </div>
            <div className="space-y-1.5">
              {current.milestones.map((m, idx) => (
                <div
                  key={idx}
                  className="rounded border border-border/60 bg-background/60 p-2 text-xs flex items-center justify-between"
                >
                  <div>
                    <div className="font-semibold text-foreground">{m.milestone}</div>
                    <div className="text-[11px] text-muted-foreground">{m.metric_to_track}</div>
                  </div>
                  <span className="rounded bg-secondary px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                    {m.target_date_window}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-foreground">
              <Target className="size-3.5 text-emerald-400" />
              <span>Measurement KPIs</span>
            </div>
            <ul className="space-y-1 text-xs text-muted-foreground pl-3 border-l-2 border-emerald-500/40">
              {current.kpis.map((kpi, idx) => (
                <li key={idx} className="text-foreground/90">
                  {kpi}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Critical Success Factors */}
      <div className="rounded-lg border border-border/60 bg-background/60 p-3.5 space-y-1.5">
        <span className="text-xs font-bold uppercase tracking-wider text-foreground">
          Critical Success Factors (Execution Disciplines)
        </span>
        <div className="grid gap-1.5 sm:grid-cols-2 text-xs text-muted-foreground">
          {strategy.critical_success_factors.map((factor, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-primary" />
              <span>{factor}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

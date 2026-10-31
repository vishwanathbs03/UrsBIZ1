"use client";

import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Database,
  Flame,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { NextBestAction } from "@/types/smart-recommendations";

interface NextBestActionHeroProps {
  action?: NextBestAction | null;
  evidenceSummary?: Record<string, any>;
  onOpenScenarios?: () => void;
}

export function NextBestActionHero({
  action,
  evidenceSummary,
  onOpenScenarios,
}: NextBestActionHeroProps) {
  if (!action) return null;

  const verifiedSources = evidenceSummary?.sources_verified || [];

  return (
    <div className="relative overflow-hidden rounded-xl border border-primary/30 bg-gradient-to-br from-card via-card/95 to-primary/5 p-6 shadow-xl">
      {/* Background glow accent */}
      <div className="pointer-events-none absolute -right-20 -top-20 size-64 rounded-full bg-primary/10 blur-3xl" />

      {/* Verified Business Data Tier Pills */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3">
        <div className="flex items-center gap-2">
          <Database className="size-4 text-primary" />
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Architecture Layer 1: Verified Business Ground Truth
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
            <CheckCircle2 className="size-3" /> Profile
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
            <CheckCircle2 className="size-3" /> Health Score ({evidenceSummary?.business_health_score ?? "58"}/100)
          </span>
          {evidenceSummary?.has_sales_ledger && (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
              <CheckCircle2 className="size-3" /> Sales Ledger (Verified)
            </span>
          )}
          {evidenceSummary?.has_forecast_intelligence && (
            <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-0.5 text-[11px] font-medium text-cyan-400">
              <CheckCircle2 className="size-3" /> Phase 4 Forecasts
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-[11px] font-medium text-violet-400">
            <CheckCircle2 className="size-3" /> Statutory Schemes ({evidenceSummary?.schemes_matched ?? "0"})
          </span>
        </div>
      </div>

      {/* Main Hero Card Body */}
      <div className="grid gap-6 md:grid-cols-12 items-start">
        <div className="space-y-4 md:col-span-8">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-rose-500/15 border border-rose-500/30 px-2.5 py-1 text-xs font-bold text-rose-400 tracking-wide uppercase">
              <Flame className="size-3.5 fill-rose-500" />
              Next Best Business Action
            </span>
            <span className="rounded bg-secondary/80 px-2 py-0.5 text-xs font-semibold text-foreground">
              Priority Score: {action.priority_score}/100
            </span>
            <span className="rounded bg-primary/10 border border-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
              {action.category}
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="size-3" /> Time to value: {action.time_to_value}
            </span>
            <span className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
              Effort: {action.effort_level}
            </span>
          </div>

          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
              {action.title}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
              {action.why_now}
            </p>
          </div>

          {/* Cost of Delay Warning */}
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-300">
            <div className="flex items-center gap-1.5 font-semibold text-amber-200 mb-1">
              <ShieldAlert className="size-4 text-amber-400 shrink-0" />
              <span>Cost of Delay (What happens if postponed)</span>
            </div>
            <p className="text-amber-200/90 leading-relaxed pl-5">
              {action.cost_of_delay}
            </p>
          </div>

          {/* Immediate First Step */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 text-xs">
            <span className="font-semibold text-foreground">Immediate First Step: </span>
            <span className="text-muted-foreground">{action.first_immediate_step}</span>
          </div>
        </div>

        {/* Action Button & Scenario Launcher */}
        <div className="flex flex-col gap-3 rounded-lg border border-border/60 bg-background/50 p-4 md:col-span-4">
          <div className="space-y-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Recommendation Engine
            </span>
            <p className="text-xs text-muted-foreground">
              Multi-factor ranking: 0.25 R + 0.25 I + 0.20 E + 0.15 C + 0.15 F
            </p>
          </div>

          <div className="pt-2 flex flex-col gap-2">
            <Button
              className="w-full gap-2 font-semibold shadow-md"
              size="sm"
              onClick={() => {
                const el = document.getElementById(action.recommendation_id);
                if (el) el.scrollIntoView({ behavior: "smooth" });
              }}
            >
              <Zap className="size-4" />
              <span>Execute This Action</span>
            </Button>

            {onOpenScenarios && (
              <Button
                variant="outline"
                className="w-full gap-2 border-primary/30 text-xs hover:bg-primary/10"
                size="sm"
                onClick={onOpenScenarios}
              >
                <TrendingUp className="size-3.5 text-primary" />
                <span>Simulate Business Impact (What-If)</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

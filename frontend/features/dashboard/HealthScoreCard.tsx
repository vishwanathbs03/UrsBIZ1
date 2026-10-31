"use client";

import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { ShieldCheck, Sparkles, TrendingUp, AlertTriangle, CheckCircle2 } from "lucide-react";

export interface HealthScoreCardProps {
  score?: number;
}

export function HealthScoreCard({ score = 85 }: HealthScoreCardProps) {
  const getGrade = (s: number) => {
    if (s >= 90) return { grade: "A+", status: "Excellent", tip: "Optimal stability & growth trajectory." };
    if (s >= 80) return { grade: "A", status: "Good", tip: "Strong baseline; ready for capital expansion." };
    if (s >= 70) return { grade: "B", status: "Fair", tip: "Update digital presence to boost score." };
    if (s >= 60) return { grade: "C", status: "Needs Improvement", tip: "Address working capital bottlenecks." };
    return { grade: "D", status: "Critical", tip: "Urgent operational & cash flow review required." };
  };

  const { grade, status, tip } = getGrade(score);

  return (
    <DashboardCard
      badge="Hero Health Metric"
      title="Business Health Score Index"
      caption="Composite digital twin health index across profile completeness, team, financial stability, and digital presence."
      className="relative overflow-hidden border-primary/30 bg-gradient-to-br from-card via-card to-primary/5 shadow-soft hover-lift"
    >
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        {/* Score & Counter */}
        <div className="flex items-center gap-4">
          <div className="relative flex size-20 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 shadow-inner">
            <ShieldCheck className="absolute size-16 text-primary/10" />
            <div className="flex flex-col items-center">
              <AnimatedCounter
                value={score}
                className="text-3xl font-black text-foreground"
                durationMs={600}
              />
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">/ 100</span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Health Grade</span>
              <LevelBadge level={status} tone={levelToTone(status)} />
            </div>
            <h3 className="text-2xl font-black text-foreground mt-0.5">{grade} <span className="text-sm font-normal text-muted-foreground">({status})</span></h3>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <TrendingUp className="size-3 text-emerald-500" />
              <span>Evaluated live via deterministic rule engine</span>
            </p>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-4 space-y-1.5">
        <div className="flex justify-between text-xs font-semibold text-muted-foreground">
          <span>Overall Health Progress</span>
          <span className="text-foreground">{score}%</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className="h-full bg-gradient-to-r from-primary via-blue-500 to-teal-400 transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </div>

      {/* Tip Banner */}
      <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-muted/30 p-2.5 text-xs text-muted-foreground">
        <Sparkles className="size-4 shrink-0 text-primary" />
        <span><strong className="text-foreground">Insight:</strong> {tip}</span>
      </div>
    </DashboardCard>
  );
}

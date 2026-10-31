import React from "react";
import type { BenchmarkReport } from "@/types/intelligence";
import { ScoreBadge } from "./ScoreBadge";
import { TermTooltip } from "@/components/common/TermTooltip";

interface BenchmarkCardProps {
  benchmark?: BenchmarkReport;
}

export const BenchmarkCard: React.FC<BenchmarkCardProps> = ({ benchmark }) => {
  if (!benchmark) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-border/50 pb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Industry Classification: {benchmark.industry}
          </span>
          <h3 className="text-xl font-bold text-card-foreground">
            <TermTooltip
              text="Industry Baseline Benchmark"
              definition="An industry baseline number used for comparison. UrsBiz uses deterministic internal baselines only when official public data is unavailable."
            />
          </h3>
        </div>
        <ScoreBadge score={benchmark.overall_benchmark_score} grade={benchmark.benchmark_grade} size="lg" />
      </div>

      <div className="mt-6 space-y-4">
        {benchmark.metrics.map((m) => {
          const isAbove = m.status === "above_average";
          const isBelow = m.status === "below_average";
          const statusText = isAbove ? "Above Average" : isBelow ? "Below Average" : "On Par";
          const statusBg = isAbove
            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
            : isBelow
            ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
            : "bg-amber-500/10 text-amber-600 dark:text-amber-400";

          return (
            <div key={m.metric_name} className="rounded-lg border border-border/40 bg-muted/20 p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-card-foreground text-sm">{m.metric_name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${statusBg}`}>
                  {statusText} ({m.percentile}th Percentile)
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded bg-card p-2 border border-border/30">
                  <span className="text-muted-foreground block">Your Value</span>
                  <span className="font-bold text-card-foreground text-sm">{m.user_score}</span>
                </div>
                <div className="rounded bg-card p-2 border border-border/30">
                  <span className="text-muted-foreground block">Industry Avg</span>
                  <span className="font-bold text-card-foreground text-sm">{m.industry_average}</span>
                </div>
                <div className="rounded bg-card p-2 border border-border/30">
                  <span className="text-muted-foreground block">Difference</span>
                  <span className={`font-bold text-sm ${m.difference >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                    {m.difference >= 0 ? `+${m.difference}` : m.difference}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

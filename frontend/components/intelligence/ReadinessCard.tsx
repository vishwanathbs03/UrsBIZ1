import React from "react";
import type { ReadinessReport } from "@/types/intelligence";
import { ScoreBadge } from "./ScoreBadge";
import { TermTooltip } from "@/components/common/TermTooltip";

interface ReadinessCardProps {
  readiness?: ReadinessReport;
}

export const ReadinessCard: React.FC<ReadinessCardProps> = ({ readiness }) => {
  if (!readiness) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-border/50 pb-4">
        <div>
          <h3 className="text-xl font-bold text-card-foreground">
            <TermTooltip
              text="Business Readiness Index"
              definition="How prepared the business is across six dimensions (digital, operational, market, export, compliance, investment). Scored 0-100 from the same fields that feed the Business Health Score."
            />
          </h3>
          <p className="text-sm text-muted-foreground">Evaluated operational readiness across 6 dimensions.</p>
        </div>
        <ScoreBadge score={readiness.overall_score} grade={readiness.grade} size="lg" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {readiness.breakdown.map((item) => {
          let barColor = "bg-rose-500";
          if (item.score >= 80) barColor = "bg-emerald-500";
          else if (item.score >= 60) barColor = "bg-cyan-500";
          else if (item.score >= 40) barColor = "bg-amber-500";

          return (
            <div key={item.dimension} className="rounded-lg border border-border/50 bg-muted/20 p-4">
              <div className="flex items-center justify-between text-sm font-semibold">
                <span className="text-card-foreground">{item.dimension}</span>
                <span className="text-muted-foreground">{item.score}/100</span>
              </div>
              <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full ${barColor} transition-all duration-500 ease-out`}
                  style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{item.details}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

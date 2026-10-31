"use client";

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Cpu,
  FileQuestion,
  HelpCircle,
  Lightbulb,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  CrossSignalInsight,
  OpportunityItem,
  RootCauseAnalysisItem,
} from "@/types/smart-recommendations";

interface MultiSignalInsightsPanelProps {
  insights: CrossSignalInsight[];
  rootCauses: RootCauseAnalysisItem[];
  opportunities: OpportunityItem[];
}

export function MultiSignalInsightsPanel({
  insights,
  rootCauses,
  opportunities,
}: MultiSignalInsightsPanelProps) {
  const [activeTab, setActiveTab] = useState<"signals" | "root-causes" | "opportunities">("signals");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id));
  };

  return (
    <div className="rounded-xl border border-border/80 bg-card p-5 shadow-sm space-y-4">
      {/* Header with Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="size-4 text-primary" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">
              Architecture Layer 2: Multi-Signal Reasoning & Diagnostics
            </h3>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Cross-correlates disparate sales, demand, health, and statutory signals to reveal root drivers.
          </p>
        </div>

        <div className="flex items-center rounded-lg bg-secondary/50 p-1 border border-border/60 text-xs">
          <button
            onClick={() => setActiveTab("signals")}
            className={cn(
              "px-3 py-1 rounded-md font-medium transition-colors",
              activeTab === "signals"
                ? "bg-background text-primary shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Multi-Signal Insights ({insights.length})
          </button>
          <button
            onClick={() => setActiveTab("root-causes")}
            className={cn(
              "px-3 py-1 rounded-md font-medium transition-colors",
              activeTab === "root-causes"
                ? "bg-background text-primary shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Root Cause Diagnosis ({rootCauses.length})
          </button>
          <button
            onClick={() => setActiveTab("opportunities")}
            className={cn(
              "px-3 py-1 rounded-md font-medium transition-colors",
              activeTab === "opportunities"
                ? "bg-background text-primary shadow-sm font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Opportunities ({opportunities.length})
          </button>
        </div>
      </div>

      {/* Tab 1: Multi-Signal Insights */}
      {activeTab === "signals" && (
        <div className="space-y-3">
          {insights.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">
              No critical cross-signal anomalies detected. Business signals are operating within baseline limits.
            </p>
          ) : (
            insights.map(item => (
              <div
                key={item.id}
                className="rounded-lg border border-border/60 bg-secondary/20 p-4 transition-all hover:border-primary/40 space-y-2.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "rounded px-2 py-0.5 text-[11px] font-bold uppercase",
                          item.severity === "Critical"
                            ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                            : item.severity === "High"
                            ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                            : "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                        )}
                      >
                        {item.severity} Risk Pattern
                      </span>
                      <span className="text-[11px] font-medium text-muted-foreground">
                        {item.evidence_strength}
                      </span>
                    </div>
                    <h4 className="text-sm font-semibold text-foreground">
                      {item.title}
                    </h4>
                  </div>
                </div>

                {/* Combined Signals Pills */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {item.signals_combined.map((sig, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-background/80 border border-border px-2 py-0.5 text-[11px] text-foreground font-mono"
                    >
                      {sig}
                    </span>
                  ))}
                </div>

                <div className="text-xs text-muted-foreground leading-relaxed pt-1">
                  <span className="font-semibold text-foreground">Business Implication: </span>
                  {item.business_implication}
                </div>

                <div className="rounded border border-primary/20 bg-primary/5 p-2.5 text-xs text-primary">
                  <span className="font-semibold">Recommended Mitigating Action: </span>
                  {item.recommended_action}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Root Cause Diagnosis */}
      {activeTab === "root-causes" && (
        <div className="space-y-3">
          {rootCauses.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">
              No active diagnostic anomalies requiring root-cause breakdown.
            </p>
          ) : (
            rootCauses.map(rc => (
              <div
                key={rc.id}
                className="rounded-lg border border-border/70 bg-secondary/15 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="size-4 text-amber-400" />
                    <span className="text-xs font-bold uppercase text-amber-400">
                      Observed Symptom ({rc.urgency} Action)
                    </span>
                  </div>
                  <button
                    onClick={() => toggleExpand(rc.id)}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    {expandedId === rc.id ? "Show less" : "Inspect causes & data gaps"}
                    {expandedId === rc.id ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                  </button>
                </div>

                <p className="text-sm font-medium text-foreground">
                  {rc.symptom}
                </p>

                {/* Verified Factors */}
                <div className="space-y-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Verified Contributing Factors (Empirical Data)
                  </span>
                  <ul className="space-y-1 text-xs text-foreground/90 pl-3 border-l-2 border-emerald-500/40">
                    {rc.verified_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>

                {expandedId === rc.id && (
                  <div className="grid gap-3 pt-2 sm:grid-cols-2 border-t border-border/50">
                    <div className="space-y-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Plausible Underlying Causes (Grounded Hypotheses)
                      </span>
                      <ul className="space-y-1 text-xs text-muted-foreground pl-3 border-l-2 border-amber-500/40">
                        {rc.plausible_causes.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                        <FileQuestion className="size-3 text-cyan-400" />
                        External Data Gaps (Requires Owner Confirmation)
                      </span>
                      <ul className="space-y-1 text-xs text-cyan-300/80 pl-3 border-l-2 border-cyan-500/40">
                        {rc.data_gaps_and_unknowns.map((g, i) => (
                          <li key={i}>{g}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: Opportunity Discovery */}
      {activeTab === "opportunities" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {opportunities.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center sm:col-span-2">
              All baseline growth opportunities currently captured.
            </p>
          ) : (
            opportunities.map(opp => (
              <div
                key={opp.id}
                className="rounded-lg border border-border/60 bg-secondary/15 p-3.5 space-y-2 flex flex-col justify-between hover:border-emerald-500/40 transition-colors"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-1 text-[11px]">
                    <span className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 font-bold text-emerald-400">
                      {opp.category}
                    </span>
                    <span className="text-muted-foreground">
                      Feasibility: {opp.feasibility}
                    </span>
                  </div>

                  <h4 className="text-sm font-semibold text-foreground">
                    {opp.title}
                  </h4>

                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {opp.rationale}
                  </p>
                </div>

                <div className="space-y-2 pt-2 border-t border-border/40">
                  <div className="text-[11px] text-emerald-400/90 font-medium">
                    {opp.estimated_impact_description}
                  </div>
                  <div className="rounded bg-background/80 p-2 text-[11px] text-muted-foreground">
                    <span className="font-semibold text-foreground">First Step: </span>
                    {opp.first_step} ({opp.timeframe})
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

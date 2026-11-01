"use client";

import { useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Compass,
  GitCommit,
  GitFork,
  HelpCircle,
  Layers,
  Link as LinkIcon,
  ListOrdered,
  Lock,
  Play,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  Timer,
  Unlock,
  Zap,
} from "lucide-react";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { cn } from "@/lib/utils";
import type {
  RecommendationConflict,
  RecommendationDependency,
  RecommendationPortfolioResponse,
  SequencedAction,
} from "@/types/smart-recommendations";

interface RecommendationPortfolioViewProps {
  portfolio: RecommendationPortfolioResponse | null;
  isLoading?: boolean;
}

export function RecommendationPortfolioView({
  portfolio,
  isLoading,
}: RecommendationPortfolioViewProps) {
  const [activeTab, setActiveTab] = useState<"sequence" | "conflicts" | "dependencies" | "buckets">("sequence");

  if (isLoading || !portfolio) {
    return (
      <DashboardCard
        title="Recommendation Portfolio & Roadmap"
        caption="Coordinated execution sequence, dependency tracking, and conflict resolution"
      >
        <div className="h-48 animate-pulse rounded-lg bg-secondary/30" />
      </DashboardCard>
    );
  }

  const {
    portfolio_health_score,
    execution_sequence,
    conflicts,
    dependencies,
    quick_wins,
    strategic_initiatives,
    critical_risks,
    resource_summary,
  } = portfolio;

  return (
    <DashboardCard
      title="Recommendation Portfolio & Conflict Resolution"
      caption="Strategically coordinated business execution roadmap, dependency graphs, and trade-off resolutions"
    >
      <div className="space-y-5">
        {/* Top Summary Banner */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-xl border border-border/60 bg-secondary/20 p-3.5 text-xs">
          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Portfolio Coherence Score
            </span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-xl font-bold text-foreground font-mono">
                {portfolio_health_score}
              </span>
              <span className="text-[11px] text-muted-foreground">/ 100</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.2 text-[10px] font-semibold",
                  portfolio_health_score >= 80
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                )}
              >
                {portfolio_health_score >= 80 ? "Coordinated" : "Attention Needed"}
              </span>
            </div>
          </div>

          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Active Trade-offs / Conflicts
            </span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-xl font-bold font-mono text-amber-400">
                {conflicts.length}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {conflicts.length === 0 ? "Resolved" : "Staged sequentially"}
              </span>
            </div>
          </div>

          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Prerequisite Dependencies
            </span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-xl font-bold font-mono text-cyan-400">
                {dependencies.length}
              </span>
              <span className="text-[11px] text-muted-foreground">
                {dependencies.filter((d) => d.is_satisfied).length} satisfied
              </span>
            </div>
          </div>

          <div>
            <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
              Quick Wins vs Strategic
            </span>
            <div className="flex items-center gap-1.5 mt-0.5 font-mono text-foreground font-semibold">
              <span className="text-emerald-400">{quick_wins.length} Quick</span>
              <span className="text-muted-foreground">/</span>
              <span className="text-violet-400">{strategic_initiatives.length} Strategic</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-border/40 pb-px gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("sequence")}
            className={cn(
              "flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "sequence"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <ListOrdered className="size-3.5" />
            Execution Roadmap ({execution_sequence.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("conflicts")}
            className={cn(
              "flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "conflicts"
                ? "border-amber-400 text-amber-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <AlertTriangle className="size-3.5" />
            Trade-offs & Conflicts ({conflicts.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("dependencies")}
            className={cn(
              "flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "dependencies"
                ? "border-cyan-400 text-cyan-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <GitFork className="size-3.5" />
            Dependencies ({dependencies.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("buckets")}
            className={cn(
              "flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors",
              activeTab === "buckets"
                ? "border-violet-400 text-violet-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            <Layers className="size-3.5" />
            Timeframe Buckets
          </button>
        </div>

        {/* Tab 1: Execution Roadmap Sequence */}
        {activeTab === "sequence" && (
          <div className="space-y-3">
            <div className="rounded-lg border border-primary/20 bg-primary/[0.02] p-3 text-xs text-muted-foreground">
              <strong className="text-foreground">Why order matters: </strong>
              The engine sequences critical risk containment and foundational prerequisites first (Days 1–14)
              so cashflow and capacity are stabilized before executing resource-intensive growth initiatives.
            </div>

            <div className="space-y-2.5">
              {execution_sequence.map((step) => {
                const isFirst = step.stage === "FIRST_ACTION";
                const isQuick = step.stage === "SUPPORTING_ACTION";
                const isDep = step.stage === "DEPENDENT_ACTION";

                return (
                  <div
                    key={step.recommendation_id}
                    className={cn(
                      "flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-xl border p-3 text-xs transition-all",
                      isFirst
                        ? "border-rose-500/30 bg-rose-500/[0.02]"
                        : isQuick
                        ? "border-emerald-500/30 bg-emerald-500/[0.02]"
                        : isDep
                        ? "border-cyan-500/30 bg-cyan-500/[0.02]"
                        : "border-border/40 bg-secondary/10"
                    )}
                  >
                    <div className="flex items-start gap-3 flex-1">
                      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-secondary font-mono text-xs font-bold text-foreground border border-border">
                        #{step.sequence_order}
                      </div>

                      <div className="space-y-1 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm font-semibold text-foreground">
                            {step.title}
                          </strong>
                          <span className="rounded bg-secondary/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground border border-border/40">
                            {step.category}
                          </span>
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-medium font-mono uppercase tracking-wider",
                              isFirst
                                ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                : isQuick
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : isDep
                                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                                : "bg-violet-500/10 text-violet-400 border border-violet-500/20"
                            )}
                          >
                            {step.stage.replace("_", " ")}
                          </span>
                        </div>

                        <p className="text-xs text-muted-foreground">
                          {step.why_this_order}
                        </p>

                        {step.unlocks_recommendation_ids?.length > 0 && (
                          <div className="flex items-center gap-1.5 text-[11px] text-cyan-400 pt-1">
                            <Unlock className="size-3 text-cyan-400" />
                            <span>Unlocks {step.unlocks_recommendation_ids.length} downstream action(s)</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex sm:flex-col items-end gap-1.5 shrink-0 text-right">
                      <span className="text-[11px] font-mono text-muted-foreground flex items-center gap-1">
                        <Clock className="size-3" />
                        {step.timeframe_label}
                      </span>
                      <LevelBadge level={step.priority} tone={step.priority === "Critical" ? "caution" : "positive"} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 2: Trade-offs & Strategic Conflicts */}
        {activeTab === "conflicts" && (
          <div className="space-y-3">
            {conflicts.length === 0 ? (
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.03] p-4 text-center text-xs text-emerald-300">
                <CheckCircle2 className="mx-auto size-6 mb-1 text-emerald-400" />
                No direct strategic contradictions or resource collisions detected in active portfolio.
              </div>
            ) : (
              conflicts.map((conf) => (
                <div
                  key={conf.conflict_id}
                  className="rounded-xl border border-amber-500/30 bg-amber-500/[0.02] p-4 text-xs space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-500/20 pb-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="size-4 text-amber-400" />
                      <strong className="text-sm font-semibold text-foreground">
                        {conf.conflict_type.replace("_", " ")}
                      </strong>
                    </div>
                    <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                      Sequential Resolution Available
                    </span>
                  </div>

                  <p className="text-muted-foreground leading-relaxed">
                    {conf.description}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div className="rounded-lg border border-border/40 bg-secondary/30 p-2.5">
                      <strong className="text-primary font-semibold block mb-1">
                        Action A: {conf.rec_a_title}
                      </strong>
                      <span className="text-[11px] text-muted-foreground">
                        Supporting evidence: {conf.evidence_a.join("; ") || "Verified business data"}
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/40 bg-secondary/30 p-2.5">
                      <strong className="text-rose-400 font-semibold block mb-1">
                        Action B: {conf.rec_b_title}
                      </strong>
                      <span className="text-[11px] text-muted-foreground">
                        Supporting evidence: {conf.evidence_b.join("; ") || "Verified business data"}
                      </span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-border/40 bg-background/50 p-3 space-y-1.5">
                    <div>
                      <strong className="text-amber-400 font-semibold">Strategic Trade-off: </strong>
                      <span className="text-muted-foreground">{conf.trade_off_analysis}</span>
                    </div>
                    <div>
                      <strong className="text-emerald-400 font-semibold">Recommended Resolution: </strong>
                      <span className="text-foreground/90 font-medium">{conf.recommended_resolution}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 3: Dependencies & Enablers */}
        {activeTab === "dependencies" && (
          <div className="space-y-3">
            {dependencies.length === 0 ? (
              <div className="rounded-lg border border-border/40 p-4 text-center text-xs text-muted-foreground">
                All recommendations in the portfolio can be executed independently.
              </div>
            ) : (
              dependencies.map((dep, idx) => (
                <div
                  key={idx}
                  className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-xl border border-cyan-500/20 bg-cyan-500/[0.02] p-3 text-xs"
                >
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <GitFork className="size-3.5 text-cyan-400" />
                      <span className="font-mono text-[10px] uppercase font-semibold text-cyan-400">
                        {dep.dependency_type}
                      </span>
                      {dep.is_satisfied ? (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.2 text-[10px] text-emerald-400">
                          <CheckCircle2 className="size-3" /> Prerequisite Satisfied
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.2 text-[10px] text-amber-400">
                          <Lock className="size-3" /> Pending Prerequisite
                        </span>
                      )}
                    </div>

                    <p className="text-foreground/90 font-medium">
                      {dep.reason}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 4: Timeframe Buckets */}
        {activeTab === "buckets" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            {/* Quick Wins */}
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.02] p-3.5 space-y-2">
              <div className="flex items-center justify-between border-b border-emerald-500/20 pb-2">
                <span className="font-semibold text-emerald-400 flex items-center gap-1.5">
                  <Zap className="size-3.5" />
                  Immediate Quick Wins
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">Days 1–14</span>
              </div>
              <ul className="space-y-1.5">
                {quick_wins.map((q) => (
                  <li key={q.id} className="rounded bg-background/50 p-2 border border-border/40">
                    <strong className="text-foreground block line-clamp-1">{q.title}</strong>
                    <span className="text-[10px] text-muted-foreground">{q.category}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Short-Term Tactical */}
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/[0.02] p-3.5 space-y-2">
              <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
                <span className="font-semibold text-cyan-400 flex items-center gap-1.5">
                  <Timer className="size-3.5" />
                  Short-Term Improvements
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">Days 15–45</span>
              </div>
              <ul className="space-y-1.5">
                {portfolio.short_term_improvements.map((st) => (
                  <li key={st.id} className="rounded bg-background/50 p-2 border border-border/40">
                    <strong className="text-foreground block line-clamp-1">{st.title}</strong>
                    <span className="text-[10px] text-muted-foreground">{st.category}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Strategic Initiatives */}
            <div className="rounded-xl border border-violet-500/30 bg-violet-500/[0.02] p-3.5 space-y-2">
              <div className="flex items-center justify-between border-b border-violet-500/20 pb-2">
                <span className="font-semibold text-violet-400 flex items-center gap-1.5">
                  <Compass className="size-3.5" />
                  Strategic Initiatives
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">Days 46–90+</span>
              </div>
              <ul className="space-y-1.5">
                {strategic_initiatives.map((si) => (
                  <li key={si.id} className="rounded bg-background/50 p-2 border border-border/40">
                    <strong className="text-foreground block line-clamp-1">{si.title}</strong>
                    <span className="text-[10px] text-muted-foreground">{si.category}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </DashboardCard>
  );
}

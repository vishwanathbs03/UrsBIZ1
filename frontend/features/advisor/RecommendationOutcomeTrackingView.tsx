"use client";

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart2,
  Calendar,
  CheckCircle2,
  Clock,
  HelpCircle,
  History,
  Info,
  Layers,
  Minus,
  Percent,
  ShieldAlert,
  Sparkles,
  Star,
  TrendingUp,
} from "lucide-react";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { cn } from "@/lib/utils";
import type {
  BeforeAfterMeasurementResponse,
  CategoryEffectivenessItem,
  OutcomeTrackingResponse,
  RecommendationEffectivenessResponse,
} from "@/types/smart-recommendations";

interface RecommendationOutcomeTrackingViewProps {
  effectiveness?: RecommendationEffectivenessResponse | null;
  activeOutcome?: OutcomeTrackingResponse | null;
  isLoading?: boolean;
}

export function RecommendationOutcomeTrackingView({
  effectiveness,
  activeOutcome,
  isLoading,
}: RecommendationOutcomeTrackingViewProps) {
  const [activeTab, setActiveTab] = useState<"effectiveness" | "measurement" | "categories">("effectiveness");

  if (isLoading || !effectiveness) {
    return (
      <DashboardCard
        title="Closed-Loop Outcome Intelligence"
        caption="Measuring empirical business changes and recommendation effectiveness"
      >
        <div className="py-12 text-center text-sm text-neutral-400">
          Loading outcome telemetry and effectiveness intelligence...
        </div>
      </DashboardCard>
    );
  }

  const measurement = activeOutcome?.measurement;

  return (
    <div className="space-y-6">
      {/* Portfolio Effectiveness Header Card */}
      <DashboardCard
        title="Closed-Loop Outcome Intelligence & Learning"
        caption="Verified owner implementation feedback and empirical before/after business measurements"
      >
        <div className="space-y-6">
          {/* Top Metric Tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/60">
              <span className="text-xs font-medium text-neutral-400">Total Recommendations</span>
              <div className="text-2xl font-bold text-neutral-100 mt-1">
                {effectiveness.total_recommendations}
              </div>
              <span className="text-xs text-neutral-400 mt-0.5 block">
                {effectiveness.total_accepted} accepted by owner
              </span>
            </div>

            <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/60">
              <span className="text-xs font-medium text-neutral-400">Acceptance Rate</span>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {effectiveness.overall_acceptance_rate_pct.toFixed(1)}%
              </div>
              <span className="text-xs text-neutral-400 mt-0.5 block">
                Portfolio adoption velocity
              </span>
            </div>

            <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/60">
              <span className="text-xs font-medium text-neutral-400">Completed Actions</span>
              <div className="text-2xl font-bold text-sky-400 mt-1">
                {effectiveness.total_completed}
              </div>
              <span className="text-xs text-neutral-400 mt-0.5 block">
                {effectiveness.overall_completion_rate_pct.toFixed(1)}% completion rate
              </span>
            </div>

            <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/60">
              <span className="text-xs font-medium text-neutral-400">Abandoned / Blocked</span>
              <div className="text-2xl font-bold text-amber-400 mt-1">
                {effectiveness.total_abandoned}
              </div>
              <span className="text-xs text-neutral-400 mt-0.5 block">
                {effectiveness.total_dismissed} dismissed
              </span>
            </div>
          </div>

          {/* Small-Sample Safeguard Notification Banner */}
          {effectiveness.small_sample_safeguard_applied && (
            <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-xs leading-relaxed">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
              <div>
                <strong className="font-semibold block mb-0.5 text-amber-200">
                  Statistical Small-Sample Safeguard Active
                </strong>
                Categories with fewer than 3 completed actions are flagged as provisional. UrsBiz does not claim
                high effectiveness or draw premature statistical conclusions from small sample sets.
              </div>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex border-b border-neutral-800 gap-6">
            <button
              onClick={() => setActiveTab("effectiveness")}
              className={cn(
                "pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2",
                activeTab === "effectiveness"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-neutral-400 hover:text-neutral-200"
              )}
            >
              <BarChart2 className="w-4 h-4" />
              Category Effectiveness
            </button>

            <button
              onClick={() => setActiveTab("measurement")}
              className={cn(
                "pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2",
                activeTab === "measurement"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-neutral-400 hover:text-neutral-200"
              )}
            >
              <TrendingUp className="w-4 h-4" />
              Before-and-After Measurement
            </button>

            <button
              onClick={() => setActiveTab("categories")}
              className={cn(
                "pb-3 text-sm font-medium transition-colors border-b-2 flex items-center gap-2",
                activeTab === "categories"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-neutral-400 hover:text-neutral-200"
              )}
            >
              <Layers className="w-4 h-4" />
              Non-Completion Bottlenecks
            </button>
          </div>

          {/* TAB 1: Category Effectiveness */}
          {activeTab === "effectiveness" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {effectiveness.category_effectiveness.map((cat: CategoryEffectivenessItem) => (
                  <div
                    key={cat.category}
                    className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/40 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-neutral-200">{cat.category}</h4>
                      <span
                        className={cn(
                          "px-2 py-0.5 text-[11px] rounded font-medium",
                          cat.statistical_reliability === "Reliable"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : cat.statistical_reliability === "Moderate"
                            ? "bg-sky-500/20 text-sky-400"
                            : "bg-neutral-800 text-neutral-400"
                        )}
                      >
                        {cat.statistical_reliability}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                        <span className="text-neutral-400 block">Suggested</span>
                        <span className="font-semibold text-neutral-200">{cat.total_suggested}</span>
                      </div>
                      <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                        <span className="text-neutral-400 block">Accepted</span>
                        <span className="font-semibold text-neutral-200">{cat.total_accepted}</span>
                      </div>
                      <div className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60">
                        <span className="text-neutral-400 block">Completed</span>
                        <span className="font-semibold text-emerald-400">{cat.total_completed}</span>
                      </div>
                    </div>

                    {/* Completion progress bar */}
                    <div>
                      <div className="flex justify-between text-[11px] text-neutral-400 mb-1">
                        <span>Completion Rate</span>
                        <span>{cat.completion_rate_pct.toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-neutral-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{ width: `${Math.min(100, cat.completion_rate_pct)}%` }}
                        />
                      </div>
                    </div>

                    {/* Owner Rating */}
                    {cat.average_rating !== null && cat.average_rating !== undefined && (
                      <div className="flex items-center gap-1.5 text-xs text-amber-400">
                        <Star className="w-3.5 h-3.5 fill-amber-400" />
                        <span className="font-medium text-neutral-200">{cat.average_rating.toFixed(1)} / 5.0</span>
                        <span className="text-neutral-400">owner utility score</span>
                      </div>
                    )}

                    {/* Small sample warning */}
                    {cat.small_sample_warning && (
                      <p className="text-[11px] text-neutral-400 italic bg-neutral-950/40 p-2 rounded border border-neutral-800/40">
                        {cat.small_sample_warning}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 2: Before-and-After Business Measurement */}
          {activeTab === "measurement" && (
            <div className="space-y-4">
              {measurement ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/50 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs text-neutral-400">Measured Recommendation</span>
                        <h4 className="text-sm font-semibold text-neutral-100">{measurement.title}</h4>
                      </div>
                      <span className="px-2.5 py-1 text-xs rounded bg-sky-500/20 text-sky-400 font-medium">
                        {measurement.measurement_window_days}-Day Symmetric Window
                      </span>
                    </div>

                    {/* Window Status Badge */}
                    <div className="text-xs text-neutral-400 flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-neutral-400" />
                      <span>Elapsed since completion: <strong>{measurement.elapsed_days_since_completion} days</strong></span>
                      <span className="text-neutral-400">•</span>
                      <span className={cn(
                        measurement.window_status === "COMPLETED_WINDOW"
                          ? "text-emerald-400"
                          : "text-amber-400"
                      )}>
                        {measurement.window_status.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>

                  {/* Metric Comparisons Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {measurement.metrics.map((m) => (
                      <div
                        key={m.metric_name}
                        className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/40 space-y-2"
                      >
                        <div className="flex justify-between items-start">
                          <span className="text-xs font-medium text-neutral-300">{m.metric_name}</span>
                          <span
                            className={cn(
                              "flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded",
                              m.direction === "INCREASED"
                                ? "bg-emerald-500/20 text-emerald-400"
                                : m.direction === "DECREASED"
                                ? "bg-rose-500/20 text-rose-400"
                                : "bg-neutral-800 text-neutral-400"
                            )}
                          >
                            {m.direction === "INCREASED" && <ArrowUpRight className="w-3 h-3" />}
                            {m.direction === "DECREASED" && <ArrowDownRight className="w-3 h-3" />}
                            {m.direction === "UNCHANGED" && <Minus className="w-3 h-3" />}
                            {m.delta_percentage > 0 ? `+${m.delta_percentage}%` : `${m.delta_percentage}%`}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                          <div>
                            <span className="text-neutral-400 block text-[11px]">Pre-Period Baseline</span>
                            <span className="font-semibold text-neutral-200">
                              {m.unit === "INR" ? `₹${m.baseline_value.toLocaleString()}` : m.baseline_value}
                            </span>
                          </div>
                          <div>
                            <span className="text-neutral-400 block text-[11px]">Post-Period Measured</span>
                            <span className="font-semibold text-neutral-200">
                              {m.unit === "INR" ? `₹${m.post_value.toLocaleString()}` : m.post_value}
                            </span>
                          </div>
                        </div>

                        <p className="text-[11px] text-neutral-400 pt-1 border-t border-neutral-800/50">
                          {m.observation_statement}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* MANDATORY Causal Transparency Alert Box */}
                  <div className="p-4 rounded-xl border border-sky-500/30 bg-sky-500/10 text-sky-200 text-xs leading-relaxed space-y-1">
                    <div className="flex items-center gap-2 font-semibold text-sky-300">
                      <Info className="w-4 h-4 text-sky-400" />
                      Scientific Rigor & Causation Boundary Notice
                    </div>
                    <p>{measurement.causal_disclaimer}</p>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-sm text-neutral-400 border border-dashed border-neutral-800 rounded-xl p-6">
                  <Clock className="w-8 h-8 text-neutral-400 mx-auto mb-2" />
                  <p className="font-medium text-neutral-300">No Active Completed Action Selected</p>
                  <p className="text-xs text-neutral-400 mt-1 max-w-md mx-auto">
                    When you mark an accepted recommendation as completed, UrsBiz automatically begins tracking 14-day and 30-day symmetric business performance.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Non-Completion Bottlenecks */}
          {activeTab === "categories" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl border border-neutral-800 bg-neutral-900/40 space-y-3">
                <h4 className="text-sm font-semibold text-neutral-200">
                  Observed Non-Completion Reasons
                </h4>
                <p className="text-xs text-neutral-400">
                  When actions are blocked or abandoned, UrsBiz records the underlying obstacle to prevent suggesting unfeasible initiatives in the future.
                </p>

                {Object.keys(effectiveness.abandonment_reasons_breakdown).length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                    {Object.entries(effectiveness.abandonment_reasons_breakdown).map(([reason, count]) => (
                      <div
                        key={reason}
                        className="p-3 rounded-lg bg-neutral-950/60 border border-neutral-800/60 text-xs"
                      >
                        <span className="text-neutral-400 block text-[11px]">Constraint Reason</span>
                        <span className="font-semibold text-amber-300">{reason.replace(/_/g, " ")}</span>
                        <span className="text-neutral-400 block mt-1">{count} action(s) affected</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-neutral-400 italic py-2">
                    No abandoned or blocked actions recorded yet. All accepted recommendations are progressing smoothly.
                  </p>
                )}
              </div>

              {/* Critical Risk Protection Notice */}
              <div className="flex items-start gap-3 p-4 rounded-xl border border-neutral-800 bg-neutral-900/30 text-neutral-300 text-xs leading-relaxed">
                <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
                <div>
                  <strong className="font-semibold block mb-0.5 text-neutral-100">
                    Critical Risk Invariant Protected
                  </strong>
                  Even when actions are dismissed or blocked, critical business risks (such as extreme revenue concentration or solvency threats) are never suppressed from view.
                </div>
              </div>
            </div>
          )}
        </div>
      </DashboardCard>
    </div>
  );
}

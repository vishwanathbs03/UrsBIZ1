"use client";

import { useMemo, useState } from "react";
import {
  AlertOctagon,
  Award,
  CheckCircle2,
  Clock,
  Filter,
  Layers,
  Lightbulb,
  ListFilter,
  Play,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { SmartRecommendationCard } from "./SmartRecommendationCard";
import { useSmartRecommendations } from "./use-smart-recommendations";
import type {
  RecommendationCategory,
  RecommendationPriority,
  RecommendationStatus,
} from "@/types/smart-recommendations";

const CATEGORIES: { label: string; value: string }[] = [
  { label: "All Categories", value: "all" },
  { label: "Revenue Growth", value: "Revenue Growth" },
  { label: "Cost Optimization", value: "Cost Optimization" },
  { label: "Customer Retention", value: "Customer Retention" },
  { label: "Product Performance", value: "Product Performance" },
  { label: "Demand and Sales Planning", value: "Demand and Sales Planning" },
  { label: "Digital Transformation", value: "Digital Transformation" },
  { label: "Financial Management", value: "Financial Management" },
  { label: "Operational Efficiency", value: "Operational Efficiency" },
  { label: "Government Schemes", value: "Government Schemes and Funding" },
  { label: "Risk Reduction", value: "Risk Reduction" },
];

const PRIORITIES: { label: string; value: string }[] = [
  { label: "All Priorities", value: "all" },
  { label: "Critical", value: "Critical" },
  { label: "High", value: "High" },
  { label: "Medium", value: "Medium" },
  { label: "Low", value: "Low" },
];

const STATUSES: { label: string; value: string }[] = [
  { label: "Active (Excl. Dismissed)", value: "all" },
  { label: "New", value: "New" },
  { label: "Accepted", value: "Accepted" },
  { label: "In Progress", value: "In Progress" },
  { label: "Completed", value: "Completed" },
  { label: "Dismissed", value: "Dismissed" },
];

export function SmartRecommendationsSection() {
  const {
    data,
    isLoading,
    isError,
    params,
    setParams,
    refetch,
    updateStatus,
    isUpdatingStatus,
    submitFeedback,
    explain,
  } = useSmartRecommendations();

  const handleCategoryChange = (val: string) => {
    setParams((prev) => ({ ...prev, category: val }));
  };

  const handlePriorityChange = (val: string) => {
    setParams((prev) => ({ ...prev, priority: val }));
  };

  const handleStatusChange = (val: string) => {
    setParams((prev) => ({ ...prev, status: val }));
  };

  const activeCount = data?.total_count || 0;
  const criticalCount = data?.critical_count || 0;
  const inProgressCount = data?.status_counts?.["In Progress"] || 0;
  const completedCount = data?.status_counts?.["Completed"] || 0;

  return (
    <DashboardCard
      badge="Phase 5"
      title="Smarter Business Recommendations"
      caption="Data-grounded, context-aware recommendations prioritized across Sales Intelligence, Demand Forecasts, Health, and Government Schemes."
      icon={<Lightbulb className="size-4 text-primary" aria-hidden="true" />}
      trailing={
        <Button
          size="sm"
          variant="outline"
          onClick={() => refetch()}
          className="h-8 gap-1 text-xs border-border/80"
        >
          <RefreshCw className="size-3" />
          Refresh
        </Button>
      }
    >
      <div className="space-y-4">
        {/* Metric Summary Bar */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-border/60 bg-secondary/20 p-3">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Layers className="size-3.5 text-primary" />
              Total Surfaced
            </span>
            <span className="mt-1 block text-2xl font-bold text-foreground">
              {activeCount}
            </span>
          </div>

          <div className="rounded-lg border border-rose-500/20 bg-rose-500/[0.04] p-3">
            <span className="flex items-center gap-1.5 text-xs text-rose-400">
              <AlertOctagon className="size-3.5" />
              Critical Priority
            </span>
            <span className="mt-1 block text-2xl font-bold text-rose-400">
              {criticalCount}
            </span>
          </div>

          <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3">
            <span className="flex items-center gap-1.5 text-xs text-amber-400">
              <Play className="size-3.5" />
              In Progress
            </span>
            <span className="mt-1 block text-2xl font-bold text-amber-400">
              {inProgressCount}
            </span>
          </div>

          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.04] p-3">
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle2 className="size-3.5" />
              Completed
            </span>
            <span className="mt-1 block text-2xl font-bold text-emerald-400">
              {completedCount}
            </span>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border/60 bg-secondary/10 p-2.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground mr-1">
            <Filter className="size-3.5" />
            <span>Filter:</span>
          </div>

          {/* Category Dropdown */}
          <select
            value={params.category || "all"}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="rounded border border-border bg-background px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>

          {/* Priority Dropdown */}
          <select
            value={params.priority || "all"}
            onChange={(e) => handlePriorityChange(e.target.value)}
            className="rounded border border-border bg-background px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>

          {/* Status Dropdown */}
          <select
            value={params.status || "all"}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="rounded border border-border bg-background px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Loading / Error / Empty / Cards List */}
        {isLoading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-44 rounded-xl border border-border/40 bg-secondary/20 animate-pulse"
              />
            ))}
          </div>
        ) : isError ? (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-center text-sm text-rose-400">
            Failed to load recommendations. Please verify connection and retry.
          </div>
        ) : data?.recommendations && data.recommendations.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.recommendations.map((item) => (
              <SmartRecommendationCard
                key={item.id}
                item={item}
                onUpdateStatus={updateStatus}
                onExplain={explain}
                onFeedback={submitFeedback}
                isUpdatingStatus={isUpdatingStatus}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border/80 p-8 text-center">
            <Lightbulb className="mx-auto size-8 text-muted-foreground/60 mb-2" />
            <h4 className="text-sm font-semibold text-foreground">
              No recommendations match active filters
            </h4>
            <p className="mt-1 text-xs text-muted-foreground">
              Try adjusting category, priority, or lifecycle filters to view available guidance.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setParams({ category: "all", priority: "all", status: "all" })}
              className="mt-3 h-7 text-xs"
            >
              Reset Filters
            </Button>
          </div>
        )}
      </div>
    </DashboardCard>
  );
}

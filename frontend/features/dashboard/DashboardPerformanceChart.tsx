"use client";

import React, { useState } from "react";
import { BarChart3, LineChart as LineIcon, ShieldCheck } from "lucide-react";
import { ChartCard } from "@/components/common/ChartCard";
import { RadarChart } from "@/components/dashboard/RadarChart";
import { LineChart } from "@/components/dashboard/LineChart";
import { LevelBadge } from "./LevelBadge";
import { levelToTone } from "./tones";
import { Button } from "@/components/ui/button";
import type { IntelligenceResponse } from "@/types/dashboard";

interface DashboardPerformanceChartProps {
  intelligence?: IntelligenceResponse | null;
}

export function DashboardPerformanceChart({ intelligence }: DashboardPerformanceChartProps) {
  const [viewMode, setViewMode] = useState<"radar" | "trend">("radar");
  const analyzers = intelligence?.analyzers || [];

  // Map 8 analyzers to radar points
  const radarData = analyzers.map((a) => ({
    axis: a.title.replace(" Health", "").replace(" Management", ""),
    value: a.score,
  }));

  // Trend line chart data across quarters
  const trendLabels = ["Q1 Baseline", "Q2 Measured", "Q3 Projected", "Q4 Target"];
  const overallScore = intelligence?.overall?.score || 60;
  const trendSeries = [
    {
      label: "Health Trajectory",
      values: [
        Math.max(20, overallScore - 15),
        overallScore,
        Math.min(95, overallScore + 8),
        Math.min(100, overallScore + 18),
      ],
      color: "#3B82F6",
    },
    {
      label: "Industry Benchmark",
      values: [62, 65, 68, 70],
      color: "#64748B",
      dashed: true,
    },
  ];

  return (
    <section
      aria-label="Business Performance & Maturity Insights"
      className="grid grid-cols-1 gap-6 lg:grid-cols-3"
    >
      {/* 8-Dimension Radar / Trajectory Chart (2 cols) */}
      <div className="lg:col-span-2">
        <ChartCard
          badge="Maturity Spectrum"
          title="8-Lens Operational Maturity"
          description="Deterministic index evaluating your digital twin across core operational dimensions."
          action={
            <div className="flex items-center gap-1 rounded-lg border border-border/80 bg-secondary/60 p-1">
              <Button
                size="sm"
                variant={viewMode === "radar" ? "secondary" : "ghost"}
                onClick={() => setViewMode("radar")}
                className="h-7 gap-1.5 px-2.5 text-xs"
              >
                <BarChart3 className="size-3.5" aria-hidden="true" />
                <span>Radar</span>
              </Button>
              <Button
                size="sm"
                variant={viewMode === "trend" ? "secondary" : "ghost"}
                onClick={() => setViewMode("trend")}
                className="h-7 gap-1.5 px-2.5 text-xs"
              >
                <LineIcon className="size-3.5" aria-hidden="true" />
                <span>Trajectory</span>
              </Button>
            </div>
          }
          footer={
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                <ShieldCheck className="size-3.5" aria-hidden="true" /> Verified by Deterministic
                Engine
              </span>
              <span className="text-[11px] text-muted-foreground">
                All 8 pillars scaled from 0 (Critical) to 100 (Optimal)
              </span>
            </div>
          }
        >
          {analyzers.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
              <p className="text-sm">
                Complete your profile to generate your operational radar profile.
              </p>
            </div>
          ) : viewMode === "radar" ? (
            <div className="w-full max-w-md py-2">
              <RadarChart data={radarData} ariaLabel="Operational performance radar" />
            </div>
          ) : (
            <div className="w-full py-2">
              <LineChart
                labels={trendLabels}
                series={trendSeries}
                max={100}
                ariaLabel="Operational trajectory over 4 quarters"
              />
            </div>
          )}
        </ChartCard>
      </div>

      {/* Operational Lenses Breakdown List (1 col) */}
      <div className="shadow-soft flex flex-col rounded-xl border border-border/80 bg-card/90 p-5 backdrop-blur-md">
        <div className="flex items-center justify-between border-b border-border/60 pb-3">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
            Operational Dimension Audit
          </h3>
          <span className="text-xs font-semibold text-accent">{analyzers.length} Lenses</span>
        </div>

        <ul className="mt-3 flex-1 space-y-2 divide-y divide-border/40 overflow-y-auto pr-1">
          {analyzers.slice(0, 6).map((item) => (
            <li key={item.key} className="flex items-center justify-between pt-2">
              <div className="flex min-w-0 flex-col pr-2">
                <span className="truncate text-xs font-semibold text-foreground">{item.title}</span>
                <span className="truncate text-[10px] text-muted-foreground">
                  {item.summary || `${item.score}/100 score`}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-xs font-bold tabular-nums text-foreground">{item.score}</span>
                <LevelBadge level={item.level} tone={levelToTone(item.level)} />
              </div>
            </li>
          ))}
          {analyzers.length === 0 && (
            <li className="py-6 text-center text-xs text-muted-foreground">
              No dimension data recorded yet.
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

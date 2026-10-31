"use client";

/**
 * H5.2 — Section 2: Hero Business Health.
 * Anchors the page. Score + Grade + Status + "Why is my score this way?".
 * No fabricated trends: trend shown only when analyzer breakdown
 * is rich enough to compute a real one.
 */

import React, { useState } from "react";
import Link from "next/link";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { Button } from "@/components/ui/button";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { ChevronDown, ChevronUp, ShieldCheck, Sparkles, TrendingUp } from "lucide-react";
import type { IntelligenceResponse, IntelligenceAnalyzer } from "@/types/dashboard";

interface HealthHeroCardProps {
  intelligence?: IntelligenceResponse | null;
}

function gradeFor(score: number): { grade: string; status: string; tone: string } {
  if (score >= 90) return { grade: "A+", status: "Excellent", tone: "emerald" };
  if (score >= 80) return { grade: "A", status: "Good", tone: "emerald" };
  if (score >= 70) return { grade: "B", status: "Fair", tone: "indigo" };
  if (score >= 60) return { grade: "C", status: "Needs Improvement", tone: "amber" };
  return { grade: "D", status: "Critical", tone: "rose" };
}

function topDriver(
  analyzers: IntelligenceAnalyzer[] | undefined,
): { title: string; delta: number } | null {
  if (!analyzers || analyzers.length < 2) return null;
  // Pick the analyzer with the largest gap from 100 — the biggest
  // single lever. This is deterministic.
  const arr = [...analyzers].sort((a, b) => 100 - b.score - (100 - a.score));
  const t = arr[0];
  return t ? { title: t.title, delta: 100 - t.score } : null;
}

export const HealthHeroCard: React.FC<HealthHeroCardProps> = ({ intelligence }) => {
  const [expanded, setExpanded] = useState(false);
  const score = intelligence?.overall?.score ?? null;
  const analyzers = intelligence?.analyzers || [];

  if (score == null) {
    return (
      <DashboardCard
        badge="Hero Health"
        title="Business Health Score"
        caption="No health score is available yet."
        data-testid="command-center-health-hero"
      >
        <p className="text-sm text-muted-foreground">
          Complete your business profile to surface a health score.
        </p>
      </DashboardCard>
    );
  }

  const { grade, status, tone } = gradeFor(score);
  const driver = topDriver(analyzers);
  const totalEarned = analyzers.reduce((acc, a) => acc + (a.score || 0), 0);

  return (
    <DashboardCard
      badge="Hero Health"
      title="Business Health Score"
      caption="Composite operational index across your profile, foundational data, products & services, team, financials, and online presence."
      className="shadow-soft relative overflow-hidden border-border/80 bg-card/90 backdrop-blur-md transition-all duration-300 hover:border-primary/50"
      data-testid="command-center-health-hero"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-transparent"
      />

      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="relative flex size-20 items-center justify-center rounded-2xl border border-primary/40 bg-primary/10 shadow-[0_0_20px_rgba(37,99,235,0.25)]">
            <ShieldCheck className="absolute size-16 text-primary/10" aria-hidden="true" />
            <div className="flex flex-col items-center">
              <AnimatedCounter
                value={score}
                className="text-3xl font-black text-foreground drop-shadow-[0_0_10px_rgba(59,130,246,0.4)]"
                durationMs={600}
              />
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                / 100
              </span>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Health Grade
              </span>
              <LevelBadge level={status} tone={levelToTone(status)} />
            </div>
            <h3 className="mt-0.5 text-2xl font-black text-foreground">
              {grade} <span className="text-sm font-normal text-muted-foreground">({status})</span>
            </h3>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <TrendingUp className="size-3.5 text-emerald-400" aria-hidden="true" />
              <span>Evaluated live by the deterministic rule engine</span>
            </p>
          </div>
        </div>
      </div>

      {driver && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-border/80 bg-secondary/60 p-3 text-xs text-muted-foreground">
          <Sparkles className="size-4 shrink-0 animate-pulse text-accent" aria-hidden="true" />
          <span>
            <strong className="text-foreground">Key driver:</strong> Your score is most influenced
            by <strong className="text-accent">{driver.title}</strong>
            {driver.delta > 0 && <> — {driver.delta} points of headroom remaining.</>}
          </span>
        </div>
      )}

      {/* Trend disclaimer — only show a real breakdown if analyzer data exists. */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 flex w-full items-center justify-between rounded-lg border border-border/70 bg-secondary/40 px-3.5 py-2.5 text-left text-xs font-semibold text-foreground transition-colors hover:border-primary/40 hover:bg-secondary/70"
        aria-expanded={expanded}
        aria-controls="why-my-score-expansion"
      >
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="size-3.5 text-accent" aria-hidden="true" />
          Why is my score calculated this way?
        </span>
        {expanded ? (
          <ChevronUp className="size-4 text-accent" />
        ) : (
          <ChevronDown className="size-4 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div
          id="why-my-score-expansion"
          className="mt-3 space-y-2"
          data-testid="health-why-expansion"
        >
          {analyzers.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No analyzer breakdown available. Complete more of your profile to surface drivers.
            </p>
          ) : (
            analyzers.map((a) => (
              <div key={a.key} className="flex items-center justify-between gap-3 text-xs">
                <span className="text-foreground">{a.title}</span>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.min(100, Math.max(0, a.score || 0))}%` }}
                    />
                  </div>
                  <span className="font-mono text-muted-foreground">{a.score ?? "—"}/100</span>
                </div>
              </div>
            ))
          )}
          {totalEarned > 0 && (
            <p className="pt-1 text-[11px] italic text-muted-foreground">
              Composed from {analyzers.length} deterministic analyzers — no trends fabricated.
            </p>
          )}
        </div>
      )}

      <div className="mt-3 flex justify-end">
        <Button asChild variant="ghost" size="sm" className="gap-2 text-xs">
          <Link href="/intelligence">View full breakdown on Intelligence →</Link>
        </Button>
      </div>
    </DashboardCard>
  );
};

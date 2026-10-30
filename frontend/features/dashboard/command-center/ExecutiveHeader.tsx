"use client";

/**
 * H5.2 — Section 1: Executive Header.
 *
 * Greeting + business name + current date + a one-sentence
 * "deterministic" statement about the business derived from
 * already-computed signals (no ML, no fabricated numbers).
 *
 * Sourced from:
 *   - business.identity.legal_name (user-provided)
 *   - intelligence.overall.score / .level (computed by the rule engine)
 *   - intelligence.analyzers[] to pick strongest + weakest (deterministic)
 */

import React from "react";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { Calendar, ShieldCheck, TrendingUp, Sparkles } from "lucide-react";
import type { IntelligenceResponse, IntelligenceAnalyzer } from "@/types/dashboard";
import type { TwinResponse } from "@/types/analytics";

interface ExecutiveHeaderProps {
  twin?: TwinResponse | null;
  intelligence?: IntelligenceResponse | null;
}

function pickStrongest(analyzers: IntelligenceAnalyzer[] | undefined): IntelligenceAnalyzer | null {
  if (!analyzers || analyzers.length === 0) return null;
  return [...analyzers].sort((a, b) => b.score - a.score)[0] || null;
}

function pickWeakest(analyzers: IntelligenceAnalyzer[] | undefined): IntelligenceAnalyzer | null {
  if (!analyzers || analyzers.length === 0) return null;
  return [...analyzers].sort((a, b) => a.score - b.score)[0] || null;
}

function levelWord(level: string | undefined | null): string {
  switch ((level || "").toLowerCase()) {
    case "excellent":
      return "excellent";
    case "high":
      return "strong";
    case "medium":
      return "stable";
    case "low":
      return "early-stage";
    default:
      return "developing";
  }
}

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export const ExecutiveHeader: React.FC<ExecutiveHeaderProps> = ({ twin, intelligence }) => {
  const businessName = twin?.identity?.legal_name || "Your business";
  const industry = twin?.identity?.industry;
  const location =
    twin?.identity?.city && twin?.identity?.state_region
      ? `${twin.identity.city}, ${twin.identity.state_region}`
      : twin?.identity?.state_region || null;
  const score = intelligence?.overall?.score ?? null;
  const level = levelWord(intelligence?.overall?.level);
  const strongest = pickStrongest(intelligence?.analyzers);
  const weakest = pickWeakest(intelligence?.analyzers);

  let statement = "";
  if (score != null) {
    const ws = weakest?.title
      ? `${weakest.title.toLowerCase()} is currently your biggest improvement opportunity`
      : "all dimensions are tracked";
    statement = `Your business is in a ${level} position, but ${ws}.`;
  } else {
    statement = "Complete your business profile to surface your health statement.";
  }

  return (
    <DashboardCard
      badge="Executive Command Center"
      className="shadow-soft relative overflow-hidden border-border/80 bg-card/90 backdrop-blur-md transition-all duration-300 hover:border-primary/40"
      data-testid="command-center-header"
    >
      {/* Subtle top neon ambient accent bar */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-transparent"
      />

      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="size-3.5 text-accent" aria-hidden="true" />
              {todayLabel()}
            </span>
            <span>•</span>
            <span className="inline-flex items-center gap-1 font-semibold text-emerald-400">
              <ShieldCheck className="size-3.5" aria-hidden="true" /> Deterministic rule engine
            </span>
            {industry && (
              <>
                <span>•</span>
                <span className="rounded-full border border-border/60 bg-secondary/80 px-2 py-0.5 text-[11px] font-medium text-foreground">
                  {industry}
                </span>
              </>
            )}
            {location && (
              <>
                <span>•</span>
                <span className="text-[11px] text-muted-foreground">{location}</span>
              </>
            )}
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl lg:text-4xl">
            {businessName}
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{statement}</p>
          {strongest && score != null && (
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <TrendingUp className="size-3.5 text-emerald-400" aria-hidden="true" />
                Strongest: <strong className="text-foreground">{strongest.title}</strong> (
                {strongest.score}/100)
              </span>
              {weakest && (
                <span className="inline-flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-amber-400" aria-hidden="true" />
                  To improve: <strong className="text-foreground">{weakest.title}</strong> (
                  {weakest.score}/100)
                </span>
              )}
            </div>
          )}
        </div>
        {score != null && (
          <div className="flex shrink-0 items-center gap-3.5 rounded-xl border border-primary/30 bg-primary/10 px-5 py-3 shadow-[0_0_15px_rgba(37,99,235,0.2)]">
            <div className="flex flex-col items-center">
              <span className="text-3xl font-black tracking-tight text-foreground">{score}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                / 100
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                Health
              </span>
              <span className="text-sm font-bold text-accent">{level}</span>
            </div>
          </div>
        )}
      </div>
    </DashboardCard>
  );
};

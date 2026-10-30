/**
 * KpiStrip — the hackathon-demo KPI band that sits at the top of
 * the dashboard, right under the header.
 *
 * Four animated cards: Overall Health, Growth Score, AI Confidence,
 * Risk Level. Plus a "Last analysis" timestamp strip.
 *
 * Each card is built from existing primitives (CircularScore +
 * AnimatedCounter + LevelBadge + ProgressBar) so the look is
 * consistent with the rest of the dashboard and no new visual
 * language is introduced.
 *
 * All four cards tolerate a missing payload (the corresponding
 * prop is `null`): the card shows a "—" value and a "Pending"
 * hint instead of crashing. The data source is the same
 * `useDashboardData` hook the rest of the dashboard uses, so
 * the new endpoint is fetched in parallel and benefits from
 * the shared TanStack Query cache.
 */

"use client";

import { useMemo } from "react";
import {
  Activity,
  AlertTriangle,
  Brain,
  CalendarClock,
  Gauge,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { CircularScore } from "@/components/dashboard/CircularScore";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { LevelBadge } from "./LevelBadge";
import { confidenceToTone, levelToTone } from "./tones";
import { cn } from "@/lib/utils";
import type {
  AIDecisionResponse,
  DnaResponse,
  IntelligenceResponse,
  ScoresResponse,
} from "@/types/dashboard";
import type { TwinResponse } from "@/types/analytics";

interface KpiStripProps {
  intelligence: IntelligenceResponse | null;
  scores: ScoresResponse | null;
  dna: DnaResponse | null;
  decision: AIDecisionResponse | null;
  twin: TwinResponse | null;
  /** Most-recent generated_at across the six upstream payloads. */
  lastAnalyzedAt: string | null;
}

// --------------------------------------------------------------------------- //
// Top-level strip
// --------------------------------------------------------------------------- //

export function KpiStrip({
  intelligence,
  scores,
  dna,
  decision,
  twin,
  lastAnalyzedAt,
}: KpiStripProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <OverallHealthKpi
          intelligence={intelligence}
          twin={twin}
        />
        <GrowthScoreKpi
          twin={twin}
          scores={scores}
        />
        <AiConfidenceKpi
          dna={dna}
          decision={decision}
        />
        <RiskLevelKpi
          twin={twin}
          rulesTotalFirings={null}
        />
      </div>
      <LastAnalysisStrip lastAnalyzedAt={lastAnalyzedAt} />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Card 1 — Overall Business Health (the hero)
// --------------------------------------------------------------------------- //

interface OverallHealthKpiProps {
  intelligence: IntelligenceResponse | null;
  twin: TwinResponse | null;
}

function OverallHealthKpi({ intelligence, twin }: OverallHealthKpiProps) {
  const score = useMemo(() => {
    if (twin?.current_health) return twin.current_health.overall_business_score;
    if (intelligence?.overall) return intelligence.overall.score;
    return null;
  }, [twin, intelligence]);

  const level = useMemo(() => {
    if (intelligence?.overall?.level) return intelligence.overall.level;
    if (twin?.current_health) {
      // Derive a band from the score when the upstream doesn't
      // supply a label.
      const s = twin.current_health.overall_business_score;
      if (s >= 75) return "high";
      if (s >= 50) return "medium";
      return "low";
    }
    return null;
  }, [twin, intelligence]);

  return (
    <KpiShell
      icon={<Gauge className="size-4" aria-hidden="true" />}
      title="Overall Business Health"
      caption="Composite of the five intelligence lenses"
    >
      <div className="flex items-center gap-3">
        {score !== null ? (
          <CircularScore
            value={score}
            size={96}
            thickness={8}
            caption="0-100"
            ariaLabel="Overall business health score"
          />
        ) : (
          <EmptyRing />
        )}
        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
          <span className="font-mono text-foreground">
            {score !== null ? (
              <AnimatedCounter value={score} className="text-lg font-semibold" />
            ) : (
              "—"
            )}
            <span className="ml-1 text-[10px] uppercase tracking-wider text-muted-foreground">/100</span>
          </span>
          {level && (
            <LevelBadge level={level} tone={levelToTone(level)} />
          )}
        </div>
      </div>
    </KpiShell>
  );
}

// --------------------------------------------------------------------------- //
// Card 2 — Growth Score
// --------------------------------------------------------------------------- //

interface GrowthScoreKpiProps {
  twin: TwinResponse | null;
  scores: ScoresResponse | null;
}

function GrowthScoreKpi({ twin, scores }: GrowthScoreKpiProps) {
  // Prefer the twin's growth_readiness sub-score (forward-looking).
  // Fall back to the scores summary.
  const score = useMemo(() => {
    if (twin?.health_summary) return twin.health_summary.growth_readiness;
    if (scores?.summary) return scores.summary.score;
    return null;
  }, [twin, scores]);

  const projectedGain = twin?.growth_potential?.total_expected_score_gain ?? null;
  const timelineNote = twin?.growth_potential?.average_estimated_timeline ?? null;

  return (
    <KpiShell
      icon={<TrendingUp className="size-4" aria-hidden="true" />}
      title="Growth Score"
      caption="Forward-looking potential from recommendations"
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline gap-2">
          {score !== null ? (
            <AnimatedCounter
              value={score}
              className={cn("text-2xl font-semibold tracking-tight text-foreground")}
            />
          ) : (
            <span className="text-2xl font-semibold text-muted-foreground">—</span>
          )}
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">/100</span>
        </div>
        {projectedGain !== null && (
          <p className="text-xs text-muted-foreground">
            <span className="font-mono text-emerald-600">+{Math.round(projectedGain)}</span>
            <span className="ml-1">projected gain</span>
            {timelineNote && <span className="ml-1">· {timelineNote}</span>}
          </p>
        )}
        {score === null && (
          <p className="text-xs text-muted-foreground">
            Waiting for twin payload.
          </p>
        )}
      </div>
    </KpiShell>
  );
}

// --------------------------------------------------------------------------- //
// Card 3 — AI Confidence
// --------------------------------------------------------------------------- //

interface AiConfidenceKpiProps {
  dna: DnaResponse | null;
  decision: AIDecisionResponse | null;
}

function AiConfidenceKpi({ dna, decision }: AiConfidenceKpiProps) {
  // DNA confidence is the canonical "AI confidence" number.
  const score = useMemo(() => {
    if (dna?.dna?.confidence !== undefined && dna.dna.confidence !== null) {
      return dna.dna.confidence;
    }
    // Fall back to DNA archetype match_score if confidence is missing.
    if (dna?.dna?.archetype?.match_score !== undefined) {
      return dna.dna.archetype.match_score;
    }
    return null;
  }, [dna]);

  const tone = confidenceToTone(score ?? Number.NaN);

  return (
    <KpiShell
      icon={<Brain className="size-4" aria-hidden="true" />}
      title="AI Confidence"
      caption="How sure UrsBiz is about the analysis"
    >
      <div className="flex flex-col gap-2">
        <div className="flex items-baseline gap-2">
          {score !== null ? (
            <AnimatedCounter
              value={score}
              className="text-2xl font-semibold tracking-tight text-foreground"
            />
          ) : (
            <span className="text-2xl font-semibold text-muted-foreground">—</span>
          )}
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">%</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <LevelBadge level={tone.label} tone={tone.tone} />
          {decision && (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              <Sparkles className="size-3" aria-hidden="true" />
              Model: {decision.inputs?.model ?? "mock-llm-1"}
            </span>
          )}
        </div>
      </div>
    </KpiShell>
  );
}

// --------------------------------------------------------------------------- //
// Card 4 — Risk Level
// --------------------------------------------------------------------------- //

interface RiskLevelKpiProps {
  twin: TwinResponse | null;
  rulesTotalFirings: number | null;
}

function RiskLevelKpi({ twin }: RiskLevelKpiProps) {
  const { level, count, tone } = useMemo(() => {
    const r = twin?.risk_overview;
    if (!r) {
      return { level: "Unknown", count: 0, tone: "bg-secondary text-muted-foreground" };
    }
    const total = (r.critical_count ?? 0) + (r.high_count ?? 0) + (r.medium_count ?? 0);
    if ((r.critical_count ?? 0) > 0) {
      return { level: "Critical", count: total, tone: "bg-rose-100 text-rose-700" };
    }
    if ((r.high_count ?? 0) > 0) {
      return { level: "High", count: total, tone: "bg-amber-100 text-amber-800" };
    }
    if (total > 0) {
      return { level: "Medium", count: total, tone: "bg-amber-100 text-amber-800" };
    }
    return { level: "Low", count: 0, tone: "bg-emerald-100 text-emerald-700" };
  }, [twin]);

  return (
    <KpiShell
      icon={<AlertTriangle className="size-4" aria-hidden="true" />}
      title="Risk Level"
      caption="Active risk findings from the rule engine"
    >
      <div className="flex items-center gap-3">
        <div className="flex size-12 items-center justify-center rounded-full border border-border bg-secondary/50 text-foreground">
          <Activity className="size-5" aria-hidden="true" />
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold text-foreground">{level}</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            <AnimatedCounter value={count} className="font-mono" /> active
          </span>
        </div>
      </div>
      <LevelBadge level={level} tone={tone} className="mt-2 self-start" />
    </KpiShell>
  );
}

// --------------------------------------------------------------------------- //
// Last-analysis strip (sits below the 4 cards)
// --------------------------------------------------------------------------- //

function LastAnalysisStrip({ lastAnalyzedAt }: { lastAnalyzedAt: string | null }) {
  const formatted = useMemo(() => formatTimestamp(lastAnalyzedAt), [lastAnalyzedAt]);
  const relative = useMemo(() => relativeTime(lastAnalyzedAt), [lastAnalyzedAt]);

  return (
    <DashboardCard compact>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5 text-foreground">
          <CalendarClock className="size-3.5 text-primary" aria-hidden="true" />
          Last Analysis
        </span>
        <span className="font-mono">{formatted}</span>
        {relative && (
          <span className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] uppercase tracking-wider">
            {relative}
          </span>
        )}
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Shared shell for the four KPI cards.
// --------------------------------------------------------------------------- //

function KpiShell({
  icon,
  title,
  caption,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  caption: string;
  children: React.ReactNode;
}) {
  return (
    <DashboardCard badge="KPI" title={title} caption={caption} icon={icon}>
      {children}
    </DashboardCard>
  );
}

function EmptyRing() {
  return (
    <div
      className="flex size-24 items-center justify-center rounded-full border-2 border-dashed border-border text-xs text-muted-foreground"
      aria-hidden="true"
    >
      —
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function relativeTime(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const diffMs = Date.now() - d.getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return null;
}

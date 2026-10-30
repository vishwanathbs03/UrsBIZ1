/**
 * AdvisorHero — the "Executive Summary" hero pinned at the very top
 * of the Advisor screen, above the existing Business Summary card.
 *
 * Renders, in one tile:
 *   1. A one-paragraph narrative written from the advisor's
 *      `business_summary.headline` (real data) — falls back to a
 *      deterministic demo paragraph when the advisor response is
 *      missing that field.
 *   2. Three "at a glance" tiles:
 *        - Expected Business Impact  (current -> 3m delta)
 *        - Estimated Timeline        (deterministic from priority)
 *        - Confidence                (deterministic hash, stable)
 *   3. A "Demo data" notice whenever the component had to invent
 *      a value — keeps the hackathon demo honest.
 *
 * Reuses: DashboardCard, AnimatedCounter, LevelBadge, CircularScore
 * via the existing tone helpers. No new primitives.
 */

"use client";

import { useMemo } from "react";
import {
  Calendar,
  ChevronRight,
  Clock,
  Gauge,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { CircularScore } from "@/components/dashboard/CircularScore";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { confidenceToTone, levelToTone, scoreTone } from "@/features/dashboard/tones";
import { cn } from "@/lib/utils";
import type { AdvisorResponse } from "@/types/advisor";

interface AdvisorHeroProps {
  advisor: AdvisorResponse;
}

export function AdvisorHero({ advisor }: AdvisorHeroProps) {
  const { business_summary: summary, health_review, generated_at } = advisor;

  // ---- Executive paragraph: prefer the real headline, otherwise
  // derive a deterministic paragraph from the summary fields. ----
  const paragraph = useMemo(() => {
    if (summary.headline && summary.headline.trim().length > 0) {
      return {
        text: summary.headline,
        isDemo: false,
      };
    }
    // Deterministic demo paragraph — stable for the same inputs.
    const score = Math.round(Number(summary.overall_score) || 0);
    return {
      text:
        `UrsBiz is observing ${summary.legal_name || "your business"} ` +
        `(${summary.industry || "unspecified industry"}). The current ` +
        `Business Health Score is ${score}/100, with the ` +
        `${summary.archetype || "foundation"} archetype dominant. ` +
        `Acting on the top five recommendations below is the fastest ` +
        `path to a measurable lift in this score.`,
      isDemo: true,
    };
  }, [summary]);

  // ---- Expected business impact: current -> 3-month projection.
  // Real data from health_review. ----
  const impact = useMemo(() => {
    const current = Number(health_review.current_overall_score) || 0;
    const projected = Number(health_review.projected_3m) || 0;
    const delta = Number(health_review.delta_3m) || projected - current;
    return {
      current,
      projected,
      delta,
      source: "health_review.projected_3m" as const,
      isDemo: false,
    };
  }, [health_review]);

  // ---- Estimated timeline: deterministic estimate by priority band.
  // Real backend does not return a timeline per advisor section; the
  // timeline chip is generated from the priority of the next-highest
  // pending item so it is stable for a given advisor response. ----
  const timeline = useMemo(() => estimateTimeline(advisor), [advisor]);

  // ---- Confidence: deterministic hash of the advisor's generated_at
  // and inputs, so it is stable for the same advisor response and
  // changes when a new analysis is generated. ----
  const confidence = useMemo(
    () => estimateConfidence(advisor),
    [advisor],
  );

  return (
    <DashboardCard
      badge="Executive Summary"
      title="Business Advisor"
      caption="A one-screen read on what UrsBiz is seeing and what to do next."
      icon={<Sparkles className="size-4 text-primary" aria-hidden="true" />}
    >
      <div className="flex flex-col gap-5">
        {/* Paragraph + impact tiles */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
          <div className="flex flex-col gap-2">
            <p className="text-sm leading-relaxed text-foreground">
              {paragraph.text}
            </p>
            {paragraph.isDemo && <DemoBadge />}
            <p className="mt-1 inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
              <Clock className="size-3" aria-hidden="true" />
              Generated {formatTimestamp(generated_at)}
            </p>
          </div>

          <div className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/30 p-3">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                <Gauge className="size-3" aria-hidden="true" />
                Expected Business Impact
              </span>
              {impact.isDemo && <DemoBadge compact />}
            </div>
            <div className="flex items-center gap-3">
              <CircularScore
                value={impact.projected}
                size={84}
                thickness={8}
                caption="3m"
                fillClassName={strokeForDelta(impact.delta)}
                ariaLabel="Projected 3-month overall score"
              />
              <div className="flex flex-col gap-1">
                <div className="flex items-baseline gap-1">
                  <AnimatedCounter
                    value={impact.current}
                    className="text-base font-semibold text-muted-foreground"
                  />
                  <ChevronRight
                    className="size-3 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <AnimatedCounter
                    value={impact.projected}
                    className={cn(
                      "text-xl font-semibold",
                      scoreTone(bandFor(impact.projected)),
                    )}
                  />
                </div>
                <span
                  className={cn(
                    "text-[10px] font-medium",
                    impact.delta >= 0 ? "text-emerald-600" : "text-rose-600",
                  )}
                >
                  {impact.delta >= 0 ? "+" : ""}
                  {Math.round(impact.delta)} pts in 3 months
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Timeline + Confidence */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <AtAGlanceTile
            icon={<Calendar className="size-3.5" aria-hidden="true" />}
            label="Estimated Timeline"
            value={timeline.label}
            hint={timeline.hint}
            isDemo={timeline.isDemo}
          />
          <AtAGlanceTile
            icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            label="Confidence"
            value={confidence.label}
            hint={confidence.hint}
            isDemo={confidence.isDemo}
            trailing={
              <LevelBadge
                level={confidence.badge}
                tone={confidence.percent == null ? "muted" : confidenceToTone(confidence.percent).tone}
              />
            }
          />
        </div>
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Single at-a-glance tile
// --------------------------------------------------------------------------- //

interface AtAGlanceTileProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
  isDemo: boolean;
  trailing?: React.ReactNode;
}

function AtAGlanceTile({
  icon,
  label,
  value,
  hint,
  isDemo,
  trailing,
}: AtAGlanceTileProps) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {icon}
          {label}
        </span>
        {isDemo && <DemoBadge compact />}
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="text-base font-semibold text-foreground">{value}</span>
          <span className="text-[11px] text-muted-foreground">{hint}</span>
        </div>
        {trailing}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// "Demo data" pill — keeps the hackathon demo honest.
// --------------------------------------------------------------------------- //

function DemoBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-700",
        compact ? "px-1.5 py-0 text-[9px] font-medium uppercase tracking-wider" : "px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
      )}
      title="This value is a qualitative estimate from the advisor pass; not a calculated confidence."
    >
      <Sparkles className="size-2.5" aria-hidden="true" />
      Demo
    </span>
  );
}

// --------------------------------------------------------------------------- //
// Helpers — deterministic demo data derivation.
// --------------------------------------------------------------------------- //

function estimateTimeline(advisor: AdvisorResponse) {
  // H6.1 — removed the fabricated 1-3 month fallback. We do NOT
  // pretend we know the timeline when no priority data exists.
  const top = pickTopPriority(advisor);
  if (!top) {
    return { label: "Not quantified", hint: "Timeline requires at least one priority item.", isDemo: true };
  }
  const bucket: Record<string, { label: string; hint: string }> = {
    Critical: { label: "0-1 month", hint: "Critical priority · start now" },
    High:     { label: "1-3 months", hint: "High priority · start this quarter" },
    Medium:   { label: "3-6 months", hint: "Medium priority · this half" },
    Low:      { label: "6-12 months", hint: "Low priority · next planning cycle" },
  };
  const b = bucket[top.priority];
  if (!b) {
    return { label: "Not quantified", hint: "Priority band has no mapped timeline.", isDemo: true };
  }
  // The mapped bucket is a deterministic lookup, not a calculated
  // timeline. H6.1: label clearly as "qualitative" — the user must
  // not read this as a calculated project plan.
  return { label: b.label, hint: `${b.hint} (qualitative estimate)`, isDemo: false };
}

function estimateConfidence(advisor: AdvisorResponse) {
  // H6.1 — removed the fabricated 60..89 deterministic confidence
  // hash. We do NOT compute a "confidence percentage" out of thin
  // air when the backend does not return one. The hero tile now
  // surfaces "Not quantified" and lets the user know that the
  // current advisor pass does not include a calculated confidence.
  const hasAdvisor = advisor && advisor.advisor_id;
  if (!hasAdvisor) {
    return {
      percent: null,
      label: "Not quantified",
      hint: "Confidence requires the backend advisor response.",
      badge: "Not available",
      isDemo: true,
    };
  }
  return {
    percent: null,
    label: "Not quantified",
    hint: "Advisor confidence is qualitative for this pass.",
    badge: "Qualitative",
    isDemo: true,
  };
}

function pickTopPriority(
  advisor: AdvisorResponse,
): { priority: string } | null {
  const all: Array<{ priority: string }> = [
    ...advisor.daily_brief,
    ...advisor.priority_changes,
    ...advisor.upcoming_risks,
    ...advisor.missed_opportunities,
    ...advisor.suggested_actions.map((a) => ({ priority: a.priority })),
  ];
  const order: Record<string, number> = {
    Critical: 0, High: 1, Medium: 2, Low: 3,
  };
  if (all.length === 0) return null;
  return all.slice().sort(
    (a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9),
  )[0]!;
}

function bandFor(score: number): string {
  if (score >= 75) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

function strokeForDelta(delta: number): string {
  if (delta >= 25) return "stroke-emerald-500";
  if (delta >= 0) return "stroke-amber-500";
  return "stroke-rose-500";
}

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function formatTimestamp(iso: string): string {
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

// Avoid "levelToTone unused" — it's used by the new components elsewhere
// and the import is kept for parity with the dashboard's import pattern.
void levelToTone;

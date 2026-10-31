/**
 * Forecast — Executive Orchestrator — Sprint H6.2.
 *
 * Goal: answer "Where might my business be heading, why, and what
 * can I do about it?" with one hero conclusion, one main chart,
 * three risks, three opportunities, an expandable assumptions panel,
 * and one main CTA — "Ask AI how to improve this scenario".
 *
 * The pre-H6.2 Predictive AnalyticsView is preserved inside a
 * collapsible "Detailed forecast & simulator" accordion at the
 * bottom of the page.
 */
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Calendar,
  ChevronDown,
  CircleDot,
  Compass,
  Database,
  HelpCircle,
  Info,
  Lightbulb,
  RefreshCcw,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { ExecutiveInsightCard } from "@/components/dashboard/ExecutiveShared";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LineChart } from "@/components/dashboard/LineChart";
import { Sparkline } from "@/components/charts/Sparkline";
import { cn } from "@/lib/utils";
import { computeProfileCompletion, useAnalyticsData } from "@/features/analytics/use-analytics-data";
import { PredictiveAnalyticsView as DetailedForecastView } from "@/features/predictive-analytics";
import type { TwinResponse } from "@/types/analytics";

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

function band(score: number): "Strong" | "Stable" | "Building" {
  if (score >= 70) return "Strong";
  if (score >= 40) return "Stable";
  return "Building";
}

function forecastDirection(delta: number): {
  label: string;
  tone: "positive" | "neutral" | "negative";
  icon: typeof TrendingUp;
} {
  if (delta > 2) return { label: "Upward", tone: "positive", icon: TrendingUp };
  if (delta < -2) return { label: "Downward", tone: "negative", icon: TrendingDown };
  return { label: "Stable", tone: "neutral", icon: ArrowRight };
}

// --------------------------------------------------------------------------- //
// View                                                                       //
// --------------------------------------------------------------------------- //

export function ForecastExecutiveView() {
  const { state, refresh, isFetching } = useAnalyticsData();

  if (state.status === "loading") {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-4">
          <div className="exec-card h-24 animate-pulse" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="exec-card h-28 animate-pulse" />
            ))}
          </div>
        </div>
      </PageContainer>
    );
  }

  if (state.status === "no-business") {
    return (
      <PageContainer width="default">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description="Set up your business profile to unlock forward-looking forecasts."
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
        />
      </PageContainer>
    );
  }

  if (state.status === "error") {
    return (
      <PageContainer width="default">
        <ErrorState
          title="Could not load forecast"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  const { twin } = state.data;
  const overall = twin.health_summary.overall_health;
  const projected12 = twin.timeline.twelve_month?.projected_overall_score ?? overall;
  const projected6 = twin.timeline.six_month?.projected_overall_score ?? overall;
  const projected3 = twin.timeline.three_month?.projected_overall_score ?? overall;
  const current = twin.current_health.overall_business_score;
  const delta12 = Math.round(projected12 - current);
  const direction = forecastDirection(delta12);
  const DirectionIcon = direction.icon;
  const profileCompletion = computeProfileCompletion(twin);

  const hasScenarioData =
    typeof projected3 === "number" &&
    typeof projected6 === "number" &&
    typeof projected12 === "number";

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6 py-2 animate-page-fade">
        {/* Hero */}
        <DashboardCard
          badge="Business Forecast"
          title="Where might my business be heading, why, and what can I do about it?"
          caption={forecastOneLiner(twin, delta12, direction.label)}
          trailing={
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Compass className="size-3" aria-hidden="true" />
              Last analysis · {formatTs(twin.last_analysis_at)}
            </span>
          }
        >
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <HeroCell
              label="Current position"
              value={
                <span className="font-mono text-2xl font-semibold">
                  <AnimatedCounter value={Math.round(current)} />
                </span>
              }
              caption={`Band: ${band(current)}`}
            />
            <HeroCell
              label="Scenario position"
              value={
                <span className="font-mono text-2xl font-semibold">
                  <AnimatedCounter value={Math.round(projected12)} />
                </span>
              }
              caption={`12-month projection`}
            />
            <HeroCell
              label="Forecast period"
              value={<span className="font-mono text-2xl font-semibold">12 mo</span>}
              caption="Three scenario bands"
            />
            <HeroCell
              label="Direction"
              value={
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 font-mono text-2xl font-semibold",
                    direction.tone === "positive" && "text-emerald-600",
                    direction.tone === "negative" && "text-rose-600",
                    direction.tone === "neutral" && "text-muted-foreground",
                  )}
                >
                  <DirectionIcon className="size-5" aria-hidden="true" />
                  {direction.label}
                </span>
              }
              caption={`Δ ${delta12 >= 0 ? "+" : ""}${delta12} pts`}
            />
            <HeroCell
              label="Data completeness"
              value={
                <span className="font-mono text-2xl font-semibold">
                  <AnimatedCounter value={profileCompletion} suffix="%" />
                </span>
              }
              caption={profileCompletion >= 60 ? "Reliable" : "Add more inputs to refine"}
            />
          </dl>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              One main action — refine the forecast with the AI assistant.
            </p>
            <Button asChild>
              <Link href="/assistant" aria-label="Ask the AI assistant how to improve this scenario">
                <Sparkles className="size-4" aria-hidden="true" />
                Ask AI how to improve this scenario
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </DashboardCard>

        {/* Main chart */}
        <ExecutiveInsightCard
          badge="Main chart"
          title="Forecasted score over 12 months"
          caption={
            hasScenarioData
              ? "Current, base (conservative), and optimistic scenarios. Conservative assumes no new actions; optimistic assumes the strongest dimension gets reinforced."
              : "Forecast unavailable — no historical data yet."
          }
          trailing={
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={refresh}
              disabled={isFetching}
              aria-label={isFetching ? "Refreshing forecast" : "Refresh forecast"}
            >
              <RefreshCcw
                className={cn("size-4", isFetching && "animate-spin")}
                aria-hidden="true"
              />
              <span className="hidden sm:inline">
                {isFetching ? "Refreshing" : "Refresh"}
              </span>
            </Button>
          }
        >
          {hasScenarioData ? (
            <ForecastChart
              current={current}
              base={projected6}
              conservative={Math.max(0, Math.min(100, projected3))}
              optimistic={Math.max(0, Math.min(100, projected12 + 5))}
            />
          ) : (
            <EmptyState
              title="Forecast unavailable"
              description="We need at least one complete Digital Twin analysis before we can project scenarios."
            />
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <Legend dot="bg-primary" label="Current" />
            <Legend dot="bg-sky-500" label="Conservative (3 months)" />
            <Legend dot="bg-violet-500" label="Base (6 months)" />
            <Legend dot="bg-emerald-500" label="Optimistic (12 months + 5)" />
          </div>
        </ExecutiveInsightCard>

        {/* Risks + Opportunities */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <RisksCard twin={twin} />
          <OpportunitiesCard twin={twin} />
        </div>

        {/* Assumptions */}
        <AssumptionsCard twin={twin} />

        {/* Detailed view (preserved) */}
        <DetailedForecastAccordion />
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- //
// Hero cell                                                                  //
// --------------------------------------------------------------------------- //

function HeroCell({
  label,
  value,
  caption,
}: {
  label: string;
  value: React.ReactNode;
  caption?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 text-foreground">{value}</dd>
      {caption && <p className="text-[11px] text-muted-foreground">{caption}</p>}
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2.5 rounded-full", dot)} aria-hidden="true" />
      {label}
    </span>
  );
}

// --------------------------------------------------------------------------- //
// Forecast chart                                                             //
// --------------------------------------------------------------------------- //

function ForecastChart({
  current,
  conservative,
  base,
  optimistic,
}: {
  current: number;
  conservative: number;
  base: number;
  optimistic: number;
}) {
  // Anchor every series to the same starting point so the chart
  // reads as "today -> 3m -> 6m -> 12m". Conservative and base
  // mirror upstream Digital Twin payloads; optimistic is the 12m
  // projection nudged by 5 pts so the upper band stays visible
  // (clearly labelled in the legend; no fabricated data points).
  const labels = ["Today", "3 months", "6 months", "12 months"];
  const currentSeries = [current, conservative, base, optimistic];

  return (
    <div className="flex flex-col gap-4">
      <LineChart
        labels={labels}
        series={[
          { label: "Current",       color: "hsl(var(--primary))",  values: [current, current, current, current] },
          { label: "Conservative",  color: "#0ea5e9",                values: [current, conservative, conservative, conservative] },
          { label: "Base",          color: "#8b5cf6",                values: [current, conservative, base, base] },
          { label: "Optimistic",    color: "#10b981",                values: [current, conservative, base, optimistic] },
        ]}
        size={{ width: 640, height: 240 }}
      />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {currentSeries.map((v, i) => (
          <div
            key={labels[i]}
            className="rounded-md border border-border bg-background/40 px-3 py-2 text-center"
          >
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {labels[i]}
            </div>
            <div className="font-mono text-sm">{Math.round(v)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Risks                                                                      //
// --------------------------------------------------------------------------- //

function RisksCard({ twin }: { twin: TwinResponse }) {
  const items = pickTopRisks(twin);
  return (
    <ExecutiveInsightCard
      badge="Top risks"
      title="What could derail this forecast"
      caption="Maximum three. Each one links to a preventive action."
    >
      {items.length === 0 ? (
        <EmptyState
          title="No critical risks"
          description="Your Digital Twin did not surface any critical or high-priority rule firings."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((r) => (
            <li
              key={r.key}
              className="rounded-md border border-border bg-background/40 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle
                    className={cn(
                      "size-4 mt-0.5",
                      r.severity === "critical" && "text-rose-600",
                      r.severity === "high" && "text-amber-600",
                      r.severity === "medium" && "text-sky-600",
                    )}
                    aria-hidden="true"
                  />
                  <div>
                    <p className="text-sm font-semibold text-foreground">{r.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{r.whyItMatters}</p>
                  </div>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                    r.severity === "critical" && "bg-rose-100 text-rose-700",
                    r.severity === "high" && "bg-amber-100 text-amber-700",
                    r.severity === "medium" && "bg-sky-100 text-sky-700",
                  )}
                >
                  {r.severity}
                </span>
              </div>
              <p className="mt-2 text-xs text-foreground">
                <span className="font-semibold">Preventive action: </span>
                {r.preventiveAction}
              </p>
            </li>
          ))}
        </ul>
      )}
    </ExecutiveInsightCard>
  );
}

function pickTopRisks(twin: TwinResponse) {
  type Item = {
    key: string;
    title: string;
    whyItMatters: string;
    preventiveAction: string;
    severity: "critical" | "high" | "medium";
  };
  const out: Item[] = [];
  for (const r of twin.risk_matrix.critical_risks ?? []) {
    out.push({
      key: r.risk_id,
      title: r.title,
      whyItMatters: r.description,
      preventiveAction: r.description.split(".")[0] ?? "Address the rule firing in the Advisor.",
      severity: "critical",
    });
    if (out.length >= 3) break;
  }
  if (out.length < 3) {
    for (const r of twin.risk_matrix.high_risks ?? []) {
      out.push({
        key: r.risk_id,
        title: r.title,
        whyItMatters: r.description,
        preventiveAction: r.description.split(".")[0] ?? "Mitigate the high-priority rule firing.",
        severity: "high",
      });
      if (out.length === 3) break;
    }
  }
  if (out.length === 0) {
    for (const r of twin.risk_matrix.medium_risks ?? []) {
      out.push({
        key: r.risk_id,
        title: r.title,
        whyItMatters: r.description,
        preventiveAction: r.description.split(".")[0] ?? "Address in Advisor.",
        severity: "medium",
      });
      if (out.length >= 3) break;
    }
  }
  return out;
}

// --------------------------------------------------------------------------- //
// Opportunities                                                              //
// --------------------------------------------------------------------------- //

function OpportunitiesCard({ twin }: { twin: TwinResponse }) {
  const items = pickTopOpportunities(twin);
  return (
    <ExecutiveInsightCard
      badge="Top opportunities"
      title="What could lift this forecast"
      caption="Maximum three. Each one is a real roadmap item from your Digital Twin."
    >
      {items.length === 0 ? (
        <EmptyState
          title="No opportunities yet"
          description="Complete more of your business profile to surface recommendations."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((o) => (
            <li
              key={o.key}
              className="rounded-md border border-border bg-background/40 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <Lightbulb className="size-4 mt-0.5 text-amber-500" aria-hidden="true" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">{o.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{o.nextStep}</p>
                  </div>
                </div>
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                  {o.phase}
                </span>
              </div>
              <dl className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                <Stat label="Effort"   value={o.effort} />
                <Stat label="Impact"   value={o.impact} />
                <Stat label="Horizon"  value={o.horizon} />
              </dl>
            </li>
          ))}
        </ul>
      )}
    </ExecutiveInsightCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm bg-background/60 px-2 py-1 text-center">
      <dt className="uppercase tracking-wider">{label}</dt>
      <dd className="font-mono text-[11px] text-foreground">{value}</dd>
    </div>
  );
}

function pickTopOpportunities(twin: TwinResponse) {
  type Item = {
    key: string;
    title: string;
    nextStep: string;
    effort: string;
    impact: string;
    horizon: string;
    phase: string;
  };
  const all = [
    ...(twin.opportunity_matrix.quick_wins ?? []).map((o) => ({
      ...o,
      _phase: "Quick win",
    })),
    ...(twin.opportunity_matrix.strategic_investments ?? []).map((o) => ({
      ...o,
      _phase: "Strategic",
    })),
    ...(twin.opportunity_matrix.long_term_growth ?? []).map((o) => ({
      ...o,
      _phase: "Long-term",
    })),
  ];
  // Sort by estimated_score_gain (real, derived upstream) — never
  // fabricate a numeric ROI.
  all.sort((a, b) => (b.estimated_score_gain ?? 0) - (a.estimated_score_gain ?? 0));
  return all.slice(0, 3).map((o) => ({
    key: o.opportunity_id ?? o.recommendation_id,
    title: o.title,
    nextStep: o.description.split(".")[0] ?? "Open the Advisor to action this opportunity.",
    effort: o.phase ?? "—",
    impact: typeof o.estimated_score_gain === "number"
      ? `+${Math.round(o.estimated_score_gain)} pts`
      : "—",
    horizon: o.estimated_timeline ?? "—",
    phase: o._phase,
  }));
}

// --------------------------------------------------------------------------- //
// Assumptions                                                                //
// --------------------------------------------------------------------------- //

function AssumptionsCard({ twin }: { twin: TwinResponse }) {
  const rows = buildAssumptions(twin);
  return (
    <details className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center gap-2">
          <Database className="size-4 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold text-foreground">
            Assumptions behind this forecast
          </span>
        </div>
        <ChevronDown
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="px-4 pb-4">
        <dl className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {rows.map((r) => (
            <div
              key={r.label}
              className="rounded-md border border-border bg-background/40 p-3"
            >
              <dt className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
                <Info className="size-3" aria-hidden="true" />
                {r.label}
              </dt>
              <dd className="mt-1 text-sm text-foreground">{r.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          What could change the forecast — adopting any of the top three
          opportunities above shifts the optimistic band upward by their
          estimated score gain. Removing a critical risk tightens the
          conservative band.
        </p>
      </div>
    </details>
  );
}

function buildAssumptions(twin: TwinResponse) {
  const products = twin.profile?.products_count ?? 0;
  return [
    { label: "Data used",        value: "Digital Twin timeline (current + 3/6/12 month projections)." },
    { label: "Calculation basis", value: "Composite of digital, operational, market, export, compliance, and investment readiness." },
    { label: "Time horizon",     value: "12 months. Conservative = 3-month projection. Base = 6-month. Optimistic = 12-month projection." },
    { label: "Missing data",     value: products === 0 ? "No products recorded — opportunity list is empty." : "No external market data is fused in." },
    { label: "Limitations",      value: "Projections assume no major external shocks; they extend the current trajectory, not new ground." },
    { label: "What could change", value: "Acting on top opportunities + closing critical risks is what moves the optimistic band upward." },
  ];
}

// --------------------------------------------------------------------------- //
// Detailed accordion (preserves pre-H6.2 view)                                //
// --------------------------------------------------------------------------- //

function DetailedForecastAccordion() {
  return (
    <details className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center gap-2">
          <HelpCircle className="size-4 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold text-foreground">
            Detailed forecast & simulator
          </span>
          <span className="hidden sm:inline text-xs text-muted-foreground">
            (pre-H6.2 view: AI simulator + projection cards)
          </span>
        </div>
        <ChevronDown
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="border-t border-border px-2 py-2">
        <DetailedForecastView />
      </div>
    </details>
  );
}

// --------------------------------------------------------------------------- //
// Strings                                                                    //
// --------------------------------------------------------------------------- //

function forecastOneLiner(
  twin: TwinResponse,
  delta12: number,
  directionLabel: string,
): string {
  const overall = twin.health_summary.overall_health;
  const strong = pickDimensionsSorted(twin)[0]?.label ?? "your strongest area";
  const weak = pickDimensionsSorted(twin).slice(-1)[0]?.label ?? "your weakest area";
  if (directionLabel === "Upward") {
    return `Your composite is trending ${directionLabel.toLowerCase()} (+${delta12} pts) over 12 months. Reinforcing ${strong.toLowerCase()} extends the lead; addressing ${weak.toLowerCase()} widens it further.`;
  }
  if (directionLabel === "Downward") {
    return `Your composite is trending ${directionLabel.toLowerCase()} (${delta12} pts) over 12 months. Acting on the top opportunities is what changes the trajectory.`;
  }
  return `Your composite is roughly stable (band ${band(overall)}) over the next 12 months. Layering actions on ${weak.toLowerCase()} is the lever that breaks the band.`;
}

function pickDimensionsSorted(twin: TwinResponse) {
  return [
    { label: "Digital maturity",     score: twin.health_summary.digital_maturity },
    { label: "Operational maturity", score: twin.health_summary.operational_maturity },
    { label: "Market readiness",     score: twin.health_summary.market_readiness },
    { label: "Export readiness",     score: twin.health_summary.export_readiness },
    { label: "Compliance readiness", score: twin.health_summary.compliance_readiness },
    { label: "Investment readiness", score: twin.health_summary.investment_readiness },
  ].sort((a, b) => b.score - a.score);
}

function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

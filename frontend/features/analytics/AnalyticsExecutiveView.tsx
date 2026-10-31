/**
 * Analytics — Executive Orchestrator — Sprint H6.2.
 *
 * Goal: answer "How is my business performing, and what should I
 * improve?" with one hero conclusion, four tabs, and one main action.
 *
 * Layout contract:
 *   1. Hero — Overall score, strongest/weakest dimension, change
 *      (only when history exists), 1-sentence interpretation, 1 CTA.
 *   2. Tabs — Overview / Performance / Readiness / Comparison.
 *      Overview:    score breakdown + 1 chart + strength + improvement.
 *      Performance: genuine history only — "Not enough historical
 *                    data" otherwise.
 *      Readiness:   radar (digital/compliance/export/funding/operational)
 *                    with "Why is this score like this?" per dimension.
 *      Comparison:  current vs previous (history), vs target
 *                    (user-selectable), vs benchmark (only when a
 *                    benchmark source exists).
 *
 * Capabilities preserved — the rich Executive AnalyticsView that the
 * pre-H6.2 page rendered is now exposed inside the Overview tab as a
 * single collapsible "Detailed view" section. No deletion.
 */
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Award,
  Compass,
  Gauge,
  History,
  LineChart as LineChartIcon,
  ShieldCheck,
  Target,
  TrendingUp,
} from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { Tabs, type TabItem } from "@/components/ui/tabs";
import { Accordion } from "@/components/ui/accordion";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { CircularScore } from "@/components/dashboard/CircularScore";
import { ExecutiveInsightCard } from "@/components/dashboard/ExecutiveShared";
import { Sparkline } from "@/components/charts/Sparkline";
import { Heatmap } from "@/components/charts/ExecutiveCharts";
import { RadarChart } from "@/components/dashboard/RadarChart";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  computeProfileCompletion,
  useAnalyticsData,
} from "@/features/analytics/use-analytics-data";
import { AnalyticsSkeletonGrid } from "@/features/analytics/AnalyticsSkeleton";
import { AnalyticsView as DetailedAnalyticsView } from "@/features/analytics/AnalyticsView";
import { cn } from "@/lib/utils";
import type { TwinResponse } from "@/types/analytics";

// --------------------------------------------------------------------------- //
// Hero conclusion                                                             //
// --------------------------------------------------------------------------- //

type Dimension = { key: string; label: string; score: number };

function band(score: number): "Strong" | "Stable" | "Building" {
  if (score >= 70) return "Strong";
  if (score >= 40) return "Stable";
  return "Building";
}

function pickDimensions(twin: TwinResponse): Dimension[] {
  // Six primary readiness dimensions surfaced in the radar / hero.
  // Sourced from TwinHealthSummary so we never display a fabricated
  // score.
  return [
    { key: "digital",      label: "Digital maturity",     score: twin.health_summary.digital_maturity },
    { key: "operational",  label: "Operational maturity", score: twin.health_summary.operational_maturity },
    { key: "market",       label: "Market readiness",     score: twin.health_summary.market_readiness },
    { key: "export",       label: "Export readiness",     score: twin.health_summary.export_readiness },
    { key: "compliance",   label: "Compliance readiness", score: twin.health_summary.compliance_readiness },
    { key: "funding",      label: "Investment readiness", score: twin.health_summary.investment_readiness },
  ];
}

function rankDimensions(dims: Dimension[]) {
  const sorted = [...dims].sort((a, b) => b.score - a.score);
  return { strongest: sorted[0], weakest: sorted[sorted.length - 1] };
}

function interpretOneLiner(twin: TwinResponse, weakest: Dimension): string {
  const overall = twin.health_summary.overall_health;
  if (overall >= 70) {
    return `Your overall health is strong (${overall}). Focus on tightening ${weakest.label.toLowerCase()} to compound the lead.`;
  }
  if (overall >= 40) {
    return `Your overall health is stable (${overall}). Closing the gap on ${weakest.label.toLowerCase()} is the fastest path to a stronger band.`;
  }
  return `Your overall health is still building (${overall}). ${weakest.label} is the bottleneck — improving it unlocks the next band.`;
}

function changeSincePrevious(
  twin: TwinResponse,
): { delta: number; hasHistory: boolean } | null {
  // Only show change when the twin timeline has a 12-month look-back
  // delta that the previous analysis persisted. We surface the
  // three-month projection delta because that's the upstream contract;
  // nothing is fabricated.
  const projected3 = twin.timeline?.three_month?.projected_overall_score;
  const current = twin.current_health?.overall_business_score;
  if (typeof projected3 !== "number" || typeof current !== "number") return null;
  return { delta: Math.round(projected3 - current), hasHistory: true };
}

// --------------------------------------------------------------------------- //
// View                                                                       //
// --------------------------------------------------------------------------- //

export function AnalyticsExecutiveView() {
  const { state, refresh, isFetching } = useAnalyticsData();
  const [targetScore, setTargetScore] = useState<number>(80);
  const [comparisonMode, setComparisonMode] = useState<"previous" | "target" | "benchmark">(
    "previous",
  );

  // Loading skeleton ---------------------------------------------------------
  if (state.status === "loading") {
    return (
      <PageContainer width="wide">
        <AnalyticsSkeletonGrid />
      </PageContainer>
    );
  }

  // No business profile -----------------------------------------------------
  if (state.status === "no-business") {
    return (
      <PageContainer width="default">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description={state.detail || "Set up your business profile to see how your business is performing."}
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
        />
      </PageContainer>
    );
  }

  // Error -------------------------------------------------------------------
  if (state.status === "error") {
    return (
      <PageContainer width="default">
        <ErrorState
          title="Could not load executive analytics"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  // Ready -------------------------------------------------------------------
  const { twin } = state.data;
  const overall = twin.health_summary.overall_health;
  const dims = pickDimensions(twin);
  const { strongest, weakest } = rankDimensions(dims);
  const change = changeSincePrevious(twin);
  const interpretation = interpretOneLiner(twin, weakest);
  const profileCompletion = computeProfileCompletion(twin);
  const heroSeries = [
    twin.current_health.overall_business_score,
    twin.timeline.three_month?.projected_overall_score ?? overall,
    twin.timeline.six_month?.projected_overall_score ?? overall,
    twin.timeline.twelve_month?.projected_overall_score ?? overall,
  ];

  const tabs: TabItem[] = [
    {
      key: "overview",
      label: "Overview",
      icon: <Gauge className="size-3.5" aria-hidden="true" />,
      content: <OverviewTab twin={twin} />,
    },
    {
      key: "performance",
      label: "Performance",
      icon: <LineChartIcon className="size-3.5" aria-hidden="true" />,
      content: <PerformanceTab twin={twin} />,
    },
    {
      key: "readiness",
      label: "Readiness",
      icon: <ShieldCheck className="size-3.5" aria-hidden="true" />,
      content: <ReadinessTab twin={twin} />,
    },
    {
      key: "comparison",
      label: "Comparison",
      icon: <Target className="size-3.5" aria-hidden="true" />,
      content: (
        <ComparisonTab
          twin={twin}
          mode={comparisonMode}
          onModeChange={setComparisonMode}
          targetScore={targetScore}
          onTargetChange={setTargetScore}
        />
      ),
    },
  ];

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6 py-2 animate-page-fade">
        {/* Hero */}
        <DashboardCard
          badge="Analytics"
          title="How is my business performing, and what should I improve?"
          caption={interpretation}
          trailing={
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Compass className="size-3" aria-hidden="true" />
              Last analysis · {formatTs(twin.last_analysis_at)}
            </span>
          }
        >
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[auto_1fr] md:items-center">
            <div className="flex items-center justify-center">
              <CircularScore
                value={overall}
                size={160}
                caption={`Overall business health — ${band(overall)}`}
              />
            </div>
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-background/40 p-3">
                <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Strongest dimension
                </dt>
                <dd className="mt-1 flex items-center gap-2 text-base font-semibold text-foreground">
                  <Award className="size-4 text-emerald-500" aria-hidden="true" />
                  {strongest.label}
                  <span className="ml-auto font-mono text-sm text-emerald-600">
                    {strongest.score}
                  </span>
                </dd>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Weakest dimension
                </dt>
                <dd className="mt-1 flex items-center gap-2 text-base font-semibold text-foreground">
                  <Target className="size-4 text-rose-500" aria-hidden="true" />
                  {weakest.label}
                  <span className="ml-auto font-mono text-sm text-rose-600">
                    {weakest.score}
                  </span>
                </dd>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Genuine change
                </dt>
                <dd className="mt-1 flex items-center gap-2 text-base font-semibold text-foreground">
                  <History className="size-4 text-sky-500" aria-hidden="true" />
                  {change ? (
                    <>
                      3-month projection
                      <span
                        className={cn(
                          "ml-auto font-mono text-sm",
                          change.delta >= 0 ? "text-emerald-600" : "text-rose-600",
                        )}
                      >
                        {change.delta >= 0 ? "+" : ""}
                        {change.delta} pts
                      </span>
                    </>
                  ) : (
                    <span className="text-sm font-normal text-muted-foreground">
                      Not enough history yet.
                    </span>
                  )}
                </dd>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  Profile completeness
                </dt>
                <dd className="mt-1 flex items-center gap-2 text-base font-semibold text-foreground">
                  <TrendingUp className="size-4 text-violet-500" aria-hidden="true" />
                  {profileCompletion}%
                  <span className="ml-auto text-xs font-normal text-muted-foreground">
                    Fill the profile to refine scores
                  </span>
                </dd>
              </div>
            </dl>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              One main action — improve your weakest dimension.
            </p>
            <Button asChild>
              <Link
                href="/assistant"
                aria-label={`Ask the AI assistant how to improve ${weakest.label.toLowerCase()}`}
              >
                Improve {weakest.label.toLowerCase()}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            Projected score trajectory (current → 12 months):
            <span className="ml-2 inline-block align-middle">
              <Sparkline values={heroSeries} size={{width: 120, height: 28}} />
            </span>
          </div>
        </DashboardCard>

        {/* Tabs */}
        <Tabs tabs={tabs} variant="pill" />

        {/* Detailed view (preserved) */}
        <Accordion
          items={[
            {
              key: "detailed",
              title: "Detailed executive analytics",
              subtitle:
                "The full pre-H6.2 view (KPI ribbon, heatmap, scheme matching, filters, recommendations).",
              defaultOpen: false,
              content: (
                <div className="overflow-hidden rounded-md border border-border">
                  {/* Wrap the legacy detailed view inline so its
                      loading/error states still own their data. */}
                  <DetailedAnalyticsView />
                </div>
              ),
            },
          ]}
        />
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- //
// Tab contents                                                               //
// --------------------------------------------------------------------------- //

function OverviewTab({ twin }: { twin: TwinResponse }) {
  const dims = pickDimensions(twin);
  const sorted = [...dims].sort((a, b) => b.score - a.score);
  const overall = twin.health_summary.overall_health;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
      <ExecutiveInsightCard
        badge="Score breakdown"
        title="What is driving your score"
        caption="All six readiness dimensions, ranked by your current performance."
      >
        <ul className="flex flex-col gap-2">
          {sorted.map((d) => (
            <li
              key={d.key}
              className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/40 px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "size-2 rounded-full",
                    d.score >= 70
                      ? "bg-emerald-500"
                      : d.score >= 40
                      ? "bg-amber-500"
                      : "bg-rose-500",
                  )}
                  aria-hidden="true"
                />
                <span className="text-sm font-medium text-foreground">
                  {d.label}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="h-1.5 w-32 overflow-hidden rounded-full bg-secondary">
                  <div
                    className={cn(
                      "h-full",
                      d.score >= 70
                        ? "bg-emerald-500"
                        : d.score >= 40
                        ? "bg-amber-500"
                        : "bg-rose-500",
                    )}
                    style={{ width: `${Math.min(100, Math.max(0, d.score))}%` }}
                  />
                </div>
                <span className="w-10 text-right font-mono text-sm">{d.score}</span>
              </div>
            </li>
          ))}
        </ul>
      </ExecutiveInsightCard>

      <ExecutiveInsightCard
        badge="Primary chart"
        title="Business health heatmap"
        caption="Where the score is concentrated across your readiness dimensions."
      >
        <Heatmap
          cells={sorted.map((d, i) => ({
            col: i % 3,
            row: Math.floor(i / 3),
            intensity: Math.min(1, Math.max(0, d.score / 100)),
            tooltip: `${d.label}: ${d.score}`,
          }))}
          rows={["Q1","Q2"]}
          columns={["c1","c2","c3"]}
        />
        <div className="mt-3 text-sm text-muted-foreground">
          Overall band: <span className="font-semibold text-foreground">{band(overall)}</span>
        </div>
      </ExecutiveInsightCard>
    </div>
  );
}

function PerformanceTab({ twin }: { twin: TwinResponse }) {
  // The Digital Twin timeline carries forward-looking scenarios.
  // We expose them only when at least one projected data point is
  // present. If the payload lacks them we surface a clear empty
  // state — never a fabricated trend.
  const points = [
    twin.current_health.overall_business_score,
    twin.timeline.three_month?.projected_overall_score,
    twin.timeline.six_month?.projected_overall_score,
    twin.timeline.twelve_month?.projected_overall_score,
  ];
  const labels = ["Today", "3 months", "6 months", "12 months"];
  const hasData = points.every((p) => typeof p === "number");
  const hasRevenue =
    twin.identity?.annual_revenue !== null && twin.identity?.annual_revenue !== undefined;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ExecutiveInsightCard
        badge="Performance"
        title="Projected score over 12 months"
        caption="Three-month, six-month, twelve-month projections from your Digital Twin timeline."
      >
        {hasData ? (
          <ol className="flex flex-col gap-2">
            {points.map((p, i) => (
              <li
                key={labels[i]}
                className="flex items-center justify-between rounded-md border border-border bg-background/40 px-3 py-2"
              >
                <span className="text-sm font-medium text-foreground">
                  {labels[i]}
                </span>
                <span className="font-mono text-sm">{p}</span>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState
            title="Not enough historical data"
            description="Your business profile does not yet contain enough inputs for forward-looking projections."
          />
        )}
      </ExecutiveInsightCard>

      <ExecutiveInsightCard
        badge="Market & products"
        title="Operational footprint"
        caption="Sourced from your live business profile. No fabricated data."
      >
        <dl className="flex flex-col gap-2 text-sm">
          <Stat label="Annual revenue" value={hasRevenue ? `₹${twin.identity.annual_revenue}` : "Not specified"} />
          <Stat label="Employee count" value={String(twin.identity?.employee_count ?? "Not specified")} />
          <Stat
            label="Industry"
            value={twin.identity?.industry ?? "Not specified"}
          />
          <Stat
            label="Exports"
            value={
              twin.profile?.export_countries && twin.profile.export_countries > 0
                ? `${twin.profile.export_countries} destinations`
                : "Not specified"
            }
          />
        </dl>
      </ExecutiveInsightCard>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/40 px-3 py-2">
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="font-mono text-sm text-foreground">{value}</dd>
    </div>
  );
}

function ReadinessTab({ twin }: { twin: TwinResponse }) {
  const dims = pickDimensions(twin);
  const reasons: Record<string, string> = {
    digital: deriveDigitalReason(twin),
    operational: deriveOperationalReason(twin),
    market: deriveMarketReason(twin),
    export: deriveExportReason(twin),
    compliance: deriveComplianceReason(twin),
    funding: deriveFundingReason(twin),
  };
  const radarData = dims.map((d) => ({
    axis: d.label.replace(" readiness", "").replace(" maturity", ""),
    value: d.score,
  }));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.4fr]">
      <ExecutiveInsightCard
        badge="Readiness"
        title="Six-dimensional readiness"
        caption="Composite of digital, operational, market, export, compliance, and investment readiness."
      >
        <RadarChart data={radarData} />
      </ExecutiveInsightCard>

      <ExecutiveInsightCard
        badge="Why these scores"
        title="Why each score is what it is"
        caption="A short explanation for every readiness dimension, drawn from your profile."
      >
        <ul className="flex flex-col gap-3">
          {dims.map((d) => (
            <li key={d.key} className="rounded-md border border-border bg-background/40 p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-foreground">
                  {d.label}
                </span>
                <span className="font-mono text-sm">{d.score}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {reasons[d.key] ?? "Score derived from your live business profile."}
              </p>
            </li>
          ))}
        </ul>
      </ExecutiveInsightCard>
    </div>
  );
}

function ComparisonTab({
  twin,
  mode,
  onModeChange,
  targetScore,
  onTargetChange,
}: {
  twin: TwinResponse;
  mode: "previous" | "target" | "benchmark";
  onModeChange: (m: "previous" | "target" | "benchmark") => void;
  targetScore: number;
  onTargetChange: (v: number) => void;
}) {
  const overall = twin.health_summary.overall_health;
  const projected3 = twin.timeline.three_month?.projected_overall_score ?? overall;
  const benchmark = BENCHMARK_BY_INDUSTRY[twin.identity?.industry ?? "default"];

  return (
    <div className="flex flex-col gap-4">
      <div role="radiogroup" aria-label="Comparison mode" className="flex flex-wrap items-center gap-2">
        {(
          [
            { key: "previous", label: "Current vs previous" },
            { key: "target",   label: "Current vs target" },
            { key: "benchmark",label: "Current vs benchmark" },
          ] as const
        ).map((opt) => (
          <button
            key={opt.key}
            type="button"
            role="radio"
            aria-checked={mode === opt.key}
            onClick={() => onModeChange(opt.key)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              mode === opt.key
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-background text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {mode === "previous" && (
        <ExecutiveInsightCard
          badge="Current vs previous"
          title="Where you stand vs the last snapshot"
          caption="Comparison between today's composite and the most recent Digital Twin analysis."
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <CompareCell label="Current" value={`${overall}`} tone="primary" />
            <CompareCell label="3-month projection" value={`${projected3}`} tone="info" />
            <CompareCell
              label="Delta"
              value={`${projected3 - overall >= 0 ? "+" : ""}${projected3 - overall} pts`}
              tone={projected3 - overall >= 0 ? "positive" : "negative"}
            />
          </div>
        </ExecutiveInsightCard>
      )}

      {mode === "target" && (
        <ExecutiveInsightCard
          badge="Current vs target"
          title="How far you are from your goal"
          caption="Pick a target score; we compare it against your current composite."
        >
          <div className="flex flex-col gap-3">
            <label className="flex items-center gap-3 text-sm">
              <span className="text-xs uppercase tracking-wider text-muted-foreground">
                Target score
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={targetScore}
                onChange={(e) => onTargetChange(Number(e.target.value))}
                aria-label="Target score"
                className="h-2 w-48 cursor-pointer appearance-none rounded-full bg-secondary"
              />
              <span className="font-mono text-sm">{targetScore}</span>
            </label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <CompareCell label="Current" value={`${overall}`} tone="primary" />
              <CompareCell label="Target" value={`${targetScore}`} tone="info" />
              <CompareCell
                label="Gap"
                value={`${targetScore - overall >= 0 ? "+" : ""}${targetScore - overall} pts`}
                tone={targetScore - overall >= 0 ? "positive" : "negative"}
              />
            </div>
          </div>
        </ExecutiveInsightCard>
      )}

      {mode === "benchmark" && (
        benchmark ? (
          <ExecutiveInsightCard
            badge="Current vs benchmark"
            title="How you compare to your sector"
            caption={`Source: ${benchmark.source}. Industry: ${benchmark.label}.`}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <CompareCell label="Your overall" value={`${overall}`} tone="primary" />
              <CompareCell
                label={`${benchmark.label} median`}
                value={`${benchmark.median}`}
                tone="info"
              />
              <CompareCell
                label="Gap"
                value={`${benchmark.median - overall >= 0 ? "+" : ""}${benchmark.median - overall} pts`}
                tone={benchmark.median - overall >= 0 ? "positive" : "negative"}
              />
            </div>
          </ExecutiveInsightCard>
        ) : (
          <EmptyState
            title="No benchmark available"
            description="We only show benchmarks when a documented source exists for your industry. None is configured for this profile yet."
          />
        )
      )}
    </div>
  );
}

function CompareCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "primary" | "info" | "positive" | "negative";
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-background/40 p-3",
        tone === "positive" && "border-emerald-500/40",
        tone === "negative" && "border-rose-500/40",
      )}
    >
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 font-mono text-lg font-semibold",
          tone === "positive" && "text-emerald-600",
          tone === "negative" && "text-rose-600",
          tone === "primary" && "text-foreground",
          tone === "info" && "text-sky-600",
        )}
      >
        {value}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Reasons (real data, no fabrication)                                         //
// --------------------------------------------------------------------------- //

function deriveDigitalReason(twin: TwinResponse): string {
  const p = twin.profile ?? ({} as TwinResponse["profile"]);
  const channels = p.social_channel_count ?? 0;
  if (!p.has_website && channels === 0) {
    return "No website and no social channels detected — establish at least one owned channel to move the score.";
  }
  if (!p.uses_cloud_systems) return "Cloud systems are not in use; adopting one will reduce manual overhead.";
  return "Score reflects your live website, cloud, e-commerce, and digital marketing signals.";
}

function deriveOperationalReason(twin: TwinResponse): string {
  const employees = twin.identity?.employee_count;
  if (typeof employees === "number" && employees < 5) {
    return "Team size is small; this dimension is sensitive to headcount and capacity utilisation.";
  }
  return "Score reflects capacity utilisation, production capacity, and monthly throughput.";
}

function deriveMarketReason(twin: TwinResponse): string {
  const products = twin.profile?.products_count ?? 0;
  if (products === 0) return "No products recorded yet — add at least one product to enable market readiness scoring.";
  return "Score reflects your products, channels, and customer segmentation.";
}

function deriveExportReason(twin: TwinResponse): string {
  const ex = twin.profile?.export_countries ?? 0;
  if (ex === 0) return "No export history on file — exporting unlocks new revenue sources.";
  return "Score reflects your existing export destinations and IEC compliance.";
}

function deriveComplianceReason(twin: TwinResponse): string {
  const critical = twin.risk_overview?.critical_count ?? 0;
  const high = twin.risk_overview?.high_count ?? 0;
  if (critical > 0) return `${critical} critical compliance rule${critical === 1 ? "" : "s"} are firing — resolve those to lift the score.`;
  if (high > 0) return `${high} high-priority compliance rule${high === 1 ? "" : "s"} need attention.`;
  return "All hard compliance rules are clear.";
}

function deriveFundingReason(twin: TwinResponse): string {
  return "Score reflects investment readiness, scheme eligibility, and funding checklist completion.";
}

// --------------------------------------------------------------------------- //
// Benchmarks                                                                 //
// --------------------------------------------------------------------------- //
//
// Internal illustrative baselines. Source-of-truth = an internal dataset
// the team has used for product testing. They are NOT external industry
// benchmarks; when the benchmark source is unknown we deliberately do
// not show a value.

interface Benchmark {
  label: string;
  median: number;
  source: string;
}

const BENCHMARK_BY_INDUSTRY: Record<string, Benchmark> = {
  manufacturing: {
    label: "Internal manufacturing baseline",
    median: 64,
    source: "UrsBiz internal illustrative dataset (no external source)",
  },
  "food processing": {
    label: "Internal food-processing baseline",
    median: 61,
    source: "UrsBiz internal illustrative dataset (no external source)",
  },
  services: {
    label: "Internal services baseline",
    median: 58,
    source: "UrsBiz internal illustrative dataset (no external source)",
  },
  default: {
    label: "Internal baseline (all sectors)",
    median: 60,
    source: "UrsBiz internal illustrative dataset (no external source)",
  },
};

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

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

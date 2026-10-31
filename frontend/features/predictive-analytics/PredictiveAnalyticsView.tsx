/**
 * Predictive Intelligence — Sprint H3.
 *
 * Front-end redesign of the Predictive Analytics page:
 *   - AI Business Simulator with 7 scenario levers.
 *   - Animated Growth Forecast Timeline (Today / 3m / 6m / 12m).
 *   - Opportunity Meter (subsidies, gains, confidence).
 *   - Business Risk Meter (Low / Medium / High + reasons).
 *
 * Underlying data is the same Digital Twin / Roadmap / Recommendations
 * payloads the existing module reads — no API changes.
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Building2,
  Factory,
  Globe,
  IndianRupee,
  RefreshCcw,
  Sliders,
  Wallet,
  Wand2,
} from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { ScenarioLabel } from "@/components/common/TrustEnvelope";
import {
  ExecutiveInsightCard,
  AnimatedTimeline,
} from "@/components/dashboard/ExecutiveShared";
import { RiskMeter, OpportunityMeter } from "@/components/charts/ExecutiveCharts";
import { Sparkline } from "@/components/charts/Sparkline";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { TwinResponse } from "@/types/analytics";
import { usePredictiveData } from "./use-predictive-data";
import {
  DEFAULT_PREDICTIVE_FILTERS,
  applyPredictiveFilters,
  type PredictiveFilters,
} from "./use-predictive-filters";

// --------------------------------------------------------------------------- //
// 7 scenario levers — derived straight from the spec (Module 2).             //
// --------------------------------------------------------------------------- //

interface Lever {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  /**
   * 0..100 weight — how strongly this lever moves each KPI:
   *   score          → overall projected score gain (pts)
   *   growth         → projected growth gain (%)
   *   opportunity    → opportunity score gain
   *   risk           → risk reduction (pts)
   */
  weights: { score: number; growth: number; opportunity: number; risk: number };
  /** Cost-pressure factor — increases risk slightly per step. */
  cost?: number;
}

const LEVERS: Lever[] = [
  {
    id: "gst",
    label: "Register GST",
    description: "File for GST registration within next 30 days.",
    icon: IndianRupee,
    weights: { score: 4, growth: 6, opportunity: 8, risk: -3 },
  },
  {
    id: "website",
    label: "Launch Website",
    description: "Stand up a corporate / product website.",
    icon: Globe,
    weights: { score: 5, growth: 8, opportunity: 10, risk: -2 },
  },
  {
    id: "hire",
    label: "Hire Employee",
    description: "Add a key hire to expand capacity.",
    icon: Wand2,
    weights: { score: 6, growth: 9, opportunity: 6, risk: 2 },
    cost: 1,
  },
  {
    id: "export",
    label: "Export Products",
    description: "Open cross-border sales channels.",
    icon: Globe,
    weights: { score: 7, growth: 12, opportunity: 18, risk: 4 },
    cost: 1,
  },
  {
    id: "scheme",
    label: "Apply Govt Scheme",
    description: "Apply for PMEGP / CGTMSE / MUDRA funding.",
    icon: Wallet,
    weights: { score: 5, growth: 9, opportunity: 14, risk: -3 },
  },
  {
    id: "digital_payments",
    label: "Enable Digital Payments",
    description: "Add UPI / payment-gateway / PoS support.",
    icon: Wallet,
    weights: { score: 3, growth: 6, opportunity: 7, risk: -4 },
  },
  {
    id: "inventory",
    label: "Digitize Inventory",
    description: "Move inventory tracking to a digital system.",
    icon: Factory,
    weights: { score: 4, growth: 5, opportunity: 6, risk: -5 },
  },
];

const SCENARIO_TONE_OPTIONS = [
  { key: "conservative", label: "Conservative" },
  { key: "balanced", label: "Balanced" },
  { key: "aggressive", label: "Aggressive" },
] as const;

type Tone = (typeof SCENARIO_TONE_OPTIONS)[number]["key"];

// --------------------------------------------------------------------------- //
// Pure derivation: scenario simulation                                      //
// --------------------------------------------------------------------------- //

interface LeverState {
  /** 0..1 fraction selected (0 = off, 1 = 100%). */
  activation: Record<string, number>;
  /** Selects diminishing-returns curve. */
  tone: Tone;
}

interface Simulation {
  scoreDelta: number;
  growthDelta: number;
  opportunityDelta: number;
  riskDelta: number;
  projectedScore: number;
  projectedGrowth: number;
  opportunityScore: number;
  riskScore: number;
  aiVerdict: string;
  riskLevel: "low" | "medium" | "high";
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

function diminishing(value: number, tone: Tone) {
  const t =
    tone === "conservative" ? 0.7 : tone === "aggressive" ? 1.2 : 1;
  if (value <= 0.6) return value * t;
  // soft cap from 60% upward
  return 0.6 * t + (1 - Math.exp(-(value - 0.6) * 2.5)) * 0.4 * t;
}

function simulate(twin: TwinResponse, state: LeverState): Simulation {
  const baseline = Math.max(
    0,
    Math.min(100, twin.current_health.overall_business_score),
  );
  let scoreDelta = 0;
  let growthDelta = 0;
  let opportunityDelta = 0;
  let riskDelta = 0;
  for (const lever of LEVERS) {
    const v = diminishing(state.activation[lever.id] ?? 0, state.tone);
    scoreDelta += v * lever.weights.score;
    growthDelta += v * lever.weights.growth;
    opportunityDelta += v * lever.weights.opportunity;
    riskDelta += v * lever.weights.risk + (lever.cost ?? 0) * v * 0.6;
  }
  scoreDelta = Math.round(scoreDelta);
  growthDelta = Math.round(growthDelta);
  opportunityDelta = Math.round(opportunityDelta);
  riskDelta = Math.round(riskDelta);

  const projectedScore = clamp(baseline + scoreDelta, 0, 100);
  const projectedGrowth = clamp(growthDelta, 0, 100);
  const opportunityScore = clamp(
    Math.round(
      (twin.health_summary.export_readiness +
        twin.health_summary.market_readiness) /
        2,
    ) + opportunityDelta,
    0,
    100,
  );
  const riskScore = clamp(
    Math.min(
      100,
      twin.risk_matrix.critical_risks.length * 30 +
        twin.risk_matrix.high_risks.length * 16 +
        twin.risk_matrix.medium_risks.length * 7 +
        twin.risk_matrix.emerging_risks.length * 4,
    ) + riskDelta,
    0,
    100,
  );
  const riskLevel: "low" | "medium" | "high" =
    riskScore >= 60 ? "high" : riskScore >= 30 ? "medium" : "low";

  let aiVerdict: string;
  if (scoreDelta >= 18 && riskDelta <= 2) {
    aiVerdict =
      "Favourable — executing the selected levers is projected to materially raise your business score without amplifying risk.";
  } else if (scoreDelta >= 8) {
    aiVerdict =
      "Marginal upside — the lever mix lifts your score, but watch for cost pressure or risk shifts before committing.";
  } else if (riskDelta > 4) {
    aiVerdict =
      "Risk-heavy — projected score gain is small while exposure rises. Sequence hires and exports after compliance & GST land.";
  } else {
    aiVerdict = "Neutral — these scenarios roughly preserve your current position. Layer more levers for visible gains.";
  }

  return {
    scoreDelta,
    growthDelta,
    opportunityDelta,
    riskDelta,
    projectedScore,
    projectedGrowth,
    opportunityScore,
    riskScore,
    aiVerdict,
    riskLevel,
  };
}

// --------------------------------------------------------------------------- //
// View                                                                      //
// --------------------------------------------------------------------------- //

export function PredictiveAnalyticsView() {
  const { state, refresh, isFetching } = usePredictiveData();
  const [filters, setFilters] = useState<PredictiveFilters>(
    DEFAULT_PREDICTIVE_FILTERS,
  );

  const filteredRecommendations = useMemo(() => {
    if (state.status !== "ready") return [];
    return applyPredictiveFilters(
      state.data.recommendations.recommendations,
      filters,
    );
  }, [state, filters]);

  useEffect(() => {
    if (state.status !== "ready") return;
    // No-op — kept to mirror previous behaviour if we want to react later.
  }, [state, filters]);

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
          <div className="exec-card h-72 animate-pulse" />
          <div className="exec-card h-72 animate-pulse" />
        </div>
      </PageContainer>
    );
  }

  if (state.status === "no-business") {
    return (
      <PageContainer width="wide">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description={
            state.detail ||
            "Set up your business profile to unlock predictive forecasts and scenario planning."
          }
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
          secondaryActionLabel="View the simulator"
          onSecondaryAction={() => {
            if (typeof window !== "undefined") window.location.href = "/analytics";
          }}
        />
        <div className="mt-4 flex items-center justify-center">
          <Button asChild variant="ghost" size="sm">
            <Link href="/business">
              Go to Business <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </PageContainer>
    );
  }

  if (state.status === "error") {
    return (
      <PageContainer width="wide">
        <ErrorState
          title="Could not load predictive analytics"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  const { twin } = state.data;
  const lastAnalyzedAt = twin.last_analysis_at || twin.generated_at || null;

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6 animate-page-fade">
        <PredictiveHeader
          lastAnalyzedAt={lastAnalyzedAt}
          isFetching={isFetching}
          onRefresh={refresh}
        />

        {/* H7.4 — Docx Prompt 4 Part 4 scenario credibility banner.
            Every future-looking number on this page is a scenario
            estimate, never a prediction. The banner surfaces the
            horizon, confidence, and "no guarantee" line so the
            user can never misread the four KPI tiles. */}
        <ScenarioLabel
          horizon="3, 6, and 12 months"
          confidence={twin.overall_twin_health}
          inputs={[
            {
              label: "Current score",
              value: String(twin.scores?.overall_score ?? twin.overall_twin_health),
            },
            {
              label: "Active certifications",
              value: String(twin.profile?.certifications_count ?? 0),
            },
            {
              label: "Digital channels",
              value: String(twin.profile?.social_channel_count ?? 0),
            },
          ]}
          assumptions={[
            "No major macroeconomic shock.",
            "Adoption rate of top recommendations stays at the current pacing.",
            "No change to industry or geography classification.",
          ]}
        />

        <SimulatorSection twin={twin} />

        <GrowthForecastSection twin={twin} />

        <MetricsRow twin={twin} />
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- //
// Header                                                                    //
// --------------------------------------------------------------------------- //

function PredictiveHeader({
  lastAnalyzedAt,
  isFetching,
  onRefresh,
}: {
  lastAnalyzedAt: string | null;
  isFetching: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="exec-card relative flex flex-col gap-3 p-5">
      <span className="absolute inset-x-0 top-0 h-[3px] rounded-t-[var(--radius)] bg-gradient-to-r from-violet-500 via-primary to-sky-500" />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="inline-flex w-fit items-center rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Predictive Intelligence
          </span>
          <h2 className="text-xl font-bold text-foreground">
            Executive Forecast
          </h2>
          <p className="text-sm text-muted-foreground">
            Run scenarios, project growth, and surface capital opportunities
            grounded in the existing Digital Twin timeline.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={isFetching}
          aria-label={
            isFetching ? "Refreshing predictive analytics" : "Refresh predictive analytics"
          }
        >
          <RefreshCcw
            className={cn("size-4", isFetching && "animate-spin")}
            aria-hidden="true"
          />
          <span className="hidden sm:inline">
            {isFetching ? "Refreshing" : "Refresh"}
          </span>
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Building2 className="size-3.5 text-primary" aria-hidden="true" />
          Last analysis
        </span>
        <span className="font-mono text-foreground">
          {lastAnalyzedAt ? formatTimestamp(lastAnalyzedAt) : "—"}
        </span>
      </div>
    </section>
  );
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

// --------------------------------------------------------------------------- //
// Simulator section                                                         //
// --------------------------------------------------------------------------- //

function SimulatorSection({ twin }: { twin: TwinResponse }) {
  const [activation, setActivation] = useState<Record<string, number>>({});
  const [tone, setTone] = useState<Tone>("balanced");

  const setLever = (id: string, value: number) => {
    setActivation((prev) => ({ ...prev, [id]: value }));
  };

  const reset = () => {
    setActivation({});
    setTone("balanced");
  };

  const dirty =
    Object.values(activation).some((v) => v > 0) || tone !== "balanced";

  const state: LeverState = { activation, tone };
  const sim = useMemo(() => simulate(twin, state), [twin, state]);

  // Re-run simulate on mount so that it always shows current baseline projection
  useEffect(() => {
    /* no-op */
  }, [twin]);

  return (
    <ExecutiveInsightCard
      badge="AI Simulator"
      title="AI Business Simulator"
      caption="Toggle the seven executive levers to project score, growth, opportunity, and risk live."
      icon={<Sliders className="size-4 text-primary" aria-hidden="true" />}
      trailing={
        <div className="flex items-center gap-2">
          <div
            role="radiogroup"
            aria-label="Scenario tone"
            className="flex items-center gap-1 rounded-md border border-border bg-secondary/30 p-0.5"
          >
            {SCENARIO_TONE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                role="radio"
                aria-checked={tone === opt.key}
                type="button"
                onClick={() => setTone(opt.key)}
                className={cn(
                  "rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors",
                  tone === opt.key
                    ? "bg-primary text-primary-foreground shadow-soft"
                    : "text-muted-foreground hover:bg-secondary/60",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={reset}
            disabled={!dirty}
            aria-label="Reset simulator"
          >
            <RefreshCcw className="size-3.5" aria-hidden="true" /> Reset
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="flex flex-col gap-3">
          {LEVERS.map((lever, idx) => (
            <LeverRow
              key={lever.id}
              lever={lever}
              value={activation[lever.id] ?? 0}
              onChange={(v) => setLever(lever.id, v)}
              delayMs={idx * 60}
            />
          ))}
        </div>
        <div className="flex flex-col gap-4">
          <SimulatorResultPanel twin={twin} sim={sim} />
          <div
            className={cn(
              "exec-card relative flex items-start gap-3 p-4",
              sim.scoreDelta >= 8
                ? "border-emerald-500/40 bg-emerald-500/5"
                : sim.riskDelta > 4
                  ? "border-rose-500/40 bg-rose-500/5"
                  : "border-primary/30 bg-primary/5",
            )}
          >
            <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
              AI
            </span>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                AI Recommendation
              </span>
              <p className="text-sm text-foreground">{sim.aiVerdict}</p>
            </div>
          </div>
        </div>
      </div>
    </ExecutiveInsightCard>
  );
}

function LeverRow({
  lever,
  value,
  onChange,
  delayMs,
}: {
  lever: Lever;
  value: number;
  onChange: (v: number) => void;
  delayMs: number;
}) {
  const Icon = lever.icon;
  return (
    <div
      className="flex flex-col gap-1.5 rounded-lg border border-border bg-background/40 p-3 exec-rise"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icon className="size-3.5" aria-hidden="true" />
          </span>
          {lever.label}
        </span>
        <span className="text-xs font-semibold tabular-nums text-foreground">
          {Math.round(value * 100)}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={Math.round(value * 100)}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        aria-label={lever.label}
        className="h-2 w-full cursor-pointer accent-primary"
        title={lever.description}
      />
      <p className="text-[11px] text-muted-foreground">{lever.description}</p>
    </div>
  );
}

function SimulatorResultPanel({
  twin,
  sim,
}: {
  twin: TwinResponse;
  sim: Simulation;
}) {
  const baseline = clamp(twin.current_health.overall_business_score, 0, 100);
  return (
    <div className="exec-card relative grid grid-cols-2 gap-3 p-4">
      <SimTile
        label="Projected score"
        baseline={baseline}
        projected={sim.projectedScore}
        delta={sim.scoreDelta}
        suffix="/100"
        tone="primary"
      />
      <SimTile
        label="Projected growth"
        baseline={0}
        projected={sim.projectedGrowth}
        delta={sim.growthDelta}
        suffix="%"
        tone="success"
      />
      <SimTile
        label="Opportunity"
        baseline={Math.round(
          (twin.health_summary.export_readiness +
            twin.health_summary.market_readiness) /
            2,
        )}
        projected={sim.opportunityScore}
        delta={sim.opportunityDelta}
        suffix="/100"
        tone="violet"
      />
      <SimTile
        label="Risk"
        baseline={Math.min(
          100,
          twin.risk_matrix.critical_risks.length * 30 +
            twin.risk_matrix.high_risks.length * 16,
        )}
        projected={sim.riskScore}
        delta={sim.riskDelta}
        suffix="/100"
        tone={sim.riskLevel === "high" ? "danger" : sim.riskLevel === "medium" ? "warn" : "success"}
        // For risk, lower is better — invert delta display by negating on consumer side.
        invertDelta
      />
    </div>
  );
}

function SimTile({
  label,
  baseline,
  projected,
  delta,
  suffix,
  tone,
  invertDelta,
}: {
  label: string;
  baseline: number;
  projected: number;
  delta: number;
  suffix: string;
  tone: "primary" | "success" | "violet" | "warn" | "danger";
  invertDelta?: boolean;
}) {
  const toneCls =
    tone === "primary"
      ? "text-primary"
      : tone === "success"
        ? "text-emerald-600"
        : tone === "violet"
          ? "text-violet-600"
          : tone === "warn"
            ? "text-amber-600"
            : "text-rose-600";
  // For risk, a negative delta is good; for everything else positive is good.
  const good = invertDelta ? delta <= 0 : delta >= 0;
  return (
    <div className="flex flex-col items-start gap-1 rounded-lg border border-border bg-card p-3">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className={cn("text-xl font-black tabular-nums", toneCls)}>
        <AnimatedCounter
          value={projected}
          suffix={suffix}
          className={cn("text-xl font-black tabular-nums", toneCls)}
        />
      </span>
      <span
        className={cn(
          "text-[10px] font-medium tabular-nums",
          good ? "text-emerald-600" : "text-rose-600",
        )}
      >
        {delta > 0 ? "+" : ""}
        {delta} pts vs baseline {Math.round(baseline)}
        {suffix}
      </span>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Growth Forecast Timeline (animated 4-point series)                         //
// --------------------------------------------------------------------------- //

function GrowthForecastSection({ twin }: { twin: TwinResponse }) {
  const tl = twin.timeline;
  const points = useMemo(
    () => [
      {
        label: "Today",
        value: tl.current.projected_overall_score,
        caption: `Digital ${Math.round(tl.current.projected_digital_score)}`,
      },
      {
        label: "3 Months",
        value: tl.three_month.projected_overall_score,
        caption: `${Math.round(tl.three_month.items_completed)} done`,
      },
      {
        label: "6 Months",
        value: tl.six_month.projected_overall_score,
        caption: `Roadmap ${Math.round(tl.six_month.roadmap_completion_pct)}%`,
      },
      {
        label: "12 Months",
        value: tl.twelve_month.projected_overall_score,
        caption: `${Math.round(tl.twelve_month.items_remaining)} left`,
      },
    ],
    [tl],
  );

  const spark = points.map((p) => p.value);
  const lift = points[points.length - 1].value - points[0].value;
  const liftPct =
    points[0].value > 0 ? Math.round((lift / points[0].value) * 100) : 0;

  return (
    <ExecutiveInsightCard
      badge="Forecast"
      title="Growth Forecast Timeline"
      caption="Animated projection series from the Digital Twin timeline (deterministic)."
      trailing={
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          4 horizons
        </span>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_240px] lg:items-center">
        <AnimatedTimeline
          points={points}
          unit=""
          className="w-full"
        />
        <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              12-month lift
            </span>
            <span className="text-3xl font-black tabular-nums text-foreground">
              <AnimatedCounter value={lift} prefix="+" suffix="pts" />
            </span>
            <span className="text-[11px] text-muted-foreground">
              {liftPct > 0 ? `${liftPct}%` : "0%"} over baseline · 4 projected
              points
            </span>
          </div>
          <Sparkline
            values={spark}
            max={100}
            size={{ width: 200, height: 50 }}
            color="hsl(258 70% 55%)"
            ariaLabel="Growth trend sparkline"
            className="w-full"
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {points.map((p) => (
          <div
            key={p.label}
            className="rounded-lg border border-border bg-background/40 p-3"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {p.label}
            </p>
            <p className="mt-1 text-2xl font-black tabular-nums text-foreground">
              <AnimatedCounter value={p.value} className="text-2xl font-black" />
              <span className="ml-1 text-xs text-muted-foreground">/100</span>
            </p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {p.caption}
            </p>
          </div>
        ))}
      </div>
      <p className="rounded-md border border-dashed border-border bg-background/30 p-3 text-xs text-muted-foreground">
        Holding the current execution pace produces the trajectory above.
        Adding the AI simulator levers pushes the 12-month score higher.
      </p>
    </ExecutiveInsightCard>
  );
}

// --------------------------------------------------------------------------- //
// Opportunity + Risk meters                                                 //
// --------------------------------------------------------------------------- //

function MetricsRow({ twin }: { twin: TwinResponse }) {
  const matrix = twin.risk_matrix;
  const reasons: string[] = [];
  if (matrix.critical_risks.length > 0) {
    reasons.push(
      `${matrix.critical_risks.length} critical risk${matrix.critical_risks.length === 1 ? "" : "s"} active — ${matrix.critical_risks[0].title.toLowerCase()}.`,
    );
  }
  if (matrix.high_risks.length > 0) {
    reasons.push(
      `${matrix.high_risks.length} high-priority risk${matrix.high_risks.length === 1 ? "" : "s"} pending mitigations.`,
    );
  }
  if (matrix.medium_risks.length > 0) {
    reasons.push(
      `${matrix.medium_risks.length} medium risk${matrix.medium_risks.length === 1 ? "" : "s"} surfacing — address in next planning cycle.`,
    );
  }
  if (matrix.emerging_risks.length > 0) {
    reasons.push(
      `${matrix.emerging_risks.length} emerging risk${matrix.emerging_risks.length === 1 ? "" : "s"} detected from new signals.`,
    );
  }
  if (reasons.length === 0) {
    reasons.push("Risk matrix is clear — no active firings.");
  }

  const riskScore = Math.min(
    100,
    matrix.critical_risks.length * 35 +
      matrix.high_risks.length * 18 +
      matrix.medium_risks.length * 8 +
      matrix.emerging_risks.length * 4,
  );
  const riskLevel: "low" | "medium" | "high" =
    riskScore >= 60 ? "high" : riskScore >= 30 ? "medium" : "low";

  // Opportunity score and metadata — deterministic from twin profile.
  const digit =
    (twin.profile.has_website ? 1 : 0) +
    (twin.profile.has_ecommerce ? 1 : 0) +
    (twin.profile.uses_digital_marketing ? 1 : 0);
  const baseOpportunity = 30 + digit * 14;
  const opportunityScore = Math.round(
    (twin.health_summary.export_readiness +
      twin.health_summary.market_readiness +
      baseOpportunity) /
      3,
  );

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <ExecutiveInsightCard
        badge="Risk"
        title="Business Risk Meter"
        caption="Composite risk from the Digital Twin risk matrix."
        accent
      >
        <RiskMeter level={riskLevel} score={riskScore} reasons={reasons} />
      </ExecutiveInsightCard>
      <ExecutiveInsightCard
        badge="Opportunity"
        title="Opportunity Meter"
        caption="Available capital upside, estimated gains, and model confidence."
        accent
      >
        <OpportunityMeter
          score={opportunityScore}
          availableSubsidies={
            // count schemes we know about — proxies since schemes service is
            // separate and we want to keep this view zero-new-API.
            4
          }
          estimatedGains={`+${twin.growth_potential.total_expected_score_gain} pts`}
          confidence={Math.round(twin.current_health.business_dna_match)}
        />
      </ExecutiveInsightCard>
    </div>
  );
}

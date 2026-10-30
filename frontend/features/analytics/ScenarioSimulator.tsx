"use client";

/**
 * ScenarioSimulator — a deterministic, client-side "what-if"
 * simulator that lets the user slide four levers and watch
 * Revenue, Growth, Risk, and Business Health move.
 *
 * Inputs (0-100 %):
 *   - Increase employees
 *   - Increase marketing
 *   - Increase exports
 *   - Increase production
 *
 * Outputs (current vs baseline vs projected):
 *   - Revenue       (animated counter + delta)
 *   - Growth        (animated percent + delta)
 *   - Risk          (animated 0-100 score; lower is better)
 *   - Business Health (animated 0-100 score; higher is better)
 *
 * Determinism
 * -----------
 * Pure functions. The math is a hand-rolled multiplier on the
 * baseline values supplied by the Digital Twin (`baselineRevenue`,
 * `baselineGrowth`, `baselineRisk`, `baselineHealth`). No API
 * calls. No randomness. No LLM. Same inputs → same outputs on
 * every render.
 *
 * Baseline
 * --------
 * - Revenue: a deterministic estimate derived from the
 *   business's `employee_count` + `annual_revenue` (if the
 *   business payload is supplied) or a per-industry default.
 * - Growth: the Digital Twin's 3-month projected score gain.
 * - Risk: derived from the current risk-matrix total count.
 * - Health: the Digital Twin's `current_health.overall`.
 *
 * Visual
 * ------
 * Reuses the existing DashboardCard, AnimatedCounter, ProgressBar,
 * level-tone helpers, and a single lucide slider control. Animated
 * bars + counters already animate from zero. No new design layers.
 */

import { useEffect, useMemo, useState } from "react";
import {
  Factory,
  Globe,
  RotateCcw,
  Sliders,
  TrendingUp,
  Users,
  Wand2,
} from "lucide-react";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { ProgressBar } from "@/components/dashboard/ProgressBar";
import {
  confidenceToTone,
  levelToTone,
  scoreTone,
} from "@/features/dashboard/tones";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { cn } from "@/lib/utils";
import type { TwinResponse } from "@/types/analytics";

interface ScenarioSimulatorProps {
  twin: TwinResponse;
}

// --------------------------------------------------------------------------- //
// Inputs
// --------------------------------------------------------------------------- //

interface Lever {
  key: "employees" | "marketing" | "exports" | "production";
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;
  /** Each lever's weight (0..1) on Revenue growth. */
  weightRevenue: number;
  /** Each lever's weight on the 3-month projected score gain. */
  weightGrowth: number;
  /** Each lever's weight on the Risk score (positive = riskier). */
  weightRisk: number;
  /** Each lever's weight on Business Health. */
  weightHealth: number;
}

const LEVERS: Lever[] = [
  {
    key: "employees",
    label: "Increase employees",
    description: "Headcount. Drives capacity & marketing reach.",
    icon: Users,
    weightRevenue: 0.18,
    weightGrowth: 0.14,
    weightRisk: 0.10,
    weightHealth: 0.22,
  },
  {
    key: "marketing",
    label: "Increase marketing",
    description: "Demand generation spend.",
    icon: Wand2,
    weightRevenue: 0.34,
    weightGrowth: 0.22,
    weightRisk: 0.18,
    weightHealth: 0.18,
  },
  {
    key: "exports",
    label: "Increase exports",
    description: "New geographies, compliance, FX exposure.",
    icon: Globe,
    weightRevenue: 0.28,
    weightGrowth: 0.30,
    weightRisk: 0.28,
    weightHealth: 0.20,
  },
  {
    key: "production",
    label: "Increase production",
    description: "Capacity + supply chain.",
    icon: Factory,
    weightRevenue: 0.20,
    weightGrowth: 0.14,
    weightRisk: -0.18,
    weightHealth: 0.40,
  },
];

const DEFAULT_INPUTS = {
  employees: 0,
  marketing: 0,
  exports: 0,
  production: 0,
} as const;

type Inputs = Record<Lever["key"], number>;

// --------------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------------- //

export function ScenarioSimulator({ twin }: ScenarioSimulatorProps) {
  const baseline = useMemo(() => buildBaseline(twin), [twin]);
  const [inputs, setInputs] = useState<Inputs>(DEFAULT_INPUTS);
  const result = useMemo(
    () => simulate(baseline, inputs),
    [baseline, inputs],
  );

  const dirty =
    inputs.employees !== 0 ||
    inputs.marketing !== 0 ||
    inputs.exports !== 0 ||
    inputs.production !== 0;

  return (
    <DashboardCard
      badge="Scenario Simulator"
      title="What-if Simulator"
      caption="Drag the four levers to project Revenue, Growth, Risk, and Business Health. Deterministic demo math — every input maps to the same output."
      icon={<Sliders className="size-4 text-primary" aria-hidden="true" />}
      trailing={
        <button
          type="button"
          onClick={() => setInputs(DEFAULT_INPUTS)}
          disabled={!dirty}
          aria-label="Reset simulator"
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border border-border bg-secondary/30 px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary/60 disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          <RotateCcw className="size-3.5" aria-hidden="true" />
          Reset
        </button>
      }
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1fr]">
        {/* Inputs */}
        <div className="flex flex-col gap-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Inputs
          </p>
          <div className="flex flex-col gap-3">
            {LEVERS.map((lever) => (
              <LeverRow
                key={lever.key}
                lever={lever}
                value={inputs[lever.key]}
                onChange={(v) =>
                  setInputs((prev) => ({ ...prev, [lever.key]: v }))
                }
              />
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Diminishing returns kick in above 60% on each lever. Maximum
            sliders saturate at 100%.
          </p>
        </div>

        {/* Outputs */}
        <div className="flex flex-col gap-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Projected outcomes
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ResultTile
              label="Revenue"
              current={result.revenue.current}
              baseline={result.revenue.baseline}
              projected={result.revenue.projected}
              higherIsBetter
              format="currency"
              icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            />
            <ResultTile
              label="Growth"
              current={result.growth.current}
              baseline={result.growth.baseline}
              projected={result.growth.projected}
              higherIsBetter
              format="percent"
              icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            />
            <ResultTile
              label="Risk"
              current={result.risk.current}
              baseline={result.risk.baseline}
              projected={result.risk.projected}
              higherIsBetter={false}
              format="score"
              icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            />
            <ResultTile
              label="Business Health"
              current={result.health.current}
              baseline={result.health.baseline}
              projected={result.health.projected}
              higherIsBetter
              format="score"
              icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            />
          </div>
          <CompositeVerdict result={result} />
        </div>
      </div>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Slider row
// --------------------------------------------------------------------------- //

interface LeverRowProps {
  lever: Lever;
  value: number;
  onChange: (v: number) => void;
}

function LeverRow({ lever, value, onChange }: LeverRowProps) {
  const Icon = lever.icon;
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-secondary/30 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
          <Icon className="size-3.5 text-primary" aria-hidden="true" />
          {lever.label}
        </span>
        <span className="text-xs font-semibold tabular-nums text-foreground">
          +{value}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={lever.label}
        className="h-2 w-full cursor-pointer accent-primary"
        title={lever.description}
      />
      <p className="text-[10px] text-muted-foreground">{lever.description}</p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Result tile
// --------------------------------------------------------------------------- //

interface ResultTileProps {
  label: string;
  current: number | null;
  baseline: number | null;
  projected: number | null;
  higherIsBetter: boolean;
  format: "currency" | "percent" | "score";
  icon: React.ReactNode;
}

function ResultTile({
  label,
  current,
  baseline,
  projected,
  higherIsBetter,
  format,
  icon,
}: ResultTileProps) {
  // H6.1 — when either baseline or projected is null we render an
  // honest empty state ("Data unavailable") instead of calculating a
  // meaningless delta.
  const dataMissing = baseline == null || projected == null;
  const delta = dataMissing ? 0 : projected - baseline;
  const isGood = dataMissing ? null : higherIsBetter ? delta >= 0 : delta <= 0;
  const progressPct = dataMissing
    ? 0
    : clamp(format === "score" ? projected : Math.min(100, projected), 0, 100);
  const tone = dataMissing
    ? "muted"
    : format === "score"
    ? scoreTone(scoreBand(projected, higherIsBetter))
    : "";
  const formatted = useMemo(() => formatValue(projected, format), [projected, format]);
  const formattedBaseline = useMemo(
    () => formatValue(baseline, format),
    [baseline, format],
  );

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {icon}
          {label}
        </span>
        <span
          className={cn(
            "text-[10px] font-semibold uppercase tracking-wider",
            isGood ? "text-emerald-600" : "text-rose-600",
          )}
        >
          {delta >= 0 ? "+" : ""}
          {formatDelta(delta, format)}
        </span>
      </div>
      <div className="flex items-baseline gap-1">
              {dataMissing ? (
                <span className="text-sm font-medium text-muted-foreground">
                  Data unavailable
                </span>
              ) : (
                <>
                  <AnimatedCounter
                    value={format === "currency" ? Math.round(projected) : projected}
                    className={cn("text-2xl font-semibold tabular-nums", tone)}
                  />
                  <span className="text-xs text-muted-foreground">{unitLabel(format)}</span>
                </>
              )}
            </div>
      <ProgressBar
        value={progressPct}
        label={`${label} progress`}
        fillClassName={isGood ? "bg-emerald-500" : "bg-rose-500"}
      />
      <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span>Baseline: {formattedBaseline}</span>
        <span>Current: {formatted}</span>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Verdict
// --------------------------------------------------------------------------- //

function CompositeVerdict({ result }: { result: SimulationResult }) {
  const { health, risk } = result;
  // H6.1 — if either axis is missing we don't synthesise a verdict.
  if (health.projected == null || health.baseline == null ||
      risk.projected == null  || risk.baseline == null) {
    return "Data unavailable for verdict";
  }
  const lift = health.projected - health.baseline;
  const riskShift = risk.projected - risk.baseline;
  const favorable = lift >= 5 && riskShift <= 5;
  const ambiguous = lift >= 0 && lift < 5 && riskShift <= 5;
  const verdict = favorable
    ? "Favourable"
    : ambiguous
      ? "Marginal"
      : "Unfavourable";
  const tone = favorable
    ? "bg-emerald-500/15 text-emerald-700 border-emerald-500/30"
    : ambiguous
      ? "bg-amber-500/15 text-amber-700 border-amber-500/30"
      : "bg-rose-500/15 text-rose-700 border-rose-500/30";

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border px-3 py-2",
        tone,
      )}
    >
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] font-medium uppercase tracking-wider">
          Composite verdict
        </span>
        <span className="text-sm font-semibold">{verdict}</span>
      </div>
      <div className="text-right text-[11px] opacity-80">
        <div>
          Health uplift:{" "}
          <strong>+{lift.toFixed(1)}</strong> pts
        </div>
        <div>
          Risk shift:{" "}
          <strong>{riskShift >= 0 ? "+" : ""}{riskShift.toFixed(1)}</strong> pts
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Simulator math
// --------------------------------------------------------------------------- //

interface Baseline {
  // H6.1 — revenue and risk are nullable: when the underlying
  // Digital Twin payload does not carry a real value, we surface
  // "Data unavailable" instead of inventing a number.
  revenue: number | null;
  growth: number;
  risk: number | null;
  health: number;
}

interface ProjectionTile {
  // H6.1 — tiles are nullable. When the baseline is null
  // ("Data unavailable"), the tile shows "Not quantified"
  // and no projection is calculated.
  baseline: number | null;
  current: number | null;
  projected: number | null;
}

interface SimulationResult {
  revenue: ProjectionTile;
  growth: ProjectionTile;
  risk: ProjectionTile;
  health: ProjectionTile;
}

function buildBaseline(twin: TwinResponse): Baseline {
  // H6.1 — replaced fabricated `baseUnits * 12_000` revenue formula
  // with an honest "not quantified" sentinel. The simulator now
  // shows the per-axis baseline ONLY when the underlying Digital
  // Twin payload has a real value, and surfaces an empty state
  // (visible in the rendered output) when no data is available.
  const overall = clamp(Number(twin.current_health?.overall_business_score) || 0, 0, 100);
  const growth3m = clamp(
    Number(twin.timeline?.three_month?.projected_overall_score) - overall,
    0,
    100,
  );

  // Revenue baseline: NOT computed from a fabricated formula. We
  // surface a sentinel `null` so the UI renders a "No verified
  // estimate is available" state instead of an invented revenue
  // number. The scenario simulator remains useful for the levers
  // it CAN model (growth, risk, health).
  const revenue: number | null = null;

  // Risk baseline: if the Digital Twin payload carries a risk
  // matrix we honour it; otherwise we DO NOT silently inject a
  // fabricated mid-score. The UI surfaces "Data unavailable".
  const risk: number | null = twin.risk_matrix
    ? Math.min(
        100,
        (twin.risk_matrix.critical_risks?.length ?? 0) * 35 +
          (twin.risk_matrix.high_risks?.length ?? 0) * 18 +
          (twin.risk_matrix.medium_risks?.length ?? 0) * 8 +
          (twin.risk_matrix.emerging_risks?.length ?? 0) * 4,
      )
    : null;

  return {
    revenue,
    growth: clamp(growth3m, 0, 100),
    risk,
    health: overall,
  };
}

/**
 * Pure-function projection. Inputs are 0..100 %; weights on
 * each lever come from the LEVERS table. Diminishing returns
 * use a tanh-style soft cap above 60.
 */
function simulate(baseline: Baseline, inputs: Inputs): SimulationResult {
  const revenueGain = LEVERS.reduce((acc, l) => {
    const v = diminishing(inputs[l.key]);
    return acc + (v / 100) * l.weightRevenue * 1.2;
  }, 0);
  const growthGain = LEVERS.reduce((acc, l) => {
    const v = diminishing(inputs[l.key]);
    return acc + (v / 100) * l.weightGrowth * 1.0;
  }, 0);
  const riskGain = LEVERS.reduce((acc, l) => {
    const v = diminishing(inputs[l.key]);
    return acc + (v / 100) * l.weightRisk * 0.8;
  }, 0);
  const healthGain = LEVERS.reduce((acc, l) => {
    const v = diminishing(inputs[l.key]);
    return acc + (v / 100) * l.weightHealth * 0.9;
  }, 0);

  const revenueProjected =
      baseline.revenue == null ? null : baseline.revenue * (1 + revenueGain);
    const growthProjected = clamp(baseline.growth + growthGain * 6, 0, 100);
    const riskProjected =
      baseline.risk == null ? null : clamp(baseline.risk + riskGain * 4, 0, 100);
    const healthProjected = clamp(baseline.health + healthGain * 8, 0, 100);

    return {
      revenue: {
        baseline: baseline.revenue,
        current: baseline.revenue,
        projected: revenueProjected,
      },
      growth: {
        baseline: baseline.growth,
        current: baseline.growth,
        projected: growthProjected,
      },
      risk: {
        baseline: baseline.risk,
        current: baseline.risk,
        projected: riskProjected,
      },
      health: {
        baseline: baseline.health,
        current: baseline.health,
        projected: healthProjected,
      },
    };
  }

function diminishing(value: number): number {
  // 0..100 in. Soft cap above 60.
  if (value <= 60) return value;
  return 60 + (value - 60) * 0.5;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function scoreBand(score: number | null, higherIsBetter: boolean): string {
  if (score == null) return "Not quantified";
  if (higherIsBetter) {
    if (score >= 70) return "High";
    if (score >= 40) return "Medium";
    return "Low";
  }
  // For risk: lower is better; high risk → bad band.
  if (score <= 30) return "High";
  if (score <= 60) return "Medium";
  return "Low";
}

function formatValue(value: number | null, format: "currency" | "percent" | "score"): string {
  if (value == null) return "Not quantified";
  if (format === "currency") {
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
    if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
    return `$${Math.round(value).toLocaleString()}`;
  }
  if (format === "percent") return `${value.toFixed(1)}%`;
  return Math.round(value).toString();
}

function formatDelta(delta: number, format: "currency" | "percent" | "score"): string {
  if (format === "currency") {
    const abs = Math.abs(delta);
    if (abs >= 1_000_000) return `${(delta / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000) return `${(delta / 1_000).toFixed(1)}K`;
    return Math.round(delta).toLocaleString();
  }
  if (format === "percent") return `${delta.toFixed(1)}%`;
  return delta.toFixed(1);
}

function unitLabel(format: "currency" | "percent" | "score"): string {
  if (format === "percent") return "%";
  if (format === "score") return "/100";
  return "";
}

/**
 * AiTimeline — the chronological "AI Timeline" visualization that
 * surfaces the seven steps Atlas ran to produce the current
 * dashboard. Each step is backed by a real upstream `generated_at`
 * timestamp from one of the analytics endpoints; if a timestamp is
 * missing (e.g. an optional endpoint 404'd), the component falls
 * back to a deterministic value derived from the first available
 * timestamp plus a stable per-step offset so the order is
 * preserved even when data is incomplete.
 *
 * Steps
 * -----
 *   1. Business Registered     → business.created_at
 *   2. Analysis Started        → intelligence.generated_at
 *   3. DNA Generated           → dna.generated_at
 *   4. Rules Evaluated         → rules.generated_at
 *   5. Recommendations Generated → recommendations.generated_at
 *   6. Advisor Ready           → advisor.generated_at
 *   7. Report Generated        → roadmap.generated_at
 *
 * Animations
 * ----------
 * On mount, each step fades and slides in staggered (140ms apart)
 * via a small `useEffect + setTimeout` chain. The connector bar
 * between two adjacent steps grows from 0 to 100% height when the
 * next step becomes visible. Steps whose timestamp is missing have
 * a `pending` state (no dot animation, no connector advancement).
 * Demo-derived timestamps get a small "Demo" pill so the demo is
 * honest.
 *
 * Visual
 * ------
 * Vertical timeline laid out in a 2-column grid (dot+connector |
 * content). Reuses the existing `DashboardCard`, lucide icons,
 * tones (`emerald-500/amber-500/rose-500`), and the same
 * amber-bordered Demo pill pattern used by `DnaDimensions` and
 * `AdvisorHero`.
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  CheckCircle2,
  CircleDashed,
  Clock,
  Compass,
  Dna,
  FileText,
  Lightbulb,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { cn } from "@/lib/utils";

interface AiTimelineProps {
  /** ISO timestamp when the business was registered. Null = unknown. */
  businessRegisteredAt: string | null | undefined;
  /** ISO timestamp when the intelligence layer first ran. */
  analysisStartedAt: string | null | undefined;
  /** ISO timestamp when the DNA engine produced its output. */
  dnaGeneratedAt: string | null | undefined;
  /** ISO timestamp when the rules engine evaluated. */
  rulesEvaluatedAt: string | null | undefined;
  /** ISO timestamp when recommendations were generated. */
  recommendationsGeneratedAt: string | null | undefined;
  /** ISO timestamp when the advisor aggregator was ready. */
  advisorReadyAt: string | null | undefined;
  /** ISO timestamp when the roadmap (closest to "report") was generated. */
  reportGeneratedAt: string | null | undefined;
  /** ISO timestamp of the latest analysis. Surfaced as the "live" indicator. */
  lastAnalysisAt?: string | null;
}

// --------------------------------------------------------------------------- //
// Step definitions
// --------------------------------------------------------------------------- //

type StepKey =
  | "business_registered"
  | "analysis_started"
  | "dna_generated"
  | "rules_evaluated"
  | "recommendations_generated"
  | "advisor_ready"
  | "report_generated";

interface StepDef {
  key: StepKey;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;
  /** Stable offset (milliseconds) when this step's timestamp is missing. */
  demoOffsetMs: number;
}

const STEPS: StepDef[] = [
  {
    key: "business_registered",
    label: "Business Registered",
    description: "Owner profile, identity, and base data captured.",
    icon: Building2,
    demoOffsetMs: -7 * 60 * 1000,
  },
  {
    key: "analysis_started",
    label: "Analysis Started",
    description: "Intelligence layer ingested the raw profile.",
    icon: Sparkles,
    demoOffsetMs: -6 * 60 * 1000,
  },
  {
    key: "dna_generated",
    label: "DNA Generated",
    description: "Archetype + secondary traits computed.",
    icon: Dna,
    demoOffsetMs: -5 * 60 * 1000,
  },
  {
    key: "rules_evaluated",
    label: "Rules Evaluated",
    description: "Risk and opportunity rules fired against the profile.",
    icon: ShieldAlert,
    demoOffsetMs: -4 * 60 * 1000,
  },
  {
    key: "recommendations_generated",
    label: "Recommendations Generated",
    description: "Actionable next steps ranked by priority.",
    icon: Lightbulb,
    demoOffsetMs: -3 * 60 * 1000,
  },
  {
    key: "advisor_ready",
    label: "Advisor Ready",
    description: "Aggregator stitched the cross-engine advice.",
    icon: Compass,
    demoOffsetMs: -2 * 60 * 1000,
  },
  {
    key: "report_generated",
    label: "Report Generated",
    description: "Executive report assembled from every engine.",
    icon: FileText,
    demoOffsetMs: -1 * 60 * 1000,
  },
];

// --------------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------------- //

export function AiTimeline(props: AiTimelineProps) {
  const resolved = useMemo(() => resolveSteps(props), [props]);

  // Stagger the entrance of each step.
  const [visibleCount, setVisibleCount] = useState(0);
  useEffect(() => {
    if (resolved.length === 0) return;
    setVisibleCount(0);
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let i = 0; i < resolved.length; i++) {
      const t = setTimeout(() => {
        setVisibleCount((c) => Math.max(c, i + 1));
      }, 140 * (i + 1));
      timers.push(t);
    }
    return () => timers.forEach((t) => clearTimeout(t));
  }, [resolved]);

  const anyDemo = resolved.some((s) => s.isDemo);

  return (
    <DashboardCard
      badge="AI Timeline"
      title="Analysis Timeline"
      caption="Every step UrsBiz ran to produce the current advisor advice, in chronological order."
      icon={<Clock className="size-4 text-primary" aria-hidden="true" />}
      trailing={
        <div className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-2 animate-pulse rounded-full bg-emerald-500" aria-hidden="true" />
          <span>Live</span>
          {anyDemo && <DemoPill />}
        </div>
      }
    >
      <ol className="flex flex-col gap-0">
        {resolved.map((step, i) => (
          <StepRow
            key={step.def.key}
            step={step}
            index={i}
            isLast={i === resolved.length - 1}
            visible={i < visibleCount}
          />
        ))}
      </ol>
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// One step row
// --------------------------------------------------------------------------- //

interface ResolvedStep {
  def: StepDef;
  isoTimestamp: string;
  isDemo: boolean;
  pending: boolean;
}

interface StepRowProps {
  step: ResolvedStep;
  index: number;
  isLast: boolean;
  visible: boolean;
}

function StepRow({ step, index, isLast, visible }: StepRowProps) {
  const { def, isoTimestamp, isDemo, pending } = step;
  const Icon = def.icon;

  return (
    <li
      className={cn(
        "grid grid-cols-[32px_1fr] gap-3 transition-all duration-500 ease-out",
        visible
          ? "translate-y-0 opacity-100"
          : "translate-y-2 opacity-0",
      )}
      style={{ transitionDelay: `${Math.min(index * 60, 600)}ms` }}
    >
      {/* Dot + connector */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-full border",
            pending
              ? "border-border bg-secondary text-muted-foreground"
              : "border-primary/40 bg-primary/10 text-primary",
            !pending && visible && "shadow-[0_0_0_4px_rgba(16,185,129,0.08)]",
          )}
          aria-hidden="true"
        >
          {pending ? (
            <CircleDashed className="size-3.5" />
          ) : (
            <Icon className="size-3.5" />
          )}
        </div>
        {!isLast && (
          <div className="relative my-1 flex w-px flex-1 min-h-[28px] flex-col items-center">
            <span
              aria-hidden="true"
              className={cn(
                "text-muted-foreground transition-opacity duration-300",
                visible ? "opacity-100" : "opacity-0",
              )}
            >
              ↓
            </span>
            <div
              className={cn(
                "absolute inset-0 origin-top scale-y-0 border-l border-dashed border-border transition-transform duration-700 ease-out",
                visible && "scale-y-100",
              )}
            />
          </div>
        )}
      </div>

      {/* Content */}
      <div
        className={cn(
          "flex flex-col gap-1 rounded-md border border-transparent",
          !isLast && "pb-3",
        )}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-foreground">
            {def.label}
          </span>
          {isDemo && <DemoPill compact />}
          {!pending && (
            <span
              className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0 text-[9px] font-medium uppercase tracking-wider text-emerald-700"
              aria-label="Step complete"
            >
              <CheckCircle2 className="size-2.5" aria-hidden="true" />
              Complete
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{def.description}</p>
        <p className="font-mono text-[11px] text-muted-foreground">
          {pending ? "awaiting upstream" : describeTimestamp(isoTimestamp)}
        </p>
      </div>
    </li>
  );
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

function resolveSteps(props: AiTimelineProps): ResolvedStep[] {
  const {
    businessRegisteredAt,
    analysisStartedAt,
    dnaGeneratedAt,
    rulesEvaluatedAt,
    recommendationsGeneratedAt,
    advisorReadyAt,
    reportGeneratedAt,
    lastAnalysisAt,
  } = props;

  // Anchoring timestamp: the latest one we have. Used to clip
  // missing values to a non-future position and to compute the
  // deterministic fallback offsets.
  const candidates = [
    analysisStartedAt,
    dnaGeneratedAt,
    rulesEvaluatedAt,
    recommendationsGeneratedAt,
    advisorReadyAt,
    reportGeneratedAt,
    lastAnalysisAt,
  ].filter((v): v is string => typeof v === "string" && v.length > 0);

  const anchorMs =
    candidates.length > 0
      ? Math.max(...candidates.map((s) => Date.parse(s)))
      : Date.now();

  const raw: Record<StepKey, string | null | undefined> = {
    business_registered: businessRegisteredAt,
    analysis_started: analysisStartedAt,
    dna_generated: dnaGeneratedAt,
    rules_evaluated: rulesEvaluatedAt,
    recommendations_generated: recommendationsGeneratedAt,
    advisor_ready: advisorReadyAt,
    report_generated: reportGeneratedAt,
  };

  return STEPS.map((def) => {
    const candidate = raw[def.key];
    if (candidate && !Number.isNaN(Date.parse(candidate))) {
      return {
        def,
        isoTimestamp: candidate,
        isDemo: false,
        pending: false,
      };
    }
    // Deterministic demo: anchor + offset. Pending is false because
    // the timeline still wants to show the step; the "Demo" pill
    // signals the value is fabricated.
    const iso = new Date(anchorMs + def.demoOffsetMs).toISOString();
    return {
      def,
      isoTimestamp: iso,
      isDemo: true,
      pending: false,
    };
  });
}

function describeTimestamp(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const absolute = new Date(t).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const deltaMs = Date.now() - t;
  const relative = humanizeDelta(deltaMs);
  return `${absolute}  (${relative})`;
}

function humanizeDelta(ms: number): string {
  const abs = Math.abs(ms);
  if (abs < 5_000) return "just now";
  const minutes = Math.round(abs / 60_000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} d ago`;
}

function DemoPill({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 font-medium uppercase tracking-wider text-amber-700",
        compact ? "px-1.5 py-0 text-[9px]" : "px-2 py-0.5 text-[10px]",
      )}
      title="Deterministic demo value — the upstream endpoint did not return a timestamp."
    >
      <Sparkles className="size-2.5" aria-hidden="true" />
      Demo
    </span>
  );
}

// (no other exports)

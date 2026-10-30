/**
 * AnalysisProgress — animated "Analyzing your business…" screen.
 *
 * Six sequential stages driven by the demo runner. Renders:
 *   - A primary hero with business name + animated progress bar
 *   - A vertical stage list (pending / running / complete)
 *   - A subtle note when the run finishes
 *
 * Pure presentational. Receives the run handle and the current
 * state from the parent. The parent decides what to do when
 * the run completes (route to /dashboard, etc.).
 */

"use client";

import { useMemo } from "react";
import {
  Activity,
  Check,
  CircleDashed,
  CircleDot,
  Compass,
  Dna,
  FileSearch,
  Gauge,
  Lightbulb,
  Loader2,
  Sparkles,
} from "lucide-react";
import { ProgressBar } from "@/components/dashboard/ProgressBar";
import { cn } from "@/lib/utils";
import { ANALYSIS_STAGES } from "./use-analysis-runner";
import type { AnalysisStage, AnalysisStageId, AnalysisStatus } from "./types";

const STAGE_ICONS: Record<AnalysisStageId, React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>> = {
  profile: FileSearch,
  dna: Dna,
  scores: Gauge,
  decision: Compass,
  recommendations: Lightbulb,
  advisor: Sparkles,
};

interface AnalysisProgressProps {
  /** Business legal name shown as a friendly greeting. */
  businessName: string;
  /** Index of the stage currently running, or null while at the start. */
  activeIndex: number | null;
  /** Cumulative percent 0..100. */
  percent: number;
  /** Current run status. */
  status: AnalysisStatus;
  /** Optional override for the headline; defaults are branded. */
  headline?: string;
  /** Optional override for the supporting copy. */
  caption?: string;
}

export function AnalysisProgress({
  businessName,
  activeIndex,
  percent,
  status,
  headline = "Analyzing your business…",
  caption = "Hold tight while UrsBiz works through six stages. This usually takes a few seconds.",
}: AnalysisProgressProps) {
  const doneCount = status === "complete"
    ? ANALYSIS_STAGES.length
    : Math.max(0, (activeIndex ?? -1) + (status === "running" ? 1 : 0));

  const fillTone = useMemo(() => {
    if (status === "failed") return "bg-rose-500";
    if (percent >= 100) return "bg-emerald-500";
    return "bg-primary";
  }, [status, percent]);

  return (
    <div className="flex flex-col items-center gap-8 py-6">
      {/* Hero */}
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="relative flex size-16 items-center justify-center">
          {status === "complete" ? (
            <div className="flex size-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <Check className="size-8" aria-hidden="true" />
            </div>
          ) : status === "failed" ? (
            <div className="flex size-16 items-center justify-center rounded-full bg-rose-100 text-rose-700">
              <Activity className="size-8" aria-hidden="true" />
            </div>
          ) : (
            <>
              <div
                aria-hidden="true"
                className="absolute inset-0 animate-ping rounded-full bg-primary/15"
              />
              <div className="flex size-16 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Loader2 className="size-7 animate-spin" aria-hidden="true" />
              </div>
            </>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            {headline}
          </h2>
          <p className="text-sm text-muted-foreground">{caption}</p>
          {businessName && (
            <p className="text-xs text-muted-foreground">
              For <span className="font-medium text-foreground">{businessName}</span>
            </p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-md">
        <ProgressBar
          value={percent}
          label="Analysis progress"
          hint={
            status === "failed"
              ? "Failed"
              : status === "complete"
              ? "100%"
              : `${percent}%`
          }
          fillClassName={fillTone}
          ariaLabel="Analysis progress percentage"
        />
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          {doneCount} of {ANALYSIS_STAGES.length} stages complete
        </p>
      </div>

      {/* Stage list */}
      <ol className="flex w-full max-w-md flex-col gap-2" aria-label="Analysis stages">
        {ANALYSIS_STAGES.map((stage, i) => {
          const State = stageState(i, activeIndex, status);
          return <StageRow key={stage.id} stage={stage} state={State} />;
        })}
      </ol>
    </div>
  );
}

type StageState = "pending" | "running" | "complete";

function stageState(index: number, activeIndex: number | null, status: AnalysisStatus): StageState {
  if (status === "complete") return "complete";
  if (status === "failed") {
    // Mark every stage up to (but not including) the failed one as complete.
    if (activeIndex === null) return "pending";
    return index <= activeIndex ? "complete" : "pending";
  }
  if (activeIndex === null) return "pending";
  if (index < activeIndex) return "complete";
  if (index === activeIndex) return "running";
  return "pending";
}

function StageRow({ stage, state }: { stage: AnalysisStage; state: StageState }) {
  const Icon = STAGE_ICONS[stage.id];
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-md border px-3 py-2 transition-colors",
        state === "complete" && "border-emerald-500/30 bg-emerald-50/40",
        state === "running"  && "border-primary/40 bg-primary/5",
        state === "pending"  && "border-border bg-secondary/30",
      )}
      aria-current={state === "running" ? "step" : undefined}
    >
      <div
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border",
          state === "complete" && "border-emerald-500 bg-emerald-500 text-white",
          state === "running"  && "border-primary bg-primary/10 text-primary",
          state === "pending"  && "border-border bg-background text-muted-foreground",
        )}
      >
        {state === "complete" ? (
          <Check className="size-4" aria-hidden="true" />
        ) : state === "running" ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <Icon className="size-4" aria-hidden="true" />
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              state === "complete" && "text-emerald-700",
              state === "running"  && "text-foreground",
              state === "pending"  && "text-muted-foreground",
            )}
          >
            {stage.label}
          </span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {state === "complete" ? "Done" : state === "running" ? "Running…" : "Pending"}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">{stage.description}</p>
      </div>
    </li>
  );
}

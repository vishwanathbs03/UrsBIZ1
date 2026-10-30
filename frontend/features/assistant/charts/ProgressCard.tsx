/**
 * SPRINT AI-15 — ProgressCard. Current vs target progress bar.
 */

import React from "react";

export interface ProgressCardProps {
  title: string;
  current: number;
  target: number;
  unit?: string;
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function ProgressCard(props: ProgressCardProps): React.JSX.Element | null {
  if (
    props.empty_reason ||
    !Number.isFinite(props.current) ||
    !Number.isFinite(props.target) ||
    props.target <= 0
  ) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "Missing current/target values."}
        </div>
      </div>
    );
  }
  const pct = Math.min(100, Math.max(0, (props.current / props.target) * 100));
  const gap = Math.max(0, props.target - props.current);
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {props.title}
        </div>
        <div className="text-xs text-slate-500">
          {(props.confidence * 100).toFixed(0)}%
        </div>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-lg font-semibold text-slate-900">
          {props.current.toLocaleString()}
        </span>
        {props.unit && <span className="text-xs text-slate-500">{props.unit}</span>}
        <span className="text-xs text-slate-400">
          / {props.target.toLocaleString()} {props.unit ?? ""}
        </span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-emerald-500"
          style={{ width: `${pct}%` }}
          aria-label={`Progress ${pct.toFixed(0)}%`}
        />
      </div>
      <div className="mt-2 text-xs text-slate-500">
        Gap: {gap.toLocaleString()} {props.unit ?? ""}
      </div>
    </div>
  );
}

export default ProgressCard;

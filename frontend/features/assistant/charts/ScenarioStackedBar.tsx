/**
 * SPRINT AI-15 — ScenarioStackedBar. Baseline + changed input +
 * estimated effect. Always labelled "Scenario estimate" (never
 * "Predicted result" — scenarios are estimates, not promises).
 */

import React from "react";

export interface ScenarioStackedBarProps {
  title: string;
  baseline: number;
  changed_input: string;
  estimated_effect: number;
  unit?: string;
  confidence: number;
  source_evidence_ids: string[];
  assumptions: string[];
  empty_reason?: string;
}

export function ScenarioStackedBar(
  props: ScenarioStackedBarProps
): React.JSX.Element | null {
  if (
    props.empty_reason ||
    !Number.isFinite(props.baseline) ||
    !Number.isFinite(props.estimated_effect)
  ) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "Missing baseline or effect values."}
        </div>
      </div>
    );
  }
  const newValue = props.baseline + props.estimated_effect;
  const W = 320;
  const H = 24;
  const max = Math.max(Math.abs(props.baseline), Math.abs(newValue), 1);
  const scale = (v: number) => (Math.abs(v) / max) * W;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-baseline justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {props.title}
        </div>
        <div className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800">
          Scenario estimate
        </div>
      </div>
      <div className="mt-3 text-xs text-slate-600">
        Changed input: <span className="font-medium">{props.changed_input}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 h-6 w-full" role="img">
        <rect
          x={0}
          y={0}
          width={scale(props.baseline)}
          height={H}
          fill="#94a3b8"
        />
        {props.estimated_effect !== 0 && (
          <rect
            x={scale(Math.min(0, props.estimated_effect))}
            y={0}
            width={scale(props.estimated_effect)}
            height={H}
            fill={props.estimated_effect >= 0 ? "#10b981" : "#ef4444"}
          />
        )}
      </svg>
      <div className="mt-2 flex items-baseline justify-between text-xs">
        <span className="text-slate-500">
          Baseline:{" "}
          <span className="font-medium text-slate-900">
            {props.baseline.toLocaleString()}
            {props.unit && ` ${props.unit}`}
          </span>
        </span>
        <span className="text-slate-500">
          Estimated:{" "}
          <span className="font-medium text-slate-900">
            {newValue.toLocaleString()}
            {props.unit && ` ${props.unit}`}
          </span>
        </span>
      </div>
      {props.assumptions.length > 0 && (
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-slate-500">
          {props.assumptions.slice(0, 3).map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
      <div className="mt-2 text-xs text-slate-400">
        Confidence: {(props.confidence * 100).toFixed(0)}%
      </div>
    </div>
  );
}

export default ScenarioStackedBar;
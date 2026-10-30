/**
 * SPRINT AI-15 — KPICard. Single-value headline tile.
 *
 * Hand-rolled SVG/CSS — no external chart library. Matches
 * the existing TrustFirstResponse aesthetic.
 */

import React from "react";

export interface KPICardProps {
  title: string;
  value: number | string;
  unit?: string;
  delta?: number;
  trend?: number[];
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function KPICard(props: KPICardProps): React.JSX.Element | null {
  if (props.empty_reason || props.value === undefined || props.value === null) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">{props.empty_reason ?? "Missing data."}</div>
      </div>
    );
  }
  const formatted =
    typeof props.value === "number"
      ? props.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : props.value;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {props.title}
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-semibold text-slate-900">{formatted}</span>
        {props.unit && (
          <span className="text-sm text-slate-500">{props.unit}</span>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
        <span>
          Confidence: {(props.confidence * 100).toFixed(0)}%
        </span>
        {props.source_evidence_ids.length > 0 && (
          <span>{props.source_evidence_ids.length} source(s)</span>
        )}
      </div>
    </div>
  );
}

export default KPICard;

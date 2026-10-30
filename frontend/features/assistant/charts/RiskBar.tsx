/**
 * SPRINT AI-15 — RiskBar. Wraps the existing RiskBarChart with the
 * AI-15 viz payload contract (title + empty_reason + confidence).
 *
 * Existing RiskBarChart stays the renderer; this thin shim sits on
 * top so VisualizationCard can dispatch to a single component per
 * chart_kind without forcing the AI-6 renderer to grow new props.
 */

import React from "react";
import { RiskBarChart, type RiskBarSegment } from "@/features/assistant/RiskBarChart";

export interface RiskBarProps {
  title: string;
  segments: RiskBarSegment[];
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function RiskBar(props: RiskBarProps): React.JSX.Element | null {
  if (
    props.empty_reason ||
    !Array.isArray(props.segments) ||
    props.segments.length === 0
  ) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "No risk segments to display."}
        </div>
      </div>
    );
  }
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
      <div className="mt-2">
        <RiskBarChart segments={props.segments} />
      </div>
    </div>
  );
}

export default RiskBar;

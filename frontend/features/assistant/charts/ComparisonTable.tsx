/**
 * SPRINT AI-15 — ComparisonTable. Side-by-side options table.
 */

import React from "react";

export interface ComparisonRow {
  label: string;
  values: [string | number, string | number];
  unit?: string;
}

export interface ComparisonTableProps {
  title: string;
  left_label: string;
  right_label: string;
  rows: ComparisonRow[];
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function ComparisonTable(props: ComparisonTableProps): React.JSX.Element | null {
  if (props.empty_reason || !props.rows || props.rows.length === 0) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "No comparison data available."}
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
      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="pb-2 text-left">Metric</th>
            <th className="pb-2 text-right">{props.left_label}</th>
            <th className="pb-2 text-right">{props.right_label}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, idx) => (
            <tr key={idx} className="border-t border-slate-100">
              <td className="py-2 text-slate-700">{row.label}</td>
              <td className="py-2 text-right font-medium text-slate-900">
                {row.values[0]}
                {row.unit && <span className="ml-1 text-xs text-slate-500">{row.unit}</span>}
              </td>
              <td className="py-2 text-right font-medium text-slate-900">
                {row.values[1]}
                {row.unit && <span className="ml-1 text-xs text-slate-500">{row.unit}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {props.source_evidence_ids.length > 0 && (
        <div className="mt-3 text-xs text-slate-500">
          {props.source_evidence_ids.length} source(s)
        </div>
      )}
    </div>
  );
}

export default ComparisonTable;

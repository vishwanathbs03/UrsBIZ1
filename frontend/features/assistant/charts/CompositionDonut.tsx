/**
 * SPRINT AI-15 — CompositionDonut. Hand-rolled SVG donut.
 *
 * Caps slices at 5 (others grouped as "Other"). Empty state
 * returns "Not enough business data" notice.
 */

import React from "react";

export interface CompositionSlice {
  label: string;
  value: number;
}

export interface CompositionDonutProps {
  title: string;
  slices: CompositionSlice[];
  unit?: string;
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

const COLORS = [
  "#0ea5e9",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#94a3b8",
];

export function CompositionDonut(
  props: CompositionDonutProps
): React.JSX.Element | null {
  const MAX_SLICES = 5;
  const raw = (props.slices ?? []).filter((s) => Number.isFinite(s.value) && s.value > 0);
  let displayed = raw;
  if (raw.length > MAX_SLICES) {
    const head = raw.slice(0, MAX_SLICES - 1);
    const rest = raw.slice(MAX_SLICES - 1);
    const otherValue = rest.reduce((acc, s) => acc + s.value, 0);
    displayed = [
      ...head,
      { label: "Other", value: otherValue },
    ];
  }
  if (props.empty_reason || displayed.length === 0) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "No composition data available."}
        </div>
      </div>
    );
  }
  const total = displayed.reduce((acc, s) => acc + s.value, 0) || 1;
  const R_OUTER = 60;
  const R_INNER = 36;
  const C = 80;
  let acc = 0;
  const segments = displayed.map((slice, i) => {
    const start = (acc / total) * Math.PI * 2 - Math.PI / 2;
    acc += slice.value;
    const end = (acc / total) * Math.PI * 2 - Math.PI / 2;
    const x1 = C + R_OUTER * Math.cos(start);
    const y1 = C + R_OUTER * Math.sin(start);
    const x2 = C + R_OUTER * Math.cos(end);
    const y2 = C + R_OUTER * Math.sin(end);
    const x3 = C + R_INNER * Math.cos(end);
    const y3 = C + R_INNER * Math.sin(end);
    const x4 = C + R_INNER * Math.cos(start);
    const y4 = C + R_INNER * Math.sin(start);
    const largeArc = end - start > Math.PI ? 1 : 0;
    const d = [
      `M ${x1} ${y1}`,
      `A ${R_OUTER} ${R_OUTER} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${x3} ${y3}`,
      `A ${R_INNER} ${R_INNER} 0 ${largeArc} 0 ${x4} ${y4}`,
      "Z",
    ].join(" ");
    return { d, color: COLORS[i % COLORS.length], label: slice.label };
  });
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
      <div className="mt-2 flex items-center gap-4">
        <svg viewBox="0 0 160 160" className="h-32 w-32" role="img">
          {segments.map((seg, i) => (
            <path key={i} d={seg.d} fill={seg.color} />
          ))}
        </svg>
        <ul className="flex-1 space-y-1 text-xs">
          {segments.map((seg, i) => (
            <li key={i} className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: seg.color }}
              />
              <span className="flex-1 text-slate-700">{seg.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default CompositionDonut;
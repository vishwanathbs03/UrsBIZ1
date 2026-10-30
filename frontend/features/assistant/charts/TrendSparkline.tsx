/**
 * SPRINT AI-15 — TrendSparkline. Mini-line SVG.
 *
 * Only renders when there are >= 2 points. Otherwise returns
 * the empty-state "Not enough business data" notice.
 */

import React from "react";

export interface TrendPoint {
  x: string | number;
  y: number;
}

export interface TrendSparklineProps {
  title: string;
  points: TrendPoint[];
  unit?: string;
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function TrendSparkline(props: TrendSparklineProps): React.JSX.Element | null {
  const validPoints = (props.points ?? []).filter(
    (p) => p && Number.isFinite(p.y)
  );
  if (props.empty_reason || validPoints.length < 2) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "Need at least 2 time-points to plot a trend."}
        </div>
      </div>
    );
  }
  const W = 320;
  const H = 80;
  const PAD = 6;
  const ys = validPoints.map((p) => p.y);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeY = maxY - minY || 1;
  const stepX = (W - 2 * PAD) / (validPoints.length - 1);
  const coords = validPoints.map((p, i) => {
    const x = PAD + i * stepX;
    const y = PAD + (H - 2 * PAD) * (1 - (p.y - minY) / rangeY);
    return { x, y };
  });
  const path = coords
    .map((c, i) => (i === 0 ? `M ${c.x} ${c.y}` : `L ${c.x} ${c.y}`))
    .join(" ");
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
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-2 h-20 w-full"
        role="img"
        aria-label={`Trend for ${props.title}`}
      >
        <path
          d={path}
          fill="none"
          stroke="#10b981"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {coords.map((c, i) => (
          <circle key={i} cx={c.x} cy={c.y} r="2.5" fill="#10b981" />
        ))}
      </svg>
      <div className="mt-2 flex items-baseline justify-between text-xs text-slate-500">
        <span>
          {validPoints[0].y.toLocaleString()}
          {props.unit && ` ${props.unit}`}
        </span>
        <span>
          {validPoints[validPoints.length - 1].y.toLocaleString()}
          {props.unit && ` ${props.unit}`}
        </span>
      </div>
    </div>
  );
}

export default TrendSparkline;
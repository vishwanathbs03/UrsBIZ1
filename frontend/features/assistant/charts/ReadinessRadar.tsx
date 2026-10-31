/**
 * SPRINT AI-15 — ReadinessRadar. Hand-rolled SVG radar.
 *
 * Renders N axes (axes are normalized 0..1). When fewer than
 * 3 axes are present, returns the empty-state notice.
 */

import React from "react";

export interface ReadinessAxis {
  label: string;
  value: number;
  max?: number;
}

export interface ReadinessRadarProps {
  title: string;
  axes: ReadinessAxis[];
  confidence: number;
  source_evidence_ids: string[];
  empty_reason?: string;
}

export function ReadinessRadar(props: ReadinessRadarProps): React.JSX.Element | null {
  const axes = (props.axes ?? []).filter(
    (a) => a && Number.isFinite(a.value)
  );
  if (props.empty_reason || axes.length < 3) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <div className="font-medium">Not enough business data</div>
        <div className="text-xs opacity-75">
          {props.empty_reason ?? "Need at least 3 readiness axes."}
        </div>
      </div>
    );
  }
  const C = 80;
  const R = 60;
  const ringFractions = [0.25, 0.5, 0.75, 1.0];
  const pointFor = (idx: number, value: number) => {
    const angle = (idx / axes.length) * Math.PI * 2 - Math.PI / 2;
    const r = (value / (axes[idx].max ?? 100)) * R;
    return {
      x: C + r * Math.cos(angle),
      y: C + r * Math.sin(angle),
      lx: C + R * Math.cos(angle),
      ly: C + R * Math.sin(angle),
      label: axes[idx].label,
    };
  };
  const pts = axes.map((_, i) => pointFor(i, axes[i].value));
  const polyPath = pts
    .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
    .join(" ") + " Z";
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
      <svg viewBox="0 0 200 200" className="mt-2 h-44 w-full" role="img">
        {ringFractions.map((f, i) => (
          <polygon
            key={i}
            points={axes
              .map((_, idx) => {
                const angle = (idx / axes.length) * Math.PI * 2 - Math.PI / 2;
                const x = C + R * f * Math.cos(angle);
                const y = C + R * f * Math.sin(angle);
                return `${x},${y}`;
              })
              .join(" ")}
            fill="none"
            stroke="#e2e8f0"
            strokeWidth="1"
          />
        ))}
        {pts.map((p, i) => (
          <line
            key={`ax-${i}`}
            x1={C}
            y1={C}
            x2={p.lx}
            y2={p.ly}
            stroke="#cbd5e1"
            strokeWidth="1"
          />
        ))}
        <path
          d={polyPath}
          fill="rgba(16,185,129,0.25)"
          stroke="#10b981"
          strokeWidth="2"
        />
        {pts.map((p, i) => (
          <circle key={`pt-${i}`} cx={p.x} cy={p.y} r="2.5" fill="#10b981" />
        ))}
      </svg>
      <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-600">
        {axes.map((a, i) => (
          <li key={i} className="flex justify-between">
            <span>{a.label}</span>
            <span className="font-medium text-slate-900">
              {a.value.toLocaleString()}/{a.max ?? 100}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ReadinessRadar;
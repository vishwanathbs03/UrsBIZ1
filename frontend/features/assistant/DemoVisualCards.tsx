"use client";

import React from "react";
import { ShieldCheck, Zap, AlertTriangle, CheckCircle2, Layers, Award } from "lucide-react";

export interface DemoVisualData {
  title: string;
  scoreGain: number; // e.g. 12
  revenueGainInr: string; // e.g. "₹30 Lakh"
  priority: "CRITICAL" | "HIGH" | "MEDIUM";
  capacityUtilPct: number; // 0..100
  confidenceScore: number; // 0..100
  citedEvidence: string[];
  roadmapMilestones: { horizon: string; title: string; timeline: string }[];
}

interface DemoVisualCardsProps {
  data?: DemoVisualData;
}

export const DemoVisualCards: React.FC<DemoVisualCardsProps> = ({
  data = {
    title: "Flagship Growth Diagnostic & Roadmap",
    scoreGain: 12,
    revenueGainInr: "₹30 Lakh",
    priority: "HIGH",
    capacityUtilPct: 88,
    confidenceScore: 92,
    citedEvidence: ["biz_profile_revenue", "rec_supplier_diversification", "scheme_mai_export"],
    roadmapMilestones: [
      { horizon: "30-Day", title: "Supplier Diversification Audit", timeline: "Days 1–15" },
      { horizon: "90-Day", title: "ISO 9001 Certification & MAI Grant", timeline: "Month 2" },
      { horizon: "6-Month", title: "Germany Trial Export Shipment", timeline: "Months 4–6" },
      { horizon: "1-Year", title: "2nd Factory Expansion Launch", timeline: "Months 7–12" },
    ],
  },
}) => {
  const getPriorityColor = (p: string) => {
    switch (p) {
      case "CRITICAL":
        return "bg-rose-950/80 text-rose-300 border-rose-700/60";
      case "HIGH":
        return "bg-amber-950/80 text-amber-300 border-amber-700/60";
      default:
        return "bg-sky-950/80 text-sky-300 border-sky-700/60";
    }
  };

  return (
    <div className="w-full bg-slate-950/90 border border-slate-800 rounded-xl p-5 shadow-2xl my-4 text-slate-100">
      {/* Top Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-400" />
          <h4 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
            {data.title}
          </h4>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold font-mono px-2.5 py-1 rounded border ${getPriorityColor(data.priority)}`}>
            {data.priority} PRIORITY
          </span>
          <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            {data.confidenceScore}% CONFIDENCE
          </span>
        </div>
      </div>

      {/* Impact Gauges & Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
        {/* Score Gain Meter */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3.5 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Health Score Impact
          </span>
          <div className="text-xl font-extrabold text-emerald-400 mt-1 flex items-baseline gap-1">
            +{data.scoreGain} <span className="text-xs font-normal text-slate-400">Pts</span>
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
            <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${Math.min(data.scoreGain * 5, 100)}%` }} />
          </div>
        </div>

        {/* Revenue Upside Gauge */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3.5 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Top-Line Revenue Upside
          </span>
          <div className="text-xl font-extrabold text-indigo-400 mt-1">
            {data.revenueGainInr}
          </div>
          <span className="text-[10px] text-slate-400">12-Month Projected Addition</span>
        </div>

        {/* Capacity Utilization Meter */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-3.5 flex flex-col justify-between">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Capacity Utilization
          </span>
          <div className="text-xl font-extrabold text-sky-400 mt-1">
            {data.capacityUtilPct}%
          </div>
          <div className="w-full bg-slate-800 h-2 rounded-full mt-2 overflow-hidden">
            <div className="bg-sky-500 h-full rounded-full" style={{ width: `${data.capacityUtilPct}%` }} />
          </div>
        </div>
      </div>

      {/* Multi-Horizon Execution Roadmap */}
      <div className="mb-5">
        <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          Multi-Horizon Action Steps
        </h5>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {data.roadmapMilestones.map((m, idx) => (
            <div key={idx} className="bg-slate-900/70 border border-slate-800/80 rounded-lg p-2.5">
              <div className="flex items-center justify-between text-[10px] text-indigo-400 font-mono font-bold mb-1">
                <span>{m.horizon}</span>
                <span className="text-slate-400">{m.timeline}</span>
              </div>
              <p className="text-xs font-medium text-slate-200 line-clamp-2">
                {m.title}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Grounded Evidence Footer */}
      <div className="border-t border-slate-800/80 pt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-400">
        <div className="flex items-center gap-1.5">
          <Award className="w-3.5 h-3.5 text-amber-400" />
          <span>Cited Evidence:</span>
          <div className="flex flex-wrap gap-1">
            {data.citedEvidence.map((e, idx) => (
              <span key={idx} className="font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                {e}
              </span>
            ))}
          </div>
        </div>
        <span className="italic">Grounded against UrsBiz EvidenceRegistry</span>
      </div>
    </div>
  );
};

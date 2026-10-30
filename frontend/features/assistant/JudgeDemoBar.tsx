"use client";

import React from "react";
import { Sparkles, Activity, UserCheck, TrendingUp, ShieldCheck, Layers, Cpu, Play } from "lucide-react";

export interface HighlightPill {
  id: string;
  label: string;
  query: string;
  icon: React.ReactNode;
}

interface JudgeDemoBarProps {
  onSelectHighlight: (query: string) => void;
}

export const JudgeDemoBar: React.FC<JudgeDemoBarProps> = ({ onSelectHighlight }) => {
  const highlights: HighlightPill[] = [
    {
      id: "twin",
      label: "1. Business Twin",
      query: "Show my Business Twin health score and DNA archetype",
      icon: <Activity className="w-3.5 h-3.5 text-indigo-400" />,
    },
    {
      id: "consultant",
      label: "2. AI Consultant",
      query: "What is my top business priority and diagnostic recommendation?",
      icon: <UserCheck className="w-3.5 h-3.5 text-emerald-400" />,
    },
    {
      id: "predictive",
      label: "3. Predictive Intel",
      query: "Show 6-month revenue forecast and scenario estimates",
      icon: <TrendingUp className="w-3.5 h-3.5 text-amber-400" />,
    },
    {
      id: "govt",
      label: "4. Govt Intel",
      query: "Advise me on eligible government export and credit schemes",
      icon: <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />,
    },
    {
      id: "roadmap",
      label: "5. Action Roadmaps",
      query: "Generate 30-day, 90-day, 6-month and 1-year execution roadmap",
      icon: <Layers className="w-3.5 h-3.5 text-purple-400" />,
    },
    {
      id: "scenario",
      label: "6. What-If Simulator",
      query: "What happens if I hire 15 people and open a second factory?",
      icon: <Cpu className="w-3.5 h-3.5 text-rose-400" />,
    },
  ];

  return (
    <div className="sticky top-0 z-50 w-full bg-slate-950/95 backdrop-blur-md border-b border-indigo-900/50 px-4 py-2.5 shadow-2xl">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Title & Badge */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-950 border border-indigo-700/60 text-indigo-300 text-[10px] font-mono font-bold tracking-wider uppercase">
            <Play className="w-3 h-3 text-emerald-400 fill-emerald-400 animate-pulse" />
            4-Min Judge Tour
          </div>
          <span className="text-xs font-bold text-slate-200 hidden sm:inline">
            Hackathon Demo Control Bar
          </span>
        </div>

        {/* 6 Quick-Jump Highlight Pills */}
        <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto py-0.5">
          {highlights.map((h) => (
            <button
              key={h.id}
              onClick={() => onSelectHighlight(h.query)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 hover:border-indigo-500/60 hover:bg-indigo-950/40 text-xs font-semibold text-slate-300 hover:text-white transition-all shadow-sm group whitespace-nowrap"
            >
              {h.icon}
              <span>{h.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

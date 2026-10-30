"use client";

import React from "react";
import { Sparkles, TrendingUp, AlertTriangle, Globe, Users, Cpu } from "lucide-react";

export interface DemoQuestion {
  id: string;
  question: string;
  category: string;
  icon: React.ReactNode;
}

interface DemoQuestionsPanelProps {
  onSelectQuestion: (question: string) => void;
}

export const DemoQuestionsPanel: React.FC<DemoQuestionsPanelProps> = ({ onSelectQuestion }) => {
  const questions: DemoQuestion[] = [
    {
      id: "q1",
      question: "How can I reach ₹3 Cr?",
      category: "Growth Strategy",
      icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
    },
    {
      id: "q2",
      question: "What is my biggest weakness?",
      category: "Risk Diagnostic",
      icon: <AlertTriangle className="w-4 h-4 text-rose-400" />,
    },
    {
      id: "q3",
      question: "Can I export to Europe?",
      category: "Export & Schemes",
      icon: <Globe className="w-4 h-4 text-sky-400" />,
    },
    {
      id: "q4",
      question: "What happens if I hire 15 people?",
      category: "Scenario Simulator",
      icon: <Users className="w-4 h-4 text-indigo-400" />,
    },
    {
      id: "q5",
      question: "Should I buy another machine?",
      category: "Capex Analysis",
      icon: <Cpu className="w-4 h-4 text-purple-400" />,
    },
  ];

  return (
    <div className="w-full bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-xl mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Judge Quick Demo Panel — 5 Flagship MSME Queries
          </span>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40">
          DEMO MODE ACTIVE
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
        {questions.map((q) => (
          <button
            key={q.id}
            onClick={() => onSelectQuestion(q.question)}
            className="flex flex-col text-left p-3 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-800/80 transition-all group"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="p-1 rounded bg-slate-900 border border-slate-800 group-hover:border-indigo-500/30">
                {q.icon}
              </span>
              <span className="text-[9px] uppercase tracking-wider font-semibold text-slate-400">
                {q.category}
              </span>
            </div>
            <span className="text-xs font-semibold text-slate-200 group-hover:text-white line-clamp-2">
              "{q.question}"
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};

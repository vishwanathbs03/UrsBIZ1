"use client";

import React, { useState } from "react";
import { Printer, Download, Award, TrendingUp, ShieldAlert, Globe, Briefcase, FileCheck } from "lucide-react";

export interface SummaryCardData {
  audience: "ceo" | "investor" | "bank" | "export" | "risk" | "growth" | "compliance";
  title: string;
  headline: string;
  metrics: Record<string, string>;
  highlights: string[];
  recommendation: string;
}

interface ExecutiveSummarySuiteProps {
  businessName?: string;
  cards?: SummaryCardData[];
}

export const ExecutiveSummarySuite: React.FC<ExecutiveSummarySuiteProps> = ({
  businessName = "Acme Textiles",
  cards = [
    {
      audience: "ceo",
      title: "CEO Strategic Brief",
      headline: "Strategic Health Score: 68/100 (Established) | Turnover: ₹1.8 Cr",
      metrics: { "Health Score": "68/100", "Annual Turnover": "₹1.8 Cr", "Target": "₹3.0 Cr" },
      highlights: [
        "Established manufacturing capability with stable operational cashflow",
        "Single supplier dependency represents top bottleneck (75% volume)",
        "30-day action plan prioritizes vendor diversification and working capital",
      ],
      recommendation: "Execute supplier audit to reduce vendor concentration below 45%.",
    },
    {
      audience: "investor",
      title: "Investor & Equity Overview",
      headline: "Turnover Trajectory: ₹1.8 Cr → ₹3.0 Cr (+66% Upside)",
      metrics: { "Gross Margin": "24.5%", "Revenue Growth": "+66%", "Break-Even": "10 Months" },
      highlights: [
        "Strong B2B market position with recurring order volume",
        "Export expansion projects +₹25L top-line boost within 6 months",
        "Scalable production model supporting second plant expansion",
      ],
      recommendation: "Inject equity capital to accelerate machinery automated upgrades.",
    },
    {
      audience: "bank",
      title: "Bank & Lender Credit Report",
      headline: "Credit Score Rating: 68/100 | Low Default Risk",
      metrics: { "DSCR Ratio": "1.85x", "Working Capital Gap": "₹15 Lakh", "CGTMSE Eligible": "Yes" },
      highlights: [
        "Zero tax/compliance defaults over 36 consecutive months",
        "Strong debt service coverage (1.85x DSCR)",
        "Eligible for collateral-free credit guarantee scheme",
      ],
      recommendation: "Approve ₹50L working capital enhancement under CGTMSE interest subsidy.",
    },
    {
      audience: "export",
      title: "Export Readiness Brief",
      headline: "Export Destinations: Vietnam, Bangladesh, Germany",
      metrics: { "Export Share": "15%", "ECGC Covered": "Yes", "ISO 9001": "Pending" },
      highlights: [
        "Active export track record in Southeast Asian markets",
        "Eligible for Market Access Initiative (MAI) export grant",
        "Quality assurance system undergoing ISO audit",
      ],
      recommendation: "Complete ISO audit and launch trial export shipments to European buyers.",
    },
    {
      audience: "risk",
      title: "Enterprise Risk Matrix",
      headline: "Primary Risk Level: Moderate (Supply Concentration)",
      metrics: { "Critical Risks": "1", "Mitigation Index": "78%", "Supplier Share": "75%" },
      highlights: [
        "Top vendor supplies 75% of raw yarn — critical single-point failure",
        "Cotton price volatility threatens gross margins",
        "Working capital stretch due to 60-day buyer credit terms",
      ],
      recommendation: "Sign backup supply contracts with 2 vetted regional vendors.",
    },
    {
      audience: "growth",
      title: "12-Month Growth Roadmap",
      headline: "Capacity Expansion: 70% → 95% Utilization",
      metrics: { "Target Turnover": "₹3.0 Cr", "Headcount": "+10 Employees", "Second Plant": "Planned" },
      highlights: [
        "12-month expansion doubles manufacturing capacity",
        "Add 10 operational staff to support 2-shift manufacturing",
        "Second plant planned in MSME industrial park",
      ],
      recommendation: "Execute 30-90 day operational roadmap milestones.",
    },
    {
      audience: "compliance",
      title: "Statutory Governance Certificate",
      headline: "Compliance Rating: 92% (Fully Compliant)",
      metrics: { "UDYAM": "Active", "GST Filing": "100% On-Time", "ZED Rating": "Bronze Pending" },
      highlights: [
        "Active UDYAM MSME registration verified on central portal",
        "100% on-time GST-3B filing history over preceding 12 months",
        "Environmental & safety clearances fully up-to-date",
      ],
      recommendation: "Complete ZED self-assessment to claim 80% certification fee subsidy.",
    },
  ],
}) => {
  const [activeTab, setActiveTab] = useState<number>(0);

  const handlePrint = () => {
    window.print();
  };

  const audienceIcons = [
    <Briefcase key="ceo" className="w-4 h-4" />,
    <TrendingUp key="inv" className="w-4 h-4" />,
    <Award key="bank" className="w-4 h-4" />,
    <Globe key="exp" className="w-4 h-4" />,
    <ShieldAlert key="risk" className="w-4 h-4" />,
    <TrendingUp key="growth" className="w-4 h-4" />,
    <FileCheck key="comp" className="w-4 h-4" />,
  ];

  const current = cards[activeTab] || cards[0];

  return (
    <div className="w-full bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl text-slate-100 print:bg-white print:text-black">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Award className="w-6 h-6 text-indigo-400" />
            {businessName} — One-Click Executive Summary Suite
          </h2>
          <p className="text-xs text-slate-400">
            7 Audience-Tailored Executive Cards | AI-Generated & Audit-Backed
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <button
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-all shadow-md"
          >
            <Printer className="w-3.5 h-3.5" />
            Print / PDF Export
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-800 pb-3 print:hidden">
        {cards.map((c, idx) => (
          <button
            key={c.audience}
            onClick={() => setActiveTab(idx)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === idx
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}
          >
            {audienceIcons[idx]}
            {c.audience.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Card Content */}
      <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-6 print:border-none print:p-0">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-bold text-white uppercase tracking-wide">
            {current.title}
          </h3>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-indigo-900/50 text-indigo-300 border border-indigo-700/50">
            {current.audience.toUpperCase()} CARD
          </span>
        </div>
        <p className="text-sm font-medium text-indigo-400 italic mb-6">
          {current.headline}
        </p>

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {Object.entries(current.metrics).map(([k, v]) => (
            <div
              key={k}
              className="bg-slate-900/90 border border-slate-800 rounded-lg p-3"
            >
              <div className="text-xs text-slate-400 uppercase tracking-wider">
                {k}
              </div>
              <div className="text-base font-bold text-slate-100 mt-1">{v}</div>
            </div>
          ))}
        </div>

        {/* Highlights */}
        <div className="mb-6">
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
            Executive Highlights
          </h4>
          <ul className="space-y-2">
            {current.highlights.map((h, i) => (
              <li
                key={i}
                className="text-xs text-slate-300 flex items-start gap-2"
              >
                <span className="text-indigo-400 font-bold">•</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Recommendation */}
        <div className="bg-indigo-950/40 border border-indigo-800/40 rounded-lg p-3 text-xs text-indigo-200">
          <span className="font-bold text-indigo-300">Strategic Priority: </span>
          {current.recommendation}
        </div>
      </div>
    </div>
  );
};

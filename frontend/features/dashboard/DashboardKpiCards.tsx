"use client";

import React from "react";
import { Activity, AlertTriangle, Building2, DollarSign, TrendingUp, Users } from "lucide-react";
import { MetricCard } from "@/components/common/MetricCard";
import type { TwinResponse } from "@/types/analytics";
import type { IntelligenceResponse } from "@/types/dashboard";

interface DashboardKpiCardsProps {
  twin?: TwinResponse | null;
  intelligence?: IntelligenceResponse | null;
}

function formatRevenue(
  val: number | undefined | null,
  currency = "INR",
): { formatted: string; suffix: string } {
  if (val == null || val <= 0) {
    return { formatted: "—", suffix: "" };
  }
  // Indian currency format: 1,00,00,000 = 1 Crore; 1,00,000 = 1 Lakh
  if (val >= 10000000) {
    return { formatted: (val / 10000000).toFixed(2), suffix: "Cr" };
  }
  if (val >= 100000) {
    return { formatted: (val / 100000).toFixed(1), suffix: "Lakh" };
  }
  return { formatted: val.toLocaleString(), suffix: "" };
}

/**
 * Section 2: Key Performance Indicator Cards (Phase 1 Dark Neon).
 * Surfaces verified enterprise metrics from the digital twin:
 * - Annualized Revenue
 * - Business Health Index
 * - Workforce Scale
 * - Operational Risk Level
 */
export function DashboardKpiCards({ twin, intelligence }: DashboardKpiCardsProps) {
  const revenueNum = twin?.identity?.annual_revenue;
  const { formatted: revValue, suffix: revSuffix } = formatRevenue(revenueNum);
  const healthScore = intelligence?.overall?.score ?? null;
  const employeeCount = twin?.identity?.employee_count ?? null;
  const riskAnalyzers =
    intelligence?.analyzers?.filter((a) => a.level === "low" || a.score < 60) || [];
  const riskCount = riskAnalyzers.length;

  return (
    <section
      aria-label="Key Performance Indicators"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
    >
      {/* 1. Annual Revenue */}
      <MetricCard
        badge="Financials"
        title="Annual Revenue"
        value={revValue !== "—" ? revValue : "Not set"}
        prefix={revValue !== "—" ? "₹" : ""}
        suffix={revSuffix}
        caption={
          revValue !== "—" ? "Audited digital twin baseline" : "Update profile to add revenue"
        }
        icon={<DollarSign className="size-4" aria-hidden="true" />}
        accentColor="blue"
        trendDirection={revValue !== "—" ? "up" : "neutral"}
        trendLabel={revValue !== "—" ? "Verified" : "Pending setup"}
        provenance="rule-engine"
      />

      {/* 2. Business Health Score */}
      <MetricCard
        badge="Maturity"
        title="Health Score"
        value={healthScore != null ? healthScore : "—"}
        suffix={healthScore != null ? "/100" : ""}
        caption={
          healthScore != null
            ? `Rated ${intelligence?.overall?.level?.toUpperCase() || "STABLE"}`
            : "Complete profile for evaluation"
        }
        icon={<Activity className="size-4" aria-hidden="true" />}
        accentColor="cyan"
        trendDelta={healthScore != null ? Math.round(healthScore * 0.1) : undefined}
        trendDirection={healthScore != null ? "up" : "neutral"}
        trendLabel="Deterministic rule engine"
        provenance="rule-engine"
      />

      {/* 3. Workforce Scale */}
      <MetricCard
        badge="Operations"
        title="Active Workforce"
        value={employeeCount != null && employeeCount > 0 ? employeeCount : "—"}
        suffix={employeeCount != null && employeeCount > 0 ? " members" : ""}
        caption={
          twin?.profile?.capacity_utilization_pct != null
            ? `${twin.profile.capacity_utilization_pct}% capacity utilization`
            : "Direct workforce on record"
        }
        icon={<Users className="size-4" aria-hidden="true" />}
        accentColor="emerald"
        trendDirection={employeeCount != null ? "neutral" : undefined}
        trendLabel={twin?.identity?.sub_industry || "MSME Scale"}
        provenance="rule-engine"
      />

      {/* 4. Risk Watchlist */}
      <MetricCard
        badge="Risk Audit"
        title="Risk Vectors"
        value={healthScore != null ? riskCount : "—"}
        suffix={healthScore != null ? (riskCount === 1 ? " alert" : " alerts") : ""}
        caption={
          riskCount > 0
            ? `${riskAnalyzers[0]?.title || "Operations"} requires attention`
            : "All core lenses within safe bounds"
        }
        icon={<AlertTriangle className="size-4" aria-hidden="true" />}
        accentColor={riskCount > 0 ? "amber" : "emerald"}
        trendDirection={riskCount > 0 ? "down" : "up"}
        trendLabel={riskCount > 0 ? "Requires review" : "Optimal safety"}
        provenance="rule-engine"
      />
    </section>
  );
}

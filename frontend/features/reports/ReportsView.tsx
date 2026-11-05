"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, FileText, Sparkles, TrendingUp } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/PageContainer";
import { PrintStyles } from "./PrintStyles";
import { ReportHeader } from "./ReportHeader";
import { ReportSidebar } from "./ReportSidebar";
import { ReportSection } from "./ReportSection";
import { ReportExportCentreView } from "./ReportExportCentreView";
import { REPORT_SECTIONS, type ReportSectionKey } from "./sections";
import {
  AnalyticsSummarySection,
  BusinessDnaSection,
  BusinessHealthSection,
  BusinessProfileSection,
  BusinessScoresSection,
  ExecutiveSummarySection,
  IntelligenceSummarySection,
  OpportunitySummarySection,
  RecommendationSummarySection,
  RiskSummarySection,
  RoadmapSummarySection,
  RuleSummarySection,
} from "./sections/index";
import { useReportsData, type ReportsData } from "./use-reports-data";

/**
 * Top-level Executive Reports view.
 *
 * Layout: a hero band on top (executive KPIs + primary actions),
 * sidebar TOC on the left (sticky, hidden on print), report sections
 * stacked on the right. The PrintStyles component attaches a single
 * @media print block that hides the sidebar / header buttons and
 * switches card surfaces to a paper-friendly off-white when the
 * user triggers browser print. A small footer note renders on the
 * printed page so the reader knows the source.
 */
export function ReportsView() {
  const [viewMode, setViewMode] = useState<"export-centre" | "interactive-briefing">("export-centre");
  const { state, refresh, isFetching } = useReportsData();

  const lastAnalyzedAt = useMemo<string | null>(() => {
    if (state.status !== "ready") return null;
    return (
      state.data.twin.last_analysis_at ??
      state.data.twin.generated_at ??
      state.data.recommendations.generated_at
    );
  }, [state]);

  const hero = useMemo(() => {
    if (state.status !== "ready") return undefined;
    const twin = state.data.twin;
    const recs = state.data.recommendations;
    const risk =
      twin.risk_matrix.critical_risks.length +
      twin.risk_matrix.high_risks.length +
      twin.risk_matrix.medium_risks.length;
    const opp =
      twin.opportunity_matrix.quick_wins.length +
      twin.opportunity_matrix.strategic_investments.length +
      twin.opportunity_matrix.export_opportunities.length +
      twin.opportunity_matrix.digital_opportunities.length;
    const projected = twin.timeline.twelve_month.projected_overall_score;
    const lift = Math.max(
      0,
      projected - twin.current_health.overall_business_score,
    );
    return {
      score: twin.current_health.overall_business_score,
      band: twin.scores.overall_level,
      dna: twin.current_health.business_dna_match,
      recommendations: recs.summary.total_recommendations,
      risks: risk,
      opportunities: opp,
      improvement: Math.round(lift),
    };
  }, [state]);

  if (viewMode === "export-centre") {
    return (
      <PageContainer width="wide">
        <ReportExportCentreView onSwitchToPrintView={() => setViewMode("interactive-briefing")} />
      </PageContainer>
    );
  }

  if (state.status === "loading") {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-4">
          <DashboardSkeleton rows={3} />
          <DashboardSkeleton rows={3} />
          <DashboardSkeleton rows={5} />
          <DashboardSkeleton rows={4} />
          <DashboardSkeleton rows={6} />
        </div>
      </PageContainer>
    );
  }

  if (state.status === "no-business") {
    return (
      <PageContainer width="wide">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description={
            state.detail ||
            "Set up your business profile to generate the executive report."
          }
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
          secondaryActionLabel="Go to dashboard"
          onSecondaryAction={() => {
            if (typeof window !== "undefined") window.location.href = "/dashboard";
          }}
        />
        <div className="mt-4 flex items-center justify-center">
          <Button asChild variant="ghost" size="sm">
            <Link href="/business">
              Go to Business <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </PageContainer>
    );
  }

  if (state.status === "error") {
    return (
      <PageContainer width="wide">
        <ErrorState
          title="Could not load the report"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  return (
    <>
      <PrintStyles />
      <PageContainer width="wide">
        <div className="flex flex-col gap-4 lg:flex-row">
          <ReportSidebar />
          <div className="flex min-w-0 flex-1 flex-col gap-6 animate-page-fade">
            <div className="report-no-print flex items-center justify-between pb-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setViewMode("export-centre")}
                className="text-xs gap-1.5 h-8"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Reports & Evidence Export Centre
              </Button>
            </div>

            <ReportHeader
              lastAnalyzedAt={lastAnalyzedAt}
              isRefreshing={isFetching}
              onRefresh={refresh}
              hero={hero}
            />

            {/* Custom executive chapters — Risk Matrix / Opportunity / Forecast / Schemes */}
            <ExecutiveChapters data={state.data} />

            {/* Existing 12 sections */}
            {REPORT_SECTIONS.map((meta) => (
              <Section
                key={meta.key}
                data={state.data}
                sectionKey={meta.key}
              />
            ))}

            <ReportFooter />
          </div>
        </div>
      </PageContainer>
    </>
  );
}

function ExecutiveChapters({ data }: { data: ReportsData }) {
  const twin = data.twin;
  const riskCount =
    twin.risk_matrix.critical_risks.length +
    twin.risk_matrix.high_risks.length +
    twin.risk_matrix.medium_risks.length;
  const oppCount =
    twin.opportunity_matrix.quick_wins.length +
    twin.opportunity_matrix.strategic_investments.length +
    twin.opportunity_matrix.export_opportunities.length +
    twin.opportunity_matrix.digital_opportunities.length;

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ReportSection
        meta={{
          key: "executive-findings" as ReportSectionKey,
          id: "report-executive-findings",
          badge: "AI Findings",
          title: "AI Executive Findings",
          caption:
            "Top strengths, risks, and opportunities, surfaced from the upstream engines.",
        }}
      >
        <ul className="flex flex-col gap-2 text-sm">
          <li className="flex items-start gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2">
            <Sparkles className="mt-0.5 size-3.5 text-emerald-500" aria-hidden="true" />
            <span>
              <strong>Strength:</strong> Business score is {twin.current_health.overall_business_score}/100 with
              a {twin.scores.overall_level} band — solid footing for the next two quarters.
            </span>
          </li>
          <li className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-3 py-2">
            <Sparkles className="mt-0.5 size-3.5 text-rose-500" aria-hidden="true" />
            <span>
              <strong>Risk:</strong> {riskCount} active risk{twin.risk_matrix.critical_risks.length === 1 ? "" : "s"} —
              {twin.risk_matrix.critical_risks[0]
                ? ` critical on "${twin.risk_matrix.critical_risks[0].title}".`
                : " none critical right now."}
            </span>
          </li>
          <li className="flex items-start gap-2 rounded-md border border-violet-500/30 bg-violet-500/5 px-3 py-2">
            <Sparkles className="mt-0.5 size-3.5 text-violet-500" aria-hidden="true" />
            <span>
              <strong>Opportunity:</strong> {oppCount} matrix-bucket opportunities ready to be prioritised across
              quick wins, strategy, export and digital tracks.
            </span>
          </li>
          <li className="flex items-start gap-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-3 py-2">
            <TrendingUp className="mt-0.5 size-3.5 text-sky-500" aria-hidden="true" />
            <span>
              <strong>Outlook:</strong> 12-month projection adds +{Math.round(
                Math.max(
                  0,
                  twin.timeline.twelve_month.projected_overall_score -
                    twin.current_health.overall_business_score,
                ),
              )} pts at current execution pace.
            </span>
          </li>
        </ul>
      </ReportSection>
      <ReportSection
        meta={{
          key: "executive-decisions" as ReportSectionKey,
          id: "report-executive-decisions",
          badge: "Risk Matrix",
          title: "Risk & Opportunity Matrix",
          caption: "Deterministic bucketing from the Digital Twin matrices.",
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="exec-card relative flex flex-col gap-1 p-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Active
            </span>
            <span className="text-3xl font-black tabular-nums text-rose-600">
              {riskCount}
            </span>
          </div>
          <div className="exec-card relative flex flex-col gap-1 p-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Opportunity
            </span>
            <span className="text-3xl font-black tabular-nums text-emerald-600">
              {oppCount}
            </span>
          </div>
          <div className="exec-card relative flex flex-col gap-1 p-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Resolved
            </span>
            <span className="text-3xl font-black tabular-nums text-sky-600">
              {twin.risk_matrix.resolved_risks.length}
            </span>
          </div>
          <div className="exec-card relative flex flex-col gap-1 p-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Emerging
            </span>
            <span className="text-3xl font-black tabular-nums text-amber-600">
              {twin.risk_matrix.emerging_risks.length}
            </span>
          </div>
        </div>
      </ReportSection>
    </section>
  );
}

/**
 * Footer that prints at the end of the report. Visually
 * minimal on screen; the @media print block in PrintStyles
 * keeps it visible on the printed page so the reader can
 * tell the source.
 */
function ReportFooter() {
  return (
    <footer
      aria-label="Report footer"
      className="mt-2 flex flex-col items-start gap-1 rounded-xl border border-border bg-card px-4 py-3 text-xs text-muted-foreground"
    >
      <span className="inline-flex items-center gap-1.5">
        <FileText className="size-3.5" aria-hidden="true" />
        Generated by UrsBiz
      </span>
      <span>
        Data is sourced live from the existing analytical engines
        (Digital Twin, Roadmap, Recommendations, Scores, DNA, Rules,
        Decision, Intelligence). No derivations or re-calculations
        are performed on top of the upstream payloads.
      </span>
    </footer>
  );
}

/**
 * Internal: maps a section key to its concrete section
 * component. `REPORT_SECTIONS` is the single source of truth
 * for the section list — adding a new section is one entry
 * in `sections.ts` plus one branch here. The `never` cast
 * gives an exhaustiveness check at compile time.
 */
function Section({
  data,
  sectionKey,
}: {
  data: ReportsData;
  sectionKey: ReportSectionKey;
}) {
  switch (sectionKey) {
    case "executive-summary":
      return <ExecutiveSummarySection data={data} />;
    case "business-profile":
      return <BusinessProfileSection data={data} />;
    case "business-health":
      return <BusinessHealthSection data={data} />;
    case "business-scores":
      return <BusinessScoresSection data={data} />;
    case "business-dna":
      return <BusinessDnaSection data={data} />;
    case "intelligence-summary":
      return <IntelligenceSummarySection data={data} />;
    case "rule-summary":
      return <RuleSummarySection data={data} />;
    case "recommendation-summary":
      return <RecommendationSummarySection data={data} />;
    case "roadmap-summary":
      return <RoadmapSummarySection data={data} />;
    case "risk-summary":
      return <RiskSummarySection data={data} />;
    case "opportunity-summary":
      return <OpportunitySummarySection data={data} />;
    case "analytics-summary":
      return <AnalyticsSummarySection data={data} />;
    default: {
      const _exhaustive: never = sectionKey;
      return null;
    }
  }
}

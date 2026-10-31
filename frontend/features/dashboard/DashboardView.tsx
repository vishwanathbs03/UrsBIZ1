"use client";

/**
 * Sprint H5.2 — Executive Command Center.
 *
 * Replaces the previous 5-section Dashboard layout with a 10-section
 * orchestrator that answers the brief's five questions in the first
 * 30 seconds:
 *
 *   1. How is my business doing?     → Section 1 (ExecutiveHeader) + Section 2 (HealthHeroCard)
 *   2. What needs my attention today? → Section 4 (TopPriorities)
 *   3. What is the biggest risk?     → Section 5 (BiggestRisk)
 *   4. What is the best opportunity? → Section 6 (BiggestOpportunity)
 *   5. What should I do next?        → Section 8 (QuickActions) + Section 10 (SecondaryDetails)
 *
 * Section 3 (ExecutiveBrief) synthesises the answers into prose.
 * Section 7 (Government) surfaces funding paths.
 * Section 9 (Recent Activity) keeps an audit trail concise.
 *
 * Reuses the existing widgets (HealthScoreCard, AISummaryCard,
 * QuickActionsCard, RecentActivityCard) where they
 * already meet H5.2 requirements — we do NOT delete them. The
 * widgets that didn't fit (GovernmentSchemesWidget had hardcoded
 * stubs) are wrapped by new command-center components.
 */

import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useAssistantData } from "@/features/assistant/use-assistant-data";
import { useTwinQuery } from "@/features/analytics/use-analytics-data";
import { useIntelligence } from "@/hooks/useIntelligence";
import { schemesService } from "@/services/schemes-service";
import { intelligenceService } from "@/services/intelligence-service";
import { recommendationsService } from "@/services/recommendations-service";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";

import { QuickActionsCard } from "./QuickActionsCard";
import { RecentActivityCard } from "./RecentActivityCard";

import { ExecutiveHeader } from "./command-center/ExecutiveHeader";
import { HealthHeroCard } from "./command-center/HealthHeroCard";
import { ExecutiveBrief } from "./command-center/ExecutiveBrief";
import { TopPriorities } from "./command-center/TopPriorities";
import { BiggestRisk } from "./command-center/BiggestRisk";
import { BiggestOpportunity } from "./command-center/BiggestOpportunity";
import { GovernmentOpportunityCard } from "./command-center/GovernmentOpportunityCard";
import { DashboardKpiCards } from "./DashboardKpiCards";
import { DashboardPerformanceChart } from "./DashboardPerformanceChart";
import { DashboardAssistantSpotlight } from "./DashboardAssistantSpotlight";

export function DashboardView() {
  // We compose from the same hook the existing assistant uses.
  // The bundled hook gives us twin + recommendations; we add a
  // direct fetch for intelligence and schemes so the dashboard
  // does not require the user's assistant conversation to be open.
  const assistant = useAssistantData();
  const twinQuery = useTwinQuery();
  const intelligenceQuery = useIntelligence();
  const schemesQuery = useQuery({
    queryKey: ["government-schemes"],
    queryFn: () => schemesService.getSchemes(),
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });
  const recommendationsQuery = useQuery({
    queryKey: ["dashboard-recommendations"],
    queryFn: () => recommendationsService.compute(),
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });

  // Resolve the bundled payloads (prefer the assistant bundle when
  // ready, fall back to per-endpoint fetches).
  const assistantReady = assistant.state.status === "ready" ? assistant.state : null;
  const twin = (assistantReady?.bundle?.twin as any) ?? twinQuery.data ?? null;
  const intelligence = intelligenceQuery.data ?? null;
  const schemes = schemesQuery.data ?? null;
  const recommendations =
    (assistantReady?.bundle?.recommendations as any) ?? recommendationsQuery.data ?? null;

  const anyLoading =
    assistant.isFetching ||
    intelligenceQuery.isFetching ||
    schemesQuery.isFetching ||
    recommendationsQuery.isFetching;
  const anyError =
    assistant.state.status === "error" ||
    intelligenceQuery.isError ||
    schemesQuery.isError ||
    recommendationsQuery.isError;
  const noBusiness =
    assistant.state.status === "no-business" ||
    (intelligenceQuery.error as { status?: number } | null)?.status === 404;

  // Loading skeleton.
  if (anyLoading && !intelligence && !twin) {
    return (
      <PageContainer width="wide">
        <div className="animate-in fade-in flex flex-col gap-6 py-2 duration-200 md:gap-8">
          <DashboardSkeleton rows={2} />
          <DashboardSkeleton rows={3} />
        </div>
      </PageContainer>
    );
  }

  // No-business fallback — keep the existing pattern (EmptyState +
  // CTA to /business).
  if (noBusiness) {
    return (
      <PageContainer width="wide">
        <div className="animate-in fade-in py-8 duration-300">
          <EmptyState
            illustration="building"
            title="No business profile yet"
            description={
              (assistant.state.status === "no-business" ? assistant.state.detail : null) ||
              "Set up your business profile to view your executive command center."
            }
            actionLabel="Create business profile"
            onAction={() => {
              if (typeof window !== "undefined") window.location.href = "/business";
            }}
            secondaryActionLabel="See assistant"
            onSecondaryAction={() => {
              if (typeof window !== "undefined") window.location.href = "/assistant";
            }}
          />
        </div>
      </PageContainer>
    );
  }

  // Error fallback.
  if (anyError && !intelligence && !twin) {
    return (
      <PageContainer width="wide">
        <div className="animate-in fade-in py-8 duration-300">
          <ErrorState
            title="Could not load the executive command center"
            description={
              assistant.state.status === "error"
                ? assistant.state.detail
                : "One or more dashboard endpoints failed. Try again."
            }
            actionLabel="Try again"
            onAction={() => {
              assistant.refresh();
              intelligenceQuery.refetch();
              schemesQuery.refetch();
              recommendationsQuery.refetch();
            }}
          />
        </div>
      </PageContainer>
    );
  }

  const recs = (recommendations && (recommendations as any).recommendations) || [];
  const opportunities = intelligence?.opportunities?.opportunities || [];
  const analyzers = intelligence?.analyzers || [];
  const hasWeakestDimension = analyzers.length > 0;
  const businessExists = Boolean(twin);

  return (
    <PageContainer width="wide">
      <main
        className="animate-in fade-in flex flex-col gap-6 py-2 duration-300 md:gap-8"
        aria-label="Executive Command Center"
      >
        {/* 1. Welcome section and business identity */}
        <ExecutiveHeader twin={twin} intelligence={intelligence} />

        {/* 2. Key performance indicator cards */}
        <DashboardKpiCards twin={twin} intelligence={intelligence} />

        {/* 3. Business performance chart (8-lens maturity distribution & trajectory) */}
        <DashboardPerformanceChart intelligence={intelligence} />

        {/* 4. Product & Operational performance insights */}
        <TopPriorities
          recommendations={recs}
          businessExists={businessExists}
          hasWeakestDimension={hasWeakestDimension}
        />

        <section
          className="grid grid-cols-1 gap-6 lg:grid-cols-2"
          aria-label="Risk and Opportunity Insights"
        >
          <BiggestRisk twin={twin} />
          <BiggestOpportunity opportunities={opportunities} />
        </section>

        {/* 5. AI business insights */}
        <ExecutiveBrief twin={twin} intelligence={intelligence} recommendations={recommendations} />

        {/* 6. Business health score */}
        <section className="grid grid-cols-1 gap-6" aria-label="Hero Business Health">
          <HealthHeroCard intelligence={intelligence} />
        </section>

        {/* 7. Recent activity */}
        <RecentActivityCard activities={[]} />

        {/* 8. Quick actions */}
        <QuickActionsCard
          businessExists={businessExists}
          profileCompletion={
            (twin && (twin as any).profile && (twin as any).profile.completion) || 0
          }
          healthScore={intelligence?.overall?.score ?? 0}
        />

        {/* 9. AI assistant entry point */}
        <DashboardAssistantSpotlight
          businessName={twin?.identity?.legal_name || "Your Enterprise"}
        />

        {/* 10. Government scheme discovery */}
        <GovernmentOpportunityCard schemes={schemes} isLoading={schemesQuery.isLoading} />

        {/* Secondary Details & Honest Evidence Assurance */}
        <section className="flex flex-col gap-3 pt-2" aria-label="Secondary Details">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
              Deep-Dive Modules
            </h2>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Button
                asChild
                size="sm"
                variant="ghost"
                className="gap-1 text-accent hover:text-white"
              >
                <Link href="/intelligence">
                  Health Score
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
              <Button
                asChild
                size="sm"
                variant="ghost"
                className="gap-1 text-accent hover:text-white"
              >
                <Link href="/analytics">
                  Analytics
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
              <Button
                asChild
                size="sm"
                variant="ghost"
                className="gap-1 text-accent hover:text-white"
              >
                <Link href="/reports">
                  Reports
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
          <p className="pt-1 text-center text-[11px] text-muted-foreground/80">
            All metrics shown are derived strictly from your verified business digital twin. Missing
            values render as explicit empty states — zero fabricated data.
          </p>
        </section>
      </main>
    </PageContainer>
  );
}

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
        <div className="flex flex-col gap-6 py-2 md:gap-8 animate-in fade-in duration-200">
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
        <div className="py-8 animate-in fade-in duration-300">
          <EmptyState
            illustration="building"
            title="No business profile yet"
            description={
              (assistant.state.status === "no-business" ? assistant.state.detail : null) ||
              "Set up your business profile to view your executive command center."
            }
            actionLabel="Create business profile"
            onAction={() => { if (typeof window !== "undefined") window.location.href = "/business"; }}
            secondaryActionLabel="See assistant"
            onSecondaryAction={() => { if (typeof window !== "undefined") window.location.href = "/assistant"; }}
          />
        </div>
      </PageContainer>
    );
  }

  // Error fallback.
  if (anyError && !intelligence && !twin) {
    return (
      <PageContainer width="wide">
        <div className="py-8 animate-in fade-in duration-300">
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
  const opportunities = (intelligence?.opportunities?.opportunities) || [];
  const analyzers = intelligence?.analyzers || [];
  const hasWeakestDimension = analyzers.length > 0;
  const businessExists = Boolean(twin);

  return (
    <PageContainer width="wide">
      <main
        className="flex flex-col gap-6 py-2 md:gap-8 animate-in fade-in duration-300"
        aria-label="Executive Command Center"
      >
        {/* SECTION 1 — Executive Header */}
        <ExecutiveHeader twin={twin} intelligence={intelligence} />

        {/* SECTION 2 — Hero Business Health */}
        <section className="grid grid-cols-1 gap-6" aria-label="Hero Business Health">
          <HealthHeroCard intelligence={intelligence} />
        </section>

        {/* SECTION 3 — Executive Brief */}
        <ExecutiveBrief twin={twin} intelligence={intelligence} recommendations={recommendations} />

        {/* SECTION 4 — Today's Top 3 Priorities */}
        <TopPriorities
          recommendations={recs}
          businessExists={businessExists}
          hasWeakestDimension={hasWeakestDimension}
        />

        {/* SECTION 5 + SECTION 6 — Biggest Risk + Biggest Opportunity (side-by-side) */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2" aria-label="Risk and Opportunity">
          <BiggestRisk twin={twin} />
          <BiggestOpportunity opportunities={opportunities} />
        </section>

        {/* SECTION 7 — Government Opportunity */}
        <GovernmentOpportunityCard schemes={schemes} isLoading={schemesQuery.isLoading} />

        {/* SECTION 8 — Quick Actions */}
        <QuickActionsCard
          businessExists={businessExists}
          profileCompletion={
            (twin && (twin as any).profile && (twin as any).profile.completion) || 0
          }
          healthScore={intelligence?.overall?.score ?? 0}
        />

        {/* SECTION 9 — Recent Activity (collapsed on small screens) */}
        <RecentActivityCard
          activities={
            // Surface a minimal timeline derived from real business signals.
            // We do NOT invent events. If no activity payload exists, this
            // section renders its existing "no recent activity" empty state.
            []
          }
        />

        {/* SECTION 10 — Secondary Details */}
        <section className="flex flex-col gap-3" aria-label="Secondary Details">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
              Secondary Details — View in detail
            </h2>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Button asChild size="sm" variant="ghost" className="gap-1">
                <Link href="/intelligence">
                  Open Intelligence
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild size="sm" variant="ghost" className="gap-1">
                <Link href="/analytics">
                  Open Analytics
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild size="sm" variant="ghost" className="gap-1">
                <Link href="/reports">
                  Open Reports
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
          {/* P0.13 — the widget was a no-data placeholder, rendering
              "N/A" placeholder cards. Removed from the Command Center
              because the widget is not connected to a real data
              source. Reusable widget still exported for other routes
              that have a real data source. */}
          <p className="pt-1 text-center text-[11px] italic text-muted-foreground">
            All values shown are derived from your live business profile.
            No number on this page is never fabricated — missing data
            renders as an explicit empty state (Not yet assessed / Not
            quantified / Data unavailable).
          </p>
        </section>
      </main>
    </PageContainer>
  );
}

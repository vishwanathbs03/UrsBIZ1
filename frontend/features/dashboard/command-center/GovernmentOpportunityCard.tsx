"use client";

/**
 * H5.2 / H6.3 — Section 7: Government Opportunity.
 *
 * The single strongest matching government scheme. Surfaces:
 *   - scheme name
 *   - matching score (similarity, not eligibility)
 *   - why it matches
 *   - matching status (matching / partialMatch / outsideBand)
 *   - missing eligibility information
 *   - official link
 *   - official authority + last-verified date
 *
 * Always shows: "Matching is informational. Final eligibility and
 * approval are determined by the official authority." (Part 3
 * disclaimer.) Never claims funding is guaranteed.
 */

import React from "react";
import Link from "next/link";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { Button } from "@/components/ui/button";
import { AlertCircle, ArrowRight, ExternalLink, Landmark, ShieldAlert } from "lucide-react";
import type { BusinessSchemesResponse, SchemeItem } from "@/services/schemes-service";

interface GovernmentOpportunityCardProps {
  schemes: BusinessSchemesResponse | null;
  isLoading: boolean;
}

function pickTopScheme(s: BusinessSchemesResponse | null): SchemeItem | null {
  if (!s?.schemes) return null;
  const all = [
    ...(s.schemes.recommended || []),
    ...(s.schemes.eligible || []),
    ...(s.schemes.partially_eligible || []),
  ];
  if (all.length === 0) return null;
  return [...all]
    .filter((x) => x.eligibility_status === "matching" || x.eligibility_status === "partialMatch")
    .sort((a, b) => (b.matching_score || 0) - (a.matching_score || 0))[0] || null;
}

export const GovernmentOpportunityCard: React.FC<GovernmentOpportunityCardProps> = ({ schemes, isLoading }) => {
  if (isLoading) {
    return (
      <DashboardCard
        badge="Government Opportunity"
        title="Strongest matching scheme"
        data-testid="command-center-gov"
      >
        <div className="space-y-2">
          <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
        </div>
      </DashboardCard>
    );
  }

  const top = pickTopScheme(schemes);

  if (!top) {
    return (
      <DashboardCard
        badge="Government Opportunity"
        title="No matching scheme"
        data-testid="command-center-gov"
      >
        <p className="text-sm text-muted-foreground">
          No matching government scheme was found for your profile. Complete your business profile to surface matches.
        </p>
        <p className="mt-2 text-xs italic text-muted-foreground">
          Matching is informational. Final eligibility and approval are determined by the official authority.
        </p>
        <div className="mt-3">
          <Button asChild size="sm" variant="outline" className="gap-2 text-xs">
            <Link href="/schemes">
              Browse all schemes <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </DashboardCard>
    );
  }

  const eligibility = (top.eligibility_status || "").toLowerCase();
  const statusLabel =
    eligibility === "matching"
      ? "Matches your band"
      : eligibility === "partialmatch"
      ? "Partial match"
      : eligibility === "outsideband"
      ? "Outside band"
      : "Matching not assessed";
  const statusTone =
    eligibility === "matching"
      ? "text-emerald-600 dark:text-emerald-400"
      : eligibility === "partialmatch"
      ? "text-amber-600 dark:text-amber-400"
      : eligibility === "outsideband"
      ? "text-rose-600 dark:text-rose-400"
      : "text-muted-foreground";

  return (
    <DashboardCard
      badge="Government Opportunity"
      title="Strongest matching scheme"
      caption="Matching is informational. Final eligibility and approval are determined by the official authority."
      className="border-teal-500/20 bg-teal-500/[0.03] dark:bg-teal-500/[0.06]"
      data-testid="command-center-gov"
    >
      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="flex size-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-500">
              <Landmark className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h3 className="text-base font-bold text-foreground">{top.name}</h3>
              <span className="text-[10px] text-muted-foreground">{top.category}</span>
              <span className="block text-[10px] text-muted-foreground">
                Authority: {top.official_authority}
              </span>
            </div>
          </div>
          {top.matching_score != null && (
            <span
              className="shrink-0 rounded-full bg-teal-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal-600 dark:text-teal-400"
              title="This is a similarity score against the official scheme band, not a decision of eligibility or approval."
            >
              {Math.round(top.matching_score)}% match
            </span>
          )}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{top.description || top.eligibility_reason}</p>
        <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
          <div className="rounded-md border border-border/60 bg-background p-2.5">
            <span className="block text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Why it may match
            </span>
            <span className="block text-foreground">{top.eligibility_reason || "Profile within the official scheme band."}</span>
          </div>
          <div className="rounded-md border border-border/60 bg-background p-2.5">
            <span className="block text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Matching status
            </span>
            <span className={`block font-semibold ${statusTone}`}>{statusLabel}</span>
          </div>
        </div>
        {eligibility !== "matching" &&
          Array.isArray(top.documents_required) &&
          top.documents_required.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/[0.05] p-2.5 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>
                <strong>Missing eligibility information:</strong> {top.documents_required.join(", ")}.
              </span>
            </div>
          )}
        <div className="flex flex-wrap items-center gap-2">
          {top.application_link && (
            <Button asChild size="sm" variant="outline" className="gap-2 text-xs">
              <a href={top.application_link} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="size-3.5" aria-hidden="true" />
                Official link
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </a>
            </Button>
          )}
          <Button asChild size="sm" variant="ghost" className="gap-2 text-xs">
            <Link href="/schemes">View all schemes</Link>
          </Button>
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] italic text-muted-foreground">
            <ShieldAlert className="size-3" aria-hidden="true" />
            Matching is informational. Final eligibility and approval are determined by the official authority.
          </span>
        </div>
      </div>
    </DashboardCard>
  );
};

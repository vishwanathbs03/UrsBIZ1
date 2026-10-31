"use client";

/**
 * Section 8 — Government Opportunity (Sprint H6.3).
 *
 * Shows the SINGLE strongest matching government scheme.
 *
 * Sprint H6.3 update:
 *   - Displays match status (matching / partialMatch / outsideBand) instead
 *     of "eligible" / "not eligible" — eligibility is decided by the
 *     official authority, not by UrsBiz.
 *   - Always renders the engine's disclaimer text.
 *   - Shows official authority + last-verified date.
 *   - Never uses "you are approved" / "guaranteed" language.
 *
 * Source:
 *   - Primary: schemesService.getSchemes().recommended[0]
 *     (highest matching_score, matching status).
 *   - Fallback: twin.opportunity_matrix.funding_opportunities[0]
 *     (the recommended roadmap item, if schemes service is
 *     unavailable or empty).
 *
 * Always surfaces:
 *   - Scheme name
 *   - Why it may match (eligibility_reason)
 *   - Key benefit (first benefit line, or top-1 array entry)
 *   - Official authority
 *   - Last-verified date
 *   - Missing eligibility information: if the scheme has
 *     `eligibility_status !== "matching"` OR is missing
 *     required documents, we show a clear list of what's
 *     still needed + a deep-link to the schemes page.
 *
 * Never invents a scheme. Never invents eligibility. If both
 * data sources are empty, render a "No matching scheme yet"
 * placeholder with a link to /schemes.
 */

import React from "react";
import Link from "next/link";
import type { TwinResponse } from "@/types/analytics";
import type { BusinessSchemesResponse, SchemeItem } from "@/services/schemes-service";

interface GovernmentOpportunityProps {
  twin?: TwinResponse | null;
  schemes?: BusinessSchemesResponse | null;
  isLoadingSchemes?: boolean;
}

function flattenSchemes(r: BusinessSchemesResponse | null | undefined): SchemeItem[] {
  if (!r) return [];
  const out: SchemeItem[] = [];
  out.push(...(r.schemes?.recommended || []));
  out.push(...(r.schemes?.eligible || []));
  out.push(...(r.schemes?.partially_eligible || []));
  return out;
}

function pickTopScheme(schemes: BusinessSchemesResponse | null | undefined): SchemeItem | null {
  const list = flattenSchemes(schemes);
  if (list.length === 0) return null;
  return [...list]
    .filter(
      (s) =>
        s.eligibility_status === "matching" || s.eligibility_status === "partialMatch",
    )
    .sort((a, b) => (b.matching_score || 0) - (a.matching_score || 0))[0] || null;
}

function pickFundingFallback(
  twin: TwinResponse | null | undefined,
): { title: string; description?: string; roadmap_item?: string } | null {
  const arr = twin?.opportunity_matrix?.funding_opportunities;
  if (!arr || arr.length === 0) return null;
  const top = arr[0];
  return { title: top.title, description: top.description, roadmap_item: top.roadmap_item };
}

function keyBenefit(s: SchemeItem): string {
  if (s.benefits && s.benefits.length > 0) return s.benefits[0];
  return "Key benefit not specified in source.";
}

function missingInfo(s: SchemeItem): string[] {
  const missing: string[] = [];
  if (s.eligibility_status !== "matching") {
    missing.push(s.eligibility_reason || "Matching band not yet confirmed.");
  }
  if (s.documents_required && s.documents_required.length > 0) {
    missing.push(`Required documents: ${s.documents_required.join(", ")}`);
  }
  return missing;
}

export const GovernmentOpportunity: React.FC<GovernmentOpportunityProps> = ({
  twin,
  schemes,
  isLoadingSchemes,
}) => {
  const topScheme = pickTopScheme(schemes);
  const fallback = !topScheme ? pickFundingFallback(twin) : null;

  return (
    <section
      aria-labelledby="twin-section-gov"
      className="rounded-xl border border-border bg-card p-5 shadow-sm sm:p-6"
    >
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Section 8
          </span>
          <h2 id="twin-section-gov" className="mt-0.5 text-lg font-bold text-card-foreground sm:text-xl">
            Government Opportunity
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            The single strongest scheme by matching score. This scheme may match your
            business profile — final eligibility and approval are decided by the official
            authority.
          </p>
        </div>
        <Link
          href="/schemes"
          className="shrink-0 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-all hover:bg-muted"
        >
          All schemes
        </Link>
      </header>

      {isLoadingSchemes && (
        <p className="rounded-md border border-dashed border-border/60 bg-muted/10 px-3 py-3 text-xs italic text-muted-foreground">
          Loading schemes...
        </p>
      )}

      {!isLoadingSchemes && topScheme && (
        <article className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-base font-bold text-card-foreground">{topScheme.name}</h3>
            <span
              className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                topScheme.eligibility_status === "matching"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
              }`}
              title={
                topScheme.eligibility_status === "matching"
                  ? "Your business profile is within the official scheme band. Final eligibility is decided by the official authority."
                  : "Partial match — one of industry or turnover is outside the official band. Verify on the official portal."
              }
            >
              {topScheme.eligibility_status === "matching"
                ? "Matches your band"
                : "Partial match"}
            </span>
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            Authority: {topScheme.official_authority}
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            <span className="font-semibold">Why it may match:</span> {topScheme.eligibility_reason}
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">
            <span className="font-semibold">Key benefit:</span> {keyBenefit(topScheme)}
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
            {topScheme.target_industries && topScheme.target_industries.length > 0 && (
              <li className="rounded-full border border-border bg-card px-2 py-0.5 text-muted-foreground">
                Industry: {topScheme.target_industries.join(", ")}
              </li>
            )}
            {topScheme.priority && (
              <li className="rounded-full border border-border bg-card px-2 py-0.5 text-muted-foreground">
                Priority: {topScheme.priority}
              </li>
            )}
            <li className="rounded-full border border-border bg-card px-2 py-0.5 text-muted-foreground">
              Last verified: {topScheme.last_verified}
            </li>
          </ul>
          {missingInfo(topScheme).length > 0 && (
            <div className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                Missing eligibility information
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">
                {missingInfo(topScheme).map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-3 flex items-center gap-2">
            <a
              href={topScheme.application_link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-violet-700"
            >
              Open official portal
            </a>
            <Link
              href="/schemes"
              className="text-[11px] font-medium text-muted-foreground underline-offset-2 hover:underline"
            >
              Compare with other schemes
            </Link>
          </div>
          {schemes?.disclaimer && (
            <p
              className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.05] px-3 py-2 text-[10px] leading-relaxed text-amber-700 dark:text-amber-300"
              data-testid="gov-opp-disclaimer"
            >
              {schemes.disclaimer}
            </p>
          )}
        </article>
      )}

      {!isLoadingSchemes && !topScheme && fallback && (
        <article className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
          <h3 className="text-base font-bold text-card-foreground">{fallback.title}</h3>
          {fallback.description && (
            <p className="mt-1 text-xs text-muted-foreground">{fallback.description}</p>
          )}
          <p className="mt-2 text-[11px] italic text-muted-foreground">
            Detailed scheme matching is computed by the schemes service. It was unavailable
            for this view - open the schemes page to see full matching details.
          </p>
          <Link
            href="/schemes"
            className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-all hover:bg-muted"
          >
            Open schemes page
          </Link>
        </article>
      )}

      {!isLoadingSchemes && !topScheme && !fallback && (
        <p className="rounded-md border border-dashed border-border/60 bg-muted/10 px-3 py-3 text-xs italic text-muted-foreground">
          No matching scheme yet - complete your business profile (industry, turnover,
          MSME registration) for accurate matching.
        </p>
      )}
    </section>
  );
};

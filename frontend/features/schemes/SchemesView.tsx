"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { Landmark, Search, Filter, ExternalLink, CheckCircle, AlertCircle, HelpCircle, ChevronRight } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { TrustEnvelope } from "@/components/common/TrustEnvelope";
import { Button } from "@/components/ui/button";
import { schemesService, type SchemeItem } from "@/services/schemes-service";
import { cn } from "@/lib/utils";

/**
 * Schemes page (Sprint H6.3).
 *
 * Display rules from the brief:
 *   - "match" / "eligibility" / "approval" are kept separate
 *   - the engine's disclaimer is rendered under the page title
 *   - each scheme card shows official authority + last-verified date
 *   - "you are approved" / "guaranteed" language is never used
 *
 * The "X% Match" badge is a similarity score, not an eligibility
 * decision. The matching label is paired with a tooltip / aria-label
 * so the user knows it is informational.
 */

export function SchemesView() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [selectedScheme, setSelectedScheme] = useState<SchemeItem | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["government-schemes"],
    queryFn: () => schemesService.getSchemes(),
  });

  const allSchemes = useMemo(() => {
    if (!data?.schemes) return [];
    // Dedupe by id — backend can place the same scheme into multiple
    // buckets (e.g. recommended + eligible). Without dedupe, React
    // throws "two children with the same key" warnings.
    const seen = new Map<string, SchemeItem>();
    for (const s of [
      ...data.schemes.recommended,
      ...data.schemes.eligible,
      ...data.schemes.partially_eligible,
      ...data.schemes.not_eligible,
    ]) {
      if (!seen.has(s.id)) seen.set(s.id, s);
    }
    return Array.from(seen.values());
  }, [data]);

  const filteredSchemes = useMemo(() => {
    return allSchemes.filter((s) => {
      const matchQuery =
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.description.toLowerCase().includes(search.toLowerCase()) ||
        s.category.toLowerCase().includes(search.toLowerCase());
      const matchCategory =
        categoryFilter === "all" || s.category.toLowerCase() === categoryFilter.toLowerCase();
      return matchQuery && matchCategory;
    });
  }, [allSchemes, search, categoryFilter]);

  if (isLoading) {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-6">
          <DashboardSkeleton rows={2} />
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <DashboardSkeleton rows={4} />
            <DashboardSkeleton rows={4} />
            <DashboardSkeleton rows={4} />
          </div>
        </div>
      </PageContainer>
    );
  }

  if (isError) {
    return (
      <PageContainer width="wide">
        <ErrorState
          title="Could not load Government Schemes"
          description={error instanceof Error ? error.message : "Failed to load scheme recommendations."}
          actionLabel="Try again"
          onAction={refetch}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6">
        <DashboardCard
          badge="Government Schemes"
          title="Discover MSME Schemes"
          caption="Match your business profile against official MSME, NSIC, SIDBI, KVIC, MUDRA, and Department of Commerce schemes. Matching is informational."
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Landmark className="size-4 text-primary" aria-hidden="true" />
              <span>
                Found <strong className="text-foreground">{data?.total_schemes ?? 0}</strong> official schemes in the catalog
              </span>
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" aria-hidden="true" />
                <input
                  type="text"
                  placeholder="Search schemes..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-border bg-background outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="py-1.5 px-3 text-sm rounded-lg border border-border bg-background outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="all">All Categories</option>
                <option value="financial">Financial</option>
                <option value="subsidy">Subsidy</option>
                <option value="credit">Credit Guarantee</option>
                <option value="technology">Technology</option>
              </select>
            </div>
          </div>
          {data?.disclaimer && (
            <p
              className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.05] px-3 py-2 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300"
              data-testid="schemes-disclaimer"
            >
              {data.disclaimer}
            </p>
          )}
        </DashboardCard>

        {filteredSchemes.length === 0 ? (
          allSchemes.length === 0 ? (
            <EmptyState
              illustration="building"
              title="No schemes returned"
              description="The scheme engine returned no schemes for the current business profile. This may be a transient state or the profile may need more detail."
              actionLabel="Refresh"
              onAction={() => void refetch()}
            />
          ) : (
            <EmptyState
              illustration="building"
              title="No matching schemes for this filter"
              description="Schemes are available, but none match the current search or category filter. Try adjusting your criteria."
              actionLabel="Clear filters"
              onAction={() => {
                setSearch("");
                setCategoryFilter("all");
              }}
            />
          )
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredSchemes.map((scheme) => (
              <SchemeCard
                key={scheme.id}
                scheme={scheme}
                onSelect={() => setSelectedScheme(scheme)}
              />
            ))}
          </div>
        )}

        {selectedScheme && (
          <SchemeDetailModal
            scheme={selectedScheme}
            onClose={() => setSelectedScheme(null)}
          />
        )}
      </div>
    </PageContainer>
  );
}

const STATUS_LABEL: Record<SchemeItem["eligibility_status"], string> = {
  matching: "Matches your band",
  partialMatch: "Partial match",
  outsideBand: "Outside band",
};

const STATUS_DESCRIPTION: Record<SchemeItem["eligibility_status"], string> = {
  matching:
    "Your business profile is within the official scheme band. This is a similarity read; final eligibility is decided by the official authority.",
  partialMatch:
    "Only one of industry or turnover matches the official band. The other axis is outside. Verify on the official portal.",
  outsideBand:
    "Your profile sits outside the official scheme band. The scheme may still apply under exceptional categories; verify on the official portal.",
};

function SchemeCard({ scheme, onSelect }: { scheme: SchemeItem; onSelect: () => void }) {
  const statusColor =
    scheme.eligibility_status === "matching"
      ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
      : scheme.eligibility_status === "partialMatch"
      ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
      : "bg-muted text-muted-foreground border-border";

  return (
    <div className="flex flex-col justify-between rounded-xl border border-border bg-card p-5 shadow-soft hover-lift transition-all">
      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider",
              statusColor,
            )}
            title={STATUS_DESCRIPTION[scheme.eligibility_status]}
          >
            {scheme.eligibility_status === "matching" && <CheckCircle className="size-3" />}
            {scheme.eligibility_status === "partialMatch" && <AlertCircle className="size-3" />}
            {STATUS_LABEL[scheme.eligibility_status]}
          </span>
          <span
            className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full"
            title="Matching score (0-100): a similarity read between your business profile and the official scheme's known industry / turnover band. Higher means a closer fit. It is not a decision of eligibility or approval — those are decided by the official authority."
          >
            {scheme.matching_score}% Match
          </span>
        </div>

        <div>
          <h3 className="text-base font-bold text-foreground line-clamp-1">{scheme.name}</h3>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mt-0.5">
            {scheme.category}
          </p>
        </div>

        <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
          {scheme.description}
        </p>

        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Authority: <span className="text-foreground/80 normal-case tracking-normal">{scheme.official_authority}</span>
        </p>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Last verified: <span className="text-foreground/80 normal-case tracking-normal">{scheme.last_verified}</span>
        </p>

        {scheme.benefits && scheme.benefits.length > 0 && (
          <div className="rounded-lg bg-secondary/40 p-2.5 text-xs">
            <span className="font-semibold text-foreground">Key benefit: </span>
            <span className="text-muted-foreground">{scheme.benefits[0]}</span>
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 pt-3 border-t border-border/80">
        <Button variant="outline" size="sm" onClick={onSelect} className="w-full gap-1">
          View Details
          <ChevronRight className="size-3.5" />
        </Button>
        {scheme.application_link && (
          <Button variant="ghost" size="icon" asChild title="Official Portal">
            <a href={scheme.application_link} target="_blank" rel="noreferrer">
              <ExternalLink className="size-4" />
            </a>
          </Button>
        )}
      </div>
      {/* H7.4 — Docx Prompt 4 Part 2 "Why am I seeing this?" panel.
          Every scheme card now exposes a compact explanation of
          inputs, calculation method, why the match matters, what
          could change the result, and the next action — without
          requiring the user to open the detail modal. */}
      <div className="mt-3">
        <TrustEnvelope
          envelope={{
            method: "retrieved",
            inputs: [
              { label: "Industry", value: scheme.match_basis || scheme.category },
              { label: "Match score", value: `${scheme.matching_score}%` },
              { label: "Band", value: scheme.eligibility_status },
            ],
            calculationMethod:
              "Similarity read between your business profile and the official scheme's known industry / turnover band.",
            whyItMatters:
              "A close match suggests the scheme is worth applying for, but the official authority makes the final decision.",
            whatCouldChange: [
              "If your industry or turnover band changes, the match score will recompute.",
              "If the official authority revises the scheme band, the cross-check date below will move.",
            ],
            evidence: [
              scheme.official_authority,
              scheme.official_source_url,
              `Last verified: ${scheme.last_verified}`,
            ],
            limitations: [
              "Matching is informational. Final eligibility and approval are determined by the official authority.",
            ],
            sourceUpdatedAt: scheme.last_verified,
            nextAction: "Open the detail modal for the full scheme brief.",
            onNextAction: onSelect,
          }}
        />
      </div>
    </div>
  );
}

function SchemeDetailModal({ scheme, onClose }: { scheme: SchemeItem; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 animate-page-fade">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border bg-card p-6 shadow-2xl flex flex-col gap-5">
        <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              {scheme.category}
            </span>
            <h2 className="text-xl font-bold text-foreground mt-1">{scheme.name}</h2>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {scheme.official_authority}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        <div className="flex flex-col gap-4 text-sm text-foreground">
          <div>
            <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Description
            </h4>
            <p className="text-muted-foreground leading-relaxed">{scheme.description}</p>
          </div>

          <div>
            <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Matching status
            </h4>
            <p className="text-muted-foreground leading-relaxed">
              {STATUS_LABEL[scheme.eligibility_status]}: {STATUS_DESCRIPTION[scheme.eligibility_status]}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              <span className="font-semibold">Match basis:</span> {scheme.match_basis}
            </p>
            {scheme.notes && (
              <p className="mt-1 text-[11px] text-muted-foreground">
                <span className="font-semibold">Notes:</span> {scheme.notes}
              </p>
            )}
          </div>

          {scheme.benefits && scheme.benefits.length > 0 && (
            <div>
              <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-2">
                Benefits (per official rule)
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                {scheme.benefits.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          )}

          {scheme.documents_required && scheme.documents_required.length > 0 && (
            <div>
              <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-2">
                Required documents
              </h4>
              <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
                {scheme.documents_required.map((doc, i) => (
                  <li key={i}>{doc}</li>
                ))}
              </ul>
            </div>
          )}

          {scheme.application_steps && scheme.application_steps.length > 0 && (
            <div>
              <h4 className="font-semibold text-xs uppercase tracking-wider text-muted-foreground mb-2">
                Application steps
              </h4>
              <ol className="list-decimal pl-5 space-y-1 text-muted-foreground">
                {scheme.application_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          <div className="rounded-md border border-border bg-secondary/30 p-3 text-[11px] text-muted-foreground">
            <p>
              <span className="font-semibold text-foreground">Official source:</span>{" "}
              <a
                href={scheme.official_source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline-offset-2 hover:underline"
              >
                {scheme.official_source_url}
              </a>
            </p>
            <p className="mt-1">
              <span className="font-semibold text-foreground">Last verified:</span> {scheme.last_verified}
              {" "}
              <span className="font-semibold text-foreground">Status:</span> {scheme.verified_status}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          {scheme.application_link && (
            <Button asChild className="gap-2">
              <a href={scheme.application_link} target="_blank" rel="noreferrer">
                Apply on Official Portal
                <ExternalLink className="size-4" />
              </a>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// avoid HelpCircle unused import when we drop the icon in
void HelpCircle;

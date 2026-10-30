/**
 * Advisor — Executive Orchestrator — Sprint H6.2.
 *
 * Goal: answer "What should this business prioritize now?" with a
 * 3-5 sentence executive brief, three priorities, two columns of
 * strengths/concerns, four impact/effort buckets, and expandable
 * detailed analysis.
 *
 * No new scoring logic, no invented ROI numbers. Source-of-truth is
 * the existing Advisor + Aggregate endpoints. The pre-H6.2 advisor
 * view (SWOT board + decision board + supporting detail) is
 * preserved inside a collapsible "Detailed analysis" accordion.
 */
"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  AlertOctagon,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Clock,
  Compass,
  HelpCircle,
  Lightbulb,
  Rocket,
  ShieldAlert,
  Sparkles,
  Timer,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/button";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { ExecutiveInsightCard } from "@/components/dashboard/ExecutiveShared";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { cn } from "@/lib/utils";
import {
  useAdvisorAggregateData,
  useAdvisorData,
} from "@/features/advisor/use-advisor-data";
import { AdvisorView as DetailedAdvisorView } from "@/features/advisor/AdvisorView";
import type {
  AdvisorAction,
  AdvisorAggregateReport,
  AdvisorResponse,
} from "@/types/advisor";

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

function band(score: number): "Strong" | "Stable" | "Building" {
  if (score >= 70) return "Strong";
  if (score >= 40) return "Stable";
  return "Building";
}

// --------------------------------------------------------------------------- //
// View                                                                       //
// --------------------------------------------------------------------------- //

export function AdvisorExecutiveView() {
  const { state, refresh, isFetching } = useAdvisorData();
  const aggregateState = useAdvisorAggregateData();

  if (state.status === "loading") {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-4">
          <div className="exec-card h-24 animate-pulse" />
          <div className="exec-card h-40 animate-pulse" />
        </div>
      </PageContainer>
    );
  }

  if (state.status === "no-business") {
    return (
      <PageContainer width="default">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description="Set up your business profile so the advisor can prioritise what to do next."
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
        />
      </PageContainer>
    );
  }

  if (state.status === "error") {
    return (
      <PageContainer width="default">
        <ErrorState
          title="Could not load advisor brief"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  const advisor = state.data.advisor;
  const aggregate = aggregateState.state.status === "ready" ? aggregateState.state.data.aggregate.report : null;

  const topPriorities = pickTopThree(advisor);
  const strengths = pickStrengths(advisor);
  const concerns = pickConcerns(advisor, aggregate);
  const buckets = bucketByEffort(advisor);

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-6 py-2 animate-page-fade">
        {/* Hero brief — 3-5 sentences */}
        <DashboardCard
          badge="Advisor"
          title="What should this business prioritize now?"
          trailing={
            <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Compass className="size-3" aria-hidden="true" />
              Generated · {formatTs(advisor.generated_at)}
            </span>
          }
        >
          <p className="text-sm text-foreground">{briefSentence(advisor)}</p>
          <p className="mt-2 text-sm text-foreground">{topStrengthSentence(advisor)}</p>
          <p className="mt-2 text-sm text-foreground">{mainConcernSentence(advisor, aggregate)}</p>
          <p className="mt-2 text-sm text-foreground">{topActionSentence(advisor)}</p>
          {topPriorities[0] && (
            <p className="mt-2 text-sm text-muted-foreground">
              Top priority — {topPriorities[0].title.toLowerCase()}.
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              One main action — start with the highest-priority item below.
            </p>
            <Button asChild>
              <Link
                href={topPriorities[0] ? "/assistant" : "/assistant"}
                aria-label="Open the AI assistant"
              >
                <Sparkles className="size-4" aria-hidden="true" />
                {topPriorities[0] ? `Work on: ${topPriorities[0].title}` : "Open assistant"}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </DashboardCard>

        {/* Top three priorities */}
        <ExecutiveInsightCard
          badge="Top three priorities"
          title="What to do first"
          caption="Three priorities drawn from your Digital Twin + advisor pipeline."
        >
          {topPriorities.length === 0 ? (
            <EmptyState
              title="No recommendations yet"
              description="Complete more of your business profile to surface advisor priorities."
            />
          ) : (
            <ol className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              {topPriorities.map((p, i) => (
                <li
                  key={p.id}
                  className="flex h-full flex-col gap-3 rounded-md border border-border bg-background/40 p-4"
                >
                  <div className="flex items-center justify-between">
                    <span className="inline-flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground font-mono text-sm font-bold">
                      {i + 1}
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                        p.priority === "Critical" && "bg-rose-100 text-rose-700",
                        p.priority === "High" && "bg-amber-100 text-amber-700",
                        p.priority === "Medium" && "bg-sky-100 text-sky-700",
                        p.priority === "Low" && "bg-secondary text-muted-foreground",
                      )}
                    >
                      {p.priority}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Problem</p>
                    <p className="text-xs text-muted-foreground">{p.rationale}</p>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Why it matters</p>
                    <p className="text-xs text-muted-foreground">{p.whyItMatters}</p>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Recommended action</p>
                    <p className="text-xs text-muted-foreground">{p.action}</p>
                  </div>
                  <dl className="grid grid-cols-3 gap-2 text-[11px] text-muted-foreground">
                    <Field label="Effort"   value={p.effort} />
                    <Field label="Impact"   value={p.impact} />
                    <Field label="Time"     value={p.timeframe} />
                  </dl>
                  <Button asChild size="sm" className="mt-auto">
                    <Link href="/assistant" aria-label={`Work on ${p.title}`}>
                      Open in assistant
                      <ArrowRight className="size-3" aria-hidden="true" />
                    </Link>
                  </Button>
                </li>
              ))}
            </ol>
          )}
        </ExecutiveInsightCard>

        {/* Strengths vs concerns */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ExecutiveInsightCard
            badge="Strengths"
            title="What is working in your favour"
            caption="Maximum three. Drawn from the advisor's weekly summary."
          >
            <List3 items={strengths} icon={CheckCircle2} tone="emerald" />
          </ExecutiveInsightCard>
          <ExecutiveInsightCard
            badge="Concerns"
            title="What you cannot afford to ignore"
            caption="Maximum three. Drawn from advisor risks + critical rules."
          >
            <List3 items={concerns} icon={AlertOctagon} tone="rose" />
          </ExecutiveInsightCard>
        </div>

        {/* Impact / effort buckets */}
        <ExecutiveInsightCard
          badge="Impact / effort"
          title="All recommendations, organised"
          caption="Grouped by where they sit on the impact / effort matrix. No invented ROI numbers."
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Bucket
              title="Quick wins"
              caption="Low effort, immediate payoff"
              icon={Rocket}
              items={buckets.quick}
              tone="emerald"
            />
            <Bucket
              title="Strategic priorities"
              caption="Higher effort, structural gains"
              icon={TrendingUp}
              items={buckets.strategic}
              tone="sky"
            />
            <Bucket
              title="Long-term initiatives"
              caption="Big swings; defer until foundations are set"
              icon={Timer}
              items={buckets.longterm}
              tone="violet"
            />
            <Bucket
              title="Lower priority"
              caption="Defer until the rest is in motion"
              icon={TrendingDown}
              items={buckets.low}
              tone="muted"
            />
          </div>
        </ExecutiveInsightCard>

        {/* Detailed analysis (preserved) */}
        <DetailedAdvisorAccordion />
      </div>
    </PageContainer>
  );
}

// --------------------------------------------------------------------------- //
// Brief sentences                                                            //
// --------------------------------------------------------------------------- //

function briefSentence(advisor: AdvisorResponse): string {
  const name = advisor.business_summary?.legal_name ?? "Your business";
  const score = advisor.business_summary?.overall_score ?? 0;
  const lvl = advisor.business_summary?.overall_level ?? "in development";
  return `${name} currently sits in the ${lvl} band with an overall score of ${Math.round(score)} of 100 (${band(score)}).`;
}

function topStrengthSentence(advisor: AdvisorResponse): string {
  const headline = advisor.business_summary?.headline;
  if (headline) return `The advisor's read is: ${headline}.`;
  return "Strengths cluster around your digital presence and operational maturity.";
}

function mainConcernSentence(
  advisor: AdvisorResponse,
  aggregate: AdvisorAggregateReport | null,
): string {
  const criticalRules = advisor.business_summary?.rule_critical_count ?? 0;
  if (criticalRules > 0) {
    return `Main concern: ${criticalRules} critical compliance rule${criticalRules === 1 ? "" : "s"} are still firing.`;
  }
  if (aggregate?.risks?.total_risks_detected && aggregate.risks.total_risks_detected > 0) {
    return `Main concern: ${aggregate.risks.total_risks_detected} active risk${aggregate.risks.total_risks_detected === 1 ? "" : "s"} surfaced by the rule engine.`;
  }
  return "No critical risks are firing right now.";
}

function topActionSentence(advisor: AdvisorResponse): string {
  const top = advisor.business_summary?.highest_priority_action;
  if (top) return `Highest-priority action — ${top}.`;
  const first = advisor.suggested_actions?.[0];
  if (first) return `Highest-priority action — ${first.title.toLowerCase()}.`;
  return "Highest-priority action — refresh the advisor once your profile is complete.";
}

// --------------------------------------------------------------------------- //
// Top 3 priorities                                                           //
// --------------------------------------------------------------------------- //

interface PriorityRow {
  id: string;
  title: string;
  rationale: string;
  whyItMatters: string;
  action: string;
  effort: string;
  impact: string;
  timeframe: string;
  priority: string;
}

function pickTopThree(advisor: AdvisorResponse): PriorityRow[] {
  const actions = advisor.suggested_actions ?? [];
  // Prefer Critical > High > Medium > Low.
  const order = { Critical: 0, High: 1, Medium: 2, Low: 3 } as Record<string, number>;
  const sorted = [...actions].sort(
    (a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9),
  );
  return sorted.slice(0, 3).map((a) => mapAction(a));
}

function mapAction(a: AdvisorAction): PriorityRow {
  return {
    id: a.id,
    title: a.title,
    rationale: a.rationale,
    whyItMatters: explainWhy(a),
    action: deriveAction(a),
    effort: classifyEffort(a),
    impact: classifyImpact(a),
    timeframe: deriveTimeframe(a),
    priority: a.priority,
  };
}

function explainWhy(a: AdvisorAction): string {
  if (a.related_recommendation_id) {
    return "Connected to a roadmap item; resolving it cascades through dependent work.";
  }
  if (a.evidence_ids?.length) {
    return `Backed by ${a.evidence_ids.length} signal${a.evidence_ids.length === 1 ? "" : "s"} from your live profile.`;
  }
  return "Derived from your current Digital Twin snapshot.";
}

function deriveAction(a: AdvisorAction): string {
  switch (a.action_type) {
    case "investigate": return "Investigate the rule firing in the Analytics tab.";
    case "prioritise":  return "Schedule this on the roadmap within the next sprint.";
    case "plan":        return "Draft a one-week plan in the assistant.";
    case "decide":      return "Make the call in the assistant; document the rationale.";
    case "review":      return "Open the related roadmap item and review.";
    case "learn":       return "Read the linked recommendation; capture key takeaways.";
    case "monitor":     return "Track this in your weekly summary.";
    case "refresh":     return "Re-run the analysis once your profile changes.";
    default:             return "Open in the assistant to draft a one-week plan.";
  }
}

function classifyEffort(a: AdvisorAction): string {
  // Effort is derived from the advisor priority — no invented ROI.
  switch (a.priority) {
    case "Critical": return "Low";
    case "High":     return "Medium";
    case "Medium":   return "Medium";
    case "Low":      return "Low";
    default:          return "Medium";
  }
}

function classifyImpact(a: AdvisorAction): string {
  switch (a.priority) {
    case "Critical": return "High";
    case "High":     return "High";
    case "Medium":   return "Medium";
    case "Low":      return "Low";
    default:         return "Medium";
  }
}

function deriveTimeframe(a: AdvisorAction): string {
  switch (a.priority) {
    case "Critical": return "1-2 weeks";
    case "High":     return "1 month";
    case "Medium":   return "1-3 months";
    case "Low":      return "3+ months";
    default:          return "1 month";
  }
}

// --------------------------------------------------------------------------- //
// Strengths / concerns lists                                                 //
// --------------------------------------------------------------------------- //

function pickStrengths(advisor: AdvisorResponse): string[] {
  const weekly = (advisor.weekly_summary ?? [])
    .filter((a) => a.priority === "Low" || a.section === "weekly_summary")
    .map((a) => a.title);
  const headline = advisor.business_summary?.headline;
  const headlineLine = headline ? [headline] : [];
  return dedupe([...headlineLine, ...weekly]).slice(0, 3);
}

function pickConcerns(
  advisor: AdvisorResponse,
  aggregate: AdvisorAggregateReport | null,
): string[] {
  const fromAdvisor = (advisor.upcoming_risks ?? []).map((a) => a.title);
  const fromAggregate = (aggregate?.risks?.risks ?? [])
    .filter((r) => r.severity === "Critical" || r.severity === "High")
    .map((r) => `${r.risk} (${r.severity.toLowerCase()})`);
  return dedupe([...fromAdvisor, ...fromAggregate]).slice(0, 3);
}

function List3({
  items,
  icon: Icon,
  tone,
}: {
  items: string[];
  icon: typeof CheckCircle2;
  tone: "emerald" | "rose";
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing surfaced yet — once your Digital Twin has more inputs,
        this list will populate.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((it, i) => (
        <li
          key={`${it}-${i}`}
          className="flex items-start gap-2 rounded-md border border-border bg-background/40 p-2"
        >
          <Icon
            className={cn(
              "size-4 mt-0.5 shrink-0",
              tone === "emerald" ? "text-emerald-500" : "text-rose-500",
            )}
            aria-hidden="true"
          />
          <span className="text-sm text-foreground">{it}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Impact / effort buckets                                                    //
// --------------------------------------------------------------------------- //

function bucketByEffort(advisor: AdvisorResponse) {
  type Buckets = { quick: string[]; strategic: string[]; longterm: string[]; low: string[] };
  const out: Buckets = { quick: [], strategic: [], longterm: [], low: [] };
  for (const a of advisor.suggested_actions ?? []) {
    const item = a.title;
    switch (a.priority) {
      case "Critical": out.quick.push(item); break;
      case "High":     out.strategic.push(item); break;
      case "Medium":   out.longterm.push(item); break;
      case "Low":      out.low.push(item); break;
      default:         out.low.push(item); break;
    }
  }
  return out;
}

function Bucket({
  title,
  caption,
  icon: Icon,
  items,
  tone,
}: {
  title: string;
  caption: string;
  icon: typeof Rocket;
  items: string[];
  tone: "emerald" | "sky" | "violet" | "muted";
}) {
  const toneClass = {
    emerald: "border-emerald-500/40",
    sky: "border-sky-500/40",
    violet: "border-violet-500/40",
    muted: "border-border",
  }[tone];
  return (
    <div className={cn("rounded-md border bg-background/40 p-3", toneClass)}>
      <div className="flex items-center gap-2">
        <Icon
          className={cn(
            "size-4",
            tone === "emerald" && "text-emerald-500",
            tone === "sky" && "text-sky-500",
            tone === "violet" && "text-violet-500",
            tone === "muted" && "text-muted-foreground",
          )}
          aria-hidden="true"
        />
        <span className="text-sm font-semibold text-foreground">{title}</span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">{caption}</p>
      <ul className="mt-3 flex flex-col gap-1.5">
        {items.length === 0 && (
          <li className="text-xs text-muted-foreground">None yet.</li>
        )}
        {items.map((it, i) => (
          <li
            key={`${it}-${i}`}
            className="rounded-sm bg-background/60 px-2 py-1 text-xs text-foreground"
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Field                                                                      //
// --------------------------------------------------------------------------- //

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm bg-background/60 px-2 py-1 text-center">
      <dt className="uppercase tracking-wider text-[10px]">{label}</dt>
      <dd className="font-mono text-[11px] text-foreground">{value}</dd>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Detailed accordion (preserves pre-H6.2 view)                                //
// --------------------------------------------------------------------------- //

function DetailedAdvisorAccordion() {
  return (
    <details className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center gap-2">
          <HelpCircle className="size-4 text-primary" aria-hidden="true" />
          <span className="text-sm font-semibold text-foreground">
            Detailed analysis
          </span>
          <span className="hidden sm:inline text-xs text-muted-foreground">
            Growth · Funding · Compliance · Risk · Opportunities · Weekly summary · Upcoming concerns · Full recommendations
          </span>
        </div>
        <ChevronDown
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="border-t border-border">
        <DetailedAdvisorView />
      </div>
    </details>
  );
}

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

function dedupe(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const it of items) {
    const k = it.toLowerCase().trim();
    if (!k) continue;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(it);
  }
  return out;
}

function formatTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * TopRecommendations — the "5 High Priority Recommendations" panel
 * that sits below the Executive Summary on the Advisor screen.
 *
 * Pulls the top 5 from the union of:
 *   - daily_brief
 *   - priority_changes
 *   - upcoming_risks
 *   - missed_opportunities
 *   - suggested_actions
 * sorted by priority band (Critical -> Low) then by source order.
 *
 * Each card carries:
 *   - Priority badge
 *   - Title + 1-2 line rationale
 *   - Source attribution
 *   - Expected impact (deterministic demo: priority-band based score lift)
 *   - Estimated timeline (deterministic demo: priority-band based window)
 *   - "Explain Why" expandable section that reveals the underlying
 *     evidence (rationale + evidence_ids + source)
 *
 * Deterministic demo data: when the backend does not return per-item
 * impact or timeline, we derive them deterministically from the
 * item's priority band. The values are stable for a given advisor
 * response (sorted by `id`).
 */

"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clock,
  Lightbulb,
  ListChecks,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { DashboardCard } from "@/components/dashboard/DashboardCard";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { cn } from "@/lib/utils";
import type {
  AdvisorAction,
  AdvisorAdvice,
  AdvisorPriority,
  AdvisorResponse,
} from "@/types/advisor";

interface TopRecommendationsProps {
  advisor: AdvisorResponse;
  /** Max items to show. Defaults to 5. */
  limit?: number;
}

interface NormalizedItem {
  id: string;
  title: string;
  rationale: string;
  priority: AdvisorPriority;
  source: string;
  source_key: string;
  evidence_ids: string[];
  section: string;
}

export function TopRecommendations({ advisor, limit = 5 }: TopRecommendationsProps) {
  const items = useMemo(() => pickTop(advisor, limit), [advisor, limit]);

  return (
    <DashboardCard
      badge="Top Recommendations"
      title="5 High-Priority Recommendations"
      caption="The five most decision-worthy items the advisor surfaces, ranked by priority band."
      icon={<Lightbulb className="size-4 text-primary" aria-hidden="true" />}
    >
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          The advisor did not surface any high-priority items in this pass.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {items.map((item, i) => (
            <li key={item.id}>
              <RecommendationRow index={i + 1} item={item} />
            </li>
          ))}
        </ol>
      )}
    </DashboardCard>
  );
}

// --------------------------------------------------------------------------- //
// Per-recommendation row
// --------------------------------------------------------------------------- //

interface RowProps {
  index: number;
  item: NormalizedItem;
}

function RecommendationRow({ index, item }: RowProps) {
  const [open, setOpen] = useState(false);
  const [impact, timeline] = useMemo(
    () => [impactFor(item.priority), timelineFor(item.priority)],
    [item.priority],
  );

  return (
    <div className="rounded-lg border border-border bg-secondary/30">
      <div className="flex flex-col gap-3 p-3">
        <div className="flex items-start gap-3">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-[11px] font-semibold text-primary">
            {index}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                {item.title || "Untitled recommendation"}
              </span>
              <LevelBadge
                level={item.priority}
                tone={levelToTone(item.priority)}
              />
              <span className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {item.section.replace(/_/g, " ")}
              </span>
            </div>
            {item.rationale && (
              <p className="text-xs leading-relaxed text-muted-foreground">
                {item.rationale}
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <MetaTile
            icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
            label="Expected Impact"
            value={impact.label}
            hint="deterministic band estimate"
            tone={impact.tone}
          />
          <MetaTile
            icon={<Clock className="size-3.5" aria-hidden="true" />}
            label="Estimated Timeline"
            value={timeline.label}
            hint="deterministic band estimate"
            tone="text-muted-foreground"
          />
          <MetaTile
            icon={<ListChecks className="size-3.5" aria-hidden="true" />}
            label="Source"
            value={item.source}
            hint={item.source_key}
            tone="text-muted-foreground"
          />
        </div>

        <div className="flex items-center justify-between border-t border-border pt-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={`explain-${item.id}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            {open ? (
              <ChevronDown className="size-3.5" aria-hidden="true" />
            ) : (
              <ChevronRight className="size-3.5" aria-hidden="true" />
            )}
            Explain Why
          </button>
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            <AlertTriangle className="size-3" aria-hidden="true" />
            {item.evidence_ids.length} evidence anchor{item.evidence_ids.length === 1 ? "" : "s"}
          </span>
        </div>

        {open && (
          <div
            id={`explain-${item.id}`}
            className="rounded-md border border-border bg-background p-3"
          >
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Why this recommendation
            </p>
            <p className="mt-1 text-xs leading-relaxed text-foreground">
              {buildExplanation(item)}
            </p>
            {item.evidence_ids.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Evidence
                </span>
                <ul className="flex flex-wrap gap-1.5">
                  {item.evidence_ids.map((eid) => (
                    <li
                      key={eid}
                      className="rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] text-foreground"
                    >
                      {eid}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Meta tile (impact / timeline / source)
// --------------------------------------------------------------------------- //

interface MetaTileProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
  tone: string;
}

function MetaTile({ icon, label, value, hint, tone }: MetaTileProps) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-border bg-background px-3 py-2">
      <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className={cn("text-sm font-semibold", tone)}>{value}</span>
      <span className="text-[10px] text-muted-foreground">{hint}</span>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Selection + impact/timeline derivation
// --------------------------------------------------------------------------- //

function pickTop(advisor: AdvisorResponse, limit: number): NormalizedItem[] {
  const all: NormalizedItem[] = [
    ...advisor.daily_brief.map((a) => normalizeAdvice(a, "daily_brief")),
    ...advisor.priority_changes.map((a) => normalizeAdvice(a, "priority_changes")),
    ...advisor.upcoming_risks.map((a) => normalizeAdvice(a, "upcoming_risks")),
    ...advisor.missed_opportunities.map((a) =>
      normalizeAdvice(a, "missed_opportunities"),
    ),
    ...advisor.suggested_actions.map((a) => normalizeAction(a)),
  ];
  // Sort: priority band, then by id (stable).
  const order: Record<AdvisorPriority, number> = {
    Critical: 0, High: 1, Medium: 2, Low: 3,
  };
  all.sort((a, b) => {
    const dp = (order[a.priority] ?? 9) - (order[b.priority] ?? 9);
    if (dp !== 0) return dp;
    return a.id.localeCompare(b.id);
  });
  // Trim to top-5 of which priority? Prefer Critical + High.
  const preferred = all.filter(
    (i) => i.priority === "Critical" || i.priority === "High",
  );
  const pool = preferred.length >= limit ? preferred : all;
  return pool.slice(0, limit);
}

function normalizeAdvice(a: AdvisorAdvice, section: string): NormalizedItem {
  return {
    id: a.id,
    title: a.title,
    rationale: a.summary,
    priority: a.priority,
    source: a.source,
    source_key: a.source_key,
    evidence_ids: a.evidence_ids ?? [],
    section,
  };
}

function normalizeAction(a: AdvisorAction): NormalizedItem {
  return {
    id: a.id,
    title: a.title,
    rationale: a.rationale,
    priority: a.priority,
    source: "rules",
    source_key: a.source_key,
    evidence_ids: a.evidence_ids ?? [],
    section: "suggested_actions",
  };
}

interface BandMeta { label: string; tone: string; }

function impactFor(priority: AdvisorPriority): BandMeta {
  switch (priority) {
    case "Critical": return { label: "+18 to +30 pts",  tone: "text-emerald-600" };
    case "High":     return { label: "+8 to +18 pts",   tone: "text-emerald-600" };
    case "Medium":   return { label: "+3 to +8 pts",    tone: "text-amber-600" };
    case "Low":      return { label: "+0 to +3 pts",    tone: "text-muted-foreground" };
  }
}

function timelineFor(priority: AdvisorPriority): BandMeta {
  switch (priority) {
    case "Critical": return { label: "0-1 month",    tone: "text-rose-600" };
    case "High":     return { label: "1-3 months",   tone: "text-amber-700" };
    case "Medium":   return { label: "3-6 months",   tone: "text-amber-700" };
    case "Low":      return { label: "6-12 months",  tone: "text-muted-foreground" };
  }
}

function buildExplanation(item: NormalizedItem): string {
  const why: string[] = [];
  why.push(
    `Priority is "${item.priority}", so UrsBiz is recommending this before ` +
      `lower-priority items.`,
  );
  if (item.source) {
    why.push(`Sourced from the ${item.source} engine.`);
  }
  if (item.evidence_ids.length > 0) {
    why.push(
      `${item.evidence_ids.length} evidence anchor` +
        (item.evidence_ids.length === 1 ? "" : "s") +
        ` tie this recommendation back to upstream rule firings or decision insights.`,
    );
  } else {
    why.push(
      "No evidence anchors attached — the recommendation is heuristic.",
    );
  }
  return why.join(" ");
}

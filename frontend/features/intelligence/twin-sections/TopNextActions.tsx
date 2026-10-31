"use client";

/**
 * Section 7 — Top 3 Next Actions.
 * The most important section of the Business Digital Twin.
 * Renders exactly 3 prioritised actions. Source =
 * recommendations.recommendations[] sorted by
 * (priority rank, estimated_score_gain desc, estimated_roi desc).
 *
 * Each action shows:
 *   - Title
 *   - Why now (one sentence, derived from the analyzer that
 *     fired the supporting rule — or the recommendation's
 *     business_impact + supporting rule category)
 *   - Expected benefit (scenario language)
 *   - Difficulty
 *   - Time required
 *   - CTA: "Ask AI for a 30-day plan" → /assistant?prompt=<question>
 *
 * If fewer than 3 recommendations exist, we show what we have
 * and explicitly mark the missing slots as "No further
 * priority action queued".
 */

import React from "react";
import Link from "next/link";
import type { RecommendationsResponse, RecommendationItem } from "@/types/analytics";
import type { RulePriority } from "@/types/dashboard";
import { InsightChip } from "@/components/intelligence/InsightChip";

interface TopNextActionsProps {
  recommendations?: RecommendationsResponse | null;
  // Optional: when we have the analyzers from the intelligence payload,
  // we can produce a sharper "Why now?" sentence anchored on the
  // dimension whose score is lowest.
  lowestDimension?: { label: string; score: number } | null;
}

const PRIORITY_RANK: Record<RulePriority, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };

function pick(recs: RecommendationItem[] | undefined, max = 3): RecommendationItem[] {
  if (!recs || recs.length === 0) return [];
  return [...recs]
    .sort((a, b) => {
      const r = (PRIORITY_RANK[a.priority] ?? 9) - (PRIORITY_RANK[b.priority] ?? 9);
      if (r !== 0) return r;
      const s = (b.estimated_score_gain || 0) - (a.estimated_score_gain || 0);
      if (s !== 0) return s;
      return (b.estimated_roi || 0) - (a.estimated_roi || 0);
    })
    .slice(0, max);
}

function prefillQuestion(rec: RecommendationItem): string {
  return `Build me a 30-day action plan for: ${rec.title}`;
}

function buildPromptHref(question: string): string {
  const params = new URLSearchParams({ prompt: question });
  return `/assistant?${params.toString()}`;
}

function whyNow(rec: RecommendationItem, lowest?: { label: string; score: number } | null): string {
  if (lowest && rec.related_score_keys && rec.related_score_keys.includes(lowest.label.toLowerCase())) {
    return `Your ${lowest.label.toLowerCase()} readiness is ${lowest.score}/100 — the lowest of your five dimensions. Acting here pulls the average up fastest.`;
  }
  if (rec.estimated_score_gain > 0) {
    return `Expected to add ${rec.estimated_score_gain} pts to your overall health score — the biggest single move available right now.`;
  }
  return rec.description || `Addressed by the rules engine at ${rec.priority} priority.`;
}

function expectedBenefit(rec: RecommendationItem): string {
  if (rec.estimated_roi > 0) {
    const timeline = rec.estimated_timeline || "near-term";
    return `Potential ${rec.estimated_roi}% modelled ROI on the ${timeline} window (scenario, not promise).`;
  }
  const phase = (rec.phase || "").toLowerCase();
  const timeline = rec.estimated_timeline || "near-term";
  return `Potential improvement in ${phase || "operational"} readiness on the ${timeline} window (scenario, not promise).`;
}

export const TopNextActions: React.FC<TopNextActionsProps> = ({
  recommendations,
  lowestDimension,
}) => {
  const items = pick(recommendations?.recommendations);
  const slots: Array<RecommendationItem | null> = [
    items[0] || null,
    items[1] || null,
    items[2] || null,
  ];

  return (
    <section
      aria-labelledby="twin-section-actions"
      className="rounded-xl border-2 border-primary/30 bg-primary/5 p-5 shadow-sm sm:p-6"
    >
      <header className="mb-4">
        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
          Section 7 — Most important
        </span>
        <h2
          id="twin-section-actions"
          className="mt-0.5 text-lg font-bold text-card-foreground sm:text-xl"
        >
          Top 3 Next Actions
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Exactly three moves, prioritised by score gain and ROI.
        </p>
      </header>

      <ol className="space-y-4">
        {slots.map((rec, idx) => (
          <li
            key={rec ? rec.id : `slot-${idx}`}
            className="rounded-xl border border-border bg-card p-4 shadow-sm"
          >
            {!rec ? (
              <p className="text-xs italic text-muted-foreground">
                Slot {idx + 1}: no further priority action queued.
              </p>
            ) : (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-extrabold text-primary-foreground">
                      {idx + 1}
                    </span>
                    <h3 className="text-base font-bold text-card-foreground">{rec.title}</h3>
                  </div>
                  <InsightChip
                    label={`Priority: ${rec.priority}`}
                    variant={rec.priority === "Critical" ? "critical" : rec.priority === "High" ? "high" : rec.priority === "Medium" ? "medium" : "low"}
                  />
                </div>
                <dl className="mt-3 space-y-2 text-xs">
                  <div>
                    <dt className="font-semibold text-card-foreground">Why now</dt>
                    <dd className="mt-0.5 text-muted-foreground">{whyNow(rec, lowestDimension)}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-card-foreground">Expected benefit</dt>
                    <dd className="mt-0.5 text-muted-foreground">{expectedBenefit(rec)}</dd>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <dt className="font-semibold text-card-foreground">Difficulty</dt>
                      <dd className="mt-0.5 text-muted-foreground">{rec.difficulty}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold text-card-foreground">Time required</dt>
                      <dd className="mt-0.5 text-muted-foreground">{rec.estimated_timeline}</dd>
                    </div>
                  </div>
                </dl>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <Link
                    href={buildPromptHref(prefillQuestion(rec))}
                    className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-all hover:opacity-90"
                  >
                    Ask AI for a 30-day plan →
                  </Link>
                  <Link
                    href="/action-board"
                    className="text-[11px] font-medium text-muted-foreground underline-offset-2 hover:underline"
                  >
                    Open Action Board
                  </Link>
                </div>
              </>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
};

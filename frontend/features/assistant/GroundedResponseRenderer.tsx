"use client";

/**
 * GroundedResponseRenderer — H7.8C (Sprint H7.8C P3 §12).
 *
 * Renders a server-validated :class:`ChatGroundedResponse`
 * as nine structured sections. The component is the visual
 * counterpart to the backend evidence-bounded pipeline — the
 * :class:`GroundingValidator` decides whether the response
 * is shown at all, and this component is what the user
 * actually sees when it is shown.
 *
 * Sections (always rendered, in order):
 *
 *   1. Executive Summary      (always expanded)
 *   2. Current Situation      (driven by ``key_findings``)
 *   3. Key Findings           (collapsible)
 *   4. Recommended Priorities (collapsible, server-resolved)
 *   5. 30-Day Action Plan     (collapsible, week-numbered)
 *   6. Scheme Profile Matches (collapsible, profile-match
 *                               disclaimer mandatory)
 *   7. Assumptions            (collapsible, always present)
 *   8. Limitations            (collapsible, always present)
 *   9. Evidence               (collapsible, evidence IDs)
 *
 * Visual rhythm mirrors :component:`ConsultantRenderer`'s
 * ``SectionCard`` — ``exec-card`` rounded-2xl border, eyebrow
 * + title, ``bg-{tone}/10`` icon, ``ChevronDown`` rotation,
 * ``border-t`` divider. This keeps the chat surface visually
 * consistent regardless of which renderer path produced the
 * message.
 *
 * Stable ``data-testid``s:
 *
 *   - ``grounded-section-{key}`` on every section card
 *   - ``grounded-evidence-item`` on every evidence reference
 *   - ``grounded-finding-item`` on every key finding
 *   - ``grounded-recommendation-item`` on every recommendation
 *   - ``grounded-plan-item`` on every plan task
 *   - ``grounded-scheme-item`` on every scheme match
 *   - ``grounded-exec-summary`` on the executive summary body
 *
 * The renderer's job is *display only* — it never mutates the
 * payload, never makes a network call, and never decides
 * whether the response is trustworthy. Those decisions live
 * in the backend validator and the
 * :func:`MessageBubble.deriveTrustLabel` derivation.
 */
import { useMemo, useState } from "react";
import {
  AlertCircle,
  BadgeCheck,
  ChevronDown,
  ClipboardList,
  Compass,
  Lightbulb,
  ListChecks,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  ChatGroundedPlanItem,
  ChatGroundedRecommendation,
  ChatGroundedResponse,
  ChatGroundedSchemeMatch,
} from "./types";

// --------------------------------------------------------------------------- //
// Section meta                                                                //
// --------------------------------------------------------------------------- //

type SectionKey =
  | "executive_summary"
  | "current_situation"
  | "key_findings"
  | "recommendations"
  | "thirty_day_plan"
  | "scheme_matches"
  | "assumptions"
  | "limitations"
  | "evidence";

interface SectionMeta {
  Icon: React.ComponentType<{ className?: string }>;
  bg: string;
  iconColor: string;
  eyebrow: string;
  /** First section is always expanded; the rest collapse by default. */
  defaultOpen: boolean;
}

const SECTION_META: Record<SectionKey, SectionMeta> = {
  executive_summary: {
    Icon: Compass,
    bg: "bg-primary/10",
    iconColor: "text-primary",
    eyebrow: "Executive Summary",
    defaultOpen: true,
  },
  current_situation: {
    Icon: Lightbulb,
    bg: "bg-amber-500/10",
    iconColor: "text-amber-600 dark:text-amber-400",
    eyebrow: "Current Situation",
    defaultOpen: true,
  },
  key_findings: {
    Icon: Lightbulb,
    bg: "bg-amber-500/10",
    iconColor: "text-amber-600 dark:text-amber-400",
    eyebrow: "Key Findings",
    defaultOpen: true,
  },
  recommendations: {
    Icon: ClipboardList,
    bg: "bg-violet-500/10",
    iconColor: "text-violet-600 dark:text-violet-400",
    eyebrow: "Recommended Priorities",
    defaultOpen: true,
  },
  thirty_day_plan: {
    Icon: ListChecks,
    bg: "bg-sky-500/10",
    iconColor: "text-sky-600 dark:text-sky-400",
    eyebrow: "30-Day Action Plan",
    defaultOpen: true,
  },
  scheme_matches: {
    Icon: BadgeCheck,
    bg: "bg-emerald-500/10",
    iconColor: "text-emerald-600 dark:text-emerald-400",
    eyebrow: "Scheme Profile Matches",
    defaultOpen: true,
  },
  assumptions: {
    Icon: AlertCircle,
    bg: "bg-slate-500/10",
    iconColor: "text-slate-600 dark:text-slate-400",
    eyebrow: "Assumptions",
    defaultOpen: false,
  },
  limitations: {
    Icon: ShieldAlert,
    bg: "bg-rose-500/10",
    iconColor: "text-rose-600 dark:text-rose-400",
    eyebrow: "Limitations",
    defaultOpen: false,
  },
  evidence: {
    Icon: Sparkles,
    bg: "bg-fuchsia-500/10",
    iconColor: "text-fuchsia-600 dark:text-fuchsia-400",
    eyebrow: "Evidence",
    defaultOpen: false,
  },
};

// --------------------------------------------------------------------------- //
// Component                                                                   //
// --------------------------------------------------------------------------- //

export function GroundedResponseRenderer({
  response,
}: {
  response: ChatGroundedResponse;
}) {
  // The "current situation" section is rendered from the
  // first half of ``key_findings`` when there are enough
  // findings; otherwise the section is hidden so the renderer
  // never shows an empty card.
  const situation = useMemo(
    () => buildCurrentSituation(response),
    [response],
  );

  return (
    <div
      className="space-y-3"
      data-testid="grounded-response-renderer"
      data-server-grounding-score={response.server_grounding_score}
    >
      <SectionCard
        sectionKey="executive_summary"
        title="Executive Summary"
      >
        <p
          data-testid="grounded-exec-summary"
          className="text-sm leading-relaxed text-foreground/90"
        >
          {response.executive_summary}
        </p>
        <ConfidenceFooter response={response} />
      </SectionCard>

      {situation.length > 0 ? (
        <SectionCard
          sectionKey="current_situation"
          title="Current Situation"
        >
          <ul className="space-y-1.5">
            {situation.map((f, i) => (
              <li
                key={`cs-${i}`}
                data-testid="grounded-finding-item"
                className="flex gap-2 rounded-lg bg-background/40 px-3 py-2 text-sm"
              >
                <span className="font-semibold text-foreground/80">
                  {f.title}
                </span>
                {f.detail ? (
                  <span className="text-muted-foreground">— {f.detail}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.key_findings.length > 0 ? (
        <SectionCard
          sectionKey="key_findings"
          title="Key Findings"
          caption="Each finding is grounded in the evidence registry."
        >
          <ul className="space-y-1.5">
            {response.key_findings.map((f, i) => (
              <li
                key={`kf-${i}`}
                data-testid="grounded-finding-item"
                className="flex flex-col gap-1 rounded-lg bg-background/40 px-3 py-2 text-sm"
              >
                <span className="font-semibold">{f.title}</span>
                {f.detail ? (
                  <span className="text-muted-foreground">{f.detail}</span>
                ) : null}
                {f.evidence_refs.length > 0 ? (
                  <EvidenceRefList refs={f.evidence_refs} />
                ) : null}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.recommendations.length > 0 ? (
        <SectionCard
          sectionKey="recommendations"
          title="Recommended Priorities"
          caption="Priorities and score gains are resolved server-side from the registry."
        >
          <ul className="grid gap-2 sm:grid-cols-2">
            {response.recommendations.map((rec, i) => (
              <li
                key={`rec-${rec.recommendation_id || i}`}
                data-testid="grounded-recommendation-item"
                data-recommendation-id={rec.recommendation_id}
              >
                <RecommendationCard rec={rec} />
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.thirty_day_plan.length > 0 ? (
        <SectionCard
          sectionKey="thirty_day_plan"
          title="30-Day Action Plan"
          caption="Each week ties to a recommendation or roadmap evidence ID."
        >
          <ol className="space-y-2">
            {response.thirty_day_plan.map((p, i) => (
              <PlanRow
                key={`plan-${p.week}-${i}`}
                item={p}
                fallbackIndex={i}
              />
            ))}
          </ol>
        </SectionCard>
      ) : null}

      {response.scheme_matches.length > 0 ? (
        <SectionCard
          sectionKey="scheme_matches"
          title="Scheme Profile Matches"
          caption="Profile match only — final eligibility and approval are determined by the official authority."
        >
          <ul className="space-y-2">
            {response.scheme_matches.map((sm, i) => (
              <SchemeRow
                key={`scheme-${sm.scheme_ref || i}`}
                match={sm}
              />
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.assumptions.length > 0 ? (
        <SectionCard
          sectionKey="assumptions"
          title="Assumptions"
        >
          <ul className="ml-4 list-disc space-y-1 text-sm text-foreground/80">
            {response.assumptions.map((a, i) => (
              <li key={`a-${i}`}>{a}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.limitations.length > 0 ? (
        <SectionCard
          sectionKey="limitations"
          title="Limitations"
        >
          <ul className="ml-4 list-disc space-y-1 text-sm text-foreground/80">
            {response.limitations.map((l, i) => (
              <li key={`l-${i}`}>{l}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {response.evidence_references.length > 0 ? (
        <SectionCard
          sectionKey="evidence"
          title="Evidence"
          caption="Stable IDs from the UrsBiz evidence registry."
        >
          <ul className="space-y-1.5">
            {response.evidence_references.map((e, i) => (
              <li
                key={`ev-${e.id || i}`}
                data-testid="grounded-evidence-item"
                data-evidence-id={e.id}
                className="flex flex-col gap-0.5 rounded-md bg-background/40 px-3 py-1.5 text-sm"
              >
                <code className="text-xs font-mono text-primary">{e.id}</code>
                <span className="text-muted-foreground">{e.label}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section card                                                                //
// --------------------------------------------------------------------------- //

function SectionCard({
  sectionKey,
  title,
  caption,
  children,
}: {
  sectionKey: SectionKey;
  title: string;
  caption?: string;
  children: React.ReactNode;
}) {
  const meta = SECTION_META[sectionKey];
  const [open, setOpen] = useState(meta.defaultOpen);
  const Icon = meta.Icon;
  return (
    <div
      data-testid={`grounded-section-${sectionKey}`}
      className={cn(
        "exec-card relative overflow-hidden rounded-2xl border bg-card shadow-sm transition-shadow",
        open && "shadow-md",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        aria-expanded={open}
        aria-controls={`grounded-section-${sectionKey}-body`}
      >
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-full",
            meta.bg,
          )}
        >
          <Icon className={cn("size-4", meta.iconColor)} aria-hidden />
        </span>
        <span className="flex-1">
          <span className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {meta.eyebrow}
          </span>
          <span className="block font-display text-base font-semibold">
            {title}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            open ? "rotate-180" : "rotate-0",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <div
          id={`grounded-section-${sectionKey}-body`}
          className="space-y-3 border-t px-4 pb-4 pt-3"
        >
          {caption ? (
            <p className="text-sm text-muted-foreground">{caption}</p>
          ) : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section content                                                             //
// --------------------------------------------------------------------------- //

function ConfidenceFooter({ response }: { response: ChatGroundedResponse }) {
  const score = Math.max(0, Math.min(100, response.server_grounding_score));
  const modelConfidence = response.confidence;
  // The displayed number is the *server* grounding score; the
  // model's self-reported confidence is surfaced in the
  // TrustMeta disclosure so the user can compare.
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border/50 pt-2 text-[10px] uppercase tracking-wider text-muted-foreground">
      <span>Server grounding score</span>
      <div className="relative h-1.5 w-32 overflow-hidden rounded-full bg-muted">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary via-violet-500 to-emerald-400"
          style={{ width: `${score}%` }}
          aria-label={`server grounding ${score} of 100`}
        />
      </div>
      <span className="font-medium tabular-nums text-foreground">
        {score}/100
      </span>
      {typeof modelConfidence === "number" ? (
        <span className="ml-auto text-muted-foreground">
          Model self-reported confidence: {modelConfidence}/100
        </span>
      ) : null}
    </div>
  );
}

function RecommendationCard({ rec }: { rec: ChatGroundedRecommendation }) {
  return (
    <div className="flex h-full flex-col gap-1 rounded-xl border border-violet-200/60 bg-violet-500/5 p-3 dark:border-violet-500/30">
      <h4 className="text-sm font-semibold leading-tight">
        {rec.title || rec.recommendation_id}
      </h4>
      <p className="text-xs text-muted-foreground">{rec.rationale}</p>
      {rec.evidence_refs.length > 0 ? (
        <EvidenceRefList refs={rec.evidence_refs} />
      ) : null}
      <code className="mt-1 truncate rounded bg-background/40 px-1 py-0.5 text-[10px] font-mono text-muted-foreground">
        {rec.recommendation_id}
      </code>
    </div>
  );
}

function PlanRow({
  item,
  fallbackIndex,
}: {
  item: ChatGroundedPlanItem;
  fallbackIndex: number;
}) {
  return (
    <li
      data-testid="grounded-plan-item"
      data-week={item.week}
      data-recommendation-ref={item.recommendation_ref ?? undefined}
      className="flex flex-col gap-1 rounded-lg border border-sky-200/60 bg-sky-500/5 p-3 text-sm dark:border-sky-500/30"
    >
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-sky-700 dark:text-sky-300">
          Week {item.week ?? fallbackIndex + 1}
        </span>
        {item.recommendation_ref ? (
          <code className="font-mono text-muted-foreground">
            {item.recommendation_ref}
          </code>
        ) : null}
      </div>
      <p className="text-foreground/90">{item.task}</p>
      {item.evidence_refs.length > 0 ? (
        <EvidenceRefList refs={item.evidence_refs} />
      ) : null}
    </li>
  );
}

function SchemeRow({ match }: { match: ChatGroundedSchemeMatch }) {
  return (
    <li
      data-testid="grounded-scheme-item"
      data-scheme-ref={match.scheme_ref}
      className="flex flex-col gap-1 rounded-lg border border-emerald-200/60 bg-emerald-500/5 p-3 text-sm dark:border-emerald-500/30"
    >
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
        <BadgeCheck className="size-3" aria-hidden />
        Profile match
      </div>
      <p className="text-foreground/90">{match.match_explanation}</p>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        Profile match only — final eligibility and approval are determined
        by the official authority.
      </p>
      {match.evidence_refs.length > 0 ? (
        <EvidenceRefList refs={match.evidence_refs} />
      ) : null}
      <code className="mt-1 truncate rounded bg-background/40 px-1 py-0.5 text-[10px] font-mono text-muted-foreground">
        {match.scheme_ref}
      </code>
    </li>
  );
}

function EvidenceRefList({ refs }: { refs: string[] }) {
  if (refs.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5 pt-1">
      {refs.map((ref, i) => (
        <li
          key={`ref-${i}-${ref}`}
          data-testid="grounded-evidence-item"
          data-evidence-id={ref}
        >
          <code className="rounded-full bg-secondary/60 px-2 py-0.5 text-[10px] font-mono text-foreground/80">
            {ref}
          </code>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Helpers                                                                     //
// --------------------------------------------------------------------------- //

/**
 * Build the "current situation" preview from the first few
 * key findings. We surface at most three findings to keep the
 * card focused on the user's present state; the rest live in
 * the dedicated "Key Findings" section.
 */
function buildCurrentSituation(
  response: ChatGroundedResponse,
): Array<{ title: string; detail?: string }> {
  return response.key_findings.slice(0, 3).map((f) => ({
    title: f.title,
    detail: f.detail,
  }));
}

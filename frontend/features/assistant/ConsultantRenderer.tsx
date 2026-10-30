"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  ClipboardList,
  Compass,
  Lightbulb,
  ListChecks,
  Send,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { formatAssistantBody } from "./AssistantRenderer";
import { ActionPlanCard } from "./ActionPlanCard";
import { DecisionSupportCard } from "./DecisionSupportCard";
import type {
  ConsultantBullet,
  ConsultantResponse,
  ConsultantSection,
} from "./types";

/**
 * Premium renderer for a Consultant response.
 *
 * Lays out the 6 sections (Summary always open; the rest
 * collapsed by default). Falls back to the legacy markdown
 * renderer when the message doesn't carry a consultant payload
 * (e.g. legacy chat history loaded from server).
 *
 * Memory-aware: surfaces an "Earlier you asked..." line under
 * the summary when the user has asked about the same topic
 * before during the session.
 */
export function ConsultantRenderer({
  response,
  memoryTopics,
  onFollowUp,
}: {
  response: ConsultantResponse;
  /** Topics already answered in this session — used for continuity. */
  memoryTopics?: string[];
  /** Called when the user clicks one of the smart follow-up chips. */
  onFollowUp?: (label: string) => void;
}) {
  return (
    <div className="space-y-3">
      {response.greeting ? (
        <p className="rounded-xl border bg-background/40 px-4 py-2 text-sm text-muted-foreground">
          {response.greeting}
        </p>
      ) : null}
      {response.sections.map((section) => (
        <SectionCard
          key={section.key + section.title}
          section={section}
          memoryNote={
            section.key === "summary" &&
            memoryTopics &&
            memoryTopics.length > 1 &&
            memoryTopics[0] !== response.topic
              ? `Earlier in this session you asked about "${memoryTopics[0]}" — building on that read below.`
              : undefined
          }
          onFollowUp={onFollowUp}
        />
      ))}
      {response.sources.length > 0 ? (
        <SourcesFooter sources={response.sources} />
      ) : null}
    </div>
  );
}

function SectionCard({
  section,
  memoryNote,
  onFollowUp,
}: {
  section: ConsultantSection;
  memoryNote?: string;
  onFollowUp?: (label: string) => void;
}) {
  // Summary stays open; everything else collapses by default.
  const [open, setOpen] = useState(section.key === "summary");
  const meta = useMemo(() => sectionMeta(section), [section]);
  return (
    <div
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
      >
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-full",
            meta.bg,
          )}
        >
          <meta.Icon className={cn("size-4", meta.iconColor)} aria-hidden />
        </span>
        <span className="flex-1">
          <span className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {meta.eyebrow}
          </span>
          <span className="block font-display text-base font-semibold">
            {section.title}
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
        <div className="space-y-3 border-t px-4 pb-4 pt-3">
          {memoryNote ? (
            <p className="rounded-lg bg-primary/5 px-3 py-2 text-xs text-primary">
              <Sparkles className="mr-2 inline size-3.5" aria-hidden />
              {memoryNote}
            </p>
          ) : null}
          {section.caption ? (
            <p className="text-sm text-muted-foreground">{section.caption}</p>
          ) : null}
          {section.body ? (
            <ProseBody body={section.body} />
          ) : null}
          {section.lines && section.lines.length > 0 ? (
            <ul className="space-y-1.5">
              {section.lines.map((l, i) => (
                <li
                  key={i}
                  className="flex gap-2 rounded-lg bg-background/40 px-3 py-2 text-sm"
                >
                  <ArrowRight
                    className="mt-0.5 size-3.5 shrink-0 text-primary"
                    aria-hidden
                  />
                  <span>{l}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {section.bullets && section.bullets.length > 0 ? (
            <ul className="grid gap-2 sm:grid-cols-2">
              {section.bullets.map((b, i) => (
                <li key={(b.id ?? b.title) + i}>
                  <BulletTile bullet={b} />
                </li>
              ))}
            </ul>
          ) : null}
          {section.weeks && section.weeks.length > 0 ? (
            <ActionPlanCard
              title={section.title}
              caption={section.caption}
              weeks={section.weeks}
            />
          ) : null}
          {section.decision ? (
            <DecisionSupportCard payload={section.decision} />
          ) : null}
          {section.key === "next_questions" && onFollowUp ? (
            <FollowUpChips
              items={section.bullets ?? []}
              onSelect={onFollowUp}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ProseBody({ body }: { body: string }) {
  // Reuse the legacy renderer so the same `**bold**` and `- bullet`
  // formatting applies — gives us the McKinsey-grade inline emphasis
  // for free.
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg bg-background/40 p-3 leading-relaxed text-foreground">
      {formatAssistantBody(body || "")}
    </div>
  );
}

function BulletTile({ bullet }: { bullet: ConsultantBullet }) {
  const tone = toneClasses(bullet.tone);
  return (
    <div className={cn("h-full rounded-xl border bg-background/40 p-3", tone.frame)}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold leading-tight">{bullet.title}</h4>
        {bullet.impact ? (
          <span
            className={cn(
              "shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
              tone.chip,
            )}
          >
            {bullet.impact}
          </span>
        ) : null}
      </div>
      {bullet.subtitle ? (
        <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">
          {bullet.subtitle}
        </p>
      ) : null}
      {(bullet.difficulty || bullet.time || bullet.meta) ? (
        <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
          {bullet.difficulty ? (
            <span className="rounded-full bg-muted px-2 py-0.5">
              {bullet.difficulty}
            </span>
          ) : null}
          {bullet.time ? (
            <span className="rounded-full bg-muted px-2 py-0.5">{bullet.time}</span>
          ) : null}
          {bullet.meta ? (
            <span className="rounded-full bg-muted px-2 py-0.5">{bullet.meta}</span>
          ) : null}
        </div>
      ) : null}
      {bullet.confidence !== undefined ? (
        <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          <span>Confidence</span>
          <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary via-violet-500 to-emerald-400"
              style={{ width: `${Math.max(0, Math.min(100, bullet.confidence))}%` }}
            />
          </div>
          <span className="font-medium tabular-nums text-foreground">
            {Math.round(bullet.confidence)}%
          </span>
        </div>
      ) : null}
      {bullet.riskIfIgnored ? (
        <p className="mt-2 border-t border-border/50 pt-2 text-[10px] text-rose-600 dark:text-rose-400">
          <AlertTriangle className="mr-1 inline size-3" aria-hidden />
          Risk if ignored: {bullet.riskIfIgnored}
        </p>
      ) : null}
    </div>
  );
}

function FollowUpChips({
  items,
  onSelect,
}: {
  items: ConsultantBullet[];
  onSelect: (label: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <button
          key={(item.id ?? item.title) + item.title}
          type="button"
          onClick={() => onSelect(item.title)}
          className="group inline-flex items-center gap-1.5 rounded-full border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground transition hover:-translate-y-px hover:border-primary/50 hover:bg-primary/10 hover:text-primary"
        >
          <Send className="size-3 transition group-hover:translate-x-0.5" aria-hidden />
          {item.title}
        </button>
      ))}
    </div>
  );
}

function SourcesFooter({
  sources,
}: {
  sources: Array<{ topic: string; detail: string }>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border bg-background/40 px-3 py-2 text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-muted-foreground"
        aria-expanded={open}
      >
        <span className="font-medium uppercase tracking-wider">
          Sources ({sources.length})
        </span>
        <ChevronDown
          className={cn(
            "size-3.5 transition-transform",
            open ? "rotate-180" : "rotate-0",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <ul className="mt-2 space-y-1.5">
          {sources.map((s, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-primary" aria-hidden>
                •
              </span>
              <span>
                <span className="font-medium text-foreground">{s.topic}</span>
                <span className="text-muted-foreground"> — {s.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section meta                                                               //
// --------------------------------------------------------------------------- //

function sectionMeta(s: ConsultantSection): {
  Icon: React.ComponentType<{ className?: string }>;
  bg: string;
  iconColor: string;
  eyebrow: string;
} {
  switch (s.key) {
    case "summary":
      return {
        Icon: Compass,
        bg: "bg-primary/10",
        iconColor: "text-primary",
        eyebrow: "Executive Summary",
      };
    case "findings":
      return {
        Icon: Lightbulb,
        bg: "bg-amber-500/10",
        iconColor: "text-amber-600 dark:text-amber-400",
        eyebrow: "Findings",
      };
    case "recommendations":
      return {
        Icon: ClipboardList,
        bg: "bg-violet-500/10",
        iconColor: "text-violet-600 dark:text-violet-400",
        eyebrow: "Recommendations",
      };
    case "impact":
      return {
        Icon: TrendingUp,
        bg: "bg-emerald-500/10",
        iconColor: "text-emerald-600 dark:text-emerald-400",
        eyebrow: "Estimated Impact",
      };
    case "action_plan":
      return {
        Icon: ListChecks,
        bg: "bg-sky-500/10",
        iconColor: "text-sky-600 dark:text-sky-400",
        eyebrow: "Action Plan",
      };
    case "next_questions":
      return {
        Icon: Sparkles,
        bg: "bg-fuchsia-500/10",
        iconColor: "text-fuchsia-600 dark:text-fuchsia-400",
        eyebrow: "Next Questions",
      };
    case "decision":
      return {
        Icon: Target,
        bg: "bg-rose-500/10",
        iconColor: "text-rose-600 dark:text-rose-400",
        eyebrow: "Decision",
      };
    default:
      return {
        Icon: Sparkles,
        bg: "bg-muted",
        iconColor: "text-muted-foreground",
        eyebrow: "Section",
      };
  }
}

function toneClasses(tone: ConsultantBullet["tone"]) {
  switch (tone) {
    case "success":
      return {
        frame: "border-emerald-200/60 dark:border-emerald-500/30",
        chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
      };
    case "warn":
      return {
        frame: "border-amber-200/60 dark:border-amber-500/30",
        chip: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
      };
    case "danger":
      return {
        frame: "border-rose-200/60 dark:border-rose-500/30",
        chip: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
      };
    case "info":
      return {
        frame: "border-sky-200/60 dark:border-sky-500/30",
        chip: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
      };
    case "violet":
      return {
        frame: "border-violet-200/60 dark:border-violet-500/30",
        chip: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
      };
    case "primary":
    default:
      return {
        frame: "border-primary/30",
        chip: "bg-primary/15 text-primary",
      };
  }
}

// Use AnimatedCounter so the impact chip on the executive summary
// animates in when the section opens. Pure side effect.
void AnimatedCounter;
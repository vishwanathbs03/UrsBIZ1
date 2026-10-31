"use client";

/**
 * ContextPanel / BusinessContextRail — Redesigned for Bilingual Copilot UX.
 *
 * Right-side contextual rail providing concise, high-signal business metrics:
 *  - 1. Business Health Score (0-100) with band badge
 *  - 2. Business DNA Archetype and match percentage
 *  - 3. Critical Recommendations count
 *  - 4. Strategic Roadmap progress bar
 *  - 5. Quick navigation shortcuts to core modules
 */

import Link from "next/link";
import {
  AlertCircle,
  BarChart3,
  Compass,
  FileText,
  Layers,
  LayoutDashboard,
  Lightbulb,
  ListChecks,
  Map,
  Sparkles,
} from "lucide-react";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { ProgressBar } from "@/components/dashboard/ProgressBar";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import type { AssistantContext } from "./types";

interface ContextPanelProps {
  context: AssistantContext;
  className?: string;
}

export function ContextPanel({ context, className }: ContextPanelProps) {
  const { t } = useLanguage();

  const quickLinks = [
    { href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard },
    { href: "/analytics", label: t("nav.analytics"), icon: BarChart3 },
    { href: "/action-board", label: t("nav.actionBoard"), icon: Layers },
    { href: "/insights", label: t("nav.insights"), icon: Lightbulb },
    { href: "/reports", label: t("nav.reports"), icon: FileText },
  ];

  return (
    <div
      className={cn(
        "flex h-full flex-col gap-3 rounded-2xl border border-border/70 bg-card/60 p-3.5 shadow-xs backdrop-blur-sm",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/40 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="flex size-6 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="size-3.5" aria-hidden="true" />
          </div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            {t("assistant.businessContextTitle")}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground/80">{t("assistant.liveTwin")}</span>
      </div>

      {context.incomplete && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <p className="text-[11px] leading-tight">
            Analysis in progress. Answers reflect currently registered data.
          </p>
        </div>
      )}

      {/* Metric Tiles */}
      <div className="flex flex-col gap-2">
        <ScoreTile context={context} />
        <DnaTile context={context} />
        <RecommendationTile context={context} />
        <RoadmapTile context={context} />
      </div>

      {/* Quick Navigation Shortcuts */}
      <div className="mt-auto border-t border-border/40 pt-3">
        <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          {t("assistant.quickNav")}
        </span>
        <div className="grid grid-cols-2 gap-1.5">
          {quickLinks.map((q) => {
            const Icon = q.icon;
            return (
              <Link
                key={q.href}
                href={q.href}
                className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-background/50 px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary/5 hover:text-foreground"
              >
                <Icon className="size-3 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{q.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ScoreTile({ context }: { context: AssistantContext }) {
  const { value, band } = context.score;
  const tone = levelToTone(band);
  const { t } = useLanguage();

  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/40 p-2.5 transition-colors hover:border-border">
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          aria-hidden="true"
          className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
        >
          <Sparkles className="size-3.5" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {t("assistant.healthScore")}
          </p>
          <p className="text-xs font-semibold text-foreground">
            <AnimatedCounter value={value} />
            <span className="text-[10px] font-normal text-muted-foreground">/100</span>
          </p>
        </div>
      </div>
      <LevelBadge level={band} tone={tone} />
    </div>
  );
}

function DnaTile({ context }: { context: AssistantContext }) {
  const { archetype, match } = context.dna;
  const { t } = useLanguage();

  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/40 p-2.5 transition-colors hover:border-border">
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          aria-hidden="true"
          className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
        >
          <Compass className="size-3.5" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {t("assistant.businessDna")}
          </p>
          <p className="truncate text-xs font-semibold text-foreground">{archetype || "General MSME"}</p>
        </div>
      </div>
      <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-muted-foreground">
        {match}%
      </span>
    </div>
  );
}

function RecommendationTile({ context }: { context: AssistantContext }) {
  const { total, critical, high } = context.recommendations;
  const { t } = useLanguage();

  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/40 p-2.5 transition-colors hover:border-border">
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          aria-hidden="true"
          className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
        >
          <ListChecks className="size-3.5" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {t("assistant.actions")}
          </p>
          <p className="text-xs font-semibold text-foreground">
            {total} <span className="font-normal text-muted-foreground">{t("assistant.recommendations")}</span>
          </p>
        </div>
      </div>
      <span className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-[10px] font-medium text-destructive">
        {critical + high} {t("assistant.priorityActions")}
      </span>
    </div>
  );
}

function RoadmapTile({ context }: { context: AssistantContext }) {
  const { avgCompletion, currentPhase } = context.roadmap;
  const { t } = useLanguage();

  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-border/60 bg-background/40 p-2.5 transition-colors hover:border-border">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            aria-hidden="true"
            className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          >
            <Map className="size-3.5" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              {t("assistant.roadmap")}
            </p>
            <p className="truncate text-xs font-semibold text-foreground">{currentPhase}</p>
          </div>
        </div>
        <span className="text-xs font-bold tabular-nums text-foreground">{avgCompletion}%</span>
      </div>
      <ProgressBar value={avgCompletion} />
    </div>
  );
}

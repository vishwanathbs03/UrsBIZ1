"use client";

import { useCallback, useMemo } from "react";
import { Download, Printer, RefreshCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AnimatedCounter } from "@/components/common/AnimatedCounter";
import { Logo } from "@/components/common/Logo";
import { cn } from "@/lib/utils";
import { ExecutiveKpiCard } from "@/components/dashboard/ExecutiveKpiCard";

interface ReportHeaderProps {
  lastAnalyzedAt: string | null;
  isRefreshing: boolean;
  onRefresh: () => void;
  /** Optional top-line numbers the hero should surface. */
  hero?: {
    score: number;
    band: string;
    dna: number;
    recommendations: number;
    risks: number;
    opportunities: number;
    improvement: number;
  };
}

export function ReportHeader({
  lastAnalyzedAt,
  isRefreshing,
  onRefresh,
  hero,
}: ReportHeaderProps) {
  const handlePrint = useCallback(() => {
    if (typeof window === "undefined") return;
    window.print();
  }, []);

  const greeting = useMemo(() => greetByHour(new Date().getHours()), []);
  const today = useMemo(
    () =>
      new Date().toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      }),
    [],
  );

  return (
    <section className="exec-card relative flex flex-col gap-5 p-6 report-cover">
      <span
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-[4px] rounded-t-[var(--radius)] bg-gradient-to-r from-violet-500 via-primary to-sky-500"
      />
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-[var(--radius)] bg-gradient-to-br from-primary/10 via-transparent to-violet-500/10"
      />
      <div className="relative grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto] lg:items-start">
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-3">
            <Logo size="md" variant="compact" />
            <span className="text-border">|</span>
            <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
              <Sparkles className="size-3" aria-hidden="true" /> {greeting} Executive Briefing
            </span>
          </div>
          <h1 className="text-2xl font-black leading-tight text-foreground sm:text-3xl">
            {hero
              ? `${hero.score}/100 — ${hero.band}`
              : "Business Executive Report"}
          </h1>
          <p className="text-sm text-muted-foreground">
            Generated {today}. A consolidated read of the business across every
            analytical engine — print-ready, downloadable as PDF.
          </p>
        </div>
        <div className="report-no-print flex flex-wrap items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            aria-label={isRefreshing ? "Refreshing report" : "Refresh report"}
          >
            <RefreshCcw
              className={cn(
                "size-4 transition-transform",
                isRefreshing && "animate-spin",
              )}
              aria-hidden="true"
            />
            <span className="hidden sm:inline">
              {isRefreshing ? "Refreshing" : "Refresh"}
            </span>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePrint}
            aria-label="Print report"
          >
            <Printer className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Print Report</span>
          </Button>
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={async () => {
              try {
                const res = await fetch(
                  "/api/v1/reports/pdf?report_type=executive",
                  { credentials: "include" },
                );
                if (res.ok) {
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "Executive_Business_Report.pdf";
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                  return;
                }
              } catch {
                // ignore
              }
              handlePrint();
            }}
            aria-label="Download PDF Report"
          >
            <Download className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Download PDF</span>
          </Button>
        </div>
      </div>
      {hero && (
        <div className="report-grid-6 relative grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <ExecutiveKpiCard
            badge="Score"
            label="Overall"
            value={hero.score}
            tone={hero.score >= 70 ? "success" : hero.score >= 40 ? "warn" : "danger"}
            caption={hero.band}
          />
          <ExecutiveKpiCard
            badge="DNA"
            label="DNA Match"
            value={hero.dna}
            tone="violet"
            caption="Archetype fit"
          />
          <ExecutiveKpiCard
            badge="Actions"
            label="Recommendations"
            value={hero.recommendations}
            tone="primary"
            caption="Prioritised"
          />
          <ExecutiveKpiCard
            badge="Risk"
            label="Active risks"
            value={hero.risks}
            tone={hero.risks > 3 ? "danger" : hero.risks > 0 ? "warn" : "success"}
            caption="From engine"
          />
          <ExecutiveKpiCard
            badge="Opportunity"
            label="Open opportunities"
            value={hero.opportunities}
            tone="success"
            caption="Untapped upside"
          />
          <ExecutiveKpiCard
            badge="Uplift"
            label="12-month lift"
            value={hero.improvement}
            suffix="pts"
            tone="primary"
            caption="Projected"
          />
        </div>
      )}
      <div className="relative flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="size-1.5 rounded-full bg-primary"
            aria-hidden="true"
          />
          Last analysis
        </span>
        <span className="font-mono text-foreground">
          {lastAnalyzedAt ? formatTimestamp(lastAnalyzedAt) : "—"}
        </span>
      </div>
    </section>
  );
}

function greetByHour(hour: number): string {
  if (hour < 5) return "Late Evening";
  if (hour < 12) return "Morning";
  if (hour < 17) return "Afternoon";
  if (hour < 21) return "Evening";
  return "Night";
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// Defeat unused-import lint if AnimatedCounter is removed during edits.
void AnimatedCounter;

"use client";

import React from "react";
import { Sparkles, AlertTriangle, HelpCircle, LineChart } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Shape matches the AI-5 ``ScenarioAnalysis.to_dict()`` env.
 *
 * The wire is a dict — the card accepts the raw envelope and
 * tolerates missing fields (every field defaults to a safe
 * empty).  The contract:
 *
 *   - scenario_name: string
 *   - baseline: list[str]
 *   - changes: list[str]
 *   - assumptions: list[str]
 *   - calculation_method: string
 *   - estimated_effects: list[str]
 *   - risks: list[str]
 *   - unknowns: list[str]
 *   - sensitivity: list[str]
 *   - confidence: "low" | "medium" | "high" | "unknown"
 *   - disclaimer: string (always "Illustrative scenario — not a prediction.")
 *   - present: bool (always true on a non-null envelope)
 */
export interface ScenarioAnalysis {
  scenario_name?: string;
  baseline?: string[];
  changes?: string[];
  assumptions?: string[];
  calculation_method?: string;
  estimated_effects?: string[];
  risks?: string[];
  unknowns?: string[];
  sensitivity?: string[];
  confidence?: string;
  disclaimer?: string;
  present?: boolean;
}

interface ScenarioAnalysisCardProps {
  /** The structured 10-field envelope from the AI-5 backend. */
  analysis: ScenarioAnalysis | null;
  /** Optional className passthrough for positioning. */
  className?: string;
}

/**
 * The AI-5 "What if" card.
 *
 * Sprint AI-5 — Business Scenario Copilot. Renders the
 * structured envelope from the chat endpoint directly above
 * the assistant message body. The card is hidden entirely
 * when ``analysis`` is null (the non-scenario path).
 *
 * Layout
 * ------
 *  - Header: scenario name + confidence chip
 *  - Two-column "Baseline | Target" (changes + baseline)
 *  - Estimated effects (bullet list)
 *  - Risks (bullet list with warning icon)
 *  - Unknowns (bullet list with help icon)
 *  - Sensitivity (bullet list)
 *  - Calculation method (collapsed details)
 *  - Disclaimer (italic, bottom)
 *
 * The card is intentionally compact — the chat surface is
 * narrow. Every section is collapsible but defaults to open
 * so the reader sees the full envelope at a glance.
 */
export function ScenarioAnalysisCard({
  analysis,
  className,
}: ScenarioAnalysisCardProps) {
  if (!analysis || analysis.present === false) return null;

  const confidence = (analysis.confidence || "unknown").toLowerCase();
  const confidenceChip = confidenceChipStyles(confidence);

  return (
    <section
      data-testid="scenario-analysis-card"
      aria-label="Business scenario analysis"
      className={cn(
        "w-full rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card shadow-soft transition-shadow hover:shadow-md",
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary"
          >
            <LineChart className="size-3.5" />
          </span>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">
            {analysis.scenario_name || "Scenario analysis"}
          </h3>
        </div>
        <span
          className={cn(
            "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
            confidenceChip,
          )}
          title={`Model confidence: ${confidence}`}
        >
          {confidence}
        </span>
      </header>

      <div className="space-y-4 p-4">
        {/* Baseline & Changes — two columns on sm+, stacked on mobile */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Section
            title="Baseline"
            items={analysis.baseline}
            emptyText="No baseline values surfaced."
          />
          <Section
            title="Target / Changes"
            items={analysis.changes}
            emptyText="No change specified."
          />
        </div>

        {/* Estimated effects */}
        <Section
          title="Estimated effects"
          items={analysis.estimated_effects}
          emptyText="Effects not estimated."
          icon={<Sparkles className="size-3.5 text-primary" />}
        />

        {/* Risks */}
        <Section
          title="Risks"
          items={analysis.risks}
          emptyText="No risks surfaced."
          icon={<AlertTriangle className="size-3.5 text-amber-500" />}
        />

        {/* Unknowns */}
        <Section
          title="Unknowns"
          items={analysis.unknowns}
          emptyText="No unknowns flagged."
          icon={<HelpCircle className="size-3.5 text-sky-500" />}
        />

        {/* Sensitivity */}
        <Section
          title="Sensitivity"
          items={analysis.sensitivity}
          emptyText="No sensitivity analysis."
        />

        {/* Assumptions */}
        <Section
          title="Assumptions"
          items={analysis.assumptions}
          emptyText="No assumptions explicit."
        />

        {/* Calculation method — collapsed details */}
        {analysis.calculation_method ? (
          <details className="rounded-md border border-dashed border-border/60 bg-background/40 px-3 py-2 text-xs">
            <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Calculation method
            </summary>
            <p className="mt-2 text-foreground/80">{analysis.calculation_method}</p>
          </details>
        ) : null}

        {/* Disclaimer — always last, italic, muted */}
        <p className="border-t border-border/40 pt-3 text-[11px] italic text-muted-foreground">
          {analysis.disclaimer || "Illustrative scenario — not a prediction."}
        </p>
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Sub-components                                                              //
// --------------------------------------------------------------------------- //

function Section({
  title,
  items,
  emptyText,
  icon,
}: {
  title: string;
  items?: string[] | null;
  emptyText: string;
  icon?: React.ReactNode;
}) {
  const list = Array.isArray(items) ? items : [];
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {icon ? <span aria-hidden="true">{icon}</span> : null}
        {title}
      </h4>
      {list.length === 0 ? (
        <p className="text-xs text-muted-foreground/70">{emptyText}</p>
      ) : (
        <ul className="space-y-1 text-xs text-foreground/85">
          {list.map((item, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span
                aria-hidden="true"
                className="mt-1.5 inline-block size-1 shrink-0 rounded-full bg-primary/60"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function confidenceChipStyles(confidence: string): string {
  switch (confidence) {
    case "high":
      return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400";
    case "medium":
      return "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400";
    case "low":
      return "bg-rose-500/10 text-rose-600 border-rose-500/20 dark:text-rose-400";
    default:
      return "bg-sky-500/10 text-sky-600 border-sky-500/20 dark:text-sky-400";
  }
}

export default ScenarioAnalysisCard;

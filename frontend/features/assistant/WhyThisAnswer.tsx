/**
 * SPRINT AI-15 — WhyThisAnswer disclosure panel.
 *
 * Renders the "Why this answer?" disclosure panel with the five
 * mandated sections (Evidence / Calculations / Assumptions /
 * Uncertainty / Alternatives) plus the AI-15-aligned tools_used /
 * tool_failures / confidence_change + quality_warning fields.
 *
 * Collapsed by default. Empty sections render no row.
 */

import React, { useState } from "react";
import type { TrustSummary } from "@/features/assistant/types";

export interface WhyThisAnswerProps {
  trust_summary?: TrustSummary | null;
}

type SectionKey =
  | "evidence"
  | "calculations"
  | "assumptions"
  | "uncertainty"
  | "alternatives"
  | "tools_used"
  | "tool_failures";

const SECTIONS: Array<{
  key: SectionKey;
  title: string;
  description: string;
}> = [
  {
    key: "evidence",
    title: "Evidence",
    description: "Business facts the engine consulted to answer this.",
  },
  {
    key: "calculations",
    title: "Calculations",
    description: "Numeric outputs with formula + source.",
  },
  {
    key: "assumptions",
    title: "Assumptions",
    description: "Declared assumptions the answer relies on.",
  },
  {
    key: "uncertainty",
    title: "Uncertainty",
    description: "Unknowns + low-confidence items.",
  },
  {
    key: "alternatives",
    title: "Alternatives",
    description: "Alternate interpretations the engine considered.",
  },
  {
    key: "tools_used",
    title: "Tools used",
    description: "Whitelisted tools the engine invoked.",
  },
  {
    key: "tool_failures",
    title: "Tool failures",
    description: "Tools that were skipped or errored out, with reasons.",
  },
];

export function WhyThisAnswer(props: WhyThisAnswerProps): React.JSX.Element | null {
  const ts = props.trust_summary;
  const [open, setOpen] = useState<boolean>(false);

  if (
    !ts ||
    (
      SECTIONS.every((s) => {
        const items = (ts as unknown as Record<string, unknown>)[s.key];
        return !items || (Array.isArray(items) && items.length === 0);
      }) &&
      !ts.confidence_change &&
      !ts.quality_warning
    )
  ) {
    return null;
  }

  return (
    <div
      className="rounded-lg border border-slate-200 bg-slate-50 text-slate-900"
      data-testid="why-this-answer"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-t-lg px-4 py-3 text-left text-sm font-medium hover:bg-slate-100"
      >
        <span>Why this answer?</span>
        <span className="text-xs text-slate-500">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-200 px-4 pb-4 pt-3">
          {ts.confidence_change && (
            <div className="mb-3 text-xs text-slate-500">
              Confidence: <span className="font-medium">{ts.confidence_change}</span>
            </div>
          )}
          {ts.quality_warning && (
            <div className="mb-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {ts.quality_warning}
            </div>
          )}
          {SECTIONS.map((s) => {
            const items = (ts as unknown as Record<string, unknown>)[
              s.key
            ] as unknown[] | undefined;
            if (!Array.isArray(items) || items.length === 0) return null;
            return (
              <section
                key={s.key}
                className="mt-3 first:mt-0"
                aria-label={s.title}
              >
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                  {s.title}
                </h4>
                <p className="text-[11px] text-slate-500">{s.description}</p>
                {s.key === "tool_failures" ? (
                  <ul className="mt-2 space-y-1 text-xs">
                    {(items as TrustSummary["tool_failures"]).map((f, i) => (
                      <li
                        key={i}
                        className="rounded border border-rose-200 bg-rose-50 px-2 py-1 text-rose-900"
                      >
                        <span className="font-medium">{f.tool}</span>{" "}
                        <span className="text-rose-700">[{f.status}]</span>{" "}
                        <span className="text-rose-700">{f.error}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-700">
                    {(items as string[]).map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default WhyThisAnswer;

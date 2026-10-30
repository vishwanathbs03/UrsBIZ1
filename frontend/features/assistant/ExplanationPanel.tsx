"use client";

/**
 * SPRINT AI-10 — Explain My Answer.
 *
 * Renders one `DecisionTrace` (the per-recommendation 6-section
 * provenance) as a collapsible accordion.
 *
 * Every string in the trace comes from structured provenance
 * metadata — the backend's
 * :mod:`app.services.ai.trace.builder` builds the trace from
 * the upstream ``Recommendation`` payload + ``EvidenceRegistry``.
 * No LLM chain-of-thought is ever exposed.
 *
 * Sections rendered (only when their list is non-empty):
 *   - Evidence      → `{id, label, value}` bullets
 *   - Calculations  → table of `name | formula | result`
 *   - Decision factors → bullet list with source footnotes
 *   - Assumptions    → bullet list
 *   - Uncertainty    → bulleted warnings with ⚠ icon
 *   - Alternatives   → chips with rec-id + relation arrows
 *
 * Confidence label rendered as a footer pill from the literal
 * `confidence_label` field.
 */

import React, { useState } from "react";

import {
  DecisionTrace,
  TraceAlternative,
  TraceAssumption,
  TraceCalculationItem,
  TraceDecisionFactor,
  TraceEvidenceItem,
  TraceUncertainty,
} from "./types";

export interface ExplanationPanelProps {
  /** The decision trace to render. */
  trace: DecisionTrace;
  /** Optional click handler for evidence items (deep-link). */
  onEvidenceClick?: (evidenceId: string) => void;
}

const SECTION_ORDER: Array<{
  key: keyof Pick<
    DecisionTrace,
    | "evidence"
    | "calculations"
    | "decision_factors"
    | "assumptions"
    | "uncertainty"
    | "alternatives"
  >;
  label: string;
  icon: string;
}> = [
  { key: "evidence", label: "Evidence", icon: "📊" },
  { key: "calculations", label: "Calculations", icon: "🧮" },
  { key: "decision_factors", label: "Decision factors", icon: "🎯" },
  { key: "assumptions", label: "Assumptions", icon: "📌" },
  { key: "uncertainty", label: "Uncertainty", icon: "⚠️" },
  { key: "alternatives", label: "Alternatives", icon: "🔀" },
];

export function ExplanationPanel({
  trace,
  onEvidenceClick,
}: ExplanationPanelProps) {
  const [openSections, setOpenSections] = useState<Set<string>>(
    () => new Set(SECTION_ORDER.map((s) => s.key)),
  );

  // Hide the panel entirely when the trace has no content —
  // the brief's example is meant for "material" recommendations
  // and a minimal rec legitimately has no trace content.
  const hasAnySection = SECTION_ORDER.some(
    (s) => Array.isArray(trace[s.key]) && trace[s.key].length > 0,
  );
  if (!hasAnySection && !trace.confidence_label) {
    return null;
  }

  const toggleSection = (key: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <div
      data-testid="explanation-panel"
      data-recommendation-id={trace.recommendation_id}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <header className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-900">
            Explain this answer
          </h4>
          <p className="text-xs text-slate-500">
            Decision trace for{" "}
            <code className="rounded bg-slate-100 px-1 text-[11px]">
              {trace.recommendation_id}
            </code>
          </p>
        </div>
        {trace.confidence_label ? (
          <span
            className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800"
            data-testid="confidence-label"
          >
            {trace.confidence_label}
          </span>
        ) : null}
      </header>

      <ul className="divide-y divide-slate-100">
        {SECTION_ORDER.map((section) => {
          const items = trace[section.key];
          if (!Array.isArray(items) || items.length === 0) {
            return null;
          }
          const isOpen = openSections.has(section.key);
          return (
            <li key={section.key} className="py-2">
              <button
                type="button"
                onClick={() => toggleSection(section.key)}
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-slate-800 hover:text-slate-900"
                data-testid={`explanation-section-${section.key}`}
              >
                <span className="flex items-center gap-2">
                  <span aria-hidden>{section.icon}</span>
                  <span>{section.label}</span>
                  <span className="text-[11px] text-slate-400">
                    ({items.length})
                  </span>
                </span>
                <span
                  aria-hidden
                  className={`text-slate-400 transition-transform ${
                    isOpen ? "rotate-90" : ""
                  }`}
                >
                  ▶
                </span>
              </button>
              {isOpen ? (
                <div className="mt-2 pl-7 text-[13px] text-slate-700">
                  {renderSection(section.key, items, onEvidenceClick)}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      <footer className="mt-3 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
        Trace generated from structured provenance metadata. No LLM reasoning is
        exposed.
      </footer>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section renderers
// --------------------------------------------------------------------------- //

function renderSection(
  key:
    | "evidence"
    | "calculations"
    | "decision_factors"
    | "assumptions"
    | "uncertainty"
    | "alternatives",
  items: unknown,
  onEvidenceClick: ((id: string) => void) | undefined,
): React.ReactElement {
  switch (key) {
    case "evidence":
      return <EvidenceList items={items as TraceEvidenceItem[]} onClick={onEvidenceClick} />;
    case "calculations":
      return <CalculationsTable items={items as TraceCalculationItem[]} />;
    case "decision_factors":
      return <FactorList items={items as TraceDecisionFactor[]} />;
    case "assumptions":
      return <AssumptionList items={items as TraceAssumption[]} />;
    case "uncertainty":
      return <UncertaintyList items={items as TraceUncertainty[]} />;
    case "alternatives":
      return <AlternativesList items={items as TraceAlternative[]} />;
    default:
      return <></>;
  }
}

function EvidenceList({
  items,
  onClick,
}: {
  items: TraceEvidenceItem[];
  onClick: ((id: string) => void) | undefined;
}): React.ReactElement {
  return (
    <ul className="space-y-1.5">
      {items.map((e) => (
        <li key={e.id} className="flex items-start gap-2">
          <button
            type="button"
            onClick={onClick ? () => onClick(e.id) : undefined}
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700 hover:bg-slate-200"
            data-testid="evidence-id"
          >
            {e.id}
          </button>
          <div className="flex-1">
            <div className="font-medium text-slate-800">{e.label}</div>
            <div className="text-[12px] text-slate-500">{e.value}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function CalculationsTable({
  items,
}: {
  items: TraceCalculationItem[];
}): React.ReactElement {
  return (
    <table className="w-full text-left text-[12px]">
      <thead>
        <tr className="border-b border-slate-200 text-slate-500">
          <th className="py-1 pr-2 font-medium">Calc</th>
          <th className="py-1 pr-2 font-medium">Formula</th>
          <th className="py-1 font-medium">Result</th>
        </tr>
      </thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.name} className="border-b border-slate-100">
            <td className="py-1 pr-2 font-medium text-slate-800">{c.name}</td>
            <td className="py-1 pr-2 font-mono text-[11px] text-slate-600">
              {c.formula}
            </td>
            <td className="py-1 font-mono text-slate-900">{c.result}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FactorList({
  items,
}: {
  items: TraceDecisionFactor[];
}): React.ReactElement {
  return (
    <ul className="list-disc space-y-1 pl-4">
      {items.map((f, i) => (
        <li key={`${f.source}-${i}`}>
          {f.factor}
          {f.source ? (
            <span className="ml-1 font-mono text-[10px] text-slate-400">
              [{f.source}]
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function AssumptionList({
  items,
}: {
  items: TraceAssumption[];
}): React.ReactElement {
  return (
    <ul className="list-disc space-y-1 pl-4">
      {items.map((a, i) => (
        <li key={`${a.source}-${i}`}>
          {a.text}
          {a.source ? (
            <span className="ml-1 font-mono text-[10px] text-slate-400">
              [{a.source}]
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function UncertaintyList({
  items,
}: {
  items: TraceUncertainty[];
}): React.ReactElement {
  return (
    <ul className="space-y-1.5">
      {items.map((u, i) => (
        <li key={`${u.source}-${i}`} className="flex items-start gap-2">
          <span aria-hidden className="text-amber-500">
            ⚠
          </span>
          <div className="flex-1">
            <div>{u.text}</div>
            {u.source ? (
              <div className="font-mono text-[10px] text-slate-400">
                {u.source}
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

function AlternativesList({
  items,
}: {
  items: TraceAlternative[];
}): React.ReactElement {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((alt) => {
        const arrow =
          alt.relation === "blocks"
            ? "←"
            : alt.relation === "is_blocked_by"
              ? "→"
              : "·";
        return (
          <li key={alt.id}>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700">
              <span aria-hidden className="text-slate-400">
                {arrow}
              </span>
              <code className="font-mono text-[10px]">{alt.id}</code>
              <span className="text-slate-600">{alt.title}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Stack — renders one ExplanationPanel per recommendation
// --------------------------------------------------------------------------- //

export interface ExplanationPanelStackProps {
  explanations: Record<string, DecisionTrace>;
  onEvidenceClick?: (id: string) => void;
}

export function ExplanationPanelStack({
  explanations,
  onEvidenceClick,
}: ExplanationPanelStackProps) {
  const entries = Object.entries(explanations);
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="mt-4 space-y-3" data-testid="explanation-stack">
      {entries.map(([recId, trace]) => (
        <ExplanationPanel
          key={recId}
          trace={trace}
          onEvidenceClick={onEvidenceClick}
        />
      ))}
    </div>
  );
}

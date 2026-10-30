"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The EvidencePanel —
 * the expandable evidence surface the brief mandates.
 *
 * The brief example:
 *
 *   Why?
 *   ▼ Evidence used
 *   Revenue ₹1.80 Cr
 *   Health score 68/100
 *   Supplier concentration 75%
 *   Recommendation: Vendor diversification
 *
 * The concrete values ("Revenue ₹1.80 Cr", "Health score
 * 68/100", "Supplier concentration 75%") are the first 5 rows
 * — visible by default, full-width, no horizontal scroll. The
 * raw evidence IDs (e.g. ``biz_profile_revenue``) are hidden
 * behind a "Show raw evidence IDs" toggle so the engineer
 * debugging can still see them without overwhelming the user.
 *
 * The panel is mounted inside the "Evidence" secondary card,
 * which is itself collapsed by default. When the user expands
 * Evidence, the panel stays open via the <details> element.
 */

import { Award, Code2 } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  type NormalizedEvidenceItem,
  normalizeEvidence,
  type AssistantContextSnapshot,
} from "./sections/normalizeEvidence";

export interface EvidencePanelProps {
  /** Raw evidence IDs from the wire. */
  ids: readonly string[];
  /** Snapshot of the business context for resolving concrete values. */
  context?: AssistantContextSnapshot | null;
  /** Optional className passthrough. */
  className?: string;
}

export function EvidencePanel({ ids, context, className }: EvidencePanelProps) {
  const items = normalizeEvidence(ids ?? [], context);
  const [showRaw, setShowRaw] = useState(false);
  if (items.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No evidence surfaced for this response.
      </p>
    );
  }
  return (
    <div className={cn("space-y-3", className)} data-testid="evidence-panel">
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex items-start justify-between gap-2 rounded-md bg-background/40 px-2 py-1.5 text-xs"
          >
            <span className="flex items-start gap-1.5">
              <Award
                className="mt-0.5 size-3 shrink-0 text-amber-500"
                aria-hidden="true"
              />
              <span className="font-medium text-foreground/90">{item.label}</span>
            </span>
            <span className="text-right tabular-nums text-foreground/80">
              {item.value}
            </span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setShowRaw((prev) => !prev)}
        aria-expanded={showRaw}
        className="inline-flex min-h-[32px] items-center gap-1 rounded-md border border-dashed border-border/60 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground transition-colors hover:bg-secondary/40"
      >
        <Code2 className="size-3" aria-hidden="true" />
        {showRaw ? "Hide raw evidence IDs" : "Show raw evidence IDs"}
      </button>
      {showRaw ? (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((item: NormalizedEvidenceItem) => (
            <li key={item.id}>
              <code className="rounded-full bg-secondary/60 px-2 py-0.5 text-[10px] font-mono text-foreground/80">
                {item.id}
              </code>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default EvidencePanel;

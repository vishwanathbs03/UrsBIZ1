"use client";

/**
 * SPRINT AI-16 — Freshness-warning inline notice.
 *
 * Renders the list of external sources whose freshness bucket
 * is AGING / STALE / UNKNOWN. The brief asks for a single
 * inline amber-bordered notice that says "This answer used N
 * sources past their safe window — re-verify before relying
 * on them." The list of individual sources is collapsible so
 * the default render stays compact.
 *
 * Visual contract
 * ---------------
 *
 *   * Amber border + amber-50 background — matches the AI-15
 *     quality-warning strip + the AI-7 MissingInfoCard
 *     visual language.
 *   * Icon + text + count — never colour-only.
 *   * The individual source list is collapsed by default; an
 *     inline ``<details>`` reveals it on demand.
 *   * Mobile: stacks to a single column.
 */

import { AlertTriangle } from "lucide-react";
import type { FreshnessWarning } from "./types";

export interface FreshnessWarningsListProps {
  items: FreshnessWarning[];
}

export function FreshnessWarningsList({ items }: FreshnessWarningsListProps) {
  if (!items || items.length === 0) return null;

  const noun = items.length === 1 ? "source" : "sources";
  const headline =
    items.length === 1
      ? "This answer used 1 source past its safe window — re-verify before relying on it."
      : `This answer used ${items.length} ${noun} past their safe window — re-verify before relying on them.`;

  return (
    <aside
      role="note"
      aria-label="Freshness warnings"
      data-testid="freshness-warnings"
      className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
          aria-hidden="true"
        />
        <div className="flex-1">
          <p className="font-medium">{headline}</p>
          <details className="mt-1">
            <summary className="cursor-pointer text-xs text-amber-800">
              View {items.length} flagged {noun}
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-900">
              {items.map((w, i) => (
                <li key={i}>
                  <span className="font-medium">
                    {w.title ?? w.url ?? "Unnamed source"}
                  </span>
                  {w.freshness ? (
                    <span className="ml-2 inline-flex items-center rounded border border-amber-300 bg-white px-1.5 py-0.5 text-[10px] uppercase">
                      {w.freshness}
                    </span>
                  ) : null}
                  {w.last_verified ? (
                    <span className="ml-2 text-amber-700">
                      (last verified {w.last_verified})
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </details>
        </div>
      </div>
    </aside>
  );
}

export default FreshnessWarningsList;
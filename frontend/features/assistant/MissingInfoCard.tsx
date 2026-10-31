"use client";

/**
 * SPRINT AI-7 — Missing-data intelligence card.
 *
 * The upgraded secondary card for the "Missing information"
 * section of ``TrustFirstResponse``. When the wire carries
 * structured ``MissingDataObject`` rows (the AI-7 brief's
 * proactive detector output), renders the 4-section layout:
 *
 *   1. What I can tell   — verified facts the assistant
 *                         already has for this intent
 *                         (annual revenue, headcount, etc.).
 *   2. What I am missing — the structured rows with HIGH /
 *                         MEDIUM / LOW chips + reason +
 *                         "Affects:" + "Source:" disclosure.
 *   3. Why it matters    — one aggregate sentence.
 *   4. Next step         — prompts the user to fill them.
 *
 * When the wire is empty, falls back to the legacy prose path
 * (``MissingInfoBody`` in ``TrustFirstResponse``) so AI-6 +
 * AI-7 callers render identically.
 *
 * Visual contract
 * ---------------
 *
 *   * Each row stacks vertically on mobile — label + chip on
 *     the first row, reason below, "Affects" + "Source" on
 *     the third. No horizontal scrolling.
 *   * The chip uses **text + colour + icon** — HIGH = red +
 *     AlertTriangle + "HIGH", MEDIUM = amber + AlertCircle,
 *     LOW = slate + Info. Never colour-only.
 *   * Each row is an ``<li>`` inside an ``<ol>`` so screen
 *     readers announce the ordinal ("Item 1 of 3").
 *   * The chip carries ``aria-label="Importance: HIGH"`` so
 *     the importance tier is announced.
 *   * "Why it matters" is a ``<p role="note">`` so it's
 *     grouped semantically.
 */

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";
import type { ChatMessage, MissingDataObject } from "./types";

export interface MissingInfoCardProps {
  message: ChatMessage;
  /**
   * Optional local fallback rows the client-side consultant
   * computed when the backend round-trip was skipped. The
   * wire-mirror rows take precedence; the fallback is only
   * read when the wire is empty.
   */
  fallbackRows?: readonly MissingDataObject[];
  /** Verified facts the assistant already knows. */
  verifiedFacts?: readonly string[];
}

export function MissingInfoCard({
  message,
  fallbackRows,
  verifiedFacts,
}: MissingInfoCardProps) {
  const wireRows = message.missing_data ?? [];
  const rows: MissingDataObject[] =
    wireRows.length > 0
      ? wireRows
      : (fallbackRows ? [...fallbackRows] : []);

  // Sort HIGH first, then MEDIUM, then LOW. The brief is
  // explicit that the most important gap leads.
  const sorted = [...rows].sort(importanceRank);

  if (sorted.length === 0) {
    return (
      <p
        data-testid="missing-info-empty"
        className="text-xs text-muted-foreground"
      >
        No missing information flagged for this response.
      </p>
    );
  }

  return (
    <div data-testid="missing-info-card" className="space-y-3">
      {/* 1. What I can tell */}
      {verifiedFacts && verifiedFacts.length > 0 ? (
        <WhatICanTell facts={verifiedFacts} />
      ) : null}

      {/* 2. What I am missing — the structured rows */}
      <WhatIAmMissing rows={sorted} />

      {/* 3. Why it matters — aggregate */}
      <WhyItMatters rows={sorted} />

      {/* 4. Next step */}
      <NextStep rows={sorted} />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section 1 — What I can tell
// --------------------------------------------------------------------------- //

function WhatICanTell({ facts }: { facts: readonly string[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        What I can tell
      </h4>
      <ul className="space-y-1.5" data-testid="missing-info-what-i-can-tell">
        {facts.slice(0, 6).map((fact, i) => (
          <li
            key={i}
            className="flex items-start gap-1.5 rounded-md bg-emerald-500/5 px-2 py-1.5 text-xs text-foreground/90"
          >
            <CheckCircle2
              className="mt-0.5 size-3 shrink-0 text-emerald-500"
              aria-hidden="true"
            />
            <span>{fact}</span>
          </li>
        ))}
        {facts.length > 6 ? (
          <li className="px-2 text-[10px] text-muted-foreground">
            + {facts.length - 6} more verified fact
            {facts.length - 6 === 1 ? "" : "s"} on your profile.
          </li>
        ) : null}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section 2 — What I am missing (the structured rows)
// --------------------------------------------------------------------------- //

function WhatIAmMissing({ rows }: { rows: readonly MissingDataObject[] }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        What I am missing
      </h4>
      <ol
        className="space-y-2"
        data-testid="missing-info-rows"
        aria-label="Structured missing data rows"
      >
        {rows.slice(0, 6).map((row, i) => (
          <MissingRow key={`${row.field}-${i}`} row={row} ordinal={i + 1} />
        ))}
      </ol>
      {rows.length > 6 ? (
        <p className="px-2 text-[10px] text-muted-foreground">
          + {rows.length - 6} more row{rows.length - 6 === 1 ? "" : "s"} —
          see Technical Provenance for the full list.
        </p>
      ) : null}
    </div>
  );
}

function MissingRow({
  row,
  ordinal,
}: {
  row: MissingDataObject;
  ordinal: number;
}) {
  return (
    <li
      data-testid="missing-info-row"
      data-importance={row.importance}
      className="rounded-md border border-border/40 bg-background/40 p-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold tabular-nums text-muted-foreground">
          {ordinal}.
        </span>
        <ImportanceChip value={row.importance} />
        <span className="font-mono text-xs text-foreground/90">
          {humaniseFieldName(row.field)}
        </span>
      </div>
      {row.reason ? (
        <p className="mt-1 text-xs text-foreground/90">{row.reason}</p>
      ) : null}
      <div className="mt-1 grid gap-1 text-[10px] text-muted-foreground sm:grid-cols-2">
        {row.affects && row.affects.length > 0 ? (
          <p>
            <span className="font-medium uppercase tracking-wide">Affects:</span>{" "}
            {row.affects.join(", ")}
          </p>
        ) : null}
        {row.suggested_source ? (
          <p>
            <span className="font-medium uppercase tracking-wide">Source:</span>{" "}
            {row.suggested_source}
          </p>
        ) : null}
      </div>
    </li>
  );
}

function ImportanceChip({
  value,
}: {
  value: MissingDataObject["importance"];
}) {
  const Icon = chipIcon(value);
  const tone = chipTone(value);
  return (
    <span
      data-testid="missing-info-chip"
      data-importance={value}
      aria-label={`Importance: ${value}`}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${tone}`}
    >
      <Icon className="size-3" aria-hidden="true" />
      {value}
    </span>
  );
}

function chipIcon(value: MissingDataObject["importance"]) {
  switch (value) {
    case "HIGH":
      return AlertTriangle;
    case "MEDIUM":
      return AlertCircle;
    case "LOW":
      return Info;
  }
}

function chipTone(value: MissingDataObject["importance"]) {
  switch (value) {
    case "HIGH":
      return "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300";
    case "MEDIUM":
      return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "LOW":
      return "border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-300";
  }
}

// --------------------------------------------------------------------------- //
// Section 3 — Why it matters (aggregate)
// --------------------------------------------------------------------------- //

function WhyItMatters({ rows }: { rows: readonly MissingDataObject[] }) {
  const high = rows.filter((r) => r.importance === "HIGH").length;
  const medium = rows.filter((r) => r.importance === "MEDIUM").length;
  const low = rows.filter((r) => r.importance === "LOW").length;
  const parts: string[] = [];
  if (high > 0) {
    parts.push(
      `${high} HIGH-importance gap${high === 1 ? "" : "s"} ` +
        `block${high === 1 ? "s" : ""} the primary answer`,
    );
  }
  if (medium > 0) {
    parts.push(
      `${medium} MEDIUM-importance gap${medium === 1 ? "" : "s"} ` +
        `limit${medium === 1 ? "s" : ""} the supporting analysis`,
    );
  }
  if (low > 0) {
    parts.push(
      `${low} LOW-importance gap${low === 1 ? "" : "s"} ` +
        `could sharpen the recommendation`,
    );
  }
  if (parts.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Why it matters
      </h4>
      <p role="note" className="text-xs leading-snug text-foreground/90">
        {parts.join("; ")}.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Section 4 — Next step
// --------------------------------------------------------------------------- //

function NextStep({ rows }: { rows: readonly MissingDataObject[] }) {
  const first = rows[0];
  const affects = first?.affects?.[0] ?? "this analysis";
  const lead = first
    ? humaniseFieldName(first.field)
    : "the missing fields";
  return (
    <div className="space-y-1.5">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Next step
      </h4>
      <p className="text-xs leading-snug text-foreground/90">
        Update your Business Profile with <span className="font-medium">{lead}</span>
        {rows.length > 1 ? " (and the other items above)" : ""} — I can then
        compute <span className="font-medium">{affects.replace(/_/g, " ")}</span>{" "}
        with full confidence.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

function importanceRank(a: MissingDataObject, b: MissingDataObject): number {
  return rankWeight(b.importance) - rankWeight(a.importance);
}

function rankWeight(value: MissingDataObject["importance"]): number {
  switch (value) {
    case "HIGH":
      return 3;
    case "MEDIUM":
      return 2;
    case "LOW":
      return 1;
  }
}

function humaniseFieldName(field: string): string {
  return field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default MissingInfoCard;

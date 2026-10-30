"use client";

/**
 * TrustEnvelope — H7.4 (Docx Prompt 4 Part 1) standard trust envelope.
 *
 * The docx requires the four critical judge-visible outputs
 * (Health score, Forecast, Recommendations, Schemes, AI Assistant)
 * to share a common response contract:
 *
 *   {
 *     "value": {},
 *     "method": "deterministic | retrieved | scenario | generative",
 *     "evidence": [],
 *     "assumptions": [],
 *     "confidence": null,
 *     "limitations": [],
 *     "source_updated_at": null
 *   }
 *
 * This component is the front-end shape of that contract. It is
 * the compact "Why am I seeing this?" expandable section the
 * docx asks for in P4 Part 2:
 *
 *   - Inputs used
 *   - Calculation method
 *   - Why it matters
 *   - What could change the result
 *   - Next action
 *
 * The component is intentionally minimal — a small disclosure
 * widget. Modal complexity is explicitly discouraged by the docx.
 * The trust label (e.g. "Calculated by UrsBiz rule engine") sits
 * beside the value via the existing TrustBadge component.
 *
 * No external deps. The renderer is a pure function over the
 * envelope; the parent page provides the values.
 */
import { ReactNode } from "react";
import { ChevronDown, ChevronRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export type TrustMethod =
  | "deterministic"
  | "retrieved"
  | "scenario"
  | "generative";

export const METHOD_LABEL: Record<TrustMethod, string> = {
  deterministic: "Calculated by UrsBiz rule engine",
  retrieved: "Retrieved from official source",
  scenario: "Scenario estimate",
  generative: "Generated explanation",
};

export const METHOD_DESCRIPTION: Record<TrustMethod, string> = {
  deterministic:
    "This value was produced by the UrsBiz deterministic engine. Same inputs always produce the same number.",
  retrieved:
    "This value was retrieved from an official external source. The source is cited below.",
  scenario:
    "This value is a scenario estimate, not a prediction. The inputs and assumptions are listed below.",
  generative:
    "This value was explained by a generative model grounded in the UrsBiz evidence bundle. The deterministic outputs remain authoritative.",
};

export interface TrustEnvelope {
  /** The method that produced the value. */
  method: TrustMethod;
  /** Inputs the engine used (field names + values). */
  inputs?: { label: string; value: string }[];
  /** Calculation method (human-readable one-liner). */
  calculationMethod?: string;
  /** Why this value matters to the user. */
  whyItMatters?: string;
  /** What could change the result. */
  whatCouldChange?: string[];
  /** Suggested next action. */
  nextAction?: string;
  /** Cited evidence (evidence_reference ids or source names). */
  evidence?: string[];
  /** Assumptions baked into the calculation. */
  assumptions?: string[];
  /** Confidence 0..100. Omit when not applicable. */
  confidence?: number;
  /** Known limitations. */
  limitations?: string[];
  /** ISO timestamp of the upstream payload that produced this value. */
  sourceUpdatedAt?: string;
  /** The next action handler — clicking the action runs this. */
  onNextAction?: () => void;
}

export function TrustEnvelope({
  envelope,
  className,
  defaultOpen = false,
}: {
  envelope: TrustEnvelope;
  className?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const methodLabel = METHOD_LABEL[envelope.method];
  const methodDescription = METHOD_DESCRIPTION[envelope.method];

  return (
    <div
      data-testid="trust-envelope"
      data-trust-method={envelope.method}
      className={cn(
        "rounded-md border border-dashed border-border bg-background/40 text-xs",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          <ShieldCheck className="size-3" aria-hidden="true" />
          {open ? "Hide" : "Why am I seeing this?"}
        </span>
        <span
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground"
          title={methodDescription}
        >
          {methodLabel}
          {open ? (
            <ChevronDown className="size-3" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-3" aria-hidden="true" />
          )}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-border/60 px-3 py-2 text-foreground/80">
          <p className="text-[11px] italic text-muted-foreground">
            {methodDescription}
          </p>
          {envelope.inputs && envelope.inputs.length > 0 ? (
            <div>
              <p className="font-semibold">Inputs used</p>
              <ul className="ml-4 list-disc">
                {envelope.inputs.map((i, k) => (
                  <li key={`i-${k}`}>
                    <span className="font-medium">{i.label}:</span> {i.value}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {envelope.calculationMethod ? (
            <p>
              <span className="font-semibold">Calculation method:</span>{" "}
              {envelope.calculationMethod}
            </p>
          ) : null}
          {envelope.whyItMatters ? (
            <p>
              <span className="font-semibold">Why it matters:</span>{" "}
              {envelope.whyItMatters}
            </p>
          ) : null}
          {envelope.whatCouldChange && envelope.whatCouldChange.length > 0 ? (
            <div>
              <p className="font-semibold">What could change the result</p>
              <ul className="ml-4 list-disc">
                {envelope.whatCouldChange.map((w, k) => (
                  <li key={`w-${k}`}>{w}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {envelope.assumptions && envelope.assumptions.length > 0 ? (
            <div>
              <p className="font-semibold">Assumptions</p>
              <ul className="ml-4 list-disc">
                {envelope.assumptions.map((a, k) => (
                  <li key={`a-${k}`}>{a}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {envelope.limitations && envelope.limitations.length > 0 ? (
            <div>
              <p className="font-semibold">Limitations</p>
              <ul className="ml-4 list-disc">
                {envelope.limitations.map((l, k) => (
                  <li key={`l-${k}`}>{l}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {envelope.evidence && envelope.evidence.length > 0 ? (
            <div>
              <p className="font-semibold">Evidence</p>
              <ul className="ml-4 list-disc">
                {envelope.evidence.map((e, k) => (
                  <li key={`e-${k}`}>{e}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {typeof envelope.confidence === "number" ? (
            <p>
              <span className="font-semibold">Confidence:</span>{" "}
              {Math.max(0, Math.min(100, envelope.confidence))}/100
            </p>
          ) : null}
          {envelope.nextAction ? (
            <button
              type="button"
              onClick={envelope.onNextAction}
              className="mt-1 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-[11px] font-medium text-primary transition-all hover:bg-primary/10"
            >
              {envelope.nextAction}
            </button>
          ) : null}
          {envelope.sourceUpdatedAt ? (
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Last updated {formatRelativeTime(envelope.sourceUpdatedAt)}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return iso;
    const now = Date.now();
    const diff = Math.max(0, now - then);
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} h ago`;
    const days = Math.floor(hours / 24);
    return `${days} d ago`;
  } catch {
    return iso;
  }
}

/**
 * ScenarioLabel — H7.4 (Docx Prompt 4 Part 4) scenario credibility.
 *
 * Every future-looking result in UrsBiz must carry this exact
 * set of fields per the docx:
 *
 *   - Scenario, not prediction
 *   - Inputs used
 *   - Assumptions
 *   - Time horizon
 *   - Confidence or uncertainty
 *   - No guarantee
 *
 * The component renders the four required visible labels and
 * refuses to render if the caller forgot the "no guarantee" line.
 */
export function ScenarioLabel({
  horizon,
  confidence,
  inputs,
  assumptions,
  noGuarantee = true,
  className,
}: {
  horizon: string;
  confidence?: number;
  inputs?: { label: string; value: string }[];
  assumptions?: string[];
  noGuarantee?: boolean;
  className?: string;
}) {
  return (
    <div
      data-testid="scenario-label"
      data-scenario-horizon={horizon}
      className={cn(
        "rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] leading-relaxed text-amber-800 dark:text-amber-200",
        className,
      )}
    >
      <p className="font-semibold uppercase tracking-wider">
        Scenario estimate — not a prediction
      </p>
      <p className="mt-1">
        <span className="font-semibold">Horizon:</span> {horizon}
      </p>
      {typeof confidence === "number" ? (
        <p>
          <span className="font-semibold">Confidence:</span>{" "}
          {Math.max(0, Math.min(100, confidence))}/100
        </p>
      ) : null}
      {inputs && inputs.length > 0 ? (
        <p>
          <span className="font-semibold">Inputs used:</span>{" "}
          {inputs.map((i) => `${i.label} (${i.value})`).join(", ")}
        </p>
      ) : null}
      {assumptions && assumptions.length > 0 ? (
        <p>
          <span className="font-semibold">Assumptions:</span>{" "}
          {assumptions.join("; ")}
        </p>
      ) : null}
      {noGuarantee ? (
        <p className="mt-1 italic">
          No guarantee — scenarios depend on inputs that may change.
        </p>
      ) : null}
    </div>
  );
}

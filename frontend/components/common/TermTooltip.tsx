"use client";

/**
 * TermTooltip — Sprint H6.3 (Part 7).
 *
 * Lightweight, dependency-free, accessible inline tooltip used to
 * clarify standardized terminology in the UrsBiz product. Uses the
 * native `title` attribute (keyboard-accessible via focus) plus an
 * optional underline-dashed visual cue. Avoids Radix / floating-ui
 * dependencies — the goal is consistent wording, not a design
 * system. The `text` prop doubles as the visible label.
 *
 * The brief's required tooltip set (Part 7) is exported as
 * `TERM_DEFINITIONS` so any surface that mentions one of these
 * terms can import the canonical wording and stay aligned.
 */

import React from "react";
import { HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface TermTooltipProps {
  /** The visible label text. */
  text: string;
  /** The tooltip body — what the term means in UrsBiz. */
  definition: string;
  /** When true, render a dashed underline + small help icon. Default true. */
  showIcon?: boolean;
  /** Optional additional className. */
  className?: string;
}

export function TermTooltip({
  text,
  definition,
  showIcon = true,
  className,
}: TermTooltipProps) {
  return (
    <span
      role="button"
      tabIndex={0}
      title={definition}
      aria-label={`${text} — ${definition}`}
      className={cn(
        "inline-flex items-center gap-1 cursor-help",
        showIcon && "border-b border-dashed border-muted-foreground/60",
        className,
      )}
    >
      <span>{text}</span>
      {showIcon && (
        <HelpCircle
          className="size-3 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      )}
    </span>
  );
}

/**
 * Canonical wording for the seven Part 7 terms. Re-use from any
 * surface that mentions the term so the user-visible explanation
 * stays the same across the app.
 */
export const TERM_DEFINITIONS = {
  readiness:
    "How prepared the business is in a given dimension (e.g. digital, export, compliance). Scored 0-100 from the same fields that feed the Business Health Score.",
  maturity:
    "The stage of operational sophistication a business sits at in a given area (for example, Digital Maturity). Higher means more digital tooling, automation, or formal processes are in place.",
  benchmark:
    "An industry baseline number used for comparison. UrsBiz uses deterministic internal baselines only when official public data is unavailable.",
  scenario:
    "A what-if projection computed from your current business profile plus one user-selected lever. Clearly labelled as a scenario estimate, not a forecast.",
  forecastConfidence:
    "How reliable the projected score is. Depends on profile completeness and the depth of historical data the Digital Twin has seen.",
  digitalTwin:
    "A deterministic, structured model of your business built from the same fields that drive the Business Health Score, readiness indices, and recommendations.",
  matchingScore:
    "A similarity score (0-100) between your business profile and an official scheme's known industry / turnover band. Higher means a closer fit. It is not a decision of eligibility or approval — those are decided by the official authority.",
} as const;

export type TermKey = keyof typeof TERM_DEFINITIONS;

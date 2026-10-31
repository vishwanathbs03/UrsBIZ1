"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The 5-label
 * mutually-exclusive TrustBar that replaces the legacy
 * ``TrustBadge`` pill below the bubble.
 *
 * The brief mandates exactly 5 labels:
 *
 *   - "Verified Business Evidence"   grounded LLM, validator passed
 *   - "AI Analysis"                  open-mode LLM, business context used
 *   - "Illustrative Scenario"        "what if" envelope is present
 *   - "Requires Verification"        open-mode LLM, no business context
 *   - "Calculated by UrsBiz"         deterministic rule engine
 *
 * Fully localized for English & Kannada while preserving
 * data-trust-bar-label machine-readable attributes.
 */

import {
  BadgeCheck,
  Cpu,
  Globe,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import type { BriefTrustLabel } from "./sections/mapTrustLabel";

interface TrustBarEntry {
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  tone: string;
}

const TRUST_BAR_COPY: Record<BriefTrustLabel, TrustBarEntry> = {
  verified_business_evidence: {
    Icon: BadgeCheck,
    tone: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  },
  ai_analysis: {
    Icon: Sparkles,
    tone: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  },
  illustrative_scenario: {
    Icon: TrendingUp,
    tone: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
  requires_verification: {
    Icon: Globe,
    tone: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  },
  calculated_by_ursbiz: {
    Icon: Cpu,
    tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  },
};

export interface TrustBarProps {
  /** One of the 5 brief-mandated labels. */
  label: BriefTrustLabel;
  /** Optional 0-100 confidence — rendered as a trailing chip. */
  confidence?: number | null;
  /** Optional className passthrough. */
  className?: string;
}

export function TrustBar({ label, confidence, className }: TrustBarProps) {
  const { language } = useLanguage();
  const entry = TRUST_BAR_COPY[label];
  const Icon = entry.Icon;
  const text = labelText(label, language);
  return (
    <div
      role="note"
      aria-label={text}
      data-trust-bar-label={label}
      data-testid="trust-bar"
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1.5",
        entry.tone,
        className,
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="truncate text-[11px] font-semibold uppercase tracking-wider">
        {text}
      </span>
      {typeof confidence === "number" && confidence >= 0 && confidence <= 100 ? (
        <span
          aria-label={`Confidence ${confidence} of 100`}
          className="ml-auto shrink-0 rounded-full bg-background/40 px-2 py-0.5 text-[10px] font-medium tabular-nums"
        >
          {confidence}/100
        </span>
      ) : null}
    </div>
  );
}

/**
 * Lookup helper that exposes the localized label copy.
 */
export function labelText(label: BriefTrustLabel, lang: string = "en"): string {
  if (lang === "kn") {
    switch (label) {
      case "verified_business_evidence":
        return "ಪರಿಶೀಲಿತ ವ್ಯವಹಾರ ಪುರಾವೆ";
      case "ai_analysis":
        return "AI ವಿಶ್ಲೇಷಣೆ";
      case "illustrative_scenario":
        return "ಸನ್ನಿವೇಶ ಅಂದಾಜು";
      case "requires_verification":
        return "ಪರಿಶೀಲನೆ ಅಗತ್ಯವಿದೆ";
      case "calculated_by_ursbiz":
        return "UrsBiz ಮೂಲಕ ಲೆಕ್ಕಹಾಕಲಾಗಿದೆ";
    }
  }
  switch (label) {
    case "verified_business_evidence":
      return "Verified Business Evidence";
    case "ai_analysis":
      return "AI Analysis";
    case "illustrative_scenario":
      return "Illustrative Scenario";
    case "requires_verification":
      return "Requires Verification";
    case "calculated_by_ursbiz":
      return "Calculated by UrsBiz";
  }
}

export default TrustBar;
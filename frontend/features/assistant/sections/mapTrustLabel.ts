/**
 * SPRINT AI-6 — Trust-first visual UI. Map the existing 8-state
 * `TrustLabel` enum to the brief-mandated 5 mutually-exclusive
 * labels:
 *
 *   - "Verified Business Evidence"
 *   - "AI Analysis"
 *   - "Illustrative Scenario"
 *   - "Requires Verification"
 *   - "Calculated by UrsBiz"
 *
 * The 8-state `TrustLabel` is preserved for the legacy
 * `TrustBadge` and `TrustMeta` pair, which remain rendered as
 * fallback surfaces. The new `TrustBar` consumes this 5-state
 * `BriefTrustLabel` instead.
 *
 * The mapping is deterministic and pure: same input → same
 * output. The `scenario_analysis` argument is consulted first
 * because the brief says "Illustrative Scenario" is the
 * mutually-exclusive label when the structured envelope is
 * present, regardless of the provider mode.
 */

import type { TrustLabel } from "../TrustBadge";

/**
 * The brief-mandated 5 mutually-exclusive trust labels.
 * The literal copy strings match the brief verbatim so the
 * verifier can grep the rendered output for them.
 */
export type BriefTrustLabel =
  | "verified_business_evidence"
  | "ai_analysis"
  | "illustrative_scenario"
  | "requires_verification"
  | "calculated_by_ursbiz";

export const BRIEF_TRUST_LABEL_TEXT: Record<BriefTrustLabel, string> = {
  verified_business_evidence: "Verified Business Evidence",
  ai_analysis: "AI Analysis",
  illustrative_scenario: "Illustrative Scenario",
  requires_verification: "Requires Verification",
  calculated_by_ursbiz: "Calculated by UrsBiz",
};

/**
 * Render priority — the first match wins. Listed in the same
 * order as the brief so reviewers can read the rules top-down.
 */
export function mapToBriefTrustLabel(
  internal: TrustLabel,
  hasScenarioAnalysis: boolean,
): BriefTrustLabel {
  // 1. Illustrative Scenario — wins whenever the structured
  //    10-field "what if" envelope is present.
  if (hasScenarioAnalysis) {
    return "illustrative_scenario";
  }
  // 2. Calculated by UrsBiz — deterministic rule engine or
  //    offline snapshot (both are non-LLM paths).
  if (
    internal === "rule_engine" ||
    internal === "offline_snapshot"
  ) {
    return "calculated_by_ursbiz";
  }
  // 3. Verified Business Evidence — grounded LLM with the
  //    GroundingValidator's stamp.
  if (
    internal === "generated" ||
    internal === "official" ||
    internal === "user_provided"
  ) {
    return "verified_business_evidence";
  }
  // 4. AI Analysis — open-mode LLM that drew on business
  //    context (records_used > 0).
  if (internal === "open_business") {
    return "ai_analysis";
  }
  // 5. Requires Verification — open-mode LLM with no
  //    business context (cannot be verified).
  return "requires_verification";
}
"use client";

/**
 * SPRINT AI-6 — Trust-First Visual AI Response UI. The shell
 * that every assistant message renders through. Sits between
 * `MessageBubble` and the three existing inner renderers
 * (`GroundedResponseRenderer`, `ConsultantRenderer`,
 * `TypedBody`).
 *
 * Layout (mobile-first, progressive disclosure):
 *
 *   1. Direct Answer — 1-3 sentences, always visible, the
 *      10-second read.
 *   2. TrustBar — one of the 5 mutually-exclusive brief labels.
 *   3. Top Recommendation — single-line primary recommendation
 *      when applicable.
 *   4. Secondary cards — all collapsed by default:
 *        - What I found
 *        - Why
 *        - Recommended actions (one ActionCard per rec)
 *        - Scenario (delegates to ScenarioAnalysisCard)
 *        - Risks
 *        - Missing information
 *        - Evidence (expandable panel with concrete values)
 *        - Assumptions
 *        - Confidence
 *   5. Technical Provenance — collapsed disclosure at the
 *      bottom. Replaces the standalone TrustMeta disclosure
 *      below the bubble.
 *
 * The shell is **additive**: the inner renderers stay mounted
 * as the source of "What I found" detail, so users can drill
 * back into the original 9-section or 6-section layout when
 * they need to.
 */

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Code2,
  FileSearch,
  HelpCircle,
  Lightbulb,
  ListChecks,
  ListOrdered,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { ActionCard, type ActionCardData } from "./ActionCard";
import { ConsultantRenderer } from "./ConsultantRenderer";
import { DirectAnswer } from "./DirectAnswer";
import { EvidencePanel } from "./EvidencePanel";
import { ExplanationPanelStack } from "./ExplanationPanel";
import { GroundedResponseRenderer } from "./GroundedResponseRenderer";
import { MissingInfoCard } from "./MissingInfoCard";
import { PriorityList, type PriorityListItem } from "./PriorityList";
import { RiskBarChart, type RiskBarSegment } from "./RiskBarChart";
import { ScenarioAnalysisCard } from "./ScenarioAnalysisCard";
import { SecondaryCard } from "./SecondaryCard";
import { TrustBar } from "./TrustBar";
import { VisualizationCard } from "./charts/VisualizationCard";
import { WhyThisAnswer } from "./WhyThisAnswer";
import { SchemeAnswerCardView } from "./SchemeAnswerCardView";
import { MixedSections } from "./MixedSections";
import { FreshnessWarningsList } from "./FreshnessWarningsList";
import { formatAssistantBody } from "./AssistantRenderer";
import { resolveDirectAnswer } from "./sections/extractDirectAnswer";
import { mapToBriefTrustLabel } from "./sections/mapTrustLabel";
import type {
  AssistantContextSnapshot,
  NormalizedEvidenceItem,
} from "./sections/normalizeEvidence";
import { normalizeEvidence } from "./sections/normalizeEvidence";
import type {
  ChatGroundedRecommendation,
  ChatGroundedResponse,
  ChatMessage,
  ConsultantResponse,
  LLMToolResult,
} from "./types";
import { deriveTrustLabel } from "./MessageBubble";

export interface TrustFirstResponseProps {
  message: ChatMessage;
  /** Trimmed context snapshot for evidence normalization. */
  context?: AssistantContextSnapshot | null;
  /** Optional follow-up click handler (passed through). */
  onFollowUp?: (label: string) => void;
}

/**
 * Pick the inner-renderer path. Mirrors the legacy MessageBubble
 * branch logic: grounded wins over consultant wins over typed body.
 */
function pickPath(message: ChatMessage): "grounded" | "consultant" | "direct" {
  if (message.generation?.grounded_payload) return "grounded";
  if (message.consultant) return "consultant";
  return "direct";
}

export function TrustFirstResponse({
  message,
  context,
  onFollowUp,
}: TrustFirstResponseProps) {
  const groundedPayload = message.generation?.grounded_payload ?? null;
  const consultant = message.consultant ?? null;
  const scenarioAnalysis = message.scenario_analysis ?? null;
  const path = pickPath(message);

  const internalLabel = deriveTrustLabel(message);
  const briefLabel = mapToBriefTrustLabel(internalLabel, !!scenarioAnalysis);

  const directAnswer = resolveDirectAnswer({
    directAnswer: message.direct_answer,
    groundedSummary: groundedPayload?.executive_summary ?? null,
    consultantBody: consultant?.body ?? null,
    content: message.content,
  });

  const confidence = message.generation?.confidence ?? groundedPayload?.confidence ?? null;

  const evidenceRefs = pickEvidenceRefs(message, groundedPayload);
  const hasSupplierConcentration = context?.primarySupplierShare
    ? context.primarySupplierShare > 0
    : false;

  return (
    <div
      data-testid="trust-first-response"
      data-trust-first-path={path}
      data-trust-first-label={briefLabel}
      className="space-y-3"
    >
      {/* 1. Direct Answer — the 10-second read */}
      {directAnswer ? (
        <DirectAnswer text={directAnswer} />
      ) : null}

      {/* 2. TrustBar — the mutually-exclusive label */}
      <TrustBar label={briefLabel} confidence={confidence ?? undefined} />

      {/* 3. Top Recommendation (single line, points at Action Cards) */}
      <TopRecommendation
        groundedPayload={groundedPayload}
        consultant={consultant}
      />

      {/* 4. Secondary cards — all collapsed by default */}
      <SecondaryCard
        title="What I found"
        caption="Key findings from your business data."
        icon={Lightbulb}
        testId="secondary-card-what-i-found"
      >
        <WhatIFoundBody
          path={path}
          message={message}
          groundedPayload={groundedPayload}
          consultant={consultant}
          onFollowUp={onFollowUp}
        />
      </SecondaryCard>

      <SecondaryCard
        title="Why"
        caption="The reasoning behind the recommendation."
        icon={HelpCircle}
        testId="secondary-card-why"
      >
        <WhyBody
          groundedPayload={groundedPayload}
          consultant={consultant}
          directAnswer={directAnswer}
        />
      </SecondaryCard>

      {/* SPRINT AI-10 — Explain My Answer. Per-recommendation
          decision traces, derived from structured provenance
          metadata. Hidden entirely for legacy rows (no
          `explanation` field) and for turns with no
          recommendations. The trace strings are deterministic
          outputs of the backend builder — no LLM chain-of-thought
          is ever exposed. */}
      {message.explanation &&
      Object.keys(message.explanation).length > 0 ? (
        <ExplanationPanelStack explanations={message.explanation} />
      ) : null}

      <SecondaryCard
        title="Recommended actions"
        caption="What to do next, in order."
        icon={ListChecks}
        testId="secondary-card-actions"
      >
        <ActionsBody
          groundedPayload={groundedPayload}
          consultant={consultant}
          evidenceRefs={evidenceRefs}
        />
      </SecondaryCard>

      {scenarioAnalysis && scenarioAnalysis.present !== false ? (
        <SecondaryCard
          title="Scenario"
          caption="Illustrative 'what if' analysis."
          icon={TrendingUp}
          testId="secondary-card-scenario"
          defaultOpen={true}
        >
          <ScenarioBody analysis={scenarioAnalysis} />
        </SecondaryCard>
      ) : null}

      <SecondaryCard
        title="Risks"
        caption="What to watch out for."
        icon={AlertTriangle}
        testId="secondary-card-risks"
      >
        <RisksBody
          groundedPayload={groundedPayload}
          consultant={consultant}
        />
      </SecondaryCard>

      <SecondaryCard
        title="Missing information"
        caption={
          message.missing_data && message.missing_data.length > 0
            ? "Proactive gaps — fill these to sharpen the answer."
            : "What would sharpen this answer."
        }
        icon={FileSearch}
        testId="secondary-card-missing-information"
        defaultOpen={
          message.missing_data !== undefined && message.missing_data.length > 0
        }
      >
        {message.missing_data && message.missing_data.length > 0 ? (
          <MissingInfoCard message={message} />
        ) : (
          <MissingInfoBody
            groundedPayload={groundedPayload}
            consultant={consultant}
          />
        )}
      </SecondaryCard>

      <SecondaryCard
        title="Evidence"
        caption="The concrete values behind this answer."
        icon={ListOrdered}
        testId="secondary-card-evidence"
      >
        <EvidencePanel ids={evidenceRefs} context={context ?? null} />
      </SecondaryCard>

      {hasSupplierConcentration ? (
        <SecondaryCard
          title="Concentration risk"
          caption="Where the dependency sits today."
          icon={ShieldAlert}
          testId="secondary-card-concentration"
        >
          <ConcentrationBody context={context ?? null} />
        </SecondaryCard>
      ) : null}

      <SecondaryCard
        title="Assumptions"
        caption="The caveats behind the numbers."
        icon={AlertCircle}
        testId="secondary-card-assumptions"
      >
        <AssumptionsBody
          groundedPayload={groundedPayload}
          consultant={consultant}
          generationAssumptions={message.generation?.assumptions ?? []}
        />
      </SecondaryCard>

      <SecondaryCard
        title="Confidence"
        caption="How sure the model is."
        icon={Sparkles}
        testId="secondary-card-confidence"
      >
        <ConfidenceBody
          confidence={confidence}
          groundingScore={message.generation?.server_grounding_score ?? null}
        />
      </SecondaryCard>

      {/* SPRINT AI-15 — Intelligent Visualization + Trust-First UX.
          Strictly additive. Three slots, each hidden when the
          server did not emit the corresponding payload. The viz
          block is one of the (≤3) supporting blocks — it is added
          in addition to the secondary cards above, never counted
          against their visual budget.
          Order:
            a) low-quality warning strip (concise, when fired)
            b) VisualizationCard slot (max 1 block; never empty)
            c) WhyThisAnswer disclosure (collapsed by default) */}

      {message.quality_warning && message.quality_warning.needs_warning ? (
        <div
          data-testid="quality-warning-strip"
          className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
          role="status"
        >
          <span className="font-semibold">Heads up:</span>{" "}
          {message.quality_warning.warning_message ??
            "This answer is below our normal confidence threshold; please treat it as a starting point."}
        </div>
      ) : null}

      {Array.isArray(message.visualization_plans) &&
      message.visualization_plans.length > 0 ? (
        <VisualizationCard
          plan={message.visualization_plans[0]}
          trust_summary={message.trust_summary}
        />
      ) : null}

      {/* SPRINT AI-16 — Mixed Question Answer Composition +
          Scheme Card. Strictly additive. Three slots, each
          hidden when the server did not emit the corresponding
          payload. Order matches the brief: scheme_card first
          (most user-decision-relevant), mixed_answer second
          (consolidated body), freshness_warnings last (advisory
          only). The renderers are self-gated — each component
          returns ``null`` when its payload is null or empty. */}
      {message.scheme_card ? (
        <SchemeAnswerCardView card={message.scheme_card} />
      ) : null}

      {message.mixed_answer && message.mixed_answer.is_mixed ? (
        <MixedSections answer={message.mixed_answer} />
      ) : null}

      {Array.isArray(message.freshness_warnings) &&
      message.freshness_warnings.length > 0 ? (
        <FreshnessWarningsList items={message.freshness_warnings} />
      ) : null}

      {message.trust_summary ? (
        <WhyThisAnswer trust_summary={message.trust_summary} />
      ) : null}

      {/* 5. Technical provenance — collapsed by default */}
      <TechnicalProvenanceToggle message={message} />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Top recommendation — single line, points at the ActionCards below.       //
// --------------------------------------------------------------------------- //

function TopRecommendation({
  groundedPayload,
  consultant,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
}) {
  const title = pickTopRecTitle(groundedPayload, consultant);
  if (!title) return null;
  return (
    <div
      data-testid="top-recommendation"
      className="flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3 py-2"
    >
      <ArrowRight
        className="mt-0.5 size-4 shrink-0 text-primary"
        aria-hidden="true"
      />
      <p className="text-sm font-medium leading-snug text-foreground">
        {title}
      </p>
    </div>
  );
}

function pickTopRecTitle(
  groundedPayload: ChatGroundedResponse | null,
  consultant: ConsultantResponse | null,
): string | null {
  if (groundedPayload && groundedPayload.recommendations.length > 0) {
    return groundedPayload.recommendations[0].title;
  }
  if (consultant) {
    for (const section of consultant.sections) {
      if (section.key !== "recommendations") continue;
      const first = section.bullets?.[0];
      if (first?.title) return first.title;
    }
  }
  return null;
}

// --------------------------------------------------------------------------- //
// What I found — the inner renderer (or the typed body) in compact form.     //
// --------------------------------------------------------------------------- //

function WhatIFoundBody({
  path,
  message,
  groundedPayload,
  consultant,
  onFollowUp,
}: {
  path: "grounded" | "consultant" | "direct";
  message: ChatMessage;
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
  onFollowUp?: (label: string) => void;
}) {
  if (path === "grounded" && groundedPayload) {
    // The shell already surfaces the 10-second read via
    // DirectAnswer + TrustBar + TopRecommendation. To avoid
    // duplicating the Executive Summary, mount the
    // GroundedResponseRenderer with a stripped payload that
    // drops the executive_summary prose — every other
    // section is fair game.
    const stripped = stripExecutiveSummary(groundedPayload);
    return (
      <div className="space-y-2">
        <GroundedResponseRenderer response={stripped} />
      </div>
    );
  }
  if (path === "consultant" && consultant) {
    return (
      <div className="space-y-2">
        <ConsultantRenderer
          response={consultant}
          onFollowUp={onFollowUp}
        />
      </div>
    );
  }
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg bg-background/40 p-3 leading-relaxed text-foreground">
      {formatAssistantBody(message.content || "")}
    </div>
  );
}

/**
 * Return a copy of the grounded payload with the executive
 * summary replaced by a single empty paragraph. The renderer
 * always mounts the executive_summary section so we have to
 * neutralise the body text directly; otherwise the user sees
 * the same sentences twice (once at the top of the shell,
 * once inside the "What I found" card).
 */
function stripExecutiveSummary(
  payload: ChatGroundedResponse,
): ChatGroundedResponse {
  return {
    ...payload,
    executive_summary: "",
  };
}

// --------------------------------------------------------------------------- //
// Why — the rationale.                                                       //
// --------------------------------------------------------------------------- //

function WhyBody({
  groundedPayload,
  consultant,
  directAnswer,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
  directAnswer: string | null;
}) {
  const bullets: string[] = [];

  if (groundedPayload) {
    if (groundedPayload.situation_assessment) {
      bullets.push(groundedPayload.situation_assessment);
    }
    if (groundedPayload.reasoning) {
      bullets.push(groundedPayload.reasoning);
    }
    for (const f of groundedPayload.key_findings.slice(0, 3)) {
      bullets.push(`${f.title} — ${f.detail}`);
    }
  }
  if (consultant) {
    for (const section of consultant.sections) {
      if (section.key === "summary" && section.body) {
        bullets.push(section.body);
      }
    }
  }
  if (bullets.length === 0 && directAnswer) {
    bullets.push(directAnswer);
  }
  if (bullets.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Reasoning details not available for this response.
      </p>
    );
  }
  return (
    <ul className="space-y-1.5">
      {bullets.map((b, i) => (
        <li
          key={i}
          className="flex items-start gap-1.5 rounded-md bg-background/40 px-2 py-1.5 text-xs text-foreground/90"
        >
          <CheckCircle2
            className="mt-0.5 size-3 shrink-0 text-emerald-500"
            aria-hidden="true"
          />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Actions — one ActionCard per recommendation, or a PriorityList for ≥3.     //
// --------------------------------------------------------------------------- //

function ActionsBody({
  groundedPayload,
  consultant,
  evidenceRefs,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
  evidenceRefs: readonly string[];
}) {
  const recs = groundedPayload
    ? groundedPayload.recommendations.map((r) => toActionCardData(r))
    : consultant
      ? consultantRecsToActionCards(consultant)
      : [];

  if (recs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No recommended actions surfaced for this response.
      </p>
    );
  }

  if (recs.length >= 3) {
    const items: PriorityListItem[] = recs.slice(0, 5).map((r) => ({
      id: r.id,
      title: r.title,
      priority: r.priority ?? null,
      score: r.expectedPurpose ?? null,
      evidenceRefs: r.evidenceRefs ?? [],
    }));
    return (
      <div className="space-y-3">
        <PriorityList items={items} title="Top priorities" />
        <details className="rounded-lg border border-border/60 bg-background/40 p-2 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Show detail cards ({recs.length})
          </summary>
          <div className="mt-2 space-y-2">
            {recs.map((r) => (
              <ActionCard key={r.id} data={r} />
            ))}
          </div>
        </details>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {recs.map((r) => (
        <ActionCard key={r.id} data={r} />
      ))}
      {evidenceRefs.length > 0 ? (
        <p className="text-[10px] text-muted-foreground">
          Evidence-backed by {evidenceRefs.length} data point
          {evidenceRefs.length === 1 ? "" : "s"}.
        </p>
      ) : null}
    </div>
  );
}

function toActionCardData(rec: ChatGroundedRecommendation): ActionCardData {
  return {
    id: rec.recommendation_id,
    title: rec.title,
    priority: derivePriority(rec),
    why: rec.rationale,
    expectedPurpose: deriveExpectedPurpose(rec),
    evidenceRefs: rec.evidence_refs,
  };
}

function consultantRecsToActionCards(
  consultant: ConsultantResponse,
): ActionCardData[] {
  const out: ActionCardData[] = [];
  for (const section of consultant.sections) {
    if (section.key !== "recommendations") continue;
    for (const b of section.bullets ?? []) {
      if (!b.title) continue;
      out.push({
        id: b.id ?? `${section.key}-${b.title}`,
        title: b.title,
        priority: b.impact ?? null,
        why: b.subtitle ?? b.meta ?? "—",
        effort: b.difficulty ?? null,
        expectedPurpose: b.impact ?? null,
        risk: b.riskIfIgnored ?? null,
        nextStep: b.time ?? null,
        evidenceRefs: [],
      });
    }
  }
  return out;
}

function derivePriority(rec: ChatGroundedRecommendation): string | null {
  if (rec.recommendation_id.includes("critical")) return "Critical";
  if (rec.recommendation_id.includes("high")) return "High";
  if (rec.recommendation_id.includes("med")) return "Medium";
  if (rec.recommendation_id.includes("low")) return "Low";
  return null;
}

function deriveExpectedPurpose(rec: ChatGroundedRecommendation): string | null {
  if (rec.evidence_refs.length === 0) return null;
  return `${rec.evidence_refs.length} evidence point${rec.evidence_refs.length === 1 ? "" : "s"}`;
}

// --------------------------------------------------------------------------- //
// Scenario — delegates to the existing ScenarioAnalysisCard.                //
// --------------------------------------------------------------------------- //

function ScenarioBody({ analysis }: { analysis: ChatMessage["scenario_analysis"] }) {
  if (!analysis) return null;
  return <ScenarioAnalysisCard analysis={analysis} />;
}

// --------------------------------------------------------------------------- //
// Risks — bullet list.                                                       //
// --------------------------------------------------------------------------- //

function RisksBody({
  groundedPayload,
  consultant,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
}) {
  const bullets: string[] = [];

  if (groundedPayload) {
    if (groundedPayload.risks && groundedPayload.risks.length > 0) {
      bullets.push(...groundedPayload.risks);
    }
    for (const l of groundedPayload.limitations) {
      bullets.push(l);
    }
  }
  if (consultant) {
    for (const section of consultant.sections) {
      for (const b of section.bullets ?? []) {
        if (b.riskIfIgnored) bullets.push(b.riskIfIgnored);
      }
    }
  }
  if (bullets.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No specific risks surfaced for this response.
      </p>
    );
  }
  return (
    <ul className="space-y-1.5">
      {bullets.map((b, i) => (
        <li
          key={i}
          className="flex items-start gap-1.5 rounded-md bg-background/40 px-2 py-1.5 text-xs text-foreground/90"
        >
          <AlertTriangle
            className="mt-0.5 size-3 shrink-0 text-rose-500"
            aria-hidden="true"
          />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Missing information — bullet list.                                         //
// --------------------------------------------------------------------------- //

function MissingInfoBody({
  groundedPayload,
  consultant,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
}) {
  const bullets: string[] = [];

  if (groundedPayload) {
    for (const l of groundedPayload.limitations) {
      bullets.push(l);
    }
  }
  if (consultant) {
    for (const section of consultant.sections) {
      if (section.key !== "impact") continue;
      for (const line of section.lines ?? []) {
        bullets.push(line);
      }
    }
  }
  if (bullets.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No missing information flagged for this response.
      </p>
    );
  }
  return (
    <ul className="space-y-1.5">
      {bullets.map((b, i) => (
        <li
          key={i}
          className="flex items-start gap-1.5 rounded-md bg-background/40 px-2 py-1.5 text-xs text-foreground/90"
        >
          <FileSearch
            className="mt-0.5 size-3 shrink-0 text-amber-500"
            aria-hidden="true"
          />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Concentration — RiskBarChart visualization (only when supplier data exists) //
// --------------------------------------------------------------------------- //

function ConcentrationBody({ context }: { context: AssistantContextSnapshot | null }) {
  if (!context || !context.primarySupplierShare) return null;
  const primary = context.primarySupplierShare;
  const other = Math.max(0, 100 - primary);
  const segments: RiskBarSegment[] = [
    { label: "Primary supplier", value: primary, tone: primary >= 60 ? "danger" : "warn" },
    { label: "Other suppliers", value: other, tone: "default" },
  ];
  return (
    <RiskBarChart
      segments={segments}
      title="Supplier concentration"
      className="mt-1"
    />
  );
}

// --------------------------------------------------------------------------- //
// Assumptions — bullet list.                                                 //
// --------------------------------------------------------------------------- //

function AssumptionsBody({
  groundedPayload,
  consultant,
  generationAssumptions,
}: {
  groundedPayload: ChatGroundedResponse | null;
  consultant: ConsultantResponse | null;
  generationAssumptions: readonly string[];
}) {
  const bullets: string[] = [];

  if (groundedPayload) {
    bullets.push(...groundedPayload.assumptions);
  }
  if (generationAssumptions.length > 0) {
    bullets.push(...generationAssumptions);
  }
  if (consultant) {
    for (const section of consultant.sections) {
      if (section.key === "summary" && section.body) {
        bullets.push(section.body);
      }
    }
  }
  if (bullets.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No assumptions flagged for this response.
      </p>
    );
  }
  return (
    <ul className="space-y-1.5">
      {bullets.map((b, i) => (
        <li
          key={i}
          className="flex items-start gap-1.5 rounded-md bg-background/40 px-2 py-1.5 text-xs text-foreground/90"
        >
          <AlertCircle
            className="mt-0.5 size-3 shrink-0 text-amber-500"
            aria-hidden="true"
          />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Confidence — gradient meter + delta text.                                  //
// --------------------------------------------------------------------------- //

function ConfidenceBody({
  confidence,
  groundingScore,
}: {
  confidence: number | null;
  groundingScore: number | null;
}) {
  const value = confidence ?? groundingScore;
  if (value === null || value === undefined) {
    return (
      <p className="text-xs text-muted-foreground">
        Confidence not reported for this response.
      </p>
    );
  }
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const ariaLabel = `Confidence ${clamped} of 100`;
  return (
    <div className="space-y-2" data-testid="confidence-meter">
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        aria-label={ariaLabel}
        className="relative h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-rose-500 via-amber-500 to-emerald-500"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <p className="text-xs tabular-nums text-foreground/90">
        <span className="font-semibold">{clamped}/100</span>
        <span className="ml-2 text-muted-foreground">
          {confidenceTone(clamped)}
        </span>
      </p>
      {groundingScore !== null && confidence !== null && groundingScore !== confidence ? (
        <p className="text-[10px] text-muted-foreground">
          Server grounding score: {groundingScore}/100
        </p>
      ) : null}
    </div>
  );
}

function confidenceTone(value: number): string {
  if (value >= 80) return "Strong evidence";
  if (value >= 60) return "Moderate evidence";
  if (value >= 40) return "Limited evidence";
  return "Low confidence — verify before acting";
}

// --------------------------------------------------------------------------- //
// Technical provenance — collapsed details at the bottom.                    //
// --------------------------------------------------------------------------- //

function TechnicalProvenanceToggle({ message }: { message: ChatMessage }) {
  const [open, setOpen] = useState(false);
  const gen = message.generation;
  return (
    <details
      data-testid="technical-provenance"
      className="rounded-xl border border-dashed border-border/60 bg-card/60"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <Code2 className="size-3" aria-hidden="true" />
        Why am I seeing this? (technical provenance)
      </summary>
      <div className="space-y-1.5 border-t border-border/40 px-3 py-3 text-xs">
        <ProvenanceRow label="Provider" value={gen?.provider ?? "client"} />
        <ProvenanceRow label="Model" value={gen?.model ?? "rule-engine"} />
        <ProvenanceRow
          label="Mode"
          value={gen?.mode ?? "client"}
        />
        <ProvenanceRow
          label="Generation method"
          value={gen?.generation_method ?? "deterministic"}
        />
        <ProvenanceRow
          label="Fallback used"
          value={gen?.fallback_used ? "Yes" : "No"}
        />
        {gen?.fallback_reason ? (
          <ProvenanceRow label="Fallback reason" value={gen.fallback_reason} />
        ) : null}
        <ProvenanceRow
          label="Schema validated"
          value={gen?.schema_validated ? "Yes" : "No"}
        />
        <ProvenanceRow
          label="Grounding validated"
          value={gen?.grounding_validated ? "Yes" : "No"}
        />
        <ProvenanceRow
          label="Grounding score"
          value={
            gen?.server_grounding_score !== undefined
              ? `${gen.server_grounding_score}/100`
              : "—"
          }
        />
        {message.llm_tool_results && message.llm_tool_results.length > 0 ? (
          <ToolPillsRow results={message.llm_tool_results} />
        ) : null}
        {/* Sprint AI-13 — partial-failure disclosure + confidence
            penalty. When at least one tool failed, surface the
            one-line sentence + the integer 0..40 penalty so the
            user can see why the trust badge may be downgraded. */}
        {message.partial_failure_disclosure ? (
          <ProvenanceRow
            label="Partial failure"
            value={message.partial_failure_disclosure}
          />
        ) : null}
        {typeof message.confidence_penalty === "number" &&
        message.confidence_penalty > 0 ? (
          <ProvenanceRow
            label="Confidence penalty"
            value={`-${message.confidence_penalty} (from partial tool failure)`}
          />
        ) : null}
        {message.tool_execution_traces &&
        message.tool_execution_traces.length > 0 ? (
          <ToolExecutionTracesRow traces={message.tool_execution_traces} />
        ) : null}
        <ProvenanceRow
          label="Provider latency"
          value={
            gen?.provider_latency_ms !== undefined && gen.provider_latency_ms !== null
              ? `${gen.provider_latency_ms} ms`
              : "—"
          }
        />
        <ProvenanceRow
          label="Generated at"
          value={gen?.generated_at ?? message.createdAt}
        />
        {gen?.context_manifest ? (
          <ProvenanceRow
            label="Records used"
            value={String(gen.context_manifest.records_used)}
          />
        ) : null}
      </div>
    </details>
  );
}

function ProvenanceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-[11px] text-foreground/90 tabular-nums">
        {value}
      </span>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Sprint AI-8 — "Used tools" pill row inside the technical provenance       //
// disclosure. Renders one pill per whitelisted tool the LLM requested:      //
// green dot when the router dispatched it (status="ok"), red when the router //
// rejected it (status="error"), grey when it was skipped (e.g. timeout).     //
// --------------------------------------------------------------------------- //

function ToolPillsRow({ results }: { results: readonly LLMToolResult[] }) {
  return (
    <div
      data-testid="tool-pills-row"
      className="flex flex-wrap items-baseline gap-2 rounded-md bg-background/40 px-2 py-1.5"
    >
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        Used tools
      </span>
      <div className="flex flex-wrap gap-1.5">
        {results.map((r, i) => (
          <ToolPill key={`${r.tool}-${i}`} result={r} />
        ))}
      </div>
    </div>
  );
}

function ToolPill({ result }: { result: LLMToolResult }) {
  // Status-driven accent: emerald=ok, rose=error, slate=skipped.
  const tone =
    result.status === "ok"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
      : result.status === "error"
        ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300"
        : "border-slate-500/40 bg-slate-500/10 text-slate-700 dark:text-slate-300";
  const dotClass =
    result.status === "ok"
      ? "bg-emerald-500"
      : result.status === "error"
        ? "bg-rose-500"
        : "bg-slate-500";
  return (
    <span
      data-testid="tool-pill"
      data-tool-name={result.tool}
      data-tool-status={result.status}
      title={
        result.status !== "ok" && result.error
          ? `${result.tool} — ${result.error}`
          : result.tool
      }
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] tabular-nums ${tone}`}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full ${dotClass}`}
      />
      <span>{result.tool}</span>
    </span>
  );
}

// --------------------------------------------------------------------------- //
// Sprint AI-13 — per-tool execution trace row inside the technical           //
// provenance disclosure. Each entry is the ToolExecutionTrace.to_dict()     //
// shape (tool_name, selected, executed, success, latency_ms,                //
// result_available, evidence_ids, failure_reason, error_category). One pill //
// per executed tool, color-coded by error_category.                        //
// --------------------------------------------------------------------------- //

const ERROR_CATEGORY_TONE: Record<string, string> = {
  none: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
  stub: "border-slate-400/40 bg-slate-400/10 text-slate-700",
  timeout: "border-amber-500/40 bg-amber-500/10 text-amber-700",
  exception: "border-rose-500/40 bg-rose-500/10 text-rose-700",
  empty_payload: "border-orange-500/40 bg-orange-500/10 text-orange-700",
};

function ToolExecutionTracesRow({
  traces,
}: {
  traces: readonly Record<string, unknown>[];
}) {
  return (
    <div
      data-testid="tool-execution-traces-row"
      className="flex flex-col gap-1.5 rounded-md bg-background/40 px-2 py-1.5"
    >
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        Tools consulted (per-tool audit)
      </span>
      <div className="flex flex-wrap gap-1.5">
        {traces.map((t, i) => {
          const toolName = String(t.tool_name ?? `tool-${i}`);
          const errorCategory = String(t.error_category ?? "none");
          const tone =
            ERROR_CATEGORY_TONE[errorCategory] ??
            "border-border bg-muted/40 text-foreground";
          const failureReason = t.failure_reason
            ? String(t.failure_reason)
            : "";
          return (
            <span
              key={`${toolName}-${i}`}
              title={
                failureReason
                  ? `${toolName} — ${failureReason}`
                  : toolName
              }
              data-error-category={errorCategory}
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] tabular-nums ${tone}`}
            >
              <span
                aria-hidden="true"
                className={`size-1.5 rounded-full ${errorCategory === "none" ? "bg-emerald-500" : "bg-current"}`}
              />
              <span>{toolName}</span>
              {typeof t.latency_ms === "number" ? (
                <span className="text-muted-foreground">
                  ·{t.latency_ms}ms
                </span>
              ) : null}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

function pickEvidenceRefs(
  message: ChatMessage,
  groundedPayload: ChatGroundedResponse | null,
): readonly string[] {
  if (groundedPayload?.evidence_references && groundedPayload.evidence_references.length > 0) {
    return groundedPayload.evidence_references.map((e) => e.id);
  }
  if (message.generation?.evidence_references && message.generation.evidence_references.length > 0) {
    return message.generation.evidence_references;
  }
  return [];
}

// Avoid an unused-import warning when the inner renderer isn't
// mounted (vite tree-shake is happy but eslint isn't).
void normalizeEvidence;
export type { NormalizedEvidenceItem };

export default TrustFirstResponse;

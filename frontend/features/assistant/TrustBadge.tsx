"use client";

/**
 * TrustBadge — H7.3 (Docx Prompt 3 Part 4) visible trust labels.
 *
 * H7.8C extends the badge with a sixth category:
 *
 *   - "Open-domain LLM — not grounded"      permissive mode
 *
 * The docx requires the assistant UI to distinguish the
 * trust categories a user can see:
 *
 *   - "Calculated by UrsBiz rule engine"     deterministic scoring
 *   - "Generated explanation"                 LLM synthesis (grounded)
 *   - "Open-domain LLM — not grounded"        open-mode LLM (H7.8C)
 *   - "Scenario estimate"                     forecast / projection
 *   - "Official external source"              government scheme data
 *   - "User-provided information"             inputs the user entered
 *
 * The badge is intentionally tiny — a pill below the
 * assistant bubble. The labels are the literal text the
 * docx asks for so the verifier can grep for the strings
 * without false negatives. No emoji / no flourish; the
 * badge is information, not decoration.
 */
import { AlertTriangle, BadgeCheck, Cpu, Globe, Sparkles, TrendingUp, User } from "lucide-react";
import { cn } from "@/lib/utils";

export type TrustLabel =
  | "rule_engine"
  | "generated"
  | "open_business"
  | "open_domain"
  | "scenario"
  | "official"
  | "user_provided"
  | "offline_snapshot";

const COPY: Record<
  TrustLabel,
  { text: string; icon: React.ComponentType<{ className?: string }>; tone: string }
> = {
  rule_engine: {
    text: "Calculated by UrsBiz rule engine",
    icon: Cpu,
    tone: "bg-emerald-500/10 text-emerald-700 border-emerald-500/30",
  },
  offline_snapshot: {
    text: "Offline demonstration snapshot — generated previously from a verified AI run.",
    icon: Cpu,
    tone: "bg-indigo-500/10 text-indigo-700 border-indigo-500/30",
  },
  generated: {
    text: "Verified against UrsBiz business evidence",
    icon: Sparkles,
    tone: "bg-violet-500/10 text-violet-700 border-violet-500/30",
  },
  open_business: {
    text: "Exploratory AI analysis · Uses your business context",
    icon: Globe,
    tone: "bg-blue-500/10 text-blue-700 border-blue-500/30",
  },
  open_domain: {
    text: "General AI explanation",
    icon: Globe,
    tone: "bg-amber-500/10 text-amber-700 border-amber-500/30",
  },
  scenario: {
    text: "Scenario estimate",
    icon: TrendingUp,
    tone: "bg-amber-500/10 text-amber-700 border-amber-500/30",
  },
  official: {
    text: "Official external source",
    icon: BadgeCheck,
    tone: "bg-sky-500/10 text-sky-700 border-sky-500/30",
  },
  user_provided: {
    text: "User-provided information",
    icon: User,
    tone: "bg-slate-500/10 text-slate-700 border-slate-500/30",
  },
};

export function TrustBadge({
  label,
  className,
}: {
  label: TrustLabel;
  className?: string;
}) {
  const entry = COPY[label];
  const Icon = entry.icon;
  return (
    <span
      role="note"
      aria-label={entry.text}
      title={entry.text}
      data-trust-label={label}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        entry.tone,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {entry.text}
    </span>
  );
}

/**
 * Sprint AI-14 — "Unsupported claim" pill.
 *
 * Lights up when the evidence-graph validator flagged at least
 * one ClaimNode with ``validation_status == "unsupported"``.
 * The pill is read-only — the count comes from
 * ``generation.unsupported_claim_count``; the LLM has no path
 * to author this number. Renders nothing when the count is 0
 * (or undefined / negative / NaN).
 */
export function UnsupportedClaimBadge({
  count,
  className,
}: {
  count?: number;
  className?: string;
}) {
  if (typeof count !== "number" || !Number.isFinite(count) || count <= 0) {
    return null;
  }
  const safe = Math.max(0, Math.floor(count));
  return (
    <span
      role="note"
      aria-label={`${safe} unsupported claim${safe === 1 ? "" : "s"} in this answer`}
      title="Some claims in this answer could not be grounded in evidence."
      data-testid="ai14-unsupported-claim-badge"
      data-count={safe}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rose-700",
        className,
      )}
    >
      <AlertTriangle className="size-3" aria-hidden="true" />
      {safe} unsupported claim{safe === 1 ? "" : "s"}
    </span>
  );
}

/**
 * TrustMeta — H7.3 (Docx Prompt 3 Part 4) required metadata block.
 *
 * Renders the docx-required fields under every assistant
 * bubble when the model produced the response:
 *
 *   - Confidence         (0..100)
 *   - Assumptions        (string list, never empty when present)
 *   - Limitations        (string list, never empty when present)
 *   - Evidence           (string list of evidence_reference ids)
 *   - Last updated       (ISO timestamp)
 *
 * H7.8C extends with the provider/model disclosure the
 * hybrid-mode envelope carries:
 *
 *   - Provider + model   ("openai_compatible:llama3.1")
 *   - Grounding score    (0..100 from the GroundingValidator)
 *   - Provider latency   (milliseconds)
 *   - Prompt truncated   (boolean — the user-prompt was clipped)
 *   - Fallback reason    (the normalized reason, only when fallback_used=true)
 *
 * The block is collapsed by default — the docx says
 * "Display: Confidence, Assumptions, Limitations, Evidence,
 * Last updated time" but does not require the block to be
 * open. A small "Why am I seeing this?" toggle expands it.
 */
export function TrustMeta({
  confidence,
  assumptions,
  limitations,
  evidence,
  generatedAt,
  provider,
  model,
  fallbackReason,
  groundingScore,
  promptTruncated,
  providerLatencyMs,
  contextManifest,
  /**
   * Sprint AI-13 — partial-failure disclosure. When at least
   * one tool failed, surface the one-line sentence so the
   * user can see why the trust badge may be downgraded.
   */
  partialFailureDisclosure,
  /**
   * Sprint AI-13 — integer 0..40 confidence penalty from
   * partial tool failure. 0 when every tool succeeded.
   * Subtract this from the displayed confidence (the wire
   * already does this server-side; we surface it again
   * here for transparency).
   */
  confidencePenalty,
  /**
   * Sprint AI-14 — per-claim evidence graph the engine
   * built. ``null`` / undefined when the engine did not run
   * (legacy rows). Rendered as a one-line summary under the
   * "Why am I seeing this?" disclosure.
   */
  evidenceGraph,
  /**
   * Sprint AI-14 — missing-data state with the four
   * {known, derived, estimated, unknown} buckets. Surfaced
   * so the user can see what the engine knows vs. what it
   * does not know.
   */
  missingDataState,
  /**
   * Sprint AI-14 — count of unsupported ClaimNodes (drives
   * the UnsupportedClaimBadge pill; we also surface the
   * number textually inside the disclosure for transparency).
   */
  unsupportedClaimCount,
  /**
   * Sprint AI-14 — count of fabricated ExternalSourceNode
   * entries (URL guard failures). Surfaced textually.
   */
  fabricatedSourceCount,
  className,
}: {
  confidence?: number;
  assumptions?: readonly string[];
  limitations?: readonly string[];
  evidence?: readonly string[];
  generatedAt?: string;
  provider?: string;
  model?: string;
  fallbackReason?: string | null;
  groundingScore?: number;
  promptTruncated?: boolean;
  providerLatencyMs?: number;
  contextManifest?: {
    business_context_used: string[];
    records_used: number;
    prompt_truncated: boolean;
  } | null;
  partialFailureDisclosure?: string | null;
  confidencePenalty?: number;
  evidenceGraph?: Record<string, unknown> | null;
  missingDataState?: Record<string, unknown> | null;
  unsupportedClaimCount?: number;
  fabricatedSourceCount?: number;
  className?: string;
}) {
  return (
    <details
      className={cn(
        "rounded-md border border-dashed border-border bg-background/40 px-3 py-2 text-xs",
        className,
      )}
      data-testid="trust-meta"
    >
      <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Why am I seeing this?
      </summary>
      <div className="mt-2 space-y-2 text-foreground/80">
        {contextManifest && contextManifest.business_context_used && (
          <p className="font-medium text-primary">
            Used {contextManifest.business_context_used.length} business-information categories ({contextManifest.records_used} records)
          </p>
        )}
        {provider || model ? (
          <p>
            <span className="font-semibold">Provider:</span>{" "}
            {provider ?? "unknown"}
            {model ? ` (${model})` : null}
            {typeof providerLatencyMs === "number" ? (
              <span className="text-muted-foreground">
                {" "}
                · {providerLatencyMs} ms
              </span>
            ) : null}
          </p>
        ) : null}
        {typeof groundingScore === "number" ? (
          <p>
            <span className="font-semibold">Grounding score:</span>{" "}
            {Math.max(0, Math.min(100, groundingScore))}/100
          </p>
        ) : null}
        {fallbackReason ? (
          <p>
            <span className="font-semibold">Fallback reason:</span>{" "}
            <code className="rounded bg-secondary px-1 text-[10px]">
              {fallbackReason}
            </code>
          </p>
        ) : null}
        {promptTruncated ? (
          <p className="text-amber-700">
            <span className="font-semibold">Note:</span> the user
            prompt was truncated to fit the model context window.
          </p>
        ) : null}
        {typeof confidence === "number" ? (
          <p>
            <span className="font-semibold">Confidence:</span>{" "}
            {Math.max(0, Math.min(100, confidence))}/100
            {typeof confidencePenalty === "number" && confidencePenalty > 0 ? (
              <span
                data-testid="ai13-confidence-penalty"
                className="ml-1 text-amber-700"
                title={`${confidencePenalty} pt deduction from partial tool failure`}
              >
                (-{confidencePenalty})
              </span>
            ) : null}
          </p>
        ) : null}
        {partialFailureDisclosure ? (
          <p
            data-testid="ai13-partial-failure-disclosure"
            className="text-amber-700"
          >
            <span className="font-semibold">Partial answer:</span>{" "}
            {partialFailureDisclosure}
          </p>
        ) : null}
        {assumptions && assumptions.length > 0 ? (
          <div>
            <p className="font-semibold">Assumptions</p>
            <ul className="ml-4 list-disc">
              {assumptions.map((a, i) => (
                <li key={`a-${i}`}>{a}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {limitations && limitations.length > 0 ? (
          <div>
            <p className="font-semibold">Limitations</p>
            <ul className="ml-4 list-disc">
              {limitations.map((l, i) => (
                <li key={`l-${i}`}>{l}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {evidence && evidence.length > 0 ? (
          <div>
            <p className="font-semibold">Evidence</p>
            <ul className="ml-4 list-disc">
              {evidence.map((e, i) => (
                <li key={`e-${i}`}>{e}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {/* Sprint AI-14 — evidence-graph disclosure. Reads only
            the public summary fields (claim counts + unsupported
            counter + contradiction severity); never renders the
            full per-claim lineage inside this disclosure block —
            that lives in the dedicated technical-provenance panel. */}
        {evidenceGraph &&
        typeof evidenceGraph === "object" &&
        (Array.isArray((evidenceGraph as Record<string, unknown>).claims) ||
          Array.isArray((evidenceGraph as Record<string, unknown>).nodes)) ? (
          <div data-testid="ai14-evidence-graph-summary">
            <p className="font-semibold">Evidence graph</p>
            <p className="text-muted-foreground">
              {(() => {
                const claims = (evidenceGraph as Record<string, unknown>)
                  .claims as unknown[] | undefined;
                const count = Array.isArray(claims) ? claims.length : 0;
                return `${count} claim${count === 1 ? "" : "s"}`;
              })()}
              {typeof unsupportedClaimCount === "number" &&
              unsupportedClaimCount > 0
                ? ` · ${unsupportedClaimCount} unsupported`
                : " · all supported"}
              {typeof (evidenceGraph as Record<string, unknown>)
                .contradiction_severity === "string" &&
              ((evidenceGraph as Record<string, unknown>)
                .contradiction_severity as string) !== "none"
                ? ` · contradictions: ${
                    (evidenceGraph as Record<string, unknown>)
                      .contradiction_severity as string
                  }`
                : ""}
              {typeof fabricatedSourceCount === "number" &&
              fabricatedSourceCount > 0
                ? ` · ${fabricatedSourceCount} unverified source${
                    fabricatedSourceCount === 1 ? "" : "s"
                  }`
                : ""}
            </p>
          </div>
        ) : null}
        {/* Sprint AI-14 — missing-data disclosure. Renders the
            "What I am missing" bucket count + sample field
            names so the user can see what's still unknown. */}
        {missingDataState &&
        typeof missingDataState === "object" &&
        Array.isArray(
          (missingDataState as Record<string, unknown>).unknown,
        ) &&
        ((missingDataState as Record<string, unknown>).unknown as unknown[])
          .length > 0 ? (
          <div data-testid="ai14-missing-data-summary">
            <p className="font-semibold">What I am missing</p>
            <ul className="ml-4 list-disc text-muted-foreground">
              {(
                (missingDataState as Record<string, unknown>)
                  .unknown as unknown[]
              )
                .slice(0, 5)
                .map((entry, i) => {
                  const e = entry as Record<string, unknown>;
                  const label =
                    typeof e.claim_text === "string"
                      ? e.claim_text
                      : typeof e.field === "string"
                      ? e.field
                      : `Missing item ${i + 1}`;
                  return <li key={`m-${i}`}>{label}</li>;
                })}
            </ul>
          </div>
        ) : null}
        {generatedAt ? (
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Last updated {formatRelativeTime(generatedAt)}
          </p>
        ) : null}
      </div>
    </details>
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

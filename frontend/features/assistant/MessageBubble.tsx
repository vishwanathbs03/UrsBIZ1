"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Bot,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageModel } from "./types";
import { TrustFirstResponse } from "./TrustFirstResponse";
import { formatAssistantBody } from "./AssistantRenderer";
import type { TrustLabel } from "./TrustBadge";
import type { AssistantContext } from "./types";

interface MessageBubbleProps {
  message: ChatMessageModel;
  /** Topics the consultant has already answered in this session. */
  memoryTopics?: string[];
  /** Called when the user clicks a smart follow-up chip. */
  onFollowUp?: (label: string) => void;
  /**
   * Optional AssistantContext snapshot — used by the AI-6
   * TrustFirstResponse shell to surface concrete evidence
   * values ("Revenue ₹1.80 Cr", "Health score 68/100",
   * "Supplier concentration 75%") instead of raw evidence
   * IDs. The shell tolerates absence by falling back to
   * generic labels.
   */
  context?: AssistantContext | null;
}

/**
 * Premium chat bubble:
 *  - Sprint H4: when the assistant message carries a structured
 *    `consultant` payload, render the McKinsey-grade 6-section layout
 *    via ConsultantRenderer. Otherwise fall back to the legacy
 *    typewriter body.
 *  - Lightweight typewriter cursor (only on the most recent assistant
 *    message).
 *  - Source list (collapsible).
 *  - Action buttons (copy, thumbs up/down).
 *  - Follow-up suggested question chips.
 *
 * No external dependency (no react-markdown): the renderer is a pure
 * function we control, so the bundle stays tiny.
 */
export function MessageBubble({
  message,
  memoryTopics: _memoryTopics,
  onFollowUp,
  context,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  // The legacy 3-state derivation is still exported because
  // downstream tests + the TrustFirstResponse shell consume it.
  // The path-selection itself now lives in the shell.

  const handleCopy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      const groundedPayload = message.generation?.grounded_payload ?? null;
      let text = message.content;
      if (groundedPayload) {
        // H7.8C — the GroundedResponseRenderer renders nine
        // sections. The clipboard copy should match what the
        // user sees: executive summary + each section's
        // textual content. A future iteration can produce a
        // markdown variant.
        const parts: string[] = [groundedPayload.executive_summary];
        for (const f of groundedPayload.key_findings) {
          parts.push(`- ${f.title}${f.detail ? ` — ${f.detail}` : ""}`);
        }
        for (const r of groundedPayload.recommendations) {
          parts.push(`- ${r.title} (${r.recommendation_id})`);
        }
        for (const p of groundedPayload.thirty_day_plan) {
          parts.push(`- Week ${p.week}: ${p.task}`);
        }
        for (const s of groundedPayload.scheme_matches) {
          parts.push(`- Scheme profile match: ${s.match_explanation}`);
        }
        for (const a of groundedPayload.assumptions) {
          parts.push(`Assumption: ${a}`);
        }
        for (const l of groundedPayload.limitations) {
          parts.push(`Limitation: ${l}`);
        }
        text = parts.join("\n");
      } else if (message.consultant) {
        text = message.consultant.sections
          .map((s) => `${s.title}\n${s.body ?? ""}`)
          .join("\n\n");
      }
      void navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <article
      aria-label={isUser ? "Your message" : "Assistant message"}
      className={cn(
        "flex w-full gap-3 exec-rise",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full border",
          isUser
            ? "border-border bg-secondary text-secondary-foreground"
            : "border-primary/30 bg-primary/10 text-primary",
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div
        className={cn(
          "flex max-w-[90%] flex-col gap-2",
          isUser ? "items-end" : "items-start",
        )}
      >
        {/* Sprint AI-6 — Trust-first visual UI.
            Every assistant message renders through the
            TrustFirstResponse shell:
              1. Direct Answer (1-3 sentences)
              2. TrustBar (5 mutually-exclusive labels)
              3. Top Recommendation
              4. Secondary cards (all collapsed by default)
              5. Technical provenance (collapsed)
            For user messages, the legacy bubble still
            renders. The standalone TrustBadge / TrustMeta
            pair below the bubble is removed — the shell
            embeds them now. The GroundedResponseRenderer
            and ConsultantRenderer are kept mounted inside
            the "What I found" card so the original 9-section
            / 6-section detail is preserved. */}
        {!isUser ? (
          <div
            data-testid="assistant-message-bubble"
            className={cn(
              "relative group w-full rounded-2xl border border-border bg-card text-card-foreground shadow-soft transition-shadow",
              "hover:shadow-md",
            )}
          >
            <div className="space-y-3 p-3 sm:p-4">
              <TrustFirstResponse
                message={message}
                context={
                  context
                    ? {
                        score: context.score,
                        recommendations: context.recommendations,
                        dnaArchetype: context.dna.archetype,
                        dnaMatch: context.dna.match,
                      }
                    : null
                }
                onFollowUp={onFollowUp}
              />
            </div>
            <ActionToolbar
              copied={copied}
              onCopy={handleCopy}
              vote={vote}
              onVote={setVote}
            />
          </div>
        ) : (
          <div
            className={cn(
              "relative group rounded-2xl px-4 py-3 leading-relaxed shadow-soft transition-shadow",
              isUser
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card text-card-foreground hover:shadow-md",
            )}
          >
            {isUser ? (
              <p className="whitespace-pre-line text-sm">{message.content}</p>
            ) : (
              <TypedBody text={message.content} />
            )}
          </div>
        )}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}
        {!isUser && (
          <FollowUpChips message={message} />
        )}
        <time
          dateTime={message.createdAt}
          className="px-1 text-[10px] uppercase tracking-wider text-muted-foreground"
        >
          {formatTime(message.createdAt)}
        </time>
      </div>
    </article>
  );
}

// --------------------------------------------------------------------------- //
// Action toolbar — copy / thumbs up/down                                     //
// --------------------------------------------------------------------------- //

function ActionToolbar({
  copied,
  onCopy,
  vote,
  onVote,
}: {
  copied: boolean;
  onCopy: () => void;
  vote: "up" | "down" | null;
  onVote: (v: "up" | "down" | null) => void;
}) {
  return (
    <div className="absolute -bottom-3 right-3 flex items-center gap-1 rounded-full border border-border bg-card px-1 py-0.5 opacity-0 shadow-soft transition-opacity group-hover:opacity-100">
      <button
        type="button"
        onClick={onCopy}
        className="rounded-full px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
        title={copied ? "Copied" : "Copy message"}
      >
        {copied ? "Copied!" : "Copy"}
      </button>
      <span className="text-border">·</span>
      <button
        type="button"
        onClick={() => onVote(vote === "up" ? null : "up")}
        aria-pressed={vote === "up"}
        className={cn(
          "rounded-full p-1 transition-colors",
          vote === "up"
            ? "bg-emerald-500/15 text-emerald-600"
            : "text-muted-foreground hover:bg-secondary/60",
        )}
        title="Helpful"
      >
        <ThumbsUp className="size-3" />
      </button>
      <button
        type="button"
        onClick={() => onVote(vote === "down" ? null : "down")}
        aria-pressed={vote === "down"}
        className={cn(
          "rounded-full p-1 transition-colors",
          vote === "down"
            ? "bg-rose-500/15 text-rose-600"
            : "text-muted-foreground hover:bg-secondary/60",
        )}
        title="Not helpful"
      >
        <ThumbsDown className="size-3" />
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Follow-up suggestions — pure derivations from intent                       //
// --------------------------------------------------------------------------- //

function FollowUpChips({ message }: { message: ChatMessageModel }) {
  const followUps = useMemo(() => deriveFollowUps(message), [message]);
  // Hooks must run unconditionally. We always allocate the
  // busy state even when there are no follow-ups so we
  // never violate the rules-of-hooks invariant.
  const [busy, setBusy] = useState<string | null>(null);
  if (followUps.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 px-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Follow up
      </span>
      {followUps.map((q) => (
        <button
          key={q.id}
          type="button"
          onClick={() => setBusy(q.id)}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-[11px] font-medium text-primary transition-all hover:-translate-y-0.5 hover:bg-primary/10",
            busy === q.id && "ring-2 ring-primary/30",
          )}
        >
          <span>{q.text}</span>
          <ArrowRight className="size-3" aria-hidden="true" />
        </button>
      ))}
      {busy && (
        <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
          <Sparkles className="size-3" aria-hidden="true" /> Hint: copy the
          question above into the prompt to continue.
        </span>
      )}
    </div>
  );
}

interface Suggestion {
  id: string;
  text: string;
}

function deriveFollowUps(message: ChatMessageModel): Suggestion[] {
  const kind = message.kind;
  // Pure mapping — same intent always yields same follow-ups.
  switch (kind) {
    case "improve_business":
      return [
        { id: "follow-budget", text: "What can I do with a small budget?" },
        { id: "follow-low-risk", text: "What is the lowest-risk next step?" },
        { id: "follow-deadline", text: "Which action takes the shortest time?" },
      ];
    case "low_score":
      return [
        { id: "follow-quick-win", text: "Show me a quick win." },
        { id: "follow-rule", text: "Why is my score low?" },
        { id: "follow-roadmap", text: "Walk me through the roadmap." },
      ];
    case "what_first":
      return [
        { id: "follow-first-step", text: "What is the very first thing to do?" },
        { id: "follow-cost", text: "How much will it cost?" },
        { id: "follow-team", text: "Do I need to hire someone?" },
      ];
    case "export_opportunities":
      return [
        { id: "follow-iec", text: "How do I get an IEC number?" },
        { id: "follow-markets", text: "Which markets are best for my product?" },
        { id: "follow-compliance", text: "What export compliance is required?" },
      ];
    case "business_dna":
      return [
        { id: "follow-improve-dna", text: "How do I strengthen my DNA match?" },
        { id: "follow-archetype", text: "What does my archetype value most?" },
        { id: "follow-industry", text: "How do my peers score?" },
      ];
    case "explain_roadmap":
      return [
        { id: "follow-first-phase", text: "Which phase should I do first?" },
        { id: "follow-dependencies", text: "What blocks the next milestone?" },
        { id: "follow-duration", text: "How long does the whole roadmap take?" },
      ];
    case "explain_recommendations":
      return [
        { id: "follow-critical", text: "Which is the most critical?" },
        { id: "follow-cheap", text: "Which is cheapest?" },
        { id: "follow-fast", text: "Which finishes fastest?" },
      ];
    case "explain_insights":
      return [
        { id: "follow-patterns", text: "Any patterns in my business?" },
        { id: "follow-low-coverage", text: "Where is my analysis weakest?" },
        { id: "follow-summary", text: "Give me a one-line summary." },
      ];
    case "explain_rules":
      return [
        { id: "follow-critical-rules", text: "Show me critical rules." },
        { id: "follow-resolved", text: "What rules have I resolved?" },
        { id: "follow-impact", text: "Which rule has the biggest impact?" },
      ];
    case "general_overview":
      return [
        { id: "follow-health", text: "How healthy is my business?" },
        { id: "follow-dna", text: "Explain my Business DNA." },
        { id: "follow-recs", text: "Show top recommendations." },
      ];
    default:
      return [
        { id: "follow-summary", text: "Summarise my business in one line." },
        { id: "follow-improve", text: "Help me improve my business." },
      ];
  }
}

// --------------------------------------------------------------------------- //
// Source list                                                                //
// --------------------------------------------------------------------------- //

function SourceList({
  sources,
}: {
  sources: NonNullable<ChatMessageModel["sources"]>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1 rounded-md border border-dashed border-border bg-background/40 px-3 py-2 text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex w-fit items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        {open ? (
          <ChevronDown className="size-3" aria-hidden="true" />
        ) : (
          <ChevronRight className="size-3" aria-hidden="true" />
        )}
        {open ? "Hide sources" : `Sources (${sources.length})`}
      </button>
      {open && (
        <ul className="flex flex-col gap-1 text-foreground/80">
          {sources.map((s, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <Bot
                className="mt-0.5 size-3 shrink-0 text-primary"
                aria-hidden="true"
              />
              <span>
                <span className="font-medium">{s.topic}</span> — {s.detail}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Typed body — typewriter effect for the *latest* assistant message only.    //
// --------------------------------------------------------------------------- //

function TypedBody({ text }: { text: string }) {
  const [shown, setShown] = useState("");
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const idRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    idRef.current = null;
  }, [text]);
  useEffect(() => {
    if (reduced) {
      setShown(text);
      return;
    }
    let cancelled = false;
    setShown("");
    let i = 0;
    const tick = () => {
      if (cancelled) return;
      i = Math.min(text.length, i + 4);
      setShown(text.slice(0, i));
      if (i < text.length) {
        idRef.current = setTimeout(tick, 12);
      }
    };
    idRef.current = setTimeout(tick, 60);
    return () => {
      cancelled = true;
      if (idRef.current) clearTimeout(idRef.current);
    };
  }, [text, reduced]);
  const complete = shown === text;
  return (
    <div className="relative">
      {formatAssistantBody(shown || text)}
      {!complete && !reduced && (
        <span
          aria-hidden="true"
          className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 animate-pulse bg-primary"
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Helpers                                                                    //
// --------------------------------------------------------------------------- //

/**
 * Derive the 3-state trust label from the message envelope.
 *
 * H7.8C — the source-of-truth is the ``generation`` envelope
 * the backend persists. The legacy ``fallback_used`` flag is
 * used only when the generation envelope is absent (the
 * client-side deterministic consultant, which never hits the
 * backend).
 *
 * The label derivation is deterministic and safe to log; the
 * verifier can grep the rendered output for these exact strings.
 */
export function deriveTrustLabel(message: ChatMessageModel): TrustLabel {
  const gen = message.generation;
  if (gen) {
    if (gen.generation_method === "offline_snapshot" || gen.fallback_reason === "offline_snapshot") {
      return "offline_snapshot";
    }
    if (gen.fallback_used) return "rule_engine";
    if (gen.mode === "open") {
      if (gen.context_manifest && gen.context_manifest.records_used > 0) {
        return "open_business";
      }
      return "open_domain";
    }
    if (gen.grounding_validated) return "generated";
    return "generated";
  }
  return message.fallback_used === false ? "generated" : "rule_engine";
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

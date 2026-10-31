"use client";

/**
 * ConversationList — Redesigned for Bilingual Copilot UX.
 *
 * Primary conversation stream:
 *  - Premium Hero Landing State with interactive prompt chips in EN / KN
 *  - Responsive message bubbles (User right-aligned, Assistant wide-card)
 *  - Smooth autoscroll
 *  - Subtle thinking state
 */

import { useEffect, useRef } from "react";
import {
  ArrowRight,
  Building,
  Globe2,
  LineChart,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { UrsBizIcon } from "@/components/common/Logo";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import type { AssistantContext, Conversation } from "./types";

interface ConversationListProps {
  conversation: Conversation;
  isThinking: boolean;
  /** True when the assistant has messages to show */
  hasMessages: boolean;
  /** Topics the consultant has already answered in this session. */
  memoryTopics?: string[];
  /** Called when the user clicks a prompt chip or smart follow-up. */
  onFollowUp?: (label: string) => void;
  /** Optional AssistantContext snapshot */
  context?: AssistantContext | null;
  /** Optional className passthrough */
  className?: string;
}

export function ConversationList({
  conversation,
  isThinking,
  hasMessages,
  memoryTopics,
  onFollowUp,
  context,
  className,
}: ConversationListProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const { t } = useLanguage();

  const heroPromptChips = [
    {
      icon: TrendingUp,
      label: t("chips.growthStrategy"),
      prompt: t("chips.growthStrategyPrompt"),
    },
    {
      icon: ShieldAlert,
      label: t("chips.riskAnalysis"),
      prompt: t("chips.riskAnalysisPrompt"),
    },
    {
      icon: LineChart,
      label: t("chips.revenuePlanning"),
      prompt: t("chips.revenuePlanningPrompt"),
    },
    {
      icon: Building,
      label: t("chips.govtSchemes"),
      prompt: t("chips.govtSchemesPrompt"),
    },
    {
      icon: Users,
      label: t("chips.hiringTeam"),
      prompt: t("chips.hiringTeamPrompt"),
    },
    {
      icon: Globe2,
      label: t("chips.exportExpansion"),
      prompt: t("chips.exportExpansionPrompt"),
    },
  ];

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distance < 300) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [conversation.messages.length, isThinking]);

  if (!hasMessages) {
    return (
      <div
        className={cn(
          "flex h-full flex-col items-center justify-center px-4 py-8 text-center",
          className,
        )}
      >
        <div className="mx-auto flex max-w-xl flex-col items-center gap-4">
          {/* Glowing Hero Icon */}
          <div className="relative flex items-center justify-center">
            <UrsBizIcon size={48} variant="app-icon" />
          </div>

          {/* Heading */}
          <div className="space-y-1">
            <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
              {t("assistant.copilotBadge")}
            </h2>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">
              {t("assistant.title")}
            </p>
            <p className="pt-1 text-sm text-muted-foreground">
              {t("assistant.subtitle")}
            </p>
          </div>

          {/* Prompt Chips Grid */}
          <div className="mt-4 grid w-full grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {heroPromptChips.map((chip) => {
              const Icon = chip.icon;
              return (
                <button
                  key={chip.label}
                  type="button"
                  onClick={() => onFollowUp?.(chip.prompt)}
                  className="group flex items-center justify-between gap-2 rounded-xl border border-border/80 bg-background/60 p-3 text-left transition-all hover:border-primary/40 hover:bg-primary/5 hover:shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                      <Icon className="size-3.5" aria-hidden="true" />
                    </div>
                    <span className="truncate text-xs font-medium text-foreground">
                      {chip.label}
                    </span>
                  </div>
                  <ArrowRight
                    className="size-3.5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
                    aria-hidden="true"
                  />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className={cn("flex-1 overflow-y-auto px-4 py-4 space-y-4", className)}
      tabIndex={0}
      aria-label="Chat messages stream"
    >
      <div className="mx-auto max-w-4xl space-y-4">
        {conversation.messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            memoryTopics={memoryTopics}
            onFollowUp={onFollowUp}
            context={context}
          />
        ))}

        {isThinking && (
          <div
            className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-muted/30 px-4 py-3 text-xs text-muted-foreground w-fit shadow-2xs"
            role="status"
            aria-live="polite"
          >
            <span className="size-2 rounded-full bg-primary animate-ping" />
            <span>{t("assistant.composingPlaceholder")}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * AI Business Assistant — Redesigned Copilot Architecture.
 *
 * Polished 3-Zone Workspace:
 *  - LEFT: Conversation History Rail (Search, + New Chat, Session rows, collapsible on mobile)
 *  - CENTER: Main AI Copilot Workspace (Status header, Message stream, Hero landing state, Floating composer)
 *  - RIGHT: Business Context Rail (Live score, DNA, Actions, Roadmap, Quick links)
 */

"use client";

import Link from "next/link";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  History,
  Info,
  Layers,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { Button } from "@/components/ui/button";
import { AssistantHeader } from "./AssistantHeader";
import { ChatSessionsList } from "./ChatSessionsList";
import { ConversationList } from "./ConversationList";
import { ContextPanel } from "./ContextPanel";
import { PromptInput } from "./PromptInput";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { SmartFollowUps } from "./SmartFollowUps";
import { useAssistantData } from "./use-assistant-data";
import { classifyQuery } from "./classify-query";
import { buildConsultantResponse } from "./consultant";
import { topicForKind } from "./memory";
import { chatService, type ChatMessageOut } from "@/services";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import type {
  ChatMessage as LocalChatMessage,
  ChatSource as LocalChatSource,
} from "./types";

function toLocalMessage(m: ChatMessageOut): LocalChatMessage {
  return {
    id: String(m.id),
    role: m.role,
    content: m.content,
    createdAt: m.created_at,
    sources: (m.sources || []).map((s) => ({
      topic: s.topic as LocalChatSource["topic"],
      detail: s.detail,
    })),
    kind: undefined,
    fallback_used: m.fallback_used,
    generation: m.generation
      ? (m.generation as unknown as LocalChatMessage["generation"])
      : undefined,
    direct_answer: m.direct_answer ?? null,
    scenario_analysis: m.scenario_analysis
      ? (m.scenario_analysis as unknown as LocalChatMessage["scenario_analysis"])
      : undefined,
    llm_tool_results: m.llm_tool_results ?? [],
    missing_data: m.missing_data ?? [],
    explanation: m.generation
      ? (((m.generation as unknown as Record<string, unknown>).explanation) as unknown as LocalChatMessage["explanation"])
      : undefined,
    tool_execution_traces: m.tool_execution_traces ?? [],
    partial_failure_disclosure: m.partial_failure_disclosure ?? null,
    confidence_penalty: m.confidence_penalty ?? 0,
  };
}

function localToOut(m: LocalChatMessage): ChatMessageOut {
  const epochId = Math.floor(Date.now() / 1000);
  let n = (localToOut as unknown as { _n: number })._n ?? 0;
  n += 1;
  (localToOut as unknown as { _n: number })._n = n;
  const id = epochId * 1000 + n;
  return {
    id,
    role: m.role,
    kind: (m.kind ?? "fallback") as string,
    content: m.content,
    sources: (m.sources || []).map((s) => ({
      topic: s.topic,
      detail: s.detail,
    })),
    created_at: m.createdAt,
    fallback_used: m.fallback_used ?? true,
    generation: m.generation
      ? (m.generation as unknown as ChatMessageOut["generation"])
      : null,
  };
}

export function AssistantView() {
  const { language, t } = useLanguage();
  const {
    state,
    isFetching,
    refresh,
    suggestedQuestions,
    conversation,
    submit,
    submitSuggested,
    clear,
    isThinking,
    smartFollowUps,
    memoryTopics,
    exportConversation,
    searchConversation,
  } = useAssistantData();

  const [serverHistory, setServerHistory] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [serverLoading, setServerLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverMessages, setServerMessages] = useState<ChatMessageOut[]>([]);
  const [useGroundedAI, setUseGroundedAI] = useState(true);

  // Responsive drawer toggles for small screens
  const [showMobileHistory, setShowMobileHistory] = useState(false);
  const [showMobileContext, setShowMobileContext] = useState(false);

  const visibleMessages: LocalChatMessage[] = serverHistory
    ? serverMessages.map(toLocalMessage)
    : conversation.messages;

  const handleServerNew = async () => {
    if (serverLoading) return;
    setServerLoading(true);
    setServerError(null);
    try {
      const detail = await chatService.createSession("");
      setActiveSessionId(detail.id);
      setServerMessages(detail.messages);
      setShowMobileHistory(false);
    } catch (err) {
      setServerError(
        err instanceof Error ? err.message : "Could not start a new conversation.",
      );
    } finally {
      setServerLoading(false);
    }
  };

  const handleServerResume = async (sessionId: number) => {
    if (serverLoading) return;
    setServerLoading(true);
    setServerError(null);
    try {
      const detail = await chatService.getSession(sessionId);
      setActiveSessionId(detail.id);
      setServerMessages(detail.messages);
      setShowMobileHistory(false);
    } catch (err) {
      setServerError(
        err instanceof Error ? err.message : "Could not resume that conversation.",
      );
    } finally {
      setServerLoading(false);
    }
  };

  const handleServerClear = () => {
    if (activeSessionId !== null) {
      void chatService.deleteSession(activeSessionId).catch(() => {});
    }
    setActiveSessionId(null);
    setServerMessages([]);
  };

  const handleServerSubmit = async (prompt: string) => {
    if (serverLoading) return;
    setServerError(null);

    const buildLocalFallbackMessages = (): [LocalChatMessage, LocalChatMessage] | null => {
      if (state.status !== "ready") return null;
      const kind = classifyQuery(prompt);
      const consultant = buildConsultantResponse({
        bundle: state.bundle,
        prompt,
        kind,
        topic: topicForKind(kind),
        recentTopics: [],
      });
      const now = new Date().toISOString();
      const userMsg: LocalChatMessage = {
        id: `local-user-${now}-${Math.random().toString(36).slice(2, 8)}`,
        role: "user",
        content: prompt,
        createdAt: now,
      };
      const assistantMsg: LocalChatMessage = {
        id: `local-assistant-${now}-${Math.random().toString(36).slice(2, 8)}`,
        role: "assistant",
        content: consultant.body,
        createdAt: now,
        kind,
        consultant,
        fallback_used: true,
        generation: {
          provider: "local-rule-engine",
          model: "client-deterministic",
          mode: useGroundedAI ? "grounded" : "open",
          fallback_used: true,
          fallback_reason: "provider_unavailable",
          generation_method: "deterministic",
          schema_validated: true,
          grounding_validated: true,
          server_grounding_score: 100,
          evidence_count: 0,
          confidence: null,
          assumptions: [
            "Local deterministic fallback — the backend provider was unreachable.",
            "Answer was assembled from the same five payloads the dashboard reads.",
          ],
          limitations: [
            "Not generated by an LLM. Numbers reflect the registered business profile only.",
          ],
          evidence_references: [],
          generated_at: now,
          prompt_truncated: false,
          provider_latency_ms: null,
          grounded_payload: null,
        },
      };
      return [userMsg, assistantMsg];
    };

    let sessionId = activeSessionId;
    if (sessionId === null) {
      try {
        const detail = await chatService.createSession("");
        sessionId = detail.id;
        setActiveSessionId(detail.id);
      } catch (err) {
        const local = buildLocalFallbackMessages();
        if (local) {
          setServerMessages(local.map(localToOut));
          setServerError(null);
        } else {
          setServerError(
            err instanceof Error ? err.message : "Could not start a conversation.",
          );
        }
        return;
      }
    }
    setServerLoading(true);
    try {
      const resp = await chatService.appendMessage(sessionId, prompt, {
        mode: useGroundedAI ? "grounded" : "open",
        language,
      });
      setActiveSessionId(resp.session.id);
      setServerError(null);
      if (resp.session && Array.isArray(resp.session.messages) && resp.session.messages.length > 0) {
        setServerMessages(resp.session.messages);
      } else {
        setServerMessages((prev) => [...prev, resp.user_message, resp.assistant_message]);
      }
    } catch (err) {
      const local = buildLocalFallbackMessages();
      if (local) {
        setServerMessages((prev) => [...prev, ...local.map(localToOut)]);
        setServerError(null);
      } else {
        setServerError(
          err instanceof Error ? err.message : t("assistant.sendFailed"),
        );
      }
    } finally {
      setServerLoading(false);
    }
  };

  if (state.status === "loading") {
    return (
      <PageContainer width="wide">
        <div className="flex flex-col gap-4">
          <DashboardSkeleton rows={2} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)_260px]">
            <DashboardSkeleton rows={8} />
            <DashboardSkeleton rows={8} />
            <DashboardSkeleton rows={8} />
          </div>
        </div>
      </PageContainer>
    );
  }

  if (state.status === "no-business") {
    return (
      <PageContainer width="wide">
        <EmptyState
          illustration="building"
          title="No business profile yet"
          description={
            state.detail ||
            "Set up your business profile to chat with the AI Business Assistant."
          }
          actionLabel="Create business profile"
          onAction={() => {
            if (typeof window !== "undefined") window.location.href = "/business";
          }}
          secondaryActionLabel="Learn more"
          onSecondaryAction={() => {
            if (typeof window !== "undefined") window.location.href = "/";
          }}
        />
        <div className="mt-4 flex items-center justify-center">
          <Button asChild variant="ghost" size="sm">
            <Link href="/business">
              Go to Business
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </PageContainer>
    );
  }

  if (state.status === "error") {
    return (
      <PageContainer width="wide">
        <ErrorState
          title="Could not load assistant data"
          description={state.detail}
          actionLabel="Try again"
          onAction={refresh}
        />
      </PageContainer>
    );
  }

  const { context, bundle } = state;
  const lastAnalyzedAt =
    bundle.twin.last_analysis_at ||
    bundle.twin.generated_at ||
    bundle.decision?.generated_at ||
    null;
  const hasMessages = visibleMessages.length > 0;
  const isBusy = isThinking || serverLoading;
  const visibleConversation = {
    id:
      serverHistory && activeSessionId !== null
        ? String(activeSessionId)
        : conversation.id,
    messages: visibleMessages,
    lastMessageAt:
      visibleMessages.length > 0
        ? visibleMessages[visibleMessages.length - 1].createdAt
        : null,
  };

  return (
    <PageContainer width="wide" className="py-4 md:py-6">
      <div className="flex flex-col gap-3">
        {/* Top Header Bar */}
        <AssistantHeader
          lastAnalyzedAt={lastAnalyzedAt}
          isFetching={isFetching}
          onRefresh={refresh}
          onClear={serverHistory ? handleServerClear : clear}
          messageCount={visibleMessages.length}
          rightSlot={
            <div className="flex items-center gap-1.5">
              {/* Grounded vs Open Mode Toggle Pill */}
              <button
                type="button"
                onClick={() => {
                  setUseGroundedAI((prev) => !prev);
                  setServerError(null);
                }}
                aria-pressed={useGroundedAI}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-semibold transition-all",
                  useGroundedAI
                    ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/15"
                    : "border-border bg-background/60 text-muted-foreground hover:bg-muted/50",
                )}
                title={
                  useGroundedAI
                    ? t("assistant.verifiedModeTooltip")
                    : t("assistant.exploratoryModeTooltip")
                }
              >
                <Sparkles className="size-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">
                  {useGroundedAI ? t("assistant.verifiedMode") : t("assistant.exploratoryMode")}
                </span>
              </button>

              {/* Mobile Sidebar Toggle Buttons */}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowMobileHistory((p) => !p)}
                className="h-8 lg:hidden px-2 text-xs"
                aria-label="Toggle chat history"
              >
                <History className="size-3.5" />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowMobileContext((p) => !p)}
                className="h-8 lg:hidden px-2 text-xs"
                aria-label="Toggle business context"
              >
                <Info className="size-3.5" />
              </Button>
            </div>
          }
        />

        {serverError && (
          <p
            className="rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2 text-xs text-destructive"
            role="alert"
          >
            {serverError}
          </p>
        )}

        {/* 3-Zone Workspace Layout */}
        <div className="relative grid h-[calc(100vh-12rem)] min-h-[580px] grid-cols-1 gap-3 lg:grid-cols-[260px_minmax(0,1fr)_260px]">
          {/* Left Zone: Conversation Rail */}
          <aside
            aria-label="Conversation history"
            className={cn(
              "hidden h-full lg:flex lg:flex-col",
              showMobileHistory &&
                "fixed inset-y-16 left-4 z-40 flex w-72 flex-col bg-background/95 shadow-2xl backdrop-blur-md lg:static lg:inset-auto lg:w-auto lg:shadow-none",
            )}
          >
            <ChatSessionsList
              onResume={handleServerResume}
              onNew={handleServerNew}
              activeSessionId={activeSessionId}
              className="h-full"
            />
          </aside>

          {/* Center Zone: Main AI Copilot */}
          <main
            aria-label="AI Copilot workspace"
            className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-border/80 bg-card/40 shadow-xs backdrop-blur-xs"
          >
            {/* Conversation Stream */}
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ConversationList
                conversation={visibleConversation}
                isThinking={isBusy}
                hasMessages={hasMessages}
                memoryTopics={memoryTopics}
                onFollowUp={(label) =>
                  serverHistory ? handleServerSubmit(label) : submit(label)
                }
                context={state.status === "ready" ? state.context : null}
              />
            </div>

            {/* Floating Composer Area */}
            <div className="shrink-0 border-t border-border/40 bg-background/80 p-3 backdrop-blur-md sm:p-4">
              <div className="mx-auto flex max-w-3xl flex-col gap-2">
                <SmartFollowUps
                  followUps={smartFollowUps}
                  onSelect={(f) =>
                    serverHistory ? handleServerSubmit(f.prompt) : submit(f.prompt)
                  }
                  disabled={isBusy}
                />
                <SuggestedQuestions
                  questions={suggestedQuestions}
                  onSelect={(q) =>
                    serverHistory ? handleServerSubmit(q) : submitSuggested(q)
                  }
                  disabled={isBusy}
                />
                <PromptInput
                  onSubmit={serverHistory ? handleServerSubmit : submit}
                  disabled={isBusy}
                  placeholder={
                    isBusy ? "Composing answer…" : "Ask anything about your business…"
                  }
                />
              </div>
            </div>
          </main>

          {/* Right Zone: Business Context */}
          <aside
            aria-label="Business context"
            className={cn(
              "hidden h-full lg:flex lg:flex-col",
              showMobileContext &&
                "fixed inset-y-16 right-4 z-40 flex w-72 flex-col bg-background/95 shadow-2xl backdrop-blur-md lg:static lg:inset-auto lg:w-auto lg:shadow-none",
            )}
          >
            <ContextPanel context={context} className="h-full" />
          </aside>
        </div>
      </div>
    </PageContainer>
  );
}

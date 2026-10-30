"use client";

/**
 * AssistantHeader — Redesigned for Bilingual Copilot UX.
 *
 * Sleek, modern header bar for the main AI Copilot workspace:
 *  - Copilot branding & title in EN / KN
 *  - Subtle live status indicator (Provider / Rule Engine)
 *  - Refresh and Clear chat actions
 *  - Action slots for mode toggles
 */

import { useEffect, useState } from "react";
import { Building2, RefreshCcw, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, chatService, type ChatProviderStatus } from "@/services/chat-service";
import { UrsBizIcon } from "@/components/common/Logo";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";

interface AssistantHeaderProps {
  lastAnalyzedAt: string | null;
  isFetching: boolean;
  onRefresh: () => void;
  onClear: () => void;
  messageCount: number;
  /** Optional right-aligned controls (e.g. server-history toggle). */
  rightSlot?: React.ReactNode;
}

type ProviderState =
  | { kind: "loading" }
  | { kind: "available"; provider: string; model: string }
  | { kind: "fallback" }
  | { kind: "auth" }
  | { kind: "error" };

function toProviderState(
  status: ChatProviderStatus | null,
  loadError: unknown | null,
): ProviderState {
  if (status) {
    if (status.available && !status.fallback_active) {
      return {
        kind: "available",
        provider: status.configured_provider,
        model: status.model,
      };
    }
    return { kind: "fallback" };
  }
  if (loadError) {
    if (loadError instanceof ApiError && loadError.isUnauthenticated) {
      return { kind: "auth" };
    }
    return { kind: "error" };
  }
  return { kind: "loading" };
}

export function AssistantHeader({
  lastAnalyzedAt,
  isFetching,
  onRefresh,
  onClear,
  messageCount,
  rightSlot,
}: AssistantHeaderProps) {
  const [providerStatus, setProviderStatus] = useState<ChatProviderStatus | null>(null);
  const [providerError, setProviderError] = useState<unknown | null>(null);
  const { t } = useLanguage();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const s = await chatService.fetchProviderStatus();
        if (!cancelled) {
          setProviderStatus(s);
          setProviderError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setProviderStatus(null);
          setProviderError(err);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const providerState = toProviderState(providerStatus, providerError);

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 bg-card/60 px-4 py-3 shadow-xs backdrop-blur-sm">
      {/* Title & Live Status */}
      <div className="flex items-center gap-3">
        <UrsBizIcon size={34} />
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-tight text-foreground sm:text-base">
              {t("assistant.title")}
            </h1>
            <span className="hidden rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary sm:inline-block">
              AI
            </span>
          </div>
          <div className="flex items-center gap-2 pt-0.5 text-xs text-muted-foreground">
            <ProviderStatusPill state={providerState} />
            {lastAnalyzedAt && (
              <>
                <span className="text-border">·</span>
                <span className="hidden items-center gap-1 text-[11px] sm:inline-flex">
                  <Building2 className="size-3 text-muted-foreground" aria-hidden="true" />
                  {formatTimestamp(lastAnalyzedAt)}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2">
        {rightSlot}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={isFetching}
          aria-label={isFetching ? t("assistant.refreshData") : t("assistant.refreshData")}
          className="h-8 gap-1.5 rounded-lg px-2.5 text-xs"
        >
          <RefreshCcw
            className={cn("size-3.5 transition-transform", isFetching && "animate-spin")}
            aria-hidden="true"
          />
          <span className="hidden sm:inline">{isFetching ? "…" : t("assistant.refreshData")}</span>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={messageCount === 0}
          aria-label={t("assistant.clearChat")}
          className="h-8 gap-1.5 rounded-lg px-2 text-xs text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="size-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">{t("assistant.clearChat")}</span>
        </Button>
      </div>
    </header>
  );
}

function ProviderStatusPill({ state }: { state: ProviderState }) {
  const { t } = useLanguage();

  switch (state.kind) {
    case "loading":
      return (
        <span
          className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
          data-testid="provider-status-pill"
          data-state="loading"
        >
          <span className="size-1.5 animate-pulse rounded-full bg-primary" />
          {t("common.loading")}
        </span>
      );
    case "available":
      return (
        <span
          className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400"
          data-testid="provider-status-pill"
          data-state="available"
        >
          <span className="size-1.5 rounded-full bg-emerald-500" />
          {state.provider} ({state.model})
        </span>
      );
    case "fallback":
      return (
        <span
          className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400"
          data-testid="provider-status-pill"
          data-state="fallback"
        >
          <span className="size-1.5 rounded-full bg-amber-500" />
          {t("assistant.localRuleEngine")}
        </span>
      );
    case "auth":
      return (
        <span
          className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground"
          data-testid="provider-status-pill"
          data-state="auth"
        >
          <span className="size-1.5 rounded-full bg-muted-foreground" />
          Auth required
        </span>
      );
    case "error":
    default:
      return (
        <span
          className="inline-flex items-center gap-1.5 text-[11px] text-destructive"
          data-testid="provider-status-pill"
          data-state="error"
        >
          <span className="size-1.5 rounded-full bg-destructive" />
          {t("assistant.localRuleEngine")}
        </span>
      );
  }
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

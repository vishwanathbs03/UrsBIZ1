"use client";

/**
 * ChatSessionsList / ConversationRail — Redesigned for Bilingual Copilot UX.
 *
 * Left conversation rail surfacing server-side sessions:
 *  - "+ New Chat" action button
 *  - Search filtering across past conversations
 *  - Lightweight, sleek conversation items with active indicators
 *  - Compact width (~260px)
 */

import { useEffect, useMemo, useState } from "react";
import { Loader2, MessageSquare, Plus, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { chatService, type ChatSessionSummary } from "@/services";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";

interface ChatSessionsListProps {
  /** Called when the user clicks a session. */
  onResume: (sessionId: number) => void;
  /** Called when the user clicks "New conversation". */
  onNew: () => void;
  /** Active session id (highlighted). */
  activeSessionId: number | null;
  /** Optional className passthrough. */
  className?: string;
}

export function ChatSessionsList({
  onResume,
  onNew,
  activeSessionId,
  className,
}: ChatSessionsListProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const { t } = useLanguage();

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await chatService.listSessions();
      setSessions(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load sessions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const handleDelete = async (e: React.MouseEvent, sessionId: number) => {
    e.stopPropagation();
    if (typeof window !== "undefined" && !window.confirm("Delete this conversation?")) {
      return;
    }
    try {
      await chatService.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete session.");
    }
  };

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter((s) => (s.title || "Untitled conversation").toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-2xl border border-border/70 bg-card/60 p-3 shadow-xs backdrop-blur-sm",
        className,
      )}
    >
      {/* Header & New Chat Button */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center gap-2">
          <div className="flex size-6 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <MessageSquare className="size-3.5" aria-hidden="true" />
          </div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            {t("assistant.newChat")}
          </span>
        </div>
        <Button
          type="button"
          size="sm"
          onClick={onNew}
          className="h-7 gap-1 rounded-lg px-2.5 text-xs font-semibold shadow-xs"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          <span>{t("assistant.newChat")}</span>
        </Button>
      </div>

      {/* Real-time Search Input */}
      <div className="relative pb-2">
        <Search className="pointer-events-none absolute left-2.5 top-2 size-3.5 text-muted-foreground/60" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={t("assistant.searchChatsPlaceholder")}
          aria-label={t("assistant.searchChatsPlaceholder")}
          className="h-7.5 w-full rounded-lg border border-border/60 bg-background/50 pl-8 pr-2.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:border-primary/40 focus:outline-none"
        />
      </div>

      {/* Session Rows List */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-0.5">
        {loading && (
          <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-3.5 animate-spin" />
            {t("common.loading")}
          </div>
        )}

        {!loading && error && (
          <p className="p-2 text-xs text-destructive">{error}</p>
        )}

        {!loading && filteredSessions.length === 0 && (
          <div className="py-8 text-center text-xs text-muted-foreground">
            {t("assistant.noChatsFound")}
          </div>
        )}

        {!loading &&
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                role="button"
                tabIndex={0}
                onClick={() => onResume(session.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onResume(session.id);
                  }
                }}
                className={cn(
                  "group relative flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl p-2 text-left transition-all",
                  isActive
                    ? "border border-primary/30 bg-primary/10 text-foreground font-medium shadow-2xs"
                    : "border border-transparent hover:bg-muted/50 text-muted-foreground hover:text-foreground",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium">
                    {session.title || "Untitled conversation"}
                  </p>
                  <p className="flex items-center gap-1 pt-0.5 text-[10px] text-muted-foreground">
                    <span>
                      {session.message_count} {t("assistant.messagesCount")}
                    </span>
                    <span>·</span>
                    <span>{formatRelativeTime(session.updated_at)}</span>
                  </p>
                </div>

                {/* Quick Delete Action */}
                <button
                  type="button"
                  onClick={(e) => handleDelete(e, session.id)}
                  aria-label="Delete chat"
                  className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground/60 hover:text-destructive transition-opacity"
                >
                  <Trash2 className="size-3" />
                </button>
              </div>
            );
          })}
      </div>
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMin = Math.floor((now.getTime() - d.getTime()) / (1000 * 60));
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    return `${Math.floor(diffHr / 24)}d ago`;
  } catch {
    return "";
  }
}
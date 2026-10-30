"use client";

import { Lightbulb } from "lucide-react";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";
import type { SuggestedQuestion } from "./types";

interface SuggestedQuestionsProps {
  questions: readonly SuggestedQuestion[];
  onSelect: (id: string) => void;
  disabled?: boolean;
}

export function SuggestedQuestions({
  questions,
  onSelect,
  disabled,
}: SuggestedQuestionsProps) {
  const { t } = useLanguage();
  if (!questions || questions.length === 0) return null;

  return (
    <div
      role="list"
      aria-label={t("assistant.suggestedTitle")}
      className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar"
    >
      <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">
        <Lightbulb className="size-3 text-primary" aria-hidden="true" />
        {t("assistant.suggestedTitle")}
      </span>
      <div className="flex items-center gap-1.5">
        {questions.map((q) => (
          <button
            key={q.id}
            type="button"
            role="listitem"
            onClick={() => onSelect(q.id)}
            disabled={disabled}
            className={cn(
              "inline-flex shrink-0 items-center rounded-full border border-border/70 bg-background/80 px-2.5 py-1 text-[11px] font-medium text-foreground transition-all",
              "hover:border-primary/40 hover:bg-primary/5 hover:text-primary",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {q.text}
          </button>
        ))}
      </div>
    </div>
  );
}

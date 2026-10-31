"use client";

/**
 * PromptInput — Modern Floating Composer for Copilot.
 *
 * Prominent floating input row at the bottom of the conversation area:
 *  - Auto-growing multiline support (up to 5 lines)
 *  - Keyboard shortcuts (Enter to send, Shift+Enter for newline)
 *  - High-contrast Send button with clean icon
 *  - Focus state with smooth ring glow
 *  - Bilingual localization support
 */

import { forwardRef, useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Sparkles } from "lucide-react";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";

interface PromptInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export const PromptInput = forwardRef<HTMLTextAreaElement, PromptInputProps>(
  function PromptInput(
    { onSubmit, disabled, placeholder, className },
    forwardedRef,
  ) {
    const [value, setValue] = useState("");
    const internalRef = useRef<HTMLTextAreaElement | null>(null);
    const { t } = useLanguage();

    const actualPlaceholder = placeholder ?? t("assistant.composerPlaceholder");

    const setRef = (node: HTMLTextAreaElement | null) => {
      internalRef.current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        forwardedRef.current = node;
      }
    };

    // Auto-resize textarea height as user types
    useEffect(() => {
      const textarea = internalRef.current;
      if (!textarea) return;
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
    }, [value]);

    const submit = useCallback(() => {
      const trimmed = value.trim();
      if (trimmed.length === 0 || disabled) return;
      onSubmit(trimmed);
      setValue("");
      if (internalRef.current) {
        internalRef.current.style.height = "auto";
      }
    }, [value, onSubmit, disabled]);

    const handleKeyDown = useCallback(
      (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          submit();
        }
      },
      [submit],
    );

    const hasContent = value.trim().length > 0;

    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className={cn("relative flex w-full flex-col", className)}
        aria-label={t("assistant.sendAria")}
      >
        <div
          className={cn(
            "relative flex items-end gap-2 rounded-2xl border border-border/80 bg-background/95 p-2 shadow-md backdrop-blur-md transition-all",
            "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20",
            disabled && "opacity-70",
          )}
        >
          <label htmlFor="assistant-prompt" className="sr-only">
            {actualPlaceholder}
          </label>
          <textarea
            id="assistant-prompt"
            ref={setRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={1}
            placeholder={actualPlaceholder}
            aria-label={actualPlaceholder}
            className={cn(
              "max-h-36 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none",
              "disabled:cursor-not-allowed",
            )}
          />

          <div className="flex items-center gap-1.5 pb-1 pr-1">
            <button
              type="submit"
              disabled={disabled || !hasContent}
              aria-label={t("assistant.sendAria")}
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-xl font-medium transition-all shadow-xs",
                hasContent && !disabled
                  ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:scale-105 active:scale-95"
                  : "bg-muted text-muted-foreground cursor-not-allowed opacity-50",
              )}
            >
              <ArrowUp className="size-4.5" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Keyboard shortcut hint */}
        <div className="flex items-center justify-between px-2 pt-1.5 text-[10px] text-muted-foreground/60">
          <span className="flex items-center gap-1">
            <Sparkles className="size-2.5 text-primary" />
            {t("assistant.groundedHint")}
          </span>
          <span className="hidden sm:inline-block">
            {t("assistant.shortcutHint")}
          </span>
        </div>
      </form>
    );
  },
);

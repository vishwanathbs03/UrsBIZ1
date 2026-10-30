"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI.
 *
 * Sleek collapsible "secondary card" primitive for progressive disclosure
 * of Supporting Explanation, Findings, Actions, Risks, and Evidence.
 */

import { ChevronDown, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SecondaryCardProps {
  /** Section title — shown in the toggle header. */
  title: string;
  /** Small line under the title. */
  caption?: string;
  /** Optional leading icon. aria-hidden by default. */
  icon?: LucideIcon;
  /** Body content. Rendered only when expanded. */
  children: ReactNode;
  /** Open by default. Default false per the brief. */
  defaultOpen?: boolean;
  /** Optional className passthrough. */
  className?: string;
  /** Optional data-testid for tests. */
  testId?: string;
}

export function SecondaryCard({
  title,
  caption,
  icon: Icon,
  children,
  defaultOpen = false,
  className,
  testId,
}: SecondaryCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section
      data-testid={testId ?? `secondary-card-${toKebab(title)}`}
      className={cn(
        "overflow-hidden rounded-xl border border-border/60 bg-background/50 transition-colors hover:border-border",
        open && "border-border bg-background/70 shadow-xs",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls={`secondary-card-${toKebab(title)}-body`}
        className="flex min-h-[40px] w-full items-center gap-2.5 px-3 py-2 text-left transition-colors sm:px-3.5"
      >
        {Icon ? (
          <span
            aria-hidden="true"
            className={cn(
              "flex size-5.5 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors",
              open && "bg-primary/10 text-primary",
            )}
          >
            <Icon className="size-3" />
          </span>
        ) : null}
        <span className="flex-1 min-w-0">
          <span className="block text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            {title}
          </span>
          {caption ? (
            <span className="block truncate text-[11px] text-muted-foreground/80">
              {caption}
            </span>
          ) : null}
        </span>
        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
            open ? "rotate-180 text-primary" : "rotate-0",
          )}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div
          id={`secondary-card-${toKebab(title)}-body`}
          className="border-t border-border/40 px-3.5 py-3 sm:px-4 text-sm"
        >
          {children}
        </div>
      ) : null}
    </section>
  );
}

function toKebab(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default SecondaryCard;
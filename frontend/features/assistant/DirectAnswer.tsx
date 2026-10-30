"use client";

/**
 * SPRINT AI-6 — Trust-first visual UI. The 1-3 sentence
 * "Direct Answer" the user can read within 10 seconds. Always
 * rendered at the top of the assistant bubble, above the
 * TrustBar and secondary cards.
 *
 * The text comes from ``extractDirectAnswer`` — server-stamped
 * ``message.direct_answer`` when available, falling back to
 * the executive summary / consultant body / message content.
 *
 * Mobile-first: a single line of bold body text, capped at 600
 * characters. No icons in the body — this is the prose-only
 * surface.
 */
import React from "react";
import { cn } from "@/lib/utils";

export interface DirectAnswerProps {
  /** 1-3 sentences already extracted. ``null`` hides the block. */
  text: string | null;
  /** Optional className passthrough for positioning. */
  className?: string;
}

export function DirectAnswer({ text, className }: DirectAnswerProps) {
  if (!text || text.trim().length === 0) {
    return null;
  }
  return (
    <p
      data-testid="direct-answer"
      className={cn(
        "text-balance text-base font-medium leading-snug text-foreground",
        className,
      )}
    >
      {text}
    </p>
  );
}

export default DirectAnswer;
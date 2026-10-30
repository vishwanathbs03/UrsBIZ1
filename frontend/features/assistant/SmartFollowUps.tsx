"use client";

import { Sparkles, Zap } from "lucide-react";
import { useLanguage } from "@/context/language-context";

interface FollowUpShape {
  id: string;
  label: string;
  prompt: string;
  routesTo: string;
}

export interface SmartFollowUpsProps {
  followUps: ReadonlyArray<FollowUpShape>;
  onSelect: (f: FollowUpShape) => void;
  disabled?: boolean;
}

export function SmartFollowUps({
  followUps,
  onSelect,
  disabled,
}: SmartFollowUpsProps) {
  const { t } = useLanguage();
  if (followUps.length === 0) return null;
  return (
    <div
      className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar"
      aria-label={t("assistant.followUpsTitle")}
    >
      <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">
        <Sparkles className="size-3 text-primary" aria-hidden />
        {t("assistant.followUpsTitle")}
      </span>
      <div className="flex items-center gap-1.5">
        {followUps.map((f) => (
          <button
            key={f.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(f)}
            className="group inline-flex shrink-0 items-center gap-1 rounded-full border border-border/70 bg-background/80 px-2.5 py-1 text-[11px] font-medium text-foreground transition-all hover:border-primary/40 hover:bg-primary/10 hover:text-primary disabled:pointer-events-none disabled:opacity-50"
          >
            <Zap
              className="size-2.5 text-primary/70 transition-transform group-hover:scale-110 group-hover:text-primary"
              aria-hidden
            />
            <span>{f.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cpu, Database, X } from "lucide-react";
import { useLanguage } from "@/context/language-context";
import { continuityService, type SystemContinuityStatus } from "@/services/continuity-service";
import { cn } from "@/lib/utils";

export function ContinuityBanner() {
  const { language } = useLanguage();
  const [dismissedMode, setDismissedMode] = useState<string | null>(null);

  const { data, isError } = useQuery<SystemContinuityStatus>({
    queryKey: ["system-continuity-status"],
    queryFn: () => continuityService.getStatus(),
    refetchInterval: 30000,
    staleTime: 15000,
    retry: 1,
  });

  // Reset dismissed state if system mode changes
  useEffect(() => {
    if (data?.system_mode && data.system_mode !== dismissedMode) {
      // If system returned to operational, clear dismissed state
      if (data.system_mode === "OPERATIONAL") {
        setDismissedMode(null);
      }
    }
  }, [data?.system_mode, dismissedMode]);

  if (isError || !data || data.system_mode === "OPERATIONAL" || dismissedMode === data.system_mode) {
    return null;
  }

  const isRuleEngine = data.system_mode === "RULE_ENGINE_FALLBACK";

  const notice = language === "kn" ? data.notice_kn : data.notice_en;

  const title = isRuleEngine
    ? language === "kn"
      ? "ನಿಯಮ ಎಂಜಿನ್ ಫಾಲ್‌ಬ್ಯಾಕ್ ಸಕ್ರಿಯವಾಗಿದೆ"
      : "Rule Engine Fallback Active"
    : language === "kn"
      ? "ಸ್ಥಿತಿಸ್ಥಾಪಕ ಓದಲು-ಮಾತ್ರ ಮೋಡ್"
      : "Resilient Read-Only Mode Active";

  const badge = isRuleEngine
    ? language === "kn"
      ? "ಶೂನ್ಯ ಕಲ್ಪನೆ ಗ್ಯಾರಂಟಿ"
      : "Zero Hallucination Guaranteed"
    : language === "kn"
      ? "ಸಂಗ್ರಹಿಸಿದ ಸ್ನ್ಯಾಪ್‌ಶಾಟ್"
      : "Cached Snapshot Active";

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="system-continuity-banner"
      data-continuity-mode={data.system_mode}
      className={cn(
        "relative z-40 flex items-center justify-between border-b px-4 py-2.5 text-xs sm:text-sm transition-all",
        isRuleEngine
          ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200"
          : "border-orange-500/30 bg-orange-500/10 text-orange-950 dark:text-orange-200"
      )}
    >
      <div className="flex flex-1 items-center gap-2.5 overflow-hidden">
        {isRuleEngine ? (
          <Cpu className="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        ) : (
          <Database className="size-4 shrink-0 text-orange-600 dark:text-orange-400" aria-hidden="true" />
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{title}:</span>
          <span className="truncate">{notice}</span>
          <span
            className={cn(
              "hidden sm:inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase",
              isRuleEngine
                ? "border-amber-600/30 bg-amber-600/10 text-amber-800 dark:text-amber-300"
                : "border-orange-600/30 bg-orange-600/10 text-orange-800 dark:text-orange-300"
            )}
          >
            {badge}
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setDismissedMode(data.system_mode)}
        aria-label={language === "kn" ? "ಸೂಚನೆ ಮುಚ್ಚಿ" : "Dismiss notice"}
        className="ml-3 shrink-0 rounded p-1 hover:bg-black/5 dark:hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-accent"
      >
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

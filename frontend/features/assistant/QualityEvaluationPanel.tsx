"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  BarChart2,
  CheckCircle2,
  HelpCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  chatFeedbackService,
  type ChatFeedbackAnalytics,
  type FeedbackCategory,
} from "@/services/chat-feedback-service";
import { useLanguage } from "@/context/language-context";
import { cn } from "@/lib/utils";

interface QualityEvaluationPanelProps {
  className?: string;
  onClose?: () => void;
}

const CATEGORY_TRANSLATIONS: Record<FeedbackCategory, { en: string; kn: string }> = {
  Helpful: { en: "Helpful", kn: "ಸಹಾಯಕ" },
  "Incorrect Information": { en: "Incorrect Information", kn: "ತಪ್ಪಾದ ಮಾಹಿತಿ" },
  "Missing Evidence": { en: "Missing Evidence", kn: "ಪುರಾವೆ ಕೊರತೆ" },
  "Outdated Data": { en: "Outdated Data", kn: "ಹಳೆಯ ಡೇಟಾ" },
  "Difficult to Understand": { en: "Difficult to Understand", kn: "ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಕಷ್ಟ" },
};

export function QualityEvaluationPanel({
  className,
  onClose,
}: QualityEvaluationPanelProps) {
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<ChatFeedbackAnalytics | null>(null);
  const { t, language } = useLanguage();

  const fetchAnalytics = async (lookback: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await chatFeedbackService.getQualityAnalytics(lookback);
      setAnalytics(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : language === "kn"
          ? "AI ಗುಣಮಟ್ಟದ ವಿಶ್ಲೇಷಣೆಗಳನ್ನು ಲೋಡ್ ಮಾಡಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ."
          : "Could not load AI quality analytics.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics(days);
  }, [days]);

  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm",
        className,
      )}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Sparkles className="size-4" />
          </div>
          <div>
            <h3 className={cn("text-sm font-semibold text-foreground", language === "kn" && "font-kannada")}>
              {language === "kn" ? "AI ಉತ್ತರ ಗುಣಮಟ್ಟ ಮತ್ತು ಪ್ರತಿಕ್ರಿಯೆ ಮೌಲ್ಯಮಾಪನ" : "AI Answer Quality & Feedback Evaluation"}
            </h3>
            <p className={cn("text-xs text-muted-foreground", language === "kn" && "font-kannada")}>
              {language === "kn"
                ? "ನಿರಂತರ ಮೇಲ್ವಿಚಾರಣೆ, ಆಧಾರಿತ ವಿಶ್ವಾಸಾರ್ಹತೆ ಮತ್ತು ಟೆಲಿಮೆಟ್ರಿ"
                : "Continuous monitoring, grounding correlation & failure mode telemetry"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Lookback Selector */}
          <div className="flex items-center rounded-lg border border-border bg-muted/40 p-0.5 text-xs">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={cn(
                  "rounded-md px-2.5 py-1 font-medium transition-colors",
                  days === d
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {d}d
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => fetchAnalytics(days)}
            disabled={loading}
            aria-label={t("common.refresh", "Refresh quality metrics")}
            className="rounded-lg border border-border p-1.5 text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-xs font-medium text-muted-foreground hover:text-foreground px-2 py-1"
            >
              {t("common.close", "Close")}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {loading && !analytics ? (
        <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
          <RefreshCw className="mr-2 size-4 animate-spin text-primary" />
          {t("a11y.loadingState", "Evaluating AI quality metrics...")}
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-xs text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : analytics ? (
        <div className="space-y-4">
          {/* Top Score Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
              <span className={cn("text-[11px] font-medium text-muted-foreground", language === "kn" && "font-kannada")}>
                {language === "kn" ? "ಗುಣಮಟ್ಟದ ಸ್ಕೋರ್" : "Quality Score"}
              </span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-bold text-foreground">
                  {analytics.quality_score}
                </span>
                <span className="text-[11px] text-muted-foreground">/ 100</span>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
              <span className={cn("text-[11px] font-medium text-muted-foreground", language === "kn" && "font-kannada")}>
                {language === "kn" ? "ಸಹಾಯಕತೆಯ ಪ್ರಮಾಣ" : "Helpfulness Rate"}
              </span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-bold text-foreground">
                  {Math.round(analytics.helpfulness_rate * 100)}%
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
              <span className={cn("text-[11px] font-medium text-muted-foreground", language === "kn" && "font-kannada")}>
                {language === "kn" ? "ಸರಾಸರಿ ರೇಟಿಂಗ್" : "Average Rating"}
              </span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-bold text-foreground">
                  {analytics.average_rating.toFixed(1)}
                </span>
                <span className="text-[11px] text-muted-foreground">/ 5.0</span>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
              <span className={cn("text-[11px] font-medium text-muted-foreground", language === "kn" && "font-kannada")}>
                {language === "kn" ? "ಒಟ್ಟು ಪ್ರತಿಕ್ರಿಯೆಗಳು" : "Total Feedback"}
              </span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-xl font-bold text-foreground">
                  {analytics.total_feedback_count}
                </span>
                <span className={cn("text-[11px] text-muted-foreground", language === "kn" && "font-kannada")}>
                  {language === "kn" ? "ರೇಟಿಂಗ್‌ಗಳು" : "ratings"}
                </span>
              </div>
            </div>
          </div>

          {/* Grounding Correlation Telemetry */}
          <div className="rounded-xl border border-border bg-card/60 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className={cn("text-xs font-semibold text-foreground flex items-center gap-1.5", language === "kn" && "font-kannada")}>
                <HelpCircle className="size-3.5 text-primary" />
                {language === "kn" ? "ಆಧಾರಿತ vs ನಿಯಮ ಎಂಜಿನ್ ಟೆಲಿಮೆಟ್ರಿ" : "Grounded vs. Rule Fallback Telemetry"}
              </span>
              <span className="text-[10px] text-muted-foreground font-mono">
                {language === "kn" ? "ಪುರಾವೆ ಹೋಲಿಕೆ" : "PROVENANCE COMPARISON"}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2.5">
                <div className="flex items-center justify-between">
                  <span className={cn("font-medium text-emerald-800 dark:text-emerald-300 flex items-center gap-1", language === "kn" && "font-kannada")}>
                    <CheckCircle2 className="size-3 text-emerald-600" />
                    {language === "kn" ? "ಆಧಾರಿತ ಉತ್ತರಗಳು" : "Grounded Turns"}
                  </span>
                  <span className="font-bold text-emerald-700">
                    {analytics.grounding_correlation.grounded_average_rating.toFixed(1)} / 5.0
                  </span>
                </div>
                <p className={cn("mt-1 text-[11px] text-muted-foreground", language === "kn" && "font-kannada")}>
                  {language === "kn"
                    ? `${analytics.grounding_correlation.grounded_message_count} ಪರಿಶೀಲಿಸಿದ ಪುರಾವೆಯೊಂದಿಗೆ ಉತ್ತರಗಳು`
                    : `${analytics.grounding_correlation.grounded_message_count} answers with verified citations`}
                </p>
              </div>

              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-2.5">
                <div className="flex items-center justify-between">
                  <span className={cn("font-medium text-amber-800 dark:text-amber-300 flex items-center gap-1", language === "kn" && "font-kannada")}>
                    <AlertCircle className="size-3 text-amber-600" />
                    {language === "kn" ? "ನಿಯಮ ಎಂಜಿನ್ ಉತ್ತರಗಳು" : "Rule Fallback Turns"}
                  </span>
                  <span className="font-bold text-amber-700">
                    {analytics.grounding_correlation.fallback_average_rating.toFixed(1)} / 5.0
                  </span>
                </div>
                <p className={cn("mt-1 text-[11px] text-muted-foreground", language === "kn" && "font-kannada")}>
                  {language === "kn"
                    ? `${analytics.grounding_correlation.fallback_message_count} ಫಾಲ್‌ಬ್ಯಾಕ್ ಉತ್ತರಗಳು (${Math.round(analytics.grounding_correlation.fallback_unhelpful_rate * 100)}% ಅತೃಪ್ತಿ ಪ್ರಮಾಣ)`
                    : `${analytics.grounding_correlation.fallback_message_count} fallbacks (${Math.round(analytics.grounding_correlation.fallback_unhelpful_rate * 100)}% dissatisfaction rate)`}
                </p>
              </div>
            </div>

            {analytics.grounding_correlation.unclassified_message_count > 0 && (
              <p className={cn("text-[10px] text-muted-foreground italic", language === "kn" && "font-kannada")}>
                {language === "kn"
                  ? `* ಗಮನಿಸಿ: ಅನಿರ್ದಿಷ್ಟ ಮೆಟಾಡೇಟಾ ಹೊಂದಿರುವ ${analytics.grounding_correlation.unclassified_message_count} ಸಂದೇಶಗಳನ್ನು ಹೋಲಿಕೆಯಿಂದ ಹೊರಗಿಡಲಾಗಿದೆ.`
                  : `* Note: ${analytics.grounding_correlation.unclassified_message_count} message turn(s) with missing or indeterminate provenance metadata were excluded from grounding comparison.`}
              </p>
            )}
          </div>

          {/* Category Breakdown */}
          <div className="rounded-xl border border-border bg-card/60 p-3.5 space-y-2.5">
            <span className={cn("text-xs font-semibold text-foreground flex items-center gap-1.5", language === "kn" && "font-kannada")}>
              <BarChart2 className="size-3.5 text-muted-foreground" />
              {language === "kn" ? "ಪ್ರತಿಕ್ರಿಯೆ ವಿಭಾಗಗಳ ಹಂಚಿಕೆ" : "Feedback Category Distribution"}
            </span>

            <div className="space-y-1.5 text-xs">
              {(
                [
                  "Helpful",
                  "Incorrect Information",
                  "Missing Evidence",
                  "Outdated Data",
                  "Difficult to Understand",
                ] as FeedbackCategory[]
              ).map((cat) => {
                const count = analytics.category_distribution[cat] || 0;
                const pct =
                  analytics.total_feedback_count > 0
                    ? Math.round((count / analytics.total_feedback_count) * 100)
                    : 0;
                const isPos = cat === "Helpful";
                const catLabel = language === "kn" ? CATEGORY_TRANSLATIONS[cat].kn : CATEGORY_TRANSLATIONS[cat].en;

                return (
                  <div key={cat} className="space-y-0.5">
                    <div className="flex justify-between text-[11px]">
                      <span className={cn("text-foreground", language === "kn" && "font-kannada")}>{catLabel}</span>
                      <span className="text-muted-foreground font-mono">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-muted/60 overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          isPos ? "bg-emerald-500" : "bg-amber-500",
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Zero-Retention Privacy Note */}
          <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-2.5 text-[11px] text-muted-foreground">
            <ShieldCheck className="size-3.5 shrink-0 text-primary mt-0.5" />
            <span className={cn(language === "kn" && "font-kannada")}>
              <strong>{language === "kn" ? "ಶೂನ್ಯ-ಧಾರಣ ಸಾರ್ವಭೌಮತ್ವ: " : "Zero-Retention Sovereignty: "}</strong>
              {language === "kn"
                ? "ಪ್ರತಿಕ್ರಿಯೆಯು ಕಟ್ಟುನಿಟ್ಟಾಗಿ ನಿಮ್ಮ ಸಂಸ್ಥೆಗೆ ಸೀಮಿತವಾಗಿದೆ. ಬಳಕೆದಾರರು ಮತ್ತು ನಿರ್ವಾಹಕರು ಯಾವುದೇ ಸಮಯದಲ್ಲಿ ಟಿಪ್ಪಣಿಗಳನ್ನು ಅಳಿಸಬಹುದು."
                : "Feedback is strictly tenant-isolated to your organization. Users and administrators can purge qualitative feedback notes at any time."}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

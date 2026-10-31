"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Award,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  FileText,
  HelpCircle,
  Lightbulb,
  ListChecks,
  Play,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { LevelBadge } from "@/features/dashboard/LevelBadge";
import { levelToTone } from "@/features/dashboard/tones";
import { cn } from "@/lib/utils";
import type {
  FeedbackType,
  RecommendationExplainResponse,
  RecommendationPriority,
  RecommendationStatus,
  SmartRecommendationItem,
} from "@/types/smart-recommendations";

interface SmartRecommendationCardProps {
  item: SmartRecommendationItem;
  onUpdateStatus: (id: string, status: RecommendationStatus, notes?: string) => Promise<any>;
  onExplain: (id: string) => Promise<RecommendationExplainResponse>;
  onFeedback?: (id: string, feedback: FeedbackType) => Promise<any>;
  isUpdatingStatus?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  "Revenue Growth": "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  "Cost Optimization": "text-amber-400 bg-amber-500/10 border-amber-500/20",
  "Customer Retention": "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  "Product Performance": "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  "Demand and Sales Planning": "text-violet-400 bg-violet-500/10 border-violet-500/20",
  "Digital Transformation": "text-blue-400 bg-blue-500/10 border-blue-500/20",
  "Financial Management": "text-rose-400 bg-rose-500/10 border-rose-500/20",
  "Operational Efficiency": "text-teal-400 bg-teal-500/10 border-teal-500/20",
  "Government Schemes and Funding": "text-amber-300 bg-amber-400/10 border-amber-400/20",
  "Risk Reduction": "text-orange-400 bg-orange-500/10 border-orange-500/20",
};

const STATUS_BADGE: Record<RecommendationStatus, { label: string; tone: "positive" | "warning" | "neutral" | "caution" }> = {
  New: { label: "New", tone: "neutral" },
  Viewed: { label: "Viewed", tone: "neutral" },
  Accepted: { label: "Accepted", tone: "positive" },
  "In Progress": { label: "In Progress", tone: "warning" },
  Completed: { label: "Completed", tone: "positive" },
  Dismissed: { label: "Dismissed", tone: "caution" },
};

export function SmartRecommendationCard({
  item,
  onUpdateStatus,
  onExplain,
  onFeedback,
  isUpdatingStatus,
}: SmartRecommendationCardProps) {
  const [showPlan, setShowPlan] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<RecommendationExplainResponse | null>(null);
  const [isLoadingAi, setIsLoadingAi] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<string | null>(null);

  const catStyle =
    CATEGORY_COLORS[item.category] || "text-primary bg-primary/10 border-primary/20";
  const statusMeta = STATUS_BADGE[item.status] || { label: item.status, tone: "neutral" };

  const handleExplain = async () => {
    if (aiExplanation) {
      setAiExplanation(null);
      return;
    }
    setIsLoadingAi(true);
    setAiError(null);
    try {
      const res = await onExplain(item.id);
      setAiExplanation(res);
    } catch (err: any) {
      setAiError(err?.message || "Could not retrieve AI explanation.");
    } finally {
      setIsLoadingAi(false);
    }
  };

  return (
    <div
      className={cn(
        "group relative flex flex-col gap-3 rounded-xl border border-border/80 bg-card/60 p-4 shadow-sm backdrop-blur-sm transition-all hover:border-primary/40 hover:shadow-md",
        item.priority === "Critical" && "border-rose-500/30 bg-rose-500/[0.03]",
        item.status === "Dismissed" && "opacity-60"
      )}
    >
      {/* Top Header: Category & Priority */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-wide",
              catStyle
            )}
          >
            <Award className="size-3" />
            {item.category}
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-muted-foreground">
            <Zap className="size-3 text-amber-400" />
            Score: <strong className="text-foreground">{item.priority_score}</strong>/100
          </span>
        </div>

        <div className="flex items-center gap-2">
          <LevelBadge level={item.status} tone={statusMeta.tone} />
          <LevelBadge level={item.priority} tone={levelToTone(item.priority)} />
        </div>
      </div>

      {/* Title & Core Description */}
      <div>
        <h4 className="text-base font-semibold text-foreground transition-colors group-hover:text-primary">
          {item.title}
        </h4>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
          {item.description}
        </p>
      </div>

      {/* Impact & Confidence Bar */}
      <div className="grid grid-cols-2 gap-2 rounded-lg border border-border/40 bg-secondary/20 p-2.5 text-xs sm:grid-cols-4">
        <div>
          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
            Expected Benefit
          </span>
          <span className="font-medium text-foreground line-clamp-1">
            {item.expected_benefit}
          </span>
        </div>

        <div>
          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
            Estimated Impact
          </span>
          <span className="font-semibold text-emerald-400">
            {item.estimated_impact !== null && item.estimated_impact !== undefined
              ? `${item.estimated_impact.toLocaleString()} ${item.impact_unit || ""}`
              : "Qualitative"}
          </span>
        </div>

        <div>
          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
            Confidence
          </span>
          <span className="font-medium text-foreground">{item.confidence}%</span>
        </div>

        <div>
          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground">
            Data Quality
          </span>
          <span
            className={cn(
              "font-medium",
              item.data_quality === "High" && "text-emerald-400",
              item.data_quality === "Moderate" && "text-amber-400",
              item.data_quality === "Limited" && "text-orange-400",
              item.data_quality === "Insufficient" && "text-rose-400"
            )}
          >
            {item.data_quality}
          </span>
        </div>
      </div>

      {/* Expandable Evidence Accordion */}
      <div className="border-t border-border/40 pt-2">
        <button
          type="button"
          onClick={() => setShowEvidence(!showEvidence)}
          className="flex w-full items-center justify-between text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <span className="flex items-center gap-1.5">
            <FileText className="size-3.5 text-primary" />
            Supporting Business Evidence ({item.evidence.length})
          </span>
          {showEvidence ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </button>

        {showEvidence && (
          <div className="mt-2.5 flex flex-col gap-1.5 rounded-lg border border-border/60 bg-background/50 p-3 text-xs text-muted-foreground">
            <div className="mb-1 font-semibold text-foreground">
              Business Context: <span className="font-normal text-muted-foreground">{item.business_context}</span>
            </div>
            <ul className="list-inside list-disc space-y-1">
              {item.evidence.map((ev, i) => (
                <li key={i} className="text-foreground/90">
                  {ev}
                </li>
              ))}
            </ul>
            {item.limitations.length > 0 && (
              <div className="mt-2 border-t border-border/30 pt-1.5 text-[11px] text-amber-400/90">
                <strong>Data Consideration:</strong> {item.limitations.join("; ")}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Expandable Action Plan */}
      {item.action_plan && (
        <div className="border-t border-border/40 pt-2">
          <button
            type="button"
            onClick={() => setShowPlan(!showPlan)}
            className="flex w-full items-center justify-between text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <span className="flex items-center gap-1.5">
              <ListChecks className="size-3.5 text-emerald-400" />
              Action Plan: {item.action_plan.objective} ({item.action_plan.suggested_timeframe})
            </span>
            {showPlan ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </button>

          {showPlan && (
            <div className="mt-2.5 space-y-2 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.02] p-3 text-xs">
              <div className="mb-2 text-xs font-semibold text-emerald-400">
                Success Metric: <span className="text-foreground font-normal">{item.action_plan.success_metric}</span>
              </div>
              <div className="space-y-2">
                {item.action_plan.steps.map((st) => (
                  <div
                    key={st.step_number}
                    className="flex items-start gap-2 rounded border border-border/40 bg-secondary/30 p-2"
                  >
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-[10px] font-bold text-emerald-400">
                      {st.step_number}
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <strong className="text-foreground">{st.title}</strong>
                        <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                          <Clock className="size-3" />
                          {st.timeframe}
                        </span>
                      </div>
                      <p className="mt-0.5 text-muted-foreground">{st.description}</p>
                      <div className="mt-1 text-[10px] text-muted-foreground">
                        Resources: {st.resources_required}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Explanation Accordion Card */}
      {aiExplanation && (
        <div className="rounded-lg border border-primary/30 bg-primary/[0.04] p-3 text-xs">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="flex items-center gap-1.5 font-semibold text-primary">
              <Sparkles className="size-3.5" />
              AI Contextual Explanation
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">
              {aiExplanation.is_ai_generated ? "Gemini 2.0 Flash" : "Deterministic Fallback Engine"}
            </span>
          </div>
          <p className="text-foreground/90 whitespace-pre-line leading-relaxed">
            {aiExplanation.explanation}
          </p>
        </div>
      )}
      {aiError && (
        <div className="rounded border border-rose-500/30 bg-rose-500/10 p-2 text-xs text-rose-400">
          {aiError}
        </div>
      )}

      {/* Card Footer: Deep links & Lifecycle Actions */}
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 border-t border-border/40 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          {item.source_module_link && (
            <Link
              href={item.source_module_link}
              className="inline-flex items-center gap-1 rounded border border-border/60 bg-secondary/40 px-2.5 py-1 text-xs font-medium text-foreground hover:bg-secondary hover:text-primary transition-colors"
            >
              <span>Explore in {item.source_modules[0] || "Module"}</span>
              <ArrowRight className="size-3" />
            </Link>
          )}

          <Button
            size="sm"
            variant="ghost"
            onClick={handleExplain}
            disabled={isLoadingAi}
            className="h-7 text-xs text-primary hover:text-primary hover:bg-primary/10 gap-1 px-2.5"
          >
            <Sparkles className="size-3" />
            {isLoadingAi ? "Explaining..." : aiExplanation ? "Hide Explanation" : "Explain with AI"}
          </Button>
        </div>

        {/* Lifecycle Transitions */}
        <div className="flex items-center gap-1.5">
          {item.status !== "Accepted" && item.status !== "In Progress" && item.status !== "Completed" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isUpdatingStatus}
              onClick={() => onUpdateStatus(item.id, "Accepted")}
              className="h-7 text-xs border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 px-2"
            >
              Accept
            </Button>
          )}

          {item.status !== "In Progress" && item.status !== "Completed" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isUpdatingStatus}
              onClick={() => onUpdateStatus(item.id, "In Progress")}
              className="h-7 text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10 px-2"
            >
              Start
            </Button>
          )}

          {item.status !== "Completed" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isUpdatingStatus}
              onClick={() => onUpdateStatus(item.id, "Completed")}
              className="h-7 text-xs border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 px-2 gap-1"
            >
              <CheckCircle2 className="size-3" />
              Complete
            </Button>
          )}

          {item.status !== "Dismissed" ? (
            <Button
              size="sm"
              variant="ghost"
              disabled={isUpdatingStatus}
              onClick={() => onUpdateStatus(item.id, "Dismissed")}
              className="h-7 text-xs text-muted-foreground hover:text-rose-400 px-1.5"
              title="Dismiss recommendation"
            >
              <XCircle className="size-3.5" />
            </Button>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              disabled={isUpdatingStatus}
              onClick={() => onUpdateStatus(item.id, "New")}
              className="h-7 text-xs text-muted-foreground hover:text-foreground px-1.5"
              title="Restore recommendation"
            >
              <RotateCcw className="size-3.5" />
            </Button>
          )}
        </div>

        {/* Feedback Bar */}
        <div className="flex flex-wrap items-center justify-between border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
          <span>Was this recommendation relevant for your business?</span>
          {feedbackSubmitted ? (
            <span className="font-semibold text-emerald-400">Feedback recorded. Thank you!</span>
          ) : (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={async () => {
                  if (onFeedback) await onFeedback(item.id, "Useful");
                  setFeedbackSubmitted("Useful");
                }}
                className="rounded px-2 py-0.5 hover:bg-secondary hover:text-foreground border border-border/60 transition-colors"
              >
                Useful
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (onFeedback) await onFeedback(item.id, "Already implemented");
                  setFeedbackSubmitted("Already implemented");
                }}
                className="rounded px-2 py-0.5 hover:bg-secondary hover:text-foreground border border-border/60 transition-colors"
              >
                Already Done
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (onFeedback) await onFeedback(item.id, "Not relevant");
                  setFeedbackSubmitted("Not relevant");
                }}
                className="rounded px-2 py-0.5 hover:bg-secondary hover:text-foreground border border-border/60 transition-colors"
              >
                Not Relevant
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

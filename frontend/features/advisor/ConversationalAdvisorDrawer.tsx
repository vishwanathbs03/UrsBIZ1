"use client";

import { useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Award,
  Calculator,
  CheckCircle2,
  Cpu,
  HelpCircle,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wrench,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { smartRecommendationsService } from "@/services/smart-recommendations-service";
import type { RecommendationAskResponse } from "@/types/smart-recommendations";

const SAMPLE_QUESTIONS = [
  "Why is my revenue vulnerable to customer loss?",
  "How is the demand looking for my products next quarter?",
  "Which government scheme should I apply for with my turnover?",
  "Why is my revenue increasing while profit is struggling?",
  "Which customers should I focus on to grow sustainably?",
];

interface ConversationTurn {
  id: string;
  question: string;
  response: RecommendationAskResponse;
}

export function ConversationalAdvisorDrawer() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [activeResponse, setActiveResponse] = useState<RecommendationAskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  const handleFeedback = async (type: string) => {
    try {
      await smartRecommendationsService.submitFeedback({
        recommendation_id: `advisor_${activeResponse?.intent || "general"}`,
        feedback_type: type as any,
        outcome_notes: `Owner feedback on answer to "${activeResponse?.question}"`,
      });
      setFeedbackSuccess(`Recorded: "${type}". Thank you!`);
      setTimeout(() => setFeedbackSuccess(null), 3500);
    } catch {
      // ignore
    }
  };

  const handleAsk = async (queryToAsk?: string) => {
    const q = (queryToAsk || question).trim();
    if (!q) return;

    setIsLoading(true);
    setError(null);

    // Build multi-turn conversational history
    const history = turns.flatMap((t) => [
      { role: "user", content: t.question },
      { role: "assistant", content: t.response.direct_answer },
    ]);

    try {
      const res = await smartRecommendationsService.askQuestion({
        question: q,
        conversation_history: history,
      });

      const newTurn: ConversationTurn = {
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        question: q,
        response: res,
      };

      setTurns((prev) => [...prev, newTurn]);
      setActiveResponse(res);
      setQuestion("");
    } catch (err: any) {
      setError(err?.message || "Failed to retrieve advisory answer. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearConversation = () => {
    setTurns([]);
    setActiveResponse(null);
    setQuestion("");
    setError(null);
  };

  return (
    <div className="rounded-xl border border-primary/30 bg-card p-5 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-border/60 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <MessageSquare className="size-4 text-primary" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-foreground">
              Conversational AI Business Advisory
            </h3>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Ask any question in natural language. Multi-turn reasoning across sales, customers, forecasts, and schemes with verified calculations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {turns.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClearConversation}
              className="h-7 text-xs gap-1 text-muted-foreground hover:text-foreground"
            >
              <Trash2 className="size-3" />
              <span>Reset Chat</span>
            </Button>
          )}
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
            <Sparkles className="size-3" /> Open-Ended Reasoner
          </span>
        </div>
      </div>

      {/* Suggested Starter Prompt Chips */}
      {turns.length === 0 && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Sample Strategic Inquiries:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {SAMPLE_QUESTIONS.map((sq, idx) => (
              <button
                key={idx}
                type="button"
                disabled={isLoading}
                onClick={() => handleAsk(sq)}
                className="rounded-full border border-border/80 bg-secondary/30 px-3 py-1 text-xs text-foreground/90 hover:border-primary hover:bg-primary/10 transition-colors text-left"
              >
                {sq}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything in your own words (e.g. Why did revenue drop? What should I do about that SKU?)"
            disabled={isLoading}
            className="w-full rounded-lg border border-border/80 bg-background py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none"
          />
        </div>
        <Button
          type="submit"
          disabled={isLoading || !question.trim()}
          size="sm"
          className="gap-1.5 font-semibold shrink-0"
        >
          {isLoading ? (
            <RefreshCw className="size-4 animate-spin" />
          ) : (
            <Send className="size-4" />
          )}
          <span>{isLoading ? "Analyzing..." : "Ask Advisor"}</span>
        </Button>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAsk()}
            className="h-6 text-xs text-rose-300 hover:text-white"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Conversation Thread History */}
      {turns.length > 1 && (
        <div className="space-y-2 border-t border-border/40 pt-2">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Conversation Thread ({turns.length} turns):
          </span>
          <div className="flex flex-wrap gap-1.5">
            {turns.map((t, idx) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveResponse(t.response)}
                className={`rounded px-2.5 py-1 text-xs transition-colors border ${
                  activeResponse?.question === t.question
                    ? "border-primary bg-primary/20 text-primary font-bold"
                    : "border-border/60 bg-secondary/20 text-muted-foreground hover:bg-secondary/40"
                }`}
              >
                Turn {idx + 1}: "{t.question.slice(0, 32)}..."
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Active Advisory Result Panel */}
      {activeResponse && (
        <div className="rounded-xl border border-border/80 bg-secondary/15 p-4.5 space-y-4 pt-4 mt-2">
          {/* Query Header & Intent */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-primary/15 border border-primary/30 px-2 py-0.5 text-xs font-bold text-primary capitalize">
                {activeResponse.intent.replace(/_/g, " ")}
              </span>
              {activeResponse.query_type && (
                <span className="rounded bg-secondary/80 border border-border/60 px-2 py-0.5 text-[11px] font-medium text-foreground">
                  {activeResponse.query_type.replace(/_/g, " ")}
                </span>
              )}
              <span className="text-xs text-muted-foreground font-medium italic">
                "{activeResponse.question}"
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                <Cpu className="size-3 text-primary" />
                {activeResponse.is_ai_generated ? "Gemini Executive Reasoning" : "Deterministic Intelligence"}
              </span>
            </div>
          </div>

          {/* Trust Label, Answerability & Quality Score Banner */}
          <div className="flex flex-wrap items-center justify-between gap-2 bg-background/80 rounded-lg p-2.5 border border-border/60">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold border ${
                  activeResponse.trust_label?.includes("Verified")
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                    : activeResponse.trust_label?.includes("High Confidence")
                    ? "border-blue-500/40 bg-blue-500/10 text-blue-400"
                    : activeResponse.trust_label?.includes("Partial")
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-400"
                    : "border-purple-500/40 bg-purple-500/10 text-purple-400"
                }`}
              >
                <ShieldCheck className="size-3.5" />
                {activeResponse.trust_label || "Verified Data Grounded"}
              </span>

              {activeResponse.answerability && (
                <span className="rounded px-2 py-0.5 text-[10px] font-mono font-semibold border border-border/70 bg-secondary/60 text-muted-foreground uppercase">
                  {activeResponse.answerability.replace(/_/g, " ")}
                </span>
              )}
            </div>

            {activeResponse.quality_evaluation && (
              <div className="flex items-center gap-2 text-xs">
                <span
                  className={`inline-flex items-center gap-1 font-bold ${
                    activeResponse.quality_evaluation.validation_status === "PASSED"
                      ? "text-emerald-400"
                      : activeResponse.quality_evaluation.validation_status === "WARNING"
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}
                >
                  <Award className="size-3.5" />
                  Quality: {Math.round(activeResponse.quality_evaluation.overall_quality_score)}/100
                </span>
                <span className="text-[10px] text-muted-foreground">
                  ({activeResponse.quality_evaluation.validation_status})
                </span>
              </div>
            )}
          </div>

          {/* Tool Execution Trace Badge Row */}
          {activeResponse.tool_executions && activeResponse.tool_executions.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] bg-background/50 rounded-lg p-2 border border-border/50">
              <span className="font-semibold text-muted-foreground flex items-center gap-1">
                <Wrench className="size-3 text-primary" />
                Executed Backend Tools:
              </span>
              {activeResponse.tool_executions.map((t, idx) => (
                <span
                  key={idx}
                  className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-mono border ${
                    t.status === "ok"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : "border-rose-500/30 bg-rose-500/10 text-rose-400"
                  }`}
                >
                  <span>{t.tool}</span>
                  <span className="text-muted-foreground">({t.duration_ms}ms)</span>
                </span>
              ))}
            </div>
          )}

          {/* Direct Answer */}
          <div className="text-sm text-foreground/95 leading-relaxed space-y-2 whitespace-pre-line">
            {activeResponse.direct_answer}
          </div>

          {/* Evidence Points & Calculations */}
          {(activeResponse.evidence_points.length > 0 || activeResponse.calculations.length > 0) && (
            <div className="grid gap-3 sm:grid-cols-2 rounded-lg border border-border/60 bg-background/60 p-3.5">
              {/* Evidence */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  Verified Business Evidence
                </span>
                <ul className="space-y-1 text-xs text-foreground/90 pl-2">
                  {activeResponse.evidence_points.map((pt, i) => (
                    <li key={i} className="list-disc list-inside">
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Calculations Lineage */}
              {activeResponse.calculations.length > 0 && (
                <div className="space-y-1.5 border-t sm:border-t-0 sm:border-l border-border/50 sm:pl-3 pt-2 sm:pt-0">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                    <Calculator className="size-3.5 text-primary" />
                    Calculations & Lineage
                  </span>
                  <div className="space-y-1">
                    {activeResponse.calculations.map((c, i) => (
                      <div key={i} className="text-xs bg-secondary/30 rounded p-1.5 font-mono">
                        <div className="text-foreground font-semibold">{c.name}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {c.formula} = <span className="text-primary font-bold">{c.result}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Grounded Findings Breakdown (Source Traceability & Claim Classification) */}
          {activeResponse.grounded_findings && activeResponse.grounded_findings.length > 0 && (
            <div className="space-y-2 border border-border/60 bg-background/50 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground flex items-center gap-1.5 uppercase tracking-wider">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  Grounded Evidence Breakdown ({activeResponse.grounded_findings.length} findings)
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {activeResponse.quality_evaluation?.evidence_coverage_pct || 100}% verified coverage
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 pt-1">
                {activeResponse.grounded_findings.map((f) => (
                  <div key={f.id} className="rounded border border-border/50 bg-secondary/20 p-2 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-1">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                          f.claim_type === "VERIFIED_FACT"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : f.claim_type === "CALCULATED_RESULT"
                            ? "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                            : f.claim_type === "FORECAST_ESTIMATE"
                            ? "bg-purple-500/15 text-purple-400 border border-purple-500/30"
                            : "bg-slate-500/15 text-slate-400 border border-slate-500/30"
                        }`}
                      >
                        {f.claim_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {f.source_module}
                      </span>
                    </div>
                    <div className="text-foreground/90 font-medium text-[11px] leading-snug">
                      {f.statement}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground pt-0.5">
                      {f.time_period && <span>Period: {f.time_period}</span>}
                      {f.provenance_record_ref && (
                        <span className="font-mono text-[9px] bg-background/60 rounded px-1 border border-border/40 truncate max-w-[180px]">
                          ref: {f.provenance_record_ref}
                        </span>
                      )}
                      {f.freshness_status && (
                        <span
                          className={`px-1 rounded text-[9px] font-semibold ${
                            f.freshness_status === "FRESH"
                              ? "text-emerald-400 bg-emerald-500/10"
                              : "text-amber-400 bg-amber-500/10"
                          }`}
                        >
                          {f.freshness_status}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Situational Recommendation */}
          {activeResponse.situational_recommendations.length > 0 && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <Zap className="size-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                  Situational Strategic Recommendation
                </span>
                <span className="rounded bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                  {activeResponse.situational_recommendations[0].priority} Priority
                </span>
              </div>
              <h4 className="text-sm font-bold text-foreground">
                {activeResponse.situational_recommendations[0].title}
              </h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {activeResponse.situational_recommendations[0].situational_rationale}
              </p>

              {/* Action Steps */}
              {activeResponse.situational_recommendations[0].action_steps.length > 0 && (
                <div className="space-y-1 pt-1">
                  <span className="text-[11px] font-semibold text-foreground">Action Steps:</span>
                  <ul className="text-xs text-foreground/90 space-y-0.5 pl-4 list-decimal">
                    {activeResponse.situational_recommendations[0].action_steps.map((st, i) => (
                      <li key={i}>{st}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Cost of Delay */}
              <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded p-2">
                <span className="font-semibold">Cost of Delay: </span>
                {activeResponse.situational_recommendations[0].cost_of_delay}
              </div>
            </div>
          )}

          {/* Data Limitations & Missing Information Disclosure */}
          {activeResponse.data_limitations_and_gaps.length > 0 && (
            <div className="rounded-lg border border-border/80 bg-background/70 p-3 space-y-1 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-muted-foreground">
                <ShieldAlert className="size-3.5 text-amber-400" />
                <span>Data Boundaries & Missing Information (No Hallucination)</span>
              </div>
              <ul className="list-disc list-inside text-muted-foreground space-y-0.5 text-[11px]">
                {activeResponse.data_limitations_and_gaps.map((g, idx) => (
                  <li key={idx}>{g}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Answer Quality Feedback Options */}
          <div className="border-t border-border/40 pt-2 space-y-1.5 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted-foreground text-[11px]">Was this answer accurate & helpful?</span>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => handleFeedback("Helpful")}
                  className="rounded border border-border/60 bg-secondary/30 hover:bg-emerald-500/15 hover:text-emerald-400 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors"
                >
                  👍 Helpful
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback("Not helpful")}
                  className="rounded border border-border/60 bg-secondary/30 hover:bg-rose-500/15 hover:text-rose-400 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors"
                >
                  👎 Not helpful
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback("Incorrect information")}
                  className="rounded border border-border/60 bg-secondary/30 hover:bg-amber-500/15 hover:text-amber-400 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors"
                >
                  ⚠️ Incorrect info
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback("Need more explanation")}
                  className="rounded border border-border/60 bg-secondary/30 hover:bg-primary/15 hover:text-primary px-2 py-0.5 text-[11px] text-muted-foreground transition-colors"
                >
                  💡 Need more info
                </button>
              </div>
            </div>
            {feedbackSuccess && (
              <div className="text-emerald-400 text-xs bg-emerald-500/10 border border-emerald-500/20 rounded p-1.5 text-center">
                {feedbackSuccess}
              </div>
            )}
          </div>

          {/* Clickable Follow-up Questions */}
          {activeResponse.follow_up_questions.length > 0 && (
            <div className="space-y-1.5 border-t border-border/40 pt-2.5">
              <span className="text-[11px] font-semibold text-primary uppercase tracking-wider flex items-center gap-1">
                <HelpCircle className="size-3" />
                Suggested Follow-Up Inquiries (Click to Ask):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {activeResponse.follow_up_questions.map((fq, idx) => (
                  <button
                    key={idx}
                    type="button"
                    disabled={isLoading}
                    onClick={() => handleAsk(fq)}
                    className="flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-xs text-primary hover:bg-primary/15 transition-colors"
                  >
                    <span>{fq}</span>
                    <ArrowRight className="size-3" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

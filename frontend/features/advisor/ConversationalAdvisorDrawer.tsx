"use client";

import { useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Calculator,
  CheckCircle2,
  HelpCircle,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { smartRecommendationsService } from "@/services/smart-recommendations-service";
import type { RecommendationAskResponse } from "@/types/smart-recommendations";

const SAMPLE_QUESTIONS = [
  "Why is my revenue vulnerable to customer loss?",
  "How is the demand looking for my products next quarter?",
  "Which government scheme should I apply for with my turnover?",
  "How can I improve my repeat customer purchase rate?",
];

export function ConversationalAdvisorDrawer() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<RecommendationAskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (queryToAsk?: string) => {
    const q = (queryToAsk || question).trim();
    if (!q) return;

    setIsLoading(true);
    setError(null);
    try {
      const res = await smartRecommendationsService.askQuestion({ question: q });
      setResponse(res);
      if (queryToAsk) {
        setQuestion(queryToAsk);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to retrieve advisory answer. Please try again.");
    } finally {
      setIsLoading(false);
    }
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
            Ask any question in natural language. Reasons across sales, customers, forecasts, and schemes with verified calculations.
          </p>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
            <Sparkles className="size-3" /> Natural Language Reasoner
          </span>
        </div>
      </div>

      {/* Suggested Starter Prompt Chips */}
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

      {/* Input Composer */}
      <form
        onSubmit={e => {
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
            onChange={e => setQuestion(e.target.value)}
            placeholder="Ask anything: e.g. Why did revenue drop? Which customer is at risk? What scheme fits me?"
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
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {/* Advisory Result Panel */}
      {response && (
        <div className="rounded-xl border border-border/80 bg-secondary/15 p-4.5 space-y-4 pt-4 mt-2">
          {/* Query Header & Intent */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="rounded bg-primary/15 border border-primary/30 px-2 py-0.5 text-xs font-bold text-primary capitalize">
                {response.intent.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-muted-foreground font-medium italic">
                "{response.question}"
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground">
              {response.is_ai_generated ? "Gemini Reasoning" : "Deterministic Engine"}
            </span>
          </div>

          {/* Direct Answer */}
          <div className="text-sm text-foreground/95 leading-relaxed space-y-2 whitespace-pre-line">
            {response.direct_answer}
          </div>

          {/* Evidence Points & Calculations */}
          {(response.evidence_points.length > 0 || response.calculations.length > 0) && (
            <div className="grid gap-3 sm:grid-cols-2 rounded-lg border border-border/60 bg-background/60 p-3.5">
              {/* Evidence */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <CheckCircle2 className="size-3.5 text-emerald-400" />
                  Verified Business Evidence
                </span>
                <ul className="space-y-1 text-xs text-foreground/90 pl-2">
                  {response.evidence_points.map((pt, i) => (
                    <li key={i} className="list-disc list-inside">
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Calculations Lineage */}
              {response.calculations.length > 0 && (
                <div className="space-y-1.5 border-t sm:border-t-0 sm:border-l border-border/50 sm:pl-3 pt-2 sm:pt-0">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                    <Calculator className="size-3.5 text-primary" />
                    Calculations & Lineage
                  </span>
                  <div className="space-y-1">
                    {response.calculations.map((c, i) => (
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

          {/* Situational Recommendation */}
          {response.situational_recommendations.length > 0 && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3.5 space-y-2">
              <div className="flex items-center gap-2">
                <Zap className="size-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                  Situational Strategic Recommendation
                </span>
                <span className="rounded bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
                  {response.situational_recommendations[0].priority} Priority
                </span>
              </div>
              <h4 className="text-sm font-bold text-foreground">
                {response.situational_recommendations[0].title}
              </h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {response.situational_recommendations[0].situational_rationale}
              </p>

              {/* Action Steps */}
              {response.situational_recommendations[0].action_steps.length > 0 && (
                <div className="space-y-1 pt-1">
                  <span className="text-[11px] font-semibold text-foreground">Action Steps:</span>
                  <ul className="text-xs text-foreground/90 space-y-0.5 pl-4 list-decimal">
                    {response.situational_recommendations[0].action_steps.map((st, i) => (
                      <li key={i}>{st}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Cost of Delay */}
              <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded p-2">
                <span className="font-semibold">Cost of Delay: </span>
                {response.situational_recommendations[0].cost_of_delay}
              </div>
            </div>
          )}

          {/* Data Limitations & Missing Information Disclosure */}
          {response.data_limitations_and_gaps.length > 0 && (
            <div className="rounded-lg border border-border/80 bg-background/70 p-3 space-y-1 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-muted-foreground">
                <ShieldAlert className="size-3.5 text-amber-400" />
                <span>Data Boundaries & Missing Information (No Hallucination)</span>
              </div>
              <ul className="list-disc list-inside text-muted-foreground space-y-0.5 text-[11px]">
                {response.data_limitations_and_gaps.map((g, idx) => (
                  <li key={idx}>{g}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Clickable Follow-up Questions */}
          {response.follow_up_questions.length > 0 && (
            <div className="space-y-1.5 border-t border-border/40 pt-2.5">
              <span className="text-[11px] font-semibold text-primary uppercase tracking-wider flex items-center gap-1">
                <HelpCircle className="size-3" />
                Suggested Follow-Up Inquiries (Click to Ask):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {response.follow_up_questions.map((fq, idx) => (
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

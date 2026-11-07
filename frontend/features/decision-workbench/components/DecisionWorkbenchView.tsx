"use client";

import { useState, useEffect } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Clock,
  Database,
  HelpCircle,
  History,
  Info,
  Lightbulb,
  Plus,
  Scale,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/common/PageHeader";
import { useLanguage } from "@/context/language-context";
import { formatINR } from "@/lib/formatters";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import {
  decisionWorkbenchService,
  type DecisionEvaluateResponse,
  type DecisionOptionEvaluation,
  type DecisionOut,
} from "@/services";

interface DecisionTemplate {
  type:
    | "offer_discount"
    | "increase_price"
    | "customer_focus"
    | "expand_product_range"
    | "reduce_expenses"
    | "test_sales_channel"
    | "custom";
  icon: string;
  label: string;
  defaultObjective: string;
}

const TEMPLATES: DecisionTemplate[] = [
  {
    type: "offer_discount",
    icon: "🏷️",
    label: "Offer a Discount",
    defaultObjective: "Should I offer a volume discount to boost orders without sacrificing gross profit?",
  },
  {
    type: "increase_price",
    icon: "📈",
    label: "Increase Product Prices",
    defaultObjective: "Should I increase prices on my top-selling lines to protect margins against inflation?",
  },
  {
    type: "customer_focus",
    icon: "👥",
    label: "Retention vs. Acquisition",
    defaultObjective: "Should I allocate marketing capital to existing customer retention or new customer acquisition?",
  },
  {
    type: "expand_product_range",
    icon: "📦",
    label: "Expand Product Range",
    defaultObjective: "Should I expand into an adjacent product category to increase average basket size?",
  },
  {
    type: "reduce_expenses",
    icon: "✂️",
    label: "Reduce Operating Costs",
    defaultObjective: "Should I reduce discretionary marketing and operational overhead to extend cash runway?",
  },
  {
    type: "test_sales_channel",
    icon: "🚀",
    label: "Test New Sales Channel",
    defaultObjective: "Should I test an online direct-to-consumer channel alongside existing wholesale distribution?",
  },
  {
    type: "custom",
    icon: "✏️",
    label: "Custom Decision",
    defaultObjective: "Evaluate a custom strategic decision with verified business evidence and risk models.",
  },
];

export function DecisionWorkbenchView() {
  const { language } = useLanguage();
  const [selectedTemplate, setSelectedTemplate] = useState<DecisionTemplate>(TEMPLATES[0]);
  const [objective, setObjective] = useState<string>(TEMPLATES[0].defaultObjective);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [evaluation, setEvaluation] = useState<DecisionEvaluateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Decision Recording State
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [rationale, setRationale] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  // History State
  const [decisions, setDecisions] = useState<DecisionOut[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [showHistory, setShowHistory] = useState<boolean>(false);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await decisionWorkbenchService.listDecisions();
      setDecisions(res.items);
    } catch {
      // Non-blocking for evaluation flow
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  const handleTemplateSelect = (tmpl: DecisionTemplate) => {
    setSelectedTemplate(tmpl);
    setObjective(tmpl.defaultObjective);
    setEvaluation(null);
    setSelectedOptionId(null);
    setRationale("");
    setSaveSuccess(false);
  };

  const handleEvaluate = async () => {
    if (!objective.trim()) return;
    setEvaluating(true);
    setError(null);
    setSaveSuccess(false);
    try {
      const res = await decisionWorkbenchService.evaluateDecision({
        decision_type: selectedTemplate.type,
        objective: objective.trim(),
      });
      setEvaluation(res);
      setSelectedOptionId(res.recommended_option_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate decision options.");
    } finally {
      setEvaluating(false);
    }
  };

  const handleSaveDecision = async (status: "Draft" | "Decided") => {
    if (!evaluation) return;
    setSaving(true);
    setError(null);
    try {
      const selectedOpt = evaluation.options.find((o) => o.option_id === selectedOptionId);
      await decisionWorkbenchService.createDecision({
        decision_type: evaluation.decision_type,
        title: `${selectedTemplate.label}: ${objective.slice(0, 80)}`,
        objective: evaluation.objective,
        baseline_snapshot: evaluation.baseline_snapshot,
        options: evaluation.options,
        selected_option_id: selectedOptionId,
        selected_option_title: selectedOpt ? selectedOpt.title : null,
        decision_rationale: rationale.trim() || null,
        status: status,
      });
      setSaveSuccess(true);
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save decision.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <PageHeader
          title="Business Decision Workbench"
          description="Evaluate strategic choices with verified business evidence, calculated financial models, and transparent risk assessments."
        />
        <Button
          variant={showHistory ? "default" : "outline"}
          onClick={() => setShowHistory(!showHistory)}
          className="flex items-center gap-2 self-start"
        >
          <History className="h-4 w-4" />
          {showHistory ? "Back to Workbench" : `Decision History (${decisions.length})`}
        </Button>
      </div>

      {showHistory ? (
        /* History View */
        <div className="space-y-4">
          <h2 className="text-xl font-bold tracking-tight">Recorded Decisions & Outcomes</h2>
          {decisions.length === 0 ? (
            <EmptyState
              title="No decisions recorded yet"
              description="Use the Decision Workbench to evaluate strategic options and record choices for your business."
            />
          ) : (
            <div className="grid gap-4">
              {decisions.map((d) => (
                <div
                  key={d.id}
                  className="rounded-xl border border-border bg-card p-6 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground text-lg">{d.title}</span>
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-primary/10 text-primary">
                        {d.status}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(d.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>

                  <p className="mt-3 text-sm text-muted-foreground">
                    <strong className="text-foreground">Objective:</strong> {d.objective}
                  </p>

                  {d.selected_option_title && (
                    <div className="mt-4 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 p-3 border border-emerald-200 dark:border-emerald-800/40">
                      <div className="text-xs font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider flex items-center gap-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Selected Strategic Option
                      </div>
                      <div className="mt-1 font-semibold text-emerald-950 dark:text-emerald-100 text-sm">
                        {d.selected_option_title}
                      </div>
                      {d.decision_rationale && (
                        <p className="mt-1 text-xs text-emerald-900/80 dark:text-emerald-200/70 italic">
                          "{d.decision_rationale}"
                        </p>
                      )}
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border/40">
                    <span>Baseline Revenue: ₹{Number(d.baseline_snapshot?.annual_revenue_inr || 0).toLocaleString("en-IN")}</span>
                    <span>Review Status: <strong className="text-foreground">{d.review_status}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Evaluation Workbench */
        <div className="space-y-6">
          {/* Template Selector Grid */}
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
              1. Select a Strategic Decision Type
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {TEMPLATES.map((tmpl) => {
                const isSelected = selectedTemplate.type === tmpl.type;
                return (
                  <button
                    key={tmpl.type}
                    type="button"
                    onClick={() => handleTemplateSelect(tmpl)}
                    className={`flex flex-col items-center justify-center p-3 rounded-lg border text-center transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 text-primary font-semibold shadow-sm ring-1 ring-primary"
                        : "border-border bg-card hover:bg-muted/50 text-foreground"
                    }`}
                  >
                    <span className="text-2xl mb-1.5">{tmpl.icon}</span>
                    <span className="text-xs leading-snug">{tmpl.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Objective Input */}
            <div className="pt-2 space-y-2">
              <label htmlFor="objective-input" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                2. Specify Decision Objective
              </label>
              <textarea
                id="objective-input"
                rows={2}
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder="Describe your business objective clearly..."
                className="w-full rounded-lg border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>

            <div className="flex justify-end pt-1">
              <Button
                onClick={handleEvaluate}
                disabled={evaluating || !objective.trim()}
                className="flex items-center gap-2"
              >
                {evaluating ? (
                  <>Evaluating Options...</>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Evaluate Decision Options
                  </>
                )}
              </Button>
            </div>
          </div>

          {error && (
            <ErrorState
              title="Evaluation Error"
              description={error}
              actionLabel="Try again"
              onAction={handleEvaluate}
            />
          )}

          {evaluating && (
            <div className="space-y-4">
              <LoadingSkeleton rows={3} variant="card" />
            </div>
          )}

          {evaluation && !evaluating && (
            <div className="space-y-8 animate-in fade-in-50 duration-300">
              {/* Baseline Summary Strip */}
              <div className="rounded-xl border border-border/80 bg-muted/40 p-5">
                <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center justify-between pb-3 border-b border-border/40">
                  <span className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-primary" />
                    Verified Business Baseline
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
                    <CheckCircle2 className="h-3 w-3" />
                    {evaluation.data_freshness}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4 pt-3 text-sm">
                  <div>
                    <span className="text-xs text-muted-foreground block">Revenue</span>
                    <strong className="text-foreground">
                      ₹{Number(evaluation.baseline_snapshot.annual_revenue_inr || 0).toLocaleString("en-IN")}
                    </strong>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block">Avg Order Value</span>
                    <strong className="text-foreground">
                      ₹{Number(evaluation.baseline_snapshot.average_order_value_inr || 0).toLocaleString("en-IN")}
                    </strong>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block">Orders Sampled</span>
                    <strong className="text-foreground">
                      {evaluation.baseline_snapshot.total_orders ?? 0}
                    </strong>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block">Repeat Rate</span>
                    <strong className="text-foreground">
                      {evaluation.baseline_snapshot.repeat_customer_rate_pct ?? 0}%
                    </strong>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block">Top Product</span>
                    <strong className="text-foreground truncate block">
                      {String(evaluation.baseline_snapshot.top_product_name || "N/A")}
                    </strong>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground block">Health Score</span>
                    <strong className="text-foreground">
                      {evaluation.baseline_snapshot.overall_health_score ?? 0}/100
                    </strong>
                  </div>
                </div>
              </div>

              {/* AI Executive Summary */}
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-5">
                <div className="flex items-center gap-2 text-primary font-bold text-sm mb-2">
                  <Zap className="h-4 w-4" />
                  Executive Synthesis & Trade-Off Analysis
                </div>
                <p className="text-sm leading-relaxed text-foreground/90">
                  {evaluation.ai_executive_summary}
                </p>
              </div>

              {/* Evaluated Options Comparison Cards */}
              <div className="space-y-4">
                <h3 className="text-lg font-bold tracking-tight flex items-center gap-2">
                  <Scale className="h-5 w-5 text-primary" />
                  Compare Evaluated Strategic Options
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {evaluation.options.map((opt) => {
                    const isSelected = selectedOptionId === opt.option_id;
                    const isRecommended = opt.option_id === evaluation.recommended_option_id;
                    return (
                      <div
                        key={opt.option_id}
                        className={`rounded-xl border flex flex-col justify-between p-5 transition-all ${
                          isSelected
                            ? "border-primary bg-card ring-2 ring-primary shadow-md"
                            : "border-border bg-card hover:border-border/80 shadow-sm"
                        }`}
                      >
                        <div className="space-y-4">
                          {/* Option Header */}
                          <div>
                            {isRecommended && (
                              <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 mb-2">
                                <Sparkles className="h-3 w-3" /> Recommended
                              </span>
                            )}
                            <h4 className="font-bold text-base text-foreground leading-snug">
                              {opt.title}
                            </h4>
                            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                              {opt.description}
                            </p>
                          </div>

                          {/* Financial Impact Projection */}
                          <div className="rounded-lg bg-muted/60 p-3 border border-border/60 space-y-1.5">
                            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                              Estimated Impact
                            </span>
                            {opt.estimated_impact.has_calculation_inputs ? (
                              <div className="grid grid-cols-2 gap-2 text-xs">
                                <div>
                                  <span className="text-muted-foreground text-[10px] block">Revenue Delta</span>
                                  <strong className={opt.estimated_impact.revenue_delta_inr && opt.estimated_impact.revenue_delta_inr > 0 ? "text-emerald-700 dark:text-emerald-400" : "text-foreground"}>
                                    {opt.estimated_impact.revenue_delta_inr !== null ? `₹${opt.estimated_impact.revenue_delta_inr.toLocaleString("en-IN")}` : "0"}
                                    {opt.estimated_impact.revenue_delta_pct ? ` (+${opt.estimated_impact.revenue_delta_pct}%)` : ""}
                                  </strong>
                                </div>
                                <div>
                                  <span className="text-muted-foreground text-[10px] block">Margin Delta</span>
                                  <strong className={opt.estimated_impact.margin_delta_pct && opt.estimated_impact.margin_delta_pct < 0 ? "text-amber-700 dark:text-amber-400" : "text-foreground"}>
                                    {opt.estimated_impact.margin_delta_pct !== null ? `${opt.estimated_impact.margin_delta_pct > 0 ? "+" : ""}${opt.estimated_impact.margin_delta_pct}% pts` : "0%"}
                                  </strong>
                                </div>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground italic">
                                Missing transaction inputs to project financial delta accurately.
                              </p>
                            )}
                            <p className="text-[10px] text-muted-foreground/80 italic pt-1 border-t border-border/40">
                              *{opt.estimated_impact.disclaimer}
                            </p>
                          </div>

                          {/* Observed Evidence */}
                          <div className="space-y-1.5">
                            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                              Supporting Facts
                            </span>
                            <ul className="text-xs space-y-1">
                              {opt.supporting_evidence.map((ev, i) => (
                                <li key={i} className="flex justify-between items-center text-muted-foreground">
                                  <span>{ev.metric}:</span>
                                  <strong className="text-foreground">{String(ev.value)} {ev.unit}</strong>
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* Benefits & Risks */}
                          <div className="space-y-2 pt-2 border-t border-border/40 text-xs">
                            <div>
                              <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                                <TrendingUp className="h-3 w-3" /> Key Benefits:
                              </span>
                              <ul className="list-disc list-inside mt-0.5 text-muted-foreground space-y-0.5">
                                {opt.potential_benefits.slice(0, 2).map((b, i) => (
                                  <li key={i}>{b}</li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <span className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" /> Execution Risks:
                              </span>
                              <ul className="list-disc list-inside mt-0.5 text-muted-foreground space-y-0.5">
                                {opt.potential_risks.slice(0, 2).map((r, i) => (
                                  <li key={i}>{r}</li>
                                ))}
                              </ul>
                            </div>
                          </div>

                          {/* Missing Info Warning */}
                          {opt.missing_information.length > 0 && (
                            <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-2 text-[11px] text-amber-900 dark:text-amber-200/80 border border-amber-200 dark:border-amber-800/40">
                              <span className="font-bold flex items-center gap-1">
                                <HelpCircle className="h-3 w-3" /> Missing Data:
                              </span>
                              <span className="block mt-0.5">{opt.missing_information[0]}</span>
                            </div>
                          )}
                        </div>

                        {/* Select Button */}
                        <div className="pt-4 mt-4 border-t border-border/40">
                          <Button
                            type="button"
                            variant={isSelected ? "default" : "outline"}
                            className="w-full text-xs"
                            onClick={() => setSelectedOptionId(opt.option_id)}
                          >
                            {isSelected ? "Selected Option" : "Select This Option"}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Decision Recording Section */}
              <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-foreground">
                  3. Record Your Business Decision
                </h3>
                <p className="text-xs text-muted-foreground">
                  Record your rationale and chosen path to evaluate observed sales outcomes over the next 30 days.
                </p>

                <div className="space-y-2">
                  <label htmlFor="rationale-input" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Decision Rationale (Why this choice?)
                  </label>
                  <textarea
                    id="rationale-input"
                    rows={2}
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                    placeholder="e.g., Implementing the 5% targeted discount to test bulk elasticity before seasonal peak..."
                    className="w-full rounded-lg border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  {saveSuccess ? (
                    <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4" />
                      Decision successfully recorded into workspace!
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      Selected:{" "}
                      <strong>
                        {evaluation.options.find((o) => o.option_id === selectedOptionId)?.title || "None selected"}
                      </strong>
                    </span>
                  )}

                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={saving || !selectedOptionId}
                      onClick={() => handleSaveDecision("Draft")}
                    >
                      Save as Draft
                    </Button>
                    <Button
                      type="button"
                      disabled={saving || !selectedOptionId}
                      onClick={() => handleSaveDecision("Decided")}
                      className="flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Confirm & Record Decision
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

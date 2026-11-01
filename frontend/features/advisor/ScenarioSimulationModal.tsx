"use client";

import { useState } from "react";
import {
  AlertCircle,
  Calculator,
  ChevronRight,
  Info,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { smartRecommendationsService } from "@/services/smart-recommendations-service";
import type {
  ScenarioSimulationRequest,
  ScenarioSimulationResponse,
} from "@/types/smart-recommendations";

interface ScenarioSimulationModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialData?: ScenarioSimulationResponse | null;
}

export function ScenarioSimulationModal({
  isOpen,
  onClose,
  initialData,
}: ScenarioSimulationModalProps) {
  const [params, setParams] = useState<ScenarioSimulationRequest>({
    sales_growth_pct: 10,
    repeat_customer_rate_improvement_pct: 15,
    expense_reduction_pct: 5,
    concentration_reduction_pct: 10,
  });

  const [result, setResult] = useState<ScenarioSimulationResponse | null>(initialData || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSimulate = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await smartRecommendationsService.simulateScenario(params);
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to execute scenario simulation.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-3xl rounded-xl border border-border bg-card p-6 shadow-2xl space-y-5 my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/60 pb-3">
          <div className="flex items-center gap-2">
            <Calculator className="size-5 text-primary" />
            <div>
              <h3 className="text-lg font-bold text-foreground">
                What-If Business Impact Simulator
              </h3>
              <p className="text-xs text-muted-foreground">
                Test hypothetical growth and cost interventions grounded in your verified baseline.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Sliders Grid */}
        <div className="grid gap-4 sm:grid-cols-2 rounded-lg border border-border/60 bg-secondary/20 p-4">
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-foreground">Monthly Sales Growth</span>
              <span className="text-primary font-mono">{params.sales_growth_pct > 0 ? `+${params.sales_growth_pct}%` : `${params.sales_growth_pct}%`}</span>
            </div>
            <input
              type="range"
              min="-20"
              max="50"
              step="5"
              value={params.sales_growth_pct}
              onChange={e => setParams(p => ({ ...p, sales_growth_pct: Number(e.target.value) }))}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>-20% (Contraction)</span>
              <span>+50% (Rapid Expansion)</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-foreground">Repeat Customer Retention Lift</span>
              <span className="text-emerald-400 font-mono">+{params.repeat_customer_rate_improvement_pct}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="40"
              step="5"
              value={params.repeat_customer_rate_improvement_pct}
              onChange={e => setParams(p => ({ ...p, repeat_customer_rate_improvement_pct: Number(e.target.value) }))}
              className="w-full accent-emerald-500"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>0% (Status Quo)</span>
              <span>+40% (Active Loyalty Program)</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-foreground">Operating Expense Reduction</span>
              <span className="text-amber-400 font-mono">-{params.expense_reduction_pct}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="25"
              step="1"
              value={params.expense_reduction_pct}
              onChange={e => setParams(p => ({ ...p, expense_reduction_pct: Number(e.target.value) }))}
              className="w-full accent-amber-500"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>0%</span>
              <span>-25% (Overhead Lean Program)</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-foreground">Top-Customer Dependency Dilution</span>
              <span className="text-cyan-400 font-mono">-{params.concentration_reduction_pct}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="40"
              step="5"
              value={params.concentration_reduction_pct}
              onChange={e => setParams(p => ({ ...p, concentration_reduction_pct: Number(e.target.value) }))}
              className="w-full accent-cyan-500"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>0% (Concentrated)</span>
              <span>-40% (Diversified)</span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={handleSimulate}
            disabled={isLoading}
            className="gap-2 font-semibold"
          >
            <RefreshCw className={`size-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>{isLoading ? "Simulating..." : "Calculate Projected Outcome"}</span>
          </Button>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {/* Results Display */}
        {result && (
          <div className="space-y-4 border-t border-border/60 pt-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
                <span className="text-[11px] font-medium text-muted-foreground uppercase">
                  Baseline Revenue
                </span>
                <div className="text-lg font-bold text-foreground mt-0.5">
                  ₹{result.baseline_revenue.toLocaleString("en-IN")}
                </div>
              </div>

              <div className="rounded-lg border border-primary/30 bg-primary/10 p-3">
                <span className="text-[11px] font-bold text-primary uppercase">
                  Projected Revenue
                </span>
                <div className="text-lg font-bold text-primary mt-0.5">
                  ₹{result.projected_revenue.toLocaleString("en-IN")}
                </div>
              </div>

              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
                <span className="text-[11px] font-bold text-emerald-400 uppercase">
                  Est. Profit Change
                </span>
                <div className="text-lg font-bold text-emerald-400 mt-0.5">
                  +₹{result.estimated_gross_profit_change.toLocaleString("en-IN")}
                </div>
              </div>

              <div className="rounded-lg border border-border/60 bg-secondary/30 p-3">
                <span className="text-[11px] font-medium text-muted-foreground uppercase">
                  Scenario Status
                </span>
                <div className="text-sm font-semibold text-foreground mt-1">
                  Deterministic
                </div>
              </div>
            </div>

            {/* Detailed Metric Lineage */}
            <div className="space-y-2">
              <span className="text-xs font-bold uppercase tracking-wider text-foreground">
                Formula Lineage & Sensitivity Breakdown
              </span>
              <div className="space-y-1.5">
                {result.metrics.map((m, idx) => (
                  <div
                    key={idx}
                    className="flex flex-col sm:flex-row sm:items-center sm:justify-between rounded bg-secondary/20 border border-border/50 p-2 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-foreground">{m.metric_name}: </span>
                      <span className="text-muted-foreground">{m.formula_explanation}</span>
                    </div>
                    <div className="font-mono text-foreground font-medium sm:text-right mt-1 sm:mt-0">
                      {m.unit} {m.projected_value.toLocaleString("en-IN")} ({m.delta_value >= 0 ? `+${m.delta_value.toLocaleString("en-IN")}` : m.delta_value.toLocaleString("en-IN")})
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Takeaways */}
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-1 text-xs">
              <span className="font-semibold text-primary">Strategic Takeaways:</span>
              <ul className="list-disc list-inside space-y-0.5 text-foreground/90">
                {result.key_takeaways.map((t, idx) => (
                  <li key={idx}>{t}</li>
                ))}
              </ul>
            </div>

            {/* Boundary Disclaimer */}
            <div className="flex items-start gap-2 text-[11px] text-muted-foreground/80 pt-1">
              <Info className="size-3.5 shrink-0 text-muted-foreground mt-0.5" />
              <span>{result.projection_disclaimer}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import {
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  ShieldAlert,
  Sparkles,
  Sliders,
  DollarSign,
  Layers,
  Save,
  Trash2,
  GitCompare,
  Info,
  Calendar,
  Clock,
  CheckCircle2,
  ArrowRight,
  Database,
  Building,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  whatIfScenarioService,
  ScenarioType,
  SimulationResult,
  ScenarioOut,
  ScenarioCaseResult,
  ScenarioCompareResponse,
} from "@/services";

interface PresetTemplate {
  type: ScenarioType;
  title: string;
  description: string;
  icon: React.ReactNode;
  defaults: {
    sales_volume_delta_pct?: number;
    price_delta_pct?: number;
    cogs_delta_pct?: number;
    opex_delta_inr?: number;
    dso_stretch_days?: number;
    lost_customer_revenue_inr?: number;
  };
}

const PRESETS: PresetTemplate[] = [
  {
    type: "sales_drop",
    title: "Demand Shock (-15%)",
    description: "Simulate a 15% reduction in overall order volume.",
    icon: <TrendingDown className="h-5 w-5 text-rose-500" />,
    defaults: { sales_volume_delta_pct: -15.0, price_delta_pct: 0, cogs_delta_pct: 0, opex_delta_inr: 0, dso_stretch_days: 0 },
  },
  {
    type: "supplier_cost_increase",
    title: "Supplier Price Spike (+10%)",
    description: "Simulate raw material or vendor cost inflation of 10%.",
    icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
    defaults: { sales_volume_delta_pct: 0, price_delta_pct: 0, cogs_delta_pct: 10.0, opex_delta_inr: 0, dso_stretch_days: 0 },
  },
  {
    type: "customer_churn",
    title: "Key Account Departure",
    description: "Simulate losing your single largest customer.",
    icon: <ShieldAlert className="h-5 w-5 text-purple-500" />,
    defaults: { sales_volume_delta_pct: 0, price_delta_pct: 0, cogs_delta_pct: 0, opex_delta_inr: 0, dso_stretch_days: 0 },
  },
  {
    type: "hiring_expansion",
    title: "Hire Salesperson (+₹45k/mo)",
    description: "Simulate adding sales headcount with salary overhead.",
    icon: <Building className="h-5 w-5 text-blue-500" />,
    defaults: { sales_volume_delta_pct: 5.0, price_delta_pct: 0, cogs_delta_pct: 0, opex_delta_inr: 45000, dso_stretch_days: 0 },
  },
  {
    type: "price_elasticity",
    title: "Price Hike (+5%) & Dip (-3%)",
    description: "Test raising prices with expected volume elasticity.",
    icon: <TrendingUp className="h-5 w-5 text-emerald-500" />,
    defaults: { sales_volume_delta_pct: -3.0, price_delta_pct: 5.0, cogs_delta_pct: 0, opex_delta_inr: 0, dso_stretch_days: 0 },
  },
  {
    type: "collection_delay",
    title: "Stretched DSO (+30 Days)",
    description: "Simulate delayed buyer payments locking up cash.",
    icon: <Clock className="h-5 w-5 text-orange-500" />,
    defaults: { sales_volume_delta_pct: 0, price_delta_pct: 0, cogs_delta_pct: 0, opex_delta_inr: 0, dso_stretch_days: 30 },
  },
];

export function WhatIfScenarioSimulatorView() {
  const [selectedType, setSelectedType] = useState<ScenarioType>("sales_drop");
  const [title, setTitle] = useState("Q3 Demand Contraction");
  const [volumeDelta, setVolumeDelta] = useState(-15.0);
  const [priceDelta, setPriceDelta] = useState(0.0);
  const [cogsDelta, setCogsDelta] = useState(0.0);
  const [opexDelta, setOpexDelta] = useState(0.0);
  const [dsoStretch, setDsoStretch] = useState(0);

  const [simulating, setSimulating] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Persistence State
  const [savedScenarios, setSavedScenarios] = useState<ScenarioOut[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Comparison State
  const [selectedForCompare, setSelectedForCompare] = useState<number[]>([]);
  const [comparisonResult, setComparisonResult] = useState<ScenarioCompareResponse | null>(null);
  const [comparing, setComparing] = useState(false);

  // Load saved scenarios on mount
  useEffect(() => {
    loadSavedScenarios();
  }, []);

  const loadSavedScenarios = async () => {
    try {
      setLoadingSaved(true);
      const res = await whatIfScenarioService.list();
      setSavedScenarios(res.items);
    } catch {
      // Ignored for initial load
    } finally {
      setLoadingSaved(false);
    }
  };

  const handleApplyPreset = (preset: PresetTemplate) => {
    setSelectedType(preset.type);
    setTitle(preset.title);
    setVolumeDelta(preset.defaults.sales_volume_delta_pct ?? 0);
    setPriceDelta(preset.defaults.price_delta_pct ?? 0);
    setCogsDelta(preset.defaults.cogs_delta_pct ?? 0);
    setOpexDelta(preset.defaults.opex_delta_inr ?? 0);
    setDsoStretch(preset.defaults.dso_stretch_days ?? 0);
  };

  const handleSimulate = async () => {
    try {
      setSimulating(true);
      setError(null);
      setSaveSuccess(false);
      const sim = await whatIfScenarioService.simulate({
        title,
        parameters: {
          scenario_type: selectedType,
          sales_volume_delta_pct: volumeDelta,
          price_delta_pct: priceDelta,
          cogs_delta_pct: cogsDelta,
          opex_delta_inr: opexDelta,
          dso_stretch_days: dsoStretch,
        },
      });
      setResult(sim);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run simulation");
    } finally {
      setSimulating(false);
    }
  };

  const handleSaveScenario = async () => {
    if (!result) return;
    try {
      const saved = await whatIfScenarioService.save({
        title,
        scenario_type: selectedType,
        parameters: {
          scenario_type: selectedType,
          sales_volume_delta_pct: volumeDelta,
          price_delta_pct: priceDelta,
          cogs_delta_pct: cogsDelta,
          opex_delta_inr: opexDelta,
          dso_stretch_days: dsoStretch,
        },
      });
      setSavedScenarios([saved, ...savedScenarios.filter((s) => s.id !== saved.id)]);
      setSaveSuccess(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save scenario");
    }
  };

  const handleDeleteScenario = async (id: number) => {
    try {
      await whatIfScenarioService.delete(id);
      setSavedScenarios(savedScenarios.filter((s) => s.id !== id));
      setSelectedForCompare(selectedForCompare.filter((cId) => cId !== id));
      if (comparisonResult) setComparisonResult(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete scenario");
    }
  };

  const handleToggleCompare = (id: number) => {
    if (selectedForCompare.includes(id)) {
      setSelectedForCompare(selectedForCompare.filter((i) => i !== id));
    } else {
      if (selectedForCompare.length >= 3) {
        setSelectedForCompare([selectedForCompare[1], selectedForCompare[2], id]);
      } else {
        setSelectedForCompare([...selectedForCompare, id]);
      }
    }
  };

  const handleCompare = async () => {
    if (selectedForCompare.length < 2) return;
    try {
      setComparing(true);
      const res = await whatIfScenarioService.compare(selectedForCompare);
      setComparisonResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setComparing(false);
    }
  };

  const handleReloadSaved = (scenario: ScenarioOut) => {
    setTitle(scenario.title);
    setSelectedType(scenario.scenario_type as ScenarioType);
    setVolumeDelta(scenario.parameters.sales_volume_delta_pct ?? 0);
    setPriceDelta(scenario.parameters.price_delta_pct ?? 0);
    setCogsDelta(scenario.parameters.cogs_delta_pct ?? 0);
    setOpexDelta(scenario.parameters.opex_delta_inr ?? 0);
    setDsoStretch(scenario.parameters.dso_stretch_days ?? 0);
    setResult(scenario.projection_result);
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="p-2 rounded-lg bg-primary/10 text-primary border border-primary/20">
              <Sliders className="h-5 w-5" />
            </span>
            <Badge variant="outline" className="border-primary/30 text-primary text-xs">
              Phase 6.19 Extension
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
            What-If Scenario Simulator
          </h1>
          <p className="text-muted-foreground text-sm mt-1 max-w-2xl leading-relaxed">
            Test hypothetical shocks, cost revisions, and pricing elasticity before committing real capital.
            All estimates are grounded in observed business baselines with deterministic calculation authority.
          </p>
        </div>

        {savedScenarios.length > 0 && (
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="px-3 py-1 text-xs">
              {savedScenarios.length} Saved Scenarios
            </Badge>
          </div>
        )}
      </div>

      {/* Mandatory Scenario Disclaimer */}
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-3 shadow-sm">
        <Info className="h-4 w-4 shrink-0 text-amber-500" />
        <span className="leading-relaxed font-medium">
          <strong>Mandatory Notice:</strong> Illustrative scenario estimate — not a guaranteed prediction.
          Projections model deterministic financial relationships based on observed sales and benchmark parameters.
        </span>
      </div>

      {/* Preset Shock Templates */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            1. Select Scenario Preset or Customize Levers
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {PRESETS.map((p) => {
            const isSelected = selectedType === p.type && title === p.title;
            return (
              <button
                key={p.title}
                type="button"
                onClick={() => handleApplyPreset(p)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "border-primary bg-primary/10 shadow-sm ring-1 ring-primary"
                    : "border-border/80 bg-card hover:border-primary/50 hover:bg-muted/40"
                }`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 rounded-lg bg-background border border-border/60">
                    {p.icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">{p.title}</h3>
                    <span className="text-[11px] text-muted-foreground">{p.type.replace("_", " ")}</span>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{p.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Levers & Parameters Controls */}
      <div className="rounded-xl border border-border/80 bg-card p-6 space-y-6 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">
              Scenario Title
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q3 Monsoon Contraction"
              className="text-sm font-medium"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-muted-foreground uppercase block mb-1.5">
              Scenario Category
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value as ScenarioType)}
              className="w-full text-sm bg-background border border-input rounded-md px-3 py-2 text-foreground"
            >
              <option value="sales_drop">Sales Drop Shock</option>
              <option value="supplier_cost_increase">Supplier Cost Increase</option>
              <option value="customer_churn">Customer Churn</option>
              <option value="hiring_expansion">Hiring / OpEx Expansion</option>
              <option value="price_elasticity">Price Elasticity Test</option>
              <option value="collection_delay">Payment Collection Delay (DSO)</option>
              <option value="custom">Custom Multi-Variable Scenario</option>
            </select>
          </div>
        </div>

        {/* Levers Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 pt-4 border-t border-border/60">
          <div>
            <div className="flex justify-between text-xs mb-1 font-semibold">
              <span className="text-muted-foreground">Volume Change</span>
              <span className={volumeDelta < 0 ? "text-rose-500 font-bold" : "text-foreground"}>
                {volumeDelta > 0 ? `+${volumeDelta}%` : `${volumeDelta}%`}
              </span>
            </div>
            <input
              type="range"
              min="-80"
              max="100"
              step="1"
              value={volumeDelta}
              onChange={(e) => setVolumeDelta(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground">Sales quantity delta</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1 font-semibold">
              <span className="text-muted-foreground">Price Change</span>
              <span className={priceDelta > 0 ? "text-emerald-500 font-bold" : "text-foreground"}>
                {priceDelta > 0 ? `+${priceDelta}%` : `${priceDelta}%`}
              </span>
            </div>
            <input
              type="range"
              min="-50"
              max="100"
              step="1"
              value={priceDelta}
              onChange={(e) => setPriceDelta(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground">Selling price revision</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1 font-semibold">
              <span className="text-muted-foreground">COGS Inflation</span>
              <span className={cogsDelta > 0 ? "text-amber-500 font-bold" : "text-foreground"}>
                {cogsDelta > 0 ? `+${cogsDelta}%` : `${cogsDelta}%`}
              </span>
            </div>
            <input
              type="range"
              min="-30"
              max="100"
              step="1"
              value={cogsDelta}
              onChange={(e) => setCogsDelta(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground">Supplier price shift</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1 font-semibold">
              <span className="text-muted-foreground">Monthly OpEx</span>
              <span className="text-foreground">
                {opexDelta >= 0 ? `+₹${opexDelta.toLocaleString("en-IN")}` : `-₹${Math.abs(opexDelta).toLocaleString("en-IN")}`}
              </span>
            </div>
            <input
              type="number"
              step="5000"
              value={opexDelta}
              onChange={(e) => setOpexDelta(parseFloat(e.target.value) || 0)}
              className="w-full text-xs bg-background border border-input rounded px-2 py-1"
            />
            <span className="text-[11px] text-muted-foreground">Headcount / rent delta</span>
          </div>

          <div>
            <div className="flex justify-between text-xs mb-1 font-semibold">
              <span className="text-muted-foreground">DSO Stretch</span>
              <span className={dsoStretch > 0 ? "text-orange-500 font-bold" : "text-foreground"}>
                {dsoStretch > 0 ? `+${dsoStretch} days` : `${dsoStretch} days`}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="90"
              step="5"
              value={dsoStretch}
              onChange={(e) => setDsoStretch(parseInt(e.target.value, 10))}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground">Collection delay</span>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center justify-between pt-4 border-t border-border/60">
          <p className="text-xs text-muted-foreground">
            Adjusting levers runs an in-memory simulation; your actual business data is never modified.
          </p>
          <Button onClick={handleSimulate} disabled={simulating} className="gap-2">
            {simulating ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Simulating...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Simulate Scenario
              </>
            )}
          </Button>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Simulation Error"
          description={error}
          actionLabel="Try again"
          onAction={handleSimulate}
        />
      )}

      {simulating && (
        <div className="space-y-4">
          <LoadingSkeleton rows={4} variant="card" />
        </div>
      )}

      {/* Simulation Results Display */}
      {result && !simulating && (
        <div className="space-y-8 animate-in fade-in-50 duration-300">
          {/* Baseline vs Benchmark Transparency Strip */}
          <div className="rounded-xl border border-border/80 bg-muted/40 p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border/60">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" />
                Baseline Parameters & Assumptions
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSaveScenario}
                  className="gap-1.5 text-xs h-8"
                >
                  <Save className="h-3.5 w-3.5 text-primary" />
                  {saveSuccess ? "Scenario Saved!" : "Save Scenario"}
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4 text-sm">
              <div>
                <span className="text-xs text-muted-foreground block">Monthly Revenue</span>
                <strong className="text-foreground">
                  ₹{Number(result.baseline_metrics.monthly_revenue_inr || 0).toLocaleString("en-IN")}
                </strong>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Gross Margin</span>
                <strong className="text-foreground">
                  {result.baseline_metrics.gross_margin_pct}%
                </strong>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Monthly OpEx</span>
                <strong className="text-foreground">
                  ₹{Number(result.baseline_metrics.monthly_opex_inr || 0).toLocaleString("en-IN")}
                </strong>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Operating Profit</span>
                <strong className="text-foreground">
                  ₹{Number(result.baseline_metrics.monthly_operating_profit_inr || 0).toLocaleString("en-IN")}
                </strong>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Cash Cushion</span>
                <strong className="text-foreground">
                  ₹{Number(result.baseline_metrics.cash_balance_inr || 0).toLocaleString("en-IN")}
                </strong>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Top Customer Share</span>
                <strong className="text-foreground">
                  {result.baseline_metrics.top_customer_share_pct || 25}%
                </strong>
              </div>
            </div>

            {/* Missing Data Disclosures */}
            {result.missing_data_disclosures.length > 0 && (
              <div className="pt-3 border-t border-border/40 text-xs text-muted-foreground space-y-1">
                <span className="font-semibold text-foreground block mb-1">
                  Data Completeness Disclosures:
                </span>
                {result.missing_data_disclosures.map((d, i) => (
                  <p key={i} className="flex items-center gap-1.5 text-[11px]">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                    {d}
                  </p>
                ))}
              </div>
            )}
          </div>

          {/* Side-by-Side 3-Case Comparison Cards */}
          <div className="space-y-3">
            <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <GitCompare className="h-4 w-4 text-primary" />
              2. Projected Outcomes: 3-Case Comparative Analysis
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {result.cases.map((c: ScenarioCaseResult) => {
                const isWorst = c.case_label.includes("Worst");
                const isBest = c.case_label.includes("Best");
                const isBase = c.case_label === "Base Case";

                const cardBorder = isWorst
                  ? "border-rose-500/40 bg-rose-500/5"
                  : isBest
                  ? "border-emerald-500/40 bg-emerald-500/5"
                  : "border-primary/40 bg-primary/5";

                return (
                  <div
                    key={c.case_label}
                    className={`rounded-xl border p-5 space-y-4 shadow-sm transition-all ${cardBorder}`}
                  >
                    <div className="flex items-center justify-between pb-3 border-b border-border/50">
                      <span className="text-sm font-bold text-foreground flex items-center gap-2">
                        {isWorst && <ShieldAlert className="h-4 w-4 text-rose-500" />}
                        {isBest && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                        {isBase && <Sliders className="h-4 w-4 text-primary" />}
                        {c.case_label}
                      </span>
                      <Badge
                        variant="outline"
                        className={
                          isWorst
                            ? "border-rose-500/40 text-rose-500 text-[10px]"
                            : isBest
                            ? "border-emerald-500/40 text-emerald-500 text-[10px]"
                            : "border-primary/40 text-primary text-[10px]"
                        }
                      >
                        {isWorst ? "1.4x Stress" : isBest ? "Mitigated" : "Standard"}
                      </Badge>
                    </div>

                    {/* Metric Cards */}
                    <div className="space-y-3 text-sm">
                      <div className="flex justify-between items-baseline">
                        <span className="text-xs text-muted-foreground">Projected Revenue</span>
                        <div className="text-right">
                          <strong className="text-foreground block">
                            ₹{c.projected_revenue_inr.toLocaleString("en-IN")}
                          </strong>
                          <span
                            className={`text-[11px] font-semibold ${
                              c.revenue_delta_pct < 0 ? "text-rose-500" : "text-emerald-500"
                            }`}
                          >
                            {c.revenue_delta_pct > 0 ? `+${c.revenue_delta_pct}%` : `${c.revenue_delta_pct}%`} (
                            ₹{c.revenue_delta_inr.toLocaleString("en-IN")})
                          </span>
                        </div>
                      </div>

                      <div className="flex justify-between items-baseline pt-2 border-t border-border/30">
                        <span className="text-xs text-muted-foreground">Gross Profit / Margin</span>
                        <div className="text-right">
                          <strong className="text-foreground block">
                            ₹{c.projected_gross_profit_inr.toLocaleString("en-IN")}
                          </strong>
                          <span className="text-[11px] text-muted-foreground">
                            {c.gross_margin_pct}% margin
                          </span>
                        </div>
                      </div>

                      <div className="flex justify-between items-baseline pt-2 border-t border-border/30">
                        <span className="text-xs text-muted-foreground">Operating Profit</span>
                        <div className="text-right">
                          <strong
                            className={`block ${
                              c.projected_operating_profit_inr < 0
                                ? "text-rose-500 font-extrabold"
                                : "text-foreground font-bold"
                            }`}
                          >
                            ₹{c.projected_operating_profit_inr.toLocaleString("en-IN")}
                          </strong>
                          <span
                            className={`text-[11px] ${
                              c.operating_profit_delta_inr < 0 ? "text-rose-500" : "text-emerald-500"
                            }`}
                          >
                            {c.operating_profit_delta_inr > 0 ? "+" : ""}
                            ₹{c.operating_profit_delta_inr.toLocaleString("en-IN")}/mo
                          </span>
                        </div>
                      </div>

                      <div className="flex justify-between items-baseline pt-2 border-t border-border/30">
                        <span className="text-xs text-muted-foreground">Cash Runway</span>
                        <div className="text-right">
                          <strong className="text-foreground block">
                            {c.cash_runway_days_estimated !== null
                              ? `${c.cash_runway_days_estimated} days`
                              : "Self-Sustaining"}
                          </strong>
                          {c.cash_runway_days_delta !== null && (
                            <span className="text-[11px] text-rose-500 font-semibold">
                              {c.cash_runway_days_delta} days vs baseline
                            </span>
                          )}
                        </div>
                      </div>

                      {c.break_even_revenue_inr && (
                        <div className="flex justify-between items-baseline pt-2 border-t border-border/30">
                          <span className="text-xs text-muted-foreground">Break-Even Sales</span>
                          <span className="text-xs font-semibold text-foreground">
                            ₹{c.break_even_revenue_inr.toLocaleString("en-IN")}/mo
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Executive Summary & Mitigations */}
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-6 space-y-4">
            <div className="flex items-center gap-2 text-primary font-bold text-sm">
              <Sparkles className="h-4 w-4" />
              Strategic Vulnerability Assessment & Grounded Mitigations
            </div>
            <p className="text-sm text-foreground/90 leading-relaxed">
              {result.ai_executive_summary}
            </p>

            {/* Vulnerabilities */}
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">
                Vulnerabilities Exposed:
              </span>
              <ul className="space-y-1.5 text-xs text-foreground/90">
                {result.vulnerabilities_exposed.map((v, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                    <span>{v}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Actionable Mitigations */}
            <div className="space-y-2 pt-2 border-t border-border/40">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">
                Recommended Risk Mitigations:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {result.mitigation_actions.map((m, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-lg border border-border/60 bg-card/80 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between font-semibold text-foreground">
                      <span>{m.title}</span>
                      <Badge variant="secondary" className="text-[10px]">
                        {m.timeframe}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground text-[11px] leading-relaxed">{m.impact}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Saved Scenarios & Comparison Drawer */}
      {savedScenarios.length > 0 && (
        <div className="rounded-xl border border-border/80 bg-card p-6 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-border/60">
            <div>
              <h2 className="text-sm font-bold text-foreground flex items-center gap-2">
                <Calendar className="h-4 w-4 text-primary" />
                Saved Scenario Workspace
              </h2>
              <p className="text-xs text-muted-foreground">
                Select 2 or 3 saved scenarios to run a side-by-side comparative analysis.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={selectedForCompare.length < 2 || comparing}
                onClick={handleCompare}
                className="gap-1.5 text-xs"
              >
                <GitCompare className="h-3.5 w-3.5 text-primary" />
                Compare Selected ({selectedForCompare.length})
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {savedScenarios.map((s) => {
              const isChecked = selectedForCompare.includes(s.id);
              const cases = s.projection_result?.cases || [];
              const base = cases.find((c) => c.case_label === "Base Case") || cases[0];

              return (
                <div
                  key={s.id}
                  className={`p-4 rounded-xl border transition-all text-xs space-y-3 ${
                    isChecked
                      ? "border-primary bg-primary/5 shadow-sm ring-1 ring-primary"
                      : "border-border/80 bg-background hover:border-border"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleCompare(s.id)}
                        className="rounded accent-primary h-4 w-4"
                      />
                      <div>
                        <h4 className="font-bold text-foreground text-sm">{s.title}</h4>
                        <span className="text-[11px] text-muted-foreground">
                          {s.scenario_type.replace("_", " ")}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteScenario(s.id)}
                      className="text-muted-foreground hover:text-rose-500 p-1"
                      title="Delete saved scenario"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {base && (
                    <div className="grid grid-cols-2 gap-2 p-2 rounded bg-muted/40 text-[11px]">
                      <div>
                        <span className="text-muted-foreground block">Revenue Δ</span>
                        <strong
                          className={
                            base.revenue_delta_pct < 0 ? "text-rose-500 font-bold" : "text-emerald-500"
                          }
                        >
                          {base.revenue_delta_pct}%
                        </strong>
                      </div>
                      <div>
                        <span className="text-muted-foreground block">Profit Δ</span>
                        <strong
                          className={
                            base.operating_profit_delta_inr < 0 ? "text-rose-500 font-bold" : "text-emerald-500"
                          }
                        >
                          ₹{Math.round(base.operating_profit_delta_inr).toLocaleString("en-IN")}/mo
                        </strong>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(s.created_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleReloadSaved(s)}
                      className="h-6 text-[11px] px-2 text-primary"
                    >
                      Reload Levers
                      <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Comparison Result Modal / Strip */}
          {comparisonResult && (
            <div className="rounded-xl border border-primary/40 bg-primary/10 p-5 space-y-4 animate-in fade-in-50 duration-300">
              <div className="flex items-center justify-between pb-2 border-b border-primary/20">
                <span className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-1.5">
                  <GitCompare className="h-4 w-4" />
                  Side-by-Side Scenario Comparison
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setComparisonResult(null)}
                  className="text-xs h-6 text-muted-foreground"
                >
                  Close
                </Button>
              </div>

              <p className="text-xs text-foreground/90 font-medium leading-relaxed">
                {comparisonResult.comparison_summary}
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {comparisonResult.scenarios.map((sc) => (
                  <div key={sc.id} className="p-3.5 rounded-lg bg-card border border-border/80 text-xs space-y-2">
                    <strong className="text-foreground block">{sc.title}</strong>
                    <div className="space-y-1 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Revenue Shift:</span>
                        <span className={sc.base_case_revenue_delta_pct < 0 ? "text-rose-500 font-bold" : "text-emerald-500"}>
                          {sc.base_case_revenue_delta_pct}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Operating Profit Shift:</span>
                        <span className={sc.base_case_profit_delta_inr < 0 ? "text-rose-500 font-bold" : "text-emerald-500"}>
                          ₹{Math.round(sc.base_case_profit_delta_inr).toLocaleString("en-IN")}/mo
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Top Vulnerability:</span>
                        <span className="text-foreground text-[10px] truncate max-w-[130px]" title={sc.top_vulnerability}>
                          {sc.top_vulnerability}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

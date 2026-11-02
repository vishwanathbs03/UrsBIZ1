"use client";

import React, { useEffect, useState } from "react";
import {
  BookOpen,
  Search,
  Calculator,
  Database,
  Info,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  RefreshCw,
  Layers,
  Sparkles,
  Code2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  metricsDictionaryService,
  MetricCategory,
  MetricDefinition,
  MetricExplorerResult,
} from "@/services";

export function MetricsDictionaryView() {
  const [metrics, setMetrics] = useState<MetricDefinition[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Explorer State
  const [exploringKey, setExploringKey] = useState<string | null>(null);
  const [explorerResult, setExplorerResult] = useState<MetricExplorerResult | null>(null);
  const [exploringLoading, setExploringLoading] = useState(false);
  const [explorerError, setExplorerError] = useState<string | null>(null);

  useEffect(() => {
    fetchDictionary();
  }, [selectedCategory]);

  const fetchDictionary = async () => {
    try {
      setLoading(true);
      setError(null);
      const cat = selectedCategory === "all" ? undefined : selectedCategory;
      const res = await metricsDictionaryService.listMetrics(cat);
      setMetrics(res.metrics);
      setCategories(res.categories);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load metrics dictionary");
    } finally {
      setLoading(false);
    }
  };

  const handleExploreMetric = async (key: string) => {
    try {
      setExploringKey(key);
      setExploringLoading(true);
      setExplorerError(null);
      const res = await metricsDictionaryService.exploreMetric(key);
      setExplorerResult(res);
    } catch (err: unknown) {
      setExplorerError(err instanceof Error ? err.message : "Failed to explore metric calculation");
    } finally {
      setExploringLoading(false);
    }
  };

  const handleCloseExplorer = () => {
    setExploringKey(null);
    setExplorerResult(null);
    setExplorerError(null);
  };

  const filteredMetrics = metrics.filter((m) => {
    const q = searchQuery.toLowerCase();
    return (
      m.title.toLowerCase().includes(q) ||
      m.key.toLowerCase().includes(q) ||
      m.formal_definition.toLowerCase().includes(q) ||
      m.business_interpretation.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="p-2 rounded-lg bg-primary/10 text-primary border border-primary/20">
              <BookOpen className="h-5 w-5" />
            </span>
            <Badge variant="outline" className="border-primary/30 text-primary text-xs">
              Phase 6.21 Extension
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
            Business Metrics Dictionary & Calculation Explorer
          </h1>
          <p className="text-muted-foreground text-sm mt-1 max-w-2xl leading-relaxed">
            The authoritative mathematical definition, exclusion rules, and industry benchmarks for every metric across
            UrsBiz. Inspect live, step-by-step arithmetic for your business with zero AI hallucination.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="px-3 py-1 text-xs">
            {metrics.length} Canonical Metrics
          </Badge>
        </div>
      </div>

      {/* Search & Category Filter */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search metrics, formulas..."
            className="pl-9 text-xs"
          />
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          <button
            type="button"
            onClick={() => setSelectedCategory("all")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              selectedCategory === "all"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            All Categories
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${
                selectedCategory === cat
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {cat.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="space-y-4">
          <LoadingSkeleton rows={4} variant="card" />
        </div>
      )}

      {error && (
        <ErrorState
          title="Dictionary Error"
          description={error}
          actionLabel="Try Again"
          onAction={fetchDictionary}
        />
      )}

      {/* Metrics Card Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredMetrics.map((m) => {
            const isExploring = exploringKey === m.key;

            return (
              <div
                key={m.key}
                className="rounded-xl border border-border/80 bg-card p-6 space-y-4 shadow-sm hover:border-border transition-all flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Title & Category Badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h2 className="text-base font-bold text-foreground">{m.title}</h2>
                      <span className="text-[11px] font-mono text-muted-foreground">{m.key}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {m.category.replace("_", " ")}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px]">
                        {m.unit}
                      </Badge>
                    </div>
                  </div>

                  {/* Interpretation */}
                  <p className="text-xs text-foreground/90 leading-relaxed font-medium">
                    {m.business_interpretation}
                  </p>

                  {/* Formula Box */}
                  <div className="rounded-lg border border-border/60 bg-muted/50 p-3 font-mono text-xs text-primary flex items-center justify-between">
                    <span className="truncate">{m.formula}</span>
                    <Code2 className="h-3.5 w-3.5 text-muted-foreground shrink-0 ml-2" />
                  </div>

                  {/* Benchmarks & Exclusion Rules */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                    <div className="space-y-1">
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Exclusion Criteria:
                      </span>
                      <ul className="text-[11px] text-muted-foreground space-y-0.5">
                        {m.exclusion_rules.map((rule, idx) => (
                          <li key={idx} className="flex items-start gap-1.5">
                            <span className="h-1 w-1 rounded-full bg-primary shrink-0 mt-1.5" />
                            <span>{rule}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Industry Benchmarks:
                      </span>
                      <div className="text-[11px] text-muted-foreground space-y-0.5">
                        {Object.entries(m.industry_benchmarks).slice(0, 2).map(([ind, val]) => (
                          <div key={ind} className="flex justify-between">
                            <span className="font-medium text-foreground/80">{ind}:</span>
                            <span>{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Explore Action Button */}
                <div className="pt-4 border-t border-border/60 flex items-center justify-between">
                  <span className="text-[11px] text-muted-foreground truncate max-w-[200px]">
                    {m.observation_period_rule}
                  </span>
                  <Button
                    size="sm"
                    variant={isExploring ? "default" : "outline"}
                    onClick={() => handleExploreMetric(m.key)}
                    disabled={exploringLoading && isExploring}
                    className="gap-1.5 text-xs h-8"
                  >
                    <Calculator className="h-3.5 w-3.5 text-primary" />
                    {isExploring && exploringLoading ? "Calculating..." : "Inspect My Business Math"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Interactive Calculation Explorer Modal / Drawer */}
      {exploringKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in-50 duration-200">
          <div className="rounded-2xl border border-primary/30 bg-card p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-border/60">
              <div className="flex items-center gap-2.5">
                <span className="p-2 rounded-lg bg-primary/10 text-primary border border-primary/20">
                  <Calculator className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-foreground">
                    Calculation Explorer: {explorerResult?.title || exploringKey}
                  </h3>
                  <span className="text-[11px] text-muted-foreground font-mono">
                    Deterministic arithmetic execution
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseExplorer}
                className="text-muted-foreground hover:text-foreground p-1.5 rounded-lg hover:bg-muted"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {exploringLoading && (
              <div className="space-y-4 py-8">
                <LoadingSkeleton rows={3} variant="card" />
              </div>
            )}

            {explorerError && (
              <ErrorState
                title="Calculation Inspection Error"
                description={explorerError}
                actionLabel="Retry"
                onAction={() => handleExploreMetric(exploringKey)}
              />
            )}

            {explorerResult && !exploringLoading && (
              <div className="space-y-5 text-xs">
                {/* Current Value Hero Strip */}
                <div className="p-4 rounded-xl border border-primary/30 bg-primary/5 flex items-center justify-between">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">
                      Your Active Business Value
                    </span>
                    <strong className="text-2xl font-black text-foreground block mt-0.5">
                      {explorerResult.formatted_current_value}
                    </strong>
                    <span className="text-[11px] text-primary font-semibold">
                      {explorerResult.data_classification} • {explorerResult.data_freshness}
                    </span>
                  </div>
                  <Badge variant="outline" className="border-primary/40 text-primary text-xs">
                    {explorerResult.unit}
                  </Badge>
                </div>

                {/* Formula Header */}
                <div className="p-3 rounded-lg bg-muted/40 font-mono text-xs text-primary flex items-center justify-between">
                  <span>{explorerResult.formula}</span>
                </div>

                {/* Step-by-Step Mathematical Trail */}
                <div className="space-y-3">
                  <span className="font-bold text-muted-foreground uppercase tracking-wider text-[11px] block">
                    Deterministic Calculation Trace:
                  </span>
                  <div className="space-y-3">
                    {explorerResult.steps.map((step) => (
                      <div
                        key={step.step_number}
                        className="p-4 rounded-xl border border-border/70 bg-muted/30 space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-foreground flex items-center gap-2">
                            <span className="flex items-center justify-center h-5 w-5 rounded-full bg-primary/20 text-primary text-[10px]">
                              {step.step_number}
                            </span>
                            {step.step_title}
                          </span>
                          <span className="text-[11px] font-mono text-primary font-semibold">
                            {String(step.output_value)}
                          </span>
                        </div>
                        <p className="text-muted-foreground leading-relaxed text-[11px]">
                          {step.description}
                        </p>
                        <div className="p-2 rounded bg-background border border-border/40 font-mono text-[10px] text-muted-foreground flex justify-between items-center">
                          <span>{step.formula_snippet}</span>
                          <span className="text-foreground/80">
                            {JSON.stringify(step.input_values)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Provenance & Disclaimer Notice */}
                <div className="p-3.5 rounded-lg border border-border/50 bg-muted/20 text-[11px] text-muted-foreground space-y-1">
                  <span className="font-semibold text-foreground block">Calculation Provenance:</span>
                  <p>{explorerResult.provenance_note}</p>
                  <p className="text-[10px] text-muted-foreground/80 pt-1">
                    {explorerResult.disclaimer}
                  </p>
                </div>

                <div className="flex justify-end pt-2">
                  <Button size="sm" onClick={handleCloseExplorer} className="text-xs">
                    Close Inspector
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  TrendingDown,
  Layers,
  ShieldCheck,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  Search,
  Calendar,
  Info,
  X,
  ChevronRight,
  CheckCircle2,
  BarChart3,
  HelpCircle,
  Clock,
  ArrowRight,
} from "lucide-react";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import {
  forecastingService,
  type DemandForecastOverviewResponse,
  type ProductForecastDetailResponse,
  type ProductForecastSummaryItem,
  type ForecastInterval,
} from "@/services/forecasting-service";

interface DemandForecastTabProps {
  onUploadClick?: () => void;
}

export function DemandForecastTab({ onUploadClick }: DemandForecastTabProps) {
  const [interval, setInterval] = useState<ForecastInterval>("weekly");
  const [horizon, setHorizon] = useState<number>(4);
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<DemandForecastOverviewResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Detail Modal / Selection state
  const [selectedProductName, setSelectedProductName] = useState<string | null>(null);
  const [productDetail, setProductDetail] = useState<ProductForecastDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [aiExplaining, setAiExplaining] = useState(false);
  const [dynamicExplanation, setDynamicExplanation] = useState<string | null>(null);

  // Fetch overview data
  const fetchOverview = async () => {
    setLoading(true);
    try {
      const data = await forecastingService.getOverview(interval, horizon);
      setOverview(data);
    } catch (err) {
      console.error("Failed to load demand forecast overview:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, [interval, horizon]);

  // Fetch single product details when selected
  const handleSelectProduct = async (productName: string, productId?: string | null) => {
    setSelectedProductName(productName);
    setDetailLoading(true);
    setDynamicExplanation(null);
    try {
      const detail = await forecastingService.getProductForecast(productName, interval, horizon, productId);
      setProductDetail(detail);
    } catch (err) {
      console.error(`Failed to load forecast for ${productName}:`, err);
    } finally {
      setDetailLoading(false);
    }
  };

  // Close product modal
  const handleCloseDetail = () => {
    setSelectedProductName(null);
    setProductDetail(null);
    setDynamicExplanation(null);
  };

  // Request Gemini explanation
  const handleRequestAiExplanation = async () => {
    if (!productDetail) return;
    setAiExplaining(true);
    try {
      const bestMetric = productDetail.backtest_metrics.find((m) => m.is_selected);
      const res = await forecastingService.explainForecast({
        product_name: productDetail.product_name,
        historical_units: productDetail.history_points.reduce((acc, p) => acc + p.actual_quantity, 0),
        forecast_units: productDetail.forecasted_units_total,
        forecast_horizon: `${horizon} ${interval === "weekly" ? "weeks" : interval === "monthly" ? "months" : "days"}`,
        selected_model: productDetail.selected_model,
        reliability: productDetail.reliability,
        trend: productDetail.demand_trend,
        best_mae: bestMetric ? bestMetric.mae : undefined,
        limitations: productDetail.limitations,
      });
      setDynamicExplanation(res.explanation);
    } catch (err) {
      console.error("Failed to explain forecast:", err);
    } finally {
      setAiExplaining(false);
    }
  };

  // Filter products by search
  const filteredProducts = useMemo(() => {
    if (!overview) return [];
    if (!searchQuery.trim()) return overview.product_summaries;
    const query = searchQuery.toLowerCase();
    return overview.product_summaries.filter(
      (p) =>
        p.product_name.toLowerCase().includes(query) ||
        p.selected_model.toLowerCase().includes(query) ||
        p.reliability.toLowerCase().includes(query)
    );
  }, [overview, searchQuery]);

  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
        <LoadingSkeleton variant="card" />
      </div>
    );
  }

  if (!overview || overview.total_products === 0) {
    return (
      <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
        <BarChart3 className="mx-auto h-16 w-16 text-neon-cyan/50 animate-pulse" />
        <h3 className="mt-4 text-base font-bold text-dark-text-primary">
          No Sales Data Available for Demand Forecasting
        </h3>
        <p className="mx-auto mt-2 max-w-md text-xs text-dark-text-muted">
          Demand forecasting requires historical sales transactions. Upload your historical sales invoices
          in the Overview tab to generate SKU-level demand projections.
        </p>
        {onUploadClick && (
          <div className="mt-6 flex justify-center">
            <Button
              onClick={onUploadClick}
              className="bg-neon-cyan text-xs font-semibold text-black hover:bg-neon-cyan/90"
            >
              Upload Sales Data
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Disclaimer & Transparency Banner */}
      <div className="rounded-xl border border-neon-cyan/30 bg-neon-cyan/5 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5 text-dark-text-primary">
          <Info className="h-4 w-4 text-neon-cyan flex-shrink-0" />
          <span>
            <strong className="text-neon-cyan">Demand Projections Notice:</strong> Forecasts represent estimated customer purchase volume derived from your verified sales transactions. They do not claim inventory stock levels or supplier capacity.
          </span>
        </div>
        <span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-[10px] font-mono text-neon-cyan uppercase flex-shrink-0">
          Pure Time-Series Engine
        </span>
      </div>

      {/* Control Bar: Horizon & Interval */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-dark-border bg-dark-card p-4">
        <div>
          <h3 className="text-sm font-bold text-dark-text-primary uppercase tracking-wider flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-neon-cyan" /> SKU-Level Demand Forecasting
          </h3>
          <p className="text-xs text-dark-text-muted">
            Chronologically validated against real MSME sales history ({overview.dataset_span_days} days span).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Interval Toggle */}
          <div className="flex items-center gap-1 rounded-lg border border-dark-border bg-dark-bg p-1 text-xs">
            <span className="text-[10px] font-medium text-dark-text-muted px-2">Cadence:</span>
            <Button
              type="button"
              size="sm"
              variant={interval === "weekly" ? "default" : "ghost"}
              onClick={() => setInterval("weekly")}
              className={`h-7 px-2.5 text-xs ${
                interval === "weekly" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90 font-semibold" : "text-dark-text-muted"
              }`}
            >
              Weekly
            </Button>
            <Button
              type="button"
              size="sm"
              variant={interval === "monthly" ? "default" : "ghost"}
              onClick={() => setInterval("monthly")}
              className={`h-7 px-2.5 text-xs ${
                interval === "monthly" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90 font-semibold" : "text-dark-text-muted"
              }`}
            >
              Monthly
            </Button>
            <Button
              type="button"
              size="sm"
              variant={interval === "daily" ? "default" : "ghost"}
              onClick={() => setInterval("daily")}
              className={`h-7 px-2.5 text-xs ${
                interval === "daily" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90 font-semibold" : "text-dark-text-muted"
              }`}
            >
              Daily
            </Button>
          </div>

          {/* Horizon Selector */}
          <div className="flex items-center gap-1 rounded-lg border border-dark-border bg-dark-bg p-1 text-xs">
            <span className="text-[10px] font-medium text-dark-text-muted px-2">Horizon:</span>
            {[4, 8, 12].map((h) => (
              <Button
                key={h}
                type="button"
                size="sm"
                variant={horizon === h ? "default" : "ghost"}
                onClick={() => setHorizon(h)}
                className={`h-7 px-2.5 text-xs ${
                  horizon === h ? "bg-neon-cyan text-black hover:bg-neon-cyan/90 font-semibold" : "text-dark-text-muted"
                }`}
              >
                {h} {interval === "weekly" ? "Wks" : interval === "monthly" ? "Mos" : "Days"}
              </Button>
            ))}
          </div>

          {/* Refresh Button */}
          <Button
            size="sm"
            variant="outline"
            onClick={fetchOverview}
            disabled={loading}
            className="h-9 border-dark-border text-dark-text-primary hover:bg-dark-border/20 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Projected Units"
          value={Math.round(overview.total_projected_demand_units).toLocaleString()}
          icon={<Layers className="h-5 w-5 text-neon-cyan" />}
          accentColor="cyan"
          caption={`Across ${overview.products_with_forecast} projected SKUs`}
        />
        <MetricCard
          title="Increasing Demand"
          value={overview.products_increasing_demand.toString()}
          icon={<TrendingUp className="h-5 w-5 text-neon-emerald" />}
          accentColor="emerald"
          caption="Positive trajectory (> 2%)"
        />
        <MetricCard
          title="Declining Demand"
          value={overview.products_declining_demand.toString()}
          icon={<TrendingDown className="h-5 w-5 text-neon-rose" />}
          accentColor="amber"
          caption="Negative trajectory (< -2%)"
        />
        <MetricCard
          title="Insufficient History"
          value={overview.products_insufficient_history.toString()}
          icon={<AlertTriangle className="h-5 w-5 text-neon-amber" />}
          accentColor="amber"
          caption="Needs >= 4 periods"
        />
      </div>

      {/* Product Demand Overview Table Card */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-dark-text-primary uppercase tracking-wider">
              Product Demand Forecast Summary
            </h3>
            <p className="text-xs text-dark-text-muted">
              Select any SKU to inspect historical vs. projected curves, prediction intervals, and holdout backtest metrics.
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-dark-text-muted" />
            <input
              type="text"
              placeholder="Search product, model..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-dark-border bg-dark-bg py-1.5 pl-8 pr-3 text-xs text-dark-text-primary placeholder:text-dark-text-muted focus:border-neon-cyan focus:outline-none"
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-dark-border">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
              <tr>
                <th className="p-3">Product Name</th>
                <th className="p-3">Data Status</th>
                <th className="p-3">Winning Model</th>
                <th className="p-3">Reliability</th>
                <th className="p-3 text-right">Historical Units</th>
                <th className="p-3 text-right">Projected ({horizon} {interval[0].toUpperCase()})</th>
                <th className="p-3 text-right">Trend</th>
                <th className="p-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border">
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-dark-text-muted">
                    No products match the search query.
                  </td>
                </tr>
              ) : (
                filteredProducts.map((p, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-dark-border/20 transition-colors cursor-pointer"
                    onClick={() => handleSelectProduct(p.product_name, p.product_id)}
                  >
                    <td className="p-3 font-semibold text-dark-text-primary max-w-[220px] truncate">
                      <span>{p.product_name}</span>
                      {p.product_id && (
                        <span className="ml-1.5 font-mono text-[10px] text-dark-text-muted bg-dark-border/40 px-1 py-0.5 rounded">
                          {p.product_id}
                        </span>
                      )}
                    </td>
                    <td className="p-3">
                      <StatusBadge status={p.data_status} />
                    </td>
                    <td className="p-3 font-mono text-neon-cyan text-[11px]">
                      {p.selected_model}
                    </td>
                    <td className="p-3">
                      <ReliabilityBadge reliability={p.reliability} />
                    </td>
                    <td className="p-3 text-right font-mono text-dark-text-muted">
                      {Math.round(p.historical_units_total).toLocaleString()}
                    </td>
                    <td className="p-3 text-right font-mono font-bold text-neon-emerald">
                      {p.data_status === "forecast_available"
                        ? Math.round(p.forecasted_units_total).toLocaleString()
                        : "—"}
                    </td>
                    <td className="p-3 text-right font-mono">
                      <TrendIndicator trend={p.demand_trend} delta={p.trend_delta_pct} />
                    </td>
                    <td className="p-3 text-center">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectProduct(p.product_name, p.product_id);
                        }}
                        className="h-6 px-2 text-[11px] text-neon-cyan hover:bg-neon-cyan/10"
                      >
                        Inspect <ChevronRight className="ml-1 h-3 w-3" />
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* DETAILED PRODUCT FORECAST MODAL / FLYOUT */}
      {selectedProductName && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm overflow-y-auto">
          <div className="relative w-full max-w-4xl rounded-2xl border border-dark-border bg-dark-bg p-6 shadow-2xl space-y-6 my-8 max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-start justify-between border-b border-dark-border pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-dark-text-primary flex items-center gap-2">
                    <span>{selectedProductName}</span>
                    {productDetail?.product_id && (
                      <span className="font-mono text-xs text-dark-text-muted bg-dark-border/50 px-1.5 py-0.5 rounded">
                        ID: {productDetail.product_id}
                      </span>
                    )}
                  </h2>
                  {productDetail && (
                    <ReliabilityBadge reliability={productDetail.reliability} />
                  )}
                </div>
                <p className="text-xs text-dark-text-muted mt-1">
                  Historical sales observations vs. {horizon}-period demand trajectory ({interval}).
                </p>
              </div>
              <button
                onClick={handleCloseDetail}
                className="rounded-lg p-1.5 text-dark-text-muted hover:bg-dark-border/40 hover:text-dark-text-primary"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {detailLoading || !productDetail ? (
              <div className="py-12 space-y-4">
                <LoadingSkeleton variant="metric" />
                <LoadingSkeleton variant="card" />
              </div>
            ) : (
              <div className="space-y-6">
                {/* Highlights Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="rounded-lg border border-dark-border bg-dark-card p-3">
                    <span className="text-dark-text-muted block text-[10px] uppercase">Selected Model</span>
                    <span className="font-mono font-bold text-neon-cyan mt-1 block">
                      {productDetail.selected_model}
                    </span>
                  </div>
                  <div className="rounded-lg border border-dark-border bg-dark-card p-3">
                    <span className="text-dark-text-muted block text-[10px] uppercase">Demand Trajectory</span>
                    <span className="font-mono font-bold mt-1 block flex items-center gap-1">
                      <TrendIndicator trend={productDetail.demand_trend} delta={productDetail.trend_delta_pct} />
                    </span>
                  </div>
                  <div className="rounded-lg border border-dark-border bg-dark-card p-3">
                    <span className="text-dark-text-muted block text-[10px] uppercase">Forecasted Units</span>
                    <span className="font-mono font-bold text-neon-emerald mt-1 block">
                      {Math.round(productDetail.forecasted_units_total).toLocaleString()} units
                    </span>
                  </div>
                  <div className="rounded-lg border border-dark-border bg-dark-card p-3">
                    <span className="text-dark-text-muted block text-[10px] uppercase">
                      {productDetail.evaluation_stage === "independent_test_evaluated"
                        ? "Independent Test (MAE)"
                        : "Tournament (MAE)"}
                    </span>
                    <span className="font-mono font-bold text-dark-text-primary mt-1 block">
                      {productDetail.evaluation_stage === "independent_test_evaluated" &&
                      productDetail.independent_test_metrics &&
                      productDetail.independent_test_metrics.length > 0
                        ? (productDetail.independent_test_metrics.find((m) => m.is_selected)?.mae.toFixed(2) ?? "N/A")
                        : (productDetail.backtest_metrics.find((m) => m.is_selected)?.mae.toFixed(2) ?? "N/A")}
                    </span>
                  </div>
                </div>

                {/* Trajectory Visualizer */}
                <div className="rounded-xl border border-dark-border bg-dark-card p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-dark-text-primary uppercase tracking-wider flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-neon-cyan" /> Demand Trajectory & Prediction Interval
                    </h4>
                    <div className="flex items-center gap-3 text-[11px]">
                      <span className="flex items-center gap-1.5 text-dark-text-muted">
                        <span className="h-2 w-3 rounded-sm bg-neon-cyan" /> Historical
                      </span>
                      <span className="flex items-center gap-1.5 text-neon-emerald">
                        <span className="h-2 w-3 rounded-sm bg-neon-emerald border border-dashed border-neon-emerald" /> Projected
                      </span>
                      <span className="flex items-center gap-1.5 text-neon-emerald/60">
                        <span className="h-2 w-3 rounded-sm bg-neon-emerald/20 border border-neon-emerald/40" />
                        {productDetail.empirical_coverage_summary
                          ? `Estimated Range (${productDetail.empirical_coverage_summary})`
                          : (productDetail.range_type || "Estimated Range")}
                      </span>
                    </div>
                  </div>

                  {/* Custom SVG Time Series Chart */}
                  <div className="h-64 w-full rounded-lg border border-dark-border/50 bg-dark-bg/60 p-4">
                    <DemandTrajectoryChart
                      history={productDetail.history_points}
                      forecast={productDetail.forecast_points}
                    />
                  </div>
                </div>

                {/* Independent Final Test & Model Selection Tournament */}
                <div className="rounded-xl border border-dark-border bg-dark-card p-5 space-y-4">
                  {/* Stage 1: If independent test was evaluated, display the separate out-of-sample test card */}
                  {productDetail.evaluation_stage === "independent_test_evaluated" &&
                    productDetail.independent_test_metrics &&
                    productDetail.independent_test_metrics.length > 0 && (
                      <div className="rounded-lg border border-neon-emerald/30 bg-neon-emerald/5 p-4 space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="h-4 w-4 text-neon-emerald" />
                            <h4 className="text-xs font-bold text-dark-text-primary uppercase tracking-wider">
                              Independent Final Test Evaluation
                            </h4>
                          </div>
                          <span className="rounded bg-neon-emerald/20 px-2 py-0.5 text-[10px] font-mono font-bold text-neon-emerald uppercase">
                            Separate Held-Out Test Segment
                          </span>
                        </div>
                        <p className="text-[11px] text-dark-text-muted">
                          Candidate models were trained and selected strictly on earlier history. This final evaluation was conducted on an untouched {productDetail.independent_test_metrics[0].test_periods}-period holdout segment never seen during model selection.
                        </p>
                        <div className="overflow-x-auto rounded border border-dark-border/60">
                          <table className="w-full text-left text-xs">
                            <thead className="border-b border-dark-border bg-dark-bg/80 text-dark-text-muted">
                              <tr>
                                <th className="p-2">Model Role</th>
                                <th className="p-2">Model Name</th>
                                <th className="p-2 text-right">Test MAE</th>
                                <th className="p-2 text-right">RMSE</th>
                                <th className="p-2 text-right">WAPE</th>
                                <th className="p-2 text-right">MASE</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-dark-border/50">
                              {productDetail.independent_test_metrics.map((item, idx) => (
                                <tr key={idx} className={item.is_selected ? "bg-neon-emerald/10 font-semibold" : ""}>
                                  <td className="p-2 text-dark-text-muted font-mono text-[11px]">
                                    {item.is_selected ? (
                                      <span className="text-neon-emerald flex items-center gap-1">
                                        <CheckCircle2 className="h-3 w-3" /> Selected Winner
                                      </span>
                                    ) : (
                                      "Reference Baseline"
                                    )}
                                  </td>
                                  <td className="p-2 font-mono text-dark-text-primary">{item.model_name}</td>
                                  <td className="p-2 text-right font-mono text-neon-emerald">{item.mae.toFixed(2)}</td>
                                  <td className="p-2 text-right font-mono">{item.rmse.toFixed(2)}</td>
                                  <td className="p-2 text-right font-mono">
                                    {item.wape !== null && item.wape !== undefined ? `${(item.wape * 100).toFixed(1)}%` : "—"}
                                  </td>
                                  <td className="p-2 text-right font-mono">
                                    {item.mase !== null && item.mase !== undefined ? item.mase.toFixed(2) : "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                  {/* Stage 2: Internal Model Selection Tournament */}
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <h4 className="text-xs font-bold text-dark-text-primary uppercase tracking-wider flex items-center gap-2">
                          <Layers className="h-4 w-4 text-neon-cyan" /> Internal Model Selection Tournament
                        </h4>
                        <p className="text-[11px] text-dark-text-muted">
                          {productDetail.provenance.evaluation_method === "rolling_origin"
                            ? `Walk-forward tournament across ${productDetail.provenance.rolling_splits_count} expanding splits. Advanced models win only if they beat the baseline by > 2% MAE.`
                            : "Chronological holdout tournament. Advanced models win only if they beat the baseline by > 2% MAE."}
                        </p>
                      </div>
                      <span className="rounded bg-dark-bg border border-dark-border px-2 py-0.5 text-[10px] font-mono text-dark-text-muted">
                        {productDetail.evaluation_stage === "independent_test_evaluated"
                          ? "Selection Stage Diagnostics"
                          : "Tournament Diagnostics Only"}
                      </span>
                    </div>

                    <div className="overflow-x-auto rounded-lg border border-dark-border">
                      <table className="w-full text-left text-xs">
                        <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
                          <tr>
                            <th className="p-2.5">Model</th>
                            <th className="p-2.5 text-right">Tournament MAE</th>
                            <th className="p-2.5 text-right">RMSE</th>
                            <th className="p-2.5 text-right">WAPE</th>
                            <th className="p-2.5 text-right">MASE</th>
                            <th className="p-2.5 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-dark-border">
                          {productDetail.backtest_metrics.map((m, i) => (
                            <tr
                              key={i}
                              className={m.is_selected ? "bg-neon-cyan/10 font-semibold" : "hover:bg-dark-border/10"}
                            >
                              <td className="p-2.5 font-mono text-dark-text-primary flex items-center gap-1.5">
                                {m.is_selected && <CheckCircle2 className="h-3.5 w-3.5 text-neon-cyan" />}
                                {m.model_name}
                              </td>
                              <td className="p-2.5 text-right font-mono">{m.mae.toFixed(2)}</td>
                              <td className="p-2.5 text-right font-mono">{m.rmse.toFixed(2)}</td>
                              <td className="p-2.5 text-right font-mono">
                                {m.wape !== null && m.wape !== undefined ? `${(m.wape * 100).toFixed(1)}%` : "—"}
                              </td>
                              <td className="p-2.5 text-right font-mono">
                                {m.mase !== null && m.mase !== undefined ? m.mase.toFixed(2) : "—"}
                              </td>
                              <td className="p-2.5 text-center">
                                {m.is_selected ? (
                                  <span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-[10px] font-mono text-neon-cyan font-bold uppercase">
                                    Selected
                                  </span>
                                ) : (
                                  <span className="text-[10px] text-dark-text-muted">Evaluated</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {/* Grounded Plain-Language Explanation */}
                <div className="rounded-xl border border-dark-border bg-dark-card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-dark-text-primary uppercase tracking-wider flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-neon-cyan" /> Forecast Explanation & Grounding
                    </h4>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleRequestAiExplanation}
                      disabled={aiExplaining}
                      className="h-7 border-neon-cyan/40 bg-neon-cyan/10 text-neon-cyan hover:bg-neon-cyan/20 text-xs"
                    >
                      <Sparkles className={`mr-1.5 h-3 w-3 ${aiExplaining ? "animate-spin" : ""}`} />
                      {aiExplaining ? "Synthesizing with Gemini..." : "Deep Explain with Gemini"}
                    </Button>
                  </div>

                  <p className="rounded-lg bg-dark-bg p-3.5 text-xs text-dark-text-primary leading-relaxed border border-dark-border/40">
                    {dynamicExplanation || productDetail.explanation}
                  </p>

                  {productDetail.limitations.length > 0 && (
                    <div className="space-y-1 text-[11px] text-dark-text-muted">
                      <span className="font-semibold text-neon-amber flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> Data Limitations & Caveats:
                      </span>
                      <ul className="list-disc pl-5 space-y-0.5">
                        {productDetail.limitations.map((lim, i) => (
                          <li key={i}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Badges & Indicators
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "forecast_available":
      return (
        <span className="rounded bg-neon-emerald/10 border border-neon-emerald/30 px-2 py-0.5 text-[10px] font-mono text-neon-emerald">
          Available
        </span>
      );
    case "insufficient_history":
      return (
        <span className="rounded bg-neon-amber/10 border border-neon-amber/30 px-2 py-0.5 text-[10px] font-mono text-neon-amber">
          &lt; 4 Periods
        </span>
      );
    case "intermittent_demand":
      return (
        <span className="rounded bg-neon-cyan/10 border border-neon-cyan/30 px-2 py-0.5 text-[10px] font-mono text-neon-cyan">
          Intermittent
        </span>
      );
    default:
      return (
        <span className="rounded bg-dark-border px-2 py-0.5 text-[10px] font-mono text-dark-text-muted">
          No Sales
        </span>
      );
  }
}

function ReliabilityBadge({ reliability }: { reliability: string }) {
  switch (reliability) {
    case "High":
      return (
        <span className="rounded-full bg-neon-emerald/20 px-2 py-0.5 text-[10px] font-medium text-neon-emerald">
          High Confidence
        </span>
      );
    case "Medium":
      return (
        <span className="rounded-full bg-neon-cyan/20 px-2 py-0.5 text-[10px] font-medium text-neon-cyan">
          Medium Confidence
        </span>
      );
    case "Low":
      return (
        <span className="rounded-full bg-neon-amber/20 px-2 py-0.5 text-[10px] font-medium text-neon-amber">
          Low Confidence
        </span>
      );
    default:
      return (
        <span className="rounded-full bg-dark-border/40 px-2 py-0.5 text-[10px] font-medium text-dark-text-muted">
          Insufficient Data
        </span>
      );
  }
}

function TrendIndicator({ trend, delta }: { trend: string; delta?: number | null }) {
  if (trend === "Increasing") {
    return (
      <span className="flex items-center gap-1 text-neon-emerald">
        <TrendingUp className="h-3.5 w-3.5" />
        {delta !== null && delta !== undefined ? `+${delta.toFixed(1)}%` : "Growing"}
      </span>
    );
  }
  if (trend === "Decreasing") {
    return (
      <span className="flex items-center gap-1 text-neon-rose">
        <TrendingDown className="h-3.5 w-3.5" />
        {delta !== null && delta !== undefined ? `${delta.toFixed(1)}%` : "Declining"}
      </span>
    );
  }
  if (trend === "Stable") {
    return <span className="text-neon-cyan">Stable</span>;
  }
  return <span className="text-dark-text-muted">N/A</span>;
}

// ---------------------------------------------------------------------------
// Custom Interactive SVG Trajectory Chart
// ---------------------------------------------------------------------------

interface TrajectoryChartProps {
  history: { period_label: string; actual_quantity: number }[];
  forecast: { period_label: string; predicted_quantity: number; lower_estimate: number; upper_estimate: number }[];
}

function DemandTrajectoryChart({ history, forecast }: TrajectoryChartProps) {
  const combinedPointsCount = history.length + forecast.length;
  if (combinedPointsCount === 0) {
    return (
      <div className="h-full flex items-center justify-center text-xs text-dark-text-muted">
        No points to plot
      </div>
    );
  }

  // Calculate scales
  const allValues = [
    ...history.map((h) => h.actual_quantity),
    ...forecast.map((f) => f.predicted_quantity),
    ...forecast.map((f) => f.upper_estimate),
  ];
  const maxVal = Math.max(...allValues, 10);
  const minVal = 0;

  const width = 800;
  const height = 220;
  const paddingLeft = 45;
  const paddingRight = 35;
  const paddingTop = 20;
  const paddingBottom = 30;

  const chartW = width - paddingLeft - paddingRight;
  const chartH = height - paddingTop - paddingBottom;

  const totalSteps = Math.max(combinedPointsCount - 1, 1);
  const getX = (index: number) => paddingLeft + (index / totalSteps) * chartW;
  const getY = (val: number) => paddingTop + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;

  // History path
  let historyPath = "";
  history.forEach((pt, i) => {
    const x = getX(i);
    const y = getY(pt.actual_quantity);
    historyPath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });

  // Forecast path (connecting from last history point if available)
  let forecastPath = "";
  const startIndex = Math.max(history.length - 1, 0);
  if (history.length > 0 && forecast.length > 0) {
    const startX = getX(startIndex);
    const startY = getY(history[history.length - 1].actual_quantity);
    forecastPath = `M ${startX} ${startY}`;
    forecast.forEach((pt, i) => {
      const x = getX(history.length + i);
      const y = getY(pt.predicted_quantity);
      forecastPath += ` L ${x} ${y}`;
    });
  } else if (forecast.length > 0) {
    forecast.forEach((pt, i) => {
      const x = getX(i);
      const y = getY(pt.predicted_quantity);
      forecastPath += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });
  }

  // 80% interval shaded polygon
  let intervalPolygon = "";
  if (forecast.length > 0) {
    const upperPoints: string[] = [];
    const lowerPoints: string[] = [];

    if (history.length > 0) {
      const lastHistX = getX(history.length - 1);
      const lastHistY = getY(history[history.length - 1].actual_quantity);
      upperPoints.push(`${lastHistX},${lastHistY}`);
      lowerPoints.push(`${lastHistX},${lastHistY}`);
    }

    forecast.forEach((pt, i) => {
      const x = getX(history.length + i);
      const yUpper = getY(pt.upper_estimate);
      const yLower = getY(pt.lower_estimate);
      upperPoints.push(`${x},${yUpper}`);
      lowerPoints.unshift(`${x},${yLower}`);
    });

    intervalPolygon = [...upperPoints, ...lowerPoints].join(" ");
  }

  const splitX = history.length > 0 && forecast.length > 0 ? getX(history.length - 1) : null;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full">
      {/* Grid horizontal lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
        const yVal = minVal + pct * (maxVal - minVal);
        const yPos = getY(yVal);
        return (
          <g key={idx}>
            <line
              x1={paddingLeft}
              y1={yPos}
              x2={width - paddingRight}
              y2={yPos}
              stroke="rgba(255,255,255,0.06)"
              strokeDasharray="3 3"
            />
            <text
              x={paddingLeft - 8}
              y={yPos + 3}
              textAnchor="end"
              fill="rgba(255,255,255,0.4)"
              fontSize="9"
              fontFamily="monospace"
            >
              {Math.round(yVal)}
            </text>
          </g>
        );
      })}

      {/* Vertical boundary line between history and forecast */}
      {splitX !== null && (
        <g>
          <line
            x1={splitX}
            y1={paddingTop}
            x2={splitX}
            y2={height - paddingBottom}
            stroke="#06B6D4"
            strokeDasharray="4 4"
            strokeWidth="1.5"
          />
          <text
            x={splitX}
            y={paddingTop - 5}
            textAnchor="middle"
            fill="#06B6D4"
            fontSize="9"
            fontWeight="bold"
          >
            TODAY / HORIZON START
          </text>
        </g>
      )}

      {/* 80% Prediction interval area */}
      {intervalPolygon && (
        <polygon
          points={intervalPolygon}
          fill="rgba(16, 185, 129, 0.12)"
          stroke="rgba(16, 185, 129, 0.3)"
          strokeDasharray="2 2"
        />
      )}

      {/* Historical observations line */}
      {historyPath && (
        <path
          d={historyPath}
          fill="none"
          stroke="#06B6D4"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {/* Forecast line */}
      {forecastPath && (
        <path
          d={forecastPath}
          fill="none"
          stroke="#10B981"
          strokeWidth="2.5"
          strokeDasharray="5 4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {/* Historical points */}
      {history.map((pt, i) => {
        const cx = getX(i);
        const cy = getY(pt.actual_quantity);
        return (
          <g key={`hist-${i}`}>
            <circle cx={cx} cy={cy} r="4" fill="#06B6D4" stroke="#0f172a" strokeWidth="1.5" />
            <text
              x={cx}
              y={height - paddingBottom + 14}
              textAnchor="middle"
              fill="rgba(255,255,255,0.5)"
              fontSize="8"
            >
              {pt.period_label}
            </text>
          </g>
        );
      })}

      {/* Forecast points */}
      {forecast.map((pt, i) => {
        const cx = getX(history.length + i);
        const cy = getY(pt.predicted_quantity);
        return (
          <g key={`fc-${i}`}>
            <circle cx={cx} cy={cy} r="4.5" fill="#10B981" stroke="#0f172a" strokeWidth="2" />
            <text
              x={cx}
              y={height - paddingBottom + 14}
              textAnchor="middle"
              fill="#10B981"
              fontSize="8"
              fontWeight="bold"
            >
              {pt.period_label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

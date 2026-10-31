/**
 * Forecasting Service — API client for Phase 4 Demand Forecasting & Predictive Intelligence.
 */

import { apiClient } from "@/services/api-client";

export type ForecastInterval = "weekly" | "monthly" | "daily";

export type ForecastReliability = "High" | "Medium" | "Low" | "Insufficient History";

export type DataLimitationStatus =
  | "forecast_available"
  | "insufficient_history"
  | "intermittent_demand"
  | "no_sales_history";

export interface BacktestMetricItem {
  model_name: string;
  mae: number;
  rmse: number;
  wape?: number | null;
  mape?: number | null;
  mase?: number | null;
  holdout_periods: number;
  is_selected: boolean;
}

export interface ForecastPeriodPoint {
  period_index: number;
  period_label: string;
  period_start: string;
  period_end: string;
  predicted_quantity: number;
  lower_estimate: number;
  upper_estimate: number;
}

export interface HistoricalPeriodPoint {
  period_label: string;
  period_start: string;
  period_end: string;
  actual_quantity: number;
  has_data: boolean;
}

export interface ProductForecastSummaryItem {
  product_name: string;
  product_id?: string | null;
  data_status: DataLimitationStatus;
  selected_model: string;
  reliability: ForecastReliability;
  historical_periods_count: number;
  historical_units_total: number;
  forecast_horizon_periods: number;
  forecasted_units_total: number;
  demand_trend: string;
  trend_delta_pct?: number | null;
  best_mae?: number | null;
  best_wape?: number | null;
  limitation_notes: string[];
}

export interface ProductForecastDetailResponse {
  product_name: string;
  product_id?: string | null;
  data_status: DataLimitationStatus;
  selected_model: string;
  reliability: ForecastReliability;
  aggregation_interval: ForecastInterval;
  forecast_horizon_periods: number;
  forecasted_units_total: number;
  demand_trend: string;
  trend_delta_pct?: number | null;
  history_points: HistoricalPeriodPoint[];
  forecast_points: ForecastPeriodPoint[];
  backtest_metrics: BacktestMetricItem[];
  explanation: string;
  limitations: string[];
  provenance: Record<string, any>;
}

export interface DemandForecastOverviewResponse {
  total_products: number;
  products_with_forecast: number;
  products_insufficient_history: number;
  products_increasing_demand: number;
  products_declining_demand: number;
  products_stable_demand: number;
  total_projected_demand_units: number;
  forecast_horizon: string;
  aggregation_interval: ForecastInterval;
  product_summaries: ProductForecastSummaryItem[];
  dataset_span_days: number;
  earliest_transaction_date?: string | null;
  latest_transaction_date?: string | null;
  inactivity_anchor_date?: string | null;
}

export interface ForecastExplainRequest {
  product_name: string;
  historical_units: number;
  forecast_units: number;
  forecast_horizon: string;
  selected_model: string;
  reliability: string;
  trend: string;
  best_mae?: number | null;
  limitations?: string[];
}

export interface ForecastExplainResponse {
  product_name: string;
  explanation: string;
  is_ai_generated: boolean;
  disclaimer: string;
}

export const forecastingService = {
  /**
   * Get demand forecast overview across all products for the active business.
   */
  async getOverview(
    interval: ForecastInterval = "weekly",
    horizon: number = 4
  ): Promise<DemandForecastOverviewResponse> {
    return apiClient.get<DemandForecastOverviewResponse>(
      `/forecasting/overview?interval=${interval}&horizon=${horizon}`
    );
  },

  /**
   * Get single product historical demand and future forecast trajectory.
   */
  async getProductForecast(
    productName: string,
    interval: ForecastInterval = "weekly",
    horizon: number = 4
  ): Promise<ProductForecastDetailResponse> {
    const encoded = encodeURIComponent(productName);
    return apiClient.get<ProductForecastDetailResponse>(
      `/forecasting/product/${encoded}?interval=${interval}&horizon=${horizon}`
    );
  },

  /**
   * Request grounded plain-language or AI explanation of verified forecast metrics.
   */
  async explainForecast(payload: ForecastExplainRequest): Promise<ForecastExplainResponse> {
    return apiClient.post<ForecastExplainResponse>("/forecasting/explain", payload);
  },
};

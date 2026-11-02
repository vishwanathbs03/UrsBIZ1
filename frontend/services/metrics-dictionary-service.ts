"use client";

/**
 * Frontend client service for Business Metrics Dictionary and Calculation Explorer (Phase 6.21 Extension).
 *
 * Connects to:
 *   GET /api/v1/metrics                     - List all canonical metric definitions with category filter
 *   GET /api/v1/metrics/{metric_key}        - Get single metric definition
 *   GET /api/v1/metrics/{metric_key}/explore - Step-by-step calculation explorer with active business data
 */

import { apiClient, ApiError } from "./api-client";

export type MetricCategory = "financial" | "sales" | "customer" | "operations" | "data_integrity";

export interface MetricVariable {
  name: string;
  symbol: string;
  description: string;
  source_table: string;
  data_classification: "Observed Fact" | "Calculated Metric" | "User-Entered" | "Benchmark Assumption";
}

export interface CalculationStep {
  step_number: number;
  step_title: string;
  description: string;
  formula_snippet: string;
  input_values: Record<string, unknown>;
  output_value: unknown;
}

export interface MetricDefinition {
  key: string;
  title: string;
  category: MetricCategory;
  formal_definition: string;
  business_interpretation: string;
  formula: string;
  unit: string;
  observation_period_rule: string;
  exclusion_rules: string[];
  known_limitations: string[];
  industry_benchmarks: Record<string, string>;
  input_variables: MetricVariable[];
}

export interface MetricExplorerResult {
  metric_key: string;
  title: string;
  category: string;
  business_id: number;
  current_value: number | string | null;
  formatted_current_value: string;
  unit: string;
  formula: string;
  has_live_data: boolean;
  data_classification: string;
  data_freshness: string;
  steps: CalculationStep[];
  provenance_note: string;
  disclaimer: string;
}

export interface MetricDictionaryResponse {
  metrics: MetricDefinition[];
  total: number;
  categories: string[];
  version: string;
}

export const metricsDictionaryService = {
  /** Fetch all metrics in the dictionary, optionally filtered by category. */
  async listMetrics(category?: string): Promise<MetricDictionaryResponse> {
    const url = category ? `/metrics?category=${encodeURIComponent(category)}` : "/metrics";
    return apiClient.get<MetricDictionaryResponse>(url);
  },

  /** Get detailed specification for a single metric. */
  async getMetric(metricKey: string): Promise<MetricDefinition> {
    return apiClient.get<MetricDefinition>(`/metrics/${metricKey}`);
  },

  /** Explore step-by-step arithmetic calculation for active business. */
  async exploreMetric(metricKey: string): Promise<MetricExplorerResult> {
    return apiClient.get<MetricExplorerResult>(`/metrics/${metricKey}/explore`);
  },
};

export { ApiError };

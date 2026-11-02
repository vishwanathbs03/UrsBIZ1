"use client";

/**
 * Frontend client service for What-If Scenario Simulator (Phase 6.19 Extension).
 *
 * Connects to:
 *   POST   /api/v1/scenarios/simulate  - Run in-memory simulation
 *   POST   /api/v1/scenarios           - Save scenario
 *   GET    /api/v1/scenarios           - List saved scenarios
 *   GET    /api/v1/scenarios/{id}      - Get saved scenario
 *   PATCH  /api/v1/scenarios/{id}      - Update scenario
 *   DELETE /api/v1/scenarios/{id}      - Delete scenario
 *   POST   /api/v1/scenarios/compare   - Compare multiple scenarios
 */

import { apiClient, ApiError } from "./api-client";

export type ScenarioType =
  | "sales_drop"
  | "supplier_cost_increase"
  | "customer_churn"
  | "hiring_expansion"
  | "price_elasticity"
  | "collection_delay"
  | "custom";

export interface ScenarioParameterIn {
  scenario_type: ScenarioType;
  sales_volume_delta_pct?: number;
  price_delta_pct?: number;
  cogs_delta_pct?: number;
  opex_delta_inr?: number;
  dso_stretch_days?: number;
  lost_customer_id?: string | null;
  lost_customer_revenue_inr?: number | null;
  assumptions_overrides?: Record<string, number> | null;
}

export interface AssumptionItem {
  name: string;
  value: number | string;
  unit: string;
  source: "Observed Fact" | "Industry Benchmark" | "User Override";
  note: string;
}

export interface ScenarioCaseResult {
  case_label: "Base Case" | "Conservative / Worst Case" | "Optimistic / Best Case";
  projected_revenue_inr: number;
  revenue_delta_inr: number;
  revenue_delta_pct: number;
  projected_cogs_inr: number;
  projected_gross_profit_inr: number;
  gross_profit_delta_inr: number;
  gross_margin_pct: number;
  projected_opex_inr: number;
  projected_operating_profit_inr: number;
  operating_profit_delta_inr: number;
  cash_runway_days_estimated: number | null;
  cash_runway_days_delta: number | null;
  break_even_revenue_inr: number | null;
}

export interface MitigationAction {
  title: string;
  impact: string;
  timeframe: string;
  feasibility: "High" | "Medium" | "Low";
}

export interface SimulationResult {
  scenario_type: ScenarioType;
  title: string;
  baseline_metrics: {
    has_sales_data?: boolean;
    annual_revenue_inr: number;
    monthly_revenue_inr: number;
    monthly_cogs_inr: number;
    monthly_gross_profit_inr: number;
    gross_margin_pct: number;
    monthly_opex_inr: number;
    monthly_operating_profit_inr: number;
    cash_balance_inr: number;
    baseline_runway_days: number;
    top_customer_name?: string;
    top_customer_spend_inr?: number;
    top_customer_share_pct?: number;
    baseline_dso_days?: number;
    [key: string]: unknown;
  };
  assumptions_applied: AssumptionItem[];
  missing_data_disclosures: string[];
  cases: ScenarioCaseResult[];
  ai_executive_summary: string;
  vulnerabilities_exposed: string[];
  mitigation_actions: MitigationAction[];
  disclaimer: string;
}

export interface ScenarioSimulateRequest {
  title: string;
  parameters: ScenarioParameterIn;
}

export interface ScenarioSaveRequest {
  title: string;
  scenario_type: ScenarioType;
  description?: string | null;
  parameters: ScenarioParameterIn;
  tags?: string[] | null;
}

export interface ScenarioUpdateRequest {
  title?: string | null;
  description?: string | null;
  parameters?: ScenarioParameterIn | null;
  tags?: string[] | null;
}

export interface ScenarioOut {
  id: number;
  business_id: number;
  owner_id: number;
  title: string;
  scenario_type: string;
  description: string | null;
  baseline_metrics: Record<string, unknown>;
  parameters: ScenarioParameterIn;
  projection_result: SimulationResult;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface ScenarioListResponse {
  items: ScenarioOut[];
  total: number;
}

export interface ScenarioComparisonItem {
  id: number;
  title: string;
  scenario_type: string;
  base_case_revenue_delta_inr: number;
  base_case_revenue_delta_pct: number;
  base_case_profit_delta_inr: number;
  base_case_runway_delta_days: number | null;
  top_vulnerability: string;
  created_at: string;
}

export interface ScenarioCompareResponse {
  scenarios: ScenarioComparisonItem[];
  comparison_summary: string;
  disclaimer: string;
}

export const whatIfScenarioService = {
  /** Run simulation in-memory without persisting. */
  async simulate(request: ScenarioSimulateRequest): Promise<SimulationResult> {
    return apiClient.post<SimulationResult>("/scenarios/simulate", request);
  },

  /** Save a simulated scenario. */
  async save(request: ScenarioSaveRequest): Promise<ScenarioOut> {
    return apiClient.post<ScenarioOut>("/scenarios", request);
  },

  /** List all saved scenarios for active business. */
  async list(): Promise<ScenarioListResponse> {
    return apiClient.get<ScenarioListResponse>("/scenarios");
  },

  /** Retrieve a single saved scenario. */
  async get(id: number): Promise<ScenarioOut> {
    return apiClient.get<ScenarioOut>(`/scenarios/${id}`);
  },

  /** Update scenario metadata or parameters. */
  async update(id: number, request: ScenarioUpdateRequest): Promise<ScenarioOut> {
    return apiClient.patch<ScenarioOut>(`/scenarios/${id}`, request);
  },

  /** Delete a saved scenario. */
  async delete(id: number): Promise<void> {
    await apiClient.delete<void>(`/scenarios/${id}`);
  },

  /** Compare 2-3 saved scenarios side-by-side. */
  async compare(scenarioIds: number[]): Promise<ScenarioCompareResponse> {
    return apiClient.post<ScenarioCompareResponse>("/scenarios/compare", {
      scenario_ids: scenarioIds,
    });
  },
};

export { ApiError };

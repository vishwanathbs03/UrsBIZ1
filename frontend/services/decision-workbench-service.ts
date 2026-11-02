"use client";

/**
 * Frontend client service for Business Decision Workbench (Phase 6.18 Extension).
 *
 * Connects to:
 *   POST   /api/v1/decisions/evaluate   evaluateDecision
 *   POST   /api/v1/decisions            createDecision
 *   GET    /api/v1/decisions            listDecisions
 *   GET    /api/v1/decisions/{id}       getDecision
 *   PATCH  /api/v1/decisions/{id}       updateDecision
 *   DELETE /api/v1/decisions/{id}       deleteDecision
 */

import { apiClient, ApiError } from "./api-client";

export interface DecisionEvidenceItem {
  source: string;
  metric: string;
  value: string | number | boolean | Record<string, unknown>;
  unit: string;
  observation_period: string;
  data_classification: "Observed Fact" | "Calculated Metric" | "User-Entered" | "Scenario Estimate";
  freshness: string;
}

export interface DecisionEstimatedImpact {
  has_calculation_inputs: boolean;
  revenue_delta_inr: number | null;
  revenue_delta_pct: number | null;
  margin_delta_pct: number | null;
  volume_delta_pct: number | null;
  payback_period_days: number | null;
  calculation_method: string;
  formula_applied: string;
  disclaimer: string;
}

export interface DecisionOptionEvaluation {
  option_id: string;
  title: string;
  description: string;
  supporting_evidence: DecisionEvidenceItem[];
  assumptions: string[];
  missing_information: string[];
  potential_benefits: string[];
  potential_risks: string[];
  estimated_impact: DecisionEstimatedImpact;
  confidence: number;
  limitations: string[];
  recommended_additional_data: string[];
}

export interface DecisionEvaluateRequest {
  decision_type:
    | "offer_discount"
    | "increase_price"
    | "customer_focus"
    | "expand_product_range"
    | "reduce_expenses"
    | "test_sales_channel"
    | "custom";
  objective: string;
  custom_parameters?: Record<string, unknown>;
}

export interface DecisionBaselineSnapshot {
  has_sales_data?: boolean;
  annual_revenue_inr?: number;
  average_order_value_inr?: number;
  total_orders?: number;
  repeat_customer_rate_pct?: number;
  top_product_name?: string;
  overall_health_score?: number;
  [key: string]: unknown;
}

export interface DecisionEvaluateResponse {
  decision_type: string;
  objective: string;
  baseline_snapshot: DecisionBaselineSnapshot;
  options: DecisionOptionEvaluation[];
  ai_executive_summary: string;
  recommended_option_id: string | null;
  data_freshness: string;
  evaluation_timestamp: string;
}

export interface DecisionCreateRequest {
  decision_type: string;
  title: string;
  objective: string;
  baseline_snapshot?: DecisionBaselineSnapshot;
  options: DecisionOptionEvaluation[];
  selected_option_id?: string | null;
  selected_option_title?: string | null;
  decision_rationale?: string | null;
  status?: "Draft" | "Evaluating" | "Decided" | "Implemented" | "Reviewed";
}

export interface DecisionUpdateRequest {
  title?: string;
  objective?: string;
  status?: "Draft" | "Evaluating" | "Decided" | "Implemented" | "Reviewed";
  selected_option_id?: string | null;
  selected_option_title?: string | null;
  decision_rationale?: string | null;
  review_status?: "Pending" | "Outcome_Observed" | "Abandoned";
  review_notes?: string | null;
  outcome_id?: number | null;
}

export interface DecisionOut {
  id: number;
  business_id: number;
  owner_id: number;
  decision_type: string;
  title: string;
  objective: string;
  status: string;
  baseline_snapshot: DecisionBaselineSnapshot;
  options: DecisionOptionEvaluation[];
  selected_option_id: string | null;
  selected_option_title: string | null;
  decision_rationale: string | null;
  decided_at: string | null;
  review_status: string;
  review_notes: string | null;
  outcome_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface DecisionListResponse {
  items: DecisionOut[];
  total: number;
}

export const decisionWorkbenchService = {
  async evaluateDecision(data: DecisionEvaluateRequest): Promise<DecisionEvaluateResponse> {
    return apiClient.post<DecisionEvaluateResponse>("/api/v1/decisions/evaluate", data);
  },

  async createDecision(data: DecisionCreateRequest): Promise<DecisionOut> {
    return apiClient.post<DecisionOut>("/api/v1/decisions", data);
  },

  async listDecisions(): Promise<DecisionListResponse> {
    return apiClient.get<DecisionListResponse>("/api/v1/decisions");
  },

  async getDecision(decisionId: number): Promise<DecisionOut> {
    return apiClient.get<DecisionOut>(`/api/v1/decisions/${decisionId}`);
  },

  async updateDecision(decisionId: number, data: DecisionUpdateRequest): Promise<DecisionOut> {
    return apiClient.patch<DecisionOut>(`/api/v1/decisions/${decisionId}`, data);
  },

  async deleteDecision(decisionId: number): Promise<{ deleted: boolean; id: number }> {
    return apiClient.delete<{ deleted: boolean; id: number }>(`/api/v1/decisions/${decisionId}`);
  },
};

export { ApiError };

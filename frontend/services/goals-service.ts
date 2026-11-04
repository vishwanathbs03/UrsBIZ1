"use client";

/**
 * Frontend client service for Business Goals & Progress Tracker (Prompt 6.24).
 *
 * Connects to authoritative backend endpoints under `/api/v1/goals`:
 *   GET    /api/v1/goals
 *   POST   /api/v1/goals
 *   GET    /api/v1/goals/{id}
 *   PUT    /api/v1/goals/{id}
 *   POST   /api/v1/goals/{id}/status
 *   POST   /api/v1/goals/{id}/progress
 *   POST   /api/v1/goals/{id}/evaluate
 *   DELETE /api/v1/goals/{id}
 *   GET    /api/v1/goals/{id}/history
 *   POST   /api/v1/goals/{id}/explain
 */

import { apiClient } from "./api-client";

export type GoalMeasurementMethod =
  | "AUTOMATED_METRIC"
  | "MANUAL_REPORTED"
  | "ESTIMATE";

export type GoalStatus =
  | "ACTIVE"
  | "PAUSED"
  | "COMPLETED"
  | "INCOMPLETE"
  | "EXPIRED"
  | "ARCHIVED";

export type GoalDataAvailability =
  | "AVAILABLE"
  | "MISSING_DATA"
  | "STALE_DATA"
  | "PENDING_PERIOD";

export type GoalMetricKey =
  | "monthly_revenue"
  | "customer_concentration"
  | "repeat_customer_rate"
  | "average_order_value"
  | "new_customers_count"
  | "sales_upload_frequency"
  | "digital_twin_health_score"
  | "manual";

export interface RelatedItem {
  id: string | number;
  type: string;
  title: string;
  status: string;
}

export interface BusinessGoalAudit {
  id: number;
  goal_id: number | null;
  business_id: number;
  changed_by_user_id: number | null;
  action: string;
  old_status?: string | null;
  new_status?: string | null;
  measured_value?: number | null;
  target_value?: number | null;
  progress_pct?: number | null;
  notes?: string | null;
  created_at: string;
}

export interface BusinessGoal {
  id: number;
  business_id: number;
  title: string;
  description?: string | null;
  timeframe?: string | null;
  priority: string;
  start_date?: string | null;
  target_date?: string | null;

  metric_key?: string | null;
  measurement_method: GoalMeasurementMethod;
  baseline_value?: number | null;
  target_value: number;
  current_value?: number | null;
  progress_pct?: number | null;
  remaining_gap?: number | null;
  unit: string;

  status: GoalStatus;
  status_notes?: string | null;

  data_availability: GoalDataAvailability;
  data_freshness_warning?: string | null;
  evidence_source: string;
  is_achieved: boolean;
  days_remaining?: number | null;
  last_evaluated_at?: string | null;

  created_at: string;
  updated_at: string;

  related_recommendations: RelatedItem[];
  related_decisions: RelatedItem[];
  audits: BusinessGoalAudit[];
}

export interface BusinessGoalListResponse {
  items: BusinessGoal[];
  total: number;
  active_count: number;
  completed_count: number;
  at_risk_count: number;
  stale_or_missing_data_count: number;
}

export interface BusinessGoalCreate {
  title: string;
  description?: string;
  metric_key?: string;
  measurement_method?: GoalMeasurementMethod;
  baseline_value?: number;
  target_value: number;
  unit?: string;
  start_date?: string;
  target_date?: string;
  timeframe?: string;
  priority?: string;
}

export interface BusinessGoalUpdate {
  title?: string;
  description?: string;
  target_value?: number;
  target_date?: string;
  priority?: string;
  status_notes?: string;
}

export interface BusinessGoalStatusUpdate {
  status: GoalStatus;
  notes?: string;
}

export interface BusinessGoalManualProgress {
  current_value: number;
  notes?: string;
}

export interface GoalAIExplanationResponse {
  goal_id: number;
  goal_title: string;
  trajectory: string;
  feasibility_assessment: string;
  analysis: string;
  suggested_actions: string[];
  evidence_summary: string;
}

export interface ListGoalsParams {
  status?: string;
  include_archived?: boolean;
}

class GoalsService {
  async listGoals(params?: ListGoalsParams): Promise<BusinessGoalListResponse> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.include_archived) query.set("include_archived", "true");

    const qs = query.toString();
    const endpoint = `/goals${qs ? `?${qs}` : ""}`;
    return apiClient.get<BusinessGoalListResponse>(endpoint);
  }

  async createGoal(payload: BusinessGoalCreate): Promise<BusinessGoal> {
    return apiClient.post<BusinessGoal>("/goals", payload);
  }

  async getGoal(goalId: number): Promise<BusinessGoal> {
    return apiClient.get<BusinessGoal>(`/goals/${goalId}`);
  }

  async updateGoal(goalId: number, payload: BusinessGoalUpdate): Promise<BusinessGoal> {
    return apiClient.put<BusinessGoal>(`/goals/${goalId}`, payload);
  }

  async updateStatus(
    goalId: number,
    payload: BusinessGoalStatusUpdate
  ): Promise<BusinessGoal> {
    return apiClient.post<BusinessGoal>(`/goals/${goalId}/status`, payload);
  }

  async recordProgress(
    goalId: number,
    payload: BusinessGoalManualProgress
  ): Promise<BusinessGoal> {
    return apiClient.post<BusinessGoal>(`/goals/${goalId}/progress`, payload);
  }

  async evaluateGoal(goalId: number): Promise<BusinessGoal> {
    return apiClient.post<BusinessGoal>(`/goals/${goalId}/evaluate`, {});
  }

  async archiveGoal(
    goalId: number
  ): Promise<{ success: boolean; archived: boolean; goal_id: number }> {
    return apiClient.delete<{ success: boolean; archived: boolean; goal_id: number }>(
      `/goals/${goalId}`
    );
  }

  async getGoalHistory(goalId: number): Promise<BusinessGoalAudit[]> {
    return apiClient.get<BusinessGoalAudit[]>(`/goals/${goalId}/history`);
  }

  async explainGoal(
    goalId: number,
    language: "en" | "kn" = "en"
  ): Promise<GoalAIExplanationResponse> {
    return apiClient.post<GoalAIExplanationResponse>(`/goals/${goalId}/explain`, {
      language,
    });
  }
}

export const goalsService = new GoalsService();

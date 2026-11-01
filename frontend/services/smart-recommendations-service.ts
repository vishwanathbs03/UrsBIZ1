/**
 * Service module for Context-Aware Smart Recommendations (Phase 5 Advanced Intelligence).
 */

import { apiClient } from "@/services/api-client";
import type {
  AdvancedRecommendationsOverviewResponse,
  BusinessSignalsFeedResponse,
  CompleteHistoryResponse,
  MonitoringEvaluationResponse,
  MonitoringPreferencesSchema,
  MonitoringPreferencesUpdate,
  OutcomeRecordingRequest,
  OutcomeTrackingResponse,
  PersonalizedGrowthStrategy,
  RecommendationAskRequest,
  RecommendationAskResponse,
  RecommendationEffectivenessResponse,
  RecommendationExplainResponse,
  RecommendationFeedbackCreate,
  RecommendationFeedbackResponse,
  RecommendationHistoryResponse,
  RecommendationPortfolioResponse,
  RecommendationStatus,
  ScenarioSimulationRequest,
  ScenarioSimulationResponse,
  SmartRecommendationsResponse,
} from "@/types/smart-recommendations";

export interface GetRecommendationsParams {
  category?: string;
  priority?: string;
  status?: string;
}

export const smartRecommendationsService = {
  getRecommendations: async (
    params?: GetRecommendationsParams
  ): Promise<SmartRecommendationsResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.category && params.category !== "all") {
      searchParams.set("category", params.category);
    }
    if (params?.priority && params.priority !== "all") {
      searchParams.set("priority", params.priority);
    }
    if (params?.status && params.status !== "all") {
      searchParams.set("status", params.status);
    }

    const qs = searchParams.toString();
    const endpoint = `/api/v1/recommendations${qs ? `?${qs}` : ""}`;
    return apiClient.get<SmartRecommendationsResponse>(endpoint);
  },

  getAdvancedOverview: async (): Promise<AdvancedRecommendationsOverviewResponse> => {
    return apiClient.get<AdvancedRecommendationsOverviewResponse>(
      "/api/v1/recommendations/advanced-overview"
    );
  },

  getGrowthStrategy: async (): Promise<PersonalizedGrowthStrategy> => {
    return apiClient.get<PersonalizedGrowthStrategy>(
      "/api/v1/recommendations/growth-strategy"
    );
  },

  simulateScenario: async (
    payload: ScenarioSimulationRequest
  ): Promise<ScenarioSimulationResponse> => {
    return apiClient.post<ScenarioSimulationResponse>(
      "/api/v1/recommendations/scenarios/simulate",
      payload
    );
  },

  submitFeedback: async (
    payload: RecommendationFeedbackCreate
  ): Promise<RecommendationFeedbackResponse> => {
    return apiClient.post<RecommendationFeedbackResponse>(
      "/api/v1/recommendations/feedback",
      payload
    );
  },

  updateStatus: async (
    recommendationId: string,
    status: RecommendationStatus,
    notes?: string
  ): Promise<{ status: string; status_updated_at: string; notes?: string }> => {
    return apiClient.patch(
      `/api/v1/recommendations/${encodeURIComponent(recommendationId)}/status`,
      { status, notes }
    );
  },

  explainRecommendation: async (
    recommendationId: string
  ): Promise<RecommendationExplainResponse> => {
    return apiClient.post(
      `/api/v1/recommendations/${encodeURIComponent(recommendationId)}/explain`,
      {}
    );
  },

  askQuestion: async (
    payload: RecommendationAskRequest
  ): Promise<RecommendationAskResponse> => {
    return apiClient.post<RecommendationAskResponse>(
      "/api/v1/recommendations/ask",
      payload
    );
  },

  getPortfolio: async (): Promise<RecommendationPortfolioResponse> => {
    return apiClient.get<RecommendationPortfolioResponse>(
      "/api/v1/recommendations/portfolio"
    );
  },

  recordOutcome: async (
    recommendationId: string,
    payload: OutcomeRecordingRequest
  ): Promise<OutcomeTrackingResponse> => {
    return apiClient.post<OutcomeTrackingResponse>(
      `/api/v1/recommendations/${encodeURIComponent(recommendationId)}/outcome`,
      payload
    );
  },

  getOutcome: async (
    recommendationId: string,
    windowDays: number = 30
  ): Promise<OutcomeTrackingResponse> => {
    return apiClient.get<OutcomeTrackingResponse>(
      `/api/v1/recommendations/${encodeURIComponent(recommendationId)}/outcome?window_days=${windowDays}`
    );
  },

  getEffectiveness: async (): Promise<RecommendationEffectivenessResponse> => {
    return apiClient.get<RecommendationEffectivenessResponse>(
      "/api/v1/recommendations/effectiveness/analytics"
    );
  },

  getRecommendationHistory: async (
    recommendationId: string
  ): Promise<RecommendationHistoryResponse> => {
    return apiClient.get<RecommendationHistoryResponse>(
      `/api/v1/recommendations/${encodeURIComponent(recommendationId)}/history`
    );
  },

  getCompleteHistory: async (
    limit: number = 100
  ): Promise<CompleteHistoryResponse> => {
    return apiClient.get<CompleteHistoryResponse>(
      `/api/v1/recommendations/history/all?limit=${limit}`
    );
  },

  // ------------------------------------------------------------------------- //
  // Proactive Monitoring & Signals Feed (Phase 5)                             //
  // ------------------------------------------------------------------------- //

  getSignalsFeed: async (
    minSeverity?: string
  ): Promise<BusinessSignalsFeedResponse> => {
    const q = minSeverity ? `?min_severity=${encodeURIComponent(minSeverity)}` : "";
    return apiClient.get<BusinessSignalsFeedResponse>(
      `/api/v1/recommendations/monitoring/signals${q}`
    );
  },

  evaluateMonitoring: async (): Promise<MonitoringEvaluationResponse> => {
    return apiClient.post<MonitoringEvaluationResponse>(
      "/api/v1/recommendations/monitoring/evaluate",
      {}
    );
  },

  getMonitoringPreferences: async (): Promise<MonitoringPreferencesSchema> => {
    return apiClient.get<MonitoringPreferencesSchema>(
      "/api/v1/recommendations/monitoring/preferences"
    );
  },

  updateMonitoringPreferences: async (
    payload: MonitoringPreferencesUpdate
  ): Promise<MonitoringPreferencesSchema> => {
    return apiClient.put<MonitoringPreferencesSchema>(
      "/api/v1/recommendations/monitoring/preferences",
      payload
    );
  },

  dismissSignal: async (eventId: string): Promise<{ status: string }> => {
    return apiClient.post<{ status: string }>(
      `/api/v1/recommendations/monitoring/signals/${encodeURIComponent(eventId)}/dismiss`,
      {}
    );
  },
};

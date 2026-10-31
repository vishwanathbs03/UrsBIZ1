/**
 * Service module for Context-Aware Smart Recommendations (Phase 5).
 */

import { apiClient } from "@/services/api-client";
import type {
  RecommendationExplainResponse,
  RecommendationStatus,
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
};

"use client";

/**
 * Frontend client service for AI Answer Feedback and Quality Evaluation (Phase 6.28).
 *
 * Connects to backend endpoints under /api/v1/chat:
 *   POST   /messages/{message_id}/feedback
 *   GET    /messages/{message_id}/feedback
 *   PATCH  /messages/{message_id}/feedback
 *   DELETE /messages/{message_id}/feedback
 *   GET    /feedback/analytics?days={days}
 */

import { apiClient } from "./api-client";

export type FeedbackCategory =
  | "Helpful"
  | "Incorrect Information"
  | "Missing Evidence"
  | "Outdated Data"
  | "Difficult to Understand";

export const FEEDBACK_CATEGORIES: FeedbackCategory[] = [
  "Helpful",
  "Incorrect Information",
  "Missing Evidence",
  "Outdated Data",
  "Difficult to Understand",
];

export interface ChatFeedbackResponse {
  id: number;
  message_id: number;
  business_id: number;
  user_id: number;
  rating: number; // 1 to 5
  is_positive: boolean;
  feedback_category: FeedbackCategory;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatFeedbackCreateRequest {
  rating: number; // 1 to 5
  feedback_category: FeedbackCategory;
  notes?: string | null;
}

export interface ChatFeedbackUpdateRequest {
  rating?: number | null;
  feedback_category?: FeedbackCategory | null;
  notes?: string | null;
}

export interface GroundingCorrelationMetrics {
  grounded_message_count: number;
  grounded_average_rating: number;
  fallback_message_count: number;
  fallback_average_rating: number;
  fallback_unhelpful_rate: number;
}

export interface ChatFeedbackAnalytics {
  business_id: number;
  lookback_days: number;
  total_feedback_count: number;
  helpful_count: number;
  unhelpful_count: number;
  helpfulness_rate: number;
  average_rating: number;
  quality_score: number;
  category_distribution: Record<FeedbackCategory, number>;
  grounding_correlation: GroundingCorrelationMetrics;
  generated_at: string;
}

export const chatFeedbackService = {
  /**
   * Submit or update structured feedback for an AI assistant message.
   */
  async submitFeedback(
    messageId: number,
    data: ChatFeedbackCreateRequest,
  ): Promise<ChatFeedbackResponse> {
    return apiClient.post<ChatFeedbackResponse>(
      `/api/v1/chat/messages/${messageId}/feedback`,
      data,
    );
  },

  /**
   * Retrieve current user's feedback on a specific message.
   */
  async getMessageFeedback(
    messageId: number,
  ): Promise<ChatFeedbackResponse | null> {
    return apiClient.get<ChatFeedbackResponse | null>(
      `/api/v1/chat/messages/${messageId}/feedback`,
    );
  },

  /**
   * Partially update existing feedback on an assistant message.
   */
  async updateFeedback(
    messageId: number,
    data: ChatFeedbackUpdateRequest,
  ): Promise<ChatFeedbackResponse> {
    return apiClient.patch<ChatFeedbackResponse>(
      `/api/v1/chat/messages/${messageId}/feedback`,
      data,
    );
  },

  /**
   * Remove feedback record (supporting zero-retention / privacy compliance).
   */
  async deleteFeedback(messageId: number): Promise<void> {
    return apiClient.delete<void>(
      `/api/v1/chat/messages/${messageId}/feedback`,
    );
  },

  /**
   * Fetch aggregate quality evaluation analytics and grounding correlation metrics.
   */
  async getQualityAnalytics(days: number = 30): Promise<ChatFeedbackAnalytics> {
    return apiClient.get<ChatFeedbackAnalytics>(
      `/api/v1/chat/feedback/analytics?days=${days}`,
    );
  },
};

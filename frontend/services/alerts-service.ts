"use client";

/**
 * Frontend client service for Business Alerts & Event Centre (Prompt 6.22).
 *
 * Connects to authoritative backend endpoints:
 *   GET    /api/v1/alerts
 *   GET    /api/v1/alerts/summary
 *   POST   /api/v1/alerts/evaluate
 *   GET    /api/v1/alerts/{eventId}
 *   PATCH  /api/v1/alerts/{eventId}/status
 *   GET    /api/v1/alerts/{eventId}/history
 *   POST   /api/v1/alerts/{eventId}/explain
 */

import { apiClient, ApiError } from "./api-client";

export type EventSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL";
export type EventNature = "CONFIRMED_EVENT" | "WARNING" | "ESTIMATE" | "ASSUMPTION";
export type EventStatus = "NEW" | "ACKNOWLEDGED" | "RESOLVED" | "DISMISSED";

export interface BusinessSignalItem {
  event_id: string;
  business_id: number;
  event_type: string;
  event_nature: EventNature | string;
  source: string;
  relevant_entity?: string | null;
  detected_at: string;
  evidence: Record<string, unknown>;
  severity: EventSeverity;
  priority_score: number;
  data_period: string;
  event_version: number;
  title: string;
  what_changed: string;
  why_it_matters: string;
  suggested_action: string;
  confidence: number;
  is_suppressed: boolean;
  suppression_reason?: string | null;
  escalation_level: number;
  linked_recommendation_id?: string | null;
  status: EventStatus | string;
  resolved_at?: string | null;
}

export interface AlertListResponse {
  business_id: number;
  total: number;
  limit: number;
  offset: number;
  alerts: BusinessSignalItem[];
}

export interface AlertSummaryResponse {
  business_id: number;
  total_alerts: number;
  new_count: number;
  acknowledged_count: number;
  resolved_count: number;
  dismissed_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_and_info_count: number;
  confirmed_events_count: number;
  warnings_count: number;
  estimates_count: number;
  assumptions_count: number;
  last_evaluated_at?: string | null;
}

export interface AlertStatusUpdate {
  status: "ACKNOWLEDGED" | "RESOLVED" | "DISMISSED";
  reason?: string;
}

export interface AlertAuditHistoryItem {
  id: number;
  event_id: string;
  business_id: number;
  previous_status: string;
  new_status: string;
  changed_by_user_id: number;
  changed_at: string;
  reason?: string | null;
}

export interface AlertExplainResponse {
  event_id: string;
  title: string;
  severity: string;
  event_nature: string;
  explanation: string;
  language: string;
  provider_used: string;
  is_fallback: boolean;
}

export interface ListAlertsParams {
  severity?: string;
  status?: string;
  event_nature?: string;
  include_suppressed?: boolean;
  limit?: number;
  offset?: number;
}

class AlertsService {
  async listAlerts(params?: ListAlertsParams): Promise<AlertListResponse> {
    const query = new URLSearchParams();
    if (params?.severity) query.set("severity", params.severity);
    if (params?.status) query.set("status", params.status);
    if (params?.event_nature) query.set("event_nature", params.event_nature);
    if (params?.include_suppressed) query.set("include_suppressed", "true");
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.offset !== undefined) query.set("offset", String(params.offset));

    const qs = query.toString();
    const endpoint = `/alerts${qs ? `?${qs}` : ""}`;
    return apiClient.get<AlertListResponse>(endpoint);
  }

  async getAlertsSummary(): Promise<AlertSummaryResponse> {
    return apiClient.get<AlertSummaryResponse>("/alerts/summary");
  }

  async evaluateAlerts(): Promise<unknown> {
    return apiClient.post("/alerts/evaluate", {});
  }

  async getAlert(eventId: string): Promise<BusinessSignalItem> {
    return apiClient.get<BusinessSignalItem>(`/alerts/${encodeURIComponent(eventId)}`);
  }

  async updateAlertStatus(
    eventId: string,
    payload: AlertStatusUpdate
  ): Promise<BusinessSignalItem> {
    return apiClient.patch<BusinessSignalItem>(
      `/alerts/${encodeURIComponent(eventId)}/status`,
      payload
    );
  }

  async getAlertHistory(eventId: string): Promise<AlertAuditHistoryItem[]> {
    return apiClient.get<AlertAuditHistoryItem[]>(
      `/alerts/${encodeURIComponent(eventId)}/history`
    );
  }

  async explainAlert(
    eventId: string,
    language: "en" | "kn" = "en"
  ): Promise<AlertExplainResponse> {
    return apiClient.post<AlertExplainResponse>(
      `/alerts/${encodeURIComponent(eventId)}/explain`,
      { language }
    );
  }
}

export const alertsService = new AlertsService();

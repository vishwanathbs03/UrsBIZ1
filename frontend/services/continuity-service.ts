/**
 * Business Continuity & System Resiliency Service (Phase 6.30).
 *
 * Fetches real-time status of LLM circuit breaker, database operational mode,
 * and deterministic fallback safeguards across English and Kannada.
 */

import { apiClient } from "./api-client";

export type ContinuityMode =
  | "OPERATIONAL"
  | "RULE_ENGINE_FALLBACK"
  | "DEGRADED_READONLY"
  | "OFFLINE";

export interface DatabaseContinuityStatus {
  status: "ok" | "degraded";
  mode: "read_write" | "read_only";
  detail: string;
}

export interface AISubsystemContinuityStatus {
  status: "operational" | "degraded" | "offline";
  provider: string;
  circuit_breaker: "CLOSED" | "OPEN" | "HALF_OPEN";
  fallback_active: boolean;
  metrics: Record<string, unknown>;
}

export interface KnowledgeContinuityStatus {
  status: "ok" | "degraded";
  detail: string;
}

export interface SystemContinuityStatus {
  system_mode: ContinuityMode;
  database: DatabaseContinuityStatus;
  ai_subsystem: AISubsystemContinuityStatus;
  knowledge: KnowledgeContinuityStatus;
  active_safeguards: string[];
  notice_en: string;
  notice_kn: string;
  can_read: boolean;
  can_write: boolean;
}

export const continuityService = {
  getStatus: async (): Promise<SystemContinuityStatus> => {
    return apiClient.get<SystemContinuityStatus>("/api/v1/health/continuity");
  },

  simulateAction: async (
    action: "trip_ai_circuit" | "reset_ai_circuit" | "simulate_db_degraded" | "reset_all",
  ): Promise<SystemContinuityStatus> => {
    return apiClient.post<SystemContinuityStatus>("/api/v1/health/continuity/simulate", { action });
  },
};

"use client";

/**
 * Frontend client service for Integration Readiness and Connector Framework (Phase 6.27).
 *
 * Connects to backend endpoints under /api/v1/integrations:
 *   GET    /catalogue
 *   GET    /connections
 *   POST   /connections
 *   GET    /connections/{id}
 *   PATCH  /connections/{id}/config
 *   PUT    /connections/{id}/credentials
 *   POST   /connections/{id}/test
 *   POST   /connections/{id}/connect
 *   POST   /connections/{id}/disconnect
 *   DELETE /connections/{id}
 *   POST   /connections/{id}/sync
 *   GET    /connections/{id}/syncs
 *   GET    /syncs
 *   GET    /audits
 */

import { apiClient } from "./api-client";

export type ConnectionStatus =
  | "NOT_CONFIGURED"
  | "CONFIGURED"
  | "CONNECTING"
  | "CONNECTED"
  | "ERROR"
  | "DISCONNECTED"
  | "DISABLED"
  | "REAUTH_REQUIRED";

export type SyncExecutionStatus =
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED";

export type OperationalStatus =
  | "OPERATIONAL"
  | "BETA"
  | "READY_FOR_CREDENTIALS"
  | "COMING_SOON";

export interface ConfigFieldOut {
  key: string;
  label: string;
  field_type: string; // "text", "password", "number", "select", "url"
  required: boolean;
  description: string;
  default_value?: unknown;
  options?: string[] | null;
  is_secret: boolean;
}

export interface ConnectorCatalogueItem {
  connector_id: string;
  name: string;
  provider: string;
  version: string;
  description: string;
  capabilities: string[];
  auth_method: string;
  sync_direction: string;
  operational_status: OperationalStatus;
  known_limitations: string[];
  config_fields: ConfigFieldOut[];
}

export interface ConnectionOut {
  id: number;
  business_id: number;
  connector_id: string;
  name: string;
  status: ConnectionStatus;
  configuration: Record<string, unknown>;
  has_credentials: boolean;
  masked_credentials: Record<string, string>;
  credential_fingerprint?: string | null;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  last_error_category?: string | null;
  last_error_message?: string | null;
  sync_cursor?: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConnectionCreateReq {
  connector_id: string;
  name: string;
  configuration: Record<string, unknown>;
  credentials: Record<string, unknown>;
}

export interface ConnectionConfigUpdateReq {
  configuration: Record<string, unknown>;
}

export interface CredentialRotateReq {
  credentials: Record<string, unknown>;
}

export interface ConnectionTestResultOut {
  success: boolean;
  status: string;
  message: string;
  tested_at: string;
}

export interface SyncTriggerReq {
  trigger_type?: string;
  batch_limit?: number;
}

export interface SyncExecutionOut {
  id: number;
  business_id: number;
  connection_id: number;
  connector_id: string;
  execution_id: string;
  trigger_type: string;
  status: SyncExecutionStatus;
  records_discovered: number;
  records_imported: number;
  records_skipped: number;
  duplicate_count: number;
  validation_failure_count: number;
  error_category?: string | null;
  error_message?: string | null;
  retry_count: number;
  sync_cursor_before?: string | null;
  sync_cursor_after?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  summary?: Record<string, unknown> | null;
  created_at: string;
}

export interface SyncExecutionListResponse {
  items: SyncExecutionOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface IntegrationAuditOut {
  id: number;
  business_id: number;
  connection_id?: number | null;
  connector_id?: string | null;
  actor_user_id?: number | null;
  event_type: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface IntegrationAuditListResponse {
  items: IntegrationAuditOut[];
  total: number;
  page: number;
  page_size: number;
}

export const integrationService = {
  // Catalogue
  getCatalogue: async (): Promise<ConnectorCatalogueItem[]> => {
    return apiClient.get<ConnectorCatalogueItem[]>("/api/v1/integrations/catalogue");
  },

  // Connections
  getConnections: async (): Promise<ConnectionOut[]> => {
    return apiClient.get<ConnectionOut[]>("/api/v1/integrations/connections");
  },

  getConnection: async (id: number): Promise<ConnectionOut> => {
    return apiClient.get<ConnectionOut>(`/api/v1/integrations/connections/${id}`);
  },

  createConnection: async (req: ConnectionCreateReq): Promise<ConnectionOut> => {
    return apiClient.post<ConnectionOut>("/api/v1/integrations/connections", req);
  },

  updateConfiguration: async (
    id: number,
    req: ConnectionConfigUpdateReq
  ): Promise<ConnectionOut> => {
    return apiClient.patch<ConnectionOut>(`/api/v1/integrations/connections/${id}/config`, req);
  },

  rotateCredentials: async (id: number, req: CredentialRotateReq): Promise<ConnectionOut> => {
    return apiClient.put<ConnectionOut>(`/api/v1/integrations/connections/${id}/credentials`, req);
  },

  testConnection: async (id: number): Promise<ConnectionTestResultOut> => {
    return apiClient.post<ConnectionTestResultOut>(`/api/v1/integrations/connections/${id}/test`);
  },

  connect: async (id: number): Promise<ConnectionOut> => {
    return apiClient.post<ConnectionOut>(`/api/v1/integrations/connections/${id}/connect`);
  },

  disconnect: async (id: number): Promise<ConnectionOut> => {
    return apiClient.post<ConnectionOut>(`/api/v1/integrations/connections/${id}/disconnect`);
  },

  deleteConnection: async (id: number): Promise<void> => {
    return apiClient.delete<void>(`/api/v1/integrations/connections/${id}`);
  },

  // Sync
  triggerSync: async (id: number, req: SyncTriggerReq = {}): Promise<SyncExecutionOut> => {
    return apiClient.post<SyncExecutionOut>(`/api/v1/integrations/connections/${id}/sync`, req);
  },

  getConnectionSyncs: async (
    id: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<SyncExecutionListResponse> => {
    return apiClient.get<SyncExecutionListResponse>(
      `/api/v1/integrations/connections/${id}/syncs?page=${page}&page_size=${pageSize}`
    );
  },

  getAllSyncs: async (
    page: number = 1,
    pageSize: number = 20
  ): Promise<SyncExecutionListResponse> => {
    return apiClient.get<SyncExecutionListResponse>(
      `/api/v1/integrations/syncs?page=${page}&page_size=${pageSize}`
    );
  },

  // Audits
  getAudits: async (
    page: number = 1,
    pageSize: number = 20
  ): Promise<IntegrationAuditListResponse> => {
    return apiClient.get<IntegrationAuditListResponse>(
      `/api/v1/integrations/audits?page=${page}&page_size=${pageSize}`
    );
  },
};

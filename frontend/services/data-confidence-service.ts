"use client";

/**
 * Frontend client service for Data Quality and Business Data Confidence Centre (Phase 6.20 Extension).
 *
 * Connects to:
 *   GET /api/v1/data-confidence         - Full confidence dashboard & insight matrix
 *   GET /api/v1/data-confidence/report  - Downloadable audit report
 */

import { apiClient, ApiError } from "./api-client";

export interface IngestionReconciliationSummary {
  total_uploads_count: number;
  total_rows_imported: number;
  valid_rows_ingested: number;
  duplicate_rows_excluded: number;
  rejected_rows_count: number;
  valid_row_rate_pct: number;
  duplicate_row_rate_pct: number;
  gross_uploaded_revenue_inr: number;
  duplicate_revenue_excluded_inr: number;
  analytical_revenue_inr: number;
  reconciliation_basis_note: string;
}

export interface ObservationWindowSummary {
  earliest_transaction_date: string | null;
  latest_transaction_date: string | null;
  observation_window_days: number;
  days_since_last_transaction: number | null;
  last_upload_timestamp: string | null;
  freshness_status: "FRESH" | "POTENTIALLY_STALE" | "EXPIRED_OR_UNAVAILABLE";
  freshness_description: string;
  unconfirmed_gaps_count: number;
  unconfirmed_gaps: Array<{
    start_date: string;
    end_date: string;
    gap_days: number;
    classification: string;
    note: string;
  }>;
}

export interface InsightReadinessItem {
  module_key: string;
  module_name: string;
  confidence_level: "High" | "Medium" | "Low" | "Degraded" | "Insufficient";
  confidence_score: number;
  readiness_status: "Ready" | "Degraded with Disclosures" | "Blocked by Missing Data";
  impact_explanation: string;
  missing_prerequisites: string[];
}

export interface DataAnomalySummary {
  anomaly_type: string;
  source_module: string;
  record_identifier: string | null;
  description: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  is_blocking: boolean;
}

export interface DataImprovementAction {
  priority: "High" | "Medium" | "Low";
  title: string;
  description: string;
  impact_on_insights: string;
  action_type: "upload_sales" | "complete_profile" | "map_customers" | "review_outliers" | "fill_gaps";
}

export interface DataConfidenceCentreResponse {
  business_id: number;
  audit_timestamp: string;
  overall_confidence_score: number;
  overall_quality_status: "VERIFIED" | "PROVISIONAL" | "SUSPECT" | "INSUFFICIENT";
  quality_status_badge: string;
  ingestion_summary: IngestionReconciliationSummary;
  observation_window: ObservationWindowSummary;
  insight_confidence_matrix: InsightReadinessItem[];
  anomalies_detected: DataAnomalySummary[];
  actionable_improvement_checklist: DataImprovementAction[];
  data_limitations: string[];
  disclaimer: string;
}

export interface DataQualityReportPayload {
  business_id: number;
  report_title: string;
  audit_timestamp: string;
  overall_quality_status: string;
  overall_confidence_score: number;
  ingestion_reconciliation: IngestionReconciliationSummary;
  observation_window: ObservationWindowSummary;
  insight_confidence_matrix: InsightReadinessItem[];
  anomalies_detected: DataAnomalySummary[];
  actionable_recommendations: DataImprovementAction[];
  provenance_disclaimer: string;
}

export const dataConfidenceService = {
  /** Fetch comprehensive data confidence dashboard and insight readiness matrix. */
  async getConfidence(): Promise<DataConfidenceCentreResponse> {
    return apiClient.get<DataConfidenceCentreResponse>("/data-confidence");
  },

  /** Fetch exportable data quality and provenance audit report. */
  async getAuditReport(): Promise<DataQualityReportPayload> {
    return apiClient.get<DataQualityReportPayload>("/data-confidence/report");
  },
};

export { ApiError };

"use client";

/**
 * Frontend client service for Reports & Evidence Export Centre (Prompt 6.25).
 *
 * Connects to authoritative backend endpoints under `/api/v1/reports`:
 *   GET    /api/v1/reports/catalog
 *   POST   /api/v1/reports/preview
 *   POST   /api/v1/reports/generate
 *   GET    /api/v1/reports/history
 *   GET    /api/v1/reports/{id}
 *   GET    /api/v1/reports/{id}/download
 *   DELETE /api/v1/reports/{id}
 */

import { apiClient } from "./api-client";
import { env } from "@/lib/env";

export type ReportType =
  | "executive_summary"
  | "sales_revenue_performance"
  | "customer_performance"
  | "product_performance"
  | "decisions_summary"
  | "alerts_summary"
  | "goals_progress"
  | "data_quality_audit"
  | "what_if_scenario_comparison";

export type ReportCategory =
  | "executive"
  | "performance"
  | "strategy_and_governance"
  | "audit_and_quality";

export type ReportFileFormat = "pdf" | "csv" | "xlsx";

export type ReportCoverageStatus =
  | "AVAILABLE"
  | "PARTIAL"
  | "MISSING_DATA"
  | "UNVERIFIED_GAP";

export interface ReportCatalogItem {
  report_type: ReportType;
  category: ReportCategory;
  title: string;
  description: string;
  supported_formats: ReportFileFormat[];
  target_audience: string;
  required_data_sources: string[];
  estimated_generation_time_sec: number;
}

export interface ReportCatalogResponse {
  catalog: ReportCatalogItem[];
  total_reports: number;
}

export interface ReportTableData {
  title: string;
  headers: string[];
  rows: (string | number)[][];
}

export interface ReportProvenance {
  metric_name: string;
  calculation_method: string;
  evidence_source: string;
  event_nature: string;
  observation_window: string;
  data_freshness?: string;
  assumptions: string[];
  limitations: string[];
  disclaimer: string;
}

export interface ReportPreviewRequest {
  report_type: ReportType;
  period_start?: string;
  period_end?: string;
}

export interface ReportPreviewResponse {
  report_type: ReportType;
  category: string;
  title: string;
  period_start: string;
  period_end: string;
  data_coverage_status: ReportCoverageStatus;
  findings: string[];
  summary_kpis: Record<string, string | number | boolean>;
  sample_tables: ReportTableData[];
  provenance: ReportProvenance;
  preview_disclaimer: string;
}

export interface ReportGenerateRequest {
  report_type: ReportType;
  file_format: ReportFileFormat;
  period_start?: string;
  period_end?: string;
  include_ai_summary?: boolean;
}

export interface ReportItemOut {
  id: number;
  business_id: number;
  user_id?: number | null;
  report_type: ReportType;
  category: string;
  title: string;
  file_format: ReportFileFormat;
  file_size_bytes: number;
  period_start: string;
  period_end: string;
  status: "COMPLETED" | "FAILED" | "PENDING";
  data_coverage_status: ReportCoverageStatus;
  download_count: number;
  last_downloaded_at?: string | null;
  created_at: string;
  download_url: string;
}

export interface ReportHistoryResponse {
  items: ReportItemOut[];
  total: number;
  page: number;
  page_size: number;
}

class ReportsService {
  /**
   * Fetch catalogue of all available report types.
   */
  async getCatalog(): Promise<ReportCatalogResponse> {
    return apiClient.get<ReportCatalogResponse>("/api/v1/reports/catalog");
  }

  /**
   * Preview a report before generating a formal export.
   */
  async previewReport(req: ReportPreviewRequest): Promise<ReportPreviewResponse> {
    return apiClient.post<ReportPreviewResponse>("/api/v1/reports/preview", req);
  }

  /**
   * Generate and persist an authoritative evidence-backed report.
   */
  async generateReport(req: ReportGenerateRequest): Promise<ReportItemOut> {
    return apiClient.post<ReportItemOut>("/api/v1/reports/generate", req);
  }

  /**
   * Fetch historical exports for the active business.
   */
  async getHistory(page = 1, pageSize = 20): Promise<ReportHistoryResponse> {
    return apiClient.get<ReportHistoryResponse>("/api/v1/reports/history", {
      query: { page, page_size: pageSize },
    });
  }

  /**
   * Fetch a single report details by ID.
   */
  async getReport(id: number): Promise<ReportItemOut> {
    return apiClient.get<ReportItemOut>(`/api/v1/reports/${id}`);
  }

  /**
   * Soft-delete/archive a report by ID.
   */
  async deleteReport(id: number): Promise<{ success: boolean; message: string }> {
    return apiClient.delete<{ success: boolean; message: string }>(`/api/v1/reports/${id}`);
  }

  /**
   * Trigger direct file download for a generated report.
   */
  async downloadReport(id: number, filename?: string): Promise<void> {
    const base = env.apiBaseUrl.replace(/\/+$/, "");
    const downloadUrl = `${base}/api/v1/reports/${id}/download`;

    const res = await fetch(downloadUrl, {
      method: "GET",
      credentials: "include",
    });

    if (!res.ok) {
      throw new Error(`Failed to download report (HTTP ${res.status})`);
    }

    const blob = await res.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename || `report_${id}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(objectUrl);
  }
}

export const reportsService = new ReportsService();

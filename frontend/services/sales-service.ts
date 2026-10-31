/**
 * Sales Service — API client integration for Phase 3 Sales Intelligence.
 */

import { apiClient } from "@/services/api-client";

export interface ColumnMapping {
  transaction_date: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  customer_name?: string;
  customer_id?: string;
  product_id?: string;
  total_amount?: string;
  invoice_id?: string;
}

export interface FilePreviewResponse {
  filename: string;
  file_format: string;
  file_size_bytes: number;
  total_rows_estimate: number;
  detected_headers: string[];
  suggested_mapping: Record<string, string | null>;
  sample_rows: Record<string, any>[];
  confidence_scores: Record<string, number>;
}

export interface QualityIssue {
  row_index: number;
  issue_type: string;
  severity: "error" | "warning";
  message: string;
  field?: string;
  value?: any;
}

export interface DataQualitySummary {
  total_rows_received: number;
  valid_rows: number;
  invalid_rows: number;
  flagged_rows: number;
  missing_dates: number;
  missing_customer_or_product: number;
  invalid_quantities: number;
  invalid_or_missing_prices: number;
  duplicate_transactions: number;
  calculated_revenues: number;
  quality_score: number;
  issues: QualityIssue[];
}

export interface SalesUploadResponse {
  upload_id: number;
  business_id: number;
  filename: string;
  file_format: string;
  status: string;
  row_count: number;
  valid_row_count: number;
  invalid_row_count: number;
  quality_summary: DataQualitySummary;
}

export interface SalesUploadListItem {
  id: number;
  filename: string;
  file_format: string;
  file_size_bytes: number;
  row_count: number;
  valid_row_count: number;
  invalid_row_count: number;
  status: string;
  quality_score: number;
  created_at: string;
}

export interface SalesSummaryResponse {
  has_sales_data: boolean;
  total_transactions: number;
  total_revenue: number;
  total_quantity: number;
  unique_customers: number;
  unique_products: number;
  first_transaction_date?: string;
  latest_transaction_date?: string;
  date_range_days: number;
  latest_upload_id?: number;
  latest_upload_filename?: string;
}

export interface CustomerMetricItem {
  customer_name: string;
  customer_id?: string;
  total_revenue: number;
  total_orders: number;
  first_purchase_date: string;
  latest_purchase_date: string;
  average_order_value: number;
  is_repeat: boolean;
  status: "Active" | "Declining" | "New";
}

export interface CustomerInsightsResponse {
  total_customers: number;
  new_customers: number;
  repeat_customers: number;
  repeat_rate_pct: number;
  average_order_value: number;
  purchase_frequency: number;
  top_customers_by_revenue: CustomerMetricItem[];
  declining_customers: CustomerMetricItem[];
  history_span_days: number;
  declining_threshold_days: number;
  inactivity_definition: string;
}

export interface ProductMetricItem {
  product_name: string;
  product_id?: string;
  total_revenue: number;
  total_quantity_sold: number;
  average_unit_price: number;
  total_transactions: number;
  first_sale_date: string;
  latest_sale_date: string;
  trend: "Increasing" | "Stable" | "Decreasing" | "Insufficient History";
  quantity_delta_pct?: number;
}

export interface ProductInsightsResponse {
  total_products: number;
  total_quantity_sold: number;
  top_products_by_revenue: ProductMetricItem[];
  fast_moving_products_by_volume: ProductMetricItem[];
  increasing_sales_products: ProductMetricItem[];
  decreasing_sales_products: ProductMetricItem[];
  insufficient_history_products: ProductMetricItem[];
}

export interface TimeSeriesPoint {
  period: string;
  revenue: number;
  quantity: number;
  transaction_count: number;
  unique_customers: number;
  has_data: boolean;
}

export interface SalesTimeSeriesResponse {
  granularity: "monthly" | "weekly" | "daily";
  points: TimeSeriesPoint[];
  total_periods: number;
  active_periods: number;
  start_date?: string;
  end_date?: string;
}

export const salesService = {
  async previewUpload(file: File): Promise<FilePreviewResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/v1/sales/upload/preview", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Preview failed" }));
      throw new Error(err.detail || `Upload preview failed with status ${res.status}`);
    }
    return res.json();
  },

  async confirmUpload(file: File, mapping: ColumnMapping): Promise<SalesUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mapping", JSON.stringify(mapping));

    const res = await fetch("/api/v1/sales/upload/confirm", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Ingestion failed" }));
      throw new Error(err.detail || `Ingestion failed with status ${res.status}`);
    }
    return res.json();
  },

  async getSummary(): Promise<SalesSummaryResponse> {
    return apiClient.get<SalesSummaryResponse>("/api/v1/sales/summary");
  },

  async getCustomerInsights(): Promise<CustomerInsightsResponse> {
    return apiClient.get<CustomerInsightsResponse>("/api/v1/sales/customer-insights");
  },

  async getProductInsights(): Promise<ProductInsightsResponse> {
    return apiClient.get<ProductInsightsResponse>("/api/v1/sales/product-insights");
  },

  async getTimeSeries(granularity: "monthly" | "weekly" | "daily" = "monthly"): Promise<SalesTimeSeriesResponse> {
    return apiClient.get<SalesTimeSeriesResponse>("/api/v1/sales/time-series", {
      query: { granularity },
    });
  },

  async listUploads(): Promise<SalesUploadListItem[]> {
    return apiClient.get<SalesUploadListItem[]>("/api/v1/sales/uploads");
  },

  async deleteUpload(uploadId: number): Promise<{ status: string; upload_id: number }> {
    return apiClient.delete<{ status: string; upload_id: number }>(`/api/v1/sales/uploads/${uploadId}`);
  },
};

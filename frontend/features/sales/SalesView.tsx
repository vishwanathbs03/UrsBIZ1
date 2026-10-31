"use client";

import React, { useState, useEffect } from "react";
import {
  ShoppingBag,
  Upload,
  Users,
  Package,
  TrendingUp,
  History,
  DollarSign,
  Layers,
  UserCheck,
  Calendar,
  AlertCircle,
  Plus,
} from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/common/PageHeader";
import { MetricCard } from "@/components/common/MetricCard";
import { Button } from "@/components/ui/button";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import {
  salesService,
  type SalesSummaryResponse,
  type CustomerInsightsResponse,
  type ProductInsightsResponse,
  type SalesTimeSeriesResponse,
  type SalesUploadListItem,
} from "@/services/sales-service";

import { SalesUploadWizard } from "./SalesUploadWizard";
import { CustomerInsightsTab } from "./CustomerInsightsTab";
import { ProductInsightsTab } from "./ProductInsightsTab";
import { SalesTrendsTab } from "./SalesTrendsTab";
import { UploadHistoryTab } from "./UploadHistoryTab";

type ActiveTab = "overview" | "customers" | "products" | "trends" | "history";

export function SalesView() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [showWizard, setShowWizard] = useState(false);
  const [loading, setLoading] = useState(true);

  const [summary, setSummary] = useState<SalesSummaryResponse | null>(null);
  const [customerInsights, setCustomerInsights] = useState<CustomerInsightsResponse | null>(null);
  const [productInsights, setProductInsights] = useState<ProductInsightsResponse | null>(null);
  const [timeSeries, setTimeSeries] = useState<SalesTimeSeriesResponse | null>(null);
  const [uploads, setUploads] = useState<SalesUploadListItem[]>([]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sum, cust, prod, ts, upl] = await Promise.all([
        salesService.getSummary().catch(() => null),
        salesService.getCustomerInsights().catch(() => null),
        salesService.getProductInsights().catch(() => null),
        salesService.getTimeSeries("monthly").catch(() => null),
        salesService.listUploads().catch(() => []),
      ]);

      setSummary(sum);
      setCustomerInsights(cust);
      setProductInsights(prod);
      setTimeSeries(ts);
      setUploads(upl || []);
    } catch (err) {
      console.error("Failed to load sales data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUploadSuccess = () => {
    setShowWizard(false);
    loadData();
  };

  return (
    <PageContainer>
      <PageHeader
        title="Sales Intelligence & Customer Demand"
        description="Upload historical MSME sales records to uncover customer behavior, product velocity, and validated revenue patterns."
        actions={
          <Button
            onClick={() => setShowWizard(true)}
            className="bg-neon-cyan text-xs font-semibold text-black hover:bg-neon-cyan/90 shadow-[0_0_15px_rgba(6,182,212,0.3)]"
          >
            <Upload className="mr-2 h-4 w-4" /> Upload Sales Data
          </Button>
        }
      />

      {/* Upload Wizard Modal */}
      {showWizard && (
        <div className="mb-8">
          <SalesUploadWizard
            onSuccess={handleUploadSuccess}
            onCancel={() => setShowWizard(false)}
          />
        </div>
      )}

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <LoadingSkeleton variant="card" />
            <LoadingSkeleton variant="card" />
          </div>
        </div>
      ) : !summary || !summary.has_sales_data ? (
        <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
          <ShoppingBag className="mx-auto h-16 w-16 text-neon-cyan/60 animate-pulse" />
          <h3 className="mt-4 text-lg font-bold text-dark-text-primary">
            No Historical Sales Data Uploaded Yet
          </h3>
          <p className="mx-auto mt-2 max-w-md text-xs text-dark-text-muted">
            Upload your historical invoices, transaction CSVs, or Excel billing ledgers.
            UrsBiz will map columns, validate data quality, and compute authentic customer and product metrics.
          </p>
          <div className="mt-6 flex justify-center">
            <Button
              onClick={() => setShowWizard(true)}
              className="bg-neon-cyan text-xs font-semibold text-black hover:bg-neon-cyan/90"
            >
              <Plus className="mr-1.5 h-4 w-4" /> Ingest Your First Sales File
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Navigation Sub-Tabs */}
          <div className="flex border-b border-dark-border space-x-2 overflow-x-auto text-xs">
            <button
              onClick={() => setActiveTab("overview")}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
                activeTab === "overview"
                  ? "border-neon-cyan text-neon-cyan"
                  : "border-transparent text-dark-text-muted hover:text-dark-text-primary"
              }`}
            >
              <ShoppingBag className="h-4 w-4" /> Overview
            </button>
            <button
              onClick={() => setActiveTab("customers")}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
                activeTab === "customers"
                  ? "border-neon-cyan text-neon-cyan"
                  : "border-transparent text-dark-text-muted hover:text-dark-text-primary"
              }`}
            >
              <Users className="h-4 w-4" /> Customer Intelligence
            </button>
            <button
              onClick={() => setActiveTab("products")}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
                activeTab === "products"
                  ? "border-neon-cyan text-neon-cyan"
                  : "border-transparent text-dark-text-muted hover:text-dark-text-primary"
              }`}
            >
              <Package className="h-4 w-4" /> Product Insights
            </button>
            <button
              onClick={() => setActiveTab("trends")}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
                activeTab === "trends"
                  ? "border-neon-cyan text-neon-cyan"
                  : "border-transparent text-dark-text-muted hover:text-dark-text-primary"
              }`}
            >
              <TrendingUp className="h-4 w-4" /> Sales Trends
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 font-medium transition-colors ${
                activeTab === "history"
                  ? "border-neon-cyan text-neon-cyan"
                  : "border-transparent text-dark-text-muted hover:text-dark-text-primary"
              }`}
            >
              <History className="h-4 w-4" /> Ingestion History ({uploads.length})
            </button>
          </div>

          {/* TAB 1: Overview */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricCard
                  title="Historical Sales Revenue"
                  value={`₹${summary.total_revenue.toLocaleString()}`}
                  icon={<DollarSign className="h-5 w-5 text-neon-emerald" />}
                  accentColor="emerald"
                  caption={`${summary.total_transactions.toLocaleString()} transactions`}
                />
                <MetricCard
                  title="Total Units Sold"
                  value={summary.total_quantity.toLocaleString()}
                  icon={<Layers className="h-5 w-5 text-neon-cyan" />}
                  accentColor="cyan"
                  caption={`${summary.unique_products} unique SKUs`}
                />
                <MetricCard
                  title="Total Customers"
                  value={summary.unique_customers.toLocaleString()}
                  icon={<Users className="h-5 w-5 text-neon-blue" />}
                  accentColor="blue"
                  caption={`${customerInsights?.repeat_customers || 0} repeat buyers`}
                />
                <MetricCard
                  title="Repeat Buyer Rate"
                  value={`${customerInsights?.repeat_rate_pct || 0}%`}
                  icon={<UserCheck className="h-5 w-5 text-neon-amber" />}
                  accentColor="amber"
                  caption="Customer retention"
                />
              </div>

              {/* Quick Summary Grid */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
                  <h3 className="mb-3 text-sm font-bold text-dark-text-primary uppercase tracking-wider">
                    Sales Dataset Details
                  </h3>
                  <div className="space-y-2.5 text-xs">
                    <div className="flex justify-between border-b border-dark-border/50 pb-2">
                      <span className="text-dark-text-muted">Date Range Span</span>
                      <span className="font-mono text-dark-text-primary">
                        {summary.first_transaction_date} to {summary.latest_transaction_date} (
                        {summary.date_range_days} days)
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-dark-border/50 pb-2">
                      <span className="text-dark-text-muted">Total Transactions Logged</span>
                      <span className="font-mono text-neon-cyan">
                        {summary.total_transactions.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-dark-border/50 pb-2">
                      <span className="text-dark-text-muted">Latest Uploaded File</span>
                      <span className="text-dark-text-primary">
                        {summary.latest_upload_filename || "N/A"}
                      </span>
                    </div>
                    <div className="flex justify-between pt-1">
                      <span className="text-dark-text-muted">Average Order Value</span>
                      <span className="font-mono text-neon-emerald">
                        ₹{customerInsights?.average_order_value.toLocaleString() || "0"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
                  <h3 className="mb-3 text-sm font-bold text-dark-text-primary uppercase tracking-wider">
                    Top Demand Drivers
                  </h3>
                  <div className="space-y-2 text-xs">
                    {productInsights?.top_products_by_revenue.slice(0, 4).map((p, i) => (
                      <div key={i} className="flex items-center justify-between border-b border-dark-border/40 pb-2">
                        <span className="font-medium text-dark-text-primary truncate max-w-[200px]">
                          {i + 1}. {p.product_name}
                        </span>
                        <span className="font-mono text-neon-emerald">
                          ₹{p.total_revenue.toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Customer Intelligence */}
          {activeTab === "customers" && <CustomerInsightsTab insights={customerInsights} />}

          {/* TAB 3: Product Insights */}
          {activeTab === "products" && <ProductInsightsTab insights={productInsights} />}

          {/* TAB 4: Sales Trends */}
          {activeTab === "trends" && <SalesTrendsTab initialData={timeSeries} />}

          {/* TAB 5: Upload History */}
          {activeTab === "history" && (
            <UploadHistoryTab uploads={uploads} onUploadDeleted={loadData} />
          )}
        </div>
      )}
    </PageContainer>
  );
}

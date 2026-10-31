"use client";

import React from "react";
import { Package, TrendingUp, TrendingDown, Layers, HelpCircle } from "lucide-react";
import { MetricCard } from "@/components/common/MetricCard";
import type { ProductInsightsResponse } from "@/services/sales-service";

interface ProductInsightsTabProps {
  insights: ProductInsightsResponse | null;
}

export function ProductInsightsTab({ insights }: ProductInsightsTabProps) {
  if (!insights || insights.total_products === 0) {
    return (
      <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
        <Package className="mx-auto h-12 w-12 text-dark-text-muted" />
        <h3 className="mt-4 text-base font-semibold text-dark-text-primary">No Product Intelligence Available</h3>
        <p className="mt-1 text-xs text-dark-text-muted">
          Upload sales records to analyze revenue performers vs. fast-moving volume drivers.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Unique Products Sold"
          value={insights.total_products.toLocaleString()}
          icon={<Package className="h-5 w-5 text-neon-cyan" />}
          accentColor="cyan"
          caption="Catalog breadth"
        />
        <MetricCard
          title="Total Units Sold"
          value={insights.total_quantity_sold.toLocaleString()}
          icon={<Layers className="h-5 w-5 text-neon-emerald" />}
          accentColor="emerald"
          caption="Physical sales volume"
        />
        <MetricCard
          title="Growing Products"
          value={insights.increasing_sales_products.length.toString()}
          icon={<TrendingUp className="h-5 w-5 text-neon-blue" />}
          accentColor="blue"
          caption=">= 10% volume growth"
        />
        <MetricCard
          title="Declining Products"
          value={insights.decreasing_sales_products.length.toString()}
          icon={<TrendingDown className="h-5 w-5 text-neon-rose" />}
          accentColor="amber"
          caption=">= 10% volume drop"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Table 1: Top Products by Revenue */}
        <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold text-dark-text-primary uppercase tracking-wider">
              Top Products by Revenue
            </h3>
            <span className="text-[11px] text-neon-emerald font-semibold">Value Drivers</span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-dark-border">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
                <tr>
                  <th className="p-3">#</th>
                  <th className="p-3">Product Name</th>
                  <th className="p-3">Total Revenue</th>
                  <th className="p-3">Units Sold</th>
                  <th className="p-3">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border">
                {insights.top_products_by_revenue.map((p, idx) => (
                  <tr key={idx} className="hover:bg-dark-border/20">
                    <td className="p-3 font-mono text-dark-text-muted">{idx + 1}</td>
                    <td className="p-3 font-semibold text-dark-text-primary">{p.product_name}</td>
                    <td className="p-3 font-mono text-neon-emerald font-semibold">
                      ₹{p.total_revenue.toLocaleString()}
                    </td>
                    <td className="p-3 text-dark-text-muted">{p.total_quantity_sold.toLocaleString()}</td>
                    <td className="p-3">
                      <TrendBadge trend={p.trend} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Table 2: Fast-Moving Products by Volume (Strictly Separated!) */}
        <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold text-dark-text-primary uppercase tracking-wider">
              Fast-Moving Products by Volume
            </h3>
            <span className="text-[11px] text-neon-cyan font-semibold">Quantity Drivers</span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-dark-border">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
                <tr>
                  <th className="p-3">#</th>
                  <th className="p-3">Product Name</th>
                  <th className="p-3">Units Sold</th>
                  <th className="p-3">Avg Unit Price</th>
                  <th className="p-3">Total Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border">
                {insights.fast_moving_products_by_volume.map((p, idx) => (
                  <tr key={idx} className="hover:bg-dark-border/20">
                    <td className="p-3 font-mono text-dark-text-muted">{idx + 1}</td>
                    <td className="p-3 font-semibold text-dark-text-primary">{p.product_name}</td>
                    <td className="p-3 font-mono text-neon-cyan font-semibold">
                      {p.total_quantity_sold.toLocaleString()}
                    </td>
                    <td className="p-3 font-mono text-dark-text-muted">₹{p.average_unit_price.toLocaleString()}</td>
                    <td className="p-3 font-mono text-dark-text-muted">₹{p.total_revenue.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function TrendBadge({ trend }: { trend: string }) {
  if (trend === "Increasing") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-neon-emerald/20 px-2 py-0.5 text-[10px] font-bold text-neon-emerald uppercase">
        <TrendingUp className="h-3 w-3" /> Growing
      </span>
    );
  }
  if (trend === "Decreasing") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-neon-rose/20 px-2 py-0.5 text-[10px] font-bold text-neon-rose uppercase">
        <TrendingDown className="h-3 w-3" /> Declining
      </span>
    );
  }
  if (trend === "Insufficient History") {
    return (
      <span className="inline-flex items-center gap-1 rounded bg-dark-border px-2 py-0.5 text-[10px] font-medium text-dark-text-muted">
        <HelpCircle className="h-3 w-3" /> &lt;3 txns
      </span>
    );
  }
  return (
    <span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-[10px] font-medium text-neon-cyan uppercase">
      Stable
    </span>
  );
}

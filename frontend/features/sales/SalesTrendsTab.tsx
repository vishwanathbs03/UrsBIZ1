"use client";

import React, { useState, useEffect } from "react";
import { Calendar, TrendingUp, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { salesService, type SalesTimeSeriesResponse } from "@/services/sales-service";

interface SalesTrendsTabProps {
  initialData: SalesTimeSeriesResponse | null;
}

export function SalesTrendsTab({ initialData }: SalesTrendsTabProps) {
  const [granularity, setGranularity] = useState<"monthly" | "weekly" | "daily">("monthly");
  const [data, setData] = useState<SalesTimeSeriesResponse | null>(initialData);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function fetchTrends() {
      setLoading(true);
      try {
        const res = await salesService.getTimeSeries(granularity);
        if (isMounted) setData(res);
      } catch (err) {
        console.error("Failed to load time series:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    fetchTrends();
    return () => {
      isMounted = false;
    };
  }, [granularity]);

  if (!data || data.points.length === 0) {
    return (
      <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
        <Calendar className="mx-auto h-12 w-12 text-dark-text-muted" />
        <h3 className="mt-4 text-base font-semibold text-dark-text-primary">No Sales Trends Available</h3>
        <p className="mt-1 text-xs text-dark-text-muted">
          Upload historical sales records to see monthly, weekly, and daily sales progressions.
        </p>
      </div>
    );
  }

  const maxRevenue = Math.max(...data.points.map((p) => p.revenue), 1);

  return (
    <div className="space-y-6">
      {/* Header & Granularity Switcher */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-dark-border bg-dark-card p-4">
        <div>
          <h3 className="text-sm font-bold text-dark-text-primary uppercase tracking-wider">
            Historical Sales Trajectory
          </h3>
          <p className="text-xs text-dark-text-muted">
            Aggregated from {data.start_date} to {data.end_date} across {data.total_periods} active periods.
          </p>
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-dark-border bg-dark-bg p-1 text-xs">
          <Button
            type="button"
            size="sm"
            variant={granularity === "monthly" ? "default" : "ghost"}
            onClick={() => setGranularity("monthly")}
            className={`h-7 px-3 text-xs ${
              granularity === "monthly" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90" : "text-dark-text-muted"
            }`}
          >
            Monthly
          </Button>
          <Button
            type="button"
            size="sm"
            variant={granularity === "weekly" ? "default" : "ghost"}
            onClick={() => setGranularity("weekly")}
            className={`h-7 px-3 text-xs ${
              granularity === "weekly" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90" : "text-dark-text-muted"
            }`}
          >
            Weekly
          </Button>
          <Button
            type="button"
            size="sm"
            variant={granularity === "daily" ? "default" : "ghost"}
            onClick={() => setGranularity("daily")}
            className={`h-7 px-3 text-xs ${
              granularity === "daily" ? "bg-neon-cyan text-black hover:bg-neon-cyan/90" : "text-dark-text-muted"
            }`}
          >
            Daily
          </Button>
        </div>
      </div>

      {/* Provenance Notice */}
      <div className="flex items-center gap-2 rounded-lg border border-dark-border bg-dark-bg/60 p-3 text-xs text-dark-text-muted">
        <Info className="h-4 w-4 text-neon-cyan shrink-0" />
        <span>
          <strong>Data Provenance Notice:</strong> These trends reflect actual uploaded sales transactions.
          Periods without transactions represent non-uploaded records, not synthetic zero-revenue interpolations.
        </span>
      </div>

      {/* Visual Bar Chart Representation */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
        <h4 className="mb-6 text-xs font-semibold text-dark-text-muted uppercase tracking-wider">
          Revenue Distribution Over Time
        </h4>
        <div className="space-y-3">
          {data.points.map((pt) => {
            const pct = Math.round((pt.revenue / maxRevenue) * 100);
            return (
              <div key={pt.period} className="flex items-center gap-4 text-xs">
                <span className="w-20 font-mono font-medium text-dark-text-muted">{pt.period}</span>
                <div className="h-4 flex-1 rounded bg-dark-bg overflow-hidden border border-dark-border">
                  <div
                    className="h-full bg-gradient-to-r from-neon-cyan to-neon-emerald transition-all duration-500"
                    style={{ width: `${Math.max(pct, 2)}%` }}
                  />
                </div>
                <span className="w-24 text-right font-mono font-semibold text-neon-emerald">
                  ₹{pt.revenue.toLocaleString()}
                </span>
                <span className="w-16 text-right text-dark-text-muted">
                  {pt.transaction_count} txns
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Data Table */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
        <h4 className="mb-4 text-xs font-semibold text-dark-text-muted uppercase tracking-wider">
          Period Breakdown Table
        </h4>
        <div className="overflow-x-auto rounded-lg border border-dark-border">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
              <tr>
                <th className="p-3">Period</th>
                <th className="p-3">Revenue</th>
                <th className="p-3">Units Sold</th>
                <th className="p-3">Transactions</th>
                <th className="p-3">Unique Customers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border">
              {data.points.map((pt) => (
                <tr key={pt.period} className="hover:bg-dark-border/20">
                  <td className="p-3 font-mono font-semibold text-dark-text-primary">{pt.period}</td>
                  <td className="p-3 font-mono text-neon-emerald">₹{pt.revenue.toLocaleString()}</td>
                  <td className="p-3 text-dark-text-primary">{pt.quantity.toLocaleString()}</td>
                  <td className="p-3 text-dark-text-muted">{pt.transaction_count}</td>
                  <td className="p-3 text-dark-text-muted">{pt.unique_customers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

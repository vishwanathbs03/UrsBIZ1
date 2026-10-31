"use client";

import React from "react";
import { Users, UserCheck, TrendingDown, DollarSign, RefreshCw, AlertCircle } from "lucide-react";
import { MetricCard } from "@/components/common/MetricCard";
import type { CustomerInsightsResponse } from "@/services/sales-service";

interface CustomerInsightsTabProps {
  insights: CustomerInsightsResponse | null;
}

export function CustomerInsightsTab({ insights }: CustomerInsightsTabProps) {
  if (!insights || insights.total_customers === 0) {
    return (
      <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
        <Users className="mx-auto h-12 w-12 text-dark-text-muted" />
        <h3 className="mt-4 text-base font-semibold text-dark-text-primary">No Customer Intelligence Available</h3>
        <p className="mt-1 text-xs text-dark-text-muted">
          Upload a sales file with customer names to calculate retention and purchase frequencies.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Level Metric Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Customers"
          value={insights.total_customers.toLocaleString()}
          icon={<Users className="h-5 w-5 text-neon-cyan" />}
          accentColor="cyan"
          caption={`${insights.new_customers} new | ${insights.repeat_customers} repeat`}
        />
        <MetricCard
          title="Repeat Rate"
          value={`${insights.repeat_rate_pct}%`}
          icon={<UserCheck className="h-5 w-5 text-neon-emerald" />}
          accentColor="emerald"
          caption={`${insights.repeat_customers} repeat accounts`}
        />
        <MetricCard
          title="Average Order Value"
          value={`₹${insights.average_order_value.toLocaleString()}`}
          icon={<DollarSign className="h-5 w-5 text-neon-amber" />}
          accentColor="amber"
          caption="Revenue per transaction"
        />
        <MetricCard
          title="Purchase Frequency"
          value={`${insights.purchase_frequency}x`}
          icon={<RefreshCw className="h-5 w-5 text-neon-blue" />}
          accentColor="blue"
          caption="Orders per customer"
        />
      </div>

      {/* Declining Customers Alert Banner */}
      {insights.declining_customers.length > 0 ? (
        <div className="rounded-xl border border-neon-rose/30 bg-neon-rose/10 p-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-neon-rose shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-bold text-dark-text-primary">
                  Declining Accounts Warning ({insights.declining_customers.length} Accounts)
                </h4>
                {insights.dataset_reference_date && (
                  <span className="rounded bg-dark-bg/80 border border-neon-rose/40 px-2.5 py-0.5 text-[11px] font-mono text-neon-rose">
                    Reference Date: {insights.dataset_reference_date} ({insights.history_span_days}d span)
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-dark-text-muted">
                {insights.inactivity_definition}
              </p>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-dark-border bg-dark-bg/60">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
                <tr>
                  <th className="p-3">Customer</th>
                  <th className="p-3">Historical Revenue</th>
                  <th className="p-3">Total Orders</th>
                  <th className="p-3">Last Purchase Date</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-border">
                {insights.declining_customers.map((c, i) => (
                  <tr key={i} className="hover:bg-dark-border/20">
                    <td className="p-3 font-medium text-dark-text-primary">{c.customer_name}</td>
                    <td className="p-3 text-neon-rose font-mono">₹{c.total_revenue.toLocaleString()}</td>
                    <td className="p-3 text-dark-text-muted">{c.total_orders}</td>
                    <td className="p-3 text-dark-text-muted">{c.latest_purchase_date}</td>
                    <td className="p-3">
                      <span className="rounded bg-neon-rose/20 px-2 py-0.5 text-[10px] font-bold uppercase text-neon-rose">
                        Declining
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dark-border bg-dark-card p-4 flex items-center justify-between text-xs text-dark-text-muted">
          <span>
            {insights.history_span_days >= 90 ? (
              <>No accounts currently meet the 60-day declining inactivity criteria relative to dataset date ({insights.dataset_reference_date || "latest record"}).</>
            ) : (
              <>Customer retention tracking active. 60-day declining inactivity analysis activates once dataset spans &ge; 90 days (current span: {insights.history_span_days} days).</>
            )}
          </span>
          {insights.dataset_reference_date && (
            <span className="font-mono text-neon-cyan/80">Anchor Date: {insights.dataset_reference_date}</span>
          )}
        </div>
      )}

      {/* Top Customers Table */}
      <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
        <h3 className="mb-4 text-sm font-bold text-dark-text-primary uppercase tracking-wider">
          Top Customers by Revenue
        </h3>
        <div className="overflow-x-auto rounded-lg border border-dark-border">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
              <tr>
                <th className="p-3">#</th>
                <th className="p-3">Customer Name</th>
                <th className="p-3">Total Revenue</th>
                <th className="p-3">Total Orders</th>
                <th className="p-3">Average Order Value</th>
                <th className="p-3">Latest Purchase</th>
                <th className="p-3">Account Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border">
              {insights.top_customers_by_revenue.map((c, idx) => (
                <tr key={idx} className="hover:bg-dark-border/20">
                  <td className="p-3 font-mono text-dark-text-muted">{idx + 1}</td>
                  <td className="p-3 font-semibold text-dark-text-primary">{c.customer_name}</td>
                  <td className="p-3 font-mono text-neon-emerald">₹{c.total_revenue.toLocaleString()}</td>
                  <td className="p-3 text-dark-text-primary">{c.total_orders}</td>
                  <td className="p-3 font-mono text-dark-text-muted">₹{c.average_order_value.toLocaleString()}</td>
                  <td className="p-3 text-dark-text-muted">{c.latest_purchase_date}</td>
                  <td className="p-3">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                        c.status === "Active"
                          ? "bg-neon-emerald/20 text-neon-emerald"
                          : c.status === "New"
                          ? "bg-neon-cyan/20 text-neon-cyan"
                          : "bg-neon-rose/20 text-neon-rose"
                      }`}
                    >
                      {c.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

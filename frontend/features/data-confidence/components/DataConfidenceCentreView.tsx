"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Database,
  Calendar,
  Clock,
  CheckCircle2,
  Download,
  Upload,
  ArrowRight,
  TrendingUp,
  Users,
  ShoppingBag,
  Activity,
  Layers,
  FileText,
  RefreshCw,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  dataConfidenceService,
  DataConfidenceCentreResponse,
  InsightReadinessItem,
} from "@/services";

export function DataConfidenceCentreView() {
  const [data, setData] = useState<DataConfidenceCentreResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfidence();
  }, []);

  const fetchConfidence = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await dataConfidenceService.getConfidence();
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load data confidence assessment");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = async () => {
    try {
      const report = await dataConfidenceService.getAuditReport();
      const blob = new Blob([JSON.stringify(report, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `UrsBiz_DataQuality_Audit_${data?.business_id || "business"}_${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Failed to export audit report");
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 pb-16">
        <div className="h-20 rounded-xl bg-card animate-pulse border border-border" />
        <LoadingSkeleton rows={4} variant="card" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="py-12">
        <ErrorState
          title="Confidence Centre Error"
          description={error || "Failed to load confidence assessment"}
          actionLabel="Retry Assessment"
          onAction={fetchConfidence}
        />
      </div>
    );
  }

  const { ingestion_summary, observation_window, insight_confidence_matrix, actionable_improvement_checklist } = data;

  const isVerified = data.overall_quality_status === "VERIFIED";
  const isProvisional = data.overall_quality_status === "PROVISIONAL";

  const statusColor = isVerified
    ? "text-emerald-500 border-emerald-500/40 bg-emerald-500/10"
    : isProvisional
    ? "text-amber-500 border-amber-500/40 bg-amber-500/10"
    : "text-rose-500 border-rose-500/40 bg-rose-500/10";

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="p-2 rounded-lg bg-primary/10 text-primary border border-primary/20">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <Badge variant="outline" className="border-primary/30 text-primary text-xs">
              Phase 6.20 Extension
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
            Data Quality & Business Confidence Centre
          </h1>
          <p className="text-muted-foreground text-sm mt-1 max-w-2xl leading-relaxed">
            Transparent data sufficiency assessment for MSME decision-making. Understand exactly which insights
            are verified, which carry conservative assumptions, and how to improve accuracy.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchConfidence}
            className="gap-1.5 text-xs h-9"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-Audit
          </Button>
          <Button
            size="sm"
            onClick={handleDownloadReport}
            className="gap-1.5 text-xs h-9 bg-primary text-primary-foreground"
          >
            <Download className="h-3.5 w-3.5" />
            Export Audit Report
          </Button>
        </div>
      </div>

      {/* Top Confidence Score Banner */}
      <div className="rounded-xl border border-border/80 bg-card p-6 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
          <div className="md:col-span-1 border-b md:border-b-0 md:border-r border-border/60 pb-4 md:pb-0 md:pr-6 text-center md:text-left">
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block mb-1">
              Overall Confidence Grade
            </span>
            <div className="flex items-center justify-center md:justify-start gap-3 mt-2">
              <span className="text-4xl font-black text-foreground">
                {Math.round(data.overall_confidence_score)}%
              </span>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${statusColor}`}>
                {data.overall_quality_status}
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2 leading-relaxed">
              Audited at {new Date(data.audit_timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} UTC
            </p>
          </div>

          <div className="md:col-span-3 grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
            <div className="p-3 rounded-lg bg-muted/40 border border-border/50">
              <span className="text-muted-foreground block mb-1">Valid Ingestion Rate</span>
              <strong className="text-foreground text-base block font-bold">
                {ingestion_summary.valid_row_rate_pct}%
              </strong>
              <span className="text-[10px] text-muted-foreground">
                {ingestion_summary.valid_rows_ingested} / {ingestion_summary.total_rows_imported} rows
              </span>
            </div>

            <div className="p-3 rounded-lg bg-muted/40 border border-border/50">
              <span className="text-muted-foreground block mb-1">Observation Window</span>
              <strong className="text-foreground text-base block font-bold">
                {observation_window.observation_window_days} Days
              </strong>
              <span className="text-[10px] text-muted-foreground">
                {observation_window.earliest_transaction_date || "N/A"} to {observation_window.latest_transaction_date || "N/A"}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-muted/40 border border-border/50 col-span-2 sm:col-span-1">
              <span className="text-muted-foreground block mb-1">Data Freshness</span>
              <strong className="text-foreground text-base block font-bold">
                {observation_window.freshness_status.replace(/_/g, " ")}
              </strong>
              <span className="text-[10px] text-muted-foreground truncate block">
                {observation_window.freshness_description}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Ingestion & Revenue Reconciliation Dual-Basis Strip */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <Database className="h-4 w-4 text-primary" />
          1. Ingestion Breakdown & Revenue Reconciliation
        </h2>
        <div className="rounded-xl border border-border/80 bg-card p-6 space-y-4 shadow-sm">
          {/* Basis Explanation Banner */}
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-xs leading-relaxed text-foreground/90 flex items-start gap-3">
            <HelpCircle className="h-4 w-4 text-primary shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold text-primary block mb-1">
                Authoritative Basis Reconciliation:
              </strong>
              {ingestion_summary.reconciliation_basis_note}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
            <div className="p-4 rounded-lg bg-muted/40 border border-border/40">
              <span className="text-xs text-muted-foreground block">Gross Uploaded Revenue</span>
              <strong className="text-foreground text-base font-bold block mt-1">
                ₹{Number(ingestion_summary.gross_uploaded_revenue_inr).toLocaleString("en-IN")}
              </strong>
              <span className="text-[10px] text-muted-foreground">All rows in upload files</span>
            </div>

            <div className="p-4 rounded-lg bg-muted/40 border border-border/40">
              <span className="text-xs text-muted-foreground block">Duplicates Excluded</span>
              <strong className="text-foreground text-base font-bold block mt-1 text-amber-500">
                -₹{Number(ingestion_summary.duplicate_revenue_excluded_inr).toLocaleString("en-IN")}
              </strong>
              <span className="text-[10px] text-muted-foreground">
                {ingestion_summary.duplicate_rows_excluded} duplicate rows excluded
              </span>
            </div>

            <div className="p-4 rounded-lg bg-muted/40 border border-emerald-500/30 bg-emerald-500/5">
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold block">
                Analytical Revenue (Net)
              </span>
              <strong className="text-foreground text-base font-bold block mt-1">
                ₹{Number(ingestion_summary.analytical_revenue_inr).toLocaleString("en-IN")}
              </strong>
              <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80">
                Authoritative analytical basis
              </span>
            </div>

            <div className="p-4 rounded-lg bg-muted/40 border border-border/40">
              <span className="text-xs text-muted-foreground block">Rejected Rows</span>
              <strong className="text-foreground text-base font-bold block mt-1 text-rose-500">
                {ingestion_summary.rejected_rows_count} Rows
              </strong>
              <span className="text-[10px] text-muted-foreground">Skipped during CSV ingestion</span>
            </div>
          </div>
        </div>
      </div>

      {/* Observation Window & Unconfirmed Gaps */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <Calendar className="h-4 w-4 text-primary" />
          2. Observation Timeline & Unconfirmed Sales Gaps
        </h2>
        <div className="rounded-xl border border-border/80 bg-card p-6 space-y-4 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground block mb-1">Calendar Observation Span</span>
              <strong className="text-foreground font-semibold block text-sm">
                {observation_window.observation_window_days} Calendar Days
              </strong>
              <span className="text-[11px] text-muted-foreground">
                {observation_window.earliest_transaction_date || "None"} &rarr; {observation_window.latest_transaction_date || "None"}
              </span>
            </div>

            <div>
              <span className="text-muted-foreground block mb-1">Data Ingestion Recency</span>
              <strong className="text-foreground font-semibold block text-sm">
                {observation_window.days_since_last_transaction !== null
                  ? `${observation_window.days_since_last_transaction} Days Elapsed`
                  : "No Transactions"}
              </strong>
              <span className="text-[11px] text-muted-foreground">
                Last upload: {observation_window.last_upload_timestamp ? new Date(observation_window.last_upload_timestamp).toLocaleDateString("en-IN") : "Never"}
              </span>
            </div>

            <div>
              <span className="text-muted-foreground block mb-1">Unconfirmed Sales Gaps</span>
              <strong className={`block text-sm font-semibold ${observation_window.unconfirmed_gaps_count > 0 ? "text-amber-500" : "text-emerald-500"}`}>
                {observation_window.unconfirmed_gaps_count} Gaps Detected
              </strong>
              <span className="text-[11px] text-muted-foreground">
                Intervals &gt; 14 days with 0 sales
              </span>
            </div>
          </div>

          {/* List of Unconfirmed Gaps */}
          {observation_window.unconfirmed_gaps.length > 0 && (
            <div className="pt-3 border-t border-border/50 space-y-2">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">
                Detected Sequence Interruptions:
              </span>
              <div className="space-y-2">
                {observation_window.unconfirmed_gaps.map((g, i) => (
                  <div
                    key={i}
                    className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/5 text-xs flex items-center justify-between"
                  >
                    <div>
                      <strong className="text-foreground font-semibold">
                        {g.start_date} to {g.end_date} ({g.gap_days} Days)
                      </strong>
                      <p className="text-muted-foreground text-[11px] mt-0.5">{g.note}</p>
                    </div>
                    <Badge variant="outline" className="border-amber-500/40 text-amber-500 text-[10px] shrink-0">
                      Unconfirmed Gap
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Insight Confidence Matrix */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary" />
          3. Insight Confidence Matrix: Module-by-Module Sufficiency
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {insight_confidence_matrix.map((item: InsightReadinessItem) => {
            const isReady = item.readiness_status === "Ready";
            const isBlocked = item.readiness_status === "Blocked by Missing Data";

            const cardBorder = isReady
              ? "border-emerald-500/30 bg-emerald-500/5"
              : isBlocked
              ? "border-rose-500/30 bg-rose-500/5"
              : "border-amber-500/30 bg-amber-500/5";

            const badgeColor = isReady
              ? "border-emerald-500/40 text-emerald-500"
              : isBlocked
              ? "border-rose-500/40 text-rose-500"
              : "border-amber-500/40 text-amber-500";

            return (
              <div
                key={item.module_key}
                className={`rounded-xl border p-5 space-y-3 shadow-sm ${cardBorder}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-bold text-foreground">{item.module_name}</h3>
                  <Badge variant="outline" className={`text-[10px] shrink-0 ${badgeColor}`}>
                    {item.confidence_level} ({Math.round(item.confidence_score)}%)
                  </Badge>
                </div>

                <p className="text-xs text-foreground/80 leading-relaxed">
                  {item.impact_explanation}
                </p>

                {item.missing_prerequisites.length > 0 && (
                  <div className="pt-2 border-t border-border/30 text-[11px] text-muted-foreground space-y-1">
                    <span className="font-semibold text-foreground block">Missing Prerequisites:</span>
                    {item.missing_prerequisites.map((p, idx) => (
                      <p key={idx} className="flex items-center gap-1.5">
                        <span className="h-1 w-1 rounded-full bg-amber-500 shrink-0" />
                        {p}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Actionable Improvement Checklist */}
      {actionable_improvement_checklist.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            4. Recommended Data Enhancements
          </h2>
          <div className="rounded-xl border border-border/80 bg-card p-6 space-y-4 shadow-sm">
            <div className="space-y-3">
              {actionable_improvement_checklist.map((action, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl border border-border/60 bg-muted/30 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 font-bold text-foreground text-sm">
                      <Badge
                        variant="secondary"
                        className={
                          action.priority === "High"
                            ? "bg-rose-500/10 text-rose-500 border border-rose-500/30 text-[10px]"
                            : "bg-muted text-muted-foreground text-[10px]"
                        }
                      >
                        {action.priority} Priority
                      </Badge>
                      {action.title}
                    </div>
                    <p className="text-muted-foreground text-xs leading-relaxed">{action.description}</p>
                    <span className="text-[11px] text-primary font-medium block mt-1">
                      Target Benefit: {action.impact_on_insights}
                    </span>
                  </div>

                  <div className="shrink-0">
                    {action.action_type === "upload_sales" || action.action_type === "fill_gaps" ? (
                      <Link href="/sales">
                        <Button size="sm" className="gap-1.5 text-xs h-8">
                          <Upload className="h-3.5 w-3.5" />
                          Upload Sales File
                        </Button>
                      </Link>
                    ) : action.action_type === "complete_profile" ? (
                      <Link href="/business">
                        <Button size="sm" variant="outline" className="gap-1.5 text-xs h-8">
                          Complete Profile
                          <ArrowRight className="h-3.5 w-3.5 ml-1" />
                        </Button>
                      </Link>
                    ) : (
                      <Link href="/sales">
                        <Button size="sm" variant="outline" className="gap-1.5 text-xs h-8">
                          View Ledger
                        </Button>
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

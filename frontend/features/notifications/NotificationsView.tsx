"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Check,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageContainer } from "@/components/layout/PageContainer";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import {
  alertsService,
  AlertAuditHistoryItem,
  AlertExplainResponse,
  AlertSummaryResponse,
  BusinessSignalItem,
  EventNature,
  EventSeverity,
  EventStatus,
} from "@/services";

export function NotificationsView() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<BusinessSignalItem[]>([]);
  const [summary, setSummary] = useState<AlertSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [natureFilter, setNatureFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Detail Modal & Explain
  const [selectedAlert, setSelectedAlert] = useState<BusinessSignalItem | null>(null);
  const [history, setHistory] = useState<AlertAuditHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [explanation, setExplanation] = useState<AlertExplainResponse | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explainLang, setExplainLang] = useState<"en" | "kn">("en");

  // Status updating
  const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);
  const [statusActionError, setStatusActionError] = useState<string | null>(null);

  const fetchAlertsData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [listRes, summaryRes] = await Promise.all([
        alertsService.listAlerts({
          severity: severityFilter === "ALL" ? undefined : severityFilter,
          status: statusFilter === "ALL" ? undefined : statusFilter,
          event_nature: natureFilter === "ALL" ? undefined : natureFilter,
          limit: 100,
        }),
        alertsService.getAlertsSummary(),
      ]);
      setAlerts(listRes.alerts);
      setSummary(summaryRes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load business alerts");
    } finally {
      setLoading(false);
    }
  }, [severityFilter, statusFilter, natureFilter]);

  useEffect(() => {
    fetchAlertsData();
  }, [fetchAlertsData]);

  const handleEvaluateNow = async () => {
    try {
      setEvaluating(true);
      await alertsService.evaluateAlerts();
      await fetchAlertsData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to run proactive evaluation");
    } finally {
      setEvaluating(false);
    }
  };

  const handleStatusChange = async (
    eventId: string,
    newStatus: "ACKNOWLEDGED" | "RESOLVED" | "DISMISSED",
    reason?: string
  ) => {
    try {
      setUpdatingStatusId(eventId);
      setStatusActionError(null);
      const updated = await alertsService.updateAlertStatus(eventId, {
        status: newStatus,
        reason: reason || `Updated to ${newStatus} via Event Centre UI`,
      });

      // Update in-memory state
      setAlerts((prev) => prev.map((a) => (a.event_id === eventId ? updated : a)));
      if (selectedAlert && selectedAlert.event_id === eventId) {
        setSelectedAlert(updated);
        // Refresh audit history
        fetchAlertHistory(eventId);
      }
      // Refresh summary counts
      alertsService.getAlertsSummary().then(setSummary).catch(() => {});
    } catch (err: unknown) {
      setStatusActionError(err instanceof Error ? err.message : "Failed to update alert status");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const fetchAlertHistory = async (eventId: string) => {
    try {
      setLoadingHistory(true);
      const res = await alertsService.getAlertHistory(eventId);
      setHistory(res);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleOpenDetail = (alert: BusinessSignalItem) => {
    setSelectedAlert(alert);
    setExplanation(null);
    setStatusActionError(null);
    fetchAlertHistory(alert.event_id);
  };

  const handleExplain = async (lang: "en" | "kn") => {
    if (!selectedAlert) return;
    try {
      setExplaining(true);
      setExplainLang(lang);
      const res = await alertsService.explainAlert(selectedAlert.event_id, lang);
      setExplanation(res);
    } catch {
      // Fallback
      setExplanation({
        event_id: selectedAlert.event_id,
        title: selectedAlert.title,
        severity: selectedAlert.severity,
        event_nature: selectedAlert.event_nature,
        explanation: `${selectedAlert.what_changed}\n\nWhy it matters: ${selectedAlert.why_it_matters}\n\nAction: ${selectedAlert.suggested_action}`,
        language: lang,
        provider_used: "deterministic_fallback",
        is_fallback: true,
      });
    } finally {
      setExplaining(false);
    }
  };

  // Filtered by text search
  const filteredAlerts = useMemo(() => {
    if (!searchQuery.trim()) return alerts;
    const q = searchQuery.toLowerCase();
    return alerts.filter(
      (a) =>
        a.title.toLowerCase().includes(q) ||
        a.what_changed.toLowerCase().includes(q) ||
        a.why_it_matters.toLowerCase().includes(q) ||
        (a.relevant_entity && a.relevant_entity.toLowerCase().includes(q))
    );
  }, [alerts, searchQuery]);

  // Color mappings
  const getSeverityBadgeClass = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-200 dark:border-rose-800";
      case "HIGH":
        return "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800";
      case "MEDIUM":
        return "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-200 dark:border-blue-800";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700";
    }
  };

  const getNatureBadgeClass = (nature: string) => {
    switch (nature.toUpperCase()) {
      case "CONFIRMED_EVENT":
        return "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800";
      case "WARNING":
        return "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800";
      case "ESTIMATE":
        return "bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950 dark:text-indigo-200 dark:border-indigo-800";
      case "ASSUMPTION":
        return "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950 dark:text-purple-200 dark:border-purple-800";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  };

  const getNatureLabel = (nature: string) => {
    switch (nature.toUpperCase()) {
      case "CONFIRMED_EVENT":
        return "Confirmed Fact";
      case "WARNING":
        return "Warning Threshold";
      case "ESTIMATE":
        return "Statistical Estimate";
      case "ASSUMPTION":
        return "Planning Assumption";
      default:
        return nature;
    }
  };

  const getStatusBadgeClass = (st: string) => {
    switch (st.toUpperCase()) {
      case "NEW":
        return "bg-blue-500 text-white";
      case "ACKNOWLEDGED":
        return "bg-amber-500 text-white";
      case "RESOLVED":
        return "bg-emerald-600 text-white";
      case "DISMISSED":
        return "bg-slate-400 text-white";
      default:
        return "bg-slate-500 text-white";
    }
  };

  return (
    <PageContainer>
      <div className="space-y-6 pb-16">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-5">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 bg-rose-50 dark:bg-rose-950/60 rounded-lg text-rose-600">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">Business Alerts & Event Centre</h1>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Proactive detection of revenue anomalies, dormant buyers, SKU velocity deceleration, and ledger staleness backed by live data.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleEvaluateNow}
              disabled={evaluating || loading}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${evaluating ? "animate-spin" : ""}`} />
              {evaluating ? "Scanning..." : "Scan Changes Now"}
            </Button>
            <Link href="/data-confidence">
              <Button variant="ghost" size="sm" className="gap-1 text-xs">
                Data Confidence <ArrowUpRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          </div>
        </div>

        {/* Overview KPI Cards */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-muted-foreground uppercase">Total Events</div>
              <div className="text-2xl font-bold mt-1">{summary.total_alerts}</div>
              <div className="text-xs text-muted-foreground mt-1">Active + Historical</div>
            </div>
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase">New / Unread</div>
              <div className="text-2xl font-bold mt-1 text-blue-600 dark:text-blue-400">{summary.new_count}</div>
              <div className="text-xs text-muted-foreground mt-1">Action pending</div>
            </div>
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-rose-600 dark:text-rose-400 uppercase">Critical Risks</div>
              <div className="text-2xl font-bold mt-1 text-rose-600 dark:text-rose-400">{summary.critical_count}</div>
              <div className="text-xs text-muted-foreground mt-1">Immediate priority</div>
            </div>
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase">Confirmed Facts</div>
              <div className="text-2xl font-bold mt-1 text-emerald-600 dark:text-emerald-400">
                {summary.confirmed_events_count}
              </div>
              <div className="text-xs text-muted-foreground mt-1">Empirical database events</div>
            </div>
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase">Warnings & Est.</div>
              <div className="text-2xl font-bold mt-1 text-amber-600 dark:text-amber-400">
                {summary.warnings_count + summary.estimates_count}
              </div>
              <div className="text-xs text-muted-foreground mt-1">Thresholds & 2σ anomalies</div>
            </div>
            <div className="p-4 rounded-xl border bg-card shadow-sm">
              <div className="text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Resolved</div>
              <div className="text-2xl font-bold mt-1 text-slate-700 dark:text-slate-300">{summary.resolved_count}</div>
              <div className="text-xs text-muted-foreground mt-1">Mitigated by owner</div>
            </div>
          </div>
        )}

        {/* Filter & Search Bar */}
        <div className="flex flex-col lg:flex-row gap-3 items-stretch lg:items-center justify-between p-3 rounded-lg border bg-muted/40">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mr-1">
              <Filter className="w-3.5 h-3.5" /> Filters:
            </div>

            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs rounded-md border bg-background px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
              <option value="INFORMATIONAL">Informational</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs rounded-md border bg-background px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="ALL">All Statuses</option>
              <option value="NEW">New</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="RESOLVED">Resolved</option>
              <option value="DISMISSED">Dismissed</option>
            </select>

            {/* Event Nature Filter */}
            <select
              value={natureFilter}
              onChange={(e) => setNatureFilter(e.target.value)}
              className="text-xs rounded-md border bg-background px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="ALL">All Event Natures</option>
              <option value="CONFIRMED_EVENT">Confirmed Fact</option>
              <option value="WARNING">Warning Threshold</option>
              <option value="ESTIMATE">Statistical Estimate (2σ)</option>
              <option value="ASSUMPTION">Planning Assumption</option>
            </select>
          </div>

          <div className="relative min-w-[220px]">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search alerts or buyers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs rounded-md border bg-background pl-8 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Content Body */}
        {loading ? (
          <LoadingSkeleton rows={4} />
        ) : error ? (
          <ErrorState title="Failed to Load Business Alerts" description={error} onAction={fetchAlertsData} />
        ) : filteredAlerts.length === 0 ? (
          <EmptyState
            title="No Business Alerts Detected"
            description={
              searchQuery || severityFilter !== "ALL" || statusFilter !== "ALL" || natureFilter !== "ALL"
                ? "No alerts match your active filter criteria. Try resetting filters."
                : "Your business metrics are operating within expected boundaries, or no sales transactions have been uploaded yet."
            }
            actionLabel="Review Data Confidence"
            onAction={() => router.push("/data-confidence")}
          />
        ) : (
          <div className="space-y-3">
            {filteredAlerts.map((alert) => (
              <div
                key={alert.event_id}
                onClick={() => handleOpenDetail(alert)}
                className={`p-4 rounded-xl border bg-card hover:bg-muted/30 transition-all cursor-pointer shadow-sm relative border-l-4 ${
                  alert.severity === "CRITICAL"
                    ? "border-l-rose-500"
                    : alert.severity === "HIGH"
                    ? "border-l-amber-500"
                    : alert.severity === "MEDIUM"
                    ? "border-l-blue-500"
                    : "border-l-slate-400"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        {alert.event_id}
                      </span>
                      <Badge variant="outline" className={`text-[10px] font-semibold py-0.5 ${getSeverityBadgeClass(alert.severity)}`}>
                        {alert.severity}
                      </Badge>
                      <Badge variant="outline" className={`text-[10px] font-semibold py-0.5 ${getNatureBadgeClass(alert.event_nature)}`}>
                        {getNatureLabel(alert.event_nature)}
                      </Badge>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${getStatusBadgeClass(alert.status)}`}>
                        {alert.status}
                      </span>
                    </div>

                    <h3 className="text-base font-semibold leading-tight text-foreground">
                      {alert.title}
                    </h3>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {alert.what_changed}
                    </p>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 shrink-0">
                    <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(alert.detected_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>

                    {/* Quick status actions */}
                    <div
                      className="flex items-center gap-1.5"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {alert.status === "NEW" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={updatingStatusId === alert.event_id}
                          onClick={() => handleStatusChange(alert.event_id, "ACKNOWLEDGED")}
                          className="text-xs h-7 px-2 text-amber-700 dark:text-amber-400"
                        >
                          Acknowledge
                        </Button>
                      )}
                      {(alert.status === "NEW" || alert.status === "ACKNOWLEDGED") && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={updatingStatusId === alert.event_id}
                          onClick={() => handleStatusChange(alert.event_id, "RESOLVED")}
                          className="text-xs h-7 px-2 text-emerald-700 dark:text-emerald-400"
                        >
                          <Check className="w-3 h-3 mr-1" /> Resolve
                        </Button>
                      )}
                    </div>
                  </div>
                </div>

                {alert.suggested_action && (
                  <div className="mt-3 pt-2.5 border-t flex items-center justify-between text-xs text-muted-foreground">
                    <div className="truncate max-w-[85%]">
                      <span className="font-semibold text-foreground">Suggested Action: </span>
                      {alert.suggested_action}
                    </div>
                    <span className="text-primary font-medium text-xs flex items-center gap-0.5 hover:underline">
                      Details <ArrowUpRight className="w-3 h-3" />
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Slide-over Detail Modal */}
        {selectedAlert && (
          <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex justify-end">
            <div className="w-full max-w-xl h-full bg-card border-l shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
              {/* Modal Header */}
              <div className="p-5 border-b flex items-start justify-between gap-3 bg-muted/20">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={`text-xs ${getSeverityBadgeClass(selectedAlert.severity)}`}>
                      {selectedAlert.severity}
                    </Badge>
                    <Badge variant="outline" className={`text-xs ${getNatureBadgeClass(selectedAlert.event_nature)}`}>
                      {getNatureLabel(selectedAlert.event_nature)}
                    </Badge>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${getStatusBadgeClass(selectedAlert.status)}`}>
                      {selectedAlert.status}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold mt-1 text-foreground">{selectedAlert.title}</h2>
                  <div className="text-xs text-muted-foreground">
                    Event ID: <span className="font-mono">{selectedAlert.event_id}</span> • Source: {selectedAlert.source}
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setSelectedAlert(null)}>
                  <X className="w-5 h-5" />
                </Button>
              </div>

              {/* Modal Scrollable Body */}
              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {statusActionError && (
                  <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded-md">
                    {statusActionError}
                  </div>
                )}

                {/* Observation Narrative */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    What Changed
                  </h4>
                  <p className="text-sm bg-muted/30 p-3 rounded-lg border text-foreground leading-relaxed">
                    {selectedAlert.what_changed}
                  </p>
                </div>

                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Why It Matters (Impact)
                  </h4>
                  <p className="text-sm bg-amber-50/50 dark:bg-amber-950/20 p-3 rounded-lg border border-amber-200 dark:border-amber-900/40 text-foreground leading-relaxed">
                    {selectedAlert.why_it_matters}
                  </p>
                </div>

                {/* Supporting Empirical Evidence */}
                {selectedAlert.evidence && Object.keys(selectedAlert.evidence).length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      Authoritative Evidence Ledger
                    </h4>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {Object.entries(selectedAlert.evidence).map(([key, val]) => (
                        <div key={key} className="p-2.5 rounded-md border bg-card">
                          <div className="text-[10px] text-muted-foreground uppercase font-mono truncate">
                            {key.replace(/_/g, " ")}
                          </div>
                          <div className="font-semibold mt-0.5 truncate text-foreground">
                            {typeof val === "object" ? JSON.stringify(val) : String(val)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggested Action */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Recommended MSME Action
                  </h4>
                  <div className="p-3.5 rounded-lg border bg-blue-50/50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900/40 text-sm">
                    <p className="text-foreground">{selectedAlert.suggested_action}</p>
                    <div className="mt-3 flex items-center gap-2">
                      <Link href="/decision-workbench">
                        <Button size="sm" variant="default" className="text-xs h-7">
                          Open Decision Workbench <ArrowUpRight className="w-3 h-3 ml-1" />
                        </Button>
                      </Link>
                      <Link href="/sales">
                        <Button size="sm" variant="outline" className="text-xs h-7">
                          Inspect Sales Ledger
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>

                {/* Grounded AI Explanations */}
                <div className="space-y-2 pt-2 border-t">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-primary" /> Plain-Language AI Explanation
                    </h4>
                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={explaining}
                        onClick={() => handleExplain("en")}
                        className="text-[11px] h-6 px-2"
                      >
                        English
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={explaining}
                        onClick={() => handleExplain("kn")}
                        className="text-[11px] h-6 px-2"
                      >
                        ಕನ್ನಡ
                      </Button>
                    </div>
                  </div>

                  {explaining ? (
                    <div className="p-4 rounded-lg border bg-muted/20 text-xs text-muted-foreground flex items-center gap-2">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-primary" />
                      Synthesizing grounded explanation from evidence...
                    </div>
                  ) : explanation ? (
                    <div className="p-3.5 rounded-lg border bg-card text-xs space-y-2">
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground pb-1 border-b">
                        <span>Provider: <strong className="text-foreground">{explanation.provider_used}</strong></span>
                        <span>Language: {explanation.language === "kn" ? "ಕನ್ನಡ" : "English"}</span>
                      </div>
                      <p className="whitespace-pre-line text-foreground leading-relaxed">
                        {explanation.explanation}
                      </p>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg border border-dashed text-xs text-muted-foreground text-center">
                      Need a clearer breakdown? Click above to generate an evidence-grounded explanation in English or Kannada.
                    </div>
                  )}
                </div>

                {/* Audit Trail */}
                <div className="space-y-2 pt-2 border-t">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5" /> State Transition Audit Trail
                  </h4>
                  {loadingHistory ? (
                    <div className="text-xs text-muted-foreground">Loading audit records...</div>
                  ) : history.length === 0 ? (
                    <div className="text-xs text-muted-foreground italic">No state changes recorded yet (currently in initial NEW status).</div>
                  ) : (
                    <div className="space-y-1.5 text-xs">
                      {history.map((h) => (
                        <div key={h.id} className="p-2 rounded border bg-muted/20 flex items-center justify-between">
                          <div>
                            <span className="font-semibold">{h.previous_status}</span> &rarr;{" "}
                            <span className="font-semibold text-primary">{h.new_status}</span>
                            {h.reason && <span className="text-muted-foreground ml-2">({h.reason})</span>}
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(h.changed_at).toLocaleString("en-IN")}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Modal Footer Lifecycle Actions */}
              <div className="p-4 border-t bg-muted/20 flex items-center justify-between gap-2">
                <div className="text-xs text-muted-foreground">
                  Update alert status:
                </div>
                <div className="flex items-center gap-2">
                  {selectedAlert.status === "NEW" && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={updatingStatusId === selectedAlert.event_id}
                      onClick={() => handleStatusChange(selectedAlert.event_id, "ACKNOWLEDGED")}
                      className="text-xs"
                    >
                      Acknowledge
                    </Button>
                  )}
                  {(selectedAlert.status === "NEW" || selectedAlert.status === "ACKNOWLEDGED") && (
                    <Button
                      size="sm"
                      variant="default"
                      disabled={updatingStatusId === selectedAlert.event_id}
                      onClick={() => handleStatusChange(selectedAlert.event_id, "RESOLVED")}
                      className="text-xs bg-emerald-600 hover:bg-emerald-700"
                    >
                      <Check className="w-3.5 h-3.5 mr-1" /> Mark Resolved
                    </Button>
                  )}
                  {(selectedAlert.status === "NEW" || selectedAlert.status === "ACKNOWLEDGED") && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={updatingStatusId === selectedAlert.event_id}
                      onClick={() => handleStatusChange(selectedAlert.event_id, "DISMISSED")}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      Dismiss
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageContainer>
  );
}

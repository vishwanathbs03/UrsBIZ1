"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Clock,
  CheckCircle2,
  XCircle,
  Ban,
  Filter,
  IndianRupee,
  RefreshCw,
  Eye,
  AlertCircle,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  collaborationService,
  type ApprovalRequestOut,
  type ApprovalSummaryResponse,
  type BusinessRole,
} from "@/services";
import { ReviewApprovalModal } from "./ReviewApprovalModal";
import { useLanguage } from "@/context/language-context";
import { formatINR, formatDate } from "@/lib/formatters";
import { cn } from "@/lib/utils";

interface ApprovalQueueProps {
  currentRole: BusinessRole;
  currentUserId?: number;
}

const STATUS_FILTERS = ["ALL", "PENDING", "APPROVED", "REJECTED", "CANCELLED"] as const;

export function ApprovalQueue({ currentRole, currentUserId }: ApprovalQueueProps) {
  const [requests, setRequests] = useState<ApprovalRequestOut[]>([]);
  const [summary, setSummary] = useState<ApprovalSummaryResponse | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeReviewRequest, setActiveReviewRequest] = useState<ApprovalRequestOut | null>(null);

  const { t, language } = useLanguage();
  const canReview = currentRole === "Owner" || currentRole === "Administrator" || currentRole === "Manager";

  const loadApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const [listRes, summaryRes] = await Promise.all([
        collaborationService.listApprovalRequests(selectedStatus),
        collaborationService.getApprovalSummary(),
      ]);
      setRequests(listRes.requests);
      setSummary(summaryRes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load approval requests");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, [selectedStatus]);

  const handleCancel = async (id: number) => {
    if (!confirm(language === "kn" ? "ಈ ಅನುಮೋದನೆ ವಿನಂತಿಯನ್ನು ರದ್ದುಗೊಳಿಸಲು ನೀವು ಖಚಿತವಾಗಿ ಬಯಸುವಿರಾ?" : "Are you sure you want to cancel this approval request?")) {
      return;
    }
    try {
      await collaborationService.cancelApprovalRequest(id);
      loadApprovals();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to cancel request");
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary KPI Strip */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
              <Clock className="w-3.5 h-3.5 text-amber-500" />
              <span>{language === "kn" ? "ಅನುಮೋದನೆ ಬಾಕಿ" : "Pending Approvals"}</span>
            </div>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {summary.pending}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              <span>{language === "kn" ? "ಅನುಮೋದಿತ" : "Approved"}</span>
            </div>
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
              {summary.approved}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
              <XCircle className="w-3.5 h-3.5 text-red-500" />
              <span>{language === "kn" ? "ತಿರಸ್ಕೃತ" : "Rejected"}</span>
            </div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
              {summary.rejected}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
              <Ban className="w-3.5 h-3.5 text-slate-400" />
              <span>{language === "kn" ? "ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ" : "Cancelled"}</span>
            </div>
            <div className="text-2xl font-bold text-slate-700 dark:text-slate-300 mt-1">
              {summary.cancelled}
            </div>
          </div>
        </div>
      )}

      {/* Filter and Controls Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-1.5 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-slate-400 mr-1" />
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSelectedStatus(s)}
              className={cn(
                "px-2.5 py-1 rounded-lg text-xs font-semibold transition-all min-h-[36px]",
                language === "kn" && "font-kannada",
                selectedStatus === s
                  ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              {s === "ALL"
                ? (language === "kn" ? "ಎಲ್ಲವೂ" : "ALL")
                : s === "PENDING"
                ? (language === "kn" ? "ಬಾಕಿ" : "PENDING")
                : s === "APPROVED"
                ? (language === "kn" ? "ಅನುಮೋದಿತ" : "APPROVED")
                : s === "REJECTED"
                ? (language === "kn" ? "ತಿರಸ್ಕೃತ" : "REJECTED")
                : (language === "kn" ? "ರದ್ದುಗೊಂಡಿದೆ" : "CANCELLED")}
            </button>
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadApprovals}
          disabled={loading}
          className="text-xs h-8 gap-1.5 min-h-[36px]"
          aria-label={t("common.refresh", "Refresh queue")}
        >
          <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
          <span>{t("common.refresh", "Refresh")}</span>
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl border border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/20 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Requests List */}
      <div className="space-y-3">
        {loading && requests.length === 0 ? (
          <div className="text-center py-12 text-xs text-slate-400">
            {t("a11y.loadingState", "Loading approval queue...")}
          </div>
        ) : requests.length === 0 ? (
          <div className="p-8 rounded-xl border border-slate-200 dark:border-slate-800 text-center space-y-2 bg-slate-50/50 dark:bg-slate-900/50">
            <ShieldCheck className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto" />
            <h4 className={cn("text-sm font-semibold text-slate-700 dark:text-slate-300", language === "kn" && "font-kannada")}>
              {language === "kn" ? "ಯಾವುದೇ ಅನುಮೋದನೆ ವಿನಂತಿಗಳಿಲ್ಲ" : "No Approval Requests in Queue"}
            </h4>
            <p className={cn("text-xs text-slate-400 max-w-sm mx-auto", language === "kn" && "font-kannada")}>
              {language === "kn"
                ? "ಸೂಕ್ಷ್ಮ ಹಣಕಾಸು ನಿಯಂತ್ರಣಗಳಿಗೆ ಸಲ್ಲಿಸಲಾದ ಎಲ್ಲಾ ವಿನಂತಿಗಳು ಇಲ್ಲಿ ಗೋಚರಿಸುತ್ತವೆ."
                : "All sensitive actions requiring secondary management approval will appear here."}
            </p>
          </div>
        ) : (
          requests.map((req) => {
            const isPending = req.status === "PENDING";
            const isRequester = currentUserId && req.requester_user_id === currentUserId;

            return (
              <div
                key={req.id}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-3 hover:border-slate-300 dark:hover:border-slate-700 transition-all"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="text-[10px] font-mono uppercase">
                        {req.entity_type}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={
                          req.status === "APPROVED"
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300"
                            : req.status === "REJECTED"
                            ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-red-300"
                            : req.status === "PENDING"
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300"
                            : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                        }
                      >
                        {req.status}
                      </Badge>
                      {req.financial_impact_amount !== null && req.financial_impact_amount !== undefined && (
                        <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 flex items-center">
                          {formatINR(req.financial_impact_amount, { language })}
                        </span>
                      )}
                    </div>
                    <h3 className={cn("text-sm font-bold text-slate-900 dark:text-slate-100", language === "kn" && "font-kannada")}>
                      {req.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {canReview && isPending && (
                      <Button
                        size="sm"
                        onClick={() => setActiveReviewRequest(req)}
                        className={cn("text-xs h-8 gap-1.5 min-h-[36px]", language === "kn" && "font-kannada")}
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        {language === "kn" ? "ವಿನಂತಿ ಪರಿಶೀಲಿಸಿ" : "Review Request"}
                      </Button>
                    )}

                    {!isPending && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveReviewRequest(req)}
                        className={cn("text-xs h-8 gap-1.5 min-h-[36px]", language === "kn" && "font-kannada")}
                      >
                        <Eye className="w-3.5 h-3.5" />
                        {language === "kn" ? "ಆಡಿಟ್ ಲಾಗ್ ನೋಡಿ" : "View Audit Log"}
                      </Button>
                    )}

                    {isPending && (isRequester || currentRole === "Owner" || currentRole === "Administrator") && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancel(req.id)}
                        className={cn("text-xs h-8 text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 min-h-[36px]", language === "kn" && "font-kannada")}
                      >
                        {t("common.cancel", "Cancel")}
                      </Button>
                    )}
                  </div>
                </div>

                {req.description && (
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    {req.description}
                  </p>
                )}

                {req.decision_notes && (
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 text-xs border border-slate-200 dark:border-slate-800">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {language === "kn" ? "ಪರಿಶೀಲನಾ ಟಿಪ್ಪಣಿ: " : "Review Notes: "}
                    </span>
                    <span className="text-slate-700 dark:text-slate-300">&ldquo;{req.decision_notes}&rdquo;</span>
                    {req.approver_name && (
                      <span className="text-[10px] text-slate-400 block mt-1">
                        — {language === "kn" ? "ಪರಿಶೀಲಿಸಿದವರು" : "Reviewed by"} {req.approver_name}{" "}
                        {req.reviewed_at ? formatDate(req.reviewed_at, { format: "short", language }) : ""}
                      </span>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800">
                  <span>
                    {language === "kn" ? "ವಿನಂತಿಸಿದವರು: " : "Requested by: "}
                    <strong>{req.requester_name || req.requester_email || `User #${req.requester_user_id}`}</strong>
                  </span>
                  <span>
                    {language === "kn" ? "ಸಲ್ಲಿಸಿದ ದಿನಾಂಕ: " : "Submitted: "}
                    {formatDate(req.requested_at, { format: "datetime", language })}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      <ReviewApprovalModal
        isOpen={Boolean(activeReviewRequest)}
        onClose={() => setActiveReviewRequest(null)}
        onSuccess={loadApprovals}
        approval={activeReviewRequest}
        currentUserId={currentUserId}
      />
    </div>
  );
}

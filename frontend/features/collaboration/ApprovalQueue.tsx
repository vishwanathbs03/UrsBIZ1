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
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load approval requests.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, [selectedStatus, currentRole]);

  const handleCancel = async (reqId: number) => {
    if (!confirm("Are you sure you want to cancel this approval request?")) return;
    try {
      await collaborationService.cancelApprovalRequest(reqId);
      loadApprovals();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Failed to cancel request.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
            <span className="text-xs text-slate-500 block">Total Requests</span>
            <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{summary.total}</span>
          </div>
          <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20 shadow-sm">
            <span className="text-xs text-amber-700 dark:text-amber-400 block font-medium flex items-center gap-1">
              <Clock className="w-3 h-3" /> Pending Review
            </span>
            <span className="text-2xl font-bold text-amber-900 dark:text-amber-200">{summary.pending}</span>
          </div>
          <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/20 shadow-sm">
            <span className="text-xs text-emerald-700 dark:text-emerald-400 block font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Approved
            </span>
            <span className="text-2xl font-bold text-emerald-900 dark:text-emerald-200">{summary.approved}</span>
          </div>
          <div className="p-4 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20 shadow-sm">
            <span className="text-xs text-red-700 dark:text-red-400 block font-medium flex items-center gap-1">
              <XCircle className="w-3 h-3" /> Rejected
            </span>
            <span className="text-2xl font-bold text-red-900 dark:text-red-200">{summary.rejected}</span>
          </div>
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 shadow-sm">
            <span className="text-xs text-slate-500 block flex items-center gap-1">
              <Ban className="w-3 h-3" /> Cancelled
            </span>
            <span className="text-2xl font-bold text-slate-700 dark:text-slate-300">{summary.cancelled}</span>
          </div>
        </div>
      )}

      {/* Filter Tabs & Refresh */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-x-auto max-w-full">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => setSelectedStatus(st)}
              className={`px-3 py-1.5 text-xs rounded-lg font-medium transition whitespace-nowrap ${
                selectedStatus === st
                  ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-sm"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
              }`}
            >
              {st === "ALL" ? "All Requests" : st.charAt(0) + st.slice(1).toLowerCase()}
            </button>
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadApprovals}
          disabled={loading}
          className="gap-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh Queue
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 rounded-xl">
          <AlertCircle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Requests List */}
      <div className="space-y-3">
        {requests.length === 0 ? (
          <div className="p-12 text-center rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-500 text-xs">
            No approval requests found matching status &ldquo;{selectedStatus}&rdquo;.
          </div>
        ) : (
          requests.map((req) => {
            const isPending = req.status === "PENDING";
            const isApproved = req.status === "APPROVED";
            const isRejected = req.status === "REJECTED";
            const isRequester = currentUserId && req.requester_user_id === currentUserId;

            return (
              <div
                key={req.id}
                className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 transition space-y-3"
              >
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5">
                        {req.entity_type} #{req.entity_id}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={
                          isApproved
                            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300"
                            : isRejected
                            ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-red-300"
                            : isPending
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300"
                            : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                        }
                      >
                        {req.status}
                      </Badge>
                      {req.financial_impact_amount !== null && req.financial_impact_amount !== undefined && (
                        <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 flex items-center">
                          ₹{req.financial_impact_amount.toLocaleString("en-IN")}
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      {req.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    {canReview && isPending && (
                      <Button
                        size="sm"
                        onClick={() => setActiveReviewRequest(req)}
                        className="text-xs h-8 gap-1.5"
                      >
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Review Request
                      </Button>
                    )}

                    {!isPending && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveReviewRequest(req)}
                        className="text-xs h-8 gap-1.5"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View Audit Log
                      </Button>
                    )}

                    {isPending && (isRequester || currentRole === "Owner" || currentRole === "Administrator") && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancel(req.id)}
                        className="text-xs h-8 text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                      >
                        Cancel
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
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Review Notes: </span>
                    <span className="text-slate-700 dark:text-slate-300">&ldquo;{req.decision_notes}&rdquo;</span>
                    {req.approver_name && (
                      <span className="text-[10px] text-slate-400 block mt-1">
                        — Reviewed by {req.approver_name} on {req.reviewed_at ? new Date(req.reviewed_at).toLocaleDateString() : ""}
                      </span>
                    )}
                  </div>
                )}

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800">
                  <span>
                    Requested by <strong>{req.requester_name || req.requester_email || `User #${req.requester_user_id}`}</strong>
                  </span>
                  <span>
                    Submitted: {new Date(req.requested_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
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

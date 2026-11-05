"use client";

import React, { useState } from "react";
import {
  X,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  IndianRupee,
  Clock,
  User,
  ShieldCheck,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  collaborationService,
  type ApprovalRequestOut,
} from "@/services";

interface ReviewApprovalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  approval: ApprovalRequestOut | null;
  currentUserId?: number;
}

export function ReviewApprovalModal({
  isOpen,
  onClose,
  onSuccess,
  approval,
  currentUserId,
}: ReviewApprovalModalProps) {
  const [decisionNotes, setDecisionNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !approval) return null;

  const isSelf = currentUserId && approval.requester_user_id === currentUserId;

  const handleReview = async (action: "APPROVE" | "REJECT") => {
    setLoading(true);
    setError(null);
    try {
      await collaborationService.reviewApprovalRequest(approval.id, {
        action,
        decision_notes: decisionNotes.trim() || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err?.message || "Failed to process review."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Review Approval Request #{approval.id}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Enforce dual-control business governance and audit tracking
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="flex items-center gap-2 p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 rounded-xl">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isSelf && (
            <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/50 text-xs text-amber-800 dark:text-amber-300">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
              <div>
                <strong>Dual-Control Notice:</strong> You submitted this approval request. Unless you are the sole registered business owner, dual-control policy mandates an independent manager or administrator review this request.
              </div>
            </div>
          )}

          {/* Details Card */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {approval.entity_type} #{approval.entity_id}
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                  {approval.title}
                </h3>
              </div>
              <Badge
                variant="outline"
                className={
                  approval.status === "APPROVED"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                    : approval.status === "REJECTED"
                    ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                }
              >
                {approval.status}
              </Badge>
            </div>

            {approval.description && (
              <p className="text-xs text-slate-600 dark:text-slate-300">
                {approval.description}
              </p>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 text-xs border-t border-slate-200 dark:border-slate-800">
              <div>
                <span className="text-slate-500 block">Financial Impact</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {approval.financial_impact_amount !== null && approval.financial_impact_amount !== undefined
                    ? `₹${approval.financial_impact_amount.toLocaleString("en-IN")}`
                    : "None stated"}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Requester</span>
                <span className="font-medium text-slate-900 dark:text-slate-100 truncate block">
                  {approval.requester_name || approval.requester_email || `User #${approval.requester_user_id}`}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Submitted At</span>
                <span className="text-slate-700 dark:text-slate-300">
                  {new Date(approval.requested_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>

          {/* Audit History */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2 flex items-center gap-1.5">
              <History className="w-3.5 h-3.5" />
              Append-Only Audit Log
            </h4>
            <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
              {approval.audits.map((a) => (
                <div
                  key={a.id}
                  className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-xs flex items-start justify-between gap-3"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900 dark:text-slate-100">
                        {a.action}
                      </span>
                      {a.new_status && (
                        <span className="text-[10px] text-slate-500">
                          → {a.new_status}
                        </span>
                      )}
                    </div>
                    {a.notes && (
                      <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                        &ldquo;{a.notes}&rdquo;
                      </p>
                    )}
                    <span className="text-[10px] text-slate-400 block mt-1">
                      By {a.user_email || `User #${a.user_id}`}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 whitespace-nowrap">
                    {new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Review Decision Notes */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
              Review Rationale / Decision Notes (Persisted to Audit)
            </label>
            <textarea
              rows={3}
              placeholder="Provide context or explanation for approval or rejection..."
              value={decisionNotes}
              onChange={(e) => setDecisionNotes(e.target.value)}
              className="w-full text-xs p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 px-6 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-950/40">
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>

          {approval.status === "PENDING" && (
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={loading}
                onClick={() => handleReview("REJECT")}
                className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 border-red-200 dark:border-red-900/50 gap-1.5"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </Button>
              <Button
                type="button"
                disabled={loading}
                onClick={() => handleReview("APPROVE")}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
              >
                <CheckCircle2 className="w-4 h-4" />
                Approve Request
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

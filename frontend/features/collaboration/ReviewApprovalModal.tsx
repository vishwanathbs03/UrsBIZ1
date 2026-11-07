"use client";

import React, { useState } from "react";
import {
  X,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
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
import { useLanguage } from "@/context/language-context";
import { formatINR, formatDate } from "@/lib/formatters";
import { cn } from "@/lib/utils";

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

  const { t, language } = useLanguage();

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
    } catch (err: unknown) {
      const msg = err && typeof err === "object" && "response" in err
        ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail)
        : err instanceof Error ? err.message : "Failed to process review.";
      setError(msg || "Failed to process review.");
    } finally {
      setLoading(false);
    }
  };

  const isPending = approval.status === "PENDING";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={language === "kn" ? "ಅನುಮೋದನೆ ಪರಿಶೀಲನಾ ವಿವರ" : "Approval Review Details"}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-xs animate-in fade-in-50 duration-200"
    >
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 max-w-xl w-full max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col justify-between">
        {/* Header */}
        <div className="p-4 px-6 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className={cn("text-base font-bold text-slate-900 dark:text-slate-100", language === "kn" && "font-kannada")}>
                {language === "kn" ? "ಅನುಮೋದನೆ ವಿನಂತಿ ಪರಿಶೀಲನೆ" : "Review Approval Request"}
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                ID #{approval.id} • {approval.entity_type}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close", "Close")}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-xl border border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/20 text-xs text-red-600 dark:text-red-400 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {isSelf && isPending && (
            <div className="p-3 rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                {language === "kn"
                  ? "ನೀವು ಈ ವಿನಂತಿಯನ್ನು ಸಲ್ಲಿಸಿದ್ದೀರಿ. ಆಡಳಿತಾತ್ಮಕ ನೀತಿಯ ಪ್ರಕಾರ ಮತ್ತೊಬ್ಬ ನಿರ್ವಾಹಕರು ಇದನ್ನು ಅನುಮೋದಿಸಬೇಕು (ಏಕಮಾತ್ರ ಮಾಲೀಕರನ್ನು ಹೊರತುಪಡಿಸಿ)."
                  : "You submitted this request. Platform governance requires independent secondary approval, unless operating as a sole registered business owner."}
              </span>
            </div>
          )}

          {/* Request Details */}
          <div className="space-y-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/30">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className={cn("text-sm font-bold text-slate-900 dark:text-slate-100", language === "kn" && "font-kannada")}>
                  {approval.title}
                </h4>
                <span className="text-xs text-slate-500 font-mono">
                  Target: #{approval.entity_id}
                </span>
              </div>
              <Badge
                variant="outline"
                className={
                  approval.status === "APPROVED"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300"
                    : approval.status === "REJECTED"
                    ? "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-red-300"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300"
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
                <span className={cn("text-slate-500 block", language === "kn" && "font-kannada")}>
                  {language === "kn" ? "ಹಣಕಾಸು ಪ್ರಭಾವ" : "Financial Impact"}
                </span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {approval.financial_impact_amount !== null && approval.financial_impact_amount !== undefined
                    ? formatINR(approval.financial_impact_amount, { language })
                    : (language === "kn" ? "ಯಾವುದೂ ಇಲ್ಲ" : "None stated")}
                </span>
              </div>
              <div>
                <span className={cn("text-slate-500 block", language === "kn" && "font-kannada")}>
                  {language === "kn" ? "ವಿನಂತಿದಾರರು" : "Requester"}
                </span>
                <span className="font-medium text-slate-900 dark:text-slate-100 truncate block">
                  {approval.requester_name || approval.requester_email || `User #${approval.requester_user_id}`}
                </span>
              </div>
              <div>
                <span className={cn("text-slate-500 block", language === "kn" && "font-kannada")}>
                  {language === "kn" ? "ಸಲ್ಲಿಸಿದ ದಿನಾಂಕ" : "Submitted At"}
                </span>
                <span className="text-slate-700 dark:text-slate-300">
                  {formatDate(approval.requested_at, { format: "short", language })}
                </span>
              </div>
            </div>
          </div>

          {/* Audit History */}
          <div>
            <h4 className={cn("text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2 flex items-center gap-1.5", language === "kn" && "font-kannada")}>
              <History className="w-3.5 h-3.5" />
              {language === "kn" ? "ಆಡಿಟ್ ಇತಿಹಾಸ ಲಾಗ್" : "Append-Only Audit Log"}
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
                      {language === "kn" ? "ಬಳಕೆದಾರ: " : "By "} {a.user_email || `User #${a.user_id}`}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 whitespace-nowrap">
                    {formatDate(a.created_at, { format: "datetime", language })}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Review Decision Notes */}
          <div>
            <label className={cn("block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5", language === "kn" && "font-kannada")}>
              {language === "kn" ? "ಪರಿಶೀಲನಾ ನಿರ್ಧಾರದ ಸಮರ್ಥನೆ / ಟಿಪ್ಪಣಿ" : "Review Rationale / Decision Notes (Persisted to Audit)"}
            </label>
            <textarea
              rows={3}
              placeholder={language === "kn" ? "ಅನುಮೋದನೆ ಅಥವಾ ತಿರಸ್ಕಾರಕ್ಕೆ ಕಾರಣವನ್ನು ನಮೂದಿಸಿ..." : "Provide context or explanation for approval or rejection..."}
              value={decisionNotes}
              onChange={(e) => setDecisionNotes(e.target.value)}
              className={cn("w-full text-xs p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-primary", language === "kn" && "font-kannada")}
            />
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 px-6 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-950/40">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={loading} className="text-xs min-h-[36px]">
            {t("common.close", "Close")}
          </Button>

          {isPending && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleReview("REJECT")}
                disabled={loading}
                className={cn("text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30 border-red-200 dark:border-red-900/50 gap-1.5 min-h-[36px]", language === "kn" && "font-kannada")}
              >
                <XCircle className="w-3.5 h-3.5" />
                {language === "kn" ? "ತಿರಸ್ಕರಿಸಿ" : "Reject"}
              </Button>
              <Button
                size="sm"
                onClick={() => handleReview("APPROVE")}
                disabled={loading}
                className={cn("text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 min-h-[36px]", language === "kn" && "font-kannada")}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                {language === "kn" ? "ಅನುಮೋದಿಸಿ" : "Approve"}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

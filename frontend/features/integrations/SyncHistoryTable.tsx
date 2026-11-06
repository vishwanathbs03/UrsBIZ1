"use client";

import React from "react";
import { SyncExecutionOut } from "@/services/integration-service";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  History,
  Layers,
  RefreshCw,
  XCircle,
} from "lucide-react";

interface SyncHistoryTableProps {
  executions: SyncExecutionOut[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
}

export const SyncHistoryTable: React.FC<SyncHistoryTableProps> = ({
  executions,
  total,
  page,
  pageSize,
  onPageChange,
}) => {
  const totalPages = Math.ceil(total / pageSize) || 1;

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCEEDED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" /> Succeeded
          </span>
        );
      case "PARTIAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-3 w-3" /> Partial
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-destructive/10 text-destructive border border-destructive/20">
            <XCircle className="h-3 w-3" /> Failed
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-primary/10 text-primary border border-primary/20 animate-pulse">
            <RefreshCw className="h-3 w-3 animate-spin" /> Running
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-muted text-muted-foreground border border-border">
            <Clock className="h-3 w-3" /> {status}
          </span>
        );
    }
  };

  if (executions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/40 p-12 text-center">
        <History className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
        <h3 className="text-base font-semibold text-foreground mb-1">
          No synchronization history recorded
        </h3>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto">
          When you trigger a manual sync or automated webhook, batch execution metrics and data provenance will be logged here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 border-b border-border text-xs uppercase font-semibold text-muted-foreground">
              <tr>
                <th className="py-3 px-4">Execution ID</th>
                <th className="py-3 px-4">Connector</th>
                <th className="py-3 px-4">Trigger</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-center">Discovered</th>
                <th className="py-3 px-4 text-center">Imported</th>
                <th className="py-3 px-4 text-center">Duplicates</th>
                <th className="py-3 px-4 text-center">Skipped</th>
                <th className="py-3 px-4">Completed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {executions.map((exec) => (
                <tr key={exec.id} className="hover:bg-muted/30 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs font-medium text-foreground">
                    {exec.execution_id}
                  </td>
                  <td className="py-3 px-4 text-foreground/90 font-medium">
                    {exec.connector_id}
                  </td>
                  <td className="py-3 px-4 text-muted-foreground text-xs">
                    {exec.trigger_type}
                  </td>
                  <td className="py-3 px-4">
                    {renderStatusBadge(exec.status)}
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-xs text-foreground">
                    {exec.records_discovered}
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    {exec.records_imported}
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-xs text-muted-foreground">
                    {exec.duplicate_count}
                  </td>
                  <td className="py-3 px-4 text-center font-mono text-xs text-amber-600 dark:text-amber-400">
                    {exec.records_skipped + exec.validation_failure_count}
                  </td>
                  <td className="py-3 px-4 text-xs text-muted-foreground whitespace-nowrap">
                    {exec.completed_at
                      ? new Date(exec.completed_at).toLocaleString()
                      : "In progress"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span>
            Showing {(page - 1) * pageSize + 1} to{" "}
            {Math.min(page * pageSize, total)} of {total} runs
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="px-2.5 py-1 rounded border border-border bg-card disabled:opacity-40 hover:bg-muted"
            >
              Previous
            </button>
            <span className="px-2 font-medium">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="px-2.5 py-1 rounded border border-border bg-card disabled:opacity-40 hover:bg-muted"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

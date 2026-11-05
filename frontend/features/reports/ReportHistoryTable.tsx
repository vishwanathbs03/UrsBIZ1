"use client";

import React, { useState } from "react";
import {
  FileText,
  FileSpreadsheet,
  Download,
  Trash2,
  RefreshCw,
  Clock,
  Calendar,
  AlertCircle,
  CheckCircle2,
  HardDrive,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ReportItemOut, ReportFileFormat } from "@/services";

interface ReportHistoryTableProps {
  reports: ReportItemOut[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  onRefresh: () => void;
  onDownload: (report: ReportItemOut) => void;
  onDelete: (id: number) => void;
  onPageChange: (newPage: number) => void;
}

export function ReportHistoryTable({
  reports,
  total,
  page,
  pageSize,
  isLoading,
  onRefresh,
  onDownload,
  onDelete,
  onPageChange,
}: ReportHistoryTableProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  const handleDeleteWithConfirm = (id: number) => {
    if (window.confirm("Are you sure you want to archive this generated report export? The historical audit record will be preserved.")) {
      onDelete(id);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Bar */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Generated Export History</h3>
          <p className="text-xs text-muted-foreground">
            Authoritative documents previously compiled and stored for your business.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onRefresh}
          disabled={isLoading}
          className="text-xs gap-1.5 h-8"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Table */}
      <div className="border rounded-xl bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/50 border-b font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
              <tr>
                <th className="px-4 py-3">Report Document</th>
                <th className="px-4 py-3">Observation Period</th>
                <th className="px-4 py-3">Format</th>
                <th className="px-4 py-3">File Size</th>
                <th className="px-4 py-3">Downloads</th>
                <th className="px-4 py-3">Generated At</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {reports.map((report) => (
                <tr key={report.id} className="hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-foreground">{report.title}</div>
                    <div className="text-[10px] text-muted-foreground capitalize">
                      {report.category.replace("_", " ")}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                    {report.period_start} → {report.period_end}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                        report.file_format === "pdf"
                          ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50"
                          : report.file_format === "xlsx"
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50"
                          : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50"
                      }`}
                    >
                      {report.file_format}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground font-mono">
                    {formatBytes(report.file_size_bytes)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {report.download_count} {report.download_count === 1 ? "time" : "times"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                    {new Date(report.created_at).toLocaleDateString("en-IN", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDownload(report)}
                        className="h-7 text-xs gap-1 px-2.5"
                      >
                        <Download className="w-3 h-3" />
                        Download
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDeleteWithConfirm(report.id)}
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {reports.length === 0 && !isLoading && (
          <div className="text-center py-12">
            <HardDrive className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-30" />
            <h4 className="text-sm font-semibold text-foreground">No reports generated yet</h4>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
              Select a report from the catalogue above to preview and export evidence-backed documents.
            </p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
          <span>
            Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} reports
          </span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="h-7 text-xs px-2.5"
            >
              Previous
            </Button>
            <span className="px-2">
              Page {page} of {totalPages}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="h-7 text-xs px-2.5"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

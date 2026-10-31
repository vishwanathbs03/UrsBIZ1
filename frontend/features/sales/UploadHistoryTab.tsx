"use client";

import React, { useState } from "react";
import { FileText, Trash2, CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { salesService, type SalesUploadListItem } from "@/services/sales-service";

interface UploadHistoryTabProps {
  uploads: SalesUploadListItem[];
  onUploadDeleted: () => void;
}

export function UploadHistoryTab({ uploads, onUploadDeleted }: UploadHistoryTabProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this upload? All associated transactions will be removed.")) {
      return;
    }
    setDeletingId(id);
    try {
      await salesService.deleteUpload(id);
      onUploadDeleted();
    } catch (err) {
      alert("Failed to delete upload.");
    } finally {
      setDeletingId(null);
    }
  };

  if (!uploads || uploads.length === 0) {
    return (
      <div className="rounded-xl border border-dark-border bg-dark-card p-12 text-center">
        <FileText className="mx-auto h-12 w-12 text-dark-text-muted" />
        <h3 className="mt-4 text-base font-semibold text-dark-text-primary">No Upload History</h3>
        <p className="mt-1 text-xs text-dark-text-muted">
          Uploaded sales records will appear here with auditable data quality metrics.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-md">
      <h3 className="mb-4 text-sm font-bold text-dark-text-primary uppercase tracking-wider">
        Sales Data Ingestion Log
      </h3>
      <div className="overflow-x-auto rounded-lg border border-dark-border">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-dark-border bg-dark-bg text-dark-text-muted">
            <tr>
              <th className="p-3">File Name</th>
              <th className="p-3">Format</th>
              <th className="p-3">Uploaded At</th>
              <th className="p-3">Valid Rows</th>
              <th className="p-3">Rejected Rows</th>
              <th className="p-3">Quality Score</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-border">
            {uploads.map((u) => (
              <tr key={u.id} className="hover:bg-dark-border/20">
                <td className="p-3 font-semibold text-dark-text-primary flex items-center gap-2">
                  <FileText className="h-4 w-4 text-neon-cyan shrink-0" />
                  {u.filename}
                </td>
                <td className="p-3 uppercase font-mono text-dark-text-muted">{u.file_format}</td>
                <td className="p-3 text-dark-text-muted">{u.created_at}</td>
                <td className="p-3 font-mono text-neon-emerald">{u.valid_row_count.toLocaleString()}</td>
                <td className="p-3 font-mono text-neon-rose">{u.invalid_row_count.toLocaleString()}</td>
                <td className="p-3 font-mono font-semibold text-neon-cyan">{u.quality_score}%</td>
                <td className="p-3 text-right">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={deletingId === u.id}
                    onClick={() => handleDelete(u.id)}
                    className="h-7 px-2 text-neon-rose hover:bg-neon-rose/10 hover:text-neon-rose"
                  >
                    {deletingId === u.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

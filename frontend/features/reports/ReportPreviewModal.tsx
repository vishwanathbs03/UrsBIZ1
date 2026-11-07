"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Download,
  ShieldCheck,
  AlertTriangle,
  Info,
  Calendar,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  FileText,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type {
  ReportFileFormat,
  ReportPreviewResponse,
  ReportCoverageStatus,
} from "@/services";

interface ReportPreviewModalProps {
  preview: ReportPreviewResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onProceedToGenerate: (format: ReportFileFormat) => void;
  isGenerating?: boolean;
}

const COVERAGE_BADGE_META: Record<
  ReportCoverageStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; color: string }
> = {
  AVAILABLE: {
    label: "Full Verified Coverage",
    variant: "default",
    color: "bg-emerald-500/10 text-emerald-600 border-emerald-300 dark:border-emerald-800",
  },
  PARTIAL: {
    label: "Partial Ingested Data",
    variant: "secondary",
    color: "bg-amber-500/10 text-amber-600 border-amber-300 dark:border-amber-800",
  },
  MISSING_DATA: {
    label: "Missing Ledger Data",
    variant: "destructive",
    color: "bg-rose-500/10 text-rose-600 border-rose-300 dark:border-rose-800",
  },
  UNVERIFIED_GAP: {
    label: "Unverified Calendar Gap",
    variant: "outline",
    color: "bg-purple-500/10 text-purple-600 border-purple-300 dark:border-purple-800",
  },
};

export function ReportPreviewModal({
  preview,
  isOpen,
  onClose,
  onProceedToGenerate,
  isGenerating = false,
}: ReportPreviewModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !preview) return null;

  const [showProvenanceDrawer, setShowProvenanceDrawer] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<ReportFileFormat>("pdf");

  const coverageMeta = COVERAGE_BADGE_META[preview.data_coverage_status] || {
    label: preview.data_coverage_status,
    variant: "outline",
    color: "bg-muted text-muted-foreground",
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Report Preview" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-card border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-5 sm:p-6 border-b shrink-0 bg-muted/20">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                {preview.category.replace("_", " ")}
              </Badge>
              <span
                className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${coverageMeta.color}`}
              >
                {coverageMeta.label}
              </span>
              <div className="flex items-center gap-1 text-xs text-muted-foreground ml-2">
                <Calendar className="w-3.5 h-3.5" />
                <span>
                  {preview.period_start} to {preview.period_end}
                </span>
              </div>
            </div>
            <h3 className="text-xl font-bold text-foreground tracking-tight">{preview.title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Preview Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {/* Missing Data Warning Banner */}
          {preview.data_coverage_status === "MISSING_DATA" && (
            <div className="p-4 rounded-xl border border-rose-300 dark:border-rose-900/60 bg-rose-500/10 text-rose-800 dark:text-rose-300 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <div className="space-y-1 text-xs">
                <h4 className="font-bold text-sm">Authoritative Sales Data Absent</h4>
                <p>
                  No transaction records were identified in the specified observation window. Default MSME micro-enterprise benchmark assumptions have been applied to demonstrate structure without fabricating numbers.
                </p>
              </div>
            </div>
          )}

          {/* Key Findings List */}
          <div className="space-y-2.5">
            <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              Executive Findings & Evidence Highlights
            </h4>
            <div className="rounded-xl border bg-card p-4 space-y-2">
              {preview.findings.map((f, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-xs text-foreground/90 leading-relaxed">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Headline KPIs Grid */}
          {Object.keys(preview.summary_kpis).length > 0 && (
            <div className="space-y-2.5">
              <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                Summary Metrics Snapshot
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(preview.summary_kpis).map(([key, val]) => {
                  const formattedKey = key.replace(/_/g, " ").replace(/\binr\b/i, "(INR)");
                  const displayVal =
                    typeof val === "number"
                      ? val >= 1000
                        ? `₹${val.toLocaleString()}`
                        : val.toString()
                      : String(val);

                  return (
                    <div key={key} className="p-3.5 rounded-xl border bg-muted/20 space-y-1">
                      <span className="text-[11px] font-medium text-muted-foreground capitalize block truncate">
                        {formattedKey}
                      </span>
                      <div className="text-base font-bold text-foreground truncate">{displayVal}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Sample Tables */}
          {preview.sample_tables && preview.sample_tables.length > 0 && (
            <div className="space-y-4">
              {preview.sample_tables.map((table, tIdx) => (
                <div key={tIdx} className="space-y-2">
                  <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                    {table.title}
                  </h4>
                  <div className="border rounded-xl overflow-hidden overflow-x-auto shadow-sm">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/50 border-b font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
                        <tr>
                          {table.headers.map((h, hIdx) => (
                            <th key={hIdx} className="px-4 py-2.5">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {table.rows.map((row, rIdx) => (
                          <tr key={rIdx} className="hover:bg-muted/20 transition-colors">
                            {row.map((cell, cIdx) => (
                              <td key={cIdx} className="px-4 py-2.5 font-medium text-foreground">
                                {cell !== null && cell !== undefined ? String(cell) : "—"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Evidence Provenance & Methodology Accordion */}
          <div className="border rounded-xl bg-card overflow-hidden">
            <button
              type="button"
              onClick={() => setShowProvenanceDrawer(!showProvenanceDrawer)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span className="text-xs font-bold text-foreground uppercase tracking-wider">
                  Calculation Transparency & Data Provenance
                </span>
              </div>
              {showProvenanceDrawer ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            {showProvenanceDrawer && (
              <div className="p-4 pt-1 border-t space-y-3 bg-muted/10 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <span className="text-[11px] text-muted-foreground block font-medium">Metric / Scope:</span>
                    <p className="font-semibold text-foreground">{preview.provenance.metric_name}</p>
                  </div>
                  <div>
                    <span className="text-[11px] text-muted-foreground block font-medium">Event Nature:</span>
                    <Badge variant="outline" className="text-[10px] font-bold mt-0.5">
                      {preview.provenance.event_nature}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-[11px] text-muted-foreground block font-medium">Calculation Method:</span>
                    <p className="text-foreground">{preview.provenance.calculation_method}</p>
                  </div>
                  <div>
                    <span className="text-[11px] text-muted-foreground block font-medium">Authoritative Source:</span>
                    <p className="text-foreground">{preview.provenance.evidence_source}</p>
                  </div>
                </div>

                {preview.provenance.assumptions && preview.provenance.assumptions.length > 0 && (
                  <div className="space-y-1 pt-2 border-t">
                    <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Applied Assumptions
                    </span>
                    <ul className="list-disc list-inside text-muted-foreground space-y-0.5">
                      {preview.provenance.assumptions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="pt-2 border-t text-[11px] text-muted-foreground italic">
                  {preview.provenance.disclaimer}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 sm:p-5 border-t shrink-0 bg-background flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-xs font-semibold text-muted-foreground">Target Format:</span>
            {(["pdf", "xlsx", "csv"] as ReportFileFormat[]).map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => setSelectedFormat(fmt)}
                className={`text-xs uppercase font-bold px-2.5 py-1 rounded-md border transition-all ${
                  selectedFormat === fmt
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background text-muted-foreground border-border hover:bg-muted"
                }`}
              >
                {fmt}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Button type="button" variant="outline" onClick={onClose} className="text-xs h-9">
              Close Preview
            </Button>
            <Button
              type="button"
              onClick={() => onProceedToGenerate(selectedFormat)}
              disabled={isGenerating}
              className="text-xs gap-1.5 h-9 shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              {isGenerating ? "Exporting..." : `Generate & Download ${selectedFormat.toUpperCase()}`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

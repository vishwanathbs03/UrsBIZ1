"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Calendar,
  FileText,
  FileSpreadsheet,
  Download,
  Eye,
  Sparkles,
  ShieldAlert,
  Info,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type {
  ReportCatalogItem,
  ReportFileFormat,
  ReportGenerateRequest,
  ReportPreviewRequest,
} from "@/services";

interface ReportConfigModalProps {
  reportItem: ReportCatalogItem;
  isOpen: boolean;
  onClose: () => void;
  onPreview: (req: ReportPreviewRequest) => void;
  onGenerate: (req: ReportGenerateRequest) => void;
  isGenerating?: boolean;
}

export function ReportConfigModal({
  reportItem,
  isOpen,
  onClose,
  onPreview,
  onGenerate,
  isGenerating = false,
}: ReportConfigModalProps) {
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

  if (!isOpen) return null;

  // Preset date windows
  const today = new Date();
  const formatIsoDate = (d: Date) => d.toISOString().split("T")[0];

  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const ninetyDaysAgo = new Date();
  ninetyDaysAgo.setDate(today.getDate() - 90);

  const startOfYear = new Date(today.getFullYear(), 0, 1);

  const [datePreset, setDatePreset] = useState<"30d" | "90d" | "ytd" | "custom">("30d");
  const [startDate, setStartDate] = useState(formatIsoDate(thirtyDaysAgo));
  const [endDate, setEndDate] = useState(formatIsoDate(today));
  const [selectedFormat, setSelectedFormat] = useState<ReportFileFormat>(
    reportItem.supported_formats[0] || "pdf"
  );
  const [includeAiSummary, setIncludeAiSummary] = useState(true);

  const handlePresetChange = (preset: "30d" | "90d" | "ytd" | "custom") => {
    setDatePreset(preset);
    if (preset === "30d") {
      setStartDate(formatIsoDate(thirtyDaysAgo));
      setEndDate(formatIsoDate(today));
    } else if (preset === "90d") {
      setStartDate(formatIsoDate(ninetyDaysAgo));
      setEndDate(formatIsoDate(today));
    } else if (preset === "ytd") {
      setStartDate(formatIsoDate(startOfYear));
      setEndDate(formatIsoDate(today));
    }
  };

  const handleTriggerPreview = () => {
    onPreview({
      report_type: reportItem.report_type,
      period_start: startDate,
      period_end: endDate,
    });
  };

  const handleTriggerGenerate = () => {
    onGenerate({
      report_type: reportItem.report_type,
      file_format: selectedFormat,
      period_start: startDate,
      period_end: endDate,
      include_ai_summary: includeAiSummary,
    });
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Report Configuration" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-card border rounded-2xl shadow-2xl p-6 sm:p-7 space-y-6 overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-start justify-between gap-4 pb-4 border-b">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                {reportItem.category.replace("_", " ")}
              </Badge>
              <span className="text-xs text-muted-foreground">Target: {reportItem.target_audience}</span>
            </div>
            <h3 className="text-lg font-bold text-foreground tracking-tight">{reportItem.title}</h3>
            <p className="text-xs text-muted-foreground line-clamp-2">{reportItem.description}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Configuration Options */}
        <div className="space-y-5">
          {/* 1. Date Range Presets */}
          <div className="space-y-2.5">
            <label className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-primary" />
              Observation Window
            </label>
            <div className="grid grid-cols-4 gap-2">
              {[
                { id: "30d", label: "Last 30 Days" },
                { id: "90d", label: "Last 90 Days" },
                { id: "ytd", label: "This Year" },
                { id: "custom", label: "Custom Dates" },
              ].map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handlePresetChange(p.id as any)}
                  className={`text-xs py-2 px-3 rounded-lg border font-medium transition-all ${
                    datePreset === p.id
                      ? "bg-primary text-primary-foreground border-primary shadow-sm"
                      : "bg-background hover:bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Custom Date Range Pickers */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <span className="text-[11px] text-muted-foreground mb-1 block">Start Date</span>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    setDatePreset("custom");
                  }}
                  className="text-xs bg-background"
                />
              </div>
              <div>
                <span className="text-[11px] text-muted-foreground mb-1 block">End Date</span>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => {
                    setEndDate(e.target.value);
                    setDatePreset("custom");
                  }}
                  className="text-xs bg-background"
                />
              </div>
            </div>
          </div>

          {/* 2. Format Picker */}
          <div className="space-y-2.5">
            <label className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-primary" />
              Export Document Format
            </label>
            <div className="grid grid-cols-3 gap-3">
              {reportItem.supported_formats.map((fmt) => {
                const isSelected = selectedFormat === fmt;
                return (
                  <button
                    key={fmt}
                    type="button"
                    onClick={() => setSelectedFormat(fmt)}
                    className={`flex items-center justify-between p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                        : "border-border bg-card hover:bg-muted/50"
                    }`}
                  >
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-foreground">
                        {fmt === "pdf" ? "PDF Document" : fmt === "xlsx" ? "Excel Workbook" : "CSV Raw Table"}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {fmt === "pdf"
                          ? "Branded & Print-Ready"
                          : fmt === "xlsx"
                          ? "Multi-Tab Spreadsheets"
                          : "Deterministic Ingestion"}
                      </div>
                    </div>
                    {isSelected && (
                      <div className="w-4 h-4 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
                        <Check className="w-2.5 h-2.5 stroke-[3]" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. AI Explanation Option */}
          <div className="flex items-center justify-between p-3 rounded-xl border bg-muted/20">
            <div className="space-y-0.5">
              <div className="text-xs font-medium text-foreground flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                Include Executive AI Commentary
              </div>
              <p className="text-[11px] text-muted-foreground">
                Adds non-mutating narrative explanations generated by Gemini with deterministic fallbacks.
              </p>
            </div>
            <input
              type="checkbox"
              checked={includeAiSummary}
              onChange={(e) => setIncludeAiSummary(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
            />
          </div>

          {/* Disclosures & Integrity Assurance */}
          <div className="rounded-xl border border-amber-200/60 dark:border-amber-900/40 bg-amber-500/5 p-3 flex gap-2.5">
            <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="text-[11px] text-amber-800 dark:text-amber-300/90 leading-relaxed">
              <strong>Integrity Guarantee:</strong> All financial and operational figures are calculated deterministically from verified sales uploads. Missing periods are honestly declared without synthetic fabrication.
            </div>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="pt-4 border-t flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={handleTriggerPreview}
            className="text-xs gap-1.5 h-9"
          >
            <Eye className="w-3.5 h-3.5" />
            Preview Evidence
          </Button>

          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" onClick={onClose} className="text-xs h-9">
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleTriggerGenerate}
              disabled={isGenerating}
              className="text-xs gap-1.5 h-9 shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              {isGenerating ? "Generating..." : `Generate & Download ${selectedFormat.toUpperCase()}`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

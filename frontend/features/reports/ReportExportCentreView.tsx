"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  FileText,
  History,
  Download,
  ShieldCheck,
  RefreshCw,
  Sparkles,
  Layers,
  FileSpreadsheet,
  AlertTriangle,
  Printer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer } from "@/components/layout/PageContainer";
import { ReportCatalogue } from "./ReportCatalogue";
import { ReportConfigModal } from "./ReportConfigModal";
import { ReportPreviewModal } from "./ReportPreviewModal";
import { ReportHistoryTable } from "./ReportHistoryTable";
import {
  reportsService,
  type ReportCatalogItem,
  type ReportCatalogResponse,
  type ReportPreviewResponse,
  type ReportItemOut,
  type ReportFileFormat,
  type ReportGenerateRequest,
  type ReportPreviewRequest,
} from "@/services";

interface ReportExportCentreViewProps {
  onSwitchToPrintView?: () => void;
}

export function ReportExportCentreView({ onSwitchToPrintView }: ReportExportCentreViewProps) {
  const [activeTab, setActiveTab] = useState<"catalog" | "history">("catalog");
  const [catalog, setCatalog] = useState<ReportCatalogItem[]>([]);
  const [history, setHistory] = useState<ReportItemOut[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [configItem, setConfigItem] = useState<ReportCatalogItem | null>(null);
  const [previewData, setPreviewData] = useState<ReportPreviewResponse | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [bannerMessage, setBannerMessage] = useState<{ type: "success" | "error"; text: string } | null>(
    null
  );

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [catRes, histRes] = await Promise.all([
        reportsService.getCatalog(),
        reportsService.getHistory(1, 20),
      ]);
      setCatalog(catRes.catalog || []);
      setHistory(histRes.items || []);
      setHistoryTotal(histRes.total || 0);
    } catch (err: any) {
      setError(err?.message || "Failed to load report export catalogue.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (page: number) => {
    setIsHistoryLoading(true);
    try {
      const histRes = await reportsService.getHistory(page, 20);
      setHistory(histRes.items || []);
      setHistoryTotal(histRes.total || 0);
      setHistoryPage(page);
    } catch (err: any) {
      setBannerMessage({ type: "error", text: "Failed to refresh export history." });
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenConfig = (item: ReportCatalogItem) => {
    setConfigItem(item);
  };

  const handleTriggerPreview = async (req: ReportPreviewRequest) => {
    try {
      const preview = await reportsService.previewReport(req);
      setPreviewData(preview);
      setIsPreviewOpen(true);
      setConfigItem(null);
    } catch (err: any) {
      setBannerMessage({
        type: "error",
        text: err?.message || "Failed to fetch report preview.",
      });
    }
  };

  const handleTriggerGenerate = async (req: ReportGenerateRequest) => {
    setIsGenerating(true);
    try {
      const generated = await reportsService.generateReport(req);
      setBannerMessage({
        type: "success",
        text: `Successfully generated ${generated.title} (${generated.file_format.toUpperCase()}). Initiating download...`,
      });
      setConfigItem(null);
      setIsPreviewOpen(false);

      // Trigger direct download
      await reportsService.downloadReport(
        generated.id,
        `${generated.report_type}_${generated.period_start}_to_${generated.period_end}.${generated.file_format}`
      );

      // Refresh export history
      await loadHistory(1);
    } catch (err: any) {
      setBannerMessage({
        type: "error",
        text: err?.message || "Report generation failed. Please verify source data and try again.",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadHistorical = async (report: ReportItemOut) => {
    try {
      await reportsService.downloadReport(
        report.id,
        `${report.report_type}_${report.period_start}_to_${report.period_end}.${report.file_format}`
      );
      // Refresh count
      loadHistory(historyPage);
    } catch (err: any) {
      setBannerMessage({ type: "error", text: "Download failed." });
    }
  };

  const handleDeleteHistorical = async (id: number) => {
    try {
      await reportsService.deleteReport(id);
      setBannerMessage({ type: "success", text: "Report export archived successfully." });
      loadHistory(historyPage);
    } catch (err: any) {
      setBannerMessage({ type: "error", text: "Failed to archive report." });
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <div className="space-y-6 max-w-7xl mx-auto py-8">
          <LoadingSkeleton />
        </div>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <div className="max-w-7xl mx-auto py-8">
          <ErrorState
            title="Unable to load Report Centre"
            description={error}
            actionLabel="Try again"
            onAction={loadData}
          />
        </div>
      </PageContainer>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto py-4 sm:py-8 px-4 sm:px-6">
      {/* Banner Notifications */}
      {bannerMessage && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between gap-3 text-xs ${
            bannerMessage.type === "success"
              ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800"
              : "bg-rose-500/10 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-800"
          }`}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 shrink-0" />
            <span>{bannerMessage.text}</span>
          </div>
          <button
            onClick={() => setBannerMessage(null)}
            className="text-xs font-semibold underline hover:opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Hero Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-primary">
              Phase 6.25 Extension Pack
            </span>
            <Badge variant="outline" className="text-[10px] font-semibold">
              Evidence-Backed Exports
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">
            Reports & Evidence Export Centre
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground max-w-3xl">
            Generate verifiable, reproducible business reports across commercial, strategic, and governance domains. All figures are deterministically calculated with immutable audit snapshots.
          </p>
        </div>

        {onSwitchToPrintView && (
          <Button
            variant="outline"
            size="sm"
            onClick={onSwitchToPrintView}
            className="text-xs gap-1.5 h-9 shrink-0 shadow-sm"
          >
            <Printer className="w-3.5 h-3.5" />
            Interactive Print Briefing
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-3 border-b">
        <button
          type="button"
          onClick={() => setActiveTab("catalog")}
          className={`flex items-center gap-2 pb-3 px-1 text-sm font-semibold border-b-2 transition-all ${
            activeTab === "catalog"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="w-4 h-4" />
          Report Catalogue ({catalog.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("history")}
          className={`flex items-center gap-2 pb-3 px-1 text-sm font-semibold border-b-2 transition-all ${
            activeTab === "history"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <History className="w-4 h-4" />
          Export History ({historyTotal})
        </button>
      </div>

      {/* Main Tab Content */}
      {activeTab === "catalog" ? (
        <ReportCatalogue
          catalog={catalog}
          onSelectPreview={(item) =>
            handleTriggerPreview({
              report_type: item.report_type,
            })
          }
          onSelectGenerate={handleOpenConfig}
        />
      ) : (
        <ReportHistoryTable
          reports={history}
          total={historyTotal}
          page={historyPage}
          pageSize={20}
          isLoading={isHistoryLoading}
          onRefresh={() => loadHistory(historyPage)}
          onDownload={handleDownloadHistorical}
          onDelete={handleDeleteHistorical}
          onPageChange={loadHistory}
        />
      )}

      {/* Modals */}
      {configItem && (
        <ReportConfigModal
          reportItem={configItem}
          isOpen={true}
          onClose={() => setConfigItem(null)}
          onPreview={handleTriggerPreview}
          onGenerate={handleTriggerGenerate}
          isGenerating={isGenerating}
        />
      )}

      {previewData && (
        <ReportPreviewModal
          preview={previewData}
          isOpen={isPreviewOpen}
          onClose={() => {
            setIsPreviewOpen(false);
            setPreviewData(null);
          }}
          onProceedToGenerate={(fmt) => {
            handleTriggerGenerate({
              report_type: previewData.report_type,
              file_format: fmt,
              period_start: previewData.period_start,
              period_end: previewData.period_end,
              include_ai_summary: true,
            });
          }}
          isGenerating={isGenerating}
        />
      )}
    </div>
  );
}

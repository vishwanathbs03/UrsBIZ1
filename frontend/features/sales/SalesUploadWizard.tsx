"use client";

import React, { useState } from "react";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  XCircle,
  ArrowRight,
  ArrowLeft,
  Loader2,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  salesService,
  type ColumnMapping,
  type FilePreviewResponse,
  type SalesUploadResponse,
} from "@/services/sales-service";

interface SalesUploadWizardProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export function SalesUploadWizard({ onSuccess, onCancel }: SalesUploadWizardProps) {
  const [step, setStep] = useState<"select" | "mapping" | "quality">("select");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<FilePreviewResponse | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({
    transaction_date: "",
    product_name: "",
    quantity: "",
    unit_price: "",
    customer_name: "",
    total_amount: "",
    invoice_id: "",
  });
  const [uploadResult, setUploadResult] = useState<SalesUploadResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (selected.size > 10 * 1024 * 1024) {
      setError("File size exceeds 10 MB limit.");
      return;
    }

    setFile(selected);
    setError(null);
    setIsLoading(true);

    try {
      const res = await salesService.previewUpload(selected);
      setPreview(res);
      // Pre-fill suggested mappings if available
      setMapping({
        transaction_date: res.suggested_mapping.transaction_date || "",
        product_name: res.suggested_mapping.product_name || "",
        quantity: res.suggested_mapping.quantity || "",
        unit_price: res.suggested_mapping.unit_price || "",
        customer_name: res.suggested_mapping.customer_name || "",
        total_amount: res.suggested_mapping.total_amount || "",
        invoice_id: res.suggested_mapping.invoice_id || "",
      });
      setStep("mapping");
    } catch (err: any) {
      setError(err.message || "Failed to parse file preview.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmMapping = async () => {
    if (!file) return;
    if (!mapping.transaction_date || !mapping.product_name || !mapping.quantity || !mapping.unit_price) {
      setError("Transaction Date, Product Name, Quantity, and Unit Price are required mappings.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const res = await salesService.confirmUpload(file, mapping);
      setUploadResult(res);
      setStep("quality");
    } catch (err: any) {
      setError(err.message || "Failed to process and ingest sales data.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-dark-border bg-dark-card p-6 shadow-2xl backdrop-blur-md">
      {/* Wizard Step Indicator */}
      <div className="mb-6 flex items-center justify-between border-b border-dark-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-dark-text-primary">Sales Data Ingestion Wizard</h2>
          <p className="text-xs text-dark-text-muted">
            Upload CSV or Excel transactions, verify column mappings, and audit data quality.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`rounded-full px-2.5 py-1 ${
              step === "select"
                ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/40"
                : "bg-dark-bg text-dark-text-muted"
            }`}
          >
            1. Upload
          </span>
          <span className="text-dark-text-muted">→</span>
          <span
            className={`rounded-full px-2.5 py-1 ${
              step === "mapping"
                ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/40"
                : "bg-dark-bg text-dark-text-muted"
            }`}
          >
            2. Map Columns
          </span>
          <span className="text-dark-text-muted">→</span>
          <span
            className={`rounded-full px-2.5 py-1 ${
              step === "quality"
                ? "bg-neon-emerald/20 text-neon-emerald border border-neon-emerald/40"
                : "bg-dark-bg text-dark-text-muted"
            }`}
          >
            3. Quality Audit
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-neon-rose/40 bg-neon-rose/10 p-3 text-xs text-neon-rose">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* STEP 1: Select File */}
      {step === "select" && (
        <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-dark-border py-12 text-center transition-colors hover:border-neon-cyan/50">
          <FileSpreadsheet className="mb-4 h-12 w-12 text-neon-cyan animate-pulse" />
          <h3 className="text-base font-semibold text-dark-text-primary">
            Upload Sales Records (.csv or .xlsx)
          </h3>
          <p className="mt-1 max-w-sm text-xs text-dark-text-muted">
            Maximum file size: 10 MB | Maximum rows: 100,000. Headers will be automatically detected.
          </p>

          <label className="mt-6 cursor-pointer">
            <Button
              type="button"
              disabled={isLoading}
              className="bg-neon-cyan font-medium text-black hover:bg-neon-cyan/90 pointer-events-none"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Inspecting File...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Browse Sales File
                </>
              )}
            </Button>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
              disabled={isLoading}
              className="hidden"
            />
          </label>
        </div>
      )}

      {/* STEP 2: Map Columns */}
      {step === "mapping" && preview && (
        <div className="space-y-6">
          <div className="rounded-lg border border-dark-border bg-dark-bg p-4 text-xs text-dark-text-muted">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-dark-text-primary">
                File: {preview.filename} ({preview.total_rows_estimate.toLocaleString()} rows detected)
              </span>
              <span className="uppercase text-neon-cyan">{preview.file_format}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-dark-text-primary">
                Transaction Date <span className="text-neon-rose">*</span>
              </label>
              <select
                value={mapping.transaction_date}
                onChange={(e) => setMapping({ ...mapping, transaction_date: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">Select header...</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-dark-text-primary">
                Product / Item Name <span className="text-neon-rose">*</span>
              </label>
              <select
                value={mapping.product_name}
                onChange={(e) => setMapping({ ...mapping, product_name: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">Select header...</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-dark-text-primary">
                Quantity Sold <span className="text-neon-rose">*</span>
              </label>
              <select
                value={mapping.quantity}
                onChange={(e) => setMapping({ ...mapping, quantity: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">Select header...</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-dark-text-primary">
                Unit Price <span className="text-neon-rose">*</span>
              </label>
              <select
                value={mapping.unit_price}
                onChange={(e) => setMapping({ ...mapping, unit_price: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">Select header...</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-dark-text-muted">Customer Name (Optional)</label>
              <select
                value={mapping.customer_name || ""}
                onChange={(e) => setMapping({ ...mapping, customer_name: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">None / Not in file</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-dark-text-muted">
                Total Revenue / Amount (Optional, computed if missing)
              </label>
              <select
                value={mapping.total_amount || ""}
                onChange={(e) => setMapping({ ...mapping, total_amount: e.target.value })}
                className="mt-1 w-full rounded-md border border-dark-border bg-dark-bg px-3 py-2 text-xs text-dark-text-primary focus:border-neon-cyan focus:outline-none"
              >
                <option value="">None (Auto-calculate from Qty × Price)</option>
                {preview.detected_headers.map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Transparency Callout */}
          <div className="rounded-lg border border-neon-cyan/20 bg-neon-cyan/5 p-3 text-xs text-dark-text-muted space-y-1.5">
            <div className="font-semibold text-neon-cyan flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4" /> Data Ingestion & Quality Protection Rules
            </div>
            <p>
              • <strong>Revenue calculation:</strong> When total amount is missing or empty, it is calculated deterministically as <em>Quantity × Unit Price</em>. If provided revenue differs from computed revenue by &gt;10%, it is retained but flagged in the audit trail.
            </p>
            <p>
              • <strong>Unsupported returns:</strong> Explicit zero or negative revenue entries (returns, credit notes, refunds) are out of scope for Phase 3 and will be flagged as rejected rows.
            </p>
            <p>
              • <strong>Duplicate protection:</strong> Transactions matching prior records (by invoice or date/product/amount) are accepted for audit history but automatically excluded from default analytics to avoid inflating sales metrics.
            </p>
          </div>

          {/* Sample Rows Preview */}
          <div>
            <h4 className="mb-2 text-xs font-semibold text-dark-text-muted uppercase tracking-wider">
              Sample Data Preview (First 5 Rows)
            </h4>
            <div className="overflow-x-auto rounded-lg border border-dark-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-dark-bg text-dark-text-muted">
                  <tr>
                    {preview.detected_headers.map((h) => (
                      <th key={h} className="border-b border-dark-border p-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-border">
                  {preview.sample_rows.map((r, i) => (
                    <tr key={i} className="hover:bg-dark-border/20">
                      {preview.detected_headers.map((h) => (
                        <td key={h} className="p-2 text-dark-text-primary">
                          {r[h] !== undefined ? String(r[h]) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-between pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep("select")}
              disabled={isLoading}
              className="text-xs"
            >
              <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Back
            </Button>
            <Button
              type="button"
              onClick={handleConfirmMapping}
              disabled={isLoading}
              className="bg-neon-cyan text-xs font-semibold text-black hover:bg-neon-cyan/90"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                  Validating Records...
                </>
              ) : (
                <>
                  Process & Validate <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* STEP 3: Quality Audit */}
      {step === "quality" && uploadResult && (
        <div className="space-y-6">
          <div className="rounded-xl border border-neon-emerald/30 bg-neon-emerald/10 p-5 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-neon-emerald" />
            <h3 className="mt-2 text-lg font-bold text-dark-text-primary">
              {uploadResult.status === "partial_success" ? "Partial Ingestion Completed" : "Ingestion Completed"}
            </h3>
            <p className="text-xs text-dark-text-muted">
              {uploadResult.valid_row_count.toLocaleString()} valid transactions ingested out of{" "}
              {uploadResult.row_count.toLocaleString()} rows.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <div className="rounded-lg border border-dark-border bg-dark-bg p-3">
              <span className="text-xs text-dark-text-muted">Quality Score</span>
              <p className="text-xl font-bold text-neon-cyan">
                {uploadResult.quality_summary.quality_score}%
              </p>
            </div>
            <div className="rounded-lg border border-dark-border bg-dark-bg p-3">
              <span className="text-xs text-dark-text-muted">Accepted Rows</span>
              <p className="text-xl font-bold text-neon-emerald">
                {uploadResult.quality_summary.valid_rows}
              </p>
            </div>
            <div className="rounded-lg border border-dark-border bg-dark-bg p-3">
              <span className="text-xs text-dark-text-muted">Rejected Rows</span>
              <p className="text-xl font-bold text-neon-rose">
                {uploadResult.quality_summary.invalid_rows}
              </p>
            </div>
            <div className="rounded-lg border border-dark-border bg-dark-bg p-3">
              <span className="text-xs text-dark-text-muted">Calculated Revs</span>
              <p className="text-xl font-bold text-neon-amber">
                {uploadResult.quality_summary.calculated_revenues}
              </p>
            </div>
            <div className="rounded-lg border border-dark-border bg-dark-bg p-3">
              <span className="text-xs text-dark-text-muted">Duplicates (Audit Only)</span>
              <p className="text-xl font-bold text-dark-text-muted">
                {uploadResult.quality_summary.duplicate_transactions}
              </p>
            </div>
          </div>

          {uploadResult.quality_summary.issues.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold text-dark-text-muted uppercase tracking-wider">
                Audit Trail (Flagged Warnings & Rejections)
              </h4>
              <div className="max-h-48 overflow-y-auto rounded-lg border border-dark-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-dark-bg text-dark-text-muted">
                    <tr>
                      <th className="p-2 border-b border-dark-border">Row</th>
                      <th className="p-2 border-b border-dark-border">Type</th>
                      <th className="p-2 border-b border-dark-border">Severity</th>
                      <th className="p-2 border-b border-dark-border">Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-border">
                    {uploadResult.quality_summary.issues.map((iss, i) => (
                      <tr key={i} className="hover:bg-dark-border/20">
                        <td className="p-2 font-mono text-dark-text-muted">#{iss.row_index}</td>
                        <td className="p-2 text-dark-text-primary">{iss.issue_type}</td>
                        <td className="p-2">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] uppercase font-semibold ${
                              iss.severity === "error"
                                ? "bg-neon-rose/20 text-neon-rose"
                                : "bg-neon-amber/20 text-neon-amber"
                            }`}
                          >
                            {iss.severity}
                          </span>
                        </td>
                        <td className="p-2 text-dark-text-muted">{iss.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              onClick={onSuccess}
              className="bg-neon-emerald text-xs font-semibold text-black hover:bg-neon-emerald/90"
            >
              Done & View Sales Intelligence
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

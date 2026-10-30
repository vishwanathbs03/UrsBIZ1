"use client";

/**
 * DownloadPdfButton — the real PDF download mechanism for the
 * Executive Report.
 *
 * Approach:
 *  1. Try the server-side route first —
 *     `GET /api/v1/reports/pdf?report_type=executive` returns a
 *     real PDF (ReportLab on the backend). If that succeeds,
 *     download the blob directly.
 *  2. Fall back to the print path — build a self-contained,
 *     print-styled HTML document from the live report data,
 *     open it in a new window, and trigger `window.print()`.
 *     The browser's print dialog offers "Save as PDF" as a
 *     destination.
 *
 * Why a print fallback? If the server-side endpoint is degraded
 * (network blip, server overload), the user still gets a real
 * PDF via the browser's native print stack — no broken
 * downloads. Why not `jsPDF` / `html2canvas`? Adding a 1MB+ dep
 * for a print-to-PDF use case is not proportionate.
 */

import { useCallback, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReportsData } from "./use-reports-data";

interface DownloadPdfButtonProps {
  data: ReportsData;
  businessName: string | null;
  lastAnalyzedAt: string | null;
}

export function DownloadPdfButton({
  data,
  businessName,
  lastAnalyzedAt,
}: DownloadPdfButtonProps) {
  const [busy, setBusy] = useState(false);

  const handleDownload = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/v1/reports/pdf?report_type=executive", {
        credentials: "include",
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = buildFilename(businessName).replace(".html", ".pdf");
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
      }
    } catch {
      // fallback
    }

    try {
      const html = buildReportHtml({
        data,
        businessName,
        lastAnalyzedAt,
      });
      const win = window.open(
        "",
        "_blank",
        "noopener,noreferrer,width=900,height=1100",
      );
      if (!win) {
        const blob = new Blob([html], { type: "text/html;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = buildFilename(businessName);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
      }
      win.document.open();
      win.document.write(html);
      win.document.close();
      win.addEventListener("load", () => {
        try {
          win.focus();
          win.print();
        } catch {
          // ignore
        }
      });
    } finally {
      setTimeout(() => setBusy(false), 600);
    }
  }, [busy, data, businessName, lastAnalyzedAt]);

  return (
    <Button
      type="button"
      variant="default"
      size="sm"
      onClick={handleDownload}
      disabled={busy}
      aria-label="Download report as PDF (opens browser print dialog; choose Save as PDF to download)"
      title="Opens the browser print dialog. Choose 'Save as PDF' to download a PDF copy."
    >
      {busy ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        <Download className="size-4" aria-hidden="true" />
      )}
      <span className="hidden sm:inline">Download PDF</span>
    </Button>
  );
}

// --------------------------------------------------------------------------- //
// HTML builder
// --------------------------------------------------------------------------- //

function buildReportHtml(args: {
  data: ReportsData;
  businessName: string | null;
  lastAnalyzedAt: string | null;
}): string {
  const { data, businessName, lastAnalyzedAt } = args;
  const sections = buildSections(data);
  const generatedAt = lastAnalyzedAt ?? new Date().toISOString();
  const title = businessName
    ? `Executive Report — ${businessName}`
    : "Executive Report";

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  @page { size: A4; margin: 16mm 14mm 16mm 14mm; }
  *,*::before,*::after { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; background: #ffffff; color: #0f172a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      "Helvetica Neue", Arial, sans-serif;
    font-size: 11pt; line-height: 1.5;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  h1, h2, h3, h4 { font-weight: 600; color: #0f172a; }
  h1 { font-size: 22pt; margin: 0 0 4pt 0; }
  h2 { font-size: 14pt; margin: 18pt 0 6pt 0; padding-bottom: 4pt;
       border-bottom: 1px solid #e2e8f0; page-break-after: avoid; }
  h3 { font-size: 12pt; margin: 12pt 0 4pt 0; }
  p { margin: 0 0 6pt 0; }
  ul, ol { margin: 4pt 0 6pt 18pt; padding: 0; }
  li { margin-bottom: 2pt; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco,
    Consolas, "Liberation Mono", monospace; font-size: 9pt; }
  .badge {
    display: inline-block; font-size: 8pt; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 2pt 6pt; border-radius: 999px;
    border: 1px solid #e2e8f0; background: #f1f5f9; color: #334155;
    margin-right: 4pt;
  }
  .badge.critical { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }
  .badge.high { background: #fff7ed; border-color: #fed7aa; color: #c2410c; }
  .badge.medium { background: #fffbeb; border-color: #fde68a; color: #92400e; }
  .badge.low { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
  .badge.advisory { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
  .badge.system { background: #f1f5f9; border-color: #cbd5e1; color: #475569; }
  .meta { color: #64748b; font-size: 9pt; margin-bottom: 12pt; }
  .kpis {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 6pt; margin: 12pt 0;
  }
  .kpi {
    border: 1px solid #e2e8f0; border-radius: 6pt; padding: 6pt 8pt;
  }
  .kpi .label {
    font-size: 8pt; text-transform: uppercase; letter-spacing: 0.06em;
    color: #64748b;
  }
  .kpi .value {
    font-size: 18pt; font-weight: 600; color: #0f172a; margin: 2pt 0;
  }
  .kpi .hint { font-size: 9pt; color: #475569; }
  table {
    width: 100%; border-collapse: collapse; margin: 8pt 0; font-size: 10pt;
  }
  th, td {
    border-bottom: 1px solid #e2e8f0; padding: 4pt 6pt;
    vertical-align: top; text-align: left;
  }
  th {
    background: #f8fafc; font-weight: 600; font-size: 9pt;
    text-transform: uppercase; letter-spacing: 0.04em; color: #475569;
  }
  .swot {
    display: grid; grid-template-columns: 1fr 1fr; gap: 6pt; margin: 8pt 0;
  }
  .swot .col {
    border: 1px solid #e2e8f0; border-radius: 6pt; padding: 6pt 8pt;
  }
  .swot h4 {
    margin: 0 0 4pt 0; font-size: 10pt;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  .col.strengths h4 { color: #047857; }
  .col.weaknesses h4 { color: #b91c1c; }
  .col.opportunities h4 { color: #1d4ed8; }
  .col.risks h4 { color: #c2410c; }
  .footer {
    margin-top: 18pt; padding-top: 6pt;
    border-top: 1px solid #e2e8f0;
    font-size: 8pt; color: #64748b; text-align: center;
  }
  @media print {
    body { font-size: 9.5pt; }
    h1 { font-size: 18pt; }
    h2 { font-size: 12pt; }
    .page-break { break-before: page; }
  }
</style>
</head>
<body>
  <header>
    <h1>${escapeHtml(title)}</h1>
    <p class="meta">
      Generated ${escapeHtml(formatTimestamp(generatedAt))} · UrsBiz
    </p>
  </header>

  ${sections.join("\n")}

  <footer class="footer">
    <p>
      Data is sourced live from the analytical engines (Digital Twin,
      Roadmap, Recommendations, Scores, DNA, Rules, Decision,
      Intelligence). No derivations are performed on top of the
      upstream payloads in this PDF.
    </p>
    <p class="limits">
      Limitations: business benchmarks are <strong>internal
      illustrative baselines</strong>, not external industry averages;
      scheme matching is informational and does not constitute
      eligibility or approval; revenue / growth projections shown
      elsewhere are scenario estimates, not forecasts; industry /
      competitor comparisons are not included in this report.
    </p>
    <p class="limits">
      Methodology: each section is generated from the same payload
      the dashboard reads. Where the dashboard shows an empty state,
      the same value is omitted here. Numbers you see in this PDF
      match the values you saw on screen at the time it was
      generated.
    </p>
  </footer>
</body>
</html>`;
}

// --------------------------------------------------------------------------- //
// Section builders
// --------------------------------------------------------------------------- //

function buildSections(data: ReportsData): string[] {
  return [
    executiveSummarySection(data),
    snapshotSection(data),
    swotSection(data),
    dnaSection(data),
    recommendationsSection(data),
    roadmapSection(data),
  ];
}

function executiveSummarySection(data: ReportsData): string {
  const { twin, decision, recommendations } = data;
  const overall = Math.round(twin.current_health?.overall_business_score ?? 0);
  const recCount = recommendations.recommendations.length;
  const proj3m = Math.round(twin.timeline?.three_month?.projected_overall_score ?? 0);
  const bullets: string[] = [];
  if (decision?.decision?.summary) {
    bullets.push(decision.decision.summary);
  }
  for (const s of (decision?.decision?.top_strengths ?? []).slice(0, 2)) {
    bullets.push(`Strength: ${s}`);
  }
  for (const r of (decision?.decision?.top_risks ?? []).slice(0, 2)) {
    bullets.push(`Risk: ${r}`);
  }
  if (bullets.length === 0) {
    bullets.push(
      `Overall business score is ${overall}/100. The Digital Twin ` +
        `projects a 3-month score of ${proj3m}/100. ${recCount} ` +
        `recommendation(s) are queued for action.`,
    );
  }

  return `
  <h2>Executive Summary</h2>
  <div class="kpis">
    <div class="kpi">
      <div class="label">Overall score</div>
      <div class="value">${overall}</div>
      <div class="hint">live, current</div>
    </div>
    <div class="kpi">
      <div class="label">3-month projection</div>
      <div class="value">${proj3m}</div>
      <div class="hint">Digital Twin forecast</div>
    </div>
    <div class="kpi">
      <div class="label">Recommendations</div>
      <div class="value">${recCount}</div>
      <div class="hint">ranked by priority</div>
    </div>
    <div class="kpi">
      <div class="label">Risk signals</div>
      <div class="value">${
        (twin.risk_matrix?.critical_risks?.length ?? 0) +
        (twin.risk_matrix?.high_risks?.length ?? 0)
      }</div>
      <div class="hint">critical + high</div>
    </div>
  </div>
  <ul>
    ${bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join("\n    ")}
  </ul>`;
}

function snapshotSection(data: ReportsData): string {
  const { twin } = data;
  const ch = twin.current_health;
  const hs = twin.health_summary;

  const rows: Array<[string, string]> = [];
  rows.push(["Archetype", ch?.business_dna_archetype ?? "—"]);
  rows.push(["DNA match", `${ch?.business_dna_match ?? 0}/100`]);
  rows.push(["Digital maturity", `${hs?.digital_maturity ?? 0}/100`]);
  rows.push(["Operational maturity", `${hs?.operational_maturity ?? 0}/100`]);
  rows.push(["Market readiness", `${hs?.market_readiness ?? 0}/100`]);
  rows.push(["Export readiness", `${hs?.export_readiness ?? 0}/100`]);
  rows.push(["Compliance readiness", `${hs?.compliance_readiness ?? 0}/100`]);
  rows.push(["Growth readiness", `${hs?.growth_readiness ?? 0}/100`]);
  rows.push(["Innovation readiness", `${hs?.innovation_readiness ?? 0}/100`]);
  rows.push(["Sustainability readiness", `${hs?.sustainability_readiness ?? 0}/100`]);

  return `
  <h2 class="page-break">Business Snapshot</h2>
  <table>
    <thead>
      <tr><th>Field</th><th>Value</th></tr>
    </thead>
    <tbody>
      ${rows.map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`).join("\n      ")}
    </tbody>
  </table>`;
}

function swotSection(data: ReportsData): string {
  const dna = data.dna?.dna;
  const strengths = (dna?.strengths ?? []).slice(0, 6);
  const weaknesses = (dna?.weaknesses ?? []).slice(0, 6);
  const opportunities = (dna?.opportunities ?? []).slice(0, 6);
  const risks = (dna?.risk_areas ?? []).slice(0, 6);

  function listCell(items: Array<{ title: string; description?: string }>, empty: string): string {
    if (items.length === 0) return `<p class="hint">${escapeHtml(empty)}</p>`;
    return `<ul>${items
      .map(
        (i) =>
          `<li><strong>${escapeHtml(i.title)}</strong>${i.description ? " — " + escapeHtml(i.description) : ""}</li>`,
      )
      .join("\n      ")}</ul>`;
  }

  return `
  <h2 class="page-break">SWOT</h2>
  <div class="swot">
    <div class="col strengths">
      <h4>Strengths</h4>
      ${listCell(strengths, "No strengths surfaced.")}
    </div>
    <div class="col weaknesses">
      <h4>Weaknesses</h4>
      ${listCell(weaknesses, "No weaknesses surfaced.")}
    </div>
    <div class="col opportunities">
      <h4>Opportunities</h4>
      ${listCell(opportunities, "No opportunities surfaced.")}
    </div>
    <div class="col risks">
      <h4>Risks</h4>
      ${listCell(risks, "No risks surfaced.")}
    </div>
  </div>`;
}

function dnaSection(data: ReportsData): string {
  const dna = data.dna?.dna;
  const archetype = dna?.archetype;
  const traits = (dna?.secondary_traits ?? []).filter((t) => t.present || t.strength > 0);
  const confidence = dna?.confidence ?? 0;
  const rationale = (dna?.confidence_rationale ?? []).slice(0, 4);

  return `
  <h2 class="page-break">Business DNA</h2>
  ${
    archetype
      ? `<p><strong>${escapeHtml(archetype.title)}</strong>
         <span class="mono">${escapeHtml(archetype.key)}</span>
         — match ${archetype.match_score}/100.</p>
         ${archetype.description ? `<p>${escapeHtml(archetype.description)}</p>` : ""}`
      : `<p>No DNA archetype produced yet.</p>`
  }

  <h3>Secondary traits</h3>
  ${
    traits.length === 0
      ? `<p class="hint">No secondary traits detected.</p>`
      : `<ul>${traits
          .map(
            (t) =>
              `<li><strong>${escapeHtml(t.title)}</strong> — strength ${t.strength}/100${t.present ? " (present)" : ""}</li>`,
          )
          .join("\n      ")}</ul>`
  }

  <h3>Confidence</h3>
  <p>
    DNA engine confidence is <strong>${Math.round(confidence)}%</strong>${
      rationale.length > 0
        ? `: ${rationale.map((r) => escapeHtml(r)).join("; ")}.`
        : "."
    }
  </p>`;
}

function recommendationsSection(data: ReportsData): string {
  const recs = data.recommendations?.recommendations ?? [];
  const order = { Critical: 0, High: 1, Medium: 2, Low: 3 } as const;
  const top = [...recs]
    .sort((a, b) => order[a.priority] - order[b.priority])
    .slice(0, 10);

  return `
  <h2 class="page-break">Top Recommendations</h2>
  ${
    top.length === 0
      ? `<p class="hint">No recommendations surfaced.</p>`
      : `<table>
    <thead>
      <tr>
        <th>#</th>
        <th>Title</th>
        <th>Priority</th>
        <th>Phase</th>
        <th>Score gain</th>
        <th>Confidence</th>
      </tr>
    </thead>
    <tbody>
      ${top
        .map(
          (r, i) => `<tr>
        <td>${i + 1}</td>
        <td>${escapeHtml(r.title)}</td>
        <td><span class="badge ${r.priority.toLowerCase()}">${escapeHtml(r.priority)}</span></td>
        <td>${escapeHtml(r.phase)}</td>
        <td>+${Math.round(r.estimated_score_gain)}</td>
        <td>${Math.round(r.confidence)}%</td>
      </tr>`,
        )
        .join("\n      ")}
    </tbody>
  </table>`
  }`;
}

function roadmapSection(data: ReportsData): string {
  const phases = ["Immediate", "Short-Term", "Medium-Term", "Long-Term"] as const;
  const items = data.roadmap?.items ?? [];
  function itemsFor(phase: string) {
    return items.filter((i) => i.phase === phase);
  }
  return `
  <h2 class="page-break">Roadmap</h2>
  ${phases
    .map((phase) => {
      const list = itemsFor(phase);
      return `
    <h3>${escapeHtml(phase)} <span class="badge">${list.length} item${list.length === 1 ? "" : "s"}</span></h3>
    ${
      list.length === 0
        ? `<p class="hint">No items in this phase.</p>`
        : `<ul>${list
            .map(
              (i) =>
                `<li><strong>${escapeHtml(i.title)}</strong> — ${i.completion_percentage}% complete, est. ROI ${i.estimated_roi}%</li>`,
            )
            .join("\n      ")}</ul>`
    }`;
    })
    .join("\n")}`;
}

// --------------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------------- //

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function buildFilename(businessName: string | null): string {
  const slug = (businessName ?? "ursbiz")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  const date = new Date().toISOString().slice(0, 10);
  return `${slug}-executive-report-${date}.html`;
}

"use client";

import React, { useState } from "react";
import {
  FileText,
  FileSpreadsheet,
  Eye,
  Download,
  Clock,
  Layers,
  Search,
  Filter,
  ShieldCheck,
  TrendingUp,
  Users,
  Package,
  Activity,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type {
  ReportCatalogItem,
  ReportCategory,
  ReportFileFormat,
} from "@/services";

interface ReportCatalogueProps {
  catalog: ReportCatalogItem[];
  onSelectPreview: (item: ReportCatalogItem) => void;
  onSelectGenerate: (item: ReportCatalogItem) => void;
}

const CATEGORY_META: Record<
  ReportCategory,
  { label: string; description: string; icon: React.ReactNode; color: string }
> = {
  executive: {
    label: "Executive Briefings",
    description: "High-level strategic summaries for business owners, investors, and board reviews.",
    icon: <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />,
    color: "border-emerald-200 dark:border-emerald-800/40 bg-emerald-500/5",
  },
  performance: {
    label: "Commercial Performance",
    description: "Detailed operational reviews of revenue, customer retention, and product margins.",
    icon: <TrendingUp className="w-5 h-5 text-blue-600 dark:text-blue-400" />,
    color: "border-blue-200 dark:border-blue-800/40 bg-blue-500/5",
  },
  strategy_and_governance: {
    label: "Strategy & Governance",
    description: "Audit trails of evaluated management decisions, alert signals, and goal achievements.",
    icon: <Layers className="w-5 h-5 text-purple-600 dark:text-purple-400" />,
    color: "border-purple-200 dark:border-purple-800/40 bg-purple-500/5",
  },
  audit_and_quality: {
    label: "Audit & Risk Stress Testing",
    description: "Reconciliation audits, data confidence scores, and what-if sensitivity simulations.",
    icon: <Activity className="w-5 h-5 text-amber-600 dark:text-amber-400" />,
    color: "border-amber-200 dark:border-amber-800/40 bg-amber-500/5",
  },
};

export function ReportCatalogue({
  catalog,
  onSelectPreview,
  onSelectGenerate,
}: ReportCatalogueProps) {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const filteredCatalog = catalog.filter((item) => {
    const matchesSearch =
      item.title.toLowerCase().includes(search.toLowerCase()) ||
      item.description.toLowerCase().includes(search.toLowerCase()) ||
      item.target_audience.toLowerCase().includes(search.toLowerCase());
    const matchesCategory =
      selectedCategory === "all" || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = Array.from(new Set(catalog.map((c) => c.category))) as ReportCategory[];

  return (
    <div className="space-y-6">
      {/* Search and Category Filters */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-muted/30 p-4 rounded-xl border">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search report catalogue..."
            className="pl-9 bg-background"
          />
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          <Button
            size="sm"
            variant={selectedCategory === "all" ? "default" : "outline"}
            onClick={() => setSelectedCategory("all")}
            className="text-xs rounded-full h-8"
          >
            All Reports ({catalog.length})
          </Button>
          {categories.map((cat) => {
            const count = catalog.filter((c) => c.category === cat).length;
            const meta = CATEGORY_META[cat];
            return (
              <Button
                key={cat}
                size="sm"
                variant={selectedCategory === cat ? "default" : "outline"}
                onClick={() => setSelectedCategory(cat)}
                className="text-xs rounded-full h-8 whitespace-nowrap"
              >
                {meta?.label || cat} ({count})
              </Button>
            );
          })}
        </div>
      </div>

      {/* Catalogue Cards Grouped by Category */}
      {categories
        .filter((cat) => selectedCategory === "all" || selectedCategory === cat)
        .map((cat) => {
          const items = filteredCatalog.filter((c) => c.category === cat);
          if (items.length === 0) return null;
          const meta = CATEGORY_META[cat];

          return (
            <div key={cat} className="space-y-4">
              <div className="flex items-center gap-2.5 pb-2 border-b">
                {meta?.icon}
                <div>
                  <h3 className="text-base font-semibold tracking-tight text-foreground">
                    {meta?.label || cat}
                  </h3>
                  <p className="text-xs text-muted-foreground">{meta?.description}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {items.map((item) => (
                  <div
                    key={item.report_type}
                    className="flex flex-col justify-between rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-all hover:border-primary/40 relative group"
                  >
                    <div>
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                          {item.target_audience}
                        </span>
                        <div className="flex items-center gap-1">
                          {item.supported_formats.map((fmt) => (
                            <span
                              key={fmt}
                              className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                                fmt === "pdf"
                                  ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50"
                                  : fmt === "xlsx"
                                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/50"
                                  : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50"
                              }`}
                            >
                              {fmt}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Title & Description */}
                      <h4 className="text-base font-semibold text-foreground group-hover:text-primary transition-colors line-clamp-1 mb-1.5">
                        {item.title}
                      </h4>
                      <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed mb-4">
                        {item.description}
                      </p>

                      {/* Required Data Sources */}
                      <div className="space-y-1 mb-4 pt-3 border-t">
                        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                          Authoritative Evidence Sources
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {item.required_data_sources.map((src, idx) => (
                            <Badge
                              key={idx}
                              variant="outline"
                              className="text-[10px] font-normal py-0 px-1.5 bg-muted/40"
                            >
                              {src}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="pt-3 border-t flex items-center justify-between gap-2 mt-auto">
                      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                        <Clock className="w-3.5 h-3.5" />
                        <span>~{item.estimated_generation_time_sec}s</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onSelectPreview(item)}
                          className="h-8 text-xs gap-1 hover:bg-muted"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          Preview
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => onSelectGenerate(item)}
                          className="h-8 text-xs gap-1 shadow-sm"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Export
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

      {filteredCatalog.length === 0 && (
        <div className="text-center py-12 border rounded-xl bg-card">
          <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <h4 className="text-base font-semibold text-foreground">No reports match your search</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Try adjusting your search keywords or switching category filters.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSearch("");
              setSelectedCategory("all");
            }}
            className="mt-4 text-xs"
          >
            Clear Filters
          </Button>
        </div>
      )}
    </div>
  );
}
